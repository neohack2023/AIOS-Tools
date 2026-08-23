import socket

import pytest

from aios_tools.browser.origin import NormalizedOrigin, OriginValidationError, assert_public_origin, same_websocket_origin


def _resolver_for(address: str):
    def resolver(host, port, *, type):
        assert type == socket.SOCK_STREAM
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]
    return resolver


def test_origin_normalizes_default_port_and_host():
    origin = NormalizedOrigin.parse("https://Example.COM:443/path?q=secret")
    assert origin.serialize() == "https://example.com"


@pytest.mark.parametrize("url", [
    "file:///tmp/x",
    "javascript:alert(1)",
    "https://user:pass@example.com/",
    "https:///",
    "https://example.com:99999/",
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
