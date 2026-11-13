"""Draw the application icon. Run once; the result is committed.

    python packaging/make_icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024  # drawn large, then scaled down for smooth edges
OUT = Path(__file__).resolve().parent.parent / "src" / "varietywin" / "resources" / "icon.ico"


def draw() -> Image.Image:
    # Sky: vertical gradient from deep blue to warm orange.
    top, bottom = (38, 70, 160), (250, 150, 90)
    sky = Image.new("RGB", (SIZE, SIZE))
    pixels = sky.load()
    for y in range(SIZE):
        t = y / (SIZE - 1)
        color = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom))
        for x in range(SIZE):
            pixels[x, y] = color

    draw = ImageDraw.Draw(sky)
    draw.ellipse((600, 250, 800, 450), fill=(255, 236, 170))  # sun
    draw.polygon([(0, 1024), (0, 720), (330, 400), (640, 760), (780, 1024)], fill=(36, 52, 92))
    draw.polygon([(420, 1024), (760, 560), (1024, 820), (1024, 1024)], fill=(22, 32, 62))

    # Rounded-square mask.
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=220, fill=255)
    icon = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    icon.paste(sky, (0, 0), mask)
    return icon


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    image = draw().resize((256, 256), Image.Resampling.LANCZOS)
    image.save(OUT, sizes=[(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 128, 256)])
    image.save(OUT.with_suffix(".png"))
    print(OUT)
