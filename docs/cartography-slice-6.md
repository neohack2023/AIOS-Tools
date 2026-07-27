# Cartography Slice 6 — Semantic mind-map projection

## Problem

The Slice 5 renderer produced a valid cross-source lineage and drift diagram, but its lane-and-row layout was not a mind map. On a mobile viewport it also left excessive whitespace and allowed long source labels to overflow.

## Implemented

- governed `AIOS System Mind Map` View Spec
- explicit central root selection
- deterministic radial-semantic layout
- stable branch ordering by label and node identity
- cubic Bézier relationship conduits
- relation-specific styling for hierarchy, scope, mirror, evidence, and implementation
- two- or three-line wrapped node labels
- mobile `contain` fit contract with safe padding
- interactive depth reduction in the WebGPU/Canvas viewer
- root emphasis without creating renderer-authored knowledge
- SVG and interactive HTML exports

## Preserved existing view

The lane-and-row renderer remains available for cross-source authority and drift inspection. This slice adds a second projection rather than changing Graph IR or replacing the lineage view.

## Safety boundary

- no source mutation
- no automatic reconciliation
- no fuzzy identity matching
- no random or force-directed layout
- no renderer-authored semantic nodes
- no capability activation or hosted deployment
