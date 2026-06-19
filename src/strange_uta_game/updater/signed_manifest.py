"""Strict parsing and selection for signed update manifest schema 2."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any
from urllib.parse import urlparse

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .model import (
    InstallAction,
    PackageChannel,
    ReleaseChannel,
    UpdateArtifact,
    UpdateOffer,
    UpdateTarget,
)


class ManifestError(ValueError):
    pass


class ManifestTargetError(ManifestError):
    pass


class ManifestSignatureError(ManifestError):
    pass


class ArtifactHashError(ManifestError):
    pass


@dataclass(frozen=True)
class _ChannelManifest:
    version: str
    minimum_version: str
    targets: Mapping[str, UpdateArtifact]


@dataclass(frozen=True)
class SignedManifest:
    generated_at: str
    channels: Mapping[ReleaseChannel, _ChannelManifest]

    def select(self, channel: ReleaseChannel, target: UpdateTarget) -> UpdateOffer:
        channel_manifest = self.channels.get(channel)
        if channel_manifest is None:
            raise ManifestTargetError(f"release channel is unavailable: {channel.value}")
        artifact = channel_manifest.targets.get(target.key)
        if artifact is None:
            raise ManifestTargetError(f"update target is unavailable: {target.key}")
        return UpdateOffer(
            channel=channel,
            version=channel_manifest.version,
            minimum_version=channel_manifest.minimum_version,
            target=target,
            artifact=artifact,
        )


_ACTION_BY_PACKAGE = {
    PackageChannel.WINDOWS_INSTALLER: InstallAction.RUN_INSTALLER,
    PackageChannel.MACOS_DMG: InstallAction.OPEN_PACKAGE,
    PackageChannel.APPIMAGE: InstallAction.REPLACE_APPIMAGE_ON_EXIT,
    PackageChannel.FLATPAK: InstallAction.FLATPAK_UPDATE,
    PackageChannel.DEB: InstallAction.OPEN_PACKAGE,
}
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _required(mapping: Mapping[str, Any], key: str, expected_type: type) -> Any:
    if key not in mapping or not isinstance(mapping[key], expected_type):
        raise ManifestError(f"missing or invalid field: {key}")
    return mapping[key]


def _target_from_key(key: str) -> UpdateTarget:
    for package in PackageChannel:
        suffix = f"-{package.value}"
        if not key.endswith(suffix):
            continue
        platform_arch = key[: -len(suffix)]
        if "-" not in platform_arch:
            break
        os_name, arch = platform_arch.split("-", 1)
        target = UpdateTarget(os_name, arch, package)
        if target.key == key:
            return target
    raise ManifestError(f"invalid target key: {key}")


def _parse_artifact(key: str, payload: Mapping[str, Any]) -> UpdateArtifact:
    target = _target_from_key(key)
    name = _required(payload, "name", str)
    url = _required(payload, "url", str)
    size = _required(payload, "size", int)
    sha256 = _required(payload, "sha256", str)
    action_value = _required(payload, "action", str)
    if not name or size <= 0 or urlparse(url).scheme != "https":
        raise ManifestError(f"invalid artifact metadata for target: {key}")
    if not _SHA256.fullmatch(sha256):
        raise ManifestError(f"invalid sha256 for target: {key}")
    try:
        action = InstallAction(action_value)
    except ValueError as error:
        raise ManifestError(f"invalid install action for target: {key}") from error
    if action is not _ACTION_BY_PACKAGE[target.package]:
        raise ManifestError(f"install action does not match package: {key}")
    return UpdateArtifact(name, url, size, sha256, action)


def parse_manifest(payload: Mapping[str, Any]) -> SignedManifest:
    if payload.get("schema") != 2:
        raise ManifestError("unsupported update manifest schema")
    generated_at = _required(payload, "generated_at", str)
    raw_channels = _required(payload, "channels", dict)
    channels: dict[ReleaseChannel, _ChannelManifest] = {}
    for channel_name, channel_payload in raw_channels.items():
        try:
            channel = ReleaseChannel(channel_name)
        except ValueError as error:
            raise ManifestError(f"unknown release channel: {channel_name}") from error
        if not isinstance(channel_payload, dict):
            raise ManifestError(f"invalid channel: {channel_name}")
        version = _required(channel_payload, "version", str)
        minimum_version = _required(channel_payload, "minimum_version", str)
        raw_targets = _required(channel_payload, "targets", dict)
        targets = {
            key: _parse_artifact(key, value)
            for key, value in raw_targets.items()
            if isinstance(key, str) and isinstance(value, dict)
        }
        if len(targets) != len(raw_targets) or not targets:
            raise ManifestError(f"invalid targets for channel: {channel_name}")
        channels[channel] = _ChannelManifest(
            version,
            minimum_version,
            MappingProxyType(targets),
        )
    if not generated_at or not channels:
        raise ManifestError("manifest has no channels")
    return SignedManifest(generated_at, MappingProxyType(channels))


def verify_manifest_signature(
    payload: bytes,
    signature: bytes | str,
    public_key: Ed25519PublicKey | bytes,
) -> None:
    """Verify a detached Ed25519 signature over exact manifest bytes."""

    if isinstance(public_key, bytes):
        try:
            loaded_key = serialization.load_pem_public_key(public_key)
        except (TypeError, ValueError) as error:
            raise ManifestSignatureError("invalid update public key") from error
        if not isinstance(loaded_key, Ed25519PublicKey):
            raise ManifestSignatureError("update public key is not Ed25519")
        public_key = loaded_key
    raw_signature: bytes
    if isinstance(signature, str):
        signature = signature.encode("ascii")
    if len(signature) == 64:
        raw_signature = signature
    else:
        try:
            raw_signature = base64.b64decode(signature.strip(), validate=True)
        except (binascii.Error, ValueError) as error:
            raise ManifestSignatureError("invalid detached signature encoding") from error
    try:
        public_key.verify(raw_signature, payload)
    except (InvalidSignature, ValueError) as error:
        raise ManifestSignatureError("manifest signature verification failed") from error


def verify_artifact_hash(path: Path, expected_sha256: str) -> None:
    """Verify an artifact with bounded memory and constant-time comparison."""

    if not _SHA256.fullmatch(expected_sha256):
        raise ArtifactHashError("invalid expected artifact hash")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    if not hmac.compare_digest(digest.hexdigest(), expected_sha256):
        raise ArtifactHashError("artifact hash verification failed")
