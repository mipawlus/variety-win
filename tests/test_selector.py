from types import SimpleNamespace

from PIL import Image

from varietywin.core import history as history_module
from varietywin.core.models import ImageCandidate
from varietywin.ui import selector


def _image(path, size=(400, 300)):
    Image.new("RGB", size, (30, 120, 200)).save(path)
    return path


def _store(tmp_path, monkeypatch):
    favorites = tmp_path / "favorites"
    favorites.mkdir()
    monkeypatch.setattr(history_module, "history_file", lambda: tmp_path / "history.json")
    monkeypatch.setattr(history_module, "favorites_dir", lambda: favorites)
    return history_module.HistoryStore(), favorites


def test_recent_and_favorite_entries(tmp_path, monkeypatch):
    store, favorites = _store(tmp_path, monkeypatch)
    a = ImageCandidate("src", "a", "x://a", title="First")
    b = ImageCandidate("src", "b", "x://b", title="Second")
    c = ImageCandidate("src", "c", "x://c")
    gone = ImageCandidate("src", "gone", "x://gone")
    paths = {name: _image(tmp_path / f"{name}.png") for name in "abc"}

    store.record_shown(a, paths["a"])
    store.record_shown(gone, tmp_path / "gone.png")
    store.record_shown(b, paths["b"])
    store.record_shown(c, paths["c"])
    store.record_shown(a, paths["a"])  # shown again: listed once, at the front
    store.ban(c)

    recent = store.recent_entries(10)
    assert [(cand.remote_id, path.name) for cand, path in recent] == [
        ("a", "a.png"),
        ("b", "b.png"),
    ]
    assert store.recent_entries(1)[0][0].title == "First"

    store.favorite(b, paths["b"])
    _image(favorites / "dropped-in-by-hand.jpg")
    (favorites / "notes.txt").write_text("not an image")
    by_name = {path.name: cand for cand, path in store.favorite_entries()}
    assert set(by_name) == {"b.png", "dropped-in-by-hand.jpg"}
    assert (by_name["b.png"].source_id, by_name["b.png"].title) == ("src", "Second")
    assert by_name["dropped-in-by-hand.jpg"].source_id == "favorites"


def test_thumbnail_is_cropped_to_size(tmp_path):
    image = selector.make_thumbnail(_image(tmp_path / "wide.jpg", (3000, 1000)))
    assert (image.width(), image.height()) == selector.THUMBNAIL_SIZE
    (tmp_path / "broken.jpg").write_bytes(b"nope")
    assert selector.make_thumbnail(tmp_path / "broken.jpg") is None


def test_clicking_a_thumbnail_shows_that_image(tmp_path, monkeypatch, qtbot):
    store, _ = _store(tmp_path, monkeypatch)
    first = ImageCandidate("src", "1", "x://1", title="A very long title " * 5)
    second = ImageCandidate("src", "2", "x://2")
    store.record_shown(first, _image(tmp_path / "1.png"))
    store.record_shown(second, _image(tmp_path / "2.png"))
    store.favorite(first, tmp_path / "1.png")

    shown = []
    engine = SimpleNamespace(history=store, show_image=lambda c, p: shown.append((c, p)))
    window = selector.WallpaperSelector(engine)
    qtbot.addWidget(window)
    window.refresh()

    assert window.recent_list.count() == 2 and window.favorites_list.count() == 1
    assert window.tabs.tabText(1) == "Favorites (1)"
    assert len(window.recent_list.item(1).text()) <= selector.TITLE_LENGTH
    qtbot.waitUntil(lambda: not window._loader.isActive(), timeout=5000)

    window.recent_list.itemClicked.emit(window.recent_list.item(1))
    window.favorites_list.itemClicked.emit(window.favorites_list.item(0))
    assert [(c.remote_id, p.name) for c, p in shown] == [("1", "1.png"), ("1", "1.png")]
    assert shown[1][1].parent.name == "favorites"
