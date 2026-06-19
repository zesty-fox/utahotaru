from strange_uta_game.runtime.capabilities import (
    Capability,
    CapabilityRegistry,
    CapabilityStatus,
)


def test_registry_reports_registered_capability():
    registry = CapabilityRegistry(
        {Capability.SYSTEM_PROXY: CapabilityStatus(True, "qt")}
    )
    assert registry.available(Capability.SYSTEM_PROXY)
    assert registry.status(Capability.SYSTEM_PROXY).provider == "qt"


def test_registry_returns_unavailable_for_missing_capability():
    registry = CapabilityRegistry()
    status = registry.status(Capability.RUBY_WINRT)
    assert not status.available
    assert status.provider == ""
