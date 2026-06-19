# Packaging, Signing, and Release Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce installable, verifiable preview and stable artifacts for Windows x64, macOS Universal, and Linux x64 from one shared application definition.

**Architecture:** A `BuildTarget` replaces product variants and describes only OS, architecture, and package channel. PyInstaller creates the shared application payload on native runners; thin platform packagers wrap that payload. Preview releases publish continuously, while stable publication requires every target, signature check, package smoke test, compatibility test, and real-device audio report.

**Tech Stack:** PyInstaller, GitHub Actions, Inno Setup, Apple codesign/notarytool, linuxdeploy/AppImage, Flatpak Builder, dpkg-deb, GPG, pytest

---

## File Map

- Create `scripts/release_tools/targets.py`: shared target model and artifact naming.
- Refactor `build.py`, `build_all.py`, and `scripts/release.py`: target-based builds.
- Create `packaging/windows/StrangeUtaGame.iss`: signed installer definition.
- Create `packaging/macos/entitlements.plist` and scripts: Universal validation, signing, DMG, notarization.
- Create `packaging/linux/`: AppDir assembly, Flatpak manifest, Debian metadata.
- Create `.github/workflows/test.yml`, `preview.yml`, and revise `release.yml`.
- Create package smoke and manifest-generation tests.
- Update release documentation.

### Task 1: Replace Product Variants With BuildTarget

**Files:**
- Create: `scripts/release_tools/__init__.py`
- Create: `scripts/release_tools/targets.py`
- Modify: `scripts/release.py:112-190,1099-1185`
- Modify: `build_all.py:30-107`
- Test: `tests/unit/packaging/test_targets.py`
- Modify: `tests/unit/updater/test_release_script.py`

- [ ] **Step 1: Write target and naming tests**

```python
@pytest.mark.parametrize(
    (target_id, artifact),
    [
        ("windows-x86_64-windows-installer", "StrangeUtaGame-2.0.0-windows-x86_64.exe"),
        ("macos-universal2-macos-dmg", "StrangeUtaGame-2.0.0-macos-universal2.dmg"),
        ("linux-x86_64-appimage", "StrangeUtaGame-2.0.0-linux-x86_64.AppImage"),
        ("linux-x86_64-flatpak", "StrangeUtaGame-2.0.0-linux-x86_64.flatpak"),
        ("linux-x86_64-deb", "strangeutagame_2.0.0_amd64.deb"),
    ],
)
def test_artifact_names_are_stable(target_id, artifact):
    assert BuildTarget.parse(target_id).artifact_name("2.0.0") == artifact


def test_target_rejects_os_arch_mismatch():
    with pytest.raises(ValueError):
        BuildTarget.parse("windows-universal2-windows-installer")
```

- [ ] **Step 2: Run tests and verify missing target model**

Run: `pytest tests/unit/packaging/test_targets.py -v`

Expected: FAIL because `packaging.targets` is missing.

- [ ] **Step 3: Implement the closed target set**

```python
SUPPORTED_TARGETS = {
    "windows-x86_64-windows-installer": BuildTarget("windows", "x86_64", "windows-installer", ".exe"),
    "macos-universal2-macos-dmg": BuildTarget("macos", "universal2", "macos-dmg", ".dmg"),
    "linux-x86_64-appimage": BuildTarget("linux", "x86_64", "appimage", ".AppImage"),
    "linux-x86_64-flatpak": BuildTarget("linux", "x86_64", "flatpak", ".flatpak"),
    "linux-x86_64-deb": BuildTarget("linux", "x86_64", "deb", ".deb"),
}
```

`BuildTarget.parse()` only accepts keys in this mapping. Refactor release CLI
from `--variant` to `--target`; retain a deprecated parser alias mapping
`main -> windows-x86_64-windows-installer`, `mac -> macos-universal2-macos-dmg`, and
`noWinIME -> windows-x86_64-windows-installer` for one release cycle. Do not encode
reading providers or audio backends in target names.

- [ ] **Step 4: Run target and release-script tests**

Run: `pytest tests/unit/packaging/test_targets.py tests/unit/updater/test_release_script.py -v`

Expected: all tests pass, including deprecated alias warnings.

- [ ] **Step 5: Commit**

```bash
git add scripts/release_tools scripts/release.py build_all.py tests/unit/packaging tests/unit/updater/test_release_script.py
git commit -m "refactor: model releases as platform targets"
```

### Task 2: Build One Shared PyInstaller Payload Per Native OS

