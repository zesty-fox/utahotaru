# Update Protocol and Installer Handoffs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Windows-only updater contract with one signed update protocol and small installer-handoff plugins for every package channel.

**Architecture:** `UpdateService` owns channel selection, manifest verification, target matching, downloading, hash verification, and progress. A manifest-selected `InstallAction` chooses a capability plugin only after the artifact is verified. Plugins never implement release discovery or downloading, and a failed handoff leaves the installed application unchanged.

**Tech Stack:** Python 3.13, requests, cryptography Ed25519, PyQt6, pytest

---

## File Map

- Create `updater/model.py`: channels, targets, artifacts, actions, errors.
- Create `updater/signed_manifest.py`: schema parsing, Ed25519 verification, artifact selection.
- Create `updater/service.py`: shared update orchestration.
- Create `updater/handoffs/`: action plugins and registry.
- Modify `updater/worker.py`: run the shared service in Qt workers.
- Modify updater UI files: consume structured results and handoff outcomes.
- Retain `updater/installer.py` as the Windows helper adapter until the old updater is retired.
- Extend updater unit and UI tests.

### Task 1: Define Stable Update Types

**Files:**
- Create: `src/strange_uta_game/updater/model.py`
- Test: `tests/unit/updater/test_model.py`

- [ ] **Step 1: Write target and artifact tests**

```python
def test_target_key_includes_package_channel():
    target = UpdateTarget("linux", "x86_64", PackageChannel.FLATPAK)
    assert target.key == "linux-x86_64-flatpak"


def test_update_error_separates_user_and_diagnostic_messages():
    error = UpdateError(
        code="signature_invalid",
        user_message="更新信息签名无效",
        diagnostic="ed25519 verification failed for manifest-v2.json",
        recoverable=False,
    )
    assert "ed25519" not in error.user_message
    assert not error.recoverable
```

- [ ] **Step 2: Run tests and verify missing model**

Run: `pytest tests/unit/updater/test_model.py -v`

Expected: FAIL because `updater.model` is missing.

- [ ] **Step 3: Implement immutable update types**

```python
class ReleaseChannel(StrEnum):
    STABLE = "stable"
    PREVIEW = "preview"


class PackageChannel(StrEnum):
    WINDOWS_INSTALLER = "windows-installer"
    MACOS_DMG = "macos-dmg"
    APPIMAGE = "appimage"
    FLATPAK = "flatpak"
    DEB = "deb"


class InstallAction(StrEnum):
    RUN_INSTALLER = "run-installer"
    OPEN_PACKAGE = "open-package"
    REPLACE_APPIMAGE_ON_EXIT = "replace-appimage-on-exit"
    FLATPAK_UPDATE = "flatpak-update"


@dataclass(frozen=True)
class UpdateTarget:
    os: str
    arch: str
    package: PackageChannel

    @property
    def key(self) -> str:
        return f"{self.os}-{self.arch}-{self.package.value}"
```

Also define `UpdateArtifact`, `UpdateOffer`, `UpdateError`, and
`HandoffResult`. `UpdateError` is a value returned across worker boundaries,
not an exception shown directly to users.

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/updater/test_model.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/strange_uta_game/updater/model.py tests/unit/updater/test_model.py
git commit -m "feat: define cross-platform update model"
```

### Task 2: Parse and Select From Manifest Schema 2

**Files:**
- Create: `src/strange_uta_game/updater/signed_manifest.py`
- Create: `tests/fixtures/updater/manifest-v2.json`
- Test: `tests/unit/updater/test_signed_manifest.py`

- [ ] **Step 1: Add a complete fixture and selection tests**

The fixture contains both channels and at least these target keys:
`windows-x86_64-windows-installer`, `macos-universal2-macos-dmg`,
`linux-x86_64-appimage`, `linux-x86_64-flatpak`, and
`linux-x86_64-deb`.

```python
def test_selects_exact_target_and_channel(manifest_payload):
    manifest = parse_manifest(manifest_payload)
    offer = manifest.select(
        ReleaseChannel.PREVIEW,
        UpdateTarget("linux", "x86_64", PackageChannel.APPIMAGE),
    )
    assert offer.artifact.name.endswith(".AppImage")
    assert offer.artifact.action is InstallAction.REPLACE_APPIMAGE_ON_EXIT


