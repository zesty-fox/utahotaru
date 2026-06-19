# Shared Runtime and Data Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce shared runtime capabilities, standard application paths, and lossless legacy-data migration without changing existing project behavior.

**Architecture:** Bootstrap creates an immutable runtime context after `QApplication` exists. UI and application code receive that context and use capability names and shared paths instead of checking an operating-system name. Standalone data moves to Qt standard directories through an atomic, idempotent migration; embedded settings providers remain untouched.

**Tech Stack:** Python 3.13, PyQt6, pathlib, dataclasses, pytest, pytest-qt

---

## File Map

- Create `src/strange_uta_game/runtime/capabilities.py`: capability identifiers and registry.
- Create `src/strange_uta_game/runtime/paths.py`: canonical Qt paths and legacy path discovery.
- Create `src/strange_uta_game/runtime/migration.py`: idempotent migration with backup and marker.
- Create `src/strange_uta_game/runtime/context.py`: immutable runtime context constructor.
- Create `src/strange_uta_game/runtime/__init__.py`: public runtime API.
- Modify `main.py`: build and pass the runtime context after creating `QApplication`.
- Modify `src/strange_uta_game/frontend/main_window.py`: accept injected runtime context.
- Modify `src/strange_uta_game/frontend/settings/app_settings.py`: use injected canonical config directory.
- Modify `src/strange_uta_game/frontend/project_store.py`: use shared cache/config paths.
- Test in `tests/unit/runtime/` and existing frontend settings/store suites.

### Task 1: Add the Capability Registry

**Files:**
- Create: `src/strange_uta_game/runtime/capabilities.py`
- Create: `src/strange_uta_game/runtime/__init__.py`
- Test: `tests/unit/runtime/test_capabilities.py`

- [ ] **Step 1: Write the failing registry tests**

```python
from strange_uta_game.runtime.capabilities import (
    Capability,
    CapabilityRegistry,
    CapabilityStatus,
)


def test_registry_reports_registered_capability():
    registry = CapabilityRegistry(
        {Capability.SYSTEM_PROXY: CapabilityStatus(True, "qt")}
    )
    assert registry.available(Capability.SYSTEM_PROXY)
    assert registry.status(Capability.SYSTEM_PROXY).provider == "qt"


def test_registry_returns_unavailable_for_missing_capability():
    registry = CapabilityRegistry()
    status = registry.status(Capability.RUBY_WINRT)
    assert not status.available
    assert status.provider == ""
```

- [ ] **Step 2: Run the tests and verify the import failure**

Run: `pytest tests/unit/runtime/test_capabilities.py -v`

Expected: FAIL with `ModuleNotFoundError: strange_uta_game.runtime`.

- [ ] **Step 3: Implement the immutable registry**

```python
# src/strange_uta_game/runtime/capabilities.py
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class Capability(StrEnum):
    RUBY_WINRT = "ruby_winrt"
    SYSTEM_PROXY = "system_proxy"
    INSTALLER_HANDOFF = "installer_handoff"
    THREAD_PRIORITY = "thread_priority"


@dataclass(frozen=True)
class CapabilityStatus:
    available: bool
    provider: str = ""
    reason: str = ""


class CapabilityRegistry:
    def __init__(
        self,
        statuses: Mapping[Capability, CapabilityStatus] | None = None,
    ) -> None:
        self._statuses = MappingProxyType(dict(statuses or {}))

    def status(self, capability: Capability) -> CapabilityStatus:
        return self._statuses.get(capability, CapabilityStatus(False))

    def available(self, capability: Capability) -> bool:
        return self.status(capability).available
```

Export these names from `runtime/__init__.py`.

- [ ] **Step 4: Run the registry tests**

Run: `pytest tests/unit/runtime/test_capabilities.py -v`

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/strange_uta_game/runtime tests/unit/runtime
git commit -m "feat: add runtime capability registry"
```

### Task 2: Centralize Canonical and Legacy Paths

**Files:**
- Create: `src/strange_uta_game/runtime/paths.py`
- Test: `tests/unit/runtime/test_paths.py`

- [ ] **Step 1: Write tests using a fake Qt path resolver**

```python
from pathlib import Path

from strange_uta_game.runtime.paths import AppPaths, build_app_paths, legacy_roots


def test_build_app_paths_keeps_data_config_and_cache_separate(tmp_path):
    values = {
        "config": tmp_path / "config",
        "data": tmp_path / "data",
        "cache": tmp_path / "cache",
    }
    paths = build_app_paths(lambda key: values[key])
    assert paths == AppPaths(**values)


