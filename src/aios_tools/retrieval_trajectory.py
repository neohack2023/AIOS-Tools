from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .canonical import canonical_sha256

AUTHORITY_ROLES = {"AUTHORITATIVE", "DRIVE_SHADOW", "IMPLEMENTATION", "EVIDENCE", "UNRESOLVED"}
DISPOSITIONS = {"SELECTED", "REJECTED"}
FORBIDDEN_FIELDS = {"content", "text", "body", "prompt", "raw", "embedding", "vector", "secret", "credential"}


def _packet_id(source_system: str, source_ref: str) -> str:
    return f"rp_{canonical_sha256({'source_system': source_system, 'source_ref': source_ref})}"


def _trajectory_id(value: dict[str, Any]) -> str:
    payload = {key: item for key, item in value.items() if key != "trajectory_id"}
    return f"rt_{canonical_sha256(payload)}"


@dataclass
class RetrievalTrajectoryBuilder:
    scope_key: str
    query_ref: str
    candidates: list[dict[str, Any]] = field(default_factory=list)
    context_packet: dict[str, Any] | None = None

    def consider(
        self,
        *,
        source_system: str,
        source_ref: str,
        authority_role: str,
        rank: int,
        score: float | None = None,
    ) -> str:
        if authority_role not in AUTHORITY_ROLES:
            raise ValueError("unsupported authority role")
        if rank < 0:
            raise ValueError("rank must be non-negative")
        packet_id = _packet_id(source_system, source_ref)
        if any(item["packet_id"] == packet_id for item in self.candidates):
            raise ValueError("packet already considered")
        candidate = {
            "packet_id": packet_id,
            "source_system": source_system,
            "source_ref": source_ref,
            "authority_role": authority_role,
            "rank": rank,
            "score": score,
            "disposition": None,
            "reason_code": None,
        }
        self.candidates.append(candidate)
        return packet_id

    def decide(self, packet_id: str, *, disposition: str, reason_code: str) -> None:
        if disposition not in DISPOSITIONS:
            raise ValueError("unsupported packet disposition")
        if not reason_code:
            raise ValueError("packet decision requires a reason code")
        candidate = self._candidate(packet_id)
        if candidate["disposition"] is not None:
            raise ValueError("packet already has a terminal disposition")
        candidate["disposition"] = disposition
        candidate["reason_code"] = reason_code

    def compose(self, *, context_packet_id: str, packet_ids: list[str], token_count: int) -> None:
        if self.context_packet is not None:
            raise ValueError("context packet already composed")
        if token_count < 0:
            raise ValueError("token count must be non-negative")
        if len(packet_ids) != len(set(packet_ids)):
            raise ValueError("context packet contains duplicate packet IDs")
        for packet_id in packet_ids:
            candidate = self._candidate(packet_id)
            if candidate["disposition"] != "SELECTED":
                raise ValueError("context packet may contain only selected packets")
        self.context_packet = {
            "context_packet_id": context_packet_id,
            "packet_ids": list(packet_ids),
            "token_count": token_count,
        }

    def finalize(self) -> dict[str, Any]:
        if not self.candidates:
            raise ValueError("retrieval trajectory requires at least one candidate")
        undecided = [item["packet_id"] for item in self.candidates if item["disposition"] is None]
        if undecided:
            raise ValueError("all considered packets require a terminal disposition")
        selected = {item["packet_id"] for item in self.candidates if item["disposition"] == "SELECTED"}
        if selected and self.context_packet is None:
            raise ValueError("selected packets require a composed context packet")
        trajectory = {
            "trajectory_version": "0.1",
            "scope_key": self.scope_key,
            "query_ref": self.query_ref,
            "candidates": sorted(self.candidates, key=lambda item: (item["rank"], item["packet_id"])),
            "context_packet": self.context_packet,
            "events": self._events(),
            "external_effects": [],
            "authority_transfer": False,
        }
        validate_retrieval_trajectory(trajectory)
        trajectory["trajectory_id"] = _trajectory_id(trajectory)
        return trajectory

    def _candidate(self, packet_id: str) -> dict[str, Any]:
        for candidate in self.candidates:
            if candidate["packet_id"] == packet_id:
                return candidate
        raise ValueError("packet decision requires prior consideration")

    def _events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for candidate in sorted(self.candidates, key=lambda item: (item["rank"], item["packet_id"])):
            events.append({
                "event_type": "retrieval.packet_considered",
                "payload": {
                    "packet_id": candidate["packet_id"],
                    "source_system": candidate["source_system"],
                    "source_ref": candidate["source_ref"],
                    "authority_role": candidate["authority_role"],
                    "rank": candidate["rank"],
                    "score": candidate["score"],
                },
            })
            events.append({
                "event_type": "retrieval.packet_selected" if candidate["disposition"] == "SELECTED" else "retrieval.packet_rejected",
                "payload": {
                    "packet_id": candidate["packet_id"],
                    "reason_code": candidate["reason_code"],
                },
            })
        if self.context_packet is not None:
            events.append({
                "event_type": "context.packet_composed",
                "payload": dict(self.context_packet),
            })
        return events


def validate_retrieval_trajectory(trajectory: dict[str, Any]) -> None:
    if trajectory.get("external_effects"):
        raise ValueError("retrieval trajectory is read-only")
    if trajectory.get("authority_transfer") is not False:
        raise ValueError("retrieval trajectory cannot transfer authority")
    if any(key.lower() in FORBIDDEN_FIELDS for key in trajectory):
        raise ValueError("retrieval trajectory contains a forbidden content field")

    seen: set[str] = set()
    selected: set[str] = set()
    for candidate in trajectory.get("candidates", []):
        forbidden = FORBIDDEN_FIELDS.intersection(key.lower() for key in candidate)
        if forbidden:
            raise ValueError("retrieval candidate contains a forbidden content field")
        packet_id = candidate.get("packet_id")
        if packet_id in seen:
            raise ValueError("duplicate retrieval packet ID")
        seen.add(packet_id)
        if packet_id != _packet_id(candidate.get("source_system", ""), candidate.get("source_ref", "")):
            raise ValueError("retrieval packet ID does not match canonical source reference")
        if candidate.get("authority_role") not in AUTHORITY_ROLES:
            raise ValueError("unsupported authority role")
        if candidate.get("disposition") not in DISPOSITIONS:
            raise ValueError("candidate requires a terminal disposition")
        if not candidate.get("reason_code"):
            raise ValueError("candidate requires a reason code")
        if candidate["disposition"] == "SELECTED":
            selected.add(packet_id)

    context = trajectory.get("context_packet")
    if selected:
        if context is None:
            raise ValueError("selected packets require a context packet")
        referenced = set(context.get("packet_ids", []))
        if referenced != selected:
            raise ValueError("context packet must contain exactly the selected packets")
    elif context is not None and context.get("packet_ids"):
        raise ValueError("context packet references packets when none were selected")
