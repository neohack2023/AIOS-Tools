from pathlib import Path
import importlib.util
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ci_exact_head_audit.py"
spec = importlib.util.spec_from_file_location("ci_exact_head_audit", MODULE_PATH)
audit = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(audit)

GOOD = """name: T
on:
  pull_request:
jobs:
  x:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout exact candidate
        uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          ref: ${{ github.event.pull_request.head.sha || github.sha }}
          persist-credentials: false
      - name: Verify checkout identity
        shell: bash
        run: |
          set -euo pipefail
          expected="${{ github.event.pull_request.head.sha || github.sha }}"
          actual="$(git rev-parse HEAD)"
          test "$actual" = "$expected"
      - name: Tests
        run: echo ok
"""


class ExactHeadPolicyTests(unittest.TestCase):
    def codes(self, text, path=".github/workflows/example.yml"):
        return {item["code"] for item in audit.validate_workflow_text(path, text)}

    def test_good_workflow_passes(self):
        self.assertEqual(audit.validate_workflow_text(".github/workflows/example.yml", GOOD), [])

    def test_semantically_valid_quoted_trigger_is_not_reimplemented(self):
        quoted = GOOD.replace("  pull_request:\n", '  "pull_request":\n')
        self.assertEqual(audit.validate_workflow_text(".github/workflows/example.yml", quoted), [])

    def test_paths_filter_must_include_workflow_exactly(self):
        path = ".github/workflows/example.yml"
        bad = GOOD.replace("  pull_request:\n", "  pull_request:\n    paths:\n      - src/**\n")
        self.assertIn("AOS-CI-SELF-TRIGGER", self.codes(bad, path))
        good = bad.replace("      - src/**\n", f"      - src/**\n      - {path}\n")
        self.assertEqual(audit.validate_workflow_text(path, good), [])

    def test_paths_ignore_is_forbidden(self):
        bad = GOOD.replace("  pull_request:\n", "  pull_request:\n    paths-ignore:\n      - docs/**\n")
        self.assertIn("AOS-CI-SELF-TRIGGER", self.codes(bad))

    def test_negative_paths_are_forbidden(self):
        path = ".github/workflows/example.yml"
        bad = GOOD.replace(
            "  pull_request:\n",
            f"  pull_request:\n    paths:\n      - {path}\n      - '!{path}'\n",
        )
        self.assertIn("AOS-CI-SELF-TRIGGER", self.codes(bad, path))

    def test_container_is_forbidden(self):
        bad = GOOD.replace("    runs-on: ubuntu-latest\n", "    runs-on: ubuntu-latest\n    container: ubuntu:24.04\n")
        self.assertIn("AOS-CI-EXECUTION-CONTEXT", self.codes(bad))

    def test_container_env_bypass_is_forbidden_with_container(self):
        bad = GOOD.replace(
            "    runs-on: ubuntu-latest\n",
            "    runs-on: ubuntu-latest\n    container:\n      image: ubuntu:24.04\n      env:\n        BASH_ENV: /tmp/preload\n",
        )
        self.assertIn("AOS-CI-EXECUTION-CONTEXT", self.codes(bad))

    def test_identity_sensitive_workflow_env_is_forbidden(self):
        bad = GOOD.replace("jobs:\n", "env:\n  GIT_DIR: /tmp/fake\njobs:\n")
        self.assertIn("AOS-CI-IDENTITY-ENV", self.codes(bad))

    def test_identity_sensitive_job_env_is_forbidden(self):
        bad = GOOD.replace("    runs-on: ubuntu-latest\n", "    runs-on: ubuntu-latest\n    env:\n      PATH: /tmp/fake\n")
        self.assertIn("AOS-CI-IDENTITY-ENV", self.codes(bad))

    def test_checkout_must_be_full_sha_pinned(self):
        bad = GOOD.replace("actions/checkout@11d5960a326750d5838078e36cf38b85af677262", "actions/checkout@v4")
        self.assertIn("AOS-CI-CHECKOUT-PIN", self.codes(bad))

    def test_checkout_must_bind_directly_to_candidate(self):
        bad = GOOD.replace("${{ github.event.pull_request.head.sha || github.sha }}", "${{ github.sha }}", 1)
        self.assertIn("AOS-CI-CHECKOUT-REF", self.codes(bad))

    def test_checkout_inputs_are_closed(self):
        bad = GOOD.replace("          persist-credentials: false\n", "          persist-credentials: false\n          path: other\n")
        self.assertIn("AOS-CI-CHECKOUT-SHAPE", self.codes(bad))

    def test_identity_step_cannot_be_conditional(self):
        bad = GOOD.replace("        shell: bash\n", "        if: false\n        shell: bash\n", 1)
        self.assertIn("AOS-CI-IDENTITY-CONDITION", self.codes(bad))

    def test_identity_step_cannot_continue_on_error(self):
        bad = GOOD.replace("        shell: bash\n", "        continue-on-error: true\n        shell: bash\n", 1)
        self.assertIn("AOS-CI-IDENTITY-CONDITION", self.codes(bad))

    def test_job_cannot_continue_on_error(self):
        bad = GOOD.replace("    runs-on: ubuntu-latest\n", "    runs-on: ubuntu-latest\n    continue-on-error: true\n")
        self.assertIn("AOS-CI-CONTINUE-ON-ERROR", self.codes(bad))

    def test_identity_body_is_closed(self):
        bad = GOOD.replace('          test "$actual" = "$expected"\n', '          actual="$expected"\n          test "$actual" = "$expected"\n')
        self.assertIn("AOS-CI-IDENTITY-VERIFY", self.codes(bad))

    def test_identity_must_run_in_workspace(self):
        bad = GOOD.replace("        shell: bash\n", "        shell: bash\n        working-directory: subdir\n", 1)
        self.assertIn("AOS-CI-IDENTITY-DIRECTORY", self.codes(bad))


if __name__ == "__main__":
    unittest.main()