**Files:**
- Modify: `build.py`
- Modify: `pyproject.toml`
- Modify: `requirements.txt`
- Modify: `requirements-winrt.txt`
- Delete: `requirements-variants.txt`
- Create: `tests/unit/packaging/test_build_config.py`

- [ ] **Step 1: Write tests for shared dependency and data collection**

```python
def test_all_targets_collect_shared_runtime_packages(build_config):
    for target in build_config.targets:
        assert "sounddevice" in target.collect_all
        assert "sudachipy" in target.collect_all
        assert "strange_uta_game.updater" in target.collect_submodules


def test_only_windows_collects_optional_winrt(build_config):
    assert "winrt" in build_config.for_os("windows").optional_collect_all
    assert "winrt" not in build_config.for_os("macos").optional_collect_all
    assert "winrt" not in build_config.for_os("linux").optional_collect_all
```

- [ ] **Step 2: Run tests and verify current variant mismatch**

Run: `pytest tests/unit/packaging/test_build_config.py -v`

Expected: FAIL because build configuration is keyed by variants.

- [ ] **Step 3: Refactor build.py into importable configuration plus CLI**

Move argument parsing and `PyInstaller.__main__.run()` under `main()`. Create a
`make_pyinstaller_args(target, project_root)` function that returns shared
arguments plus small native additions. Use `--target-architecture=universal2`
for macOS and reject a non-universal Python interpreter before building.

Merge Sudachi dependencies into the shared locked requirements and delete
`requirements-variants.txt`. Keep `requirements-winrt.txt` as a Windows-only
dependency input referenced by CI, not as a product variant.
Set package data to include `.wav`, `.ico`, `.icns`, translations, dictionaries,
and the update public key; stop collecting BASS DLLs for stable targets.

- [ ] **Step 4: Run build-config and embedded-contract tests**

Run: `pytest tests/unit/packaging/test_build_config.py tests/unit/test_embedded_contract.py -v`

Expected: all tests pass and importing `build` does not start PyInstaller.

- [ ] **Step 5: Commit**

```bash
git add build.py pyproject.toml requirements.txt requirements-winrt.txt requirements-variants.txt tests/unit/packaging/test_build_config.py
git commit -m "refactor: share PyInstaller application payload"
```

### Task 3: Package AppImage, Flatpak, and Debian Artifacts

**Files:**
- Create: `packaging/linux/build_appimage.sh`
- Create: `packaging/linux/io.github.karaoke_studio.StrangeUtaGame.yml`
- Create: `packaging/linux/debian/control`
- Create: `packaging/linux/debian/postinst`
- Create: `packaging/linux/strangeutagame.desktop`
- Create: `packaging/linux/io.github.karaoke_studio.StrangeUtaGame.metainfo.xml`
- Create: `packaging/linux/build_deb.sh`
- Test: `tests/unit/packaging/test_linux_metadata.py`

- [ ] **Step 1: Write metadata validation tests**

```python
def test_desktop_entry_executes_packaged_binary(repo_root):
    desktop = DesktopEntry.parse(
        repo_root / "packaging/linux/strangeutagame.desktop"
    )
    assert desktop.exec == "StrangeUtaGame %F"
    assert "application/x-strangeutagame" in desktop.mime_types


def test_flatpak_uses_fixed_app_id(flatpak_manifest):
    assert flatpak_manifest["app-id"] == "io.github.karaoke_studio.StrangeUtaGame"
    assert "--socket=pulseaudio" in flatpak_manifest["finish-args"]


def test_deb_declares_native_audio_and_qt_dependencies(deb_control):
    assert deb_control["Architecture"] == "amd64"
    assert "libportaudio2" in deb_control["Depends"]
    assert "libgl1" in deb_control["Depends"]
```

- [ ] **Step 2: Run tests and verify missing metadata**

Run: `pytest tests/unit/packaging/test_linux_metadata.py -v`

Expected: FAIL because Linux packaging files do not exist.

- [ ] **Step 3: Add deterministic Linux package definitions**

The Flatpak manifest uses `org.freedesktop.Platform` and SDK `24.08`, the fixed
application ID, Wayland/X11 fallback, PulseAudio socket access, and only
home-directory file access needed for media/project selection. The Debian
control file depends on `libportaudio2, libgl1, libegl1,
libxkbcommon-x11-0`. The AppImage script assembles an AppDir from the PyInstaller
payload and runs the CI-provided, checksum-pinned `linuxdeploy` binary.

