#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SKILLS = {"plan-feature", "review-pr", "verify-head", "harvest-lesson"}
ROLE_BINDINGS = {
    "aios-tools-coordinator.agent.md": "plan-feature",
    "aios-tools-reviewer.agent.md": "review-pr",
    "aios-tools-verifier.agent.md": "verify-head",
    "aios-tools-knowledge-steward.agent.md": "harvest-lesson",
}
EXPECTED_INSTRUCTIONS = {
    "browser.instructions.md",
    "benchmark.instructions.md",
    "audio-model.instructions.md",
    "cartography-web.instructions.md",
    "execution-core.instructions.md",
}
REQUIRED_AGENT_SYSTEM_PATHS = {
    "docs/agent-system/README.md",
    "docs/agent-system/context/REPOSITORY_HANDOFF.md",
    "docs/agent-system/context/governance-lock.yaml",
    "docs/agent-system/knowledge/KNOWLEDGE_INDEX.md",
    "docs/agent-system/adapters/AGENT_ADAPTER_MAP.md",
    "docs/agent-system/ROLE_AND_SKILL_PROFILE.md",
    "docs/agent-system/review/REVIEW_RULES.md",
    "docs/agent-system/lessons/README.md",
    "docs/agent-system/lessons/CANDIDATES.md",
    "docs/agent-system/audit/AUDIT_CONTRACT.md",
}
PROMOTION_STATES = {"NONE", "PROMOTED", "REJECTED"}
PRIVATE_URL_PATTERNS = (
    "https://app.notion.com/",
    "https://www.notion.so/",
    "https://drive.google.com/",
)


