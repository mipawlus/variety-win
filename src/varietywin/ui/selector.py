"""A window of thumbnails for picking a wallpaper from recent ones or the favorites."""

import logging
from pathlib import Path

from PIL import Image, ImageOps
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QImage, QPixmap
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QTabWidget, QVBoxLayout, QWidget

from ..core.engine import RotationEngine
from ..core.models import ImageCandidate

logger = logging.getLogger(__name__)

THUMBNAIL_SIZE = (208, 130)
MAX_RECENT = 60
THUMBNAILS_PER_TICK = 3
TITLE_LENGTH = 30

Entry = tuple[ImageCandidate, Path]


def make_thumbnail(path: Path, size: tuple[int, int] = THUMBNAIL_SIZE) -> QImage | None:
    try:
        with Image.open(path) as opened:
            # Lets the JPEG decoder work at a fraction of the full size: much faster.
            opened.draft("RGB", (size[0] * 2, size[1] * 2))
            image = ImageOps.exif_transpose(opened).convert("RGB")
        image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)
        data = image.tobytes()
        return QImage(data, size[0], size[1], size[0] * 3, QImage.Format.Format_RGB888).copy()
    except Exception:
        logger.warning("Could not make a thumbnail for %s", path)
        return None


def _short(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= TITLE_LENGTH else text[: TITLE_LENGTH - 1] + "…"


class _ThumbnailList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setIconSize(QSize(*THUMBNAIL_SIZE))
        self.setGridSize(QSize(THUMBNAIL_SIZE[0] + 20, THUMBNAIL_SIZE[1] + 34))
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setWordWrap(False)
        self.setUniformItemSizes(True)
        self.entries: list[Entry] = []

        placeholder = QPixmap(*THUMBNAIL_SIZE)
        placeholder.fill(QColor(90, 90, 90))
        self._placeholder = QIcon(placeholder)

    def set_entries(self, entries: list[Entry]) -> None:
        self.clear()
        self.entries = entries
        for candidate, path in entries:
            title = candidate.title or path.stem
            item = QListWidgetItem(self._placeholder, _short(title))
            item.setToolTip(title)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            self.addItem(item)


class WallpaperSelector(QWidget):
    def __init__(self, engine: RotationEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("Variety for Windows - Choose wallpaper")
        self.resize(990, 580)  # four thumbnails per row

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.recent_list = _ThumbnailList()
        self.favorites_list = _ThumbnailList()
        self.tabs.addTab(self.recent_list, "Recent")
        self.tabs.addTab(self.favorites_list, "Favorites")
        layout.addWidget(self.tabs)

        for thumbnails in (self.recent_list, self.favorites_list):
            thumbnails.itemClicked.connect(
                lambda item, source=thumbnails: self._on_clicked(source, item)
            )

        # Thumbnails are made a few at a time so the window stays responsive.
        self._pending: list[tuple[_ThumbnailList, int, Path]] = []
        self._loader = QTimer(self)
        self._loader.setInterval(0)
        self._loader.timeout.connect(self._load_some)

    def refresh(self) -> None:
        self.recent_list.set_entries(self.engine.history.recent_entries(MAX_RECENT))
        self.favorites_list.set_entries(self.engine.history.favorite_entries())
        self.tabs.setTabText(1, f"Favorites ({len(self.favorites_list.entries)})")
        self._pending = [
            (thumbnails, row, path)
            for thumbnails in (self.recent_list, self.favorites_list)
            for row, (_, path) in enumerate(thumbnails.entries)
        ]
        self._loader.start()

    def _load_some(self) -> None:
        for _ in range(THUMBNAILS_PER_TICK):
            if not self._pending:
                self._loader.stop()
                return
            thumbnails, row, path = self._pending.pop(0)
            image = make_thumbnail(path)
            item = thumbnails.item(row)
            if image is not None and item is not None:
                item.setIcon(QIcon(QPixmap.fromImage(image)))

    def _on_clicked(self, thumbnails: _ThumbnailList, item: QListWidgetItem) -> None:
        row = thumbnails.row(item)
        if 0 <= row < len(thumbnails.entries):
            candidate, path = thumbnails.entries[row]
            self.engine.show_image(candidate, path)

    def show_and_refresh(self) -> None:
        self.refresh()
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:
        self._loader.stop()
        self._pending.clear()
        super().closeEvent(event)
