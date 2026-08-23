from __future__ import annotations

from datetime import datetime, timedelta, timezone
import inspect
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from aios_tools.browser.auth import SessionValidator
from aios_tools.browser.secret_store import InMemorySyntheticProtectedSessionStore
from aios_tools.browser.session import AuthCapabilityManifest, SessionDescriptor, identity_fingerprint


ROOT = Path(__file__).resolve().parents[1]
AUTH_POLICY = ROOT / "policies" / "browser-auth-policy.v0.1.json"
RECEIPT_SCHEMA = ROOT / "contracts" / "browser-auth-receipt.v0.1.schema.json"
REF_SCHEMA = ROOT / "contracts" / "browser-session-ref.v0.1.schema.json"
FIXTURE_SECRET = "SYNTHETIC_COOKIE=fixture-secret-never-output"


def _descriptor() -> SessionDescriptor:
    now = datetime(2026, 8, 23, 13, 0, tzinfo=timezone.utc)
    return SessionDescriptor.verified(
        origin="https://example.invalid",
        identity_context_fingerprint=identity_fingerprint("synthetic-user@example.invalid"),
        created_at=now,
        verified_at=now,
        expires_at=now + timedelta(hours=1),
        backend_kind=InMemorySyntheticProtectedSessionStore.BACKEND_KIND,
        capabilities=AuthCapabilityManifest(cookies=True, local_storage=True, indexed_db=True),
    )


def test_02c_a_policy_is_fail_closed_for_real_auth_state():
    policy = json.loads(AUTH_POLICY.read_text(encoding="utf-8"))
    assert policy["policy_version"] == "browser-auth-policy/0.1-candidate"
    assert policy["session_reuse_enabled"] is False
    assert policy["real_auth_state_capture_enabled"] is False
    assert policy["authority_transfer"] is False
    assert policy["protected_store"]["plaintext_fallback"] is False
    assert policy["protected_store"]["admitted_production_backends"] == []
    assert policy["protected_store"]["synthetic_backend_test_only"] is True
    assert policy["validation"]["exact_origin_required"] is True
    assert policy["validation"]["identity_context_fingerprint_required"] is True
    assert policy["validation"]["expiry_required"] is True
    assert policy["validation"]["exclusive_lease_required"] is True
    assert policy["capabilities"]["virtual_webauthn_real_user_persistence"] == "block"


def test_opaque_session_ref_matches_contract():
    descriptor = _descriptor()
    schema = json.loads(REF_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(descriptor.session_ref.value)


def test_public_auth_receipt_matches_secret_free_contract():
    descriptor = _descriptor()
    receipt = descriptor.public_receipt()
    schema = json.loads(RECEIPT_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(receipt)
    rendered = json.dumps(receipt, sort_keys=True)
    assert descriptor.session_ref.value not in rendered
    assert descriptor.identity_context_fingerprint not in rendered
    assert FIXTURE_SECRET not in rendered


def test_session_restore_api_accepts_no_raw_storage_or_profile_path():
    parameters = inspect.signature(SessionValidator.validate_for_restore).parameters
    forbidden = {
        "storage_state",
        "storage_state_path",
        "cookie",
        "cookies",
        "token",
        "password",
        "mfa_code",
        "user_data_dir",
        "profile_path",
        "cdp_endpoint",
    }
    assert forbidden.isdisjoint(parameters)


def test_fixture_secret_does_not_escape_into_runtime_policy_contract_or_plan_files():
    protected_roots = [
        ROOT / "src" / "aios_tools" / "browser",
        ROOT / "policies",
        ROOT / "contracts",
        ROOT / "docs" / "plans",
    ]
    leaks = []
    for root in protected_roots:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".json", ".md"}:
                if FIXTURE_SECRET in path.read_text(encoding="utf-8"):
                    leaks.append(str(path.relative_to(ROOT)))
    assert leaks == []
