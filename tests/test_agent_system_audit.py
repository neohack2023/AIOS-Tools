from datetime import date
import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "agent_system_audit.py"
spec = importlib.util.spec_from_file_location("agent_system_audit", MODULE_PATH)
audit = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(audit)


class AgentSystemAuditTests(unittest.TestCase):
    def test_skill_requires_matching_name_and_description(self):
        text = "---\nname: wrong\ndescription:\n---\n"
        codes = {item["code"] for item in audit.validate_skill_text("review-pr", text)}
        self.assertIn("AOS-SKILL-NAME", codes)
        self.assertIn("AOS-SKILL-DESCRIPTION", codes)

    def test_skill_rejects_shell_preapproval(self):
        text = "---\nname: review-pr\ndescription: review\nallowed-tools: shell\n---\n"
        codes = {item["code"] for item in audit.validate_skill_text("review-pr", text)}
        self.assertIn("AOS-SKILL-SHELL-PREAPPROVAL", codes)

    def test_promoted_lesson_requires_target_and_evidence(self):
        fields = {
            "candidate_state": "CONFIRMED_CANDIDATE",
            "source_commit": "a" * 40,
            "source_paths_or_receipts": "example",
            "promotion_state": "PROMOTED",
            "promotion_target": "none",
            "promotion_evidence": "none",
        }
        codes = [item["code"] for item in audit.validate_lesson("LESSON-X", fields)]
        self.assertEqual(codes.count("AOS-LESSON-PROMOTION"), 2)

    def test_governance_lock_expires_fail_closed(self):
        lock = {
            "bundle_id": "X",
            "bundle_version": "0.4",
            "state": "STAGING_ACTIVE",
            "materialized_on": "2026-09-04",
            "valid_through": "2026-09-05",
            "normal_repo_work_external_fetch_required": "false",
            "upstream_authority_cutover": "false",
            "repository_autonomy_phase": "4",
            "native_adapter_state": "ACTIVE",
            "native_skill_state": "ACTIVE",
            "organization_audit_state": "ACTIVE",
            "sync_state": "NOT_INSTALLED_PHASE_5",
        }
        codes = {item["code"] for item in audit.validate_lock(lock, date(2026, 9, 6))}
        self.assertIn("AOS-LOCK-STALE", codes)


if __name__ == "__main__":
    unittest.main()
