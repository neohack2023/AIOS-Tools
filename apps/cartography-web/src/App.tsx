import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react';
import { SOURCE_BACKED_FIXTURE } from './data/sourceBackedFixture';
import { GpuGraph } from './renderers/GpuGraph';
import { useUrlWorkspaceState } from './state/urlState';
import type {
  GraphNode,
  GraphSnapshot,
  LayoutResult,
  RendererBackend,
  RuntimeState,
  ViewMode,
} from './types';

interface RuntimeNotice {
  state: RuntimeState;
  detail?: string;
}

interface LayoutWorkerResponse {
  ok: boolean;
  result?: LayoutResult;
  request_id?: string;
  error?: string;
}

const AUTHORITY_FILTERS = ['AUTHORITATIVE', 'DRIVE_SHADOW'];
const VIEW_LABELS: Record<ViewMode, string> = {
  mindmap: 'Mind Map',
  lineage: 'Lineage',
  outline: 'Outline',
};

function getBreadcrumbs(snapshot: GraphSnapshot, nodeId: string): GraphNode[] {
  const byId = new Map(snapshot.nodes.map((node) => [node.node_id, node]));
  const path: GraphNode[] = [];
  const seen = new Set<string>();
  let current = byId.get(nodeId);
  while (current && !seen.has(current.node_id)) {
    path.unshift(current);
    seen.add(current.node_id);
    current = current.parent_node_id ? byId.get(current.parent_node_id) : undefined;
  }
  return path;
}

function StatusRail({
  backend,
  notice,
  snapshot,
}: {
  backend: RendererBackend;
  notice: RuntimeNotice;
  snapshot: GraphSnapshot;
}) {
  const notices = [
    { label: backend.toUpperCase(), tone: backend === 'webgpu' ? 'healthy' : backend === 'webgl2' ? 'warning' : 'neutral' },
    { label: notice.state.replace('-', ' ').toUpperCase(), tone: notice.state === 'error' || notice.state === 'context-lost' ? 'danger' : notice.state === 'fallback' ? 'warning' : 'healthy' },
    { label: snapshot.freshness_state, tone: snapshot.freshness_state === 'STALE' ? 'warning' : 'healthy' },
    { label: snapshot.coverage_state, tone: snapshot.coverage_state === 'PARTIAL' ? 'warning' : 'healthy' },
  ];
  return (
    <div className="status-rail" aria-label="Workbench status">
      {notices.map((item) => (
        <span className={`status-chip status-${item.tone}`} key={item.label}>{item.label}</span>
      ))}
      {notice.detail ? <span className="status-detail" title={notice.detail}>{notice.detail}</span> : null}
    </div>
  );
}

function Breadcrumbs({ nodes, onSelect }: { nodes: GraphNode[]; onSelect: (id: string) => void }) {
  return (
    <nav className="breadcrumbs" aria-label="Graph path">
      {nodes.map((node, index) => (
        <span key={node.node_id}>
          {index ? <span aria-hidden="true">/</span> : null}
          <button type="button" onClick={() => onSelect(node.node_id)}>{node.label}</button>
        </span>
      ))}
    </nav>
  );
}

function OutlineTree({
  snapshot,
  selectedId,
  onSelect,
  compact = false,
}: {
  snapshot: GraphSnapshot;
  selectedId: string;
  onSelect: (id: string) => void;
  compact?: boolean;
}) {
  const children = useMemo(() => {
    const map = new Map<string | null, GraphNode[]>();
    for (const node of snapshot.nodes) {
      const parent = node.parent_node_id ?? null;
      const list = map.get(parent) ?? [];
      list.push(node);
      map.set(parent, list);
    }
    for (const list of map.values()) list.sort((a, b) => a.label.localeCompare(b.label));
    return map;
  }, [snapshot.nodes]);

  const renderLevel = (parent: string | null, depth: number): React.ReactNode =>
    (children.get(parent) ?? []).map((node) => (
      <li key={node.node_id}>
        <button
          type="button"
          className={node.node_id === selectedId ? 'is-selected' : ''}
          style={{ paddingInlineStart: `${12 + depth * 18}px` }}
          onClick={() => onSelect(node.node_id)}
        >
          <span className={`authority-dot authority-${node.authority_role.toLowerCase()}`} aria-hidden="true" />
          <span>{node.label}</span>
        </button>
        {renderLevel(node.node_id, depth + 1)}
      </li>
    ));

  return <ul className={`outline-tree ${compact ? 'is-compact' : ''}`}>{renderLevel(null, 0)}</ul>;
}

