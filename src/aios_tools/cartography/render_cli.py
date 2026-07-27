"""Command-line export for validated Cartography snapshots and compiled views."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .png import render_png
from .render import compile_render_scene, render_svg
from .webgpu import render_webgpu_html


def main() -> None:
    parser = argparse.ArgumentParser(prog="aios-cartography-render")
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--view", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--format", choices=("svg", "png", "html", "scene"), required=True)
    parser.add_argument("--title", default="AIOS Cartography")
    parser.add_argument("--scale", type=int, default=1)
    args = parser.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    compiled_view = json.loads(args.view.read_text(encoding="utf-8"))
    scene = compile_render_scene(snapshot, compiled_view)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "svg":
        args.output.write_text(render_svg(scene, title=args.title), encoding="utf-8")
    elif args.format == "png":
        args.output.write_bytes(render_png(scene, scale=args.scale))
    elif args.format == "html":
        args.output.write_text(render_webgpu_html(scene, title=args.title), encoding="utf-8")
    else:
        args.output.write_text(json.dumps(scene, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
