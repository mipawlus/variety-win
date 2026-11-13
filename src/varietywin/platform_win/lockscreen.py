"""Set the Windows lock screen picture through the WinRT LockScreen API."""

import logging
import threading
from pathlib import Path

from winrt.windows.storage import StorageFile
from winrt.windows.system.userprofile import LockScreen

logger = logging.getLogger(__name__)

_lock = threading.Lock()


def set_lock_screen(path: Path) -> None:
    """Blocks until Windows has taken the image. Do not call on the UI thread."""
    with _lock:
        file = StorageFile.get_file_from_path_async(str(path.resolve())).get()
        LockScreen.set_image_file_async(file).get()


def set_lock_screen_in_background(path: Path) -> threading.Thread:
    def work() -> None:
        try:
            set_lock_screen(path)
        except Exception:
            logger.exception("Could not set the lock screen picture to %s", path)

    thread = threading.Thread(target=work, name="lockscreen", daemon=True)
    thread.start()
    return thread
