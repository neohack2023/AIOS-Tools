import type {
  GraphEdge,
  GraphNode,
  LayoutRequest,
  LayoutResult,
  PositionedEdge,
  PositionedNode,
} from '../types';

const NODE_WIDTH = 230;
const NODE_HEIGHT = 88;
const ROOT_WIDTH = 280;
const ROOT_HEIGHT = 108;
const PADDING = 140;

interface Traversal {
  order: string[];
  parent: Map<string, string | null>;
  depth: Map<string, number>;
  children: Map<string, string[]>;
  visibleIds: Set<string>;
}

function nodeOrder(nodes: Map<string, GraphNode>, id: string): string {
  const node = nodes.get(id);
  return `${node?.label.toLocaleLowerCase() ?? ''}\u0000${id}`;
}

function buildTraversal(request: LayoutRequest): Traversal {
  const nodes = new Map(request.nodes.map((node) => [node.node_id, node]));
  const adjacency = new Map<string, string[]>();
  for (const node of request.nodes) adjacency.set(node.node_id, []);
  for (const edge of request.edges) {
    if (!nodes.has(edge.source_node_id) || !nodes.has(edge.target_node_id)) continue;
    adjacency.get(edge.source_node_id)?.push(edge.target_node_id);
    adjacency.get(edge.target_node_id)?.push(edge.source_node_id);
  }
  for (const values of adjacency.values()) values.sort((a, b) => nodeOrder(nodes, a).localeCompare(nodeOrder(nodes, b)));

  const parent = new Map<string, string | null>([[request.root_node_id, null]]);
  const depth = new Map<string, number>([[request.root_node_id, 0]]);
  const order: string[] = [];
  const queue = [request.root_node_id];

  while (queue.length) {
    const current = queue.shift()!;
    order.push(current);
    const currentDepth = depth.get(current) ?? 0;
    if (currentDepth >= request.depth) continue;
    for (const neighbor of adjacency.get(current) ?? []) {
      if (parent.has(neighbor)) continue;
      parent.set(neighbor, current);
      depth.set(neighbor, currentDepth + 1);
      queue.push(neighbor);
    }
  }

  const children = new Map<string, string[]>();
  for (const id of order) children.set(id, []);
  for (const [id, parentId] of parent) {
    if (parentId) children.get(parentId)?.push(id);
  }
  for (const values of children.values()) values.sort((a, b) => nodeOrder(nodes, a).localeCompare(nodeOrder(nodes, b)));

  return { order, parent, depth, children, visibleIds: new Set(order) };
}

export function isSingleChildChain(traversal: Traversal): boolean {
  if (traversal.order.length < 2) return false;
  return traversal.order.every((id) => (traversal.children.get(id)?.length ?? 0) <= 1);
}

function nodeBox(node: GraphNode, depth: number, x: number, y: number, rootId: string): PositionedNode {
  const root = node.node_id === rootId;
  return {
    ...node,
    x,
    y,
    width: root ? ROOT_WIDTH : NODE_WIDTH,
    height: root ? ROOT_HEIGHT : NODE_HEIGHT,
    depth,
  };
}

function normalize(nodes: PositionedNode[]): { nodes: PositionedNode[]; width: number; height: number } {
  const minX = Math.min(...nodes.map((node) => node.x));
  const minY = Math.min(...nodes.map((node) => node.y));
  const maxX = Math.max(...nodes.map((node) => node.x + node.width));
  const maxY = Math.max(...nodes.map((node) => node.y + node.height));
  const offsetX = PADDING - minX;
  const offsetY = PADDING - minY;
  return {
    nodes: nodes.map((node) => ({ ...node, x: node.x + offsetX, y: node.y + offsetY })),
    width: Math.max(720, maxX - minX + PADDING * 2),
    height: Math.max(520, maxY - minY + PADDING * 2),
  };
}

function pointsForEdge(source: PositionedNode, target: PositionedNode): Array<[number, number]> {
  const sx = source.x + source.width / 2;
  const sy = source.y + source.height / 2;
  const tx = target.x + target.width / 2;
  const ty = target.y + target.height / 2;
  const dx = tx - sx;
  return [
    [sx, sy],
    [sx + dx * 0.38, sy],
    [sx + dx * 0.68, ty],
    [tx, ty],
  ];
}

function positionedEdges(edges: GraphEdge[], nodes: PositionedNode[]): PositionedEdge[] {
  const byId = new Map(nodes.map((node) => [node.node_id, node]));
  return edges.flatMap((edge) => {
    const source = byId.get(edge.source_node_id);
    const target = byId.get(edge.target_node_id);
    if (!source || !target) return [];
    return [{ ...edge, points: pointsForEdge(source, target) }];
  });
}

