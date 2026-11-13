"""Google Earth View: curated satellite images.

The Earth View website is retired, but its images are still hosted. There is no index to
query, so image numbers are probed at random within the ranges the collection uses.
"""

import base64
import logging
import random
from pathlib import Path

import requests

from ..core.models import ImageCandidate
from .base import ImageSource

logger = logging.getLogger(__name__)

IMAGE_URL = "https://www.gstatic.com/prettyearth/assets/full/{id}.jpg"
DATA_URL = "https://www.gstatic.com/prettyearth/assets/data/v3/{id}.json"

# Inclusive id ranges of the collection; not every number in a range exists.
ID_RANGES = ((1003, 2448), (5003, 6607), (7001, 7023))
MAX_PROBES_PER_FETCH = 12

# Remembered for the lifetime of the process, shared by all Earth View entries.
_known_good: set[int] = set()
_known_missing: set[int] = set()


def _random_id() -> int:
    start, end = random.choices(ID_RANGES, weights=[b - a + 1 for a, b in ID_RANGES])[0]
    return random.randint(start, end)


def _exists(image_id: int) -> bool:
    if image_id in _known_good:
        return True
    if image_id in _known_missing:
        return False
    resp = requests.head(IMAGE_URL.format(id=image_id), timeout=10)
    if resp.status_code == 404:
        _known_missing.add(image_id)
        return False
    resp.raise_for_status()
    _known_good.add(image_id)
    return True


class EarthViewSource(ImageSource):
    id = "earthview"
    display_name = "Google Earth View"
    requires_credentials = False

    def describe(self) -> str:
        return "satellite images"

    def fetch_candidates(self, count: int = 1) -> list[ImageCandidate]:
        found: list[int] = []
        for _ in range(MAX_PROBES_PER_FETCH):
            if len(found) >= count:
                break
            image_id = _random_id()
            if image_id not in found and _exists(image_id):
                found.append(image_id)
        return [
            ImageCandidate(
                source_id=self.id,
                remote_id=str(image_id),
                url=IMAGE_URL.format(id=image_id),
                title=f"Earth View {image_id}",
                extra={"resolution": "1800x1200"},
            )
            for image_id in found
        ]

    def download(self, candidate: ImageCandidate, dest_dir: Path) -> Path:
        dest = dest_dir / f"earthview_{candidate.remote_id}.jpg"
        if dest.exists():
            return dest

        # The data file holds the image together with where it was taken.
        try:
            resp = requests.get(DATA_URL.format(id=candidate.remote_id), timeout=30)
            resp.raise_for_status()
            data = resp.json()
            image_bytes = base64.b64decode(data["dataUri"].split(",", 1)[1])
            self._add_details(candidate, data)
        except Exception:
            logger.info("No Earth View data for %s, fetching the plain image", candidate.remote_id)
            resp = requests.get(candidate.url, timeout=30)
            resp.raise_for_status()
            image_bytes = resp.content

        dest.write_bytes(image_bytes)
        return dest

    @staticmethod
    def _add_details(candidate: ImageCandidate, data: dict) -> None:
        geocode = data.get("geocode") or {}
        place = [
            geocode.get("locality") or geocode.get("administrative_area_level_1"),
            geocode.get("country"),
        ]
        title = ", ".join(part for part in place if part)
        if title:
            candidate.title = title
        candidate.author = data.get("attribution", "")
        if "lat" in data and "lng" in data:
            zoom = data.get("zoom", 12)
            candidate.source_page_url = (
                f"https://www.google.com/maps/@{data['lat']},{data['lng']},{zoom}z/data=!3m1!1e3"
            )
