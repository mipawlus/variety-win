import random
from pathlib import Path

from ..core.models import ImageCandidate
from .base import ConfigField, ImageSource

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}


class LocalFolderSource(ImageSource):
    id = "local_folder"
    display_name = "Local folder"
    requires_credentials = False

    @classmethod
    def config_fields(cls) -> list[ConfigField]:
        return [
            ConfigField(key="folder", label="Folder", type="path", default=""),
            ConfigField(key="recursive", label="Include subfolders", type="bool", default=True),
        ]

    def validate_config(self) -> list[str]:
        errors = []
        folder = self.config.get("folder", "")
        if not folder:
            errors.append("No folder configured.")
        elif not Path(folder).is_dir():
            errors.append(f"Folder does not exist: {folder}")
        return errors

    def describe(self) -> str:
        return self.config.get("folder", "") or "(no folder chosen)"

    def _list_images(self) -> list[Path]:
        folder = Path(self.config.get("folder", ""))
        if not folder.is_dir():
            return []
        recursive = self.config.get("recursive", True)
        pattern_iter = folder.rglob("*") if recursive else folder.glob("*")
        return [p for p in pattern_iter if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]

    def fetch_candidates(self, count: int = 1) -> list[ImageCandidate]:
        images = self._list_images()
        if not images:
            return []
        chosen = random.sample(images, k=min(count, len(images)))
        return [
            ImageCandidate(
                source_id=self.id,
                remote_id=str(path),
                url=str(path),
                title=path.stem,
            )
            for path in chosen
        ]

    def download(self, candidate: ImageCandidate, dest_dir: Path) -> Path:
        return Path(candidate.url)
