from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_installer_uses_per_user_location():
    iss_text = (ROOT / "packaging/windows/StrangeUtaGame.iss").read_text(
        encoding="utf-8"
    )
    assert "PrivilegesRequired=lowest" in iss_text
    assert "DefaultDirName={localappdata}\\Programs\\StrangeUtaGame" in iss_text


def test_installer_registers_project_extension():
    iss_text = (ROOT / "packaging/windows/StrangeUtaGame.iss").read_text(
        encoding="utf-8"
    )
    assert ".sug" in iss_text
    assert "StrangeUtaGame.Project" in iss_text


def test_sign_script_uses_rfc3161_timestamp():
    sign_script = (ROOT / "packaging/windows/sign.ps1").read_text(encoding="utf-8")
    assert "/tr https://timestamp.digicert.com" in sign_script
    assert "/td SHA256" in sign_script
