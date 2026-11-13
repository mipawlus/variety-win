from PIL import Image

from varietywin.config.schema import FilterConfig
from varietywin.core import filters


def _make_image(path, color=(200, 40, 40)):
    image = Image.new("RGB", (64, 48), color)
    image.putpixel((10, 10), (0, 255, 0))
    image.save(path)
    return path


def test_no_filters_returns_original(tmp_path):
    src = _make_image(tmp_path / "a.png")
    assert filters.apply_filters(src, FilterConfig(), tmp_path / "out") == src
    assert not (tmp_path / "out").exists()


def test_grayscale_and_brightness(tmp_path):
    src = _make_image(tmp_path / "a.png")
    plain = filters.apply_filters(src, FilterConfig(grayscale=True), tmp_path / "out")
    dark = filters.apply_filters(
        src, FilterConfig(grayscale=True, brightness=0.5), tmp_path / "out"
    )
    assert plain != src and dark != plain

    with Image.open(plain) as image:
        assert image.size == (64, 48)
        r, g, b = image.getpixel((40, 30))
        assert abs(r - g) <= 2 and abs(g - b) <= 2
    with Image.open(dark) as image:
        assert image.getpixel((40, 30))[0] < r

    with Image.open(src) as original:
        assert original.getpixel((40, 30)) == (200, 40, 40)


def test_blur_smooths_and_result_is_reused(tmp_path):
    src = _make_image(tmp_path / "a.png")
    config = FilterConfig(blur=True)
    first = filters.apply_filters(src, config, tmp_path / "out")
    with Image.open(first) as image:
        assert image.getpixel((10, 10))[1] < 200  # the lone green pixel got smeared

    mtime = first.stat().st_mtime_ns
    assert filters.apply_filters(src, config, tmp_path / "out") == first
    assert len(list((tmp_path / "out").iterdir())) == 1
    assert first.stat().st_mtime_ns >= mtime
