import { describe, expect, it } from 'vitest';
import { compileLayout } from './strategies';
import type { GraphEdge, GraphNode, LayoutRequest } from '../types';

function chainRequest(view: 'mindmap' | 'lineage' = 'mindmap'): LayoutRequest {
  const nodes: GraphNode[] = Array.from({ length: 5 }, (_, index) => ({
    node_id: `node-${index}`,
    label: `Node ${index}`,
    node_type: 'fixture',
    source_system: index < 3 ? 'notion' : 'google_drive',
    source_object_id: String(index),
    source_pointer: `fixture://${index}`,
    authority_role: index < 3 ? 'AUTHORITATIVE' : 'DRIVE_SHADOW',
    parent_node_id: index ? `node-${index - 1}` : null,
  }));
  const edges: GraphEdge[] = Array.from({ length: 4 }, (_, index) => ({
    edge_id: `edge-${index}`,
    relation_type: 'contains',
    source_node_id: `node-${index}`,
    target_node_id: `node-${index + 1}`,
    directionality: 'DIRECTED',
    explanation: 'fixture chain',
  }));
  return { request_id: 'chain', view, root_node_id: 'node-0', depth: 6, nodes, edges };
}

describe('layout strategy router', () => {
  it('routes a single-child mind-map chain to tidy-tree instead of a collapsed radial spoke', () => {
    const layout = compileLayout(chainRequest());
    expect(layout.strategy).toBe('tidy-tree');
    const ordered = [...layout.nodes].sort((a, b) => a.depth - b.depth);
    expect(ordered.map((node) => node.x)).toEqual([...ordered.map((node) => node.x)].sort((a, b) => a - b));
    expect(new Set(ordered.map((node) => node.y)).size).toBe(1);
  });

  it('uses deterministic radial placement for a true multi-branch mind map', () => {
    const request = chainRequest();
    request.nodes.push({
      ...request.nodes[4],
      node_id: 'branch-node',
      label: 'Branch node',
      source_object_id: 'branch',
      parent_node_id: 'node-0',
    });
    request.edges.push({
      edge_id: 'branch-edge',
      relation_type: 'contains',
      source_node_id: 'node-0',
      target_node_id: 'branch-node',
      directionality: 'DIRECTED',
      explanation: 'fixture branch',
    });
    const first = compileLayout(request);
    const second = compileLayout(request);
    expect(first.strategy).toBe('radial');
    expect(first).toEqual(second);
  });

  it('routes lineage views to stable source lanes', () => {
    const layout = compileLayout(chainRequest('lineage'));
    expect(layout.strategy).toBe('lineage-lanes');
    const notionX = new Set(layout.nodes.filter((node) => node.source_system === 'notion').map((node) => node.x));
    const driveX = new Set(layout.nodes.filter((node) => node.source_system === 'google_drive').map((node) => node.x));
    expect(notionX.size).toBe(1);
    expect(driveX.size).toBe(1);
    expect([...notionX][0]).not.toBe([...driveX][0]);
  });
});
