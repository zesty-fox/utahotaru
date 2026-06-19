from __future__ import annotations

from pathlib import Path

from ..installer import launch_verified_installer
from ..model import HandoffResult, UpdateError


class WindowsInstallerHandoff:
    def __init__(self, launcher=launch_verified_installer):
        self._launcher = launcher

    def prepare(self, artifact: Path) -> HandoffResult:
        result = self._launcher(artifact)
        error = None if result.launched else UpdateError(
            "installer_launch_failed",
            "无法启动 Windows 安装程序",
            result.reason,
        )
        return HandoffResult(
            launched=result.launched,
            exit_required=result.launched,
            error=error,
        )
