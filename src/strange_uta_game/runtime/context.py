"""Application runtime context construction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .capabilities import CapabilityRegistry
from .migration import migrate_legacy_data
from .paths import AppPaths, build_app_paths, legacy_roots


@dataclass(frozen=True)
class RuntimeContext:
    """Immutable services and paths detected during application bootstrap."""

    paths: AppPaths
    capabilities: CapabilityRegistry


def build_runtime_context(
    program_dir: Path,
    cwd: Path,
    *,
    app_paths: AppPaths | None = None,
) -> RuntimeContext:
    """Build shared runtime state and migrate legacy standalone data."""

    paths = (app_paths or build_app_paths()).ensure()
    migrate_legacy_data(paths, legacy_roots(program_dir, cwd))
    return RuntimeContext(paths=paths, capabilities=CapabilityRegistry())