def test_legacy_roots_preserves_redirect_precedence(tmp_path):
    program = tmp_path / "program"
    redirected = tmp_path / "redirected"
    program.mkdir()
    redirected.mkdir()
    (program / ".config_redirect").write_text(str(redirected), encoding="utf-8")
    assert legacy_roots(program, tmp_path / "cwd")[0] == redirected
```

- [ ] **Step 2: Verify the tests fail**

Run: `pytest tests/unit/runtime/test_paths.py -v`

Expected: FAIL because `runtime.paths` does not exist.

- [ ] **Step 3: Implement shared path resolution**

```python
# src/strange_uta_game/runtime/paths.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QStandardPaths


@dataclass(frozen=True)
class AppPaths:
    config: Path
    data: Path
    cache: Path

    def ensure(self) -> "AppPaths":
        for path in (self.config, self.data, self.cache):
            path.mkdir(parents=True, exist_ok=True)
        return self


def _qt_resolver(key: str) -> Path:
    locations = {
        "config": QStandardPaths.StandardLocation.AppConfigLocation,
        "data": QStandardPaths.StandardLocation.AppDataLocation,
        "cache": QStandardPaths.StandardLocation.CacheLocation,
    }
    return Path(QStandardPaths.writableLocation(locations[key]))


def build_app_paths(
    resolver: Callable[[str], Path] = _qt_resolver,
) -> AppPaths:
    return AppPaths(
        config=resolver("config"),
        data=resolver("data"),
        cache=resolver("cache"),
    )


def legacy_roots(program_dir: Path, cwd: Path) -> tuple[Path, ...]:
    roots: list[Path] = []
    redirect = program_dir / ".config_redirect"
    if redirect.is_file():
        candidate = Path(redirect.read_text(encoding="utf-8").strip())
        if candidate.is_dir():
            roots.append(candidate)
    for candidate in (program_dir, cwd, Path.home() / ".strange_uta_game"):
        if candidate not in roots:
            roots.append(candidate)
    return tuple(roots)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/runtime/test_paths.py -v`

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/strange_uta_game/runtime/paths.py tests/unit/runtime/test_paths.py
git commit -m "feat: centralize cross-platform app paths"
```

### Task 3: Add Atomic Legacy-Data Migration

**Files:**
- Create: `src/strange_uta_game/runtime/migration.py`
- Test: `tests/unit/runtime/test_migration.py`

- [ ] **Step 1: Write migration behavior tests**

```python
import json

from strange_uta_game.runtime.migration import migrate_legacy_data
from strange_uta_game.runtime.paths import AppPaths


def test_migration_copies_known_files_and_keeps_source(tmp_path):
    source = tmp_path / "legacy"
    source.mkdir()
    (source / "config.json").write_text('{"ui": {"language": "ja_JP"}}')
    paths = AppPaths(tmp_path / "config", tmp_path / "data", tmp_path / "cache")
    result = migrate_legacy_data(paths, (source,))
    assert result.migrated == ("config.json",)
    assert (paths.config / "config.json").exists()
    assert (source / "config.json").exists()
    marker = json.loads((paths.data / "migration-v1.json").read_text())
    assert marker["version"] == 1


def test_migration_is_idempotent_and_never_overwrites_target(tmp_path):
    source = tmp_path / "legacy"
    source.mkdir()
    (source / "config.json").write_text('{"source": true}')
    paths = AppPaths(tmp_path / "config", tmp_path / "data", tmp_path / "cache")
    paths.ensure()
    (paths.config / "config.json").write_text('{"target": true}')
    first = migrate_legacy_data(paths, (source,))
    second = migrate_legacy_data(paths, (source,))
    assert not first.migrated
    assert second.already_complete
    assert '"target": true' in (paths.config / "config.json").read_text()
```

- [ ] **Step 2: Run tests and observe failure**

Run: `pytest tests/unit/runtime/test_migration.py -v`

Expected: FAIL because `migrate_legacy_data` is missing.

- [ ] **Step 3: Implement migration with atomic copies**

Implement `MigrationResult`, the fixed file map below, temporary-file writes,
backup creation, and an atomic marker replacement:

