import configparser
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_desktop_entry_executes_packaged_binary():
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(ROOT / "packaging/linux/strangeutagame.desktop", encoding="utf-8")
    entry = parser["Desktop Entry"]

    assert entry["Exec"] == "StrangeUtaGame %F"
    assert "application/x-strangeutagame" in entry["MimeType"]


def test_flatpak_uses_fixed_app_id():
    manifest = json.loads(
        (ROOT / "packaging/linux/io.github.karaoke_studio.StrangeUtaGame.yml").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["app-id"] == "io.github.karaoke_studio.StrangeUtaGame"
    assert "--socket=pulseaudio" in manifest["finish-args"]


def test_deb_declares_native_audio_and_qt_dependencies():
    fields = {}
    for line in (ROOT / "packaging/linux/debian/control").read_text(encoding="utf-8").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key] = value.strip()

    assert fields["Architecture"] == "amd64"
    assert "libportaudio2" in fields["Depends"]
    assert "libgl1" in fields["Depends"]
