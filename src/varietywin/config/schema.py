from typing import Any

from pydantic import BaseModel, Field

CONFIG_SCHEMA_VERSION = 1


class GeneralSettings(BaseModel):
    rotation_interval_seconds: int = 300
    paused: bool = False


class SourceConfig(BaseModel):
    source_id: str
    enabled: bool = True
    options: dict[str, Any] = Field(default_factory=dict)


class FilterConfig(BaseModel):
    blur: bool = False
    oblur: bool = False
    grayscale: bool = False
    brightness: float = 1.0


class QuoteConfig(BaseModel):
    enabled: bool = False
    # Text file with one quote per line ("text -- author"). Empty = built-in quotes.
    file: str = ""


class ClockConfig(BaseModel):
    enabled: bool = False
    show_date: bool = True


class ImageRequirements(BaseModel):
    # Smallest acceptable image, as a percentage of the screen's width and height. 0 = any size.
    min_size_percent: int = Field(default=50, ge=0, le=100)
    # Skip portrait images on landscape screens and the other way round.
    match_orientation: bool = True


class MonitorConfig(BaseModel):
    same_on_all_monitors: bool = True
    per_monitor_source_ids: dict[str, str] = Field(default_factory=dict)


class AppConfig(BaseModel):
    schema_version: int = CONFIG_SCHEMA_VERSION
    general: GeneralSettings = Field(default_factory=GeneralSettings)
    sources: dict[str, SourceConfig] = Field(
        default_factory=lambda: {
            "local_folder": SourceConfig(
                source_id="local_folder", enabled=False, options={"folder": "", "recursive": True}
            ),
            "bing": SourceConfig(source_id="bing", enabled=True, options={"market": "en-US"}),
            "reddit": SourceConfig(
                source_id="reddit",
                enabled=False,
                options={
                    "subreddits": "EarthPorn,wallpaper,wallpapers",
                    "sort": "hot",
                    "allow_nsfw": False,
                },
            ),
            "wallhaven": SourceConfig(
                source_id="wallhaven",
                enabled=True,
                options={
                    "query": "landscape, nature, mountains",
                    "categories": "100",
                    "purity": "100",
                    "api_key": "",
                },
            ),
        }
    )
    filters: FilterConfig = Field(default_factory=FilterConfig)
    requirements: ImageRequirements = Field(default_factory=ImageRequirements)
    quotes: QuoteConfig = Field(default_factory=QuoteConfig)
    clock: ClockConfig = Field(default_factory=ClockConfig)
    monitors: MonitorConfig = Field(default_factory=MonitorConfig)