function Inspector({
  node,
  breadcrumbs,
  onSelect,
  onSetRoot,
  onClose,
}: {
  node?: GraphNode;
  breadcrumbs: GraphNode[];
  onSelect: (id: string) => void;
  onSetRoot: (id: string) => void;
  onClose: () => void;
}) {
  if (!node) {
    return (
      <aside className="inspector" aria-label="Node inspector">
        <div className="empty-panel">
          <strong>No node selected</strong>
          <p>Select a node to inspect its authority, source pointer, type, freshness, and path.</p>
        </div>
      </aside>
    );
  }

  return (
    <aside className="inspector" aria-label="Node inspector">
      <div className="panel-heading">
        <div>
          <span className="panel-kicker">Inspector</span>
          <h2>{node.label}</h2>
        </div>
        <button type="button" className="quiet-button" onClick={onClose}>Close</button>
      </div>
      <Breadcrumbs nodes={breadcrumbs} onSelect={onSelect} />
      <dl className="inspector-grid">
        <div><dt>Type</dt><dd>{node.node_type}</dd></div>
        <div><dt>Authority</dt><dd>{node.authority_role}</dd></div>
        <div><dt>Source</dt><dd>{node.source_system}</dd></div>
        <div><dt>Freshness</dt><dd>{node.freshness_state ?? 'UNKNOWN'}</dd></div>
        <div className="wide"><dt>Source object</dt><dd><code>{node.source_object_id}</code></dd></div>
      </dl>
      <div className="inspector-actions">
        <button type="button" onClick={() => onSetRoot(node.node_id)}>Focus as root</button>
        <a href={node.source_pointer} target="_blank" rel="noreferrer">Open source</a>
      </div>
    </aside>
  );
}

