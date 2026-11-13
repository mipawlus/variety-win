"""Image effects. As in Variety, one of the enabled effects is picked at random per wallpaper."""

import hashlib
import logging
import random
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from ..config.schema import FilterConfig

logger = logging.getLogger(__name__)

NONE = "none"

# The artistic effects work on at most this many pixels along the longer edge: they are
# slow on huge images, and the detail they would add is not visible anyway.
MAX_WORK_EDGE = 2560


def _grayscale(image: Image.Image, seed: int) -> Image.Image:
    return ImageOps.grayscale(image).convert("RGB")


def _blur(fraction: float) -> Callable[[Image.Image, int], Image.Image]:
    # Radius relative to the image size, so the look does not depend on the resolution.
    def apply(image: Image.Image, seed: int) -> Image.Image:
        return image.filter(ImageFilter.GaussianBlur(max(2.0, max(image.size) * fraction)))

    return apply


def _oil(image: Image.Image, seed: int) -> Image.Image:
    # Flat patches of the locally most common colour, like brush strokes.
    small_edge = 900
    scale = small_edge / max(image.size)
    small = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    small = small.filter(ImageFilter.ModeFilter(7))
    painted = small.resize(image.size, Image.Resampling.BICUBIC)
    return ImageEnhance.Color(painted).enhance(1.15)


def _pixelate(image: Image.Image, seed: int) -> Image.Image:
    block = max(4, max(image.size) // 110)
    small = image.resize(
        (max(1, image.width // block), max(1, image.height // block)), Image.Resampling.BOX
    )
    return small.resize(image.size, Image.Resampling.NEAREST)


def _pointillism(image: Image.Image, seed: int) -> Image.Image:
    rng = random.Random(seed)  # the same image always gets the same dots
    width, height = image.size
    radius = max(3.0, max(image.size) / 260)
    canvas = image.filter(ImageFilter.GaussianBlur(radius * 2))
    draw = ImageDraw.Draw(canvas)
    pixels = image.load()
    for _ in range(int(width * height / (radius * radius * 1.3))):
        x, y = rng.randrange(width), rng.randrange(height)
        r = radius * rng.uniform(0.6, 1.25)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=pixels[x, y])
    return canvas


# name -> (label for the preferences, function, limit the working size first)
EFFECTS: dict[str, tuple[str, Callable[[Image.Image, int], Image.Image] | None, bool]] = {
    NONE: ("Keep original", None, False),
    "grayscale": ("Grayscale", _grayscale, False),
    "soft_blur": ("Soft blur", _blur(0.0025), False),
    "heavy_blur": ("Heavy blur", _blur(0.012), False),
    "oil": ("Oil painting", _oil, True),
    "pointillism": ("Pointillism", _pointillism, True),
    "pixelate": ("Pixelate", _pixelate, False),
}


def choose_effect(filters: FilterConfig) -> str:
    enabled = [name for name in filters.effects if name in EFFECTS]
    return random.choice(enabled) if enabled else NONE


def _brightness_changed(filters: FilterConfig) -> bool:
    return abs(filters.brightness - 1.0) > 0.005


def apply_filters(source: Path, filters: FilterConfig, out_dir: Path, effect: str = NONE) -> Path:
    """Return a path to `source` with `effect` and the configured brightness applied.

    The original file is never modified. Results are written to `out_dir` and reused.
    """
    if effect not in EFFECTS:
        effect = NONE
    if effect == NONE and not _brightness_changed(filters):
        return source

    out_dir.mkdir(parents=True, exist_ok=True)
    stat = source.stat()
    identity = hashlib.sha1(f"{source.resolve()}|{stat.st_mtime_ns}|{stat.st_size}".encode())
    signature = f"{effect}-{round(filters.brightness * 100)}"
    dest = out_dir / f"{source.stem[:60]}-{identity.hexdigest()[:8]}-{signature}.jpg"
    if dest.exists():
        dest.touch()  # keep it fresh for the cache eviction order
        return dest

    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")

    _, function, limit_size = EFFECTS[effect]
    if function is not None:
        if limit_size and max(image.size) > MAX_WORK_EDGE:
            image.thumbnail((MAX_WORK_EDGE, MAX_WORK_EDGE), Image.Resampling.LANCZOS)
        image = function(image, int(identity.hexdigest()[:8], 16))
    if _brightness_changed(filters):
        image = ImageEnhance.Brightness(image).enhance(filters.brightness)

    image.save(dest, "JPEG", quality=92)
    return dest
