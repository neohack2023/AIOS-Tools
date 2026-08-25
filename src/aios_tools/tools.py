from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .audio_native_demucs import NativeDemucsProfile, run_native_demucs
from .canonical import canonical_sha256


def system_health(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "service": "AIOS-Tools",
        "version": "0.1.0",
        "state": "BOOTSTRAP_OPERATIONAL",
        "default_mode": "READ_ONLY",
        "portable_repo_required": False,
        "authority_role": "EXECUTION_INFRASTRUCTURE",
    }


def hash_json(payload: dict[str, Any]) -> dict[str, Any]:
    if "value" not in payload:
        raise ValueError("input must contain 'value'")
    return {"algorithm": "sha256-canonical-json-v1", "digest": canonical_sha256(payload["value"])}


def validate_schema(payload: dict[str, Any]) -> dict[str, Any]:
    if "schema" not in payload or "instance" not in payload:
        raise ValueError("input must contain 'schema' and 'instance'")
    schema = payload["schema"]
    instance = payload["instance"]
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        return {
            "valid": False,
            "schema_valid": False,
            "errors": [{"validator": "schema", "path": list(exc.path), "schema_path": list(exc.schema_path), "message": exc.message}],
        }
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.absolute_path))
    return {
        "valid": not errors,
        "schema_valid": True,
        "draft": "2020-12",
        "errors": [
            {"validator": error.validator, "path": list(error.absolute_path), "schema_path": list(error.absolute_schema_path), "message": error.message}
            for error in errors
        ],
    }


def audio_demucs_separate(payload: dict[str, Any]) -> dict[str, Any]:
    required = {"source_path", "output_dir", "profile_path"}
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"input missing fields: {', '.join(missing)}")
    profile = NativeDemucsProfile.from_json(Path(str(payload["profile_path"])))
    result = run_native_demucs(profile, Path(str(payload["source_path"])), Path(str(payload["output_dir"])))
    return {**result, "workflow": "AUDIO_STEM_SECTION_ANALYSIS", "engine": "demucs", "profile_id": profile.profile_id, "evidence_class": "MODEL_ESTIMATE", "runtime_admission": False, "authority_transfer": False}


def browser_inspect(payload: dict[str, Any]) -> dict[str, Any]:
    from .browser.runtime import run_browser_inspect
    return run_browser_inspect(payload)


def browser_profile_replay(payload: dict[str, Any]) -> dict[str, Any]:
    from .browser.site_profile import run_site_profile_replay
    return run_site_profile_replay(payload)


def browser_session_open(payload: dict[str, Any]) -> dict[str, Any]:
    from .browser.interactive import run_interactive_open
    return run_interactive_open(payload)


def browser_session_observe(payload: dict[str, Any]) -> dict[str, Any]:
    from .browser.interactive import run_interactive_observe
    return run_interactive_observe(payload)


def browser_session_act(payload: dict[str, Any]) -> dict[str, Any]:
    from .browser.interactive import run_interactive_act
    return run_interactive_act(payload)


def browser_session_close(payload: dict[str, Any]) -> dict[str, Any]:
    from .browser.interactive import run_interactive_close
    return run_interactive_close(payload)


