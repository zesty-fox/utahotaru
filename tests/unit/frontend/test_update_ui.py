from PyQt6.QtWidgets import QWidget

from strange_uta_game.updater.manifest import LatestRelease
from strange_uta_game.updater.model import UpdateError
from strange_uta_game.updater.ui.update_dialog import UpdateAvailableDialog


def test_signature_error_disables_install_button(qtbot):
    release = LatestRelease(
        tag="SUGv2.0.0",
        version="2.0.0",
        name="2.0.0",
        body="",
        html_url="",
        prerelease=False,
        published_at="2026-06-20T00:00:00Z",
    )
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.resize(800, 600)
    dialog = UpdateAvailableDialog(release, local_version="1.2.3", parent=parent)
    qtbot.addWidget(dialog)

    dialog.show_error(
        UpdateError("signature_invalid", "签名无效", "detail", False)
    )

    assert not dialog.install_button.isEnabled()
