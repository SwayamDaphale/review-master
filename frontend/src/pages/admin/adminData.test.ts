import { describe, expect, it } from 'vitest';
import { MODELS_SEED, modelBlockers, type EvalModel } from './adminData';

const smartphone = MODELS_SEED[0] as EvalModel;

describe('modelBlockers', () => {
  it('blocks a draft with no weights and no approvals', () => {
    const b = modelBlockers(smartphone);
    expect(b).toContain('7 of 7 weights are not set');
    expect(b).toContain('Domain expert approval is missing');
    expect(b).toContain('Engineering approval is missing');
  });

  it('blocks weights that do not add up to one', () => {
    const m: EvalModel = { ...smartphone, params: smartphone.params.map((p) => ({ ...p, weight: 0.2 })), domainApproved: true, engineeringApproved: true };
    expect(modelBlockers(m)[0]).toMatch(/not 1\.00/);
  });

  it('allows publishing when weights sum to one and both approvals exist', () => {
    const weights = [0.22, 0.2, 0.2, 0.14, 0.1, 0.08, 0.06];
    const m: EvalModel = {
      ...smartphone,
      params: smartphone.params.map((p, i) => ({ ...p, weight: weights[i] ?? 0 })),
      domainApproved: true,
      engineeringApproved: true,
    };
    expect(modelBlockers(m)).toEqual([]);
  });
});