def _mutation_failure_truth(payload: dict[str, Any], operation: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    """Preserve durable unknown-state truth if an effect executor raises after mutation begins."""
    from .browser.mutation import MutationLedger
    from .browser.origin import NormalizedOrigin
    try:
        return operation(payload)
    except Exception:
        key = payload.get("idempotency_key")
        if not isinstance(key, str) or not key:
            raise
        ledger_status = MutationLedger.default().status(key)
        if ledger_status not in {"MUTATION_STATE_UNKNOWN", "ROLLBACK_FAILED"}:
            raise
        raw_target = payload.get("mutation_url", payload.get("url"))
        if not isinstance(raw_target, str):
            raise
        return {
            "terminal_status": ledger_status,
            "semantic_success": False,
            "target_origin": NormalizedOrigin.parse(raw_target).serialize(),
            "method": str(payload.get("method", "UNKNOWN")).upper(),
            "mutation_count": 2 if ledger_status == "ROLLBACK_FAILED" else 1,
            "durable_ledger_state": ledger_status,
            "executor_exception_sanitized": True,
            "authority_transfer": False,
        }


def browser_mutate_request(payload: dict[str, Any]) -> dict[str, Any]:
    from .browser.effects_runtime import run_mutation_request
    return _mutation_failure_truth(payload, run_mutation_request)


def browser_mutate_reversible(payload: dict[str, Any]) -> dict[str, Any]:
    from .browser.effects_runtime import run_mutation_reversible
    result = _mutation_failure_truth(payload, run_mutation_reversible)
    if result.get("rollback_attempted") is True:
        result.setdefault("mutation_count", 2)
    return result


def browser_upload_execute(payload: dict[str, Any]) -> dict[str, Any]:
    from .browser.effects_runtime import run_upload_execute
    return _mutation_failure_truth(payload, run_upload_execute)


def browser_session_capture(payload: dict[str, Any]) -> dict[str, Any]:
    from .browser.session_capture import run_session_capture
    return run_session_capture(payload)


def browser_download_promote(payload: dict[str, Any]) -> dict[str, Any]:
    from .browser.downloads import DownloadRecord
    from .browser.promotion import DownloadPromotionManager, DownloadPromotionRules
    from .browser.site_profile import load_site_profile
    if set(payload) != {"profile_id", "download"}:
        raise ValueError("browser.download.promote requires profile_id and download")
    profile_id = payload.get("profile_id")
    profile = load_site_profile(profile_id)
    rules = profile.get("download_rules")
    if not isinstance(rules, dict) or rules.get("auto_promote") is not True:
        raise ValueError("site profile does not admit automatic download promotion")
    raw = payload.get("download")
    if not isinstance(raw, dict):
        raise ValueError("download promotion receipt must be an object")
    required = {"state", "source_origin", "source_path_digest", "suggested_filename", "content_type", "declared_size", "observed_bytes", "sha256", "quarantine_name", "promoted", "mime_extension_mismatch", "reason"}
    if set(raw) != required:
        raise ValueError("download promotion receipt has unexpected fields")
    record = DownloadRecord(**raw)
    manager = DownloadPromotionManager.from_environment()
    receipt = manager.promote(record, DownloadPromotionRules(profile_id=profile_id, auto_promote=True, allowed_content_types=tuple(rules.get("allowed_content_types", ())), allowed_extensions=tuple(rules.get("allowed_extensions", ())), max_bytes=int(rules.get("max_bytes", 0))))
    return {"terminal_status": "SUCCEEDED", "semantic_success": True, "promotion": receipt.to_dict(), "authority_transfer": False}


def browser_runtime_status(payload: dict[str, Any]) -> dict[str, Any]:
    if payload:
        raise ValueError("browser.runtime.status accepts no input")
    import json
    from .browser.policy import load_browser_policy
    from .browser.secret_store import default_protected_session_store
    auth_path = Path(__file__).resolve().parents[2] / "policies" / "browser-auth-policy.v0.1.json"
    auth = json.loads(auth_path.read_text(encoding="utf-8"))
    browser_policy = load_browser_policy()
    health = default_protected_session_store().health()
    return {
        "capability_id": "cap:browser-control",
        "runtime_state": browser_policy["runtime_state"],
        "browser_policy_version": browser_policy["policy_version"],
        "auth_policy_version": auth.get("policy_version"),
        "session_reuse_enabled": auth.get("session_reuse_enabled") is True,
        "real_auth_state_capture_enabled": auth.get("real_auth_state_capture_enabled") is True,
        "production_user_takeover_enabled": auth.get("production_user_takeover_enabled") is True,
        "protected_store": {"backend_kind": health.backend_kind, "available": health.available, "protected": health.protected, "admitted": health.admitted, "synthetic": health.synthetic},
        "remote_mutation_tools_admitted": sorted(name for name, meta in browser_policy["admitted_tools"].items() if meta["effect_class"].startswith("REMOTE_MUTATION_")),
        "global_network_switch_changed": False,
        "authority_transfer": False,
    }


HANDLERS = {
    "system.health": system_health,
    "canonical.hash_json": hash_json,
    "schema.validate": validate_schema,
    "audio.demucs.separate": audio_demucs_separate,
    "browser.inspect": browser_inspect,
    "browser.profile.replay": browser_profile_replay,
    "browser.session.open": browser_session_open,
    "browser.session.observe": browser_session_observe,
    "browser.session.act": browser_session_act,
    "browser.session.close": browser_session_close,
    "browser.mutate.request": browser_mutate_request,
    "browser.mutate.reversible": browser_mutate_reversible,
    "browser.upload.execute": browser_upload_execute,
    "browser.session.capture": browser_session_capture,
    "browser.download.promote": browser_download_promote,
    "browser.runtime.status": browser_runtime_status,
}
