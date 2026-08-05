from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from audio_model_lock_common import *

def _validate_base_manifest(data: dict[str, Any]) -> None:
    if data.get("profile_id") != PROFILE_ID:
        raise DependencyLockError("unexpected profile_id")
    if data.get("tool_identity") != TOOL_IDENTITY:
        raise DependencyLockError("unexpected tool_identity")
    authority = data.get("authority")
    if not isinstance(authority, dict) or authority.get("authority_transfer") is not False:
        raise DependencyLockError("authority_transfer must remain false")
    runtime = data.get("runtime_reference")
    if not isinstance(runtime, dict) or runtime.get("network_during_analysis") is not False:
        raise DependencyLockError("analysis network policy must remain false")
    weights = data.get("weights")
    if not isinstance(weights, list) or [item.get("target") for item in weights] != EXPECTED_TARGETS:
        raise DependencyLockError("weight target order is not contractual")


def _extract_license(record: dict[str, Any]) -> str:
    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        raise DependencyLockError("Zenodo record metadata is missing")
    license_value = metadata.get("license")
    if isinstance(license_value, dict):
        identifier = license_value.get("id") or license_value.get("title")
    else:
        identifier = license_value
    if not isinstance(identifier, str) or not identifier.strip():
        raise DependencyLockError("Zenodo record license is missing")
    return identifier.strip()


