from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

CONFIG_SCHEMA_VERSION = 2


class GeneralSettings(BaseModel):
    rotation_interval_seconds: int = 300
    paused: bool = False
    # Also use each new wallpaper as the lock screen picture.
    change_lock_screen: bool = False


class SourceConfig(BaseModel):
    """One entry in the sources list. `source_id` is the kind of source (e.g. "wallhaven");
    several entries may share it, each with its own options."""

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    source_id: str
    enabled: bool = True
    options: dict[str, Any] = Field(default_factory=dict)


class FilterConfig(BaseModel):
    # Names from core.filters.EFFECTS. One is picked at random for each wallpaper;
    # "none" in the list means some wallpapers are left as they are.
    effects: list[str] = Field(default_factory=lambda: ["none"])
    brightness: float = 1.0

    @model_validator(mode="before")
    @classmethod
    def _upgrade_switches(cls, data):
        # Earlier versions had separate on/off switches instead of a list.
        if isinstance(data, dict) and "effects" not in data:
            effects = []
            if data.get("grayscale"):
                effects.append("grayscale")
            if data.get("blur"):
                effects.append("heavy_blur")
            data = {**data, "effects": effects or ["none"]}
        return data


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
    # Monitor id -> id of the source entry that monitor is limited to.
    per_monitor_source_ids: dict[str, str] = Field(default_factory=dict)


class AppConfig(BaseModel):
    schema_version: int = CONFIG_SCHEMA_VERSION
    general: GeneralSettings = Field(default_factory=GeneralSettings)
    sources: list[SourceConfig] = Field(
        default_factory=lambda: [
            SourceConfig(id="bing", source_id="bing", options={"market": "en-US"}),
            SourceConfig(
                id="reddit",
                source_id="reddit",
                enabled=False,
                options={
                    "subreddits": "EarthPorn,wallpaper,wallpapers",
                    "sort": "hot",
                    "allow_nsfw": False,
                },
            ),
            SourceConfig(
                id="wallhaven",
                source_id="wallhaven",
                options={
                    "query": "landscape, nature, mountains",
                    "categories": "100",
                    "purity": "100",
                    "api_key": "",
                },
            ),
        ]
    )
    filters: FilterConfig = Field(default_factory=FilterConfig)
    requirements: ImageRequirements = Field(default_factory=ImageRequirements)
    quotes: QuoteConfig = Field(default_factory=QuoteConfig)
    clock: ClockConfig = Field(default_factory=ClockConfig)
    monitors: MonitorConfig = Field(default_factory=MonitorConfig)

    @field_validator("sources", mode="before")
    @classmethod
    def _upgrade_v1_sources(cls, value):
        # Version 1 stored exactly one entry per kind of source, as a dict keyed by kind.
        if isinstance(value, dict):
            return [
                {**entry, "id": key} if isinstance(entry, dict) else entry
                for key, entry in value.items()
            ]
        return value
