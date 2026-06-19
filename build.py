"""Build the shared PyInstaller application payload for one native target."""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from scripts.release_tools.targets import SUPPORTED_TARGETS, BuildTarget

PROJECT_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class OsBuildConfig:
    os: str
    collect_all: tuple[str, ...]
    collect_submodules: tuple[str, ...]
    optional_collect_all: tuple[str, ...] = ()


@dataclass(frozen=True)
class BuildConfig:
    targets: tuple[OsBuildConfig, ...]

    def for_os(self, os_name: str) -> OsBuildConfig:
        for target in self.targets:
            if target.os == os_name:
                return target
        raise ValueError(f"unsupported build OS: {os_name}")


_SHARED_COLLECT_ALL = (
    "sounddevice",
    "soundfile",
    "pedalboard",
    "sudachipy",
)
_SHARED_SUBMODULES = ("strange_uta_game.updater",)
BUILD_CONFIG = BuildConfig(
    (
        OsBuildConfig(
            "windows",
            _SHARED_COLLECT_ALL,
            _SHARED_SUBMODULES,
            optional_collect_all=("winrt",),
        ),
        OsBuildConfig("macos", _SHARED_COLLECT_ALL, _SHARED_SUBMODULES),
        OsBuildConfig("linux", _SHARED_COLLECT_ALL, _SHARED_SUBMODULES),
    )
)


def _native_os() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    raise RuntimeError(f"unsupported build platform: {sys.platform}")


def _add_data(source: Path, destination: str) -> str:
    return f"--add-data={source}{os.pathsep}{destination}"


def make_pyinstaller_args(
    target: BuildTarget,
    project_root: Path = PROJECT_ROOT,
    *,
    clean: bool = False,
) -> list[str]:
    if target.os != _native_os():
        raise ValueError(f"target {target.id} must be built on native {target.os}")
    os_config = BUILD_CONFIG.for_os(target.os)
    package_root = project_root / "src" / "strange_uta_game"
    args = [
        str(project_root / "main.py"),
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name=StrangeUtaGame",
        f"--paths={project_root / 'src'}",
        f"--additional-hooks-dir={project_root / 'pyinstaller_hooks'}",
        _add_data(package_root / "config", "strange_uta_game/config"),
        _add_data(package_root / "resource", "strange_uta_game/resource"),
        "--collect-data=sudachidict_small",
        "--exclude-module=strange_uta_game.backend.infrastructure.audio.bass_engine",
        "--exclude-module=strange_uta_game.backend.infrastructure.audio.bass_tsm_engine",
    ]
    if clean:
        args.append("--clean")
    icon = package_root / "resource" / (
        "icon.icns" if target.os == "macos" else "icon.ico"
    )
    args.append(f"--icon={icon}")
    for package in os_config.collect_all:
        args.append(f"--collect-all={package}")
    for package in os_config.collect_submodules:
        args.append(f"--collect-submodules={package}")
    for package in os_config.optional_collect_all:
        if importlib.util.find_spec(package) is not None:
            args.append(f"--collect-all={package}")
    if target.os == "macos":
        args.append("--target-architecture=universal2")
    return args


def _verify_universal_python() -> None:
    result = subprocess.run(
        ["lipo", "-archs", sys.executable],
        capture_output=True,
        text=True,
        check=True,
    )
    architectures = set(result.stdout.split())
    if not {"arm64", "x86_64"}.issubset(architectures):
        raise RuntimeError("macOS Universal builds require a universal2 Python interpreter")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument("--target", choices=sorted(SUPPORTED_TARGETS))
    target_group.add_argument("--variant", choices=("main", "noWinIME", "mac"))
    parser.add_argument("--clean", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.target:
        target = BuildTarget.parse(args.target)
    else:
        target = BuildTarget.from_legacy_alias(args.variant)
        print(f"! --variant {args.variant} 已弃用；请改用 --target {target.id}")
    if target.os == "macos":
        _verify_universal_python()
    from PyInstaller.__main__ import run

    run(make_pyinstaller_args(target, clean=args.clean))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
