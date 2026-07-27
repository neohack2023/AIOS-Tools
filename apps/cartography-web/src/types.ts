export type ViewMode = 'mindmap' | 'lineage' | 'outline';
export type RendererBackend = 'initializing' | 'webgpu' | 'webgl2' | 'dom';
export type RuntimeState =
  | 'loading'
  | 'ready'
  | 'stale'
  | 'partial'
  | 'fallback'
  | 'context-lost'
  | 'error';

export interface GraphNode {
  node_id: string;
  label: string;
  node_type: string;
  source_system: string;
  source_object_id: string;
  source_pointer: string;
  authority_role: string;
  parent_node_id?: string | null;
  freshness_state?: string;
  attributes?: Record<string, unknown>;
}

export interface GraphEdge {
  edge_id: string;
  relation_type: string;
  source_node_id: string;
  target_node_id: string;
  directionality: 'DIRECTED' | 'UNDIRECTED';
  explanation: string;
}

export interface GraphSnapshot {
  snapshot_id: string;
  snapshot_digest: string;
  observed_at: string;
  coverage_state: 'COMPLETE' | 'PARTIAL';
  freshness_state: 'CURRENT' | 'STALE';
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface PositionedNode extends GraphNode {
  x: number;
  y: number;
  width: number;
  height: number;
  depth: number;
}

export interface PositionedEdge extends GraphEdge {
  points: Array<[number, number]>;
}

export interface LayoutResult {
  request_id: string;
  strategy: 'tidy-tree' | 'radial' | 'lineage-lanes';
  width: number;
  height: number;
  nodes: PositionedNode[];
  edges: PositionedEdge[];
}

export interface LayoutRequest {
  request_id: string;
  view: Exclude<ViewMode, 'outline'>;
  root_node_id: string;
  depth: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface WorkspaceState {
  view: ViewMode;
  root: string;
  depth: number;
  selected: string;
  filters: string[];
  snapshot: string;
}
