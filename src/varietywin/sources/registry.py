from .base import ImageSource
from .bing import BingSource
from .earthview import EarthViewSource
from .local_folder import LocalFolderSource
from .reddit import RedditSource
from .unsplash import UnsplashSource
from .wallhaven import WallhavenSource

SOURCE_REGISTRY: dict[str, type[ImageSource]] = {
    LocalFolderSource.id: LocalFolderSource,
    WallhavenSource.id: WallhavenSource,
    UnsplashSource.id: UnsplashSource,
    BingSource.id: BingSource,
    EarthViewSource.id: EarthViewSource,
    RedditSource.id: RedditSource,
}


def get_source_class(source_id: str) -> type[ImageSource] | None:
    return SOURCE_REGISTRY.get(source_id)
