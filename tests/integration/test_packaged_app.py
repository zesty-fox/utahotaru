from pathlib import Path

import pytest

from scripts.smoke_test_installed_app import InstalledAppSmoke, run_smoke


class FakePackagedApp:
    def __init__(self, root: Path):
        self.root = root
        self.closed = False

    def start(self) -> None:
        pass

    def open_legacy_project(self) -> None:
        pass

    def export_srt(self) -> None:
        (self.root / "smoke.srt").write_text("subtitle", encoding="utf-8")

    def close(self) -> None:
        self.closed = True


class FakeQtApplication:
    def __init__(self):
        self.quit_called = False

    def processEvents(self) -> None:
        pass

    def quit(self) -> None:
        self.quit_called = True


def test_smoke_report_requires_start_open_export_and_clean_exit(tmp_path):
    packaged_app = FakePackagedApp(tmp_path)

    report = run_smoke(packaged_app)

    assert report == {
        "schema": 1,
        "started": True,
        "opened_legacy_project": True,
        "exported_srt": True,
        "clean_exit": True,
    }
    assert packaged_app.closed


def test_source_smoke_opens_legacy_project_and_exports_srt(tmp_path):
    pytest.importorskip("PyQt6")
    qt_app = FakeQtApplication()
    fixture = (
        Path(__file__).parents[2]
        / "src/strange_uta_game/resource/smoke/legacy_v2.sug"
    )
    packaged_app = InstalledAppSmoke(qt_app, fixture, tmp_path)

    report = run_smoke(packaged_app)

    assert all(value is True for key, value in report.items() if key != "schema")
    assert (tmp_path / "legacy-v2.srt").read_text(encoding="utf-8").startswith(
        "1\n00:00:01,000 --> 00:00:06,000\n"
    )
    assert qt_app.quit_called
