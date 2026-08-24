from __future__ import annotations

from hashlib import sha256
import json

import pytest

from aios_tools.browser.downloads import DownloadRecord
from aios_tools.browser.promotion import (
    DownloadPromotionError,
    DownloadPromotionManager,
    DownloadPromotionRules,
)


def _record(body: bytes, *, name="track.mp3", content_type="audio/mpeg", mismatch=False):
    return DownloadRecord(
        state="QUARANTINED",
        source_origin="https://example.com",
        source_path_digest="sha256:path",
        suggested_filename=name,
        content_type=content_type,
        declared_size=len(body),
        observed_bytes=len(body),
        sha256="sha256:" + sha256(body).hexdigest(),
        quarantine_name="download-test.quarantine",
        promoted=False,
        mime_extension_mismatch=mismatch,
        reason=None,
    )


def _manager(tmp_path, body=b"audio"):
    quarantine = tmp_path / "q"
    artifacts = tmp_path / "artifacts"
    quarantine.mkdir()
    artifacts.mkdir()
    (quarantine / "download-test.quarantine").write_bytes(body)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"version": "1", "artifacts": {}}), encoding="utf-8")
    return DownloadPromotionManager(
        quarantine_root=quarantine,
        artifact_root=artifacts,
        manifest_path=manifest,
    ), manifest, artifacts


def _rules(**changes):
    return DownloadPromotionRules(
        profile_id=changes.get("profile_id", "SITE_PROFILE_TEST"),
        auto_promote=changes.get("auto_promote", True),
        allowed_content_types=changes.get("allowed_content_types", ("audio/mpeg",)),
        allowed_extensions=changes.get("allowed_extensions", (".mp3",)),
        max_bytes=changes.get("max_bytes", 1024),
    )


def test_download_auto_promotion_profile_only(tmp_path):
    manager, manifest, artifacts = _manager(tmp_path)
    receipt = manager.promote(_record(b"audio"), _rules())
    assert receipt.automatic is True
    assert receipt.authority_transfer is False
    saved = json.loads(manifest.read_text(encoding="utf-8"))
    assert receipt.artifact_ref in saved["artifacts"]
    assert (artifacts / receipt.relative_path).read_bytes() == b"audio"


def test_download_auto_promotion_requires_profile_admission(tmp_path):
    manager, _, _ = _manager(tmp_path)
    with pytest.raises(DownloadPromotionError, match="does not admit"):
        manager.promote(_record(b"audio"), _rules(auto_promote=False))


@pytest.mark.parametrize("name", ["payload.exe", "payload.ps1", "payload.sh"])
def test_download_auto_promotion_blocks_executables(tmp_path, name):
    manager, _, _ = _manager(tmp_path, body=b"x")
    with pytest.raises(DownloadPromotionError, match="executable"):
        manager.promote(
            _record(b"x", name=name, content_type="application/octet-stream"),
            _rules(
                allowed_content_types=("application/octet-stream",),
                allowed_extensions=(__import__("pathlib").Path(name).suffix,),
            ),
        )


def test_download_auto_promotion_rehashes_quarantine(tmp_path):
    manager, _, _ = _manager(tmp_path, body=b"original")
    record = _record(b"original")
    (manager.quarantine_root / record.quarantine_name).write_bytes(b"changed")
    with pytest.raises(DownloadPromotionError, match="changed"):
        manager.promote(record, _rules())


def test_download_auto_promotion_rejects_symlinked_quarantine_entry(tmp_path):
    manager, _, _ = _manager(tmp_path, body=b"audio")
    source = manager.quarantine_root / "download-test.quarantine"
    real = manager.quarantine_root / "real.quarantine"
    source.replace(real)
    try:
        source.symlink_to(real)
    except (OSError, NotImplementedError):
        return
    with pytest.raises(DownloadPromotionError, match="symlink|reparse"):
        manager.promote(_record(b"audio"), _rules())
