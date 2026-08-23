import socket

import pytest

from aios_tools.browser.origin import NormalizedOrigin, OriginValidationError, assert_public_origin, same_websocket_origin


def _resolver_for(address: str):
    def resolver(host, port, *, type):
        assert type == socket.SOCK_STREAM
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        sockaddr = (address, port, 0, 0) if family == socket.AF_INET6 else (address, port)
        return [(family, socket.SOCK_STREAM, 6, "", sockaddr)]
    return resolver


def test_origin_normalizes_default_port_and_host():
    origin = NormalizedOrigin.parse("https://Example.COM:443/path?q=secret")
    assert origin.serialize() == "https://example.com"


def test_origin_serializes_ipv6_with_brackets():
    origin = NormalizedOrigin.parse("https://[2606:4700:4700::1111]/path")
    assert origin.serialize() == "https://[2606:4700:4700::1111]"


@pytest.mark.parametrize("url", [
    "file:///tmp/x",
    "javascript:alert(1)",
    "https://user:pass@example.com/",
    "https:///",
    "https://example.com:99999/",
    "https://[not-an-ipv6]/",
])
def test_origin_rejects_unsafe_forms(url):
    with pytest.raises(OriginValidationError):
        NormalizedOrigin.parse(url)


def test_public_network_guard_rejects_private_dns_resolution():
    origin = NormalizedOrigin.parse("https://example.test")
    with pytest.raises(OriginValidationError):
        assert_public_origin(origin, _resolver_for("10.20.30.40"))


def test_public_network_guard_accepts_global_resolution():
    origin = NormalizedOrigin.parse("https://example.test")
    assert assert_public_origin(origin, _resolver_for("8.8.8.8")) == ("8.8.8.8",)


def test_websocket_origin_mapping_is_exact():
    origin = NormalizedOrigin.parse("https://example.com")
    assert same_websocket_origin("wss://example.com/socket", origin)
    assert not same_websocket_origin("ws://example.com/socket", origin)
    assert not same_websocket_origin("wss://cdn.example.com/socket", origin)
