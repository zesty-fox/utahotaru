from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from strange_uta_game.updater.model import (
    InstallAction,
    PackageChannel,
    ReleaseChannel,
    UpdateArtifact,
    UpdateOffer,
    UpdateTarget,
)
from strange_uta_game.updater.service import UpdateService


class FakeHttp:
    def __init__(self, responses=None, download_data=b""):
        self.responses = responses or {}
        self.download_data = download_data
        self.requested = []

    def get_bytes(self, url: str) -> bytes:
        self.requested.append(url)
        return self.responses[url]

    def download_to(self, url: str, path: Path, **kwargs) -> None:
        self.requested.append(url)
        path.write_bytes(self.download_data)


def test_check_verifies_before_parsing():
    fixture = Path(__file__).resolve().parents[2] / "fixtures" / "updater" / "manifest-v2.json"
    manifest_bytes = fixture.read_bytes()
    private_key = Ed25519PrivateKey.generate()
    manifest_url = "https://updates.example.invalid/manifest-v2.json"
    fake_http = FakeHttp(
        {
            manifest_url: manifest_bytes,
            f"{manifest_url}.sig": private_key.sign(manifest_bytes),
        }
    )
    service = UpdateService(
        fake_http,
        public_key=private_key.public_key(),
        manifest_urls=(manifest_url,),
    )

    offer = service.check(
        ReleaseChannel.STABLE,
        UpdateTarget("linux", "x86_64", PackageChannel.APPIMAGE),
        current_version="1.2.3",
    )

    assert offer is not None
    assert offer.version == "2.0.0"
    assert fake_http.requested[-1].endswith("manifest-v2.json.sig")


def test_download_removes_partial_file_after_hash_failure(tmp_path):
    artifact = UpdateArtifact(
        name="new.AppImage",
        url="https://example.invalid/new.AppImage",
        size=7,
        sha256="0" * 64,
        action=InstallAction.REPLACE_APPIMAGE_ON_EXIT,
    )
    offer = UpdateOffer(
        ReleaseChannel.STABLE,
        "2.0.0",
        "1.2.3",
        UpdateTarget("linux", "x86_64", PackageChannel.APPIMAGE),
        artifact,
    )
    service = UpdateService(FakeHttp(download_data=b"partial"), public_key=b"")

    result = service.download(offer, tmp_path)

    assert result.error is not None
    assert result.error.code == "artifact_hash_invalid"
    assert list(tmp_path.iterdir()) == []