function tidyTree(request: LayoutRequest, traversal: Traversal): LayoutResult {
  const sourceNodes = new Map(request.nodes.map((node) => [node.node_id, node]));
  const yById = new Map<string, number>();
  let nextLeaf = 0;

  function placeY(id: string): number {
    const children = traversal.children.get(id) ?? [];
    if (!children.length) {
      const y = nextLeaf * 150;
      nextLeaf += 1;
      yById.set(id, y);
      return y;
    }
    const values = children.map(placeY);
    const y = values.reduce((sum, value) => sum + value, 0) / values.length;
    yById.set(id, y);
    return y;
  }
  placeY(request.root_node_id);

  const rawNodes = traversal.order.map((id) => {
    const depth = traversal.depth.get(id) ?? 0;
    return nodeBox(sourceNodes.get(id)!, depth, depth * 310, yById.get(id) ?? 0, request.root_node_id);
  });
  const normalized = normalize(rawNodes);
  return {
    request_id: request.request_id,
    strategy: 'tidy-tree',
    width: normalized.width,
    height: normalized.height,
    nodes: normalized.nodes,
    edges: positionedEdges(request.edges, normalized.nodes),
  };
}

function radial(request: LayoutRequest, traversal: Traversal): LayoutResult {
  const sourceNodes = new Map(request.nodes.map((node) => [node.node_id, node]));
  const leafCounts = new Map<string, number>();
  function leafCount(id: string): number {
    const cached = leafCounts.get(id);
    if (cached) return cached;
    const children = traversal.children.get(id) ?? [];
    const count = Math.max(1, children.reduce((sum, child) => sum + leafCount(child), 0));
    leafCounts.set(id, count);
    return count;
  }
  leafCount(request.root_node_id);

  const positions = new Map<string, [number, number]>([[request.root_node_id, [0, 0]]]);
  function place(id: string, start: number, span: number): void {
    const children = traversal.children.get(id) ?? [];
    const total = children.reduce((sum, child) => sum + leafCount(child), 0) || 1;
    let cursor = start;
    for (const child of children) {
      const childSpan = (span * leafCount(child)) / total;
      const angle = cursor + childSpan / 2;
      const radius = (traversal.depth.get(child) ?? 0) * 270;
      positions.set(child, [Math.cos(angle) * radius, Math.sin(angle) * radius]);
      place(child, cursor, childSpan);
      cursor += childSpan;
    }
  }
  place(request.root_node_id, -Math.PI, Math.PI * 2);

  const rawNodes = traversal.order.map((id) => {
    const [x, y] = positions.get(id) ?? [0, 0];
    return nodeBox(sourceNodes.get(id)!, traversal.depth.get(id) ?? 0, x, y, request.root_node_id);
  });
  const normalized = normalize(rawNodes);
  return {
    request_id: request.request_id,
    strategy: 'radial',
    width: normalized.width,
    height: normalized.height,
    nodes: normalized.nodes,
    edges: positionedEdges(request.edges, normalized.nodes),
  };
}

function lineageLanes(request: LayoutRequest, traversal: Traversal): LayoutResult {
  const visible = request.nodes.filter((node) => traversal.visibleIds.has(node.node_id));
  const lanes = [...new Set(visible.map((node) => node.source_system))].sort();
  const grouped = new Map(lanes.map((lane) => [lane, [] as GraphNode[]]));
  for (const node of visible) grouped.get(node.source_system)?.push(node);
  for (const values of grouped.values()) values.sort((a, b) => a.label.localeCompare(b.label));

  const rawNodes: PositionedNode[] = [];
  lanes.forEach((lane, laneIndex) => {
    (grouped.get(lane) ?? []).forEach((node, rowIndex) => {
      rawNodes.push(nodeBox(node, traversal.depth.get(node.node_id) ?? 0, laneIndex * 440, rowIndex * 132, request.root_node_id));
    });
  });
  const normalized = normalize(rawNodes);
  return {
    request_id: request.request_id,
    strategy: 'lineage-lanes',
    width: normalized.width,
    height: normalized.height,
    nodes: normalized.nodes,
    edges: positionedEdges(request.edges, normalized.nodes),
  };
}

export function compileLayout(request: LayoutRequest): LayoutResult {
  const traversal = buildTraversal(request);
  if (request.view === 'lineage') return lineageLanes(request, traversal);
  if (isSingleChildChain(traversal)) return tidyTree(request, traversal);
  return radial(request, traversal);
}
