import pytest

from scripts.release_tools.targets import BuildTarget


@pytest.mark.parametrize(
    ("target_id", "artifact"),
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
