from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices

from ..model import HandoffResult, UpdateError


class OpenPackageHandoff:
    def __init__(self, opener=QDesktopServices.openUrl):
        self._opener = opener

    def prepare(self, artifact: Path) -> HandoffResult:
        launched = bool(self._opener(QUrl.fromLocalFile(str(artifact))))
        error = None if launched else UpdateError(
            "package_open_failed",
            "无法打开系统安装包",
            str(artifact),
            True,
        )
        return HandoffResult(launched=launched, error=error)
