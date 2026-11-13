import hashlib
import logging
import random
import time
from pathlib import Path

from PySide6.QtCore import QDate, QLocale, QObject, QTime, QTimer, Signal
from PySide6.QtGui import QGuiApplication

from ..config.schema import AppConfig
from ..platform_win import wallpaper_multi, wallpaper_single
from ..sources.registry import get_source_class
from ..util.paths import cache_dir
from . import filters, overlay, quality, quotes
from .cache import CacheManager
from .history import HistoryStore
from .models import ImageCandidate

logger = logging.getLogger(__name__)

MAX_ROTATE_ATTEMPTS = 5
FILTERED_SUBDIR = "filtered"
OVERLAY_SUBDIR = "overlay"


def _key(candidate: ImageCandidate) -> str:
    return f"{candidate.source_id}:{candidate.remote_id}"


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

        # What is on screen right now, keyed by monitor id (None = whole desktop).
        self._shown: dict[str | None, tuple[ImageCandidate, Path]] = {}
        self._displayed_files: dict[str | None, Path] = {}
        self._monitor_sizes: dict[str, tuple[int, int]] = {}
        # Images that failed the size/orientation requirements during this run.
        self._rejected: set[tuple[str | None, str]] = set()

        self._quote: quotes.Quote | None = None

        # Redraws the clock at the start of every minute.
        self._clock_timer = QTimer(self)
        self._clock_timer.setSingleShot(True)
        self._clock_timer.timeout.connect(self._on_clock_tick)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.rotate)
        self._apply_timer_interval()

    def _apply_timer_interval(self) -> None:
        self._timer.setInterval(self.config.general.rotation_interval_seconds * 1000)

    def start(self) -> None:
        self._apply_timer_interval()
        if not self.config.general.paused:
            self._timer.start()
        self._schedule_clock_tick()

    def stop(self) -> None:
        self._timer.stop()
        self._clock_timer.stop()

    def set_paused(self, paused: bool) -> None:
        self.config.general.paused = paused
        if paused:
            self._timer.stop()
        else:
            self._timer.start()

    def _active_sources(self) -> list:
        sources = []
        for entry in self.config.sources:
            if not entry.enabled:
                continue
            source_cls = get_source_class(entry.source_id)
            if source_cls is None:
                logger.warning("Unknown source id: %s", entry.source_id)
                continue
            source = source_cls(entry.options)
            source.entry_id = entry.id
            problems = source.validate_config()
            if problems:
                logger.warning("Skipping source '%s': %s", entry.source_id, "; ".join(problems))
                continue
            sources.append(source)
        return sources

    def has_usable_sources(self) -> bool:
        return bool(self._active_sources())

    def _targets(self) -> list[str | None]:
        """Monitor ids to set individually, or [None] for one wallpaper on the whole desktop."""
        if self.config.monitors.same_on_all_monitors:
            return [None]
        try:
            monitors = wallpaper_multi.list_monitors()
        except Exception:
            logger.exception("Could not enumerate monitors, using a single wallpaper")
            return [None]
        if len(monitors) < 2:
            return [None]
        self._monitor_sizes = {m.id: (m.width, m.height) for m in monitors}
        return [m.id for m in monitors]

    def _screen_size(self, target: str | None) -> tuple[int, int] | None:
        if target is not None:
            return self._monitor_sizes.get(target)
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return None
        size = screen.size() * screen.devicePixelRatio()
        return size.width(), size.height()

    def _meets_requirements(self, size: tuple[int, int] | None, target: str | None) -> bool:
        screen = self._screen_size(target)
        if size is None or screen is None:
            return True
        return quality.is_acceptable(size, screen, self.config.requirements)

    def _reject(
        self, candidate: ImageCandidate, target: str | None, local_path: Path | None = None
    ) -> None:
        logger.info("Skipping %s: too small or wrong orientation", _key(candidate))
        self._rejected.add((target, _key(candidate)))
        # Remove the download, but never a file that lives outside our cache (local folders).
        if local_path is not None and local_path.parent == cache_dir():
            local_path.unlink(missing_ok=True)

    def _sources_for(self, target: str | None, sources: list) -> list:
        wanted = self.config.monitors.per_monitor_source_ids.get(target) if target else None
        if wanted:
            matching = [s for s in sources if s.entry_id == wanted]
            if matching:
                return matching
        return sources

    def _display(self, path: Path, target: str | None) -> None:
        shown_file = filters.apply_filters(
            path, self.config.filters, cache_dir() / FILTERED_SUBDIR
        )

        overlay_dir = cache_dir() / OVERLAY_SUBDIR
        quote = self._current_quote()
        clock = self._clock_text()
        screen = self._screen_size(target)
        if (quote or clock) and screen:
            # A fresh file name each time: Windows ignores a wallpaper path it already shows.
            tag = hashlib.sha1((target or "desktop").encode()).hexdigest()[:8]
            shown_file = overlay.render(
                shown_file,
                screen,
                overlay_dir / f"{tag}-{time.time_ns()}.jpg",
                quote=quote,
                clock=clock,
            )

        if target is None:
            wallpaper_single.set_wallpaper(shown_file)
        else:
            wallpaper_multi.set_wallpaper(target, shown_file)

        previous = self._displayed_files.get(target)
        self._displayed_files[target] = shown_file
        if previous and previous != shown_file and previous.parent == overlay_dir:
            previous.unlink(missing_ok=True)

    def _current_quote(self) -> quotes.Quote | None:
        if not self.config.quotes.enabled:
            return None
        if self._quote is None:
            self._advance_quote()
        return self._quote

    def _advance_quote(self) -> None:
        if self.config.quotes.enabled:
            self._quote = quotes.pick(quotes.load(self.config.quotes.file), self._quote)
        else:
            self._quote = None

    def _clock_text(self) -> tuple[str, str] | None:
        if not self.config.clock.enabled:
            return None
        locale = QLocale.system()
        time_text = locale.toString(QTime.currentTime(), QLocale.FormatType.ShortFormat)
        date_text = ""
        if self.config.clock.show_date:
            date_text = locale.toString(QDate.currentDate(), "dddd, d MMMM")
        return time_text, date_text

    def _schedule_clock_tick(self) -> None:
        if not self.config.clock.enabled:
            self._clock_timer.stop()
            return
        now = QTime.currentTime()
        ms_to_next_minute = 60_000 - (now.second() * 1000 + now.msec())
        self._clock_timer.start(ms_to_next_minute + 50)

    def _on_clock_tick(self) -> None:
        if self.config.clock.enabled:
            self._redisplay()
        self._schedule_clock_tick()

    def next_quote(self) -> None:
        self._advance_quote()
        self._redisplay()

    def _pick_and_show(
        self, sources: list, target: str | None, used: set[str]
    ) -> tuple[ImageCandidate, Path] | None:
        for _ in range(MAX_ROTATE_ATTEMPTS):
            source = random.choice(sources)
            try:
                candidates = source.fetch_candidates(count=3)
            except Exception as exc:
                logger.exception("Failed to fetch candidates from source '%s'", source.id)
                self.error_occurred.emit(f"{source.display_name}: {exc}")
                continue

            candidates = [
                c
                for c in candidates
                if not self.history.is_banned(c)
                and _key(c) not in used
                and (target, _key(c)) not in self._rejected
            ]
            if not candidates:
                continue

            recent_window = max(1, min(10, len(candidates) - 1))
            recent_keys = self.history.recently_shown_keys(limit=recent_window)
            fresh = [c for c in candidates if _key(c) not in recent_keys]
            pool = fresh or candidates

            random.shuffle(pool)
            for candidate in pool:
                # Some sources report the size up front, which saves a pointless download.
                reported = quality.parse_resolution(candidate.extra.get("resolution", ""))
                if not self._meets_requirements(reported, target):
                    self._reject(candidate, target)
                    continue
                try:
                    local_path = source.download(candidate, dest_dir=cache_dir())
                    if not self._meets_requirements(quality.image_size(local_path), target):
                        self._reject(candidate, target, local_path)
                        continue
                    self._display(local_path, target)
                except Exception as exc:
                    logger.exception(
                        "Failed to set wallpaper for candidate %s", candidate.remote_id
                    )
                    self.error_occurred.emit(str(exc))
                    break
                return candidate, local_path
        return None

    def _protected_paths(self) -> set[Path]:
        protected = self.history.protected_paths()
        protected.update(p.resolve() for p in self._displayed_files.values())
        protected.update(path.resolve() for _, path in self._shown.values())
        return protected

    def _set_current(self, targets: list[str | None]) -> None:
        for target in targets:
            if target in self._shown:
                self.current_candidate, self.current_path = self._shown[target]
                return

    def rotate(self) -> None:
        sources = self._active_sources()
        if not sources:
            self.error_occurred.emit(
                "No image source is ready. Enable one in Preferences > Sources."
            )
            return

        targets = self._targets()
        self._advance_quote()
        new: dict[str | None, tuple[ImageCandidate, Path]] = {}
        used: set[str] = set()
        for target in targets:
            picked = self._pick_and_show(self._sources_for(target, sources), target, used)
            if picked is not None:
                new[target] = picked
                used.add(_key(picked[0]))

        if not new:
            self.error_occurred.emit(
                "Could not find a new wallpaper after several attempts. If this keeps "
                "happening, relax the image requirements in Preferences > Display."
            )
            return

        self._shown = {t: v for t, v in self._shown.items() if t in targets} | new
        self._displayed_files = {
            t: p for t, p in self._displayed_files.items() if t in self._shown
        }
        # Record the first monitor last so it is the "current" history entry.
        for target in reversed(targets):
            if target in new:
                self.history.record_shown(*new[target])
        self._set_current(targets)
        self.cache.enforce_limit(protected=self._protected_paths())
        self.wallpaper_changed.emit(self.current_candidate)

    def reapply(self) -> None:
        """Redisplay after a settings change (filters or monitor layout)."""
        self._rejected.clear()
        self._schedule_clock_tick()
        targets = self._targets()
        if not self._shown or set(targets) != set(self._shown):
            self.rotate()
            return
        self._advance_quote()
        self._redisplay()

    def _redisplay(self) -> None:
        for target, (_, path) in self._shown.items():
            if not path.exists():
                continue
            try:
                self._display(path, target)
            except Exception as exc:
                logger.exception("Failed to reapply wallpaper %s", path)
                self.error_occurred.emit(str(exc))

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
        # In per-monitor mode history navigation acts on the first monitor.
        target = self._targets()[0]
        try:
            self._display(local_path, target)
        except Exception as exc:
            logger.exception("Failed to set wallpaper from history entry")
            self.error_occurred.emit(str(exc))
            return
        self.current_candidate = self._candidate_from_entry(entry)
        self.current_path = local_path
        if target is None:
            self._shown = {}
        self._shown[target] = (self.current_candidate, local_path)
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
