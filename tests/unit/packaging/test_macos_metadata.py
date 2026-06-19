import plistlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_entitlements_keep_hardened_runtime_restrictions():
    with (ROOT / "packaging/macos/entitlements.plist").open("rb") as stream:
        entitlements = plistlib.load(stream)

    assert "com.apple.security.cs.allow-jit" not in entitlements
    assert "com.apple.security.cs.disable-library-validation" not in entitlements


def test_packager_requires_identity_and_notary_credentials():
    script_text = (ROOT / "packaging/macos/sign_and_package.sh").read_text(
        encoding="utf-8"
    )

    for name in (
        "APPLE_SIGNING_IDENTITY",
        "APPLE_ID",
        "APPLE_TEAM_ID",
        "APPLE_APP_PASSWORD",
    ):
        assert f"${{{name}:?" in script_text
