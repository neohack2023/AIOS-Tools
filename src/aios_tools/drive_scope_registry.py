"""Exact-scope, read-only Drive registry resolver.

This module is intentionally mechanical. It selects one registered scope by exact
scope key or declared alias, validates authority state, and returns the smallest
registered packet pointers without opening neighboring scopes.

It performs no Drive writes and exposes no mutation surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


_ALLOWED_AUTHORITY_STATES = {
    "drive_authoritative",
    "drive_verified_mirror",
    "notion_authoritative",
    "pending_migration",
}


@dataclass(frozen=True)
class ScopeRegistryResolution:
    requested_scope: str
    canonical_scope: str
    authority_state: str
    source_system: str
    packet_refs: tuple[str, ...]
    handoff_ref: str | None
    registry_object_id: str | None


class ScopeRegistryError(ValueError):
    """Raised when an exact, unambiguous governed scope cannot be resolved."""


def resolve_scope_registry(
    entries: Iterable[dict[str, Any]],
    requested_scope: str,
    *,
    max_packet_refs: int = 8,
) -> ScopeRegistryResolution:
    """Resolve one scope using exact scope/alias matching and fail-closed rules.

    Expected entry fields:
    - scope_key: canonical scope identity
    - aliases: optional list[str]
    - authority_state: governed authority state
    - source_system: e.g. DRIVE / NOTION
    - packet_refs: optional list[str], already-ranked smallest useful packets
    - handoff_ref: optional str
    - registry_object_id: optional str

    No semantic/fuzzy matching is performed.
    """

    if not isinstance(requested_scope, str) or not requested_scope.strip():
        raise ScopeRegistryError("requested_scope must be a non-empty string")
    if max_packet_refs < 1:
        raise ScopeRegistryError("max_packet_refs must be positive")

    normalized_request = requested_scope.strip()
    matches: list[dict[str, Any]] = []

    for raw in entries:
        if not isinstance(raw, dict):
            raise ScopeRegistryError("registry entries must be objects")

        scope_key = raw.get("scope_key")
        if not isinstance(scope_key, str) or not scope_key:
            raise ScopeRegistryError("registry entry missing non-empty scope_key")

        aliases = raw.get("aliases", []) or []
        if not isinstance(aliases, list) or any(not isinstance(alias, str) or not alias for alias in aliases):
            raise ScopeRegistryError(f"invalid aliases for scope {scope_key}")

        identities = {scope_key, *aliases}
        if normalized_request in identities:
            matches.append(raw)

    if not matches:
        raise ScopeRegistryError(f"scope not registered: {normalized_request}")
    if len(matches) > 1:
        raise ScopeRegistryError(f"ambiguous scope registration: {normalized_request}")

    entry = matches[0]
    scope_key = entry["scope_key"]
    authority_state = entry.get("authority_state")
    if authority_state not in _ALLOWED_AUTHORITY_STATES:
        raise ScopeRegistryError(f"unsupported authority_state for {scope_key}: {authority_state!r}")

    source_system = entry.get("source_system")
    if not isinstance(source_system, str) or not source_system:
        raise ScopeRegistryError(f"missing source_system for {scope_key}")

    if authority_state in {"drive_authoritative", "drive_verified_mirror"} and source_system.upper() != "DRIVE":
        raise ScopeRegistryError(
            f"authority/source conflict for {scope_key}: {authority_state} requires DRIVE source"
        )
    if authority_state == "notion_authoritative" and source_system.upper() != "NOTION":
        raise ScopeRegistryError(
            f"authority/source conflict for {scope_key}: notion_authoritative requires NOTION source"
        )

    packet_refs = entry.get("packet_refs", []) or []
    if not isinstance(packet_refs, list) or any(not isinstance(ref, str) or not ref for ref in packet_refs):
        raise ScopeRegistryError(f"invalid packet_refs for {scope_key}")

    handoff_ref = entry.get("handoff_ref")
    if handoff_ref is not None and (not isinstance(handoff_ref, str) or not handoff_ref):
        raise ScopeRegistryError(f"invalid handoff_ref for {scope_key}")

    registry_object_id = entry.get("registry_object_id")
    if registry_object_id is not None and (not isinstance(registry_object_id, str) or not registry_object_id):
        raise ScopeRegistryError(f"invalid registry_object_id for {scope_key}")

    return ScopeRegistryResolution(
        requested_scope=normalized_request,
        canonical_scope=scope_key,
        authority_state=authority_state,
        source_system=source_system.upper(),
        packet_refs=tuple(packet_refs[:max_packet_refs]),
        handoff_ref=handoff_ref,
        registry_object_id=registry_object_id,
    )
