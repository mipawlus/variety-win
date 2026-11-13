"""Decide whether an image is good enough to be a wallpaper on a given screen."""

from pathlib import Path

from PIL import Image

from ..config.schema import ImageRequirements

EXIF_ORIENTATION_TAG = 274
ROTATED_ORIENTATIONS = {5, 6, 7, 8}

Size = tuple[int, int]


def image_size(path: Path) -> Size:
    """Displayed width and height, read from the file header without decoding the image."""
    with Image.open(path) as image:
        width, height = image.size
        if image.getexif().get(EXIF_ORIENTATION_TAG) in ROTATED_ORIENTATIONS:
            width, height = height, width
    return width, height


def parse_resolution(text: str) -> Size | None:
    """Parse a "1920x1080" style string, as some sources report sizes before download."""
    try:
        width, height = (int(part) for part in text.lower().split("x"))
    except (ValueError, AttributeError):
        return None
    return (width, height) if width > 0 and height > 0 else None


def is_acceptable(size: Size, screen: Size, requirements: ImageRequirements) -> bool:
    width, height = size
    screen_width, screen_height = screen

    if requirements.match_orientation:
        if screen_width >= screen_height and width < height:
            return False
        if screen_width < screen_height and height < width:
            return False

    factor = requirements.min_size_percent / 100
    return width >= screen_width * factor and height >= screen_height * factor
