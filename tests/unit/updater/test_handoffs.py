from __future__ import annotations

from strange_uta_game.updater.handoffs.appimage import AppImageHandoff
from strange_uta_game.updater.handoffs.flatpak import FlatpakHandoff
from strange_uta_game.updater.handoffs.open_package import OpenPackageHandoff
from strange_uta_game.updater.handoffs.registry import default_handoffs
from strange_uta_game.updater.model import InstallAction


class FakeRunner:
    def __init__(self, returncode: int = 0):
        self.returncode = returncode
        self.calls = []

    def run(self, args, **kwargs):
        self.calls.append(args)
        return type("Result", (), {"returncode": self.returncode})()


def test_registry_selects_by_manifest_action():
    registry = default_handoffs()

    assert isinstance(registry[InstallAction.OPEN_PACKAGE], OpenPackageHandoff)


def test_flatpak_handoff_uses_fixed_app_id(tmp_path):
    runner = FakeRunner(returncode=0)

    result = FlatpakHandoff(runner=runner).launch(tmp_path / "unused")

    assert runner.calls == [
        ["flatpak", "update", "io.github.karaoke_studio.StrangeUtaGame", "-y"]
    ]
    assert result.launched


def test_appimage_handoff_never_replaces_running_binary(tmp_path):
    current = tmp_path / "current.AppImage"
    current.write_bytes(b"current")
    new = tmp_path / "new.AppImage"
    new.write_bytes(b"new")

    result = AppImageHandoff(current=current).prepare(new)

    assert result.exit_required
    assert (tmp_path / "pending-update.json").exists()
    assert current.read_bytes() == b"current"
