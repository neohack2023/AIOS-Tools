export interface ObservatoryWorkflowProjection {
  workflow_id: 'context-expansion.packet-read-only';
  workflow_version: '0.1';
  status: 'COMPLETED';
  mode: 'READ_ONLY';
  started_at: string;
  completed_at: string;
  event_count: number;
}

export interface ObservatoryIdentityProjection {
  request_id: string;
  trace_id: string;
  receipt_id: string;
  execution_id: string | null;
  trajectory_id: string;
  context_packet_id: string;
  expansion_record_id: string;
}

export interface ObservatoryContextExpansionProjection {
  current_tier: 'L0' | 'L1' | 'L2';
  requested_tier: 'L0' | 'L1' | 'L2';
  tier_movement: string;
  sufficiency_verdict: 'SUFFICIENT' | 'INSUFFICIENT' | 'UNKNOWN' | 'BLOCKED';
  expansion_trigger:
    | 'SUFFICIENCY_FAILED'
    | 'AUTHORITY_AMBIGUITY'
    | 'CONFLICT_DETECTED'
    | 'EVIDENCE_GAP'
    | 'USER_REQUEST'
    | 'BUDGET_REALLOCATION'
    | 'RECOVERY'
    | 'COMPACTION_RESET';
  decision_result: 'EXPANDED' | 'DENIED' | 'BLOCKED' | 'NO_OP';
  budget_state: 'WITHIN_BUDGET' | 'APPROVED_INCREASE';
  lifecycle_state: string;
}

export interface ObservatoryEvidenceLink {
  evidence_type: 'CONTEXT_EXPANSION_DECISION_RECORD';
  evidence_id: string;
  schema_version: '0.1';
  scope_key: string;
  lifecycle_state: string;
  authority_transfer: false;
  referenced_by_event_types: string[];
}

export interface ObservatoryProjection {
  projection_id: string;
  projection_version: '0.1';
  projection_kind: 'CONTEXT_EXPANSION_OBSERVATORY';
  observed_at: string;
  scope_key: string;
  workflow: ObservatoryWorkflowProjection;
  identities: ObservatoryIdentityProjection;
  context_expansion: ObservatoryContextExpansionProjection;
  evidence_links: ObservatoryEvidenceLink[];
  privacy: {
    source_content_included: false;
    event_payloads_included: false;
    raw_receipt_included: false;
    raw_cedr_included: false;
  };
  external_effects: [];
  authority_transfer: false;
}

export interface ObservatoryProjectionRow {
  path: string;
  category: string;
  label: string;
  value: string;
}

const TOP_LEVEL_KEYS = [
  'projection_id',
  'projection_version',
  'projection_kind',
  'observed_at',
  'scope_key',
  'workflow',
  'identities',
  'context_expansion',
  'evidence_links',
  'privacy',
  'external_effects',
  'authority_transfer',
] as const;

const WORKFLOW_KEYS = [
  'workflow_id',
  'workflow_version',
  'status',
  'mode',
  'started_at',
  'completed_at',
  'event_count',
] as const;

const IDENTITY_KEYS = [
  'request_id',
  'trace_id',
  'receipt_id',
  'execution_id',
  'trajectory_id',
  'context_packet_id',
  'expansion_record_id',
] as const;

const CONTEXT_KEYS = [
  'current_tier',
  'requested_tier',
  'tier_movement',
  'sufficiency_verdict',
  'expansion_trigger',
  'decision_result',
  'budget_state',
  'lifecycle_state',
] as const;

const EVIDENCE_KEYS = [
  'evidence_type',
  'evidence_id',
  'schema_version',
  'scope_key',
  'lifecycle_state',
  'authority_transfer',
  'referenced_by_event_types',
] as const;

const PRIVACY_KEYS = [
  'source_content_included',
  'event_payloads_included',
  'raw_receipt_included',
  'raw_cedr_included',
] as const;

const FORBIDDEN_KEYS = new Set([
  'events',
  'payload',
  'context_expansion_decision',
  'cognition_receipt',
  'opened_items',
  'rejected_items',
  'omitted_items',
  'authority_sources_considered',
  'decision_reason',
  'source_content',
  'prompt',
  'embedding',
  'vector',
]);

