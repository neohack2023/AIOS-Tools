from __future__ import annotations

import pytest

from aios_tools.drive_scope_registry import ScopeRegistryError, resolve_scope_registry


def _entries():
    return [
        {
            "scope_key": "global-working-memory",
            "aliases": ["AI_MEMORY_OS", "AI Knowledge System"],
            "authority_state": "drive_authoritative",
            "source_system": "DRIVE",
            "registry_object_id": "drive:scope-registry:global-working-memory",
            "handoff_ref": "drive:handoff:global-working-memory",
            "packet_refs": [
                "drive:packet:runtime-rules",
                "drive:packet:scope-registry",
                "drive:packet:current-handoff",
                "drive:packet:task-001",
            ],
        },
        {
            "scope_key": "girls-of-gaming",
            "aliases": ["Girls of Gaming"],
            "authority_state": "drive_authoritative",
            "source_system": "DRIVE",
            "packet_refs": ["drive:packet:gog-current"],
        },
    ]


def test_exact_scope_returns_only_registered_scope_packet_refs() -> None:
    result = resolve_scope_registry(_entries(), "global-working-memory")

    assert result.canonical_scope == "global-working-memory"
    assert result.source_system == "DRIVE"
    assert result.packet_refs == (
        "drive:packet:runtime-rules",
        "drive:packet:scope-registry",
        "drive:packet:current-handoff",
        "drive:packet:task-001",
    )
    assert "drive:packet:gog-current" not in result.packet_refs


def test_declared_alias_resolves_without_semantic_guessing() -> None:
    result = resolve_scope_registry(_entries(), "AI_MEMORY_OS")
    assert result.canonical_scope == "global-working-memory"


def test_unknown_near_match_fails_closed_instead_of_selecting_sibling() -> None:
    with pytest.raises(ScopeRegistryError, match="scope not registered"):
        resolve_scope_registry(_entries(), "global memory")


def test_duplicate_alias_is_ambiguous_and_fails_closed() -> None:
    entries = _entries()
    entries[1]["aliases"].append("AI_MEMORY_OS")

    with pytest.raises(ScopeRegistryError, match="ambiguous scope registration"):
        resolve_scope_registry(entries, "AI_MEMORY_OS")


def test_drive_authority_conflict_is_rejected() -> None:
    entries = _entries()
    entries[0]["source_system"] = "NOTION"

    with pytest.raises(ScopeRegistryError, match="requires DRIVE source"):
        resolve_scope_registry(entries, "global-working-memory")


def test_unverified_or_unknown_authority_state_is_rejected() -> None:
    entries = _entries()
    entries[0]["authority_state"] = "drive_candidate"

    with pytest.raises(ScopeRegistryError, match="unsupported authority_state"):
        resolve_scope_registry(entries, "global-working-memory")


def test_packet_projection_is_bounded() -> None:
    result = resolve_scope_registry(_entries(), "global-working-memory", max_packet_refs=2)
    assert result.packet_refs == (
        "drive:packet:runtime-rules",
        "drive:packet:scope-registry",
    )


def test_invalid_write_like_fields_do_not_expand_capability_surface() -> None:
    # The resolver only interprets read-side registry fields. Mutation-looking
    # fields remain inert data and are not represented in its result contract.
    entries = _entries()
    entries[0]["write_capability"] = "drive.files.update"
    result = resolve_scope_registry(entries, "global-working-memory")

    assert not hasattr(result, "write_capability")
