# StrangeUtaGame Cross-Platform Migration Design

Date: 2026-06-20

## 1. Summary

StrangeUtaGame will migrate from a Windows-first desktop application to an
officially supported Windows, macOS, and Linux application while retaining its
Python and PyQt6 architecture. The migration follows a shared-first rule: a
feature has one cross-platform implementation unless an operating system makes
that impossible.

The first stable cross-platform release must provide the same user-visible core
features on all three systems. It must preserve existing `.sug` projects,
settings, shortcuts, and dictionaries. Preview builds may expose incomplete
work, but the stable release is gated on all three platforms passing the same
functional and audio-quality requirements.

## 2. Current State

The project already has useful cross-platform boundaries:

- Domain and application services are separated from most infrastructure.
- `IAudioEngine` defines the playback contract.
- `SoundDeviceEngine` implements an offline TSM cache, a producer/consumer ring
  buffer, a minimal audio callback, hardware-latency compensation, a monotonic
  playback clock, and device recovery.
- Sudachi and pykakasi provide non-Windows Japanese reading analysis.
- PyQt6 supplies a cross-platform UI and standard desktop APIs.

The remaining Windows-first behavior is concentrated in a smaller set of
areas:

- `MainWindow` constructs BASS-based engines directly.
- Only Windows BASS DLLs and plugins are bundled.
- WinRT Japanese analysis and its installation UI are Windows-specific.
- The updater assumes `Updater.exe`, PE files, Windows process locking, and a
  Windows installation layout.
- Theme, proxy, taskbar, path, build, and release code contains direct platform
  checks.
- Release CI currently produces only Windows variants.

## 3. Goals

1. Officially support Windows x64, macOS Universal (Apple Silicon and Intel),
   and Linux x64.
2. Provide the same core editing, timing, playback, speed-change, reading
   analysis, import, export, and update experience on every platform.
3. Keep existing `.sug` files and user data fully compatible without requiring
   manual conversion.
4. Achieve no more than 10 ms timing error after device calibration.
5. Support pitch-preserving playback from 0.2x through 2.0x.
6. Maximize shared implementation and keep operating-system code outside UI,
   domain, and application services.
7. Publish cryptographically verifiable artifacts for all platforms and
   notarize macOS releases.
8. Publish Linux AppImage, Flatpak, and `.deb` artifacts, with Ubuntu 22.04 and
   24.04 LTS as baseline test environments.
9. Provide public preview builds throughout the migration and release the first
   stable version on all three platforms together.

## 4. Non-Goals

- Rewriting the application in C++, Rust, Electron, Tauri, or another UI stack.
- Supporting Windows ARM64 or Linux ARM64 in the first release.
- Providing a browser version.
- Making every operating system use the same low-level audio API or installer.
- Retaining the current Windows updater's internal implementation.
- Maintaining BASS and sounddevice as permanent equal-status audio backends.

Rust remains a future option for an isolated performance-critical module only
if measured results show that the shared Python audio implementation cannot
meet the acceptance criteria.

## 5. Architectural Principles

### 5.1 Shared First

UI, application services, domain logic, audio algorithms, reading fallback,
data migration, update discovery, download verification, and error presentation
use one implementation on all platforms.

New direct `sys.platform` checks are prohibited in UI, domain, and application
modules. Platform checks are allowed only during bootstrap, capability
discovery, packaging, or within a narrowly scoped optional capability plugin.

### 5.2 Capabilities Instead of Platform Branches

Bootstrap creates a `CapabilityRegistry` and a service container. Consumers ask
whether a capability such as `ruby_winrt`, `installer_handoff`,
`system_proxy`, or `thread_priority` is available. They do not branch on an OS
name.

An unavailable optional capability returns a structured unavailable result and
falls back to a shared implementation. It must not cause imports or application
startup to fail.

### 5.3 Dependency Direction

Dependencies flow in this order:

1. PyQt6 presentation layer
2. Application services
3. Domain and format core
4. Stable capability ports
5. Shared infrastructure and optional capability plugins

Infrastructure may depend on platform APIs. Higher layers may depend only on
ports and structured results.

## 6. Components

### 6.1 Bootstrap and Service Container

Bootstrap detects the OS, CPU architecture, frozen/development mode, package
channel, and optional capabilities once. It then constructs the application
services and injects their ports.

The container owns the active audio engine, reading providers, platform
services, update service, and installer handoff. `MainWindow` receives these
services instead of importing concrete infrastructure classes.

### 6.2 Audio Port

`IAudioEngine` remains the public boundary and is refined where necessary to
make capabilities and errors explicit. The shared `SoundDeviceEngine` becomes
the default implementation on all platforms.

The shared pipeline is:

