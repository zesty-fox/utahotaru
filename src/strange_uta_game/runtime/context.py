"""Application runtime context construction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .capabilities import Capability, CapabilityRegistry, CapabilityStatus
from .migration import migrate_legacy_data
from .paths import AppPaths, build_app_paths, legacy_roots
from .winrt import winrt_japanese_status


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
    winrt_available, winrt_reason = winrt_japanese_status()
    capabilities = CapabilityRegistry(
        {
            Capability.RUBY_WINRT: CapabilityStatus(
                available=winrt_available,
                provider="winrt" if winrt_available else "",
                reason=winrt_reason,
            )
        }
    )
    return RuntimeContext(paths=paths, capabilities=capabilities)
