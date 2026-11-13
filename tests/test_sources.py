import base64

import pytest

from varietywin.sources import earthview
from varietywin.sources.earthview import EarthViewSource
from varietywin.sources.unsplash import UnsplashSource

PHOTO = {
    "id": "abc123",
    "width": 6000,
    "height": 4000,
    "description": None,
    "alt_description": "a foggy forest",
    "urls": {"raw": "https://images.unsplash.com/photo-1?ixid=x"},
    "links": {
        "html": "https://unsplash.com/photos/abc123",
        "download_location": "https://api.unsplash.com/photos/abc123/download",
    },
    "user": {"name": "Jan Kowalski", "links": {"html": "https://unsplash.com/@jan"}},
}


def test_unsplash_needs_a_key():
    assert UnsplashSource({"query": "forest"}).validate_config()
    assert not UnsplashSource({"api_key": "k"}).validate_config()


def test_unsplash_fetch_and_download(requests_mock, tmp_path):
    api = requests_mock.get("https://api.unsplash.com/photos/random", json=[PHOTO])
    image = requests_mock.get("https://images.unsplash.com/photo-1", content=b"jpeg-bytes")
    report = requests_mock.get("https://api.unsplash.com/photos/abc123/download", json={})

    source = UnsplashSource({"api_key": " key ", "query": "forest, fog"})
    assert source.describe() == "forest, fog"
    (candidate,) = source.fetch_candidates(count=3)

    request = api.last_request
    assert request.headers["Authorization"] == "Client-ID key"
    assert request.qs["query"][0] in {"forest", "fog"}
    assert request.qs["orientation"] == ["landscape"]
    assert (candidate.remote_id, candidate.title, candidate.author) == (
        "abc123",
        "a foggy forest",
        "Jan Kowalski",
    )
    assert candidate.extra["resolution"] == "6000x4000"

    path = source.download(candidate, tmp_path)
    assert path.read_bytes() == b"jpeg-bytes"
    assert "w=3840" in image.last_request.url and report.called
    assert report.last_request.headers["Authorization"] == "Client-ID key"

    source.download(candidate, tmp_path)  # already cached: nothing is fetched again
    assert image.call_count == 1 and report.call_count == 1


def test_unsplash_tag_without_results(requests_mock):
    requests_mock.get("https://api.unsplash.com/photos/random", status_code=404)
    assert UnsplashSource({"api_key": "k", "query": "zzzz"}).fetch_candidates(3) == []


@pytest.fixture
def earth(requests_mock, monkeypatch):
    monkeypatch.setattr(earthview, "_known_good", set())
    monkeypatch.setattr(earthview, "_known_missing", set())
    monkeypatch.setattr(earthview, "ID_RANGES", ((10, 13),))
    for image_id in (10, 12):
        requests_mock.head(earthview.IMAGE_URL.format(id=image_id), status_code=200)
    for image_id in (11, 13):
        requests_mock.head(earthview.IMAGE_URL.format(id=image_id), status_code=404)
    return requests_mock


def test_earthview_finds_existing_images_and_remembers_misses(earth):
    source = EarthViewSource({})
    seen = set()
    for _ in range(20):
        candidates = source.fetch_candidates(count=2)
        seen.update(c.remote_id for c in candidates)
        assert len({c.remote_id for c in candidates}) == len(candidates) <= 2
    assert seen == {"10", "12"}
    assert earth.call_count <= 4  # each id is probed once, then remembered


def test_earthview_download_uses_place_details(earth, tmp_path):
    data = {
        "lat": 41.1,
        "lng": 28.9,
        "zoom": 13,
        "attribution": "©2019 Maxar",
        "geocode": {"locality": "Istanbul", "country": "Turkey"},
        "dataUri": "data:image/jpeg;base64," + base64.b64encode(b"earth-jpeg").decode(),
    }
    earth.get(earthview.DATA_URL.format(id=10), json=data)
    earth.get(earthview.DATA_URL.format(id=12), status_code=404)
    earth.get(earthview.IMAGE_URL.format(id=12), content=b"plain-jpeg")

    source = EarthViewSource({})
    by_id = {}
    while len(by_id) < 2:
        by_id.update({c.remote_id: c for c in source.fetch_candidates(count=2)})

    path = source.download(by_id["10"], tmp_path)
    assert path.read_bytes() == b"earth-jpeg"
    assert by_id["10"].title == "Istanbul, Turkey" and by_id["10"].author == "©2019 Maxar"
    assert "41.1,28.9,13z" in by_id["10"].source_page_url

    fallback = source.download(by_id["12"], tmp_path)
    assert fallback.read_bytes() == b"plain-jpeg" and by_id["12"].title == "Earth View 12"