1. Decode supported audio to contiguous PCM. Video input continues through the
   shared FFmpeg extraction path before audio loading.
2. Keep the original PCM as the waveform and original-timeline source.
3. Render pitch-preserving speed variants outside the real-time callback and
   cache them with bounded memory and disk policies.
4. Feed rendered PCM through the single-producer/single-consumer ring buffer.
5. Keep the PortAudio callback allocation-free, lock-free, and free of Python
   DSP work.
6. Derive the authoritative playback position from consumed device frames and
   a monotonic clock, including measured output-latency compensation.

Timing input reads this authoritative audio position, then applies device
calibration and the existing song/global offsets before issuing a domain
command. UI display smoothing must never be used as the timing source.

The implementation is shared. A small audio profile may supply tested device
defaults, diagnostic labels, and optional thread-priority support for WASAPI,
CoreAudio, or PipeWire/PulseAudio. Profiles may not duplicate playback, timing,
seek, TSM, or recovery algorithms.

BASS remains available during preview releases for Windows comparison and
emergency fallback. It is removed from default release artifacts after the
shared path meets the stable audio gate. This prevents a permanent dual-backend
maintenance burden.

### 6.3 Japanese Reading Port

Sudachi followed by pykakasi is the shared fallback chain and is packaged on
all platforms. Existing Windows users retain WinRT-first behavior when the
Windows Japanese Basic/IME capability and WinRT package are available.

WinRT is an optional `RubyPort` provider. Its absence or failure silently moves
to the shared chain and never prevents startup. It does not require a separate
Windows product variant. Existing LLM reading analysis remains a separate
user-selected provider and retains its local fallback behavior.

### 6.4 Shared Platform Services

Qt or standard-library APIs are used before custom platform code:

- `QStandardPaths` for canonical configuration, data, and cache locations
- Qt desktop services for opening files and URLs
- Qt font, appearance, and screen APIs where sufficient
- environment and library-supported proxy discovery before OS-specific reads
- shared file dialogs and local file access

Any unavoidable system integration is exposed as a small capability plugin in
one platform directory and covered by the same contract tests as its peers.

### 6.5 User Data and Compatibility

The application keeps the `.sug` schema compatible. Existing project files are
opened and saved without lossy conversion.

Canonical user data moves to Qt standard locations, but startup also searches
all legacy locations. When legacy settings, shortcuts, dictionaries, singer
presets, or other persistent data are found, migration:

1. creates a backup,
2. copies or converts data atomically,
3. records a migration version,
4. is safe to repeat after interruption, and
5. leaves the source data intact.

Golden fixtures verify that legacy and migrated data produce the same domain
state and user-visible settings.

### 6.6 Update Service

One `UpdateService` implements channel selection, version comparison, manifest
retrieval, artifact selection, download, signature/hash validation, progress,
and errors.

A signed manifest identifies each artifact by release channel, version, OS,
architecture, and package channel. It contains SHA-256 hashes, minimum
compatible versions, and the required installer action.

Only final installation handoff differs:

- Windows launches the signed installer or approved replacement helper.
- macOS hands off to the signed and notarized application/DMG update flow.
- Linux uses the action appropriate to Flatpak, `.deb`, or AppImage.

An update failure must leave the current application runnable. The UI always
offers a manual-download fallback. Stable and preview channels are isolated so
preview users do not accidentally update stable installations.

## 7. Error Handling and Diagnostics

Infrastructure returns structured errors containing a stable code, recovery
classification, safe user message, and diagnostic detail. Infrastructure does
not create dialogs. Application services decide whether to retry, fall back,
pause, or present a localized message.

Required audio recovery behavior includes:

- Unsupported input reports the failing format and available conversion path.
- Device removal pauses playback and preserves the original-timeline position.
- Device restoration rebuilds the stream without changing project state.
- Speed-render failure permits original-speed playback and reports the failed
  cache entry.
- Repeated underruns create diagnostics with backend, device, sample rate,
  block size, requested/actual latency, and recovery attempts.

Logs must avoid user lyric content, credentials, proxy secrets, and LLM keys.
Preview builds may expose an explicit diagnostic export for issue reports.

## 8. Packaging, Signing, and Distribution

Official artifacts are:

- Windows x64: signed installer and optional portable archive, using
  Authenticode signing.
- macOS Universal: signed application and DMG, using Developer ID signing and
  Apple notarization.
- Linux x64: AppImage, Flatpak, and `.deb`, with detached GPG signatures for
  direct downloads, a signed release manifest, GPG-signed repository metadata
  where applicable, and verifiable Flatpak provenance.

