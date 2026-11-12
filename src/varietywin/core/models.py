from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ImageCandidate:
    source_id: str
    remote_id: str
    url: str
    title: str = ""
    author: str = ""
    author_url: str = ""
    source_page_url: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageMetadata:
    candidate: ImageCandidate
    local_path: Path
