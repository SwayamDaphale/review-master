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

  it('throws not_implemented for deferred endpoints without falling back to mock fixtures', async () => {
    const client = new HttpClient('http://localhost:8000');

    await expect(client.getSummaries(['v1', 'v2'])).rejects.toThrow(ApiError);
    await expect(client.getSummaries(['v1', 'v2'])).rejects.toMatchObject({
      code: 'not_implemented',
    });

    await expect(client.getPriceHistory('v1')).rejects.toThrow(ApiError);
    await expect(client.getPriceHistory('v1')).rejects.toMatchObject({
      code: 'not_implemented',
    });
  });
});
