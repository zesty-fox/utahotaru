from strange_uta_game.updater.model import (
    InstallAction,
    PackageChannel,
    ReleaseChannel,
    UpdateArtifact,
    UpdateOffer,
    UpdateTarget,
)
from strange_uta_game.updater.worker import UpdateChecker


class StubService:
    def __init__(self, offer):
        self.offer = offer

    def check(self, channel, target, *, current_version):
        return self.offer


def test_worker_emits_offer_without_platform_fields(qtbot):
    target = UpdateTarget("linux", "x86_64", PackageChannel.FLATPAK)
    offer = UpdateOffer(
        ReleaseChannel.STABLE,
        "2.0.0",
        "1.2.3",
        target,
        UpdateArtifact(
            "app.flatpakref",
            "https://example.invalid/app.flatpakref",
            1,
            "a" * 64,
            InstallAction.FLATPAK_UPDATE,
        ),
    )
    worker = UpdateChecker(service=StubService(offer), target=target)

    with qtbot.waitSignal(worker.check_finished) as signal:
        worker.check_now()

    assert signal.args[0].offer.target == target
