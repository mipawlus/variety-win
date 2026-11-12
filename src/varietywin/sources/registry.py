from .base import ImageSource
from .bing import BingSource
from .local_folder import LocalFolderSource
from .reddit import RedditSource
from .wallhaven import WallhavenSource

SOURCE_REGISTRY: dict[str, type[ImageSource]] = {
    LocalFolderSource.id: LocalFolderSource,
    BingSource.id: BingSource,
    RedditSource.id: RedditSource,
    WallhavenSource.id: WallhavenSource,
}


def get_source_class(source_id: str) -> type[ImageSource] | None:
    return SOURCE_REGISTRY.get(source_id)
