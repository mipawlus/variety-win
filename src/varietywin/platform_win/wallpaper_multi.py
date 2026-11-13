"""Per-monitor wallpapers through the IDesktopWallpaper COM interface (Windows 8+)."""

import ctypes
from ctypes import POINTER, c_int, c_uint, c_void_p, c_wchar_p
from ctypes.wintypes import RECT
from dataclasses import dataclass
from pathlib import Path

import comtypes
from comtypes import GUID, HRESULT, STDMETHOD, IUnknown

CLSID_DESKTOP_WALLPAPER = GUID("{C2CF3110-460E-4FC1-B9D0-8A1C0C9CC4BD}")

DWPOS_FILL = 4


class IDesktopWallpaper(IUnknown):
    _iid_ = GUID("{B92B56A9-8B55-4E14-9A89-0199BBB6F93B}")
    # Only the leading part of the vtable is declared; the order must match the SDK header.
    _methods_ = [
        STDMETHOD(HRESULT, "SetWallpaper", [c_wchar_p, c_wchar_p]),
        STDMETHOD(HRESULT, "GetWallpaper", [c_wchar_p, POINTER(c_void_p)]),
        STDMETHOD(HRESULT, "GetMonitorDevicePathAt", [c_uint, POINTER(c_void_p)]),
        STDMETHOD(HRESULT, "GetMonitorDevicePathCount", [POINTER(c_uint)]),
        STDMETHOD(HRESULT, "GetMonitorRECT", [c_wchar_p, POINTER(RECT)]),
        STDMETHOD(HRESULT, "SetBackgroundColor", [c_uint]),
        STDMETHOD(HRESULT, "GetBackgroundColor", [POINTER(c_uint)]),
        STDMETHOD(HRESULT, "SetPosition", [c_int]),
        STDMETHOD(HRESULT, "GetPosition", [POINTER(c_int)]),
    ]


@dataclass(frozen=True)
class Monitor:
    id: str
    index: int
    left: int
    top: int
    width: int
    height: int

    @property
    def label(self) -> str:
        return f"Monitor {self.index + 1} ({self.width}×{self.height})"


def _desktop_wallpaper():
    return comtypes.CoCreateInstance(
        CLSID_DESKTOP_WALLPAPER, interface=IDesktopWallpaper, clsctx=comtypes.CLSCTX_LOCAL_SERVER
    )


def _take_string(pointer: c_void_p) -> str:
    try:
        return ctypes.wstring_at(pointer.value) if pointer.value else ""
    finally:
        ctypes.windll.ole32.CoTaskMemFree(pointer)


def list_monitors() -> list[Monitor]:
    """Return the monitors currently attached to the desktop, left to right."""
    dw = _desktop_wallpaper()
    count = c_uint()
    dw.GetMonitorDevicePathCount(ctypes.byref(count))

    found = []
    for i in range(count.value):
        raw = c_void_p()
        dw.GetMonitorDevicePathAt(i, ctypes.byref(raw))
        monitor_id = _take_string(raw)
        if not monitor_id:
            continue
        rect = RECT()
        try:
            dw.GetMonitorRECT(monitor_id, ctypes.byref(rect))
        except comtypes.COMError:
            continue  # known to Windows but not currently attached
        width, height = rect.right - rect.left, rect.bottom - rect.top
        if width <= 0 or height <= 0:
            continue
        found.append((monitor_id, rect.left, rect.top, width, height))

    found.sort(key=lambda m: (m[1], m[2]))
    return [Monitor(m[0], index, m[1], m[2], m[3], m[4]) for index, m in enumerate(found)]


def set_wallpaper(monitor_id: str, path: Path) -> None:
    dw = _desktop_wallpaper()
    dw.SetPosition(DWPOS_FILL)
    dw.SetWallpaper(monitor_id, str(path.resolve()))
