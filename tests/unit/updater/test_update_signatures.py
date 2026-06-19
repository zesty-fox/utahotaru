from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from strange_uta_game.updater.signed_manifest import (
    ArtifactHashError,
    ManifestSignatureError,
    verify_artifact_hash,
    verify_manifest_signature,
)


@pytest.fixture
def ed25519_keypair():
    private_key = Ed25519PrivateKey.generate()
    return private_key, private_key.public_key()


def test_manifest_signature_accepts_exact_bytes(ed25519_keypair):
    private_key, public_key = ed25519_keypair
    payload = b'{"schema":2}'
    signature = private_key.sign(payload)

    verify_manifest_signature(payload, signature, public_key)


def test_manifest_signature_rejects_modified_bytes(ed25519_keypair):
    private_key, public_key = ed25519_keypair
    signature = private_key.sign(b'{"schema":2}')

    with pytest.raises(ManifestSignatureError):
        verify_manifest_signature(b'{"schema":3}', signature, public_key)


def test_download_hash_rejects_partial_file(tmp_path):
    path = tmp_path / "artifact"
    path.write_bytes(b"partial")

    with pytest.raises(ArtifactHashError):
        verify_artifact_hash(path, "0" * 64)
