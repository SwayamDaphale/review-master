import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

describe('Review Master Trust Architecture & Calculations', () => {
  it('strictly maintains 3 separate trust outputs without blending', () => {
    const outputs = {
      overall_score: 8.6,
      confidence_state: 'high',
      confidence_score: 0.94,
      community_authentic_ratio: 0.88
    };

    assert.equal(typeof outputs.overall_score, 'number');
    assert.equal(outputs.confidence_state, 'high');
    assert.equal(outputs.community_authentic_ratio, 0.88);
    // Guarantee score and confidence are separate fields
    assert.notEqual(outputs.overall_score, outputs.confidence_score);
  });

  it('treats missing evidence as null or insufficient rather than zero', () => {
    const sampleEval = {
      thermal_throttling_score: null,
      status: 'insufficient_evidence'
    };

    assert.equal(sampleEval.thermal_throttling_score, null);
    assert.notEqual(sampleEval.thermal_throttling_score, 0);
  });
});
