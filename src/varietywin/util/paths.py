from pathlib import Path

from platformdirs import PlatformDirs

_dirs = PlatformDirs(appname="VarietyWin", appauthor=False, roaming=True)


def config_dir() -> Path:
    path = Path(_dirs.user_config_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_file() -> Path:
    return config_dir() / "config.json"


def cache_dir() -> Path:
    path = Path(_dirs.user_cache_dir) / "images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def favorites_dir() -> Path:
    path = Path(_dirs.user_data_dir) / "favorites"
    path.mkdir(parents=True, exist_ok=True)
    return path


def history_file() -> Path:
    path = Path(_dirs.user_data_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path / "history.json"


def log_dir() -> Path:
    path = Path(_dirs.user_log_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path
