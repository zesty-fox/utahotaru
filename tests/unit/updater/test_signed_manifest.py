import json
from pathlib import Path

import pytest

from strange_uta_game.updater.model import PackageChannel, ReleaseChannel, UpdateTarget
from strange_uta_game.updater.signed_manifest import ManifestTargetError, parse_manifest


@pytest.fixture
def manifest_payload():
    path = Path(__file__).resolve().parents[2] / "fixtures" / "updater" / "manifest-v2.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_selects_exact_target_and_channel(manifest_payload):
    manifest = parse_manifest(manifest_payload)

    offer = manifest.select(
        ReleaseChannel.PREVIEW,
        UpdateTarget("linux", "x86_64", PackageChannel.APPIMAGE),
    )

    assert offer.artifact.name.endswith(".AppImage")
    assert offer.artifact.action.value == "replace-appimage-on-exit"


def test_never_falls_back_to_another_architecture(manifest_payload):
    manifest = parse_manifest(manifest_payload)

    with pytest.raises(ManifestTargetError):
        manifest.select(
            ReleaseChannel.STABLE,
            UpdateTarget("linux", "aarch64", PackageChannel.FLATPAK),
        )
