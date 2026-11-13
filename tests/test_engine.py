from types import SimpleNamespace

import pytest
from PIL import Image

from varietywin.config.schema import AppConfig, SourceConfig
from varietywin.core import engine as engine_module
from varietywin.core import history as history_module
from varietywin.core.models import ImageCandidate


SCREEN = (1000, 500)


def options_invalid(options):
    return bool(options.get("broken"))


def _fake_source(source_id, image_dir, count=6, sizes=None):
    class FakeSource:
        id = source_id
        display_name = source_id

        def __init__(self, options):
            self.options = options

        def validate_config(self):
            return ["not set up"] if options_invalid(self.options) else []

        def fetch_candidates(self, count_=3, **_):
            return [
                ImageCandidate(source_id=source_id, remote_id=str(i), url=f"x://{i}")
                for i in range(count)
            ]

        def download(self, candidate, dest_dir):
            path = image_dir / f"{source_id}-{candidate.remote_id}.png"
            if not path.exists():
                size = (sizes or {}).get(candidate.remote_id, SCREEN)
                Image.new("RGB", size, (120, 60, 30)).save(path)
            return path

    return FakeSource


@pytest.fixture
def env(tmp_path, monkeypatch, qapp):
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(engine_module, "cache_dir", lambda: cache)
    monkeypatch.setattr(history_module, "history_file", lambda: tmp_path / "history.json")
    monkeypatch.setattr(history_module, "favorites_dir", lambda: tmp_path)

    sources = {"a": _fake_source("a", cache), "b": _fake_source("b", cache)}
    monkeypatch.setattr(engine_module, "get_source_class", sources.get)

    monkeypatch.setattr(
        engine_module.RotationEngine,
        "_screen_size",
        lambda self, target: self._monitor_sizes.get(target, SCREEN),
    )

    calls = SimpleNamespace(single=[], multi=[], monitors=[], lock=[])
    monkeypatch.setattr(
        engine_module.lockscreen, "set_lock_screen_in_background", calls.lock.append
    )
    monkeypatch.setattr(engine_module.wallpaper_single, "set_wallpaper", calls.single.append)
    monkeypatch.setattr(
        engine_module.wallpaper_multi,
        "set_wallpaper",
        lambda monitor_id, path: calls.multi.append((monitor_id, path)),
    )
    monkeypatch.setattr(
        engine_module.wallpaper_multi,
        "list_monitors",
        lambda: [SimpleNamespace(id=m, width=SCREEN[0], height=SCREEN[1]) for m in calls.monitors],
    )

    config = AppConfig(
        sources=[
            SourceConfig(id="entry-a", source_id="a"),
            SourceConfig(id="entry-b", source_id="b"),
        ]
    )
    entry = {e.source_id: e for e in config.sources}
    return SimpleNamespace(config=config, calls=calls, cache=cache, sources=sources, entry=entry)


def test_single_wallpaper_rotation(env):
    engine = engine_module.RotationEngine(env.config)
    engine.rotate()

    assert len(env.calls.single) == 1 and not env.calls.multi
    assert env.calls.single[0] == engine.current_path
    assert engine.history.current_entry().remote_id == engine.current_candidate.remote_id


def test_filters_are_applied_and_reapplied(env):
    env.config.filters.grayscale = True
    engine = engine_module.RotationEngine(env.config)
    engine.rotate()

    shown = env.calls.single[-1]
    assert shown.parent == env.cache / "filtered"
    assert shown != engine.current_path  # history keeps the untouched original

    env.config.filters.grayscale = False
    engine.reapply()
    assert env.calls.single[-1] == engine.current_path
    assert len(engine.history._data.shown) == 1  # reapply is not a rotation


