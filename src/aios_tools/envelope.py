from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ToolError:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionReceipt:
    request_id: str
    tool: str
    tool_version: str
    scope: str
    mode: str
    status: str
    started_at: str
    completed_at: str
    output: dict[str, Any] = field(default_factory=dict)
    errors: list[ToolError] = field(default_factory=list)
    provenance: list[dict[str, Any]] = field(default_factory=list)
    external_effects: list[dict[str, Any]] = field(default_factory=list)
    authority_transfer: bool = False
    receipt_id: str = field(default_factory=lambda: f"receipt-{uuid4()}")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["errors"] = [asdict(error) for error in self.errors]
        return value
