"""Shared update checking and verified artifact download orchestration."""

from __future__ import annotations

import json
import os
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .model import ReleaseChannel, UpdateError, UpdateOffer, UpdateTarget
from .signed_manifest import (
    ArtifactHashError,
    ManifestError,
    ManifestSignatureError,
    parse_manifest,
    verify_artifact_hash,
    verify_manifest_signature,
)
from .version import is_newer_version

DEFAULT_MANIFEST_URLS = (
    "https://github.com/karaoke-studio/StrangeUtaGame/"
    "releases/latest/download/manifest-v2.json",
)


class UpdateHttpClient(Protocol):
    def get_bytes(self, url: str) -> bytes: ...

    def download_to(self, url: str, path: Path, **kwargs) -> None: ...


class UpdateCheckError(RuntimeError):
    def __init__(self, error: UpdateError):
        self.error = error
        super().__init__(error.diagnostic or error.user_message)


@dataclass(frozen=True)
class DownloadResult:
    path: Path | None = None
    error: UpdateError | None = None

    @property
    def ok(self) -> bool:
        return self.path is not None and self.error is None


class UpdateService:
    def __init__(
        self,
        http: UpdateHttpClient,
        *,
        public_key: Ed25519PublicKey | bytes,
        manifest_urls: tuple[str, ...] = DEFAULT_MANIFEST_URLS,
    ) -> None:
        self._http = http
        self._public_key = public_key
        self._manifest_urls = manifest_urls

    def check(
        self,
        channel: ReleaseChannel,
        target: UpdateTarget,
        *,
        current_version: str,
    ) -> UpdateOffer | None:
        diagnostics: list[str] = []
        signature_failed = False
        for manifest_url in self._manifest_urls:
            try:
                payload = self._http.get_bytes(manifest_url)
                signature = self._http.get_bytes(f"{manifest_url}.sig")
                verify_manifest_signature(payload, signature, self._public_key)
                raw_manifest = json.loads(payload)
                if not isinstance(raw_manifest, dict):
                    raise ManifestError("manifest root must be an object")
                offer = parse_manifest(raw_manifest).select(channel, target)
                return offer if is_newer_version(offer.version, current_version) else None
            except Exception as error:
                signature_failed = signature_failed or isinstance(
                    error, ManifestSignatureError
                )
                diagnostics.append(f"{manifest_url}: {error}")
        error = UpdateError(
            code="signature_invalid" if signature_failed else "manifest_unavailable",
            user_message=(
                "更新信息签名无效" if signature_failed else "无法获取可信的更新信息"
            ),
            diagnostic=" | ".join(diagnostics),
            recoverable=not signature_failed,
        )
        raise UpdateCheckError(error)

    def download(
        self,
        offer: UpdateOffer,
        cache_dir: Path,
        *,
        progress_cb=None,
        cancel_check=None,
    ) -> DownloadResult:
        cache_dir.mkdir(parents=True, exist_ok=True)
        partial = cache_dir / f"{offer.artifact.name}.partial"
        final = cache_dir / offer.artifact.name
        try:
            self._http.download_to(
                offer.artifact.url,
                partial,
                progress_cb=progress_cb,
                cancel_check=cancel_check,
            )
            if partial.stat().st_size != offer.artifact.size:
                raise ArtifactHashError("artifact size verification failed")
            verify_artifact_hash(partial, offer.artifact.sha256)
            os.replace(partial, final)
            return DownloadResult(path=final)
        except ArtifactHashError as error:
            update_error = UpdateError(
                "artifact_hash_invalid",
                "更新文件校验失败",
                str(error),
                False,
            )
        except OSError as error:
            update_error = UpdateError(
                "artifact_write_failed",
                "无法保存更新文件",
                str(error),
                True,
            )
        except Exception as error:
            code = "cancelled" if cancel_check and cancel_check() else "download_failed"
            update_error = UpdateError(
                code,
                "更新下载已取消" if code == "cancelled" else "更新文件下载失败",
                str(error),
                code != "cancelled",
            )
        with suppress(OSError):
            partial.unlink(missing_ok=True)
        return DownloadResult(error=update_error)
