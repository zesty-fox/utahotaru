#!/usr/bin/env python3
"""Verify collected release artifacts and reports before publication."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

try:
    from scripts.release_tools.targets import SUPPORTED_TARGETS
except ModuleNotFoundError:
    from release_tools.targets import SUPPORTED_TARGETS


@dataclass(frozen=True)
class GateResult:
    passed: bool
    missing: tuple[str, ...]
    invalid: tuple[str, ...]
    manifest_channel: str


def _read_json(path: Path, missing: list[str], invalid: list[str]) -> dict | None:
    if not path.is_file():
        missing.append(path.name)
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        invalid.append(path.name)
        return None
    if not isinstance(value, dict):
        invalid.append(path.name)
        return None
    return value


def verify_release_gate(root: Path, channel: str = "stable") -> GateResult:
    missing: list[str] = []
    invalid: list[str] = []
    manifest = _read_json(root / "manifest-v2.json", missing, invalid)
    signature = root / "manifest-v2.json.sig"
    if not signature.is_file():
        missing.append(signature.name)

    manifest_channel = ""
    targets = {}
    if manifest is not None:
        channels = manifest.get("channels")
        if not isinstance(channels, dict) or set(channels) != {channel}:
            invalid.append("manifest-v2.json:channel")
        else:
            manifest_channel = channel
            channel_data = channels[channel]
            if isinstance(channel_data, dict) and isinstance(channel_data.get("targets"), dict):
                targets = channel_data["targets"]
            else:
                invalid.append("manifest-v2.json:targets")

    expected_targets = set(SUPPORTED_TARGETS)
    if set(targets) != expected_targets:
        invalid.append("manifest-v2.json:target-set")
    for target_id, target in SUPPORTED_TARGETS.items():
        target_data = targets.get(target_id, {})
        artifact_name = target_data.get("name") if isinstance(target_data, dict) else None
        if not artifact_name:
            artifact_name = target.artifact_name("UNKNOWN")
            missing.append(f"artifact:{target_id}")
        elif not (root / artifact_name).is_file():
            missing.append(artifact_name)
        if target.os == "linux" and artifact_name and not (root / f"{artifact_name}.asc").is_file():
            missing.append(f"{artifact_name}.asc")

        verify_name = f"verify-{target_id}.json"
        verify_report = _read_json(root / verify_name, missing, invalid)
        if verify_report is not None and verify_report.get("passed") is not True:
            invalid.append(verify_name)

        smoke_name = f"smoke-{target_id}.json"
        smoke = _read_json(root / smoke_name, missing, invalid)
        required_smoke = (
            "started",
            "opened_legacy_project",
            "exported_srt",
            "clean_exit",
        )
        if smoke is not None and (
            smoke.get("schema") != 1
            or any(smoke.get(field) is not True for field in required_smoke)
        ):
            invalid.append(smoke_name)

    missing_result = tuple(sorted(set(missing)))
    invalid_result = tuple(sorted(set(invalid)))
    return GateResult(
        passed=not missing_result and not invalid_result,
        missing=missing_result,
        invalid=invalid_result,
        manifest_channel=manifest_channel,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--channel", choices=("stable", "preview"), default="stable")
    args = parser.parse_args()
    result = verify_release_gate(args.root, args.channel)
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