function asRecord(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`${label} must be an object`);
  }
  return value as Record<string, unknown>;
}

function assertExactKeys(value: Record<string, unknown>, expected: readonly string[], label: string): void {
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  if (actual.length !== wanted.length || actual.some((key, index) => key !== wanted[index])) {
    throw new Error(`${label} keys do not match the projection contract`);
  }
}

function rejectForbiddenKeys(value: unknown): void {
  if (Array.isArray(value)) {
    value.forEach(rejectForbiddenKeys);
    return;
  }
  if (!value || typeof value !== 'object') return;
  for (const [key, item] of Object.entries(value)) {
    if (FORBIDDEN_KEYS.has(key)) throw new Error(`Projection contains forbidden raw field: ${key}`);
    rejectForbiddenKeys(item);
  }
}

function requireString(value: unknown, label: string): asserts value is string {
  if (typeof value !== 'string' || !value.trim()) throw new Error(`${label} must be non-empty`);
}

function requirePattern(value: unknown, pattern: RegExp, label: string): asserts value is string {
  requireString(value, label);
  if (!pattern.test(value)) throw new Error(`${label} has an invalid format`);
}

function requireEnum<T extends string>(value: unknown, allowed: readonly T[], label: string): asserts value is T {
  if (typeof value !== 'string' || !allowed.includes(value as T)) throw new Error(`${label} is unsupported`);
}

export function parseObservatoryProjection(input: unknown): ObservatoryProjection {
  rejectForbiddenKeys(input);
  const projection = asRecord(input, 'Observatory projection');
  assertExactKeys(projection, TOP_LEVEL_KEYS, 'Observatory projection');

  requirePattern(projection.projection_id, /^op_[0-9a-f]{64}$/, 'projection_id');
  if (projection.projection_version !== '0.1') throw new Error('projection_version is unsupported');
  if (projection.projection_kind !== 'CONTEXT_EXPANSION_OBSERVATORY') throw new Error('projection_kind is unsupported');
  requireString(projection.observed_at, 'observed_at');
  requireString(projection.scope_key, 'scope_key');
  if (projection.authority_transfer !== false) throw new Error('authority transfer must remain false');
  if (!Array.isArray(projection.external_effects) || projection.external_effects.length !== 0) {
    throw new Error('external_effects must remain empty');
  }

  const workflow = asRecord(projection.workflow, 'workflow');
  assertExactKeys(workflow, WORKFLOW_KEYS, 'workflow');
  if (workflow.workflow_id !== 'context-expansion.packet-read-only') throw new Error('workflow_id is unsupported');
  if (workflow.workflow_version !== '0.1') throw new Error('workflow_version is unsupported');
  if (workflow.status !== 'COMPLETED' || workflow.mode !== 'READ_ONLY') throw new Error('workflow must be completed and read-only');
  requireString(workflow.started_at, 'workflow.started_at');
  requireString(workflow.completed_at, 'workflow.completed_at');
  if (!Number.isInteger(workflow.event_count) || Number(workflow.event_count) < 1) throw new Error('workflow.event_count must be positive');

  const identities = asRecord(projection.identities, 'identities');
  assertExactKeys(identities, IDENTITY_KEYS, 'identities');
  requireString(identities.request_id, 'identities.request_id');
  requireString(identities.trace_id, 'identities.trace_id');
  requirePattern(identities.receipt_id, /^cr_[0-9a-f]{64}$/, 'identities.receipt_id');
  if (identities.execution_id !== null) requireString(identities.execution_id, 'identities.execution_id');
  requirePattern(identities.trajectory_id, /^rt_[0-9a-f]{64}$/, 'identities.trajectory_id');
  requireString(identities.context_packet_id, 'identities.context_packet_id');
  requirePattern(identities.expansion_record_id, /^cedr_[0-9a-f]{64}$/, 'identities.expansion_record_id');

  const context = asRecord(projection.context_expansion, 'context_expansion');
  assertExactKeys(context, CONTEXT_KEYS, 'context_expansion');
  requireEnum(context.current_tier, ['L0', 'L1', 'L2'] as const, 'context_expansion.current_tier');
  requireEnum(context.requested_tier, ['L0', 'L1', 'L2'] as const, 'context_expansion.requested_tier');
  if (context.tier_movement !== `${context.current_tier}->${context.requested_tier}`) throw new Error('tier_movement does not match tiers');
  requireEnum(context.sufficiency_verdict, ['SUFFICIENT', 'INSUFFICIENT', 'UNKNOWN', 'BLOCKED'] as const, 'context_expansion.sufficiency_verdict');
  requireEnum(context.expansion_trigger, ['SUFFICIENCY_FAILED', 'AUTHORITY_AMBIGUITY', 'CONFLICT_DETECTED', 'EVIDENCE_GAP', 'USER_REQUEST', 'BUDGET_REALLOCATION', 'RECOVERY', 'COMPACTION_RESET'] as const, 'context_expansion.expansion_trigger');
  requireEnum(context.decision_result, ['EXPANDED', 'DENIED', 'BLOCKED', 'NO_OP'] as const, 'context_expansion.decision_result');
  requireEnum(context.budget_state, ['WITHIN_BUDGET', 'APPROVED_INCREASE'] as const, 'context_expansion.budget_state');
  requireString(context.lifecycle_state, 'context_expansion.lifecycle_state');

  if (!Array.isArray(projection.evidence_links) || projection.evidence_links.length < 1) throw new Error('evidence_links must not be empty');
  for (const item of projection.evidence_links) {
    const link = asRecord(item, 'evidence link');
    assertExactKeys(link, EVIDENCE_KEYS, 'evidence link');
    if (link.evidence_type !== 'CONTEXT_EXPANSION_DECISION_RECORD') throw new Error('evidence_type is unsupported');
    if (link.evidence_id !== identities.expansion_record_id) throw new Error('evidence link must reference the projected CEDR');
    if (link.schema_version !== '0.1') throw new Error('evidence schema version is unsupported');
    if (link.scope_key !== projection.scope_key) throw new Error('evidence scope must match projection scope');
    requireString(link.lifecycle_state, 'evidence.lifecycle_state');
    if (link.authority_transfer !== false) throw new Error('evidence authority transfer must remain false');
    if (!Array.isArray(link.referenced_by_event_types) || link.referenced_by_event_types.length < 1) {
      throw new Error('evidence event references must not be empty');
    }
    link.referenced_by_event_types.forEach((eventType) => requireString(eventType, 'evidence event type'));
  }

  const privacy = asRecord(projection.privacy, 'privacy');
  assertExactKeys(privacy, PRIVACY_KEYS, 'privacy');
  if (Object.values(privacy).some((value) => value !== false)) throw new Error('privacy flags must remain false');

  return input as ObservatoryProjection;
}

