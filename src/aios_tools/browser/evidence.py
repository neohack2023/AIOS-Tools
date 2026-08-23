from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from time import time
from urllib.parse import urlsplit

from .origin import NormalizedOrigin


def _digest(value: str) -> str:
    return "sha256:" + sha256(value.encode("utf-8")).hexdigest()


def minimize_url(raw_url: str) -> dict[str, str]:
    origin = NormalizedOrigin.parse(raw_url).serialize()
    path = urlsplit(raw_url).path or "/"
    return {"origin": origin, "path_digest": _digest(path)}


@dataclass(slots=True)
class BrowserEvidence:
    target_origin: str
    context_id: str
    network: list[dict] = field(default_factory=list)
    console: list[dict] = field(default_factory=list)
    page_errors: list[dict] = field(default_factory=list)
    blocked: list[dict] = field(default_factory=list)
    trace_digest: str | None = None
    cancelled: bool = False

    def request(self, *, method: str, url: str, resource_type: str, allowed: NormalizedOrigin) -> None:
        origin = NormalizedOrigin.parse(url)
        self.network.append({
            "event": "request",
            "method": method,
            "origin": origin.serialize(),
            "path_digest": _digest(urlsplit(url).path or "/"),
            "resource_type": resource_type,
            "same_origin": origin == allowed,
            "at": time(),
        })

    def response(self, *, url: str, status: int) -> None:
        try:
            origin = NormalizedOrigin.parse(url).serialize()
            path = urlsplit(url).path or "/"
        except Exception:
            return
        self.network.append({"event": "response", "origin": origin, "path_digest": _digest(path), "status": int(status), "at": time()})

    def block(self, *, channel: str, url: str, reason: str) -> None:
        self.blocked.append({"channel": channel, "url_digest": _digest(url), "reason": reason, "at": time()})

    def console_event(self, kind: str, text: str) -> None:
        self.console.append({"type": kind, "text_digest": _digest(text), "at": time()})

    def page_error(self, text: str) -> None:
        self.page_errors.append({"text_digest": _digest(text), "at": time()})

    def finalize_trace(self, path: Path) -> None:
        if path.exists() and path.is_file():
            digest = sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            self.trace_digest = "sha256:" + digest.hexdigest()

    def to_dict(self) -> dict:
        return {
            "target_origin": self.target_origin,
            "context_id": self.context_id,
            "network": list(self.network),
            "console": list(self.console),
            "page_errors": list(self.page_errors),
            "blocked": list(self.blocked),
            "trace_digest": self.trace_digest,
            "cancelled": self.cancelled,
        }
