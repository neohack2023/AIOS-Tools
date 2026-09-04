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

    def test_identity_step_continue_on_error_true_fails(self):
        bad = GOOD.replace(
            "        shell: bash\n        run: |\n",
            "        shell: bash\n        continue-on-error: true\n        run: |\n",
        )
        codes = {item["code"] for item in audit.validate_workflow_text("x.yml", bad)}
        self.assertIn("AOS-CI-CONTINUE-ON-ERROR", codes)

    def test_job_continue_on_error_true_fails(self):
        bad = GOOD.replace(
            "    runs-on: ubuntu-latest\n",
            "    runs-on: ubuntu-latest\n    continue-on-error: true\n",
        )
        codes = {item["code"] for item in audit.validate_workflow_text("x.yml", bad)}
        self.assertIn("AOS-CI-CONTINUE-ON-ERROR", codes)

    def test_continue_on_error_expression_fails_closed(self):
        bad = GOOD.replace(
            "    runs-on: ubuntu-latest\n",
            "    runs-on: ubuntu-latest\n    continue-on-error: ${{ matrix.experimental }}\n",
        )
        codes = {item["code"] for item in audit.validate_workflow_text("x.yml", bad)}
        self.assertIn("AOS-CI-CONTINUE-ON-ERROR", codes)

    def test_literal_continue_on_error_false_is_allowed(self):
        good = GOOD.replace(
            "        shell: bash\n        run: |\n",
            "        shell: bash\n        continue-on-error: false\n        run: |\n",
        )
        self.assertEqual(audit.validate_workflow_text("x.yml", good), [])

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


class ExactHeadAdversarialTests(unittest.TestCase):
    def assert_rejected(self, text):
        self.assertTrue(audit.validate_workflow_text('x.yml', text))

    def test_complete_body_mutations(self):
        mutations = [
            ('          test ', '          actual="$expected"\n          test '),
            ('          set -euo pipefail\n', ''),
            ('          test ', '          set +e\n          test '),
            ('          test ', '          exit 0\n          test '),
            ('          actual=', '          expected="spoof"\n          actual='),
            ('        run: |', '        run: >'),
            ('        shell: bash', '        shell: sh'),
            ('        shell: bash', '        shell: bash {0} || true'),
            ('        shell: bash\n', ''),
            ('          set -euo pipefail', '          : <<\'HIDDEN\'\n          set -euo pipefail'),
        ]
        for old, new in mutations:
            with self.subTest(new=new):
                self.assert_rejected(GOOD.replace(old, new))
        self.assert_rejected(GOOD + '          echo success\n')
        self.assert_rejected(GOOD.replace(
            '          actual="$(git rev-parse HEAD)"\n          test "$actual" = "$expected"',
            '          test "$actual" = "$expected"\n          actual="$(git rev-parse HEAD)"'))

    def test_verifier_controls(self):
        for control in ['if: false', '"if": false', "'if': ${{ false }}",
                        'if: always()', 'env: {BASH_ENV: spoof.sh}',
                        'working-directory: other', 'timeout-minutes: 0']:
            with self.subTest(control=control):
                self.assert_rejected(GOOD.replace('        shell: bash',
                                                      f'        {control}\n        shell: bash'))

    def test_structural_bypasses(self):
        cases = [
            GOOD.replace('      - name: Verify', '      - if: false\n        name: Verify'),
            GOOD.replace('      - name: Verify', '      - run: echo intervening\n      - name: Verify'),
            GOOD.replace('      - name: Verify', '  other:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Verify'),
            GOOD.replace('        shell: bash', '        "continue-on-error": true\n        shell: bash'),
            GOOD.replace('    runs-on:', '    "continue-on-error": true\n    runs-on:'),
            GOOD.replace('        shell: bash', '        shell: sh\n        shell: bash'),
            GOOD.replace('        shell: bash', '        env: &shared {}\n        shell: bash'),
            GOOD.replace('        shell: bash', '        <<: {if: false}\n        shell: bash'),
            GOOD.replace('          persist-credentials:', '          repository: elsewhere/repo\n          persist-credentials:'),
            GOOD.replace('          persist-credentials:', '          path: other\n          persist-credentials:'),
            GOOD.replace('        uses: actions/checkout', '        if: false\n        uses: actions/checkout'),
            GOOD.replace('    runs-on:', '    defaults:\n      run:\n        working-directory: other\n    runs-on:'),
            GOOD + '  unchecked:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo pass\n',
        ]
        for i, case in enumerate(cases):
            with self.subTest(case=i):
                self.assert_rejected(case)

    def test_inherited_shell_and_git_environment_is_rejected(self):
        for key in ["BASH_ENV", "PATH", "GIT_DIR", "GIT_WORK_TREE"]:
            for location in ["jobs:", "    runs-on: ubuntu-latest"]:
                indent = "" if location == "jobs:" else "    "
                bad = GOOD.replace(location, f"{indent}env:\n{indent}  {key}: spoof\n{location}")
                with self.subTest(key=key, location=location):
                    self.assert_rejected(bad)

    def test_powershell_complete_body(self):
        body = '\n'.join([
            f"$expected = '{audit.EXACT_CANDIDATE_EXPR}'",
            '$actual = git rev-parse HEAD',
            'if ($actual -ne $expected) { throw "Checkout mismatch: expected $expected, got $actual" }',
        ])
        self.assertTrue(audit._verification_enforces_compare('pwsh', body))
        for mutation in [body + '\nexit 0', body.replace('if (', '$actual = $expected\nif ('),
                         'try {\n' + body + '\n} catch {}', body.replace('throw', 'Write-Output')]:
            self.assertFalse(audit._verification_enforces_compare('pwsh', mutation))

    def test_real_bash_comparison_passes_only_for_checked_out_commit(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run(['git', 'init', '-q', directory], check=True)
            subprocess.run(['git', '-C', directory, '-c', 'user.name=Fixture',
                            '-c', 'user.email=fixture@example.invalid',
                            'commit', '-qm', 'fixture', '--allow-empty'], check=True)
            head = subprocess.check_output(['git', '-C', directory, 'rev-parse', 'HEAD'], text=True).strip()
            body = audit.yaml.load(GOOD, Loader=audit.WorkflowLoader)['jobs']['x']['steps'][1]['run']
            self.assertTrue(audit._verification_enforces_compare('bash', body))
            for expected, success in [(head, True), ('0' * 40, False)]:
                result = subprocess.run(['bash', '-c', body.replace(audit.EXACT_CANDIDATE_EXPR, expected)],
                                        cwd=directory, capture_output=True)
                self.assertEqual(result.returncode == 0, success)


if __name__ == "__main__":
    unittest.main()
