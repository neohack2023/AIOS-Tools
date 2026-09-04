from pathlib import Path
import importlib.util
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ci_exact_head_audit.py"
spec = importlib.util.spec_from_file_location("ci_exact_head_audit", MODULE_PATH)
audit = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(audit)

GOOD = """name: T\non:\n  pull_request:\njobs:\n  x:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Checkout exact candidate\n        uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262\n        with:\n          ref: ${{ github.event.pull_request.head.sha || github.sha }}\n          persist-credentials: false\n      - name: Verify checkout identity\n        shell: bash\n        run: |\n          set -euo pipefail\n          expected=\"${{ github.event.pull_request.head.sha || github.sha }}\"\n          actual=\"$(git rev-parse HEAD)\"\n          test \"$actual\" = \"$expected\"\n"""


class ExactHeadAuditTests(unittest.TestCase):
    def test_good_workflow_passes(self):
        self.assertEqual(audit.validate_workflow_text("x.yml", GOOD), [])

    def test_bare_checkout_tag_fails(self):
        bad = GOOD.replace("actions/checkout@11d5960a326750d5838078e36cf38b85af677262", "actions/checkout@v4")
        codes = {item["code"] for item in audit.validate_workflow_text("x.yml", bad)}
        self.assertIn("AOS-CI-CHECKOUT-PIN", codes)

    def test_merge_ref_fails(self):
        bad = GOOD.replace("${{ github.event.pull_request.head.sha || github.sha }}", "${{ github.sha }}", 1)
        codes = {item["code"] for item in audit.validate_workflow_text("x.yml", bad)}
        self.assertIn("AOS-CI-CHECKOUT-REF", codes)

    def test_nested_block_scalar_cannot_impersonate_direct_with_ref(self):
        bad = GOOD.replace(
            "        with:\n          ref: ${{ github.event.pull_request.head.sha || github.sha }}\n          persist-credentials: false\n",
            "        run: |\n          echo 'with:'\n          echo '  ref: ${{ github.event.pull_request.head.sha || github.sha }}'\n          echo '  persist-credentials: false'\n",
        )
        codes = {item["code"] for item in audit.validate_workflow_text("x.yml", bad)}
        self.assertIn("AOS-CI-CHECKOUT-REF", codes)

    def test_missing_identity_step_fails(self):
        bad = GOOD.replace("Verify checkout identity", "Run tests")
        codes = {item["code"] for item in audit.validate_workflow_text("x.yml", bad)}
        self.assertIn("AOS-CI-IDENTITY-VERIFY", codes)

    def test_identity_step_must_enforce_exact_comparison(self):
        bad = GOOD.replace(
            '          test "$actual" = "$expected"\n',
            '          echo "$actual $expected"\n',
        )
        codes = {item["code"] for item in audit.validate_workflow_text("x.yml", bad)}
        self.assertIn("AOS-CI-IDENTITY-VERIFY", codes)

    def test_suppressed_comparison_fails(self):
        bad = GOOD.replace(
            '          test "$actual" = "$expected"\n',
            '          test "$actual" = "$expected" || true\n',
        )
        codes = {item["code"] for item in audit.validate_workflow_text("x.yml", bad)}
        self.assertIn("AOS-CI-IDENTITY-VERIFY", codes)

    def test_candidate_env_shadow_is_forbidden(self):
        bad = GOOD.replace(
            "    runs-on: ubuntu-latest\n",
            "    runs-on: ubuntu-latest\n    env:\n      AIOS_CANDIDATE_SHA: ${{ github.sha }}\n",
        )
        codes = {item["code"] for item in audit.validate_workflow_text("x.yml", bad)}
        self.assertIn("AOS-CI-CANDIDATE-SHADOW", codes)

    def test_flow_style_pull_request_trigger_fails_closed(self):
        bad = GOOD.replace("on:\n  pull_request:\n", "on: [pull_request]\n")
        codes = {item["code"] for item in audit.validate_workflow_text("x.yml", bad)}
        self.assertIn("AOS-CI-TRIGGER-SYNTAX", codes)

    def test_quoted_pull_request_trigger_fails_closed(self):
        bad = GOOD.replace("  pull_request:\n", '  "pull_request":\n')
        codes = {item["code"] for item in audit.validate_workflow_text("x.yml", bad)}
        self.assertIn("AOS-CI-TRIGGER-SYNTAX", codes)

    def test_path_filtered_workflow_must_trigger_on_itself(self):
        path = ".github/workflows/example.yml"
        bad = GOOD.replace("  pull_request:\n", "  pull_request:\n    paths:\n      - src/**\n")
        codes = {item["code"] for item in audit.validate_workflow_text(path, bad)}
        self.assertIn("AOS-CI-SELF-TRIGGER", codes)
        good = bad.replace("      - src/**\n", f"      - src/**\n      - {path}\n")
        self.assertEqual(audit.validate_workflow_text(path, good), [])


if __name__ == "__main__":
    unittest.main()