```python
CONFIG_FILES = ("config.json", "dictionary.json", "singers.json", "network_dictionary.json")


@dataclass(frozen=True)
class MigrationResult:
    migrated: tuple[str, ...]
    source: str = ""
    already_complete: bool = False


def _atomic_copy(source: Path, target: Path) -> None:
    temporary = target.with_suffix(target.suffix + ".migrating")
    shutil.copy2(source, temporary)
    os.replace(temporary, target)
```

`migrate_legacy_data()` must call `paths.ensure()`, choose the first legacy root
containing a known file, copy only missing targets, preserve source files, write
backups under `paths.data / "migration-backup-v1"`, and atomically create
`migration-v1.json` only after all copies succeed.

- [ ] **Step 4: Run migration tests**

Run: `pytest tests/unit/runtime/test_migration.py -v`

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/strange_uta_game/runtime/migration.py tests/unit/runtime/test_migration.py
git commit -m "feat: migrate legacy user data atomically"
```

### Task 4: Build and Inject Runtime Context

**Files:**
- Create: `src/strange_uta_game/runtime/context.py`
- Modify: `main.py:24-150`
- Modify: `src/strange_uta_game/frontend/main_window.py:50-93`
- Test: `tests/unit/runtime/test_context.py`
- Test: `tests/unit/frontend/test_main_window_runtime.py`

- [ ] **Step 1: Write context-construction tests**

```python
from strange_uta_game.runtime.context import RuntimeContext, build_runtime_context


