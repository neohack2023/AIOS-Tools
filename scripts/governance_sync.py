#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_DISPOSITIONS = {
    "NO_MATERIAL_DELTA",
    "MATERIAL_DELTA_RECONCILED",
    "MATERIAL_DELTA_PENDING",
}


def parse_top_level_map(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for line in text.splitlines():
        if not line or line[0].isspace() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def err(code: str, message: str) -> Dict[str, str]:
    return {"code": code, "message": message}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_repository(root: Path = ROOT) -> Dict[str, object]:
    errors: List[Dict[str, str]] = []
    lock_path = root / "docs/agent-system/context/governance-lock.yaml"
    if not lock_path.is_file():
        return {"schema": "AIOS_TOOLS_GOVERNANCE_SYNC_VALIDATION_01", "result": "FAIL", "errors": [err("GSYNC-LOCK-MISSING", "governance lock missing")]}

    lock = parse_top_level_map(lock_path.read_text(encoding="utf-8"))
    required_lock = {
        "repository_autonomy_phase",
        "sync_state",
        "sync_role",
        "sync_freshness_days",
        "upstream_source_ids_csv",
        "last_sync_receipt",
        "last_sync_receipt_sha256",
        "valid_through",
    }
    missing = sorted(required_lock - set(lock))
    if missing:
        errors.append(err("GSYNC-LOCK-FIELDS", f"missing lock fields: {', '.join(missing)}"))
        return {"schema": "AIOS_TOOLS_GOVERNANCE_SYNC_VALIDATION_01", "result": "FAIL", "errors": errors}

    if lock["repository_autonomy_phase"] != "5":
        errors.append(err("GSYNC-PHASE", "repository_autonomy_phase must be 5"))
    if lock["sync_role"] != "KNOWLEDGE_STEWARD":
        errors.append(err("GSYNC-ROLE", "sync role must remain KNOWLEDGE_STEWARD"))
    if lock["sync_state"] not in {"ACTIVE", "ACTIVE_PENDING_DELTA"}:
        errors.append(err("GSYNC-STATE", "sync_state must be ACTIVE or ACTIVE_PENDING_DELTA"))

    try:
        freshness_days = int(lock["sync_freshness_days"])
    except ValueError:
        freshness_days = 0
        errors.append(err("GSYNC-FRESHNESS", "sync_freshness_days must be an integer"))
    if freshness_days <= 0:
        errors.append(err("GSYNC-FRESHNESS", "sync_freshness_days must be positive"))

    receipt_rel = lock["last_sync_receipt"]
    receipt_path = root / receipt_rel
    if not receipt_path.is_file():
        errors.append(err("GSYNC-RECEIPT-MISSING", f"receipt missing: {receipt_rel}"))
        return {"schema": "AIOS_TOOLS_GOVERNANCE_SYNC_VALIDATION_01", "result": "FAIL", "errors": errors}

    receipt_bytes = receipt_path.read_bytes()
    observed_digest = sha256_bytes(receipt_bytes)
    if observed_digest != lock["last_sync_receipt_sha256"]:
        errors.append(err("GSYNC-RECEIPT-DIGEST", f"receipt digest mismatch: observed {observed_digest}"))

    try:
        receipt = json.loads(receipt_bytes)
    except json.JSONDecodeError as exc:
        errors.append(err("GSYNC-RECEIPT-JSON", f"invalid receipt JSON: {exc}"))
        return {"schema": "AIOS_TOOLS_GOVERNANCE_SYNC_VALIDATION_01", "result": "FAIL", "errors": errors}

    if receipt.get("schema") != "AIOS_TOOLS_GOVERNANCE_SYNC_RECEIPT_01":
        errors.append(err("GSYNC-SCHEMA", "unexpected receipt schema"))
    if receipt.get("repository") != "neohack2023/AIOS-Tools":
        errors.append(err("GSYNC-REPOSITORY", "receipt repository mismatch"))

    expected_sources = [s for s in lock["upstream_source_ids_csv"].split(",") if s]
    source_set = receipt.get("source_set") or []
    actual_sources = [item.get("source_id") for item in source_set if isinstance(item, dict)]
    if actual_sources != expected_sources:
        errors.append(err("GSYNC-SOURCE-SET", f"source set mismatch: expected {expected_sources}, got {actual_sources}"))
    for item in source_set:
        if not isinstance(item, dict):
            errors.append(err("GSYNC-SOURCE-SHAPE", "source record must be an object"))
            continue
        page_id = str(item.get("notion_page_id", ""))
        if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", page_id):
            errors.append(err("GSYNC-SOURCE-ID", f"invalid opaque upstream page id for {item.get('source_id')}"))
        if not item.get("observed_last_edited_at"):
            errors.append(err("GSYNC-SOURCE-VERSION", f"missing observed source version for {item.get('source_id')}"))
        if not item.get("classification"):
            errors.append(err("GSYNC-SOURCE-CLASS", f"missing source classification for {item.get('source_id')}"))

    disposition = receipt.get("delta_disposition")
    if disposition not in ALLOWED_DISPOSITIONS:
        errors.append(err("GSYNC-DISPOSITION", f"invalid delta disposition {disposition!r}"))

    authority = receipt.get("authority_boundary") or {}
    if authority.get("normal_repo_work_external_fetch_required") is not False:
        errors.append(err("GSYNC-LOCAL-FIRST", "normal repository work must remain external-fetch-free"))
    if authority.get("upstream_authority_cutover") is not False:
        errors.append(err("GSYNC-AUTHORITY", "synchronization must not cut upstream authority over to GitHub"))
    if authority.get("mutation_authority_granted_by_sync") is not False:
        errors.append(err("GSYNC-MUTATION", "synchronization must not grant mutation authority"))
    if authority.get("sync_role") != "KNOWLEDGE_STEWARD":
        errors.append(err("GSYNC-ROLE", "receipt sync role must be KNOWLEDGE_STEWARD"))

    freshness = receipt.get("freshness") or {}
    renewal = freshness.get("renewal_applied")
    previous = freshness.get("previous_valid_through")
    requested = freshness.get("requested_valid_through")
    lock_valid = lock["valid_through"]

    if disposition == "MATERIAL_DELTA_PENDING":
        if renewal is not False:
            errors.append(err("GSYNC-PENDING-RENEWAL", "pending material delta cannot renew freshness"))
        if previous != requested or requested != lock_valid:
            errors.append(err("GSYNC-PENDING-WINDOW", "pending delta must leave valid_through unchanged"))
        if lock["sync_state"] != "ACTIVE_PENDING_DELTA":
            errors.append(err("GSYNC-PENDING-STATE", "pending material delta requires ACTIVE_PENDING_DELTA"))
    elif disposition in {"NO_MATERIAL_DELTA", "MATERIAL_DELTA_RECONCILED"}:
        if renewal is not True:
            errors.append(err("GSYNC-RENEWAL", "reconciled/no-delta receipt must explicitly apply renewal"))
        try:
            performed = date.fromisoformat(str(receipt.get("performed_on", "")))
            expected_valid = (performed + timedelta(days=freshness_days)).isoformat()
        except ValueError:
            expected_valid = None
            errors.append(err("GSYNC-DATE", "performed_on must be an ISO date"))
        if expected_valid and (requested != expected_valid or lock_valid != expected_valid):
            errors.append(err("GSYNC-RENEWAL-WINDOW", f"renewed valid_through must equal {expected_valid}"))

    return {
        "schema": "AIOS_TOOLS_GOVERNANCE_SYNC_VALIDATION_01",
        "sync_id": receipt.get("sync_id"),
        "receipt_sha256": observed_digest,
        "delta_disposition": disposition,
        "freshness_renewed": renewal,
        "result": "PASS" if not errors else "FAIL",
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="outputs/governance-sync-validation.json")
    args = parser.parse_args()
    report = validate_repository()
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
