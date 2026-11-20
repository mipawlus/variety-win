"""Draw the quote and the clock onto a screen-sized copy of the wallpaper."""

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .quotes import Quote

Size = tuple[int, int]

# Tried in order; Pillow looks these up in the Windows fonts folder.
TEXT_FONTS = ("segoeui.ttf", "arial.ttf")
CLOCK_FONTS = ("segoeuil.ttf", "segoeui.ttf", "arial.ttf")
AUTHOR_FONTS = ("segoeuii.ttf", "segoeui.ttf", "ariali.ttf")

WHITE = (255, 255, 255, 255)
SHADOW = (0, 0, 0, 150)
PANEL = (0, 0, 0, 125)


@lru_cache(maxsize=32)
def _font(names: tuple[str, ...], size: int) -> ImageFont.ImageFont:
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _wrap(text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        attempt = f"{current} {word}".strip()
        if current and font.getlength(attempt) > max_width:
            lines.append(current)
            current = word
        else:
            current = attempt
    if current:
        lines.append(current)
    return lines


def _draw_clock(draw: ImageDraw.ImageDraw, size: Size, margin: int, clock: tuple[str, str]):
    width, height = size
    time_text, date_text = clock
    time_size = round(height * 0.11)
    date_size = round(height * 0.03)
    offset = max(1, round(height * 0.002))
    right = width - margin

    rows = [(time_text, _font(CLOCK_FONTS, time_size), margin)]
    if date_text:
        rows.append((date_text, _font(TEXT_FONTS, date_size), margin + round(time_size * 1.2)))
    for text, font, top in rows:
        draw.text((right + offset, top + offset), text, font=font, fill=SHADOW, anchor="ra")
        draw.text((right, top), text, font=font, fill=WHITE, anchor="ra")


def _draw_quote(draw: ImageDraw.ImageDraw, size: Size, margin: int, quote: Quote):
    width, height = size
    text_size = round(height * 0.026)
    author_size = round(height * 0.022)
    text_font = _font(TEXT_FONTS, text_size)
    author_font = _font(AUTHOR_FONTS, author_size)
    line_height = round(text_size * 1.35)
    padding = round(text_size * 0.9)

    lines = _wrap(quote.text, text_font, round(width * 0.36))
    author = f"— {quote.author}" if quote.author else ""
    text_width = max(
        [text_font.getlength(line) for line in lines] + [author_font.getlength(author)]
    )
    text_height = line_height * len(lines) + (round(line_height * 1.1) if author else 0)

    # Sits bottom-right, lifted clear of the taskbar.
    right = width - margin
    bottom = height - margin - round(height * 0.05)
    left = right - round(text_width) - 2 * padding
    top = bottom - text_height - 2 * padding
    draw.rounded_rectangle((left, top, right, bottom), radius=round(text_size * 0.6), fill=PANEL)

    y = top + padding
    for line in lines:
        draw.text((left + padding, y), line, font=text_font, fill=WHITE)
        y += line_height
    if author:
        draw.text(
            (right - padding, y + round(line_height * 0.1)),
            author,
            font=author_font,
            fill=WHITE,
            anchor="ra",
        )


def render(
    base: Path,
    screen: Size,
    dest: Path,
    quote: Quote | None = None,
    clock: tuple[str, str] | None = None,
) -> Path:
    """Write `base`, scaled and cropped to fill `screen`, with the overlays drawn on top.

    Also used without overlays: scaling here with a good filter looks better than
    letting Windows shrink a much larger image.

    `clock` is (time, date) as already formatted text; an empty date is left out.
    """
    with Image.open(base) as opened:
        # Lets the JPEG decoder skip detail the screen cannot show: much faster for
        # huge images. Square request, as the image may still be rotated by EXIF.
        edge = max(screen)
        opened.draft("RGB", (edge, edge))
        image = ImageOps.exif_transpose(opened).convert("RGB")
    image = ImageOps.fit(image, screen, Image.Resampling.LANCZOS).convert("RGBA")

    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    margin = round(screen[1] * 0.06)
    if clock is not None:
        _draw_clock(draw, screen, margin, clock)
    if quote is not None:
        _draw_quote(draw, screen, margin, quote)

    dest.parent.mkdir(parents=True, exist_ok=True)
    Image.alpha_composite(image, layer).convert("RGB").save(dest, "JPEG", quality=95, subsampling=0)
    return dest
