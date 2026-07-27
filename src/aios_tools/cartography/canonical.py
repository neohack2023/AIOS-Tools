"""Canonical Graph IR serialization and digest helpers."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from math import copysign, isfinite
from typing import Any
import json

from .graph_ir import GraphIRError, validate_graph_ir


def _unsupported_numbers(value: Any, pointer: str = "") -> list[GraphIRError]:
    errors: list[GraphIRError] = []
    if isinstance(value, float):
        if not isfinite(value) or (value == 0.0 and copysign(1.0, value) < 0):
            errors.append(GraphIRError(
                "UNSUPPORTED_CANONICAL_VALUE",
                "Canonical Graph IR rejects non-finite numbers and negative zero",
                pointer or "/",
            ))
    elif isinstance(value, dict):
        for key, child in value.items():
            errors.extend(_unsupported_numbers(child, f"{pointer}/{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_unsupported_numbers(child, f"{pointer}/{index}"))
    return errors


def canonical_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return a detached payload with canonical node and edge ordering."""
    payload = deepcopy(snapshot)
    payload["snapshot_digest"] = ""
    payload["nodes"] = sorted(payload.get("nodes", []), key=lambda item: item["node_id"])
    payload["edges"] = sorted(payload.get("edges", []), key=lambda item: item["edge_id"])
    return payload


def canonical_json(snapshot: dict[str, Any]) -> str:
    """Serialize a valid Graph IR snapshot deterministically without mutation."""
    errors = validate_graph_ir(snapshot) + _unsupported_numbers(snapshot)
    if errors:
        codes = ", ".join(sorted({error.code for error in errors}))
        raise ValueError(f"Graph IR is not canonicalizable: {codes}")
    return json.dumps(
        canonical_payload(snapshot),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def snapshot_digest(snapshot: dict[str, Any]) -> str:
    """Return the sha256-canonical-json-v1 digest for a Graph IR snapshot."""
    return sha256(canonical_json(snapshot).encode("utf-8")).hexdigest()
