import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HttpClient } from './httpClient';
import { ApiError } from '../types/api';

describe('HttpClient', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('handles base URL without trailing slash', async () => {
    const client = new HttpClient('http://api.test:8000///');
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], next_cursor: null }),
    });
    globalThis.fetch = mockFetch;

    await client.getCatalogProducts();
    expect(mockFetch).toHaveBeenCalledWith(
      'http://api.test:8000/api/v1/products',
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: 'application/json',
        }),
      }),
    );
  });

  it('performs successful product listing', async () => {
    const client = new HttpClient('http://localhost:8000');
    const mockData = {
      items: [
        {
          id: '11111111-1111-1111-1111-111111111111',
          name: 'Samsung Galaxy S24 Ultra',
          manufacturer: 'Samsung',
          category: 'smartphone',
          generation: '2024',
          mpn: 'SM-S928B',
        },
      ],
      next_cursor: null,
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockData,
    });

    const result = await client.getCatalogProducts();
    expect(result.items).toHaveLength(1);
    expect(result.items[0].name).toBe('Samsung Galaxy S24 Ultra');
    expect(result.items[0].category).toBe('smartphone');
  });

  it('encodes search query and category parameters correctly', async () => {
    const client = new HttpClient('http://localhost:8000');
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], next_cursor: null }),
    });
    globalThis.fetch = mockFetch;

    await client.getCatalogProducts({ q: 'thinkpad x1', category: 'laptop', limit: 25, cursor: 'cur-123' });
    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/products?q=thinkpad+x1&category=laptop&limit=25&cursor=cur-123',
      expect.anything(),
    );
  });

  it('retrieves product detail and attached variants', async () => {
    const client = new HttpClient('http://localhost:8000');
    const mockDetail = {
      product: {
        id: 'p-1',
        name: 'iPhone 16 Pro',
        manufacturer: 'Apple',
        category: 'smartphone',
        generation: '16',
        mpn: 'MYNE3HN/A',
      },
      variants: [
        {
          id: 'v-1',
          product_id: 'p-1',
          configuration: { storage_gb: 128 },
          label: 'Apple iPhone 16 Pro 128GB',
        },
      ],
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockDetail,
    });

    const result = await client.getProduct('p-1');
    expect(result.product.id).toBe('p-1');
    expect(result.variants).toHaveLength(1);
    expect(result.variants[0].label).toBe('Apple iPhone 16 Pro 128GB');
  });

  it('submits extraction snapshot to /api/v1/extractions/smartphones', async () => {
    const client = new HttpClient('http://localhost:8000');
    const mockResponse = {
      status: 'success',
      record_id: 'rec-123',
      listing_id: 'list-456',
      match_state: 'confirmed',
    };
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockResponse,
    });
    globalThis.fetch = mockFetch;

    const payload = { schema_version: '1.0' };
    const res = await client.submitExtraction(payload);
    expect(res).toEqual(mockResponse);
    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/extractions/smartphones',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    );
  });

  it('matches extracted smartphone against canonical catalog', async () => {
    const client = new HttpClient('http://localhost:8000');
    const mockCatalog = {
      items: [
        {
          id: 'prod-s24',
          name: 'Samsung Galaxy S24 Ultra',
          manufacturer: 'Samsung',
          category: 'smartphone',
        },
      ],
      next_cursor: null,
    };
    const mockDetail = {
      product: {
        id: 'prod-s24',
        name: 'Samsung Galaxy S24 Ultra',
        manufacturer: 'Samsung',
        category: 'smartphone',
      },
      variants: [
        {
          id: 'var-256',
          product_id: 'prod-s24',
          configuration: { ram_gb: 12, storage_gb: 256 },
          label: 'Samsung Galaxy S24 Ultra 256GB',
        },
      ],
    };

    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockCatalog,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockDetail,
      });

    const matchResult = await client.matchExtracted({
      category: 'smartphone',
      brand: 'Samsung',
      model_name: 'Galaxy S24 Ultra',
      model_number: null,
      ram_gb: 12,
      storage_gb: 256,
      display_size_inches: 6.8,
      battery_capacity_mah: 5000,
      operating_system: 'Android 14',
      processor: 'Snapdragon 8 Gen 3',
      supports_5g: true,
      price_amount: 129999,
      currency: 'INR',
      rating: 4.5,
      review_count: 500,
      availability: 'in_stock',
    });

    expect(matchResult.match_state).toBe('confirmed');
    expect(matchResult.candidates).toHaveLength(1);
    expect(matchResult.candidates[0].variant.id).toBe('var-256');
  });

  it('throws ApiError with not_found on HTTP 404', async () => {
    const client = new HttpClient('http://localhost:8000');
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({ detail: "Product with id '000' was not found" }),
    });

    await expect(client.getProduct('000')).rejects.toThrow(ApiError);
    await expect(client.getProduct('000')).rejects.toMatchObject({
      code: 'not_found',
    });
  });

  it('throws ApiError with server_error on HTTP 500', async () => {
    const client = new HttpClient('http://localhost:8000');
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: async () => ({ detail: 'Database connection failed' }),
    });

    await expect(client.getCatalogProducts()).rejects.toThrow(ApiError);
    await expect(client.getCatalogProducts()).rejects.toMatchObject({
      code: 'server_error',
    });
  });

  it('handles network connection error without silent mock fallback', async () => {
    const client = new HttpClient('http://localhost:8000');
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('Failed to fetch'));

    await expect(client.getCatalogProducts()).rejects.toThrow(ApiError);
    await expect(client.getCatalogProducts()).rejects.toMatchObject({
      code: 'network_error',
    });
  });

  it('performs real variant view retrieval and synthesis', async () => {
    const client = new HttpClient('http://localhost:8000');
    const mockVariantData = {
      variant: { id: 'var-1', product_id: 'prod-1', label: '8GB/128GB', configuration: { ram_gb: 8, storage_gb: 128 } },
      product: { id: 'prod-1', name: 'Test Smartphone', manufacturer: 'Acme', category: 'smartphone' },
    };
    const mockEval = {
      id: 'eval-1',
      overall_score: '85.50',
      confidence_state: 'high',
      confidence_score: '0.90',
      coverage: '0.95',
      parameter_results: [
        { parameter_key: 'display', status: 'scored', score: '88.0', effective_weight: '0.2', is_critical: false },
      ],
      created_at: new Date().toISOString(),
    };

    globalThis.fetch = vi.fn().mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/products/variants/var-1')) {
        return { ok: true, status: 200, json: async () => mockVariantData };
      }
      if (url.includes('/api/v1/variants/var-1/evaluations/latest')) {
        return { ok: true, status: 200, json: async () => mockEval };
      }
      if (url.includes('/api/v1/evidence')) {
        return { ok: true, status: 200, json: async () => ({ items: [] }) };
      }
      if (url.includes('/api/v1/products/prod-1/listings')) {
        return { ok: true, status: 200, json: async () => [] };
      }
      return { ok: false, status: 404, statusText: 'Not Found', json: async () => ({}) };
    });

    const view = await client.getVariantView('var-1');
    expect(view.product.name).toBe('Test Smartphone');
    expect(view.variant.label).toBe('8GB/128GB');
    expect(view.evaluation.overall_score).toBe(85.5);
    expect(view.evaluation.confidence.state).toBe('high');
    expect(view.evaluation.parameters).toHaveLength(1);
    expect(view.evaluation.parameters[0].key).toBe('display');
  });

  it('performs create and consume of single-use import handoff token', async () => {
    const client = new HttpClient('http://localhost:8000');
    globalThis.fetch = vi.fn().mockImplementation(async (url: string, opts: any) => {
      if (url.includes('/api/v1/import-tokens/consume')) {
        const body = JSON.parse(opts.body);
        if (body.import_code === 'valid-token') {
          return {
            ok: true,
            status: 200,
            json: async () => ({
              status: 'consumed',
              job_id: 'job-123',
              consumed_at: new Date().toISOString(),
            }),
          };
        }
        return { ok: false, status: 409, statusText: 'Conflict', json: async () => ({ detail: 'Already consumed' }) };
      }
      if (url.includes('/api/v1/import-tokens')) {
        return {
          ok: true,
          status: 201,
          json: async () => ({ import_code: 'valid-token', expires_at: new Date().toISOString() }),
        };
      }
      return { ok: false, status: 404, statusText: 'Not Found', json: async () => ({}) };
    });

    const tokenRes = await client.createImportToken({ context_data: { source: 'test' } });
    expect(tokenRes.import_code).toBe('valid-token');

    const consumeRes = await client.consumeImportToken('valid-token');
    expect(consumeRes.status).toBe('consumed');
    expect(consumeRes.job_id).toBe('job-123');

    await expect(client.consumeImportToken('used-token')).rejects.toMatchObject({
      code: 'conflict',
    });
  });
});
