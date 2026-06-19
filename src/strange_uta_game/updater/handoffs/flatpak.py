from __future__ import annotations

import subprocess
from pathlib import Path

from ..model import HandoffResult, UpdateError

FLATPAK_APP_ID = "io.github.karaoke_studio.StrangeUtaGame"


class FlatpakHandoff:
    def __init__(self, runner=subprocess):
        self._runner = runner

    def launch(self, artifact: Path) -> HandoffResult:
        _ = artifact
        try:
            result = self._runner.run(
                ["flatpak", "update", FLATPAK_APP_ID, "-y"],
                shell=False,
                check=False,
            )
        except OSError as error:
            return HandoffResult(
                error=UpdateError("flatpak_failed", "Flatpak 更新启动失败", str(error))
            )
        launched = result.returncode == 0
        error = None if launched else UpdateError(
            "flatpak_failed",
            "Flatpak 更新失败",
            f"exit code {result.returncode}",
        )
        return HandoffResult(launched=launched, error=error)

    def prepare(self, artifact: Path) -> HandoffResult:
        return self.launch(artifact)
