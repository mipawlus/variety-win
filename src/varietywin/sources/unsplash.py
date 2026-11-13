import logging
import random
from pathlib import Path

import requests

from ..core.models import ImageCandidate
from .base import ConfigField, ImageSource

logger = logging.getLogger(__name__)

API_URL = "https://api.unsplash.com/photos/random"
# Unsplash serves any size on request; ask for one that is big enough for a 4K screen.
IMAGE_PARAMS = "&w=3840&q=85&fm=jpg"


class UnsplashSource(ImageSource):
    id = "unsplash"
    display_name = "Unsplash"
    requires_credentials = True

    @classmethod
    def config_fields(cls) -> list[ConfigField]:
        return [
            ConfigField(key="query", label="Tags (comma-separated)", type="str", default=""),
            ConfigField(
                key="api_key",
                label="Access key (free, from unsplash.com/developers)",
                type="str",
                secret=True,
                default="",
            ),
        ]

    def validate_config(self) -> list[str]:
        if not self.config.get("api_key", "").strip():
            return ["Unsplash needs an access key. Create a free one at unsplash.com/developers."]
        return []

    def _tags(self) -> list[str]:
        return [tag.strip() for tag in self.config.get("query", "").split(",") if tag.strip()]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Client-ID {self.config.get('api_key', '').strip()}",
            "Accept-Version": "v1",
        }

    def describe(self) -> str:
        return ", ".join(self._tags()) or "any photo"

    def fetch_candidates(self, count: int = 1) -> list[ImageCandidate]:
        params = {"count": max(1, min(count, 30)), "orientation": "landscape"}
        tags = self._tags()
        if tags:
            params["query"] = random.choice(tags)
        resp = requests.get(API_URL, params=params, headers=self._headers(), timeout=15)
        if resp.status_code == 404:  # nothing matches the tag
            return []
        resp.raise_for_status()

        candidates = []
        for photo in resp.json():
            user = photo.get("user") or {}
            candidates.append(
                ImageCandidate(
                    source_id=self.id,
                    remote_id=photo["id"],
                    url=photo["urls"]["raw"] + IMAGE_PARAMS,
                    title=photo.get("description") or photo.get("alt_description") or "",
                    author=user.get("name", ""),
                    author_url=(user.get("links") or {}).get("html", ""),
                    source_page_url=(photo.get("links") or {}).get("html", ""),
                    extra={
                        "resolution": f"{photo.get('width', 0)}x{photo.get('height', 0)}",
                        "download_location": (photo.get("links") or {}).get(
                            "download_location", ""
                        ),
                    },
                )
            )
        return candidates

    def download(self, candidate: ImageCandidate, dest_dir: Path) -> Path:
        dest = dest_dir / f"unsplash_{candidate.remote_id}.jpg"
        if dest.exists():
            return dest
        resp = requests.get(candidate.url, timeout=30)
        resp.raise_for_status()
        dest.write_bytes(resp.content)

        # Unsplash asks API users to report each download; a failure here must not matter.
        download_location = candidate.extra.get("download_location")
        if download_location:
            try:
                requests.get(download_location, headers=self._headers(), timeout=10)
            except requests.RequestException:
                logger.debug("Could not report the download to Unsplash", exc_info=True)
        return dest