Every script starts with:

```bash
#!/usr/bin/env bash
set -euo pipefail
```

`build_deb.sh` installs payload under `/opt/strangeutagame`, the desktop entry
under `/usr/share/applications`, icons under `/usr/share/icons/hicolor`, and a
launcher symlink under `/usr/bin/strangeutagame`, then runs
`dpkg-deb --root-owner-group --build`.

- [ ] **Step 4: Validate and build Linux packages**

Run:

```bash
desktop-file-validate packaging/linux/strangeutagame.desktop
appstreamcli validate packaging/linux/io.github.karaoke_studio.StrangeUtaGame.metainfo.xml
flatpak-builder --force-clean build-flatpak packaging/linux/io.github.karaoke_studio.StrangeUtaGame.yml
bash packaging/linux/build_appimage.sh dist/StrangeUtaGame dist/release
bash packaging/linux/build_deb.sh dist/StrangeUtaGame 2.0.0 dist/release
```

Expected: validators exit 0 and all three Linux artifacts exist.

- [ ] **Step 5: Commit**

```bash
git add packaging/linux tests/unit/packaging/test_linux_metadata.py
git commit -m "feat: package Linux release formats"
```

### Task 4: Package, Sign, and Notarize macOS Universal

**Files:**
- Create: `packaging/macos/entitlements.plist`
- Create: `packaging/macos/sign_and_package.sh`
- Create: `packaging/macos/verify_artifact.sh`
- Test: `tests/unit/packaging/test_macos_metadata.py`

- [ ] **Step 1: Write entitlement and script-contract tests**

```python
def test_entitlements_keep_hardened_runtime_restrictions(entitlements):
    assert "com.apple.security.cs.allow-jit" not in entitlements
    assert "com.apple.security.cs.disable-library-validation" not in entitlements


def test_packager_requires_identity_and_notary_credentials(script_text):
    for name in (
        "APPLE_SIGNING_IDENTITY",
        "APPLE_ID",
        "APPLE_TEAM_ID",
        "APPLE_APP_PASSWORD",
    ):
        assert f"${{{name}:?" in script_text
```

- [ ] **Step 2: Run tests and verify missing package scripts**

Run: `pytest tests/unit/packaging/test_macos_metadata.py -v`

Expected: FAIL because macOS packaging files do not exist.

- [ ] **Step 3: Implement strict Universal signing flow**

`sign_and_package.sh` verifies every Mach-O file contains both `x86_64` and
`arm64` with `lipo -archs`, signs nested libraries from inside out, signs the
application with hardened runtime and timestamp, verifies with
`codesign --verify --deep --strict --verbose=2`, creates a compressed DMG,
submits it using `xcrun notarytool submit --wait`, staples the ticket, and runs
`spctl --assess --type open`.

Required environment variables are the four names in the test. The script
prints no credential values.

- [ ] **Step 4: Run metadata tests and signed build on macOS CI**

Run: `pytest tests/unit/packaging/test_macos_metadata.py -v`

Expected: tests pass.

Run on the signing runner:
`bash packaging/macos/sign_and_package.sh dist/StrangeUtaGame.app dist/release/StrangeUtaGame-2.0.0-macos-universal2.dmg`.

Expected: notarization succeeds, stapling succeeds, and verification exits 0.

- [ ] **Step 5: Commit**

```bash
git add packaging/macos tests/unit/packaging/test_macos_metadata.py
git commit -m "feat: sign and notarize macOS Universal builds"
```

### Task 5: Build and Sign the Windows Installer

**Files:**
- Create: `packaging/windows/StrangeUtaGame.iss`
- Create: `packaging/windows/sign.ps1`
- Create: `packaging/windows/verify.ps1`
- Test: `tests/unit/packaging/test_windows_installer.py`

- [ ] **Step 1: Write installer-contract tests**

```python
def test_installer_uses_per_user_location(iss_text):
    assert "PrivilegesRequired=lowest" in iss_text
    assert "DefaultDirName={localappdata}\\Programs\\StrangeUtaGame" in iss_text


def test_installer_registers_project_extension(iss_text):
    assert ".sug" in iss_text
    assert "StrangeUtaGame.Project" in iss_text


def test_sign_script_uses_rfc3161_timestamp(sign_script):
    assert "/tr https://timestamp.digicert.com" in sign_script
    assert "/td SHA256" in sign_script
```

- [ ] **Step 2: Run tests and verify missing installer**

