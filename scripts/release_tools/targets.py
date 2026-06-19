"""Closed cross-platform release target model and artifact naming."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BuildTarget:
    os: str
    arch: str
    package: str
    extension: str

    @property
    def id(self) -> str:
        return f"{self.os}-{self.arch}-{self.package}"

    @classmethod
    def parse(cls, target_id: str) -> BuildTarget:
        try:
            return SUPPORTED_TARGETS[target_id]
        except KeyError as error:
            raise ValueError(f"unsupported build target: {target_id}") from error

    @classmethod
    def from_legacy_alias(cls, alias: str) -> BuildTarget:
        try:
            return cls.parse(LEGACY_TARGET_ALIASES[alias])
        except KeyError as error:
            raise ValueError(f"unsupported legacy build alias: {alias}") from error

    def artifact_name(self, version: str) -> str:
        if self.package == "deb":
            return f"strangeutagame_{version}_amd64.deb"
        return f"StrangeUtaGame-{version}-{self.os}-{self.arch}{self.extension}"

    @property
    def legacy_build_variant(self) -> str:
        return "mac" if self.os == "macos" else "main"


SUPPORTED_TARGETS = {
    target.id: target
    for target in (
        BuildTarget("windows", "x86_64", "windows-installer", ".exe"),
        BuildTarget("macos", "universal2", "macos-dmg", ".dmg"),
        BuildTarget("linux", "x86_64", "appimage", ".AppImage"),
        BuildTarget("linux", "x86_64", "flatpak", ".flatpak"),
        BuildTarget("linux", "x86_64", "deb", ".deb"),
    )
}

LEGACY_TARGET_ALIASES = {
    "main": "windows-x86_64-windows-installer",
    "noWinIME": "windows-x86_64-windows-installer",
    "mac": "macos-universal2-macos-dmg",
}
