import { describe, expect, it } from 'vitest';
import { mockApi } from './mockApi';
import { FIXTURES } from './mockData';
import { parseIdentifier } from '../lib/identifiers';
import { SAMPLE_EXTRACTION, SAMPLE_EXTRACTION_PARTIAL, parseExtractedJson } from '../lib/extensionImport';
import { ApiError } from '../types/api';

function extracted(json: string) {
  const r = parseExtractedJson(json);
  if (!r.ok) throw new Error(r.error);
  return r.value;
}

describe('fixtures keep the evidence rules', () => {
  it('never shows a missing parameter as zero', () => {
    for (const f of FIXTURES) {
      for (const p of f.evaluation.parameters) {
        if (p.status === 'not_scored') expect(p.score).toBeNull();
        if (p.score !== null) expect(p.status).toBe('scored');
      }
    }
  });

  it('withholds the overall score when evidence is insufficient', () => {
    for (const f of FIXTURES) {
      if (f.evaluation.confidence.state === 'insufficient_evidence') expect(f.evaluation.overall_score).toBeNull();
    }
  });

  it('has weights that add up to one in every evaluation', () => {
    for (const f of FIXTURES) {
      const sum = f.evaluation.parameters.reduce((a, p) => a + (p.weight ?? 0), 0);
      expect(sum).toBeCloseTo(1, 5);
    }
  });
});

describe('search and lookup', () => {
  it('finds a product by words in any order', async () => {
    const r = await mockApi.searchProducts('ultra galaxy');
    expect(r.map((x) => x.product.name)).toEqual(['Samsung Galaxy S25 Ultra']);
  });

  it('matches an Amazon India link by its product ID', async () => {
    const r = await mockApi.lookupIdentifier(parseIdentifier('https://www.amazon.in/x/dp/B0DSKMV3ZC/ref=abc'));
    expect(r.match_state).toBe('confirmed');
    expect(r.candidates).toHaveLength(1);
  });

  it('says unmatched, without inventing a score, for an unknown product ID', async () => {
    const r = await mockApi.lookupIdentifier(parseIdentifier('B0ZZZZZZZZ'));
    expect(r.match_state).toBe('unmatched');
    expect(r.candidates).toHaveLength(0);
  });

  it('refuses links from other sites', async () => {
    const r = await mockApi.lookupIdentifier(parseIdentifier('https://example.com/dp/B0DSKMV3ZC'));
    expect(r.match_state).toBe('unmatched');
  });
});

describe('matching extension data', () => {
  it('confirms a full match', async () => {
    const r = await mockApi.matchExtracted(extracted(SAMPLE_EXTRACTION));
    expect(r.match_state).toBe('confirmed');
    expect(r.candidates[0]?.variant.id).toBe('v-s25u-12-256');
  });

  it('reports a probable match when details are unclear, like the extension does', async () => {
    const r = await mockApi.matchExtracted(extracted(SAMPLE_EXTRACTION_PARTIAL));
    expect(r.match_state).toBe('probable');
  });

  it('asks for a choice when several variants fit', async () => {
    const r = await mockApi.matchExtracted({ ...extracted(SAMPLE_EXTRACTION), brand: 'Sample', model_name: 'Phone C', ram_gb: null, storage_gb: null });
    expect(r.match_state).toBe('ambiguous');
    expect(r.candidates.length).toBeGreaterThan(1);
  });

  it('says unmatched for a model that is not in the catalogue', async () => {
    const r = await mockApi.matchExtracted({ ...extracted(SAMPLE_EXTRACTION), model_name: 'Unknown Phone' });
    expect(r.match_state).toBe('unmatched');
  });
});

describe('compare', () => {
  it('compares products of the same category', async () => {
    const r = await mockApi.compare(['v-s25u-12-256', 'v-iphone17pm-1tb']);
    expect(r.category).toBe('smartphone');
    expect(r.items).toHaveLength(2);
  });

  it('blocks a cross-category comparison', async () => {
    await expect(mockApi.compare(['v-s25u-12-256', 'v-ssd-1tb'])).rejects.toMatchObject({ code: 'different_categories' });
  });

  it('needs two to three products', async () => {
    await expect(mockApi.compare(['v-s25u-12-256'])).rejects.toBeInstanceOf(ApiError);
    await expect(mockApi.compare(['v-s25u-12-256', 'v-iphone17pm-1tb', 'v-phone-c-12-256', 'v-phone-c-8-128'])).rejects.toMatchObject({ code: 'too_many' });
  });
});
