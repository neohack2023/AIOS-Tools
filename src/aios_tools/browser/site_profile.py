from __future__ import annotations

import asyncio
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

from .evidence import minimize_url
from .origin import NormalizedOrigin
from .runtime import inspect_async


ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "profiles" / "browser"
_PROFILE_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")


class BrowserSiteProfileError(RuntimeError):
    pass


def load_site_profile(profile_id: str) -> dict[str, Any]:
    if not isinstance(profile_id, str) or not _PROFILE_ID_RE.fullmatch(profile_id):
        raise BrowserSiteProfileError("invalid browser site profile id")
    path = PROFILE_ROOT / f"{profile_id}.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BrowserSiteProfileError("browser site profile is unavailable") from exc
    if not isinstance(value, dict) or value.get("profile_id") != profile_id:
        raise BrowserSiteProfileError("browser site profile identity is invalid")
    if value.get("authority_transfer") is not False:
        raise BrowserSiteProfileError("browser site profile may not transfer authority")
    return value


async def replay_site_profile_async(profile_id: str) -> dict[str, Any]:
    profile = load_site_profile(profile_id)
    if profile.get("mode") != "REPLAY" or profile.get("effect_class") != "READ_NETWORK":
        raise BrowserSiteProfileError("site profile is not admitted for read-only replay")
    entrypoint = profile.get("validation_entrypoint")
    if not isinstance(entrypoint, str):
        raise BrowserSiteProfileError("site profile validation entrypoint is missing")
    expected_origin = profile.get("origin")
    if not isinstance(expected_origin, str) or NormalizedOrigin.parse(entrypoint).serialize() != expected_origin:
        raise BrowserSiteProfileError("site profile validation origin is inconsistent")
    expected = minimize_url(entrypoint)
    result = await inspect_async({
        "url": entrypoint,
        "visible_text_chars": int(profile.get("validation_visible_text_chars", 4000)),
        "elapsed_seconds": int(profile.get("validation_elapsed_seconds", 60)),
    })
    path_match = result.get("final_path_digest") == expected["path_digest"]
    origin_match = result.get("final_origin") == expected_origin
    success = bool(
        result.get("terminal_status") == "SUCCEEDED"
        and result.get("semantic_success") is True
        and path_match
        and origin_match
    )
    visible = result.get("visible_text")
    marker = profile.get("optional_visible_marker")
    marker_observed = bool(isinstance(marker, str) and isinstance(visible, str) and marker in visible)
    return {
        "profile_id": profile_id,
        "profile_version": profile.get("version"),
        "terminal_status": "SUCCEEDED" if success else "PROFILE_STALE",
        "semantic_success": success,
        "target_origin": expected_origin,
        "entrypoint_fingerprint": "sha256:" + sha256(entrypoint.encode("utf-8")).hexdigest(),
        "final_path_digest_match": path_match,
        "final_origin_match": origin_match,
        "optional_marker_observed": marker_observed,
        "fresh_session": True,
        "underlying_terminal_status": result.get("terminal_status"),
        "authority_transfer": False,
        "evidence": result.get("evidence", {}),
        "budget_used": result.get("budget_used", {}),
    }


def run_site_profile_replay(payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != {"profile_id"}:
        raise ValueError("browser.profile.replay accepts only profile_id")
    profile_id = payload.get("profile_id")
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(replay_site_profile_async(profile_id))
    raise BrowserSiteProfileError("site profile sync bridge cannot run inside an active event loop")
