from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/governance_sync.py"
spec = importlib.util.spec_from_file_location("governance_sync", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

SOURCES = [
    ("AIOS_TOOLS_EXECUTION_LAYER_CONTRACT", "3aa43bd4-ae4a-81f6-b295-d0a61bfdc70a"),
    ("AIOS_GITHUB_GOVERNED_EXECUTION_CONTRACT_v0.1", "3aa43bd4-ae4a-8125-a453-d4ecd5fad910"),
    ("VERIFIER_OWNED_ACCEPTANCE_01", "3cc43bd4-ae4a-811f-a48f-ebed755e58cc"),
]


class GovernanceSyncTests(unittest.TestCase):
    def build_repo(self, mutate=None):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        receipt_rel = "docs/agent-system/governance-sync/receipts/test.json"
        receipt_path = root / receipt_rel
        receipt_path.parent.mkdir(parents=True)
        receipt = {
            "schema": "AIOS_TOOLS_GOVERNANCE_SYNC_RECEIPT_01",
            "sync_id": "GSYNC-TEST-001",
            "repository": "neohack2023/AIOS-Tools",
            "performed_on": "2026-09-04",
            "source_set": [
                {
                    "source_id": sid,
                    "notion_page_id": pid,
                    "observed_last_edited_at": "2026-09-01T00:00:00Z",
                    "classification": "STABLE_TEST_AUTHORITY",
                }
                for sid, pid in SOURCES
            ],
            "delta_disposition": "MATERIAL_DELTA_PENDING",
            "freshness": {
                "previous_valid_through": "2026-10-04",
                "requested_valid_through": "2026-10-04",
                "renewal_applied": False,
                "reason": "MATERIAL_DELTA_PENDING",
            },
            "authority_boundary": {
                "normal_repo_work_external_fetch_required": False,
                "upstream_authority_cutover": False,
                "mutation_authority_granted_by_sync": False,
                "sync_role": "KNOWLEDGE_STEWARD",
            },
        }
        if mutate:
            mutate(receipt)
        raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
        receipt_path.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()

        lock_path = root / "docs/agent-system/context/governance-lock.yaml"
        lock_path.parent.mkdir(parents=True)
        lock_path.write_text(
            "\n".join(
                [
                    "repository_autonomy_phase: 5",
                    "sync_state: ACTIVE_PENDING_DELTA",
                    "sync_role: KNOWLEDGE_STEWARD",
                    "sync_freshness_days: 30",
                    "upstream_source_ids_csv: " + ",".join(s for s, _ in SOURCES),
                    f"last_sync_receipt: {receipt_rel}",
                    f"last_sync_receipt_sha256: {digest}",
                    "valid_through: 2026-10-04",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return tmp, root, lock_path

    def test_valid_pending_receipt_passes(self):
        tmp, root, _ = self.build_repo()
        try:
            report = module.validate_repository(root)
            self.assertEqual("PASS", report["result"])
            self.assertFalse(report["freshness_renewed"])
        finally:
            tmp.cleanup()

    def test_digest_mismatch_fails(self):
        tmp, root, lock_path = self.build_repo()
        try:
            text = lock_path.read_text(encoding="utf-8").replace("last_sync_receipt_sha256: ", "last_sync_receipt_sha256: deadbeef")
            lock_path.write_text(text, encoding="utf-8")
            report = module.validate_repository(root)
            self.assertEqual("FAIL", report["result"])
            self.assertIn("GSYNC-RECEIPT-DIGEST", {e["code"] for e in report["errors"]})
        finally:
            tmp.cleanup()

    def test_pending_delta_cannot_renew(self):
        def mutate(receipt):
            receipt["freshness"]["renewal_applied"] = True
        tmp, root, _ = self.build_repo(mutate)
        try:
            report = module.validate_repository(root)
            self.assertEqual("FAIL", report["result"])
            self.assertIn("GSYNC-PENDING-RENEWAL", {e["code"] for e in report["errors"]})
        finally:
            tmp.cleanup()

    def test_source_set_mismatch_fails(self):
        def mutate(receipt):
            receipt["source_set"] = receipt["source_set"][:-1]
        tmp, root, _ = self.build_repo(mutate)
        try:
            report = module.validate_repository(root)
            self.assertEqual("FAIL", report["result"])
            self.assertIn("GSYNC-SOURCE-SET", {e["code"] for e in report["errors"]})
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
