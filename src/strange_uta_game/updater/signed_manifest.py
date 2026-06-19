"""Strict parsing and selection for signed update manifest schema 2."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any
from urllib.parse import urlparse

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