Run: `pytest tests/unit/packaging/test_windows_installer.py -v`

Expected: FAIL because the Inno Setup files do not exist.

- [ ] **Step 3: Add installer and Authenticode flow**

The Inno definition installs the shared payload per-user, registers `.sug`,
creates uninstall metadata, preserves user data outside the installation
directory, and receives the version through `/DAppVersion=2.0.0`.

`sign.ps1` requires `WINDOWS_CERTIFICATE_PFX` and
`WINDOWS_CERTIFICATE_PASSWORD`, signs the main executable and installer with
SHA-256 plus RFC3161 timestamp, and fails on any non-zero `signtool` result.
`verify.ps1` runs `Get-AuthenticodeSignature` and requires
`$signature.Status -eq 'Valid'` for both files.

- [ ] **Step 4: Build and verify on Windows CI**

Run:

```powershell
iscc /DAppVersion=2.0.0 packaging/windows/StrangeUtaGame.iss
pwsh packaging/windows/sign.ps1
pwsh packaging/windows/verify.ps1
```

Expected: installer exists and both signatures report `Valid`.

- [ ] **Step 5: Commit**

```bash
git add packaging/windows tests/unit/packaging/test_windows_installer.py
git commit -m "feat: build signed Windows installer"
```

### Task 6: Generate Signed Release Manifests

**Files:**
- Create: `scripts/generate_release_manifest.py`
- Modify: `scripts/release.py`
- Test: `tests/unit/packaging/test_release_manifest_generation.py`

- [ ] **Step 1: Write deterministic generation tests**

```python
def test_manifest_contains_every_stable_target(
    tmp_path, release_artifacts, fake_gpg_signer
):
    manifest = generate_manifest(
        "2.0.0", "stable", release_artifacts, gpg_signer=fake_gpg_signer
    )
    assert set(manifest["channels"]["stable"]["targets"]) == {
        "windows-x86_64-windows-installer",
        "macos-universal2-macos-dmg",
        "linux-x86_64-appimage",
        "linux-x86_64-flatpak",
        "linux-x86_64-deb",
    }
    linux_paths = [item.path for item in release_artifacts if item.target.os == "linux"]
    assert fake_gpg_signer.signed == linux_paths


def test_manifest_json_is_canonical(release_artifacts):
    first = serialize_manifest(generate_manifest("2.0.0", "preview", release_artifacts))
    second = serialize_manifest(generate_manifest("2.0.0", "preview", reversed(release_artifacts)))
    assert first == second
```

- [ ] **Step 2: Run tests and verify missing generator**

Run: `pytest tests/unit/packaging/test_release_manifest_generation.py -v`

Expected: FAIL because the generator is missing.

- [ ] **Step 3: Generate, sign, and verify schema 2**

Hash each final artifact, map its target to the action defined in Plan 03,
serialize with sorted keys and compact separators, and sign the exact bytes
using an Ed25519 private key read from `UPDATE_ED25519_PRIVATE_KEY_B64`.
Immediately verify the signature using the embedded public key before writing
`manifest-v2.json` and `manifest-v2.json.sig`.

For every direct Linux download, import `LINUX_GPG_PRIVATE_KEY_B64` into an
ephemeral `GNUPGHOME`, run `gpg --batch --armor --detach-sign <artifact>`, and
verify the resulting `.asc` file before collection. Delete the ephemeral
keyring at the end of the CI job.

- [ ] **Step 4: Run generation and updater compatibility tests**

Run: `pytest tests/unit/packaging/test_release_manifest_generation.py tests/unit/updater/test_signed_manifest.py tests/unit/updater/test_update_signatures.py -v`

Expected: all tests pass and the updater parses the generated fixture.

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_release_manifest.py scripts/release.py tests/unit/packaging/test_release_manifest_generation.py
git commit -m "feat: generate signed cross-platform manifests"
```

### Task 7: Add Preview and Stable CI Gates

**Files:**
- Create: `.github/workflows/test.yml`
- Create: `.github/workflows/preview.yml`
- Modify: `.github/workflows/release.yml`
- Create: `scripts/verify_release_gate.py`
- Create: `tests/unit/packaging/test_release_gate.py`

- [ ] **Step 1: Write stable-gate tests**

```python
def test_stable_gate_requires_all_artifacts_signatures_and_audio_reports(gate_fixture):
    gate_fixture.remove("audio-linux-x86_64.json")
    result = verify_release_gate(gate_fixture.root)
    assert not result.passed
    assert "audio-linux-x86_64.json" in result.missing


