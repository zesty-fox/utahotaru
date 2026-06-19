from __future__ import annotations

import pytest

from strange_uta_game.backend.infrastructure.parsers.ruby_analyzer import (
    ProviderChain,
    ProviderUnavailableError,
    RubyAnalyzer,
    RubyResult,
    build_provider_chain,
)


class FailingProvider(RubyAnalyzer):
    name = "failing"

    def analyze(self, text: str) -> list[RubyResult]:
        raise ProviderUnavailableError("offline")

    def get_reading(self, text: str) -> str:
        raise ProviderUnavailableError("offline")


class StubProvider(RubyAnalyzer):
    name = "stub"

    def __init__(self, reading: str):
        self.reading = reading

    def analyze(self, text: str) -> list[RubyResult]:
        return [RubyResult(text, self.reading, 0, len(text))]

    def get_reading(self, text: str) -> str:
        return self.reading


class BrokenProvider(FailingProvider):
    name = "broken"

    def get_reading(self, text: str) -> str:
        raise ValueError("malformed provider result")


def test_windows_capability_preserves_winrt_first():
    providers = build_provider_chain(winrt_available=True)

    assert [provider.name for provider in providers] == [
        "winrt",
        "sudachi",
        "pykakasi",
    ]


def test_shared_chain_works_without_winrt():
    providers = build_provider_chain(winrt_available=False)

    assert [provider.name for provider in providers] == ["sudachi", "pykakasi"]


def test_provider_failure_falls_through():
    analyzer = ProviderChain((FailingProvider(), StubProvider("にほんご")))

    assert analyzer.get_reading("日本語") == "にほんご"


def test_programming_errors_are_not_hidden_by_fallback():
    analyzer = ProviderChain((BrokenProvider(), StubProvider("にほんご")))

    with pytest.raises(ValueError, match="malformed"):
        analyzer.get_reading("日本語")
