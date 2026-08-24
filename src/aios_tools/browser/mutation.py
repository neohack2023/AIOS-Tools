from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import os
from pathlib import Path
import json
import re
import sqlite3
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .origin import NormalizedOrigin, OriginValidationError


_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_COMPACT_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


class MutationPolicyError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class MutationStateUnknown(MutationPolicyError):
    def __init__(self, message: str = "remote mutation state is unknown") -> None:
        super().__init__("MUTATION_STATE_UNKNOWN", message)


def canonical_http_url(raw: str) -> str:
    if not isinstance(raw, str) or not raw:
        raise MutationPolicyError("MUTATION_TARGET_INVALID", "mutation target must be a non-empty URL")
    parts = urlsplit(raw)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password or parts.fragment:
        raise MutationPolicyError("MUTATION_TARGET_INVALID", "mutation target URL is invalid")
    try:
        origin = NormalizedOrigin.parse(raw).serialize()
    except OriginValidationError as exc:
        raise MutationPolicyError("MUTATION_TARGET_INVALID", "mutation target origin is invalid") from exc
    origin_parts = urlsplit(origin)
    path = parts.path or "/"
    return urlunsplit((origin_parts.scheme, origin_parts.netloc, path, parts.query, ""))


def _fingerprint(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()



def mutation_contract_fingerprint(value: Any) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MutationPolicyError("MUTATION_INPUT_INVALID", "mutation contract is not JSON serializable") from exc
    return "sha256:" + hashlib.sha256(encoded).hexdigest()

def _parse_expiry(value: Any, *, now: datetime) -> datetime:
    if not isinstance(value, str):
        raise MutationPolicyError("APPROVAL_INVALID", "remote mutation approval requires expires_at")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MutationPolicyError("APPROVAL_INVALID", "remote mutation approval expiry is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MutationPolicyError("APPROVAL_INVALID", "remote mutation approval expiry must be timezone-aware")
    parsed = parsed.astimezone(timezone.utc)
    if parsed <= now:
        raise MutationPolicyError("APPROVAL_EXPIRED", "remote mutation approval has expired")
    if (parsed - now).total_seconds() > 900:
        raise MutationPolicyError("APPROVAL_INVALID", "remote mutation approval may not exceed a 15 minute horizon")
    return parsed


@dataclass(slots=True)
class MutationGrant:
    request_id: str
    tool: str
    scope: str
    effect_class: str
    target_url: str
    method: str
    idempotency_key: str
    approval_id: str
    approved_by: str
    expires_at: datetime
    rollback_fingerprint: str | None = None
    _consumed: bool = False

    def consume(self, *, target_url: str, method: str, idempotency_key: str, now: datetime | None = None) -> None:
        now_value = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if self._consumed:
            raise MutationPolicyError("MUTATION_PERMIT_CONSUMED", "remote mutation approval is one-shot")
        if now_value >= self.expires_at:
            raise MutationPolicyError("APPROVAL_EXPIRED", "remote mutation approval expired before use")
        canonical = canonical_http_url(target_url)
        if not hmac.compare_digest(canonical, self.target_url):
            raise MutationPolicyError("APPROVAL_TARGET_MISMATCH", "approval does not cover the requested target")
        normalized_method = str(method).upper()
        if normalized_method != self.method:
            raise MutationPolicyError("APPROVAL_METHOD_MISMATCH", "approval does not cover the requested method")
        if not hmac.compare_digest(str(idempotency_key), self.idempotency_key):
            raise MutationPolicyError("APPROVAL_IDEMPOTENCY_MISMATCH", "approval does not cover the idempotency key")
        self._consumed = True

    def public_receipt(self) -> dict[str, object]:
        return {
            "approval_id_fingerprint": _fingerprint(self.approval_id),
            "approved_by_fingerprint": _fingerprint(self.approved_by),
            "target_url_fingerprint": _fingerprint(self.target_url),
            "method": self.method,
            "effect_class": self.effect_class,
            "idempotency_key_fingerprint": _fingerprint(self.idempotency_key),
            "expires_at": self.expires_at.isoformat(),
            "rollback_fingerprint": self.rollback_fingerprint,
            "one_shot": True,
            "authority_transfer": False,
        }


def build_mutation_grant(
    *,
    request_id: str,
    tool: str,
    scope: str,
    effect_class: str,
    payload: dict[str, Any],
    authority_context: dict[str, Any],
    now: datetime | None = None,
) -> MutationGrant:
    if effect_class not in {"REMOTE_MUTATION_REVERSIBLE", "REMOTE_MUTATION_HIGH_IMPACT"}:
        raise MutationPolicyError("EFFECT_CLASS_BLOCKED", "tool is not a remote mutation capability")
    if not isinstance(payload, dict):
        raise MutationPolicyError("MUTATION_INPUT_INVALID", "remote mutation payload must be an object")
    target_raw = payload.get("mutation_url", payload.get("url"))
    method = str(payload.get("method", "")).upper()
    key = payload.get("idempotency_key")
    if method not in _MUTATING_METHODS:
        raise MutationPolicyError("MUTATION_METHOD_BLOCKED", "remote mutation method is not admitted")
    if not isinstance(key, str) or not _COMPACT_ID_RE.fullmatch(key):
        raise MutationPolicyError("MUTATION_IDEMPOTENCY_REQUIRED", "remote mutation requires a compact idempotency key")
    target = canonical_http_url(target_raw)

    approval = authority_context.get("approval")
    if not isinstance(approval, dict) or approval.get("approved") is not True:
        raise MutationPolicyError("APPROVAL_REQUIRED", "remote mutation requires explicit approval")
    exact_fields = {
        "tool": tool,
        "scope": scope,
        "effect_class": effect_class,
        "target_url": target,
        "method": method,
        "idempotency_key": key,
    }
    for field, expected in exact_fields.items():
        if approval.get(field) != expected:
            raise MutationPolicyError("APPROVAL_SCOPE_MISMATCH", f"remote mutation approval {field} does not match")
    approval_id = approval.get("approval_id")
    approved_by = approval.get("approved_by")
    if not isinstance(approval_id, str) or not _COMPACT_ID_RE.fullmatch(approval_id):
        raise MutationPolicyError("APPROVAL_INVALID", "remote mutation approval requires approval_id")
    if not isinstance(approved_by, str) or not approved_by.strip():
        raise MutationPolicyError("APPROVAL_INVALID", "remote mutation approval requires approved_by")
    if approval.get("one_shot") is not True:
        raise MutationPolicyError("APPROVAL_INVALID", "remote mutation approval must be one-shot")
    if effect_class == "REMOTE_MUTATION_HIGH_IMPACT" and approval.get("high_impact_ack") is not True:
        raise MutationPolicyError("APPROVAL_REQUIRED", "high-impact remote mutation requires explicit acknowledgement")
    rollback_fingerprint = None
    if effect_class == "REMOTE_MUTATION_REVERSIBLE":
        rollback = payload.get("rollback")
        if not isinstance(rollback, dict):
            raise MutationPolicyError("ROLLBACK_REQUIRED", "reversible mutation requires rollback contract")
        rollback_fingerprint = mutation_contract_fingerprint(rollback)
        if approval.get("rollback_fingerprint") != rollback_fingerprint:
            raise MutationPolicyError("APPROVAL_SCOPE_MISMATCH", "approval does not cover the rollback contract")
    now_value = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    expiry = _parse_expiry(approval.get("expires_at"), now=now_value)
    return MutationGrant(
        request_id=request_id,
        tool=tool,
        scope=scope,
        effect_class=effect_class,
        target_url=target,
        method=method,
        idempotency_key=key,
        approval_id=approval_id,
        approved_by=approved_by,
        expires_at=expiry,
        rollback_fingerprint=rollback_fingerprint,
    )


class MutationLedger:
    """Durable duplicate-prevention ledger. It stores no request body or secret."""

    def __init__(self, path: Path | str) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            parent = Path(self.path).expanduser().resolve().parent
            parent.mkdir(parents=True, exist_ok=True)
            self.path = str(Path(self.path).expanduser().resolve())
        self._initialize()

    @classmethod
    def default(cls) -> "MutationLedger":
        root = os.environ.get("AIOS_RUNTIME_STATE_DIR")
        if root:
            base = Path(root).expanduser()
        else:
            base = Path.home() / ".aios-tools" / "runtime"
        return cls(base / "browser-mutations.sqlite3")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS browser_mutations (
                    idempotency_key TEXT PRIMARY KEY,
                    target_fingerprint TEXT NOT NULL,
                    method TEXT NOT NULL,
                    approval_fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def reserve(self, grant: MutationGrant, *, now: datetime | None = None) -> None:
        now_value = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO browser_mutations
                    (idempotency_key, target_fingerprint, method, approval_fingerprint, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'STARTED', ?, ?)
                    """,
                    (
                        grant.idempotency_key,
                        _fingerprint(grant.target_url),
                        grant.method,
                        _fingerprint(grant.approval_id),
                        now_value,
                        now_value,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise MutationPolicyError(
                "MUTATION_DUPLICATE_BLOCKED",
                "idempotency key has already been reserved; blind retry is blocked",
            ) from exc

    def mark(self, idempotency_key: str, status: str, *, now: datetime | None = None) -> None:
        if status not in {"SUCCEEDED", "FAILED_NO_EFFECT", "MUTATION_STATE_UNKNOWN", "ROLLED_BACK", "ROLLBACK_FAILED"}:
            raise ValueError("invalid mutation ledger status")
        now_value = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE browser_mutations SET status = ?, updated_at = ? WHERE idempotency_key = ?",
                (status, now_value, idempotency_key),
            )
            if cursor.rowcount != 1:
                raise MutationPolicyError("MUTATION_LEDGER_MISSING", "mutation reservation is unavailable")

    def status(self, idempotency_key: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM browser_mutations WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
        return None if row is None else str(row[0])