def test_never_falls_back_to_another_architecture(manifest_payload):
    manifest = parse_manifest(manifest_payload)
    with pytest.raises(ManifestTargetError):
        manifest.select(
            ReleaseChannel.STABLE,
            UpdateTarget("linux", "aarch64", PackageChannel.FLATPAK),
        )
```

- [ ] **Step 2: Run tests and verify parser failure**

Run: `pytest tests/unit/updater/test_signed_manifest.py -v`

Expected: FAIL because `parse_manifest` is missing.

- [ ] **Step 3: Implement strict schema parsing**

The top-level schema is:

```json
{
  "schema": 2,
  "generated_at": "2026-06-20T00:00:00Z",
  "channels": {
    "stable": {
      "version": "2.0.0",
      "minimum_version": "1.2.3",
      "targets": {
        "linux-x86_64-appimage": {
          "name": "StrangeUtaGame-2.0.0-x86_64.AppImage",
          "url": "https://example.invalid/file",
          "size": 1,
          "sha256": "64-lowercase-hex-characters",
          "action": "replace-appimage-on-exit"
        }
      }
    }
  }
}
```

Reject unknown schema versions, missing fields, invalid hashes, non-HTTPS URLs,
duplicate target keys, and action/package mismatches. Do not silently select a
different architecture or package channel.

- [ ] **Step 4: Run parser and existing version tests**

Run: `pytest tests/unit/updater/test_signed_manifest.py tests/unit/updater/test_version.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/strange_uta_game/updater/signed_manifest.py tests/fixtures/updater/manifest-v2.json tests/unit/updater/test_signed_manifest.py
git commit -m "feat: parse target-aware update manifests"
```

### Task 3: Verify Manifest Signatures and Artifact Hashes

**Files:**
- Modify: `requirements.txt`
- Modify: `pyproject.toml`
- Modify: `src/strange_uta_game/updater/signed_manifest.py`
- Create: `src/strange_uta_game/config/update-public-key.pem`
- Test: `tests/unit/updater/test_update_signatures.py`

- [ ] **Step 1: Generate test-only keys and write verification tests**

```python
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
```

- [ ] **Step 2: Run tests and verify missing verification API**

Run: `pytest tests/unit/updater/test_update_signatures.py -v`

Expected: FAIL because signature verification is missing.

- [ ] **Step 3: Add Ed25519 verification**

Pin `cryptography` in requirements and add it to project dependencies. Load the
embedded public key with `serialization.load_pem_public_key`, require an
`Ed25519PublicKey`, decode detached signatures from base64, and verify the exact
downloaded manifest bytes before JSON parsing. Hash artifacts in 1 MiB chunks
using `hashlib.sha256()` and `hmac.compare_digest()`.

The committed PEM file contains only the release public key. The private key is
stored exclusively in protected CI secrets.

- [ ] **Step 4: Run signature tests**

Run: `pytest tests/unit/updater/test_update_signatures.py tests/unit/updater/test_signed_manifest.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt pyproject.toml src/strange_uta_game/config/update-public-key.pem src/strange_uta_game/updater/signed_manifest.py tests/unit/updater
git commit -m "feat: verify signed update manifests"
```

### Task 4: Implement Shared UpdateService

**Files:**
- Create: `src/strange_uta_game/updater/service.py`
- Modify: `src/strange_uta_game/updater/http_client.py`
- Modify: `src/strange_uta_game/updater/settings.py`
- Test: `tests/unit/updater/test_update_service.py`

- [ ] **Step 1: Write orchestration tests with a fake HTTP client**

```python
def test_check_verifies_before_parsing(fake_http, signed_manifest_bytes, target):
    service = UpdateService(fake_http, public_key=TEST_PUBLIC_KEY)
    offer = service.check(ReleaseChannel.STABLE, target, current_version="1.2.3")
    assert offer.version == "2.0.0"
    assert fake_http.requested[-1].endswith("manifest-v2.json.sig")


