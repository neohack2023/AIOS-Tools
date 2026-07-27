"""Read-only Google Drive source adapter for Cartography Slice 4."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .fixtures import adapt_drive_tree


class DriveReadClient(Protocol):
    """Minimal Drive read contract. No upload, update, move, or delete methods exist."""

    def get_metadata(self, file_id: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class DriveReadResult:
    records: tuple[dict[str, Any], ...]
    nodes: tuple[dict[str, Any], ...]
    edges: tuple[dict[str, Any], ...]
    unresolved_references: tuple[dict[str, Any], ...]
    source_trace: tuple[dict[str, str], ...]


class DriveAncestorChainAdapter:
    """Read a Drive object and explicit parent chain into Graph IR.

    The adapter follows only provider-declared parent IDs, preserves Drive as
    ``DRIVE_SHADOW``, never infers hierarchy, and fails closed on malformed
    records, multiple parents, cycles, or excessive depth.
    """

    adapter_id = "drive.ancestor_chain.read_only"
    adapter_version = "0.1.0"

    def __init__(self, client: DriveReadClient, *, max_depth: int = 32) -> None:
        if max_depth < 1:
            raise ValueError("max_depth must be positive")
        self._client = client
        self._max_depth = max_depth

    def read(self, file_id: str, scope_key: str) -> DriveReadResult:
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        current: str | None = file_id

        while current:
            if current in seen:
                raise ValueError(f"Drive ancestor cycle detected at {current}")
            if len(records) >= self._max_depth:
                raise ValueError("Drive ancestor chain exceeded max_depth")
            seen.add(current)

            raw = self._client.get_metadata(current)
            record = self._normalize(raw)
            if record["id"] != current:
                raise ValueError(f"Client returned Drive object {record['id']} for requested {current}")
            records.append(record)
            current = record.get("parent_id")

        nodes, edges, unresolved = adapt_drive_tree(records, scope_key)
        trace = tuple(
            {
                "source_object_id": record["id"],
                "source_pointer": record["url"],
                "adapter_id": self.adapter_id,
                "adapter_version": self.adapter_version,
            }
            for record in sorted(records, key=lambda item: item["id"])
        )
        return DriveReadResult(
            records=tuple(records),
            nodes=tuple(nodes),
            edges=tuple(edges),
            unresolved_references=tuple(unresolved),
            source_trace=trace,
        )

    @staticmethod
    def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
        object_id = raw.get("id")
        name = raw.get("name", raw.get("title"))
        url = raw.get("webViewLink", raw.get("url"))
        kind = raw.get("file_or_folder")
        mime_type = raw.get("mimeType", raw.get("mime_type", ""))
        if kind not in {"file", "folder"}:
            kind = "folder" if mime_type == "application/vnd.google-apps.folder" else "file"
        required = {"id": object_id, "name": name, "url": url}
        missing = [key for key, value in required.items() if not isinstance(value, str) or not value]
        if missing:
            raise ValueError(f"Malformed Drive metadata; missing {', '.join(missing)}")

        parent_ids = raw.get("parents", raw.get("parent_ids", [])) or []
        if not isinstance(parent_ids, list) or any(not isinstance(parent, str) or not parent for parent in parent_ids):
            raise ValueError("Drive parent IDs must be a list of non-empty strings")
        if len(parent_ids) > 1:
            raise ValueError("Drive object has multiple parents; bounded ancestor adapter refuses ambiguity")

        normalized: dict[str, Any] = {
            "id": object_id,
            "type": kind,
            "name": name,
            "url": url,
            "authority_role": "DRIVE_SHADOW",
            "coverage_state": "COMPLETE",
            "mime_type": mime_type,
            "modified_time": raw.get("modifiedTime", raw.get("modified_time")),
        }
        if parent_ids:
            normalized["parent_id"] = parent_ids[0]
        return normalized
