"""Dependency-free deterministic PNG export for Cartography scenes."""
from __future__ import annotations

import struct
import zlib
from typing import Any


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _set_pixel(buf: bytearray, width: int, height: int, x: int, y: int, color: tuple[int, int, int, int]) -> None:
    if 0 <= x < width and 0 <= y < height:
        offset = (y * width + x) * 4
        buf[offset:offset + 4] = bytes(color)


def _line(buf: bytearray, width: int, height: int, x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int, int]) -> None:
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        _set_pixel(buf, width, height, x0, y0, color)
        if x0 == x1 and y0 == y1:
            break
        twice = 2 * err
        if twice >= dy:
            err += dy
            x0 += sx
        if twice <= dx:
            err += dx
            y0 += sy


def _rect(buf: bytearray, width: int, height: int, x: int, y: int, w: int, h: int,
          fill: tuple[int, int, int, int], stroke: tuple[int, int, int, int]) -> None:
    for yy in range(max(0, y), min(height, y + h)):
        start = (yy * width + max(0, x)) * 4
        end = (yy * width + min(width, x + w)) * 4
        if end > start:
            buf[start:end] = bytes(fill) * ((end - start) // 4)
    _line(buf, width, height, x, y, x + w - 1, y, stroke)
    _line(buf, width, height, x, y + h - 1, x + w - 1, y + h - 1, stroke)
    _line(buf, width, height, x, y, x, y + h - 1, stroke)
    _line(buf, width, height, x + w - 1, y, x + w - 1, y + h - 1, stroke)


def render_png(scene: dict[str, Any], *, scale: int = 1) -> bytes:
    """Rasterize a scene into deterministic RGBA PNG bytes.

    This export intentionally renders graph geometry and authority accents only.
    The standalone SVG and WebGPU viewer carry full searchable text labels.
    """
    if scale < 1 or scale > 4:
        raise ValueError("scale must be between 1 and 4")
    width = int(scene["width"]) * scale
    height = int(scene["height"]) * scale
    background = (7, 16, 24, 255)
    pixels = bytearray(bytes(background) * width * height)

    for edge in scene.get("edges", []):
        points = edge.get("points", [])
        for first, second in zip(points, points[1:]):
            _line(
                pixels, width, height,
                int(first[0]) * scale, int(first[1]) * scale,
                int(second[0]) * scale, int(second[1]) * scale,
                (101, 123, 145, 255),
            )
    for node in scene.get("nodes", []):
        rgb = tuple(int(value) for value in node["accent_rgb"])
        _rect(
            pixels, width, height,
            int(node["x"]) * scale, int(node["y"]) * scale,
            int(node["width"]) * scale, int(node["height"]) * scale,
            (13, 26, 37, 255),
            (rgb[0], rgb[1], rgb[2], 255),
        )
        accent_width = 6 * scale
        _rect(
            pixels, width, height,
            int(node["x"]) * scale, int(node["y"]) * scale,
            accent_width, int(node["height"]) * scale,
            (rgb[0], rgb[1], rgb[2], 255),
            (rgb[0], rgb[1], rgb[2], 255),
        )

    raw = bytearray()
    stride = width * 4
    for row in range(height):
        raw.append(0)
        raw.extend(pixels[row * stride:(row + 1) * stride])
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    metadata = f'snapshot={scene["source_snapshot_digest"]};view={scene["view_id"]}'.encode("utf-8")
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"tEXt", b"AIOS\x00" + metadata) + _chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + _chunk(b"IEND", b"")