def test_build_runtime_context_runs_migration_once(qapp, tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(
        "strange_uta_game.runtime.context.migrate_legacy_data",
        lambda paths, roots: called.append((paths, roots)),
    )
    context = build_runtime_context(program_dir=tmp_path, cwd=tmp_path)
    assert isinstance(context, RuntimeContext)
    assert len(called) == 1
```

Add a frontend test that constructs `MainWindow.__new__(MainWindow)`, calls a
small `_set_runtime_context(context)` helper, and asserts object identity. This
avoids constructing the full Fluent window in a unit test.

- [ ] **Step 2: Verify tests fail**

Run: `pytest tests/unit/runtime/test_context.py tests/unit/frontend/test_main_window_runtime.py -v`

Expected: FAIL because `RuntimeContext` and injection are not defined.

- [ ] **Step 3: Implement runtime context**

```python
# src/strange_uta_game/runtime/context.py
@dataclass(frozen=True)
class RuntimeContext:
    paths: AppPaths
    capabilities: CapabilityRegistry


def build_runtime_context(program_dir: Path, cwd: Path) -> RuntimeContext:
    paths = build_app_paths().ensure()
    roots = legacy_roots(program_dir, cwd)
    migrate_legacy_data(paths, roots)
    capabilities = CapabilityRegistry()
    return RuntimeContext(paths=paths, capabilities=capabilities)
```

Change `MainWindow.__init__` to accept `runtime_context: RuntimeContext | None =
None`, store it before `super().__init__()`, and retain a default construction
path only for embedded/test callers. In `main.py`, call
`QCoreApplication.setOrganizationName("KaraokeStudio")` and
`setApplicationName("StrangeUtaGame")` before resolving paths, then pass the
constructed context into `MainWindow`.

- [ ] **Step 4: Run focused tests**

Run: `pytest tests/unit/runtime tests/unit/frontend/test_main_window_runtime.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add main.py src/strange_uta_game/runtime src/strange_uta_game/frontend/main_window.py tests/unit/runtime tests/unit/frontend/test_main_window_runtime.py
git commit -m "feat: inject shared runtime context"
```

### Task 5: Move Standalone Settings and Cache Consumers to AppPaths

**Files:**
- Modify: `src/strange_uta_game/frontend/settings/app_settings.py:352-410`
- Modify: `src/strange_uta_game/frontend/project_store.py:20-70`
- Modify: `src/strange_uta_game/backend/infrastructure/audio/tsm_cache.py:96-121`
- Modify: `src/strange_uta_game/backend/infrastructure/audio/video_converter.py`
- Test: `tests/unit/frontend/test_app_paths_integration.py`
- Test: existing settings, store, and TSM cache tests

- [ ] **Step 1: Write path-injection tests**

```python
from strange_uta_game.frontend.settings.app_settings import AppSettings
from strange_uta_game.runtime.paths import AppPaths


def test_app_settings_uses_injected_config_directory(tmp_path):
    paths = AppPaths(tmp_path / "config", tmp_path / "data", tmp_path / "cache").ensure()
    settings = AppSettings(app_paths=paths)
    settings.set("ui.language", "en_US")
    assert (paths.config / "config.json").exists()


def test_explicit_config_path_still_wins_for_tests(tmp_path):
    explicit = tmp_path / "explicit.json"
    settings = AppSettings(config_path=str(explicit))
    settings.set("ui.language", "en_US")
    assert explicit.exists()
```

- [ ] **Step 2: Verify the new argument fails**

Run: `pytest tests/unit/frontend/test_app_paths_integration.py -v`

Expected: FAIL with unexpected keyword argument `app_paths`.

- [ ] **Step 3: Thread AppPaths through standalone consumers**

Add `app_paths: AppPaths | None = None` as a keyword-only `AppSettings`
argument. Preserve the precedence `provider > explicit config_path >
app_paths.config`. Replace module-level `_CONFIG_DIR` and `_get_cache_dir()` in
`ProjectStore` with constructor-injected `AppPaths`. Add `set_cache_root(path)`
to `tsm_cache.py` and `video_converter.py`, called once by bootstrap before
audio or project services are created.

Use this exact precedence helper:

```python
def _standalone_config_path(
    config_path: str | None,
    app_paths: AppPaths | None,
) -> Path:
    if config_path is not None:
        return Path(config_path)
    if app_paths is not None:
        return app_paths.config / "config.json"
    return AppSettings.get_config_dir() / "config.json"
```

- [ ] **Step 4: Run all persistence-related tests**

Run: `pytest tests/unit/frontend tests/unit/infrastructure/test_tsm_cache.py tests/unit/infrastructure/test_sug_io.py -v`

Expected: all tests pass; embedded-provider tests perform no standalone file IO.

- [ ] **Step 5: Commit**

```bash
git add src/strange_uta_game/frontend/settings/app_settings.py src/strange_uta_game/frontend/project_store.py src/strange_uta_game/backend/infrastructure/audio/tsm_cache.py src/strange_uta_game/backend/infrastructure/audio/video_converter.py tests/unit/frontend
git commit -m "refactor: use shared application paths"
```

### Task 6: Enforce the Platform-Branch Boundary

**Files:**
- Create: `scripts/check_platform_boundaries.py`
- Create: `tests/unit/runtime/test_platform_boundaries.py`
- Modify: `.github/workflows/release.yml`
- Modify: `README_DEV.md`

- [ ] **Step 1: Write the architecture check test**

```python
from scripts.check_platform_boundaries import find_forbidden_checks


def test_ui_domain_and_application_have_no_direct_platform_checks():
    violations = find_forbidden_checks()
    assert violations == []
```

- [ ] **Step 2: Run it and record current violations**

Run: `pytest tests/unit/runtime/test_platform_boundaries.py -v`

Expected: FAIL listing current checks in `frontend/theme.py` and other higher
layer files. The failure list is the migration inventory, not an allow-list.

- [ ] **Step 3: Implement the AST checker and move existing checks**

The checker walks Python files under `frontend`, `backend/domain`, and
`backend/application`, reporting comparisons or attribute access involving
`sys.platform`, `os.name`, or `platform.system`. Move the current theme
preference lookup into `runtime/platform_theme.py` behind a `ThemeHints`
dataclass. Keep pre-`QApplication` Windows taskbar setup in `main.py`; document
it as a bootstrap exception.

```python
FORBIDDEN_ROOTS = (
    Path("src/strange_uta_game/frontend"),
    Path("src/strange_uta_game/backend/domain"),
    Path("src/strange_uta_game/backend/application"),
)
```

- [ ] **Step 4: Add and run the CI check**

Add `python scripts/check_platform_boundaries.py` before packaging in CI.

Run: `python scripts/check_platform_boundaries.py && pytest tests/unit/runtime tests/unit/frontend -v`

Expected: checker exits 0 and tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/check_platform_boundaries.py src/strange_uta_game/runtime src/strange_uta_game/frontend/theme.py tests/unit/runtime .github/workflows/release.yml README_DEV.md
git commit -m "refactor: enforce shared-first platform boundaries"
```

## Completion Gate

Run:

```bash
python scripts/check_platform_boundaries.py
pytest tests/unit/runtime tests/unit/frontend tests/unit/domain tests/unit/application tests/unit/infrastructure -v
```

Expected: no platform-boundary violations and the complete unit suite passes.
On Windows, verify an existing portable-directory configuration migrates once;
on macOS and Linux, verify new data is written beneath Qt standard locations.
