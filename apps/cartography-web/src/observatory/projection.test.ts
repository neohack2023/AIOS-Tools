import { describe, expect, it } from 'vitest';
import rawProjection from '../data/observatoryProjectionFixture.json';
import {
  filterProjectionRows,
  flattenObservatoryProjection,
  parseObservatoryProjection,
} from './projection';

function cloneFixture(): unknown {
  return JSON.parse(JSON.stringify(rawProjection));
}

describe('Observatory projection fixture', () => {
  it('loads the checked-in fixture through the strict read-model validator', () => {
    const projection = parseObservatoryProjection(rawProjection);

    expect(projection.projection_id).toMatch(/^op_[0-9a-f]{64}$/);
    expect(projection.workflow).toMatchObject({ status: 'COMPLETED', mode: 'READ_ONLY' });
    expect(projection.identities.execution_id).toBeNull();
    expect(projection.context_expansion.tier_movement).toBe('L0->L1');
    expect(projection.external_effects).toEqual([]);
    expect(projection.authority_transfer).toBe(false);
    expect(Object.values(projection.privacy)).toEqual([false, false, false, false]);
  });

  it('flattens only projected metadata for selection and filtering', () => {
    const rows = flattenObservatoryProjection(parseObservatoryProjection(rawProjection));
    const contextRows = filterProjectionRows(rows, 'insufficient', 'context_expansion');

    expect(contextRows).toEqual([
      expect.objectContaining({
        path: 'context_expansion.sufficiency_verdict',
        value: 'INSUFFICIENT',
      }),
    ]);
    expect(rows.some((row) => row.path.split('.').at(-1) === 'events')).toBe(false);
    expect(rows.some((row) => row.path.split('.').at(-1) === 'source_content')).toBe(false);
    expect(rows).toContainEqual(expect.objectContaining({
      path: 'privacy.source_content_included',
      value: 'false',
    }));
  });

  it('fails closed when raw receipt fields are injected', () => {
    const invalid = cloneFixture() as Record<string, unknown>;
    invalid.events = [{ payload: { source_content: 'forbidden' } }];

    expect(() => parseObservatoryProjection(invalid)).toThrow(/forbidden raw field/);
  });

  it('fails closed when an execution identity is synthesized as an empty alias', () => {
    const invalid = cloneFixture() as { identities: { execution_id: string } };
    invalid.identities.execution_id = '';

    expect(() => parseObservatoryProjection(invalid)).toThrow(/execution_id must be non-empty/);
  });

  it('fails closed when evidence no longer references the projected CEDR', () => {
    const invalid = cloneFixture() as { evidence_links: Array<{ evidence_id: string }> };
    invalid.evidence_links[0].evidence_id = `cedr_${'4'.repeat(64)}`;

    expect(() => parseObservatoryProjection(invalid)).toThrow(/projected CEDR/);
  });
});
