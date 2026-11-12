import random
from pathlib import Path

import requests

from ..core.models import ImageCandidate
from .base import ConfigField, ImageSource

API_URL = "https://wallhaven.cc/api/v1/search"


class WallhavenSource(ImageSource):
    id = "wallhaven"
    display_name = "Wallhaven"
    requires_credentials = False

    @classmethod
    def config_fields(cls) -> list[ConfigField]:
        return [
            ConfigField(key="query", label="Search query", type="str", default=""),
            ConfigField(
                key="categories", label="Categories (general/anime/people)", type="str", default="100"
            ),
            ConfigField(key="purity", label="Purity (sfw/sketchy/nsfw)", type="str", default="100"),
            ConfigField(
                key="api_key", label="API key (optional, needed for NSFW)", type="str", secret=True, default=""
            ),
        ]

    def fetch_candidates(self, count: int = 1) -> list[ImageCandidate]:
        params = {
            "categories": self.config.get("categories", "100"),
            "purity": self.config.get("purity", "100"),
            "sorting": "random",
        }
        query = self.config.get("query", "")
        if query:
            params["q"] = query
        api_key = self.config.get("api_key", "")
        if api_key:
            params["apikey"] = api_key

        resp = requests.get(API_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        results = data.get("data", [])
        if not results:
            return []

        chosen = random.sample(results, k=min(count, len(results)))
        return [
            ImageCandidate(
                source_id=self.id,
                remote_id=item["id"],
                url=item["path"],
                title=item["id"],
                source_page_url=item.get("url", ""),
                extra={"resolution": item.get("resolution", "")},
            )
            for item in chosen
        ]

    def download(self, candidate: ImageCandidate, dest_dir: Path) -> Path:
        suffix = Path(candidate.url).suffix or ".jpg"
        dest = dest_dir / f"wallhaven_{candidate.remote_id}{suffix}"
        if not dest.exists():
            resp = requests.get(candidate.url, timeout=30)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
        return dest
