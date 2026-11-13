import hashlib
import logging
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from ..config.schema import FilterConfig

logger = logging.getLogger(__name__)

# Blur radius as a fraction of the image's longer edge, so the look is resolution independent.
BLUR_RADIUS_FRACTION = 0.012


def is_active(filters: FilterConfig) -> bool:
    return filters.blur or filters.grayscale or abs(filters.brightness - 1.0) > 0.005


def _signature(filters: FilterConfig) -> str:
    raw = f"b{int(filters.blur)}g{int(filters.grayscale)}l{filters.brightness:.2f}"
    return hashlib.sha1(raw.encode()).hexdigest()[:8]


def apply_filters(source: Path, filters: FilterConfig, out_dir: Path) -> Path:
    """Return a path to `source` with the configured filters applied.

    The original file is never modified. Results are written to `out_dir` and reused.
    """
    if not is_active(filters):
        return source

    out_dir.mkdir(parents=True, exist_ok=True)
    stat = source.stat()
    identity = hashlib.sha1(f"{source.resolve()}|{stat.st_mtime_ns}|{stat.st_size}".encode())
    dest = out_dir / f"{source.stem[:60]}-{identity.hexdigest()[:8]}-{_signature(filters)}.jpg"
    if dest.exists():
        dest.touch()  # keep it fresh for the cache eviction order
        return dest

    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")

    if filters.grayscale:
        image = ImageOps.grayscale(image).convert("RGB")
    if filters.blur:
        radius = max(2.0, max(image.size) * BLUR_RADIUS_FRACTION)
        image = image.filter(ImageFilter.GaussianBlur(radius))
    if abs(filters.brightness - 1.0) > 0.005:
        image = ImageEnhance.Brightness(image).enhance(filters.brightness)

    image.save(dest, "JPEG", quality=92)
    return dest
