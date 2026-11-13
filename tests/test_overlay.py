from PIL import Image, ImageChops

from varietywin.core import overlay, quotes

SCREEN = (1280, 720)
BACKGROUND = (40, 90, 160)


def _base(tmp_path, size=(2000, 2000)):
    path = tmp_path / "base.png"
    Image.new("RGB", size, BACKGROUND).save(path)
    return path


def _changed_box(path):
    with Image.open(path) as image:
        plain = Image.new("RGB", image.size, BACKGROUND)
        difference = ImageChops.difference(image.convert("RGB"), plain).convert("L")
        return difference.point(lambda value: 255 if value > 40 else 0).getbbox()


def test_render_fills_the_screen_and_places_overlays(tmp_path):
    base = _base(tmp_path)
    quote = quotes.Quote("Zażółć gęślą jaźń. " * 8, "Anonim")

    clock_only = overlay.render(base, SCREEN, tmp_path / "c.jpg", clock=("12:34", "Friday"))
    with Image.open(clock_only) as image:
        assert image.size == SCREEN
    left, top, right, bottom = _changed_box(clock_only)
    assert left > SCREEN[0] / 2 and bottom < SCREEN[1] / 2  # top-right corner
    assert right <= SCREEN[0] and top >= 0

    quote_only = overlay.render(base, SCREEN, tmp_path / "q.jpg", quote=quote)
    left, top, right, bottom = _changed_box(quote_only)
    assert left > SCREEN[0] / 2 and top > SCREEN[1] / 2  # bottom-right corner
    assert right < SCREEN[0] and bottom < SCREEN[1] * 0.92  # clear of the taskbar
    assert right - left <= SCREEN[0] * 0.45  # long text wraps

    plain = overlay.render(base, SCREEN, tmp_path / "p.jpg")
    assert _changed_box(plain) is None


def test_quotes_file_parsing_and_fallback(tmp_path):
    file = tmp_path / "quotes.txt"
    file.write_text(
        "# my quotes\n\n"
        "Lepszy wróbel w garści -- Przysłowie\n"
        "\"Just text\"\n"
        "Well-known - with a hyphen — Someone\n",
        encoding="utf-8",
    )
    assert quotes.load(str(file)) == [
        quotes.Quote("Lepszy wróbel w garści", "Przysłowie"),
        quotes.Quote("Just text"),
        quotes.Quote("Well-known - with a hyphen", "Someone"),
    ]
    assert quotes.load("") is quotes.BUILTIN_QUOTES
    assert quotes.load(str(tmp_path / "missing.txt")) is quotes.BUILTIN_QUOTES

    first = quotes.BUILTIN_QUOTES[0]
    assert all(quotes.pick(quotes.BUILTIN_QUOTES, first) != first for _ in range(50))
    assert quotes.pick([first], first) == first
