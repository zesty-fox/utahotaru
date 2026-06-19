from __future__ import annotations

import sys
from pathlib import Path

from ..model import InstallAction
from .appimage import AppImageHandoff
from .base import InstallerHandoff
from .flatpak import FlatpakHandoff
from .open_package import OpenPackageHandoff
from .windows import WindowsInstallerHandoff


def default_handoffs(
    current_appimage: Path | None = None,
) -> dict[InstallAction, InstallerHandoff]:
    current = current_appimage or Path(sys.argv[0])
    return {
        InstallAction.RUN_INSTALLER: WindowsInstallerHandoff(),
        InstallAction.OPEN_PACKAGE: OpenPackageHandoff(),
        InstallAction.REPLACE_APPIMAGE_ON_EXIT: AppImageHandoff(current),
        InstallAction.FLATPAK_UPDATE: FlatpakHandoff(),
    }
