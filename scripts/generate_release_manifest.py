#!/usr/bin/env python3
"""Generate canonical schema-2 update manifests and detached signatures."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

try:
    from scripts.release_tools.targets import SUPPORTED_TARGETS, BuildTarget
except ModuleNotFoundError:  # direct ``python scripts/...`` execution
    from release_tools.targets import SUPPORTED_TARGETS, BuildTarget

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ReleaseArtifact:
    target: BuildTarget
    path: Path
    url: str


class ArtifactSigner(Protocol):
    def sign(self, path: Path) -> None: ...


class GpgSigner:
    def sign(self, path: Path) -> None:
        signature = path.with_name(f"{path.name}.asc")
        subprocess.run(
            [
                "gpg",
                "--batch",
                "--yes",
                "--armor",
                "--detach-sign",
                "--output",
                str(signature),
                str(path),
            ],
            check=True,
        )
        subprocess.run(
            ["gpg", "--batch", "--verify", str(signature), str(path)],
            check=True,
        )


_ACTION_BY_PACKAGE = {
    "windows-installer": "run-installer",
    "macos-dmg": "open-package",
    "appimage": "replace-appimage-on-exit",
    "flatpak": "flatpak-update",
    "deb": "open-package",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def generate_manifest(
    version: str,
    channel: str,
    artifacts: Iterable[ReleaseArtifact],
    *,
    gpg_signer: ArtifactSigner | None = None,
    minimum_version: str = "1.2.3",
    generated_at: str = "1970-01-01T00:00:00Z",
) -> dict:
    if channel not in {"stable", "preview"}:
        raise ValueError(f"invalid release channel: {channel}")
    artifacts = list(artifacts)
    if gpg_signer is not None:
        for artifact in artifacts:
            if artifact.target.os == "linux":
                gpg_signer.sign(artifact.path)
    targets = {}
    for artifact in sorted(artifacts, key=lambda item: item.target.id):
        if artifact.target.id in targets:
            raise ValueError(f"duplicate artifact target: {artifact.target.id}")
        if not artifact.path.is_file() or not artifact.url.startswith("https://"):
            raise ValueError(f"invalid release artifact: {artifact.target.id}")
        targets[artifact.target.id] = {
            "name": artifact.path.name,
            "url": artifact.url,
            "size": artifact.path.stat().st_size,
            "sha256": _sha256(artifact.path),
            "action": _ACTION_BY_PACKAGE[artifact.target.package],
        }
    if channel == "stable" and set(targets) != set(SUPPORTED_TARGETS):
        missing = sorted(set(SUPPORTED_TARGETS) - set(targets))
        raise ValueError(f"stable release is missing targets: {missing}")
    return {
        "schema": 2,
        "generated_at": generated_at,
        "channels": {
            channel: {
                "version": version,
                "minimum_version": minimum_version,
                "targets": targets,
            }
        },
    }


def serialize_manifest(manifest: dict) -> bytes:
    return json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _load_private_key(encoded: str) -> Ed25519PrivateKey:
    raw = base64.b64decode(encoded, validate=True)
    if len(raw) == 32:
        return Ed25519PrivateKey.from_private_bytes(raw)
    key = serialization.load_pem_private_key(raw, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("UPDATE_ED25519_PRIVATE_KEY_B64 is not an Ed25519 key")
    return key


def _parse_artifact(value: str, base_url: str) -> ReleaseArtifact:
    target_id, separator, raw_path = value.partition("=")
    if not separator:
        raise ValueError("artifact must use TARGET=PATH syntax")
    path = Path(raw_path)
    return ReleaseArtifact(
        BuildTarget.parse(target_id),
        path,
        f"{base_url.rstrip('/')}/{path.name}",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("channel", choices=("stable", "preview"))
    parser.add_argument("--artifact", action="append", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--gpg-sign-linux", action="store_true")
    args = parser.parse_args(argv)

    artifacts = [_parse_artifact(value, args.base_url) for value in args.artifact]
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    manifest = generate_manifest(
        args.version,
        args.channel,
        artifacts,
        gpg_signer=GpgSigner() if args.gpg_sign_linux else None,
        generated_at=generated_at,
    )
    payload = serialize_manifest(manifest)
    private_value = os.environ.get("UPDATE_ED25519_PRIVATE_KEY_B64", "")
    if not private_value:
        raise SystemExit("UPDATE_ED25519_PRIVATE_KEY_B64 is required")
    private_key = _load_private_key(private_value)
    signature = private_key.sign(payload)
    public_key_path = (
        ROOT / "src/strange_uta_game/config/update-public-key.pem"
    )
    embedded_key = serialization.load_pem_public_key(public_key_path.read_bytes())
    if not isinstance(embedded_key, Ed25519PublicKey):
        raise SystemExit("embedded update public key is not Ed25519")
    if embedded_key.public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    ) != private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    ):
        raise SystemExit("update private key does not match embedded public key")
    embedded_key.verify(signature, payload)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "manifest-v2.json").write_bytes(payload)
    (args.output_dir / "manifest-v2.json.sig").write_bytes(
        base64.b64encode(signature) + b"\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
