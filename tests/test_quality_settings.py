import os
import winreg

import requests

from varietywin.platform_win import desktop_quality
from varietywin.sources import wallhaven
from varietywin.sources.bing import BingSource
from varietywin.sources.wallhaven import WallhavenSource

TEST_KEY = rf"Software\VarietyWinTests\desktop-{os.getpid()}"


def test_windows_recompression_is_turned_off_once():
    try:
        assert desktop_quality.current_quality(TEST_KEY) is None
        assert desktop_quality.ensure_full_quality(TEST_KEY)
        assert desktop_quality.current_quality(TEST_KEY) == 100
        assert not desktop_quality.ensure_full_quality(TEST_KEY)  # already done
    finally:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, TEST_KEY)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\VarietyWinTests")


def _wallhaven_page(last_page=20):
    return {
        "data": [
            {"id": f"w{i}", "path": f"https://w.wallhaven.cc/full/w{i}.jpg", "resolution": "3840x2160"}
            for i in range(5)
        ],
        "meta": {"last_page": last_page},
    }


def test_wallhaven_picks_top_rated_by_default_from_varied_pages(requests_mock, monkeypatch):
    monkeypatch.setattr(wallhaven, "_last_pages", {})
    api = requests_mock.get(wallhaven.API_URL, json=_wallhaven_page())
    source = WallhavenSource({"query": "forest"})

    source.fetch_candidates(3)
    first = api.last_request.qs
    assert first["sorting"] == ["toplist"] and first["toprange"] == ["1y"]
    assert first["page"] == ["1"]  # number of pages not known yet

    pages = set()
    for _ in range(40):
        source.fetch_candidates(3)
        pages.add(int(api.last_request.qs["page"][0]))
    assert len(pages) > 3 and max(pages) <= wallhaven.MAX_PAGE


def test_wallhaven_random_and_favorites(requests_mock, monkeypatch):
    monkeypatch.setattr(wallhaven, "_last_pages", {})
    api = requests_mock.get(wallhaven.API_URL, json=_wallhaven_page(last_page=2))

    WallhavenSource({"pick_from": "Random"}).fetch_candidates(3)
    assert api.last_request.qs["sorting"] == ["random"] and "page" not in api.last_request.qs

    source = WallhavenSource({"pick_from": "Most favorited"})
    for _ in range(10):
        source.fetch_candidates(3)
        assert api.last_request.qs["sorting"] == ["favorites"]
        assert int(api.last_request.qs["page"][0]) <= 2


def test_bing_prefers_the_4k_image(requests_mock, tmp_path):
    requests_mock.get(
        "https://www.bing.com/HPImageArchive.aspx",
        json={"images": [{"url": "/th?id=OHR.X_1920x1080.jpg", "urlbase": "/th?id=OHR.X", "hsh": "h1"},
                         {"url": "/th?id=OHR.Y_1920x1080.jpg", "urlbase": "/th?id=OHR.Y", "hsh": "h2"}]},
    )
    requests_mock.get("https://www.bing.com/th?id=OHR.X_UHD.jpg", content=b"uhd",
                      headers={"Content-Type": "image/jpeg"})
    requests_mock.get("https://www.bing.com/th?id=OHR.Y_UHD.jpg", status_code=404)
    requests_mock.get("https://www.bing.com/th?id=OHR.Y_1920x1080.jpg", content=b"hd",
                      headers={"Content-Type": "image/jpeg"})

    x, y = BingSource({"market": "en-US"}).fetch_candidates(2)
    assert BingSource({}).download(x, tmp_path).read_bytes() == b"uhd"
    assert BingSource({}).download(y, tmp_path).read_bytes() == b"hd"


def test_bing_reports_a_failed_download(requests_mock, tmp_path):
    requests_mock.get(
        "https://www.bing.com/HPImageArchive.aspx",
        json={"images": [{"url": "/th?id=OHR.Z_1920x1080.jpg", "urlbase": "/th?id=OHR.Z", "hsh": "h3"}]},
    )
    requests_mock.get("https://www.bing.com/th?id=OHR.Z_UHD.jpg", status_code=404)
    requests_mock.get("https://www.bing.com/th?id=OHR.Z_1920x1080.jpg", status_code=503)
    (z,) = BingSource({}).fetch_candidates(1)
    try:
        BingSource({}).download(z, tmp_path)
    except requests.HTTPError:
        pass
    else:
        raise AssertionError("expected an error")
    assert not list(tmp_path.iterdir())
