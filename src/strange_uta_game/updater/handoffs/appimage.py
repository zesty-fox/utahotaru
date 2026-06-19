from __future__ import annotations

import json
import os
from pathlib import Path

from ..model import HandoffResult, UpdateError


class AppImageHandoff:
    def __init__(self, current: Path, pending_path: Path | None = None):
        self._current = current
        self._pending_path = pending_path

    def prepare(self, artifact: Path) -> HandoffResult:
        pending_path = self._pending_path or artifact.parent / "pending-update.json"
        temporary = pending_path.with_suffix(".json.writing")
        record = {
            "schema": 1,
            "pid": os.getpid(),
            "current": str(self._current.resolve()),
            "artifact": str(artifact.resolve()),
        }
        try:
            artifact.chmod(artifact.stat().st_mode | 0o111)
            temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, pending_path)
        except OSError as error:
            temporary.unlink(missing_ok=True)
            return HandoffResult(
                error=UpdateError(
                    "appimage_handoff_failed",
                    "无法准备 AppImage 更新",
                    str(error),
                )
            )
        return HandoffResult(exit_required=True)