Linux has no single code-signing and trust mechanism equivalent to Windows
Authenticode or Apple Developer ID. For this design, "signed Linux artifacts"
means that every direct download is covered by a detached GPG signature and the
signed manifest, while repository and Flatpak installations use their native
signed metadata and provenance mechanisms.

Build definitions share dependency and application-data declarations. Small
platform sections add only native libraries, icons/metadata, signing, and
package assembly. Release CI runs on native Windows, macOS, and Linux runners;
cross-compilation is not used for final artifacts.

## 9. Delivery Stages

### Stage 1: Characterization

- Add golden legacy projects and configuration fixtures.
- Record current Windows functional behavior.
- Build the repeatable audio loopback and timing measurement harness.
- Establish package-size, startup-time, and long-playback baselines.

### Stage 2: Shared Runtime

- Introduce bootstrap, dependency injection, capability registry, and
  structured infrastructure errors.
- Make `SoundDeviceEngine` the development default and complete missing
  keysound, format, calibration, and recovery behavior.
- Move platform-neutral integrations to Qt APIs.
- Implement idempotent user-data discovery and migration.

### Stage 3: Public Preview

- Produce installable artifacts on all target platforms.
- Publish a separate preview channel with explicit known issues.
- Collect opt-in diagnostics and test on a broader device/distro matrix.
- Retain BASS only as a Windows comparison/fallback during this stage.

### Stage 4: Stable Release

- Complete signing and macOS notarization.
- Pass package installation, upgrade, rollback, and removal tests.
- Pass real-device audio gates on all reference environments.
- Remove BASS from default artifacts.
- Publish the same stable application version on all platforms together.

## 10. Testing Strategy

### 10.1 Automated Tests

- Run domain, application, parser, exporter, and persistence tests on all three
  CI operating systems.
- Run each optional platform plugin against a shared port contract suite.
- Add audio clock, seek, pause/resume, speed mapping, cache, underrun, and
  recovery tests using deterministic fake devices.
- Add golden compatibility tests for `.sug`, settings, shortcuts, dictionaries,
  and singer presets.
- Add Qt UI smoke tests for application startup, project opening, playback
  control, editing, export, settings, and update prompts.
- Install and launch every packaged artifact in a clean environment.
- Verify manifests, artifact hashes, signatures, channel isolation, failed
  downloads, and non-destructive update rollback.

### 10.2 Real-Device Tests

Before a stable release, run calibrated loopback tests on representative
WASAPI, CoreAudio, and PipeWire/PulseAudio systems. Tests cover:

- timing input error after calibration,
- original-speed and 0.2x through 2.0x playback,
- rapid seek/play/pause cycles,
- at least two hours of continuous playback,
- device unplug/replug and sleep/wake recovery,
- common sample rates and mono/stereo sources, and
- package install, update, rollback, and uninstall behavior.

## 11. Stable Release Acceptance Criteria

The first stable cross-platform release is accepted only when:

1. Core features are available on Windows x64, macOS Universal, and Linux x64.
2. Calibrated timing error is no more than 10 ms on every reference system.
3. Pitch-preserving 0.2x through 2.0x playback passes functional and endurance
   tests.
4. Existing `.sug` projects and persistent user data migrate without loss.
5. All official artifacts install, launch, update, and recover from failed
   updates.
6. Windows and macOS artifacts pass signature validation; macOS artifacts pass
   notarization; Linux downloads and repository metadata are verifiable.
7. AppImage, Flatpak, and `.deb` pass the defined Linux smoke suite, including
   Ubuntu 22.04 and 24.04 LTS baselines.
8. No UI, domain, or application-service code contains new direct platform
   branches.
9. Known platform differences are limited to documented optional capabilities
   or package installation behavior, not missing core features.

If any platform misses a stable gate, development continues through preview
builds. Other platforms do not publish the coordinated stable release early.

## 12. Risks and Mitigations

### Audio timing varies by device

Mitigation: retain per-device calibration, measure actual stream latency, use a
shared authoritative clock, maintain real-device reference coverage, and tune
only thin audio profiles when measurements require it.

### Python packaging expands the build matrix

Mitigation: use native CI runners, share package-data declarations, pin native
dependencies, cache immutable runtime inputs, and test installed artifacts
rather than only build directories.

### Linux package channels behave differently

Mitigation: keep application behavior shared and isolate only the installation
handoff. Test each channel independently and encode channel identity in the
manifest and installed metadata.

### Optional WinRT behavior diverges from shared reading analysis

Mitigation: keep it behind the same port, retain the shared fallback chain, add
provider contract tests, and avoid a separate Windows application variant.

### A future performance limit requires native code

Mitigation: preserve a stable audio port and collect profiling evidence. Move
only the proven bottleneck to Rust or C++ rather than changing the UI or domain
architecture.
