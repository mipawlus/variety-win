from pathlib import Path

import requests

from ..core.models import ImageCandidate
from .base import ConfigField, ImageSource

API_URL = "https://www.bing.com/HPImageArchive.aspx"


class BingSource(ImageSource):
    id = "bing"
    display_name = "Bing Daily Image"
    requires_credentials = False

    @classmethod
    def config_fields(cls) -> list[ConfigField]:
        return [ConfigField(key="market", label="Market", type="str", default="en-US")]

    def describe(self) -> str:
        return self.config.get("market", "en-US")

    def fetch_candidates(self, count: int = 1) -> list[ImageCandidate]:
        market = self.config.get("market", "en-US")
        params = {"format": "js", "idx": 0, "n": min(max(count, 1), 8), "mkt": market}
        resp = requests.get(API_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        candidates = []
        for image in data.get("images", []):
            url = "https://www.bing.com" + image["url"]
            remote_id = image.get("hsh") or image.get("urlbase", url)
            candidates.append(
                ImageCandidate(
                    source_id=self.id,
                    remote_id=remote_id,
                    url=url,
                    title=image.get("copyright", ""),
                    source_page_url=image.get("copyrightlink", ""),
                )
            )
        return candidates

    def download(self, candidate: ImageCandidate, dest_dir: Path) -> Path:
        dest = dest_dir / f"bing_{candidate.remote_id}.jpg"
        if not dest.exists():
            resp = requests.get(candidate.url, timeout=30)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
        return dest
