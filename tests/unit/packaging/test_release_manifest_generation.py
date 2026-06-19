from pathlib import Path

import pytest

from scripts.generate_release_manifest import (
    ReleaseArtifact,
    generate_manifest,
    serialize_manifest,
)
from scripts.release_tools.targets import SUPPORTED_TARGETS


class FakeGpgSigner:
    def __init__(self):
        self.signed = []

    def sign(self, path: Path) -> None:
        self.signed.append(path)


@pytest.fixture
def release_artifacts(tmp_path):
    artifacts = []
    for target in SUPPORTED_TARGETS.values():
        path = tmp_path / target.artifact_name("2.0.0")
        path.write_bytes(target.id.encode())
        artifacts.append(
            ReleaseArtifact(
                target=target,
                path=path,
                url=f"https://example.invalid/{path.name}",
            )
        )
    return artifacts


def test_manifest_contains_every_stable_target(release_artifacts):
    signer = FakeGpgSigner()

    manifest = generate_manifest(
        "2.0.0", "stable", release_artifacts, gpg_signer=signer
    )

    assert set(manifest["channels"]["stable"]["targets"]) == set(SUPPORTED_TARGETS)
    linux_paths = [item.path for item in release_artifacts if item.target.os == "linux"]
    assert signer.signed == linux_paths


def test_manifest_json_is_canonical(release_artifacts):
    first = serialize_manifest(generate_manifest("2.0.0", "preview", release_artifacts))
    second = serialize_manifest(
        generate_manifest("2.0.0", "preview", reversed(release_artifacts))
    )

    assert first == second
