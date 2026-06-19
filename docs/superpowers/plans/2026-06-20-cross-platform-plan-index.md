# Cross-Platform Migration Plan Index

The design is implemented as four sequential plans. Each plan produces a
working, testable increment and must pass its completion gate before the next
plan starts.

1. [Shared Runtime and Data Compatibility](2026-06-20-cross-platform-01-shared-runtime.md)
2. [Shared Audio and Reading Providers](2026-06-20-cross-platform-02-audio-reading.md)
3. [Update Protocol and Installer Handoffs](2026-06-20-cross-platform-03-updates.md)
4. [Packaging, Signing, and Release Gates](2026-06-20-cross-platform-04-release.md)

## Spec Coverage

| Design requirement | Implementation plan |
| --- | --- |
| Shared-first boundaries, bootstrap, capabilities | Plan 01, Tasks 1, 4, and 6 |
| Standard paths and lossless legacy migration | Plan 01, Tasks 2, 3, and 5 |
| Shared audio engine, timing, keysounds, diagnostics | Plan 02, Tasks 1 through 4 |
| WinRT optional provider and shared reading fallback | Plan 02, Task 5 |
| Calibrated 10 ms audio acceptance gate | Plan 02, Task 6; Plan 04, Task 7 |
| Signed update manifest and exact target selection | Plan 03, Tasks 1 through 4 |
| Package-specific installation handoff and rollback | Plan 03, Tasks 5 through 7 |
| Windows, macOS, and Linux artifacts | Plan 04, Tasks 2 through 5 |
| Linux AppImage, Flatpak, and `.deb` | Plan 04, Task 3 |
| Signing, notarization, GPG provenance | Plan 04, Tasks 4 through 7 |
| Public preview and coordinated stable release | Plan 04, Tasks 7 and 8 |
| Installed-package, compatibility, and failure tests | Completion gates in all plans |

Execute the plans in numeric order. A plan's completion gate is the entry gate
for the next plan; do not combine their commits or skip a gate.

The source design is
[2026-06-20-cross-platform-migration-design.md](../specs/2026-06-20-cross-platform-migration-design.md).
