"""Start Mimamori when Windows starts (per-user, no admin needed).

This is the one thing Mimamori writes outside its own folder: a single value
under HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run. Turning the option
off removes it again.
"""
from __future__ import annotations

import sys

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Mimamori"


def supported() -> bool:
    """Only for the built exe on Windows (not when running from source)."""
    return sys.platform == "win32" and getattr(sys, "frozen", False)


def _command() -> str:
    return f'"{sys.executable}" --minimized'


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            value, _ = winreg.QueryValueEx(k, VALUE_NAME)
            return bool(value)
    except OSError:
        return False


def points_here() -> bool:
    """True if the startup entry launches this exe (not an old/moved copy)."""
    if not is_enabled():
        return False
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
        value, _ = winreg.QueryValueEx(k, VALUE_NAME)
    return value == _command()


def set_enabled(enabled: bool) -> None:
    if sys.platform != "win32":
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enabled:
            winreg.SetValueEx(k, VALUE_NAME, 0, winreg.REG_SZ, _command())
        else:
            try:
                winreg.DeleteValue(k, VALUE_NAME)
            except FileNotFoundError:
                pass
