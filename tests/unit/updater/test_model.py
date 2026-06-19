from strange_uta_game.updater.model import (
    PackageChannel,
    UpdateError,
    UpdateTarget,
)


def test_target_key_includes_package_channel():
    target = UpdateTarget("linux", "x86_64", PackageChannel.FLATPAK)

    assert target.key == "linux-x86_64-flatpak"


def test_update_error_separates_user_and_diagnostic_messages():
    error = UpdateError(
        code="signature_invalid",
        user_message="更新信息签名无效",
        diagnostic="ed25519 verification failed for manifest-v2.json",
        recoverable=False,
    )

    assert "ed25519" not in error.user_message
    assert not error.recoverable
