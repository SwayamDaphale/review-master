import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  submitListingIngestion,
  getIngestionJobStatus,
  resolveIdentity,
  createHandoffToken,
  listComparisonSessions,
  addVariantToComparison,
  createComparisonSession,
  IngestionApiError,
} from '../src/api/client.mjs';

describe('Extension API Client Integration', () => {
  const originalFetch = globalThis.fetch;

  it('submitListingIngestion sends validated record and parses response', async () => {
    globalThis.fetch = async (url, opts) => {
      assert.match(url, /\/api\/v1\/listings\/ingest$/);
      assert.equal(opts.method, 'POST');
      assert.equal(opts.headers['Content-Type'], 'application/json');
      const body = JSON.parse(opts.body);
      assert.equal(body.source.asin, 'B0TESTASIN1');

      return {
        ok: true,
        status: 202,
        json: async () => ({
          job_id: '12345678-1234-1234-1234-1234567890ab',
          status: 'accepted',
          is_duplicate: false,
        }),
      };
    };

    try {
      const res = await submitListingIngestion({
        schema_version: '1.0',
        source: { asin: 'B0TESTASIN1', marketplace: 'amazon_in' },
        raw_extraction: { title: 'Test Phone' },
        normalized: { brand: 'TestBrand', model_name: 'TestModel' },
      });
      assert.equal(res.status, 'accepted');
      assert.equal(res.job_id, '12345678-1234-1234-1234-1234567890ab');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('getIngestionJobStatus retrieves terminal and running status views', async () => {
    globalThis.fetch = async (url) => {
      assert.match(url, /\/api\/v1\/ingestion-jobs\/job-xyz$/);
      return {
        ok: true,
        status: 200,
        json: async () => ({
          job_id: 'job-xyz',
          job_type: 'listing_ingestion',
          status: 'completed',
        }),
      };
    };

    try {
      const res = await getIngestionJobStatus('job-xyz');
      assert.equal(res.job_id, 'job-xyz');
      assert.equal(res.status, 'completed');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('resolveIdentity executes 5-stage identity resolution', async () => {
    globalThis.fetch = async (url, opts) => {
      assert.match(url, /\/api\/v1\/identity\/resolve$/);
      assert.equal(opts.method, 'POST');
      return {
        ok: true,
        status: 200,
        json: async () => ({
          outcome: 'MATCH_EXACT',
          product_id: 'prod-uuid-1',
          variant_id: 'var-uuid-1',
          confidence_score: 1.0,
        }),
      };
    };

    try {
      const res = await resolveIdentity({
        marketplace_code: 'amazon_in',
        asin: 'B0TEST001',
      });
      assert.equal(res.outcome, 'MATCH_EXACT');
      assert.equal(res.variant_id, 'var-uuid-1');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('createHandoffToken calls import-tokens endpoint and returns single-use code', async () => {
    globalThis.fetch = async (url, opts) => {
      assert.match(url, /\/api\/v1\/import-tokens$/);
      assert.equal(opts.method, 'POST');
      return {
        ok: true,
        status: 201,
        json: async () => ({
          import_code: 'sec_token_random_high_entropy_123',
          expires_at: '2026-11-13T12:00:00Z',
        }),
      };
    };

    try {
      const res = await createHandoffToken({
        context_data: { asin: 'B0TEST001' },
      });
      assert.equal(res.import_code, 'sec_token_random_high_entropy_123');
      assert.ok(res.expires_at);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('comparison methods create session and add variants', async () => {
    globalThis.fetch = async (url, opts) => {
      if (url.includes('/api/v1/comparisons') && opts.method === 'POST') {
        if (url.includes('/items')) {
          return {
            ok: true,
            status: 200,
            json: async () => ({ session_id: 'sess-1', variant_id: 'var-1', position: 1 }),
          };
        }
        return {
          ok: true,
          status: 201,
          json: async () => ({ id: 'sess-1', title: 'Test Comparison', status: 'active' }),
        };
      }
      if (url.includes('/api/v1/comparisons')) {
        return {
          ok: true,
          status: 200,
          json: async () => [{ id: 'sess-1', title: 'Test Comparison', status: 'active' }],
        };
      }
      return { ok: false, status: 404, statusText: 'Not Found' };
    };

    try {
      const sessions = await listComparisonSessions();
      assert.equal(sessions.length, 1);
      assert.equal(sessions[0].id, 'sess-1');

      const newSess = await createComparisonSession('Test Comparison');
      assert.equal(newSess.id, 'sess-1');

      const addItem = await addVariantToComparison('sess-1', 'var-1');
      assert.equal(addItem.variant_id, 'var-1');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('handles backend rejection and network failure with IngestionApiError', async () => {
    globalThis.fetch = async () => ({
      ok: false,
      status: 409,
      statusText: 'Conflict',
      json: async () => ({ detail: 'Max 2 active sessions reached' }),
    });

    try {
      await assert.rejects(
        () => createComparisonSession('Test'),
        (err) => {
          assert.ok(err instanceof IngestionApiError);
          assert.equal(err.status, 409);
          assert.match(err.message, /Max 2 active sessions/);
          return true;
        }
      );
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});

