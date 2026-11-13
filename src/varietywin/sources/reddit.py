import random
from pathlib import Path

import requests

from ..core.models import ImageCandidate
from .base import ConfigField, ImageSource

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".gif", ".webp")
USER_AGENT = "varietywin/0.1 (wallpaper rotator; +https://github.com)"


class RedditSource(ImageSource):
    id = "reddit"
    display_name = "Reddit"
    requires_credentials = False

    @classmethod
    def config_fields(cls) -> list[ConfigField]:
        return [
            ConfigField(
                key="subreddits",
                label="Subreddits (comma-separated)",
                type="str",
                default="EarthPorn,wallpaper,wallpapers",
            ),
            ConfigField(
                key="sort",
                label="Sort",
                type="choice",
                choices=["hot", "top", "new"],
                default="hot",
            ),
            ConfigField(key="allow_nsfw", label="Allow NSFW", type="bool", default=False),
        ]

    def _subreddits(self) -> list[str]:
        raw = self.config.get("subreddits", "EarthPorn")
        return [s.strip() for s in raw.split(",") if s.strip()]

    def describe(self) -> str:
        return ", ".join(f"r/{name}" for name in self._subreddits())

    def fetch_candidates(self, count: int = 1) -> list[ImageCandidate]:
        subreddits = self._subreddits()
        if not subreddits:
            return []

        subreddit = random.choice(subreddits)
        sort = self.config.get("sort", "hot")
        allow_nsfw = self.config.get("allow_nsfw", False)
        url = f"https://www.reddit.com/r/{subreddit}/{sort}.json"
        resp = requests.get(
            url,
            params={"limit": max(count * 5, 25)},
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        posts = []
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            if post.get("stickied"):
                continue
            if post.get("over_18") and not allow_nsfw:
                continue
            image_url = post.get("url_overridden_by_dest") or post.get("url", "")
            if not image_url.lower().endswith(IMAGE_SUFFIXES):
                continue
            posts.append(post)

        if not posts:
            return []

        chosen = random.sample(posts, k=min(count, len(posts)))
        candidates = []
        for post in chosen:
            image_url = post.get("url_overridden_by_dest") or post["url"]
            candidates.append(
                ImageCandidate(
                    source_id=self.id,
                    remote_id=post["id"],
                    url=image_url,
                    title=post.get("title", ""),
                    author=post.get("author", ""),
                    source_page_url="https://www.reddit.com" + post.get("permalink", ""),
                )
            )
        return candidates

    def download(self, candidate: ImageCandidate, dest_dir: Path) -> Path:
        suffix = Path(candidate.url).suffix or ".jpg"
        dest = dest_dir / f"reddit_{candidate.remote_id}{suffix}"
        if not dest.exists():
            resp = requests.get(candidate.url, headers={"User-Agent": USER_AGENT}, timeout=30)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
        return dest