def test_download_removes_partial_file_after_hash_failure(
    fake_http, update_offer, tmp_path
):
    service = UpdateService(fake_http, public_key=TEST_PUBLIC_KEY)
    result = service.download(update_offer, tmp_path)
    assert result.error.code == "artifact_hash_invalid"
    assert list(tmp_path.iterdir()) == []
```

- [ ] **Step 2: Run tests and verify missing service**

Run: `pytest tests/unit/updater/test_update_service.py -v`

Expected: FAIL because `UpdateService` is missing.

- [ ] **Step 3: Implement check and download stages**

`check()` downloads manifest bytes and detached signature from each configured
source, verifies before parsing, selects the exact channel/target, and compares
versions. `download()` writes to `<name>.partial`, verifies length and SHA-256,
then atomically renames to the final cache path. It returns `UpdateError`
values for exhausted sources, bad signatures, bad hashes, insufficient disk,
and cancellation.

```python
@dataclass(frozen=True)
class DownloadResult:
    path: Path | None = None
    error: UpdateError | None = None

    @property
    def ok(self) -> bool:
        return self.path is not None and self.error is None
```

- [ ] **Step 4: Run updater service tests**

Run: `pytest tests/unit/updater/test_update_service.py tests/unit/updater/test_http_client.py tests/unit/updater/test_settings.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/strange_uta_game/updater/service.py src/strange_uta_game/updater/http_client.py src/strange_uta_game/updater/settings.py tests/unit/updater
git commit -m "feat: add shared update service"
```

### Task 5: Add Installer-Handoff Plugins

**Files:**
- Create: `src/strange_uta_game/updater/handoffs/base.py`
- Create: `src/strange_uta_game/updater/handoffs/registry.py`
- Create: `src/strange_uta_game/updater/handoffs/windows.py`
- Create: `src/strange_uta_game/updater/handoffs/open_package.py`
- Create: `src/strange_uta_game/updater/handoffs/appimage.py`
- Create: `src/strange_uta_game/updater/handoffs/flatpak.py`
- Modify: `src/strange_uta_game/updater/installer.py`
- Test: `tests/unit/updater/test_handoffs.py`

- [ ] **Step 1: Write registry and command tests**

```python
def test_registry_selects_by_manifest_action():
    registry = default_handoffs()
    assert isinstance(registry[InstallAction.OPEN_PACKAGE], OpenPackageHandoff)


def test_flatpak_handoff_uses_fixed_app_id(tmp_path):
    runner = FakeRunner(returncode=0)
    result = FlatpakHandoff(runner=runner).launch(tmp_path / "unused")
    assert runner.calls == [["flatpak", "update", "io.github.karaoke_studio.StrangeUtaGame", "-y"]]
    assert result.launched


def test_appimage_handoff_never_replaces_running_binary(tmp_path):
    current = tmp_path / "current.AppImage"
    current.write_bytes(b"current")
    handoff = AppImageHandoff(current=current)
    result = handoff.prepare(tmp_path / "new.AppImage")
    assert result.exit_required
    assert (tmp_path / "pending-update.json").exists()
    assert current.read_bytes() == b"current"
```

- [ ] **Step 2: Run tests and verify missing plugins**

Run: `pytest tests/unit/updater/test_handoffs.py -v`

Expected: FAIL because the handoff package is missing.

- [ ] **Step 3: Implement narrow action plugins**

Define:

```python
class InstallerHandoff(Protocol):
    def prepare(self, artifact: Path) -> HandoffResult: ...
