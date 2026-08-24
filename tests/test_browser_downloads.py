from __future__ import annotations

from collections import deque
from hashlib import sha256
from pathlib import Path

from aios_tools.browser.downloads import (
    DownloadLimits,
    DownloadQuarantine,
    DownloadTransferCancelled,
)


def _quarantine(tmp_path: Path, **overrides) -> DownloadQuarantine:
    limits = DownloadLimits(
        max_downloads=overrides.get("max_downloads", 2),
        max_file_bytes=overrides.get("max_file_bytes", 1024),
        max_aggregate_bytes=overrides.get("max_aggregate_bytes", 2048),
    )
    return DownloadQuarantine(tmp_path, limits, id_factory=overrides.get("id_factory"))


def test_download_quarantine_hash_and_no_promotion(tmp_path):
    quarantine = _quarantine(tmp_path)
    body = b"hostile browser bytes"
    record = quarantine.quarantine_chunks(
        [body],
        source_url="https://example.com/files/report.pdf?token=SECRET",
        suggested_filename="report.pdf",
        content_type="application/pdf",
        declared_size=len(body),
    )
    assert record.state == "QUARANTINED"
    assert record.promoted is False
    assert record.sha256 == "sha256:" + sha256(body).hexdigest()
    assert record.source_origin == "https://example.com"
    assert "SECRET" not in str(record.to_dict())
    assert record.quarantine_name is not None
    stored = tmp_path / record.quarantine_name
    assert stored.read_bytes() == body


def test_download_path_traversal_suggested_filename_is_blocked(tmp_path):
    quarantine = _quarantine(tmp_path)
    record = quarantine.quarantine_chunks(
        [b"x"],
        source_url="https://example.com/download",
        suggested_filename="../../escape.exe",
    )
    assert record.state == "BLOCKED"
    assert record.reason == "SUGGESTED_FILENAME_PATH_TRAVERSAL"
    assert record.promoted is False
    assert record.quarantine_name is None
    assert list(tmp_path.iterdir()) == []


def test_download_declared_size_budget_blocks_before_write(tmp_path):
    quarantine = _quarantine(tmp_path, max_file_bytes=4, max_aggregate_bytes=8)
    record = quarantine.quarantine_chunks(
        [b"12345"],
        source_url="https://example.com/download",
        suggested_filename="large.bin",
        declared_size=5,
    )
    assert record.state == "BLOCKED"
    assert record.reason == "DOWNLOAD_FILE_SIZE_BUDGET_EXHAUSTED"
    assert list(tmp_path.iterdir()) == []


def test_download_stream_over_budget_is_explicit_incomplete_and_unpromoted(tmp_path):
    quarantine = _quarantine(tmp_path, max_file_bytes=4, max_aggregate_bytes=8)
    record = quarantine.quarantine_chunks(
        [b"12", b"345"],
        source_url="https://example.com/download",
        suggested_filename="unknown.bin",
    )
    assert record.state == "INCOMPLETE"
    assert record.reason == "DOWNLOAD_FILE_SIZE_BUDGET_EXHAUSTED"
    assert record.promoted is False
    assert record.observed_bytes == 2
    assert record.quarantine_name is not None
    assert record.quarantine_name.endswith(".partial")
    assert (tmp_path / record.quarantine_name).read_bytes() == b"12"


def test_download_partial_cancel_no_promotion(tmp_path):
    quarantine = _quarantine(tmp_path)

    def chunks():
        yield b"partial"
        raise DownloadTransferCancelled("cancel fixture")

    record = quarantine.quarantine_chunks(
        chunks(),
        source_url="https://example.com/download",
        suggested_filename="partial.bin",
    )
    assert record.state == "INCOMPLETE"
    assert record.reason == "DOWNLOAD_CANCELLED"
    assert record.promoted is False
    assert record.observed_bytes == len(b"partial")
    assert record.quarantine_name.endswith(".partial")


