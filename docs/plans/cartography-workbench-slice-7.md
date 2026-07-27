# Cartography Slice 7 — Unified Workbench shell and real GPU proof

## Governing contract

- Notion: `AIOS_SYSTEM_CARTOGRAPHY_ENGINE_CONTRACT.md`
- Scope: `global-working-memory`
- Repository authority: executable implementation only

## Purpose

Replace disconnected HTML, SVG, PNG, and JSON artifacts as the primary interaction surface with one locally served React and TypeScript application. Keep exports as outputs of the application rather than separate products.

## Included

- `apps/cartography-web/`
- one Vite-served application URL
- Mind Map, Lineage, and Outline views in one shell
- search, breadcrumbs, outline navigator, and inspector
- URL-backed active view, root, depth, selected node, filters, and snapshot
- worker-based layout router
- deterministic tidy-tree handling for single-child chains
- deterministic radial layout for real branches
- deterministic lineage lanes
- Three.js WebGPU node and edge geometry
- explicit WebGL2 fallback
- visible backend and runtime-state indicators
- loading, stale, partial, fallback, context-loss, and error states
- mobile portrait focus mode
- mobile landscape inspection mode
- unit, interaction, and screenshot regression tests

## Non-goals

- hosted deployment
- connector credentials in the browser
- source writes
- automatic drift reconciliation
- full AIOS system-graph coverage
- collaboration or CRDT state
- Active promotion

## Validation

```bash
cd apps/cartography-web
npm install
npm run test
npm run build
npx playwright install --with-deps chromium
npm run test:e2e
```

Repository Python validation remains unchanged and must continue to pass.

## Risks

- WebGPU availability differs by browser and secure-context support.
- The browser test environment may exercise WebGL2 fallback rather than WebGPU.
- Screenshot baselines are tied to the pinned browser package and viewport.
- The bundled source-backed fixture is partial and stale by design; it is not a live connector refresh.

## Rollback

Remove `apps/cartography-web/` and the dedicated web CI job. Existing Python Cartography exports and renderer contracts remain untouched.
