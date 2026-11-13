import os

from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QStyle, QSystemTrayIcon

from ..core.engine import RotationEngine
from ..core.models import ImageCandidate
from .preferences.window import PreferencesWindow


class TrayIcon(QSystemTrayIcon):
    def __init__(self, engine: RotationEngine, parent=None):
        style = QApplication.instance().style()
        icon = style.standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)
        super().__init__(icon, parent)
        self.engine = engine
        self._preferences: PreferencesWindow | None = None

        self.setToolTip("Variety for Windows")

        self.menu = QMenu()
        self.next_action = self.menu.addAction("Next wallpaper", self._on_next)
        self.previous_action = self.menu.addAction("Previous wallpaper", self._on_previous)
        self.pause_action = self.menu.addAction("Pause", self._on_toggle_pause)
        self.quote_action = self.menu.addAction("Next quote", self.engine.next_quote)
        self.menu.addSeparator()
        self.favorite_action = self.menu.addAction("Favorite", self._on_toggle_favorite)
        self.favorite_action.setCheckable(True)
        self.menu.addAction("Trash (never show again)", self._on_trash)
        self.menu.addAction("Open containing folder", self._on_open_folder)
        self.menu.addAction("Image info...", self._on_show_info)
        self.menu.addSeparator()
        self.menu.addAction("Preferences...", self._on_open_preferences)
        self.menu.addSeparator()
        self.menu.addAction("Quit", self._on_quit)
        self.setContextMenu(self.menu)

        self.engine.wallpaper_changed.connect(self._on_wallpaper_changed)
        self.engine.error_occurred.connect(self._on_error)

        self._update_pause_label()
        self._update_favorite_state()

    def _on_next(self) -> None:
        if not self.engine.next_from_history():
            self.engine.rotate()

    def _on_previous(self) -> None:
        self.engine.previous()

    def _on_toggle_pause(self) -> None:
        self.engine.set_paused(not self.engine.config.general.paused)
        self._update_pause_label()

    def _update_pause_label(self) -> None:
        self.quote_action.setVisible(self.engine.config.quotes.enabled)
        paused = self.engine.config.general.paused
        self.pause_action.setText("Resume" if paused else "Pause")

    def _on_toggle_favorite(self) -> None:
        self.engine.toggle_favorite_current()
        self._update_favorite_state()

    def _update_favorite_state(self) -> None:
        candidate = self.engine.current_candidate
        is_fav = candidate is not None and self.engine.history.is_favorite(candidate)
        self.favorite_action.setChecked(is_fav)

    def _on_trash(self) -> None:
        self.engine.trash_current()

    def _on_open_folder(self) -> None:
        path = self.engine.current_path
        if path is not None and path.exists():
            os.startfile(path.parent)

    def _on_show_info(self) -> None:
        candidate = self.engine.current_candidate
        if candidate is None:
            QMessageBox.information(None, "Variety for Windows", "No wallpaper shown yet.")
            return
        lines = [
            f"Title: {candidate.title or '(none)'}",
            f"Source: {candidate.source_id}",
        ]
        if candidate.author:
            lines.append(f"Author: {candidate.author}")
        if candidate.source_page_url:
            lines.append(f"Page: {candidate.source_page_url}")
        QMessageBox.information(None, "Image info", "\n".join(lines))

    def _on_open_preferences(self) -> None:
        self.open_preferences()

    def open_preferences(self, initial_tab: str | None = None) -> None:
        if self._preferences is not None:
            self._preferences.raise_()
            self._preferences.activateWindow()
            return

        def _on_saved() -> None:
            self.engine.start()
            self.engine.reapply()
            self._update_pause_label()

        self._preferences = PreferencesWindow(
            self.engine.config, on_saved=_on_saved, initial_tab=initial_tab
        )
        try:
            self._preferences.exec()
        finally:
            self._preferences = None

    def handle_command(self, command: str) -> None:
        """Run a command received from the command line (see ipc.COMMANDS)."""
        paused = self.engine.config.general.paused
        handlers = {
            "next": self._on_next,
            "previous": self._on_previous,
            "pause": lambda: paused or self._on_toggle_pause(),
            "resume": lambda: paused and self._on_toggle_pause(),
            "toggle-pause": self._on_toggle_pause,
            "favorite": self._on_toggle_favorite,
            "trash": self._on_trash,
            "preferences": self._on_open_preferences,
            "quit": self._on_quit,
        }
        handler = handlers.get(command)
        if handler is not None:
            handler()

    def _on_quit(self) -> None:
        QApplication.instance().quit()

    def _on_wallpaper_changed(self, candidate: ImageCandidate) -> None:
        title = candidate.title or candidate.remote_id
        self.setToolTip(f"Variety for Windows\n{title}")
        self._update_favorite_state()

    def _on_error(self, message: str) -> None:
        self.showMessage("Variety for Windows", message, QSystemTrayIcon.MessageIcon.Warning, 5000)
