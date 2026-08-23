from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import socket
from typing import Callable
from urllib.parse import urlsplit

Resolver = Callable[..., list[tuple]]


class OriginValidationError(ValueError):
    """Raised when a browser target or network destination is not admitted."""


@dataclass(frozen=True, slots=True)
class NormalizedOrigin:
    scheme: str
    host: str
    port: int

    @classmethod
    def parse(cls, raw: str, *, schemes: frozenset[str] = frozenset({"http", "https"})) -> "NormalizedOrigin":
        if not isinstance(raw, str) or not raw.strip():
            raise OriginValidationError("browser target must be a non-empty URL")
        parsed = urlsplit(raw)
        scheme = parsed.scheme.lower()
        if scheme not in schemes:
            raise OriginValidationError("browser origin scheme is not admitted")
        if parsed.username is not None or parsed.password is not None:
            raise OriginValidationError("userinfo is forbidden in browser targets")
        if not parsed.hostname:
            raise OriginValidationError("browser target requires a hostname")
        try:
            host = parsed.hostname.encode("idna").decode("ascii").rstrip(".").lower()
            port = parsed.port or (443 if scheme == "https" else 80)
        except (UnicodeError, ValueError) as exc:
            raise OriginValidationError("browser target host or port is invalid") from exc
        if not host or "%" in host or not (1 <= port <= 65535):
            raise OriginValidationError("browser target host or port is invalid")
        return cls(scheme, host, port)

    def serialize(self) -> str:
        default = 443 if self.scheme == "https" else 80
        return f"{self.scheme}://{self.host}" + ("" if self.port == default else f":{self.port}")

    def websocket_tuple(self) -> tuple[str, str, int]:
        return ("wss" if self.scheme == "https" else "ws", self.host, self.port)


def _resolve_addresses(origin: NormalizedOrigin, resolver: Resolver = socket.getaddrinfo) -> set[ipaddress._BaseAddress]:
    try:
        return {ipaddress.ip_address(origin.host)}
    except ValueError:
        try:
            infos = resolver(origin.host, origin.port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise OriginValidationError("browser target DNS resolution failed") from exc
        addresses: set[ipaddress._BaseAddress] = set()
        for info in infos:
            sockaddr = info[4]
            if not sockaddr:
                continue
            try:
                addresses.add(ipaddress.ip_address(sockaddr[0]))
            except ValueError:
                continue
        if not addresses:
            raise OriginValidationError("browser target resolved to no usable addresses")
        return addresses


def assert_public_origin(origin: NormalizedOrigin, resolver: Resolver = socket.getaddrinfo) -> tuple[str, ...]:
    addresses = _resolve_addresses(origin, resolver)
    if any(not address.is_global for address in addresses):
        raise OriginValidationError("browser target resolved outside the admitted public network")
    return tuple(sorted(str(address) for address in addresses))


def same_http_origin(raw_url: str, allowed: NormalizedOrigin) -> bool:
    try:
        return NormalizedOrigin.parse(raw_url) == allowed
    except OriginValidationError:
        return False


def same_websocket_origin(raw_url: str, allowed: NormalizedOrigin) -> bool:
    parsed = urlsplit(raw_url)
    if parsed.scheme not in {"ws", "wss"} or parsed.username is not None or parsed.password is not None or not parsed.hostname:
        return False
    try:
        host = parsed.hostname.encode("idna").decode("ascii").rstrip(".").lower()
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
    except (UnicodeError, ValueError):
        return False
    return (parsed.scheme, host, port) == allowed.websocket_tuple()