def test_download_mime_extension_mismatch_is_visible_not_silently_renamed(tmp_path):
    quarantine = _quarantine(tmp_path)
    record = quarantine.quarantine_chunks(
        [b"%PDF"],
        source_url="https://example.com/download",
        suggested_filename="payload.exe",
        content_type="application/pdf",
    )
    assert record.state == "QUARANTINED"
    assert record.suggested_filename == "payload.exe"
    assert record.mime_extension_mismatch is True


def test_download_duplicate_collision_allocates_new_runtime_name(tmp_path):
    tokens = deque(["same", "same", "unique"])
    quarantine = _quarantine(tmp_path, id_factory=lambda: tokens.popleft())
    first = quarantine.quarantine_chunks(
        [b"a"],
        source_url="https://example.com/a",
        suggested_filename="a.bin",
    )
    second = quarantine.quarantine_chunks(
        [b"b"],
        source_url="https://example.com/b",
        suggested_filename="b.bin",
    )
    assert first.quarantine_name == "download-same.quarantine"
    assert second.quarantine_name == "download-unique.quarantine"
    assert (tmp_path / first.quarantine_name).read_bytes() == b"a"
    assert (tmp_path / second.quarantine_name).read_bytes() == b"b"


def test_download_count_and_aggregate_budgets_never_expand(tmp_path):
    quarantine = _quarantine(tmp_path, max_downloads=2, max_file_bytes=4, max_aggregate_bytes=5)
    first = quarantine.quarantine_chunks(
        [b"123"],
        source_url="https://example.com/1",
        suggested_filename="1.bin",
    )
    second = quarantine.quarantine_chunks(
        [b"45"],
        source_url="https://example.com/2",
        suggested_filename="2.bin",
    )
    third = quarantine.quarantine_chunks(
        [b"x"],
        source_url="https://example.com/3",
        suggested_filename="3.bin",
    )
    assert first.state == "QUARANTINED"
    assert second.state == "QUARANTINED"
    assert third.state == "BLOCKED"
    assert third.reason == "DOWNLOAD_COUNT_BUDGET_EXHAUSTED"
    assert quarantine.aggregate_bytes_used == 5


def test_download_source_file_symlink_is_rejected_when_supported(tmp_path):
    source = tmp_path / "source.bin"
    source.write_bytes(b"x")
    link = tmp_path / "source-link.bin"
    try:
        link.symlink_to(source)
    except (OSError, NotImplementedError):
        return
    quarantine_root = tmp_path / "q"
    quarantine_root.mkdir()
    quarantine = DownloadQuarantine(
        quarantine_root,
        DownloadLimits(max_downloads=1, max_file_bytes=16, max_aggregate_bytes=16),
    )
    try:
        quarantine.quarantine_file(
            link,
            source_url="https://example.com/file",
            suggested_filename="file.bin",
        )
    except Exception as exc:
        assert "reparse" in str(exc)
    else:
        raise AssertionError("symlink source unexpectedly admitted")


def test_browser_inspect_public_payload_still_has_no_download_path_surface():
    runtime = Path(__file__).resolve().parents[1] / "src" / "aios_tools" / "browser" / "runtime.py"
    source = runtime.read_text(encoding="utf-8")
    public_fields = '{"url", "visible_text_chars", "elapsed_seconds"}'
    assert public_fields in source
    for forbidden in ("download_dir", "download_path", "output_dir", "destination_path"):
        assert forbidden not in public_fields


def test_download_elapsed_budget_blocks_and_never_expands(tmp_path):
    ticks = iter([0.0, 0.5, 1.1])
    last = [0.0]

    def clock():
        try:
            last[0] = next(ticks)
        except StopIteration:
            pass
        return last[0]

    quarantine = _quarantine(
        tmp_path,
        max_elapsed_seconds=1.0,
        clock=clock,
    )
    record = quarantine.quarantine_chunks(
        [b"a", b"b"],
        source_url="https://example.com/time",
        suggested_filename="time.bin",
    )
    assert record.state == "INCOMPLETE"
    assert record.reason == "DOWNLOAD_ELAPSED_BUDGET_EXHAUSTED"
    assert record.promoted is False
    assert record.observed_bytes == 1
