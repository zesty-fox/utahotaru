"""Immutable values shared by update services, workers, and UI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ReleaseChannel(StrEnum):
    STABLE = "stable"
    PREVIEW = "preview"


class PackageChannel(StrEnum):
    WINDOWS_INSTALLER = "windows-installer"
    MACOS_DMG = "macos-dmg"
    APPIMAGE = "appimage"
    FLATPAK = "flatpak"
    DEB = "deb"


class InstallAction(StrEnum):
    RUN_INSTALLER = "run-installer"
    OPEN_PACKAGE = "open-package"
    REPLACE_APPIMAGE_ON_EXIT = "replace-appimage-on-exit"
    FLATPAK_UPDATE = "flatpak-update"


@dataclass(frozen=True)
class UpdateTarget:
    os: str
    arch: str
    package: PackageChannel

    @property
    def key(self) -> str:
        return f"{self.os}-{self.arch}-{self.package.value}"


@dataclass(frozen=True)
class UpdateArtifact:
    name: str
    url: str
    size: int
    sha256: str
    action: InstallAction


@dataclass(frozen=True)
class UpdateOffer:
    channel: ReleaseChannel
    version: str
    minimum_version: str
    target: UpdateTarget
    artifact: UpdateArtifact


@dataclass(frozen=True)
class UpdateError:
    code: str
    user_message: str
    diagnostic: str = ""
    recoverable: bool = True


@dataclass(frozen=True)
class HandoffResult:
    launched: bool = False
    exit_required: bool = False
    error: UpdateError | None = None
