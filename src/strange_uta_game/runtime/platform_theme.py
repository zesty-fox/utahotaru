"""Platform-specific theme detection behind a shared runtime interface."""

from __future__ import annotations

from dataclasses import dataclass

from strange_uta_game.runtime.platform_info import is_windows


@dataclass(frozen=True)
class ThemeHints:
    use_windows_registry: bool = False
    is_windows_10: bool = False


def detect_theme_hints() -> ThemeHints:
    if not is_windows():
        return ThemeHints()
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        ) as key:
            build_str, _ = winreg.QueryValueEx(key, "CurrentBuildNumber")
        return ThemeHints(use_windows_registry=True, is_windows_10=int(build_str) < 22000)
    except Exception:
        return ThemeHints(use_windows_registry=True)


def windows_apps_use_dark_theme() -> bool:
    """Read the Windows app theme, falling back to light on lookup failure."""

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return value == 0
    except Exception:
        return False
