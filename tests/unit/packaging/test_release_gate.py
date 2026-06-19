import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from scripts.release_tools.targets import SUPPORTED_TARGETS
from scripts.verify_release_gate import verify_release_gate


@dataclass
class GateFixture:
    root: Path

    def remove(self, name: str) -> None:
        (self.root / name).unlink()


@pytest.fixture
def gate_fixture(tmp_path):
    version = "2.0.0"
    targets = {}
    for target in SUPPORTED_TARGETS.values():
        artifact = target.artifact_name(version)
        (tmp_path / artifact).write_bytes(b"artifact")
        if target.os == "linux":
            (tmp_path / f"{artifact}.asc").write_text("gpg signature", encoding="ascii")
        targets[target.id] = {"name": artifact}
        (tmp_path / f"verify-{target.id}.json").write_text(
            json.dumps({"passed": True}), encoding="utf-8"
        )
        (tmp_path / f"smoke-{target.id}.json").write_text(
            json.dumps(
                {
                    "schema": 1,
                    "started": True,
                    "opened_legacy_project": True,
                    "exported_srt": True,
                    "clean_exit": True,
                }
            ),
            encoding="utf-8",
        )
    manifest = {
        "schema": 2,
        "channels": {"stable": {"version": version, "targets": targets}},
    }
    (tmp_path / "manifest-v2.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "manifest-v2.json.sig").write_text("signature", encoding="ascii")
    for platform_name in ("windows-x86_64", "macos-universal2", "linux-x86_64"):
        (tmp_path / f"audio-{platform_name}.json").write_text(
            json.dumps({"schema": 1, "passed": True, "max_error_ms": 9.5}),
            encoding="utf-8",
        )
    return GateFixture(tmp_path)


def test_stable_gate_requires_all_artifacts_signatures_and_audio_reports(gate_fixture):
    assert verify_release_gate(gate_fixture.root).passed
    gate_fixture.remove("audio-linux-x86_64.json")

    result = verify_release_gate(gate_fixture.root)

    assert not result.passed
    assert "audio-linux-x86_64.json" in result.missing


def test_preview_gate_does_not_accept_stable_channel(gate_fixture):
    manifest_path = gate_fixture.root / "manifest-v2.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["channels"] = {"preview": manifest["channels"]["stable"]}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = verify_release_gate(gate_fixture.root, channel="preview")

    assert result.manifest_channel == "preview"
