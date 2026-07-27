# Cartography Slice 5: Deterministic Visual Renderer

## Governed pipeline

```text
live read-only adapters
→ validated Graph IR
→ exact identity bindings
→ deterministic drift results
→ compiled View Spec
→ deterministic render scene
→ SVG / PNG / interactive WebGPU map
```

## Implemented

- Stable lane-and-row layout with no random seed or source mutation.
- Scene JSON retaining snapshot ID, snapshot digest, View Spec ID, identity summary, and drift summary.
- Searchable standalone SVG with source pointers and drift-state attributes.
- Dependency-free deterministic PNG geometry export with embedded snapshot metadata.
- Self-contained interactive WebGPU viewer with Canvas2D overlay/fallback, pan, zoom, node inspection, SVG export, and PNG export.
- `aios-cartography-render` CLI for `scene`, `svg`, `png`, and `html` outputs.
- Source-backed proof using the merged Notion and Google Drive adapters, exact identity binding, and drift comparison.

## Safety boundary

The renderer consumes validated immutable snapshots and compiled View Specs. It has no connector credentials, network fetches, reconciliation path, source-write methods, or authority-promotion capability. Interaction changes camera state only.

## Determinism contract

For identical snapshot digest, compiled View Spec, identity resolution, drift report, renderer version, title, and scale:

- scene JSON is byte-stable after canonical serialization;
- SVG output is byte-stable;
- Python PNG output is byte-stable;
- WebGPU HTML payload is byte-stable.

The browser-exported PNG reflects the current interactive camera state and is therefore an explicit presentation export, not the canonical deterministic artifact.

## Excluded

- automatic source reconciliation;
- fuzzy identity matching;
- source mutation;
- physics or force-directed layout;
- renderer-authored knowledge;
- Active promotion;
- hosted deployment or credential binding.
