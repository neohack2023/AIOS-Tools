import { useMemo, useState } from 'react';
import {
  filterProjectionRows,
  flattenObservatoryProjection,
  type ObservatoryProjection,
} from './projection';

const CATEGORY_LABELS: Record<string, string> = {
  all: 'All metadata',
  workflow: 'Workflow',
  identities: 'Identities',
  context_expansion: 'Context expansion',
  evidence_links: 'Evidence links',
  privacy: 'Privacy',
  projection_id: 'Projection',
  projection_version: 'Projection',
  projection_kind: 'Projection',
  observed_at: 'Projection',
  scope_key: 'Projection',
  authority_transfer: 'Authority',
};

export function ObservatoryPanel({ projection }: { projection: ObservatoryProjection }) {
  const rows = useMemo(() => flattenObservatoryProjection(projection), [projection]);
  const categories = useMemo(
    () => ['all', ...Array.from(new Set(rows.map((row) => row.category))).sort()],
    [rows],
  );
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('all');
  const [selectedPath, setSelectedPath] = useState('context_expansion.sufficiency_verdict');
  const visibleRows = useMemo(
    () => filterProjectionRows(rows, query, category),
    [category, query, rows],
  );
  const selected = rows.find((row) => row.path === selectedPath) ?? visibleRows[0];

  return (
    <section className="observatory-panel" aria-label="Observatory projection inspector" data-testid="observatory-panel">
      <div className="observatory-heading">
        <div>
          <span className="panel-kicker">Observatory</span>
          <h3>Context expansion projection</h3>
        </div>
        <div className="observatory-badges" aria-label="Projection state">
          <span>CHECKED-IN FIXTURE</span>
          <span>READ ONLY</span>
        </div>
      </div>

      <div className="observatory-summary">
        <div><span>Decision</span><strong>{projection.context_expansion.decision_result}</strong></div>
        <div><span>Sufficiency</span><strong>{projection.context_expansion.sufficiency_verdict}</strong></div>
        <div><span>Tier</span><strong>{projection.context_expansion.tier_movement}</strong></div>
        <div><span>Budget</span><strong>{projection.context_expansion.budget_state}</strong></div>
      </div>

      <div className="observatory-controls">
        <label>
          <span>Filter metadata</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Identifier, status, or value"
          />
        </label>
        <label>
          <span>Section</span>
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            {categories.map((value) => (
              <option value={value} key={value}>{CATEGORY_LABELS[value] ?? value.replaceAll('_', ' ')}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="observatory-browser">
        <div className="observatory-row-list" aria-label="Projection metadata rows">
          {visibleRows.length ? visibleRows.map((row) => (
            <button
              type="button"
              className={row.path === selected?.path ? 'is-selected' : ''}
              onClick={() => setSelectedPath(row.path)}
              key={row.path}
            >
              <span>{row.label}</span>
              <small>{row.value}</small>
            </button>
          )) : (
            <p className="observatory-empty">No metadata matches this filter.</p>
          )}
        </div>
        <div className="observatory-detail" aria-live="polite">
          {selected ? (
            <>
              <span className="panel-kicker">Selected field</span>
              <strong>{selected.label}</strong>
              <code>{selected.path}</code>
              <p>{selected.value}</p>
            </>
          ) : (
            <p>Select a projected metadata field.</p>
          )}
        </div>
      </div>

      <div className="observatory-privacy-note">
        Source content, raw events, raw receipts, prompts, embeddings, vectors, and hidden reasoning are not present in this projection.
      </div>
    </section>
  );
}
