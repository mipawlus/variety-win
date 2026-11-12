import logging

from ..util.paths import config_file
from .defaults import default_config
from .schema import AppConfig, CONFIG_SCHEMA_VERSION

logger = logging.getLogger(__name__)


def load() -> AppConfig:
    path = config_file()
    if not path.exists():
        config = default_config()
        save(config)
        return config

    try:
        raw = path.read_text(encoding="utf-8")
        config = AppConfig.model_validate_json(raw)
    except Exception:
        logger.exception("Failed to load config from %s, falling back to defaults", path)
        return default_config()

    if config.schema_version != CONFIG_SCHEMA_VERSION:
        config.schema_version = CONFIG_SCHEMA_VERSION
        save(config)

    return config


def save(config: AppConfig) -> None:
    path = config_file()
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
