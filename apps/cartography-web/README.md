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

## Validation

```bash
npm run test
npm run build
npx playwright install --with-deps chromium
npm run test:e2e
```