def test_per_monitor_rotation_uses_distinct_images_and_mapped_sources(env):
    env.calls.monitors[:] = ["m1", "m2"]
    env.config.monitors.same_on_all_monitors = False
    env.config.monitors.per_monitor_source_ids = {"m1": "entry-a", "m2": "entry-b"}
    engine = engine_module.RotationEngine(env.config)

    for _ in range(5):
        env.calls.multi.clear()
        engine.rotate()
        assert not env.calls.single
        assert [m for m, _ in env.calls.multi] == ["m1", "m2"]
        assert env.calls.multi[0][1].name.startswith("a-")
        assert env.calls.multi[1][1].name.startswith("b-")

    assert engine.current_candidate.source_id == "a"
    assert engine.history.current_entry().source_id == "a"


def test_per_monitor_never_repeats_an_image_across_monitors(env):
    env.calls.monitors[:] = ["m1", "m2", "m3"]
    env.config.monitors.same_on_all_monitors = False
    env.entry["b"].enabled = False
    engine = engine_module.RotationEngine(env.config)

    for _ in range(10):
        env.calls.multi.clear()
        engine.rotate()
        paths = [p for _, p in env.calls.multi]
        assert len(paths) == 3 and len(set(paths)) == 3


def test_per_monitor_falls_back_to_single_with_one_monitor(env):
    env.calls.monitors[:] = ["m1"]
    env.config.monitors.same_on_all_monitors = False
    engine = engine_module.RotationEngine(env.config)
    engine.rotate()
    assert len(env.calls.single) == 1 and not env.calls.multi


def test_reapply_rotates_when_monitor_mode_changes(env):
    env.calls.monitors[:] = ["m1", "m2"]
    engine = engine_module.RotationEngine(env.config)
    engine.rotate()
    env.config.monitors.same_on_all_monitors = False
    engine.reapply()
    assert [m for m, _ in env.calls.multi] == ["m1", "m2"]


def test_small_and_portrait_images_are_skipped(env):
    sizes = {"0": (300, 200), "1": (500, 1000), "2": (300, 200), "3": (40, 40), "4": (600, 300)}
    env.sources["a"] = _fake_source("a", env.cache, count=5, sizes=sizes)
    env.entry["b"].enabled = False
    engine = engine_module.RotationEngine(env.config)

    for _ in range(4):
        engine.rotate()
    assert {path.name for path in env.calls.single} == {"a-4.png"}
    # rejected downloads do not pile up in the cache
    assert sorted(p.name for p in env.cache.glob("*.png")) == ["a-4.png"]

    env.config.requirements.min_size_percent = 0
    env.config.requirements.match_orientation = False
    engine.reapply()  # settings changed: earlier rejections are forgotten
    for _ in range(30):
        engine.rotate()
    assert len({path.name for path in env.calls.single}) == 5


def test_reported_resolution_avoids_download(env):
    downloads = []

    class Reporting(_fake_source("a", env.cache, count=2)):
        def fetch_candidates(self, **_):
            return [
                ImageCandidate("a", "small", "x://s", extra={"resolution": "320x200"}),
                ImageCandidate("a", "big", "x://b", extra={"resolution": "1920x1080"}),
            ]

        def download(self, candidate, dest_dir):
            downloads.append(candidate.remote_id)
            return super().download(candidate, dest_dir)

    env.sources["a"] = Reporting
    env.entry["b"].enabled = False
    engine = engine_module.RotationEngine(env.config)
    engine.rotate()
    engine.rotate()
    assert set(downloads) == {"big"}


def test_quote_and_clock_are_drawn_on_a_screen_sized_copy(env):
    env.config.quotes.enabled = True
    env.config.clock.enabled = True
    engine = engine_module.RotationEngine(env.config)
    engine.rotate()

    first = env.calls.single[-1]
    assert first.parent == env.cache / "overlay"
    with Image.open(first) as image:
        assert image.size == SCREEN
    assert engine.current_path.parent == env.cache  # history keeps the clean original

    quote = engine._quote
    engine.next_quote()
    second = env.calls.single[-1]
    assert engine._quote != quote
    assert second != first and second.exists() and not first.exists()
    assert len(engine.history._data.shown) == 1

    env.config.quotes.enabled = False
    env.config.clock.enabled = False
    engine.reapply()
    assert env.calls.single[-1] == engine.current_path
    assert not list((env.cache / "overlay").iterdir())
    engine.stop()


