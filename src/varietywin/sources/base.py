from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Literal

from ..core.models import ImageCandidate


@dataclass
class ConfigField:
    key: str
    label: str
    type: Literal["str", "int", "bool", "path", "choice"]
    secret: bool = False
    choices: list[str] | None = None
    default: Any = None


class ImageSource(ABC):
    id: ClassVar[str]
    display_name: ClassVar[str]
    requires_credentials: ClassVar[bool] = False

    def __init__(self, config: dict[str, Any]):
        self.config = config

    @classmethod
    def config_fields(cls) -> list[ConfigField]:
        return []

    def validate_config(self) -> list[str]:
        return []

    @abstractmethod
    def fetch_candidates(self, count: int = 1) -> list[ImageCandidate]:
        ...

    @abstractmethod
    def download(self, candidate: ImageCandidate, dest_dir: Path) -> Path:
        ...