def test_preview_gate_does_not_accept_stable_channel(gate_fixture):
    result = verify_release_gate(gate_fixture.root, channel="preview")
    assert result.manifest_channel == "preview"
```

- [ ] **Step 2: Run tests and verify missing gate**

Run: `pytest tests/unit/packaging/test_release_gate.py -v`

Expected: FAIL because `verify_release_gate` is missing.

- [ ] **Step 3: Implement workflows and explicit stable gate**

`test.yml` runs the unit suite and platform-boundary checker on
`windows-latest`, `macos-latest`, `ubuntu-22.04`, and `ubuntu-24.04`.
`preview.yml` builds and signs every available target from the default branch,
publishes a GitHub prerelease, and never updates the stable manifest.

`release.yml` requires all five artifacts, their verification outputs, package
smoke reports, legacy-data golden tests, and three schema-1 audio reports with
`passed: true` and `max_error_ms <= 10.0`. Its release job depends on every
matrix build and runs `verify_release_gate.py` before uploading or changing a
GitHub release.

Use protected secrets named:

```text
WINDOWS_CERTIFICATE_PFX_BASE64
WINDOWS_CERTIFICATE_PASSWORD
APPLE_CERTIFICATE_P12_BASE64
APPLE_CERTIFICATE_PASSWORD
APPLE_SIGNING_IDENTITY
APPLE_ID
APPLE_TEAM_ID
APPLE_APP_PASSWORD
UPDATE_ED25519_PRIVATE_KEY_B64
LINUX_GPG_PRIVATE_KEY_B64
```

- [ ] **Step 4: Run gate tests and validate workflow syntax**

Run: `pytest tests/unit/packaging/test_release_gate.py -v`

Expected: tests pass.

Run: `actionlint .github/workflows/test.yml .github/workflows/preview.yml .github/workflows/release.yml`

Expected: no workflow errors.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows scripts/verify_release_gate.py tests/unit/packaging/test_release_gate.py
git commit -m "ci: gate preview and stable cross-platform releases"
```

### Task 8: Add Installed-Package Smoke Tests and Release Documentation

**Files:**
- Create: `scripts/smoke_test_installed_app.py`
- Create: `tests/integration/test_packaged_app.py`
- Modify: `RELEASING.md`
- Modify: `README.md`
- Modify: `README_DEV.md`

- [ ] **Step 1: Write the smoke-report contract test**

```python
def test_smoke_report_requires_start_open_export_and_clean_exit(tmp_path):
    report = run_smoke(FakePackagedApp(tmp_path))
    assert report == {
        "schema": 1,
        "started": True,
        "opened_legacy_project": True,
        "exported_srt": True,
        "clean_exit": True,
    }
```

- [ ] **Step 2: Run test and verify missing smoke runner**

Run: `pytest tests/integration/test_packaged_app.py -v`

Expected: FAIL because the smoke runner is missing.

- [ ] **Step 3: Implement headless smoke commands and document releases**

Add a packaged-only CLI flag `--smoke-test REPORT_PATH` that creates a Qt
application, opens a committed legacy `.sug` fixture, exports SRT to a temporary
directory, closes services, and writes the schema-1 JSON report. It must not
play audio or modify the fixture.

Update release docs with target names, credential setup, preview/stable channel
behavior, GPG verification commands, macOS notarization verification, Windows
signature verification, Linux support scope, and rollback procedure. Update
README platform badges only after stable gates pass.

- [ ] **Step 4: Run source and packaged smoke tests**

Run: `pytest tests/integration/test_packaged_app.py -v`

Expected: test passes.

Run each installed artifact with `--smoke-test smoke-<target>.json`.

Expected: every report has schema 1 and all four boolean fields are true.

- [ ] **Step 5: Commit**

```bash
git add scripts/smoke_test_installed_app.py tests/integration/test_packaged_app.py RELEASING.md README.md README_DEV.md main.py
git commit -m "docs: finalize cross-platform release workflow"
```

## Completion Gate

Run:

```bash
pytest tests/unit tests/integration -v
python scripts/check_platform_boundaries.py
actionlint .github/workflows/test.yml .github/workflows/preview.yml .github/workflows/release.yml
python scripts/verify_release_gate.py release-gate-input
```

Expected: tests, boundary checks, workflow validation, signature verification,
package smoke reports, legacy compatibility checks, and all three audio reports
pass. Only then may the coordinated stable GitHub release and stable update
manifest be published.
