import { describe, expect, it } from 'vitest';
import { SOURCE_BACKED_FIXTURE } from './sourceBackedFixture';
import type { CoverageDomain } from '../types';

const EXPECTED_DOMAINS: CoverageDomain[] = [
  'governance',
  'registries',
  'project-branches',
  'retrieval',
  'workflows',
  'stone-mason',
  'observability',
  'implementation',
];

describe('Slice 8 source-backed system graph', () => {
  it('resolves every declared coverage domain without rendering gap placeholders', () => {
    expect(SOURCE_BACKED_FIXTURE.coverage_report.declared_domains).toEqual(EXPECTED_DOMAINS);
    expect(SOURCE_BACKED_FIXTURE.coverage_report.resolved_domains).toEqual(EXPECTED_DOMAINS);
    expect(SOURCE_BACKED_FIXTURE.coverage_report.resolved_node_count).toBe(
      SOURCE_BACKED_FIXTURE.nodes.length,
    );
    expect(SOURCE_BACKED_FIXTURE.nodes).toHaveLength(41);

    const renderedIds = new Set(SOURCE_BACKED_FIXTURE.nodes.map((node) => node.node_id));
    for (const gap of SOURCE_BACKED_FIXTURE.coverage_report.unresolved) {
      expect(renderedIds.has(gap.gap_id)).toBe(false);
    }
  });

  it('keeps exact provenance on every node', () => {
    const supportedSystems = new Set(['notion', 'google_drive', 'github']);
    for (const node of SOURCE_BACKED_FIXTURE.nodes) {
      expect(supportedSystems.has(node.source_system)).toBe(true);
      expect(node.source_object_id.trim()).not.toBe('');
      expect(node.source_pointer).toMatch(/^https:\/\//);
      expect(node.attributes?.coverage_status).toBe('RESOLVED');
      expect(node.attributes?.provenance_basis).toBe('EXACT_SOURCE_OBJECT');
      expect(EXPECTED_DOMAINS).toContain(node.attributes?.domain);
      expect(node.node_id).not.toMatch(/placeholder|synthetic|unknown/i);
    }
  });

  it('preserves source authority roles', () => {
    const notionNodes = SOURCE_BACKED_FIXTURE.nodes.filter((node) => node.source_system === 'notion');
    const driveNodes = SOURCE_BACKED_FIXTURE.nodes.filter((node) => node.source_system === 'google_drive');
    const githubNodes = SOURCE_BACKED_FIXTURE.nodes.filter((node) => node.source_system === 'github');

    expect(notionNodes.length).toBeGreaterThan(0);
    expect(driveNodes.length).toBeGreaterThan(0);
    expect(githubNodes.length).toBeGreaterThan(0);
    expect(notionNodes.every((node) => node.authority_role === 'AUTHORITATIVE')).toBe(true);
    expect(driveNodes.every((node) => node.authority_role === 'DRIVE_SHADOW')).toBe(true);
    expect(githubNodes.every((node) => node.authority_role === 'IMPLEMENTATION')).toBe(true);
  });

  it('keeps all hierarchy and cross-source edges endpoint-complete', () => {
    const ids = new Set(SOURCE_BACKED_FIXTURE.nodes.map((node) => node.node_id));
    const edgeIds = new Set<string>();
    for (const edge of SOURCE_BACKED_FIXTURE.edges) {
      expect(ids.has(edge.source_node_id)).toBe(true);
      expect(ids.has(edge.target_node_id)).toBe(true);
      expect(edgeIds.has(edge.edge_id)).toBe(false);
      edgeIds.add(edge.edge_id);
    }

    const relationTypes = new Set(SOURCE_BACKED_FIXTURE.edges.map((edge) => edge.relation_type));
    expect(relationTypes).toContain('mirrored_by');
    expect(relationTypes).toContain('implemented_by');
    expect(relationTypes).toContain('backed_by');
  });

  it('retains the two exact Drive physical hierarchies', () => {
    const parents = new Map(
      SOURCE_BACKED_FIXTURE.nodes.map((node) => [node.node_id, node.parent_node_id ?? null]),
    );

    expect(parents.get('drive-cartography-contract')).toBe('drive-mason');
    expect(parents.get('drive-mason')).toBe('drive-governance');
    expect(parents.get('drive-governance')).toBe('drive-ai-memory-os');

    expect(parents.get('drive-project-scope-registry')).toBe('drive-registries-folder');
    expect(parents.get('drive-capability-registry')).toBe('drive-registries-folder');
    expect(parents.get('drive-retrieval-runtime-registry')).toBe('drive-registries-folder');
    expect(parents.get('drive-runtime-telemetry-registry')).toBe('drive-registries-folder');
    expect(parents.get('drive-registries-folder')).toBe('drive-system-folder');
    expect(parents.get('drive-system-folder')).toBe('drive-ai-knowledge-system');
  });
});
