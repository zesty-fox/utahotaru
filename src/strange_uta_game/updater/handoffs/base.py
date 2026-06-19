from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..model import HandoffResult


class InstallerHandoff(Protocol):
    def prepare(self, artifact: Path) -> HandoffResult: ...
