"""Cross-platform application paths and legacy location discovery."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QStandardPaths


@dataclass(frozen=True)
class AppPaths:
    """Canonical writable locations for standalone application data."""

    config: Path
    data: Path
    cache: Path

    def ensure(self) -> AppPaths:
        """Create all canonical directories and return this path set."""

        for path in (self.config, self.data, self.cache):
            path.mkdir(parents=True, exist_ok=True)
        return self


def _qt_resolver(key: str) -> Path:
    locations = {
        "config": QStandardPaths.StandardLocation.AppConfigLocation,
        "data": QStandardPaths.StandardLocation.AppDataLocation,
        "cache": QStandardPaths.StandardLocation.CacheLocation,
    }
    return Path(QStandardPaths.writableLocation(locations[key]))


def build_app_paths(
    resolver: Callable[[str], Path] = _qt_resolver,
) -> AppPaths:
    """Build canonical paths using Qt or an injected resolver."""

    return AppPaths(
        config=resolver("config"),
        data=resolver("data"),
        cache=resolver("cache"),
    )


def legacy_roots(program_dir: Path, cwd: Path) -> tuple[Path, ...]:
    """Return legacy standalone roots in migration precedence order."""

    roots: list[Path] = []
    redirect = program_dir / ".config_redirect"
    if redirect.is_file():
        candidate = Path(redirect.read_text(encoding="utf-8").strip())
        if candidate.is_dir():
            roots.append(candidate)
    for candidate in (program_dir, cwd, Path.home() / ".strange_uta_game"):
        if candidate not in roots:
            roots.append(candidate)
    return tuple(roots)
