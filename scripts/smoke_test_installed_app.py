#!/usr/bin/env python3
"""Run the non-interactive compatibility smoke test in an installed app."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Protocol

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if SRC_ROOT.is_dir() and str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


class SmokeApplication(Protocol):
    def start(self) -> None: ...

    def open_legacy_project(self) -> None: ...

    def export_srt(self) -> None: ...

    def close(self) -> None: ...


class InstalledAppSmoke:
    """Exercise project compatibility and export without touching audio."""

    def __init__(self, qt_app, fixture_path: Path, output_dir: Path):
        self._qt_app = qt_app
        self._fixture_path = fixture_path
        self._output_dir = output_dir
        self._project = None

    def start(self) -> None:
        if self._qt_app is None:
            raise RuntimeError("QApplication was not created")
        self._qt_app.processEvents()

    def open_legacy_project(self) -> None:
        from strange_uta_game.backend.infrastructure.persistence.sug_io import (
            SugProjectParser,
        )

        if not self._fixture_path.is_file():
            raise FileNotFoundError(self._fixture_path)
        self._project = SugProjectParser.load(str(self._fixture_path))

    def export_srt(self) -> None:
        from strange_uta_game.backend.infrastructure.exporters.srt_exporter import (
            SRTExporter,
        )

        if self._project is None:
            raise RuntimeError("no project is open")
        self._output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self._output_dir / "legacy-v2.srt"
        SRTExporter().export(self._project, str(output_path))
        if not output_path.is_file() or not output_path.read_text(encoding="utf-8").strip():
            raise RuntimeError("SRT export is empty")

    def close(self) -> None:
        self._project = None
        self._qt_app.processEvents()
        self._qt_app.quit()


def run_smoke(packaged_app: SmokeApplication) -> dict[str, int | bool]:
    report: dict[str, int | bool] = {
        "schema": 1,
        "started": False,
        "opened_legacy_project": False,
        "exported_srt": False,
        "clean_exit": False,
    }
    try:
        packaged_app.start()
        report["started"] = True
        packaged_app.open_legacy_project()
        report["opened_legacy_project"] = True
        packaged_app.export_srt()
        report["exported_srt"] = True
    except Exception:
        pass
    finally:
        try:
            packaged_app.close()
            report["clean_exit"] = True
        except Exception:
            pass
    return report


def write_report(report_path: Path, report: dict[str, int | bool]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def default_fixture_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT / "src"))
    return base / "strange_uta_game/resource/smoke/legacy_v2.sug"


def execute_installed_smoke(qt_app, report_path: Path) -> int:
    with tempfile.TemporaryDirectory(prefix="strangeutagame-smoke-") as temp_dir:
        report = run_smoke(
            InstalledAppSmoke(qt_app, default_fixture_path(), Path(temp_dir))
        )
    write_report(report_path, report)
    return 0 if all(value is True for key, value in report.items() if key != "schema") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args(argv)
    from PyQt6.QtWidgets import QApplication

    qt_app = QApplication.instance() or QApplication([])
    return execute_installed_smoke(qt_app, args.report)


if __name__ == "__main__":
    raise SystemExit(main())
