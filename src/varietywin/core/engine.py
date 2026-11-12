import logging
import random
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from ..config.schema import AppConfig
from ..platform_win import wallpaper_single
from ..sources.registry import get_source_class
from ..util.paths import cache_dir
from .cache import CacheManager
from .history import HistoryStore
from .models import ImageCandidate

logger = logging.getLogger(__name__)

MAX_ROTATE_ATTEMPTS = 5


class RotationEngine(QObject):
    wallpaper_changed = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.history = HistoryStore()
        self.cache = CacheManager(cache_dir())

        self.current_candidate: ImageCandidate | None = None
        self.current_path: Path | None = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.rotate)
        self._apply_timer_interval()

    def _apply_timer_interval(self) -> None:
        self._timer.setInterval(self.config.general.rotation_interval_seconds * 1000)

    def start(self) -> None:
        self._apply_timer_interval()
        if not self.config.general.paused:
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def set_paused(self, paused: bool) -> None:
        self.config.general.paused = paused
        if paused:
            self._timer.stop()
        else:
            self._timer.start()

    def _active_sources(self) -> list:
        sources = []
        for source_id, source_config in self.config.sources.items():
            if not source_config.enabled:
                continue
            source_cls = get_source_class(source_id)
            if source_cls is None:
                logger.warning("Unknown source id: %s", source_id)
                continue
            sources.append(source_cls(source_config.options))
        return sources

    def rotate(self) -> None:
        sources = self._active_sources()
        if not sources:
            self.error_occurred.emit("No active image sources configured.")
            return

        for _ in range(MAX_ROTATE_ATTEMPTS):
            source = random.choice(sources)
            try:
                candidates = source.fetch_candidates(count=3)
            except Exception as exc:
                logger.exception("Failed to fetch candidates from source '%s'", source.id)
                self.error_occurred.emit(f"{source.display_name}: {exc}")
                continue

            candidates = [c for c in candidates if not self.history.is_banned(c)]
            if not candidates:
                continue

            recent_window = max(1, min(10, len(candidates) - 1))
            recent_keys = self.history.recently_shown_keys(limit=recent_window)
            fresh = [c for c in candidates if f"{c.source_id}:{c.remote_id}" not in recent_keys]
            pool = fresh or candidates

            candidate = random.choice(pool)
            try:
                local_path = source.download(candidate, dest_dir=cache_dir())
                wallpaper_single.set_wallpaper(local_path)
            except Exception as exc:
                logger.exception("Failed to set wallpaper for candidate %s", candidate.remote_id)
                self.error_occurred.emit(str(exc))
                continue

            self.current_candidate = candidate
            self.current_path = local_path
            self.history.record_shown(candidate, local_path)
            self.cache.enforce_limit(protected=self.history.protected_paths())
            self.wallpaper_changed.emit(candidate)
            return

        self.error_occurred.emit("Could not find a new wallpaper after several attempts.")

    def _candidate_from_entry(self, entry) -> ImageCandidate:
        return ImageCandidate(
            source_id=entry.source_id,
            remote_id=entry.remote_id,
            url=entry.url,
            title=entry.title,
        )

    def _apply_history_entry(self, entry) -> None:
        local_path = Path(entry.local_path)
        if not local_path.exists():
            self.error_occurred.emit(f"Image no longer available: {local_path}")
            return
        try:
            wallpaper_single.set_wallpaper(local_path)
        except Exception as exc:
            logger.exception("Failed to set wallpaper from history entry")
            self.error_occurred.emit(str(exc))
            return
        self.current_candidate = self._candidate_from_entry(entry)
        self.current_path = local_path
        self.wallpaper_changed.emit(self.current_candidate)

    def previous(self) -> None:
        entry = self.history.previous_entry()
        if entry is None:
            self.error_occurred.emit("No earlier wallpaper in history.")
            return
        self._apply_history_entry(entry)

    def next_from_history(self) -> bool:
        entry = self.history.next_entry()
        if entry is None:
            return False
        self._apply_history_entry(entry)
        return True

    def toggle_favorite_current(self) -> None:
        if self.current_candidate is None or self.current_path is None:
            return
        if self.history.is_favorite(self.current_candidate):
            self.history.unfavorite(self.current_candidate)
        else:
            self.history.favorite(self.current_candidate, self.current_path)

    def trash_current(self) -> None:
        if self.current_candidate is None:
            return
        self.history.ban(self.current_candidate)
        self.rotate()
