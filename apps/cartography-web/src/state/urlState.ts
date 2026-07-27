import { useCallback, useEffect, useState } from 'react';
import type { ViewMode, WorkspaceState } from '../types';

export const DEFAULT_WORKSPACE_STATE: WorkspaceState = {
  view: 'mindmap',
  root: 'notion-global-working-memory',
  depth: 4,
  selected: '',
  filters: [],
  snapshot: 'cartography-system-graph-source-backed-2026-07-27',
};

const VIEWS = new Set<ViewMode>(['mindmap', 'lineage', 'outline']);

export function parseWorkspaceState(search: string): WorkspaceState {
  const params = new URLSearchParams(search);
  const rawView = params.get('view') as ViewMode | null;
  const rawDepth = Number.parseInt(params.get('depth') ?? '', 10);
  const filters = (params.get('filters') ?? '')
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean);

  return {
    view: rawView && VIEWS.has(rawView) ? rawView : DEFAULT_WORKSPACE_STATE.view,
    root: params.get('root') || DEFAULT_WORKSPACE_STATE.root,
    depth: Number.isFinite(rawDepth) ? Math.min(6, Math.max(1, rawDepth)) : DEFAULT_WORKSPACE_STATE.depth,
    selected: params.get('selected') || '',
    filters,
    snapshot: params.get('snapshot') || DEFAULT_WORKSPACE_STATE.snapshot,
  };
}

export function serializeWorkspaceState(state: WorkspaceState): string {
  const params = new URLSearchParams();
  params.set('view', state.view);
  params.set('root', state.root);
  params.set('depth', String(state.depth));
  params.set('snapshot', state.snapshot);
  if (state.selected) params.set('selected', state.selected);
  if (state.filters.length) params.set('filters', state.filters.join(','));
  return params.toString();
}

export function useUrlWorkspaceState(): [
  WorkspaceState,
  (patch: Partial<WorkspaceState>, historyMode?: 'push' | 'replace') => void,
] {
  const [state, setState] = useState<WorkspaceState>(() => parseWorkspaceState(window.location.search));

  useEffect(() => {
    const handlePopState = () => setState(parseWorkspaceState(window.location.search));
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const update = useCallback((patch: Partial<WorkspaceState>, historyMode: 'push' | 'replace' = 'push') => {
    setState((current) => {
      const next = { ...current, ...patch };
      const url = `${window.location.pathname}?${serializeWorkspaceState(next)}${window.location.hash}`;
      if (historyMode === 'replace') window.history.replaceState(next, '', url);
      else window.history.pushState(next, '', url);
      return next;
    });
  }, []);

  useEffect(() => {
    if (!window.location.search) {
      const url = `${window.location.pathname}?${serializeWorkspaceState(state)}`;
      window.history.replaceState(state, '', url);
    }
  }, [state]);

  return [state, update];
}
