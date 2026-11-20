"""Stop Windows from recompressing wallpapers.

Windows re-encodes every JPEG wallpaper at quality 85 before showing it, which adds
visible blocks and banding to skies and gradients. The `JPEGImportQuality` value
raises that to 100. It only affects how wallpapers are stored, and is per user.
"""

import logging
import winreg

logger = logging.getLogger(__name__)

DESKTOP_KEY = r"Control Panel\Desktop"
VALUE_NAME = "JPEGImportQuality"
FULL_QUALITY = 100


def current_quality(key_path: str = DESKTOP_KEY) -> int | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return int(value)
    except (FileNotFoundError, ValueError, TypeError):
        return None


def ensure_full_quality(key_path: str = DESKTOP_KEY) -> bool:
    """Returns True if the setting was changed. Applies from the next wallpaper on."""
    if current_quality(key_path) == FULL_QUALITY:
        return False
    try:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_DWORD, FULL_QUALITY)
    except OSError:
        logger.exception("Could not turn off wallpaper recompression")
        return False
    logger.info("Turned off Windows wallpaper recompression (%s = 100)", VALUE_NAME)
    return True
