#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import agent_system_audit as base

ROOT = Path(__file__).resolve().parents[1]

base.EXPECTED_SKILLS = set(base.EXPECTED_SKILLS) | {"sync-governance"}
base.REQUIRED_AGENT_SYSTEM_PATHS = set(base.REQUIRED_AGENT_SYSTEM_PATHS) | {
    "docs/agent-system/governance-sync/README.md",
    "docs/agent-system/governance-sync/UPSTREAM_SYNC_PROFILE.md",
    "docs/agent-system/governance-sync/receipts/GSYNC-AIOS-TOOLS-20260904-001.json",
}


def validate_lock_phase5(lock, today: date):
    errors = []
    required = {
        "bundle_id",
        "bundle_version",
        "state",
        "materialized_on",
        "valid_through",
        "normal_repo_work_external_fetch_required",
        "upstream_authority_cutover",
        "repository_autonomy_phase",
        "native_adapter_state",
        "native_skill_state",
        "organization_audit_state",
        "sync_state",
        "sync_role",
        "sync_freshness_days",
        "upstream_source_ids_csv",
        "last_sync_receipt",
        "last_sync_receipt_sha256",
    }
    missing = sorted(required - set(lock))
    if missing:
        errors.append(base.error("AOS-LOCK-MISSING", f"missing governance-lock fields: {', '.join(missing)}"))
        return errors
    if lock["repository_autonomy_phase"] != "5":
        errors.append(base.error("AOS-LOCK-PHASE", "repository_autonomy_phase must be 5"))
    if lock["organization_audit_state"] != "ACTIVE":
        errors.append(base.error("AOS-LOCK-AUDIT", "organization_audit_state must be ACTIVE"))
    if lock["sync_state"] not in {"ACTIVE", "ACTIVE_PENDING_DELTA"}:
        errors.append(base.error("AOS-LOCK-SYNC", "Phase 5 sync_state must be ACTIVE or ACTIVE_PENDING_DELTA"))
    if lock["sync_role"] != "KNOWLEDGE_STEWARD":
        errors.append(base.error("AOS-LOCK-SYNC-ROLE", "Phase 5 sync role must be KNOWLEDGE_STEWARD"))
    if lock["normal_repo_work_external_fetch_required"].lower() != "false":
        errors.append(base.error("AOS-LOCK-LOCAL-FIRST", "normal repo work must remain external-fetch-free"))
    if lock["upstream_authority_cutover"].lower() != "false":
        errors.append(base.error("AOS-LOCK-AUTHORITY", "Phase 5 must not cut upstream authority over to GitHub"))
    try:
        expiry = date.fromisoformat(lock["valid_through"])
    except ValueError:
        errors.append(base.error("AOS-LOCK-DATE", "valid_through must be an ISO date"))
    else:
        if today > expiry:
            errors.append(base.error("AOS-LOCK-STALE", f"governance bundle expired on {expiry.isoformat()}"))
    return errors


base.validate_lock = validate_lock_phase5


def audit(root: Path = ROOT):
    report = base.audit(root=root)
    errors = [item for item in report["errors"] if item.get("code") != "AOS-HANDOFF-PHASE"]

    handoff_path = root / "docs/agent-system/context/REPOSITORY_HANDOFF.md"
    if handoff_path.is_file():
        handoff = handoff_path.read_text(encoding="utf-8")
        if "PHASE_5_ACTIVE" not in handoff or "GOVERNANCE_SYNC_ACTIVE" not in handoff:
            errors.append(base.error("AOS-HANDOFF-PHASE", "handoff does not declare Phase 5 governance synchronization active", str(handoff_path.relative_to(root))))

    steward_path = root / ".github/agents/aios-tools-knowledge-steward.agent.md"
    if steward_path.is_file():
        steward = steward_path.read_text(encoding="utf-8")
        if ".github/skills/sync-governance/SKILL.md" not in steward:
            errors.append(base.error("AOS-ROLE-SKILL-BINDING", "Knowledge Steward does not bind to sync-governance", str(steward_path.relative_to(root))))

    report["repository_autonomy_phase"] = 5
    report["result"] = "PASS" if not errors else "FAIL"
    report["errors"] = errors
    report["schema"] = "AIOS_TOOLS_ORGANIZATION_AUDIT_PHASE5_01"
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="outputs/agent-system-audit.json")
    args = parser.parse_args()
    report = audit()
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