def test_sources_that_are_not_set_up_are_skipped(env):
    env.entry["a"].options["broken"] = True
    engine = engine_module.RotationEngine(env.config)
    assert engine.has_usable_sources()
    for _ in range(5):
        engine.rotate()
    assert all(path.name.startswith("b-") for path in env.calls.single)

    env.entry["b"].options["broken"] = True
    errors = []
    engine.error_occurred.connect(errors.append)
    assert not engine.has_usable_sources()
    engine.rotate()
    assert len(env.calls.single) == 5 and "Preferences > Sources" in errors[0]


def test_default_config_works_without_a_folder():
    from varietywin.sources.registry import get_source_class

    config = AppConfig()
    ready = [
        entry.source_id
        for entry in config.sources
        if entry.enabled
        and not get_source_class(entry.source_id)(entry.options).validate_config()
    ]
    assert ready == ["bing", "wallhaven"]


def test_same_kind_of_source_can_be_added_twice(env):
    env.config.sources = [
        SourceConfig(id="one", source_id="a", options={"tag": "forest"}),
        SourceConfig(id="two", source_id="a", options={"tag": "space"}, enabled=False),
    ]
    engine = engine_module.RotationEngine(env.config)
    assert [(s.entry_id, s.options["tag"]) for s in engine._active_sources()] == [
        ("one", "forest")
    ]
    env.config.sources[1].enabled = True
    assert [s.entry_id for s in engine._active_sources()] == ["one", "two"]


def test_version_1_config_is_upgraded():
    old = {
        "schema_version": 1,
        "sources": {
            "local_folder": {"source_id": "local_folder", "enabled": True, "options": {}},
            "wallhaven": {
                "source_id": "wallhaven",
                "enabled": False,
                "options": {"query": "cats"},
            },
        },
        "filters": {"blur": True, "quote_enabled": True},
        "monitors": {"per_monitor_source_ids": {"mon": "wallhaven"}},
    }
    config = AppConfig.model_validate(old)
    assert [(e.id, e.source_id, e.enabled) for e in config.sources] == [
        ("local_folder", "local_folder", True),
        ("wallhaven", "wallhaven", False),
    ]
    assert config.sources[1].options == {"query": "cats"}
    assert config.filters.blur and config.monitors.per_monitor_source_ids == {"mon": "wallhaven"}
    assert AppConfig.model_validate_json(config.model_dump_json()) == config


def test_lock_screen_follows_the_wallpaper_without_overlays(env):
    engine = engine_module.RotationEngine(env.config)
    engine.rotate()
    assert not env.calls.lock  # off by default

    env.config.general.change_lock_screen = True
    env.config.clock.enabled = True
    env.config.filters.grayscale = True
    engine.reapply()
    assert len(env.calls.lock) == 1
    assert env.calls.lock[0].parent == env.cache / "filtered"  # filtered, but no clock
    assert env.calls.single[-1].parent == env.cache / "overlay"

    engine._on_clock_tick()  # the clock redraws; the lock screen is left alone
    assert len(env.calls.lock) == 1

    for _ in range(4):
        engine.rotate()
    assert len(env.calls.lock) >= 2
    engine.stop()


def test_lock_screen_uses_the_first_monitor(env):
    env.calls.monitors[:] = ["m1", "m2"]
    env.config.monitors.same_on_all_monitors = False
    env.config.general.change_lock_screen = True
    engine = engine_module.RotationEngine(env.config)
    engine.rotate()
    assert env.calls.lock == [env.calls.multi[0][1]]