def read_text(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def parse_frontmatter(text: str) -> Dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out: Dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def parse_top_level_map(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for line in text.splitlines():
        if not line or line[0].isspace() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def error(code: str, message: str, path: str | None = None) -> Dict[str, str]:
    item = {"code": code, "message": message}
    if path:
        item["path"] = path
    return item


def validate_skill_text(name: str, text: str) -> List[Dict[str, str]]:
    errors: List[Dict[str, str]] = []
    fm = parse_frontmatter(text)
    if fm.get("name") != name:
        errors.append(error("AOS-SKILL-NAME", f"skill name must equal directory name {name!r}"))
    if not fm.get("description"):
        errors.append(error("AOS-SKILL-DESCRIPTION", "skill description is required"))
    allowed = fm.get("allowed-tools", "").lower()
    if "shell" in allowed or "bash" in allowed:
        errors.append(error("AOS-SKILL-SHELL-PREAPPROVAL", "shell/bash must not be pre-approved"))
    return errors


def validate_lock(lock: Dict[str, str], today: date) -> List[Dict[str, str]]:
    errors: List[Dict[str, str]] = []
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
    }
    missing = sorted(required - set(lock))
    if missing:
        errors.append(error("AOS-LOCK-MISSING", f"missing governance-lock fields: {', '.join(missing)}"))
        return errors
    if lock["repository_autonomy_phase"] != "4":
        errors.append(error("AOS-LOCK-PHASE", "repository_autonomy_phase must be 4"))
    if lock["organization_audit_state"] != "ACTIVE":
        errors.append(error("AOS-LOCK-AUDIT", "organization_audit_state must be ACTIVE"))
    if lock["normal_repo_work_external_fetch_required"].lower() != "false":
        errors.append(error("AOS-LOCK-LOCAL-FIRST", "normal repo work must remain external-fetch-free"))
    if lock["upstream_authority_cutover"].lower() != "false":
        errors.append(error("AOS-LOCK-AUTHORITY", "Phase 4 must not cut upstream authority over to GitHub"))
    try:
        expiry = date.fromisoformat(lock["valid_through"])
    except ValueError:
        errors.append(error("AOS-LOCK-DATE", "valid_through must be an ISO date"))
    else:
        if today > expiry:
            errors.append(error("AOS-LOCK-STALE", f"governance bundle expired on {expiry.isoformat()}"))
    return errors


def parse_lesson_blocks(text: str) -> List[Tuple[str, Dict[str, str]]]:
    blocks: List[Tuple[str, Dict[str, str]]] = []
    matches = list(re.finditer(r"^## (LESSON-[^\n]+)$", text, flags=re.MULTILINE))
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        fields: Dict[str, str] = {}
        for line in text[start:end].splitlines():
            m = re.match(r"^- ([a-z0-9_]+):\s*(.+?)\s*$", line.strip())
            if not m:
                continue
            value = m.group(2).strip()
            if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
                value = value[1:-1]
            fields[m.group(1)] = value
        blocks.append((match.group(1).strip(), fields))
    return blocks


def validate_lesson(name: str, fields: Dict[str, str]) -> List[Dict[str, str]]:
    errors: List[Dict[str, str]] = []
    for key in ("candidate_state", "source_commit", "source_paths_or_receipts", "promotion_state"):
        if not fields.get(key):
            errors.append(error("AOS-LESSON-MISSING", f"{name} missing {key}"))
    source_commit = fields.get("source_commit", "")
    if source_commit and not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        errors.append(error("AOS-LESSON-SOURCE", f"{name} source_commit must be a full 40-character SHA"))
    state = fields.get("promotion_state")
    if state and state not in PROMOTION_STATES:
        errors.append(error("AOS-LESSON-STATE", f"{name} has invalid promotion_state {state!r}"))
    if state == "PROMOTED":
        if fields.get("promotion_target", "none").lower() == "none":
            errors.append(error("AOS-LESSON-PROMOTION", f"{name} is PROMOTED without promotion_target"))
        if fields.get("promotion_evidence", "none").lower() == "none":
            errors.append(error("AOS-LESSON-PROMOTION", f"{name} is PROMOTED without promotion_evidence"))
    return errors


def git_head(root: Path) -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    except Exception:
        return None


def audit(root: Path = ROOT, today: date | None = None) -> Dict[str, object]:
    today = today or date.today()
    errors: List[Dict[str, str]] = []

    for rel in sorted(REQUIRED_AGENT_SYSTEM_PATHS):
        path = root / rel
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(error("AOS-REQUIRED-PATH", "required agent-system surface missing or empty", rel))

    skills_root = root / ".github/skills"
    actual_skills = {p.name for p in skills_root.iterdir() if p.is_dir()} if skills_root.is_dir() else set()
    if actual_skills != EXPECTED_SKILLS:
        errors.append(error("AOS-SKILL-CATALOG", f"expected {sorted(EXPECTED_SKILLS)}, found {sorted(actual_skills)}", ".github/skills"))
    for skill in sorted(EXPECTED_SKILLS & actual_skills):
        rel = f".github/skills/{skill}/SKILL.md"
        path = root / rel
        if not path.is_file():
            errors.append(error("AOS-SKILL-FILE", "missing SKILL.md", rel))
            continue
        for item in validate_skill_text(skill, path.read_text(encoding="utf-8")):
            item["path"] = rel
            errors.append(item)

    for agent_file, skill in ROLE_BINDINGS.items():
        rel = f".github/agents/{agent_file}"
        path = root / rel
        if not path.is_file():
            errors.append(error("AOS-ROLE-MISSING", "required role profile missing", rel))
            continue
        if f".github/skills/{skill}/SKILL.md" not in path.read_text(encoding="utf-8"):
            errors.append(error("AOS-ROLE-SKILL-BINDING", f"role does not bind to {skill}", rel))

    instructions_root = root / ".github/instructions"
    actual_instructions = {p.name for p in instructions_root.glob("*.instructions.md")}
    missing_instructions = sorted(EXPECTED_INSTRUCTIONS - actual_instructions)
    if missing_instructions:
        errors.append(error("AOS-INSTRUCTION-CATALOG", f"missing instruction packets: {', '.join(missing_instructions)}", ".github/instructions"))
    for name in sorted(EXPECTED_INSTRUCTIONS & actual_instructions):
        rel = f".github/instructions/{name}"
        fm = parse_frontmatter(read_text(root, rel))
        if not fm.get("applyTo"):
            errors.append(error("AOS-INSTRUCTION-APPLYTO", "path instruction requires applyTo frontmatter", rel))

    lock_path = "docs/agent-system/context/governance-lock.yaml"
    if (root / lock_path).is_file():
        for item in validate_lock(parse_top_level_map(read_text(root, lock_path)), today):
            item["path"] = lock_path
            errors.append(item)

    lessons_path = "docs/agent-system/lessons/CANDIDATES.md"
    if (root / lessons_path).is_file():
        blocks = parse_lesson_blocks(read_text(root, lessons_path))
        if not blocks:
            errors.append(error("AOS-LESSON-CATALOG", "candidate lesson lane contains no parseable lessons", lessons_path))
        for name, fields in blocks:
            for item in validate_lesson(name, fields):
                item["path"] = lessons_path
                errors.append(item)

    handoff_path = "docs/agent-system/context/REPOSITORY_HANDOFF.md"
    if (root / handoff_path).is_file():
        handoff = read_text(root, handoff_path)
        if "PHASE_4_ACTIVE" not in handoff or "organization audit" not in handoff.lower():
            errors.append(error("AOS-HANDOFF-PHASE", "handoff does not declare Phase 4 organization audit active", handoff_path))

    scan_paths = [root / "AGENTS.md", root / ".github/copilot-instructions.md"]
    scan_paths += list((root / "docs/agent-system").rglob("*.md")) if (root / "docs/agent-system").is_dir() else []
    scan_paths += list((root / ".github/agents").glob("*.md")) if (root / ".github/agents").is_dir() else []
    scan_paths += list((root / ".github/instructions").glob("*.md")) if (root / ".github/instructions").is_dir() else []
    scan_paths += list((root / ".github/skills").rglob("*.md")) if (root / ".github/skills").is_dir() else []
    for path in scan_paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in PRIVATE_URL_PATTERNS:
            if pattern in text:
                errors.append(error("AOS-PUBLIC-LEAKAGE", f"public repository agent surface contains private-workspace URL pattern {pattern}", str(path.relative_to(root))))

    expected_sha = os.environ.get("AIOS_AUDIT_CANDIDATE_SHA", "").strip()
    observed_sha = git_head(root)
    if expected_sha:
        if not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
            errors.append(error("AOS-AUDIT-IDENTITY", "AIOS_AUDIT_CANDIDATE_SHA must be a full SHA"))
        elif observed_sha and observed_sha != expected_sha:
            errors.append(error("AOS-AUDIT-IDENTITY", f"checked-out HEAD {observed_sha} does not match expected candidate {expected_sha}"))

    return {
        "schema": "AIOS_TOOLS_ORGANIZATION_AUDIT_01",
        "repository_autonomy_phase": 4,
        "candidate_sha": expected_sha or observed_sha,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "PASS" if not errors else "FAIL",
        "errors": errors,
    }


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
