# AIOS Cartography Workbench

One read-only React and TypeScript application for Cartography Mind Map, Lineage, and Outline views.

## Local URL

```bash
npm install
npm run dev
```

Open `http://localhost:5173/`.

Production preview:

```bash
npm run build
npm run preview
```

Open `http://localhost:4173/`.

## Governed system graph

The bundled Slice 8 snapshot expands the original shell proof into a bounded cross-source AIOS graph covering:

- governance
- registries
- project branches
- retrieval and context assembly
- workflows and routing
- STONE and MASON
- observability and runtime telemetry
- GitHub implementation state

Every rendered node carries an exact source-system object ID and source pointer. Notion objects use `AUTHORITATIVE`, Google Drive objects use `DRIVE_SHADOW`, and GitHub objects use `IMPLEMENTATION`.

Coverage gaps are retained in `coverage_report.unresolved`. They are never converted into placeholder graph nodes. Current explicit gaps are registry row-level expansion, live workflow execution instances, and live telemetry events.

## URL-backed state

The application preserves these fields in the query string:

- `view`
- `root`
- `depth`
- `selected`
- `filters`
- `snapshot`

Browser back, forward, reload, and copied URLs restore the workspace.

## Rendering boundary

- Three.js `WebGPURenderer` is attempted first.
- WebGL2 is the explicit fallback.
- Nodes and edges are GPU geometry.
- Labels and inspection controls remain accessible DOM overlays.
- Outline is an equivalent DOM projection.
- The browser contains no Notion or Drive credentials and exposes no source-write path.
- Slice 8 changes source coverage only; it does not rewrite the renderer or layout engine.

## Validation

```bash
npm run test
npm run build
npx playwright install --with-deps chromium
npm run test:e2e
```
