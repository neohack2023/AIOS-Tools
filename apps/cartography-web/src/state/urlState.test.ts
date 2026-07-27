import { describe, expect, it } from 'vitest';
import { DEFAULT_WORKSPACE_STATE, parseWorkspaceState, serializeWorkspaceState } from './urlState';

describe('URL-backed workspace state', () => {
  it('round-trips all governed workspace fields', () => {
    const state = {
      view: 'lineage' as const,
      root: 'drive-ai-memory-os',
      depth: 3,
      selected: 'drive-mason',
      filters: ['DRIVE_SHADOW', 'IMPLEMENTATION'],
      snapshot: 'snapshot-42',
    };
    expect(parseWorkspaceState(`?${serializeWorkspaceState(state)}`)).toEqual(state);
  });

  it('fails closed to valid Slice 8 defaults for unsupported view and depth values', () => {
    const parsed = parseWorkspaceState('?view=unknown&depth=99');
    expect(parsed.view).toBe(DEFAULT_WORKSPACE_STATE.view);
    expect(parsed.depth).toBe(6);
    expect(parsed.root).toBe(DEFAULT_WORKSPACE_STATE.root);
    expect(parsed.snapshot).toBe('cartography-system-graph-source-backed-2026-07-27');
  });
});
