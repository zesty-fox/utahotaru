"""Shared runtime bootstrap primitives."""

from .capabilities import Capability, CapabilityRegistry, CapabilityStatus
from .context import RuntimeContext, build_runtime_context
from .migration import MigrationResult, migrate_legacy_data
from .paths import AppPaths, build_app_paths, legacy_roots

__all__ = [
    "AppPaths",
    "Capability",
    "CapabilityRegistry",
    "CapabilityStatus",
    "MigrationResult",
    "RuntimeContext",
    "build_app_paths",
    "build_runtime_context",
    "legacy_roots",
    "migrate_legacy_data",
]
