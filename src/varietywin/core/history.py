import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from ..util.paths import favorites_dir, history_file
from .models import ImageCandidate

logger = logging.getLogger(__name__)

MAX_HISTORY_ENTRIES = 500
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}


def _key(source_id: str, remote_id: str) -> str:
    return f"{source_id}:{remote_id}"


class HistoryEntry(BaseModel):
    source_id: str
    remote_id: str
    url: str
    title: str = ""
    local_path: str
    shown_at: str


class HistoryData(BaseModel):
    shown: list[HistoryEntry] = Field(default_factory=list)
    favorites: list[str] = Field(default_factory=list)
    banned: list[str] = Field(default_factory=list)


class HistoryStore:
    def __init__(self) -> None:
        self._path = history_file()
        self._data = self._load()
        self._position = len(self._data.shown)

    def _load(self) -> HistoryData:
        if self._path.exists():
            try:
                return HistoryData.model_validate_json(self._path.read_text(encoding="utf-8"))
            except Exception:
                logger.exception("Failed to load history from %s, starting fresh", self._path)
        return HistoryData()

    def _save(self) -> None:
        self._path.write_text(self._data.model_dump_json(indent=2), encoding="utf-8")

    def is_banned(self, candidate: ImageCandidate) -> bool:
        return _key(candidate.source_id, candidate.remote_id) in self._data.banned

    def is_favorite(self, candidate: ImageCandidate) -> bool:
        return _key(candidate.source_id, candidate.remote_id) in self._data.favorites

    def recently_shown_keys(self, limit: int = 10) -> set[str]:
        return {
            _key(entry.source_id, entry.remote_id) for entry in self._data.shown[-limit:]
        }

    def protected_paths(self) -> set[Path]:
        paths = set()
        for entry in self._data.shown[-5:]:
            paths.add(Path(entry.local_path).resolve())
        return paths

    def record_shown(self, candidate: ImageCandidate, local_path: Path) -> None:
        entry = HistoryEntry(
            source_id=candidate.source_id,
            remote_id=candidate.remote_id,
            url=candidate.url,
            title=candidate.title,
            local_path=str(local_path),
            shown_at=datetime.now(timezone.utc).isoformat(),
        )
        self._data.shown.append(entry)
        if len(self._data.shown) > MAX_HISTORY_ENTRIES:
            self._data.shown = self._data.shown[-MAX_HISTORY_ENTRIES:]
        self._position = len(self._data.shown)
        self._save()

    def ban(self, candidate: ImageCandidate) -> None:
        key = _key(candidate.source_id, candidate.remote_id)
        if key not in self._data.banned:
            self._data.banned.append(key)
        if key in self._data.favorites:
            self._data.favorites.remove(key)
        self._save()

    def favorite(self, candidate: ImageCandidate, local_path: Path) -> Path:
        key = _key(candidate.source_id, candidate.remote_id)
        dest = favorites_dir() / local_path.name
        if not dest.exists():
            shutil.copy2(local_path, dest)
        if key not in self._data.favorites:
            self._data.favorites.append(key)
        self._save()
        return dest

    def unfavorite(self, candidate: ImageCandidate) -> None:
        key = _key(candidate.source_id, candidate.remote_id)
        if key in self._data.favorites:
            self._data.favorites.remove(key)
            self._save()

    @staticmethod
    def _candidate(entry: HistoryEntry) -> ImageCandidate:
        return ImageCandidate(
            source_id=entry.source_id,
            remote_id=entry.remote_id,
            url=entry.url,
            title=entry.title,
        )

    def recent_entries(self, limit: int) -> list[tuple[ImageCandidate, Path]]:
        """Most recently shown first, each image once, only those still on disk."""
        seen: set[str] = set()
        result: list[tuple[ImageCandidate, Path]] = []
        for entry in reversed(self._data.shown):
            key = _key(entry.source_id, entry.remote_id)
            if key in seen or key in self._data.banned:
                continue
            seen.add(key)
            path = Path(entry.local_path)
            if path.exists():
                result.append((self._candidate(entry), path))
                if len(result) >= limit:
                    break
        return result

    def favorite_entries(self) -> list[tuple[ImageCandidate, Path]]:
        """Images in the favorites folder, newest first, with their details where known."""
        by_file_name = {Path(entry.local_path).name: entry for entry in self._data.shown}
        files = [
            path
            for path in favorites_dir().iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        ]
        files.sort(key=lambda path: path.stat().st_mtime, reverse=True)

        result = []
        for path in files:
            entry = by_file_name.get(path.name)
            if entry is not None:
                candidate = self._candidate(entry)
            else:
                candidate = ImageCandidate(
                    source_id="favorites", remote_id=path.name, url=str(path), title=path.stem
                )
            result.append((candidate, path))
        return result

    def current_entry(self) -> HistoryEntry | None:
        if not self._data.shown or self._position < 1:
            return None
        return self._data.shown[self._position - 1]

    def previous_entry(self) -> HistoryEntry | None:
        if self._position <= 1:
            return None
        self._position -= 1
        return self._data.shown[self._position - 1]

    def next_entry(self) -> HistoryEntry | None:
        if self._position >= len(self._data.shown):
            return None
        entry = self._data.shown[self._position]
        self._position += 1
        return entry

    def at_latest(self) -> bool:
        return self._position >= len(self._data.shown)