def _zenodo_files(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    files = record.get("files")
    if not isinstance(files, list):
        raise DependencyLockError("Zenodo record files are missing")
    indexed: dict[str, dict[str, Any]] = {}
    for item in files:
        if isinstance(item, dict) and isinstance(item.get("key"), str):
            indexed[item["key"]] = item
    return indexed


def run_fetch(args: argparse.Namespace) -> int:
    base = load_json(args.manifest)
    _validate_base_manifest(base)
    quarantine = args.quarantine.resolve()
    if quarantine.exists() and any(quarantine.iterdir()) and not args.allow_existing:
        raise DependencyLockError(f"quarantine is not empty: {quarantine}")
    package_dir = quarantine / "package"
    weights_dir = quarantine / "weights"
    metadata_dir = quarantine / "metadata"
    receipt_path = args.output.resolve()

    pypi, pypi_transport = fetch_json(PYPI_JSON_URL)
    write_json(metadata_dir / "openunmix-1.3.0-pypi.json", pypi)
    urls = pypi.get("urls")
    if not isinstance(urls, list):
        raise DependencyLockError("PyPI release file list is missing")
    wheel = next((item for item in urls if isinstance(item, dict) and item.get("filename") == PACKAGE_FILENAME), None)
    if wheel is None:
        raise DependencyLockError(f"PyPI wheel not found: {PACKAGE_FILENAME}")
    digests = wheel.get("digests")
    if not isinstance(digests, dict):
        raise DependencyLockError("PyPI wheel digests are missing")
    wheel_sha256 = digests.get("sha256")
    wheel_md5 = digests.get("md5")
    wheel_size = wheel.get("size")
    wheel_url = wheel.get("url")
    if not isinstance(wheel_url, str) or not isinstance(wheel_size, int):
        raise DependencyLockError("PyPI wheel URL or size is invalid")
    governed_package = base.get("package_artifact")
    if isinstance(governed_package, dict) and governed_package.get("locked") is True:
        governed_sha256 = governed_package.get("sha256")
        governed_size = governed_package.get("byte_size")
        if governed_sha256 != wheel_sha256 or governed_size != wheel_size:
            raise DependencyLockError("PyPI package artifact no longer matches the frozen manifest")
    package_result = fetch_file(
        wheel_url,
        package_dir / PACKAGE_FILENAME,
        expected_sha256=wheel_sha256 if isinstance(wheel_sha256, str) else None,
        expected_md5=wheel_md5 if isinstance(wheel_md5, str) else None,
        expected_size=wheel_size,
    )

    zenodo, zenodo_transport = fetch_json(ZENODO_RECORD_URL)
    write_json(metadata_dir / "zenodo-3370489.json", zenodo)
    zenodo_files = _zenodo_files(zenodo)
    license_id = _extract_license(zenodo)
    weight_receipts: list[dict[str, Any]] = []
    for item in base["weights"]:
        filename = item["filename"]
        provider_md5 = item["provider_md5"]
        source_url = item["source_url"]
        record_file = zenodo_files.get(filename)
        if record_file is None:
            raise DependencyLockError(f"weight absent from Zenodo record: {filename}")
        record_checksum = record_file.get("checksum")
        if not isinstance(record_checksum, str) or not record_checksum.startswith("md5:"):
            raise DependencyLockError(f"Zenodo provider checksum missing for {filename}")
        record_md5 = record_checksum.split(":", 1)[1].lower()
        if record_md5 != provider_md5:
            raise DependencyLockError(
                f"governed/provider MD5 mismatch for {filename}: manifest {provider_md5}, Zenodo {record_md5}"
            )
        record_size = record_file.get("size")
        if not isinstance(record_size, int) or record_size <= 0:
            raise DependencyLockError(f"Zenodo byte size missing for {filename}")
        governed_sha256 = item.get("sha256")
        governed_size = item.get("byte_size")
        if item.get("locked") is True:
            if not isinstance(governed_sha256, str) or not HEX64.fullmatch(governed_sha256):
                raise DependencyLockError(f"frozen SHA-256 missing for {filename}")
            if governed_size != record_size:
                raise DependencyLockError(f"Zenodo byte size no longer matches the frozen manifest: {filename}")
        result = fetch_file(
            source_url,
            weights_dir / filename,
            expected_sha256=governed_sha256 if isinstance(governed_sha256, str) else None,
            expected_md5=provider_md5,
            expected_size=record_size,
        )
        weight_receipts.append(
            {
                "target": item["target"],
                "filename": filename,
                "source_url": source_url,
                "final_url": result["final_url"],
                "redirect_chain": result["redirect_chain"],
                "provider_md5": provider_md5,
                "local_md5": result["md5"],
                "sha256": result["sha256"],
                "byte_size": result["byte_size"],
                "admitted_to_quarantine": True,
            }
        )

    receipt = {
        "schema_version": "0.1.0",
        "status": "DEPENDENCIES_QUARANTINED_VERIFIED",
        "run_classification": "CONTROLLED_DEPENDENCY_FETCH",
        "profile_id": PROFILE_ID,
        "tool_identity": TOOL_IDENTITY,
        "retrieved_at": utc_now(),
        "authority_transfer": False,
        "network_policy": {
            "phase": "CONTROLLED_DEPENDENCY_FETCH",
            "allowed_hosts": sorted(ALLOWED_FETCH_HOSTS),
            "analysis_network_allowed": False,
        },
        "provider_metadata": {
            "pypi": pypi_transport,
            "zenodo": {
                **zenodo_transport,
                "record_id": 3370489,
                "doi": "10.5281/zenodo.3370489",
                "license": license_id,
            },
        },
        "package_artifact": {
            "filename": PACKAGE_FILENAME,
            "source_url": wheel_url,
            "final_url": package_result["final_url"],
            "redirect_chain": package_result["redirect_chain"],
            "provider_sha256": wheel_sha256,
            "local_sha256": package_result["sha256"],
            "provider_md5": wheel_md5,
            "local_md5": package_result["md5"],
            "byte_size": package_result["byte_size"],
            "admitted_to_quarantine": True,
        },
        "weights": weight_receipts,
        "gates": {
            "package_artifact_locked": True,
            "all_weight_provider_checksums_verified": True,
            "all_weight_sha256_present": True,
            "resource_envelope_measured_with_pretrained_weights": False,
            "profile_checksum_frozen": False,
            "runtime_review_completed": False,
            "runtime_admission": False,
            "pilot_authorized": False,
        },
    }
    write_json(receipt_path, receipt)
    print("DEPENDENCY_FETCH_RECEIPT_JSON=" + json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


class PeakMemorySampler:
    def __init__(self, interval_seconds: float = 0.05):
        self.interval_seconds = interval_seconds
        self.peak_rss = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _sample(self) -> None:
        import psutil

        process = psutil.Process(os.getpid())
        while not self._stop.is_set():
            rss = process.memory_info().rss
            for child in process.children(recursive=True):
                try:
                    rss += child.memory_info().rss
                except psutil.Error:
                    continue
            self.peak_rss = max(self.peak_rss, rss)
            self._stop.wait(self.interval_seconds)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._sample, name="peak-rss-sampler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

