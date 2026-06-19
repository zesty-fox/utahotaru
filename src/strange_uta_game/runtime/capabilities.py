"""Runtime capability identifiers and immutable availability registry."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class Capability(StrEnum):
    """Optional runtime capabilities exposed to shared application code."""

    RUBY_WINRT = "ruby_winrt"
    SYSTEM_PROXY = "system_proxy"
    INSTALLER_HANDOFF = "installer_handoff"
    THREAD_PRIORITY = "thread_priority"


@dataclass(frozen=True)
class CapabilityStatus:
    """Availability and provider metadata for one capability."""

    available: bool
    provider: str = ""
    reason: str = ""


class CapabilityRegistry:
    """Read-only snapshot of capabilities detected during bootstrap."""

    def __init__(
        self,
        statuses: Mapping[Capability, CapabilityStatus] | None = None,
    ) -> None:
        self._statuses = MappingProxyType(dict(statuses or {}))

    def status(self, capability: Capability) -> CapabilityStatus:
        """Return capability status, defaulting to unavailable."""

        return self._statuses.get(capability, CapabilityStatus(False))

    def available(self, capability: Capability) -> bool:
        """Return whether a capability is available."""

        return self.status(capability).available
