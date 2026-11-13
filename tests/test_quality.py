from PIL import Image

from varietywin.config.schema import ImageRequirements
from varietywin.core import quality

SCREEN = (1920, 1080)


def test_size_and_orientation_rules():
    default = ImageRequirements()
    assert quality.is_acceptable((1920, 1080), SCREEN, default)
    assert quality.is_acceptable((960, 540), SCREEN, default)
    assert not quality.is_acceptable((959, 540), SCREEN, default)
    assert not quality.is_acceptable((2000, 3000), SCREEN, default)
    assert quality.is_acceptable((2000, 2000), SCREEN, default)
    assert quality.is_acceptable((2000, 3000), (1080, 1920), default)
    assert not quality.is_acceptable((3000, 2000), (1080, 1920), default)

    anything = ImageRequirements(min_size_percent=0, match_orientation=False)
    assert quality.is_acceptable((10, 500), SCREEN, anything)


def test_image_size_honours_exif_rotation(tmp_path):
    plain = tmp_path / "plain.jpg"
    Image.new("RGB", (80, 40)).save(plain)
    assert quality.image_size(plain) == (80, 40)

    rotated = tmp_path / "rotated.jpg"
    exif = Image.Exif()
    exif[quality.EXIF_ORIENTATION_TAG] = 6
    Image.new("RGB", (80, 40)).save(rotated, exif=exif)
    assert quality.image_size(rotated) == (40, 80)


def test_parse_resolution():
    assert quality.parse_resolution("1920x1080") == (1920, 1080)
    assert quality.parse_resolution("") is None
    assert quality.parse_resolution("big") is None