function labelForPath(path: string): string {
  return path
    .split('.')
    .at(-1)!
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function flattenObservatoryProjection(projection: ObservatoryProjection): ObservatoryProjectionRow[] {
  const rows: ObservatoryProjectionRow[] = [];
  const visit = (value: unknown, path: string, category: string): void => {
    if (Array.isArray(value)) {
      if (value.every((item) => typeof item !== 'object')) {
        rows.push({ path, category, label: labelForPath(path), value: value.join(', ') || 'None' });
        return;
      }
      value.forEach((item, index) => visit(item, `${path}.${index + 1}`, category));
      return;
    }
    if (value && typeof value === 'object') {
      Object.entries(value).forEach(([key, item]) => visit(item, path ? `${path}.${key}` : key, category || key));
      return;
    }
    rows.push({
      path,
      category,
      label: labelForPath(path),
      value: value === null ? 'Not supplied' : String(value),
    });
  };

  Object.entries(projection).forEach(([key, value]) => {
    if (key === 'external_effects') return;
    visit(value, key, key);
  });
  return rows;
}

export function filterProjectionRows(
  rows: ObservatoryProjectionRow[],
  query: string,
  category: string,
): ObservatoryProjectionRow[] {
  const needle = query.trim().toLocaleLowerCase();
  return rows.filter((row) => {
    if (category !== 'all' && row.category !== category) return false;
    if (!needle) return true;
    return `${row.path} ${row.label} ${row.value}`.toLocaleLowerCase().includes(needle);
  });
}
