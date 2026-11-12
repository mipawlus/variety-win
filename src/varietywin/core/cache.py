import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MAX_CACHE_BYTES = 500 * 1024 * 1024


class CacheManager:
    def __init__(self, cache_dir: Path, max_bytes: int = DEFAULT_MAX_CACHE_BYTES):
        self.cache_dir = cache_dir
        self.max_bytes = max_bytes

    def current_size(self) -> int:
        return sum(f.stat().st_size for f in self.cache_dir.rglob("*") if f.is_file())

    def enforce_limit(self, protected: set[Path] | None = None) -> None:
        protected = protected or set()
        total = self.current_size()
        if total <= self.max_bytes:
            return

        candidates = [
            f for f in self.cache_dir.rglob("*") if f.is_file() and f.resolve() not in protected
        ]
        candidates.sort(key=lambda f: f.stat().st_mtime)

        for f in candidates:
            if total <= self.max_bytes:
                break
            try:
                size = f.stat().st_size
                f.unlink()
                total -= size
            except OSError:
                logger.warning("Failed to evict cache file %s", f)
