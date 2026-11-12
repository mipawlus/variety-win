import ctypes
from pathlib import Path

SPI_SETDESKWALLPAPER = 0x0014
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02

_user32 = ctypes.windll.user32
_user32.SystemParametersInfoW.argtypes = [
    ctypes.c_uint,
    ctypes.c_uint,
    ctypes.c_wchar_p,
    ctypes.c_uint,
]
_user32.SystemParametersInfoW.restype = ctypes.c_int


def set_wallpaper(path: Path) -> None:
    abs_path = str(path.resolve())
    result = _user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER, 0, abs_path, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
    )
    if not result:
        raise OSError(f"SystemParametersInfoW failed to set wallpaper: {abs_path}")