```

The Windows implementation wraps the existing `launch_updater` behavior. The
open-package implementation uses `QDesktopServices.openUrl(QUrl.fromLocalFile())`
for notarized DMG and `.deb` files. AppImage writes a signed/hashed pending
record and launches a small replacement command only after the main PID exits.
Flatpak runs the fixed application ID without interpolating manifest strings.
All subprocess calls use argument lists and `shell=False`.

- [ ] **Step 4: Run handoff and legacy installer tests**

Run: `pytest tests/unit/updater/test_handoffs.py tests/unit/updater/test_installer.py tests/unit/updater/test_updater_main.py -v`

Expected: all tests pass; legacy Windows behavior is covered through its plugin.

- [ ] **Step 5: Commit**

```bash
git add src/strange_uta_game/updater/handoffs src/strange_uta_game/updater/installer.py tests/unit/updater
git commit -m "feat: add package-specific installer handoffs"
```

### Task 6: Connect Qt Workers and Update UI

**Files:**
- Modify: `src/strange_uta_game/updater/worker.py`
- Modify: `src/strange_uta_game/updater/ui/update_dialog.py`
- Modify: `src/strange_uta_game/updater/ui/update_progress_window.py`
- Modify: `src/strange_uta_game/frontend/settings/sub_interfaces/network.py`
- Test: `tests/unit/updater/test_worker_service.py`
- Test: `tests/unit/frontend/test_update_ui.py`

- [ ] **Step 1: Write worker result and localized-error tests**

```python
def test_worker_emits_offer_without_platform_fields(qtbot, update_service, target):
    worker = UpdateChecker(service=update_service, target=target)
    with qtbot.waitSignal(worker.check_finished) as signal:
        worker.check_now()
    assert signal.args[0].offer.target == target


def test_signature_error_disables_install_button(update_dialog):
    update_dialog.show_error(UpdateError("signature_invalid", "签名无效", "detail", False))
    assert not update_dialog.install_button.isEnabled()
```

- [ ] **Step 2: Run tests and verify old result mismatch**

Run: `pytest tests/unit/updater/test_worker_service.py tests/unit/frontend/test_update_ui.py -v`

Expected: FAIL because workers still emit the GitHub-release-specific result.

- [ ] **Step 3: Replace worker orchestration**

Workers call `UpdateService.check()` and `download()` and emit typed values.
Dialogs map stable error codes through `tr()`, display preview/stable channel and
package channel, and invoke the handoff registry only after a successful hash
check. Keep manual-download URL visible for every failure.

- [ ] **Step 4: Run complete updater tests**

Run: `pytest tests/unit/updater tests/unit/frontend/test_update_ui.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/strange_uta_game/updater src/strange_uta_game/frontend/settings/sub_interfaces/network.py tests/unit/updater tests/unit/frontend/test_update_ui.py
git commit -m "feat: connect UI to shared update service"
```

### Task 7: Add Destructive-Failure and Channel-Isolation Tests

**Files:**
- Create: `tests/integration/test_update_recovery.py`
- Create: `tests/integration/test_update_channels.py`
- Modify: `pytest.ini`
- Modify: `docs/auto_update.md`

- [ ] **Step 1: Write integration scenarios**

Cover interrupted download, invalid signature, invalid hash, handoff process
failure, AppImage pending replacement rollback, stable installation checking
preview, and preview installation checking stable. Each scenario starts with a
sentinel current executable and asserts its bytes are unchanged after failure.

```python
@pytest.mark.integration
def test_failed_handoff_keeps_current_install(update_sandbox):
    original = update_sandbox.current.read_bytes()
    result = update_sandbox.run_handoff(returncode=7)
    assert not result.launched
    assert update_sandbox.current.read_bytes() == original
```

- [ ] **Step 2: Run integration tests and verify missing sandbox fixture**

Run: `pytest tests/integration/test_update_recovery.py tests/integration/test_update_channels.py -v`

Expected: FAIL because `update_sandbox` is missing.

- [ ] **Step 3: Implement isolated update sandbox fixtures**

Use only temporary directories, fake HTTP responses, and fake subprocess
runners. Never modify the developer's current executable. Document schema 2,
key rotation, channels, package actions, and rollback behavior in
`docs/auto_update.md`.

- [ ] **Step 4: Run all updater tests**

Run: `pytest tests/unit/updater tests/integration/test_update_recovery.py tests/integration/test_update_channels.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/integration pytest.ini docs/auto_update.md
git commit -m "test: cover update recovery and channel isolation"
```

## Completion Gate

Run:

```bash
pytest tests/unit/updater tests/integration/test_update_recovery.py tests/integration/test_update_channels.py -v
python scripts/check_platform_boundaries.py
```

Expected: all update tests pass, stable and preview remain isolated, and no
failure modifies the sentinel current installation. Validate a locally signed
test manifest on every target package channel before Plan 04 publishes preview
artifacts.
