import pytest
from PIL import Image, ImageChops

from varietywin.config.schema import FilterConfig
from varietywin.core import filters


def _make_image(path, size=(240, 160)):
    image = Image.new("RGB", size, (200, 40, 40))
    for x in range(0, size[0], 16):  # stripes, so every effect has something to change
        image.paste((30, 60, 220), (x, 0, x + 6, size[1]))
    image.save(path)
    return path


def test_no_effect_returns_original(tmp_path):
    src = _make_image(tmp_path / "a.png")
    assert filters.apply_filters(src, FilterConfig(), tmp_path / "out") == src
    assert filters.apply_filters(src, FilterConfig(), tmp_path / "out", "bogus") == src
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("effect", [name for name in filters.EFFECTS if name != filters.NONE])
def test_every_effect_changes_the_image_but_not_its_size_or_the_original(tmp_path, effect):
    src = _make_image(tmp_path / "a.png")
    before = src.read_bytes()
    result = filters.apply_filters(src, FilterConfig(), tmp_path / "out", effect)

    assert result != src and src.read_bytes() == before
    with Image.open(result) as changed, Image.open(src) as original:
        assert changed.size == original.size
        assert ImageChops.difference(changed.convert("RGB"), original.convert("RGB")).getbbox()

    # Same input and settings: the stored result is reused, also for the random-dot effect.
    assert filters.apply_filters(src, FilterConfig(), tmp_path / "out", effect) == result
    assert len(list((tmp_path / "out").iterdir())) == 1


def test_grayscale_and_brightness(tmp_path):
    src = _make_image(tmp_path / "a.png")
    plain = filters.apply_filters(src, FilterConfig(), tmp_path / "out", "grayscale")
    dark = filters.apply_filters(src, FilterConfig(brightness=0.5), tmp_path / "out", "grayscale")
    only_dark = filters.apply_filters(src, FilterConfig(brightness=0.5), tmp_path / "out")
    assert len({src, plain, dark, only_dark}) == 4

    with Image.open(plain) as image:
        r, g, b = image.getpixel((10, 10))
        assert abs(r - g) <= 2 and abs(g - b) <= 2
    with Image.open(dark) as image:
        assert image.getpixel((10, 10))[0] < r


def test_large_images_are_reduced_for_artistic_effects(tmp_path):
    src = _make_image(tmp_path / "huge.png", (3200, 1200))
    with Image.open(filters.apply_filters(src, FilterConfig(), tmp_path / "out", "oil")) as image:
        assert image.size == (2560, 960)
    result = filters.apply_filters(src, FilterConfig(), tmp_path / "out", "pixelate")
    with Image.open(result) as image:
        assert image.size == (3200, 1200)


def test_choose_effect_and_old_settings():
    assert filters.choose_effect(FilterConfig()) == "none"
    assert filters.choose_effect(FilterConfig(effects=["bogus"])) == "none"
    picks = {filters.choose_effect(FilterConfig(effects=["oil", "none"])) for _ in range(60)}
    assert picks == {"oil", "none"}

    assert FilterConfig.model_validate({"grayscale": True, "blur": True}).effects == [
        "grayscale",
        "heavy_blur",
    ]
    assert FilterConfig.model_validate({"blur": False, "oblur": True}).effects == ["none"]
