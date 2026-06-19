"""Lightweight detection for the optional WinRT Japanese reading provider."""

from __future__ import annotations

from contextlib import suppress


def winrt_japanese_status() -> tuple[bool, str]:
    """Return availability and a machine-readable reason without hard imports."""

    try:
        from winrt._winrt import STA, init_apartment  # type: ignore[import-not-found]
    except ImportError:
        return False, "no_winrt_package"
    try:
        with suppress(OSError):
            init_apartment(STA)
        from winrt.windows.globalization import (  # type: ignore[import-not-found]
            JapanesePhoneticAnalyzer,
        )

        words = JapanesePhoneticAnalyzer.get_words("日本語")
        reading = "".join(word.yomi_text or "" for word in words)
        has_kana = any("぀" <= char <= "ヿ" for char in reading)
        if words and reading and reading != "日本語" and has_kana:
            return True, "ok"
        return False, "engine_unavailable"
    except Exception as error:
        return False, f"error:{type(error).__name__}"