export default function App() {
  const snapshot = SOURCE_BACKED_FIXTURE;
  const [workspace, updateWorkspace] = useUrlWorkspaceState();
  const [search, setSearch] = useState('');
  const deferredSearch = useDeferredValue(search.trim().toLocaleLowerCase());
  const [layout, setLayout] = useState<LayoutResult | null>(null);
  const [backend, setBackend] = useState<RendererBackend>('initializing');
  const [runtime, setRuntime] = useState<RuntimeNotice>({ state: 'loading' });
  const workerRef = useRef<Worker | null>(null);
  const latestRequestRef = useRef('');

  const selectedNode = snapshot.nodes.find((node) => node.node_id === workspace.selected);
  const rootNode = snapshot.nodes.find((node) => node.node_id === workspace.root) ?? snapshot.nodes[0];
  const activeFilters = new Set(workspace.filters);

  const filteredSnapshot = useMemo<GraphSnapshot>(() => {
    const nodes = snapshot.nodes.filter(
      (node) => !activeFilters.size || activeFilters.has(node.authority_role) || node.node_id === rootNode.node_id,
    );
    const ids = new Set(nodes.map((node) => node.node_id));
    return {
      ...snapshot,
      nodes,
      edges: snapshot.edges.filter((edge) => ids.has(edge.source_node_id) && ids.has(edge.target_node_id)),
    };
  }, [activeFilters, rootNode.node_id, snapshot]);

  const searchResults = useMemo(() => {
    if (!deferredSearch) return [];
    return snapshot.nodes
      .filter((node) => `${node.label} ${node.node_type} ${node.source_system}`.toLocaleLowerCase().includes(deferredSearch))
      .slice(0, 12);
  }, [deferredSearch, snapshot.nodes]);

  const breadcrumbs = useMemo(
    () => getBreadcrumbs(snapshot, selectedNode?.node_id ?? rootNode.node_id),
    [rootNode.node_id, selectedNode?.node_id, snapshot],
  );

  useEffect(() => {
    if (workspace.view === 'outline') {
      setBackend('dom');
      setRuntime({ state: 'ready' });
      setLayout(null);
      return;
    }
    const worker = workerRef.current ?? new Worker(new URL('./layout/layout.worker.ts', import.meta.url), { type: 'module' });
    workerRef.current = worker;
    const requestId = crypto.randomUUID();
    latestRequestRef.current = requestId;
    setRuntime({ state: 'loading', detail: 'Computing layout in worker' });
    worker.onmessage = (event: MessageEvent<LayoutWorkerResponse>) => {
      const response = event.data;
      if (response.ok && response.result?.request_id === latestRequestRef.current) {
        setLayout(response.result);
        return;
      }
      if (!response.ok && response.request_id === latestRequestRef.current) {
        setLayout(null);
        setRuntime({ state: 'error', detail: response.error ?? 'Layout worker failed' });
      }
    };
    worker.postMessage({
      request_id: requestId,
      view: workspace.view,
      root_node_id: rootNode.node_id,
      depth: workspace.depth,
      nodes: filteredSnapshot.nodes,
      edges: filteredSnapshot.edges,
    });
  }, [filteredSnapshot.edges, filteredSnapshot.nodes, rootNode.node_id, workspace.depth, workspace.view]);

  useEffect(() => () => workerRef.current?.terminate(), []);

  const handleRuntimeState = useCallback((state: RuntimeState, detail?: string) => {
    setRuntime({ state, detail });
  }, []);
  const handleBackend = useCallback((value: RendererBackend) => setBackend(value), []);
  const selectNode = useCallback((nodeId: string) => updateWorkspace({ selected: nodeId }), [updateWorkspace]);

  const toggleFilter = (filter: string) => {
    const next = new Set(workspace.filters);
    if (next.has(filter)) next.delete(filter);
    else next.add(filter);
    updateWorkspace({ filters: [...next].sort() });
  };

  return (
    <main className="workbench" data-view={workspace.view}>
      <header className="app-header">
        <div className="brand-block">
          <strong>AIOS Cartography</strong>
          <span>Governed interactive workbench</span>
        </div>
        <nav className="view-switcher" aria-label="Cartography views">
          {(Object.keys(VIEW_LABELS) as ViewMode[]).map((view) => (
            <button
              type="button"
              className={workspace.view === view ? 'is-active' : ''}
              aria-pressed={workspace.view === view}
              onClick={() => updateWorkspace({ view })}
              key={view}
            >
              {VIEW_LABELS[view]}
            </button>
          ))}
        </nav>
        <StatusRail backend={backend} notice={runtime} snapshot={snapshot} />
      </header>

      <section className="workspace-grid">
        <aside className="navigator" aria-label="Graph navigator">
          <div className="panel-heading">
            <div>
              <span className="panel-kicker">Navigator</span>
              <h1>{VIEW_LABELS[workspace.view]}</h1>
            </div>
            <span className="node-count">{filteredSnapshot.nodes.length} nodes</span>
          </div>
          <label className="search-box">
            <span>Search graph</span>
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Name, type, or source"
            />
          </label>
          {searchResults.length ? (
            <div className="search-results" aria-label="Search results">
              {searchResults.map((node) => (
                <button type="button" key={node.node_id} onClick={() => selectNode(node.node_id)}>
                  <span>{node.label}</span><small>{node.node_type}</small>
                </button>
              ))}
            </div>
          ) : null}
          <div className="filter-group">
            <span>Authority filters</span>
            {AUTHORITY_FILTERS.map((filter) => (
              <label key={filter}>
                <input
                  type="checkbox"
                  checked={workspace.filters.includes(filter)}
                  onChange={() => toggleFilter(filter)}
                />
                {filter}
              </label>
            ))}
          </div>
          <div className="depth-control">
            <span>Visible depth</span>
            <div>
              <button type="button" onClick={() => updateWorkspace({ depth: Math.max(1, workspace.depth - 1) })}>−</button>
              <output>{workspace.depth}</output>
              <button type="button" onClick={() => updateWorkspace({ depth: Math.min(6, workspace.depth + 1) })}>+</button>
            </div>
          </div>
          <OutlineTree snapshot={filteredSnapshot} selectedId={workspace.selected} onSelect={selectNode} compact />
        </aside>

        <section className="canvas-region" aria-label="Cartography viewport">
          <div className="canvas-toolbar">
            <Breadcrumbs nodes={breadcrumbs} onSelect={selectNode} />
            <div className="canvas-meta">
              <span>{layout?.strategy ?? 'outline'}</span>
              <span>snapshot {workspace.snapshot}</span>
            </div>
          </div>
          <div className="viewport-frame">
            {workspace.view === 'outline' ? (
              <div className="outline-projection" data-testid="outline-view">
                <div className="outline-heading">
                  <h2>Accessible graph outline</h2>
                  <p>Equivalent source-backed projection with keyboard navigation and visible authority roles.</p>
                </div>
                <OutlineTree snapshot={filteredSnapshot} selectedId={workspace.selected} onSelect={selectNode} />
              </div>
            ) : layout ? (
              <GpuGraph
                layout={layout}
                selectedId={workspace.selected}
                onSelect={selectNode}
                onBackend={handleBackend}
                onRuntimeState={handleRuntimeState}
              />
            ) : (
              <div className={`runtime-panel runtime-${runtime.state}`} role={runtime.state === 'error' ? 'alert' : 'status'}>
                <strong>{runtime.state === 'error' ? 'View failed' : 'Preparing governed view'}</strong>
                <p>{runtime.detail ?? 'Waiting for the layout worker.'}</p>
              </div>
            )}
          </div>
        </section>

        <Inspector
          node={selectedNode}
          breadcrumbs={breadcrumbs}
          onSelect={selectNode}
          onSetRoot={(root) => updateWorkspace({ root, selected: root })}
          onClose={() => updateWorkspace({ selected: '' })}
        />
      </section>

      <footer className="app-footer">
        <span>Read-only · no source mutation · URL state enabled</span>
        <code>{snapshot.snapshot_id}</code>
      </footer>
    </main>
  );
}
