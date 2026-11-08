/**
 * Real HTTP API Client for Review Master FastAPI backend (/api/v1).
 * Communicates directly with PostgreSQL-backed catalog endpoints.
 */

import type { ApiClient } from './client';
import {
  ApiError,
  type Category,
  type ComparisonResult,
  type ExtractedSmartphone,
  type MatchResult,
  type PriceHistory,
  type ProductDetail,
  type ProductSummary,
  type VariantView,
  type CatalogSearchResult,
  type CatalogProductDetail,
} from '../types/api';
import type { ParsedIdentifier } from '../lib/identifiers';
import { STORAGE_KEYS, readStored } from '../lib/storage';

export interface AuthUser {
  id: string;
  email: string;
  display_name: string | null;
  roles: string[];
  is_active: boolean;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token?: string;
  csrf_token?: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

function getCsrfToken(): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(/(?:^|;\s*)rm_csrf_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export class HttpClient implements ApiClient {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;

  constructor(
    baseUrl: string = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
    timeoutMs = 5000,
  ) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
    this.timeoutMs = timeoutMs;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    const session = readStored<{ accessToken?: string } | null>(STORAGE_KEYS.session, null);
    const authHeaders: Record<string, string> = {};
    if (session?.accessToken) {
      authHeaders['Authorization'] = `Bearer ${session.accessToken}`;
    }

    if (path.startsWith('/api/v1/auth/refresh') || path.startsWith('/api/v1/auth/logout')) {
      const csrf = getCsrfToken();
      if (csrf) {
        authHeaders['X-CSRF-Token'] = csrf;
      }
    }

    try {
      const response = await fetch(url, {
        ...options,
        credentials: 'include',
        signal: controller.signal,
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          ...authHeaders,
          ...options.headers,
        },
      });

      if (!response.ok) {
        if (response.status === 404) {
          throw new ApiError('not_found', `Resource at ${path} was not found.`);
        }
        if (response.status === 429) {
          throw new ApiError('rate_limited', 'Too many requests. Please try again shortly.');
        }
        if (response.status >= 500) {
          throw new ApiError('server_error', `Backend error (${response.status}): ${response.statusText}`);
        }
        let detail = response.statusText;
        try {
          const body = await response.json();
          if (body?.detail) {
            detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
          }
        } catch {
          // ignore json parse error on error body
        }
        throw new ApiError('bad_request', detail);
      }

      return (await response.json()) as T;
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        throw err;
      }
      if (err instanceof DOMException && err.name === 'AbortError') {
        throw new ApiError('timeout', `Request to ${path} timed out after ${this.timeoutMs}ms.`);
      }
      throw new ApiError('network_error', (err as Error).message || 'Failed to connect to backend.');
    } finally {
      clearTimeout(timer);
    }
  }

  // --- Real Catalog Endpoints (Phase B2) ---

  async getCatalogProducts(params?: {
    q?: string;
    category?: Category;
    limit?: number;
    cursor?: string;
  }): Promise<CatalogSearchResult> {
    const searchParams = new URLSearchParams();
    if (params?.q) searchParams.set('q', params.q);
    if (params?.category) searchParams.set('category', params.category);
    if (params?.limit) searchParams.set('limit', String(params.limit));
    if (params?.cursor) searchParams.set('cursor', params.cursor);

    const qs = searchParams.toString();
    const path = `/api/v1/products${qs ? `?${qs}` : ''}`;
    return this.request<CatalogSearchResult>(path);
  }

  async getCatalogProductDetail(productId: string): Promise<CatalogProductDetail> {
    return this.request<CatalogProductDetail>(`/api/v1/products/${encodeURIComponent(productId)}`);
  }

  async getProduct(productId: string): Promise<ProductDetail> {
    const detail = await this.getCatalogProductDetail(productId);
    return {
      product: {
        id: detail.product.id,
        name: detail.product.name,
        manufacturer: detail.product.manufacturer,
        model: detail.product.name,
        category: detail.product.category as Category,
        mpn: detail.product.mpn ?? undefined,
      },
      variants: detail.variants.map((v) => ({
        id: v.id,
        product_id: v.product_id,
        label: v.label,
        configuration: v.configuration as Record<string, string | number>,
      })),
    };
  }

  async listProducts(category?: Category): Promise<ProductSummary[]> {
    const catalog = await this.getCatalogProducts({ category });
    return catalog.items.map((item) => ({
      product: {
        id: item.id,
        name: item.name,
        manufacturer: item.manufacturer,
        model: item.name,
        category: item.category as Category,
        mpn: item.mpn ?? undefined,
      },
      variant: {
        id: `unevaluated-${item.id}`,
        product_id: item.id,
        label: 'Standard',
        configuration: {},
      },
      evaluation: {
        evaluation_id: `none-${item.id}`,
        variant_id: `unevaluated-${item.id}`,
        model: { name: 'Review Master V1', version: 'pending' },
        overall_score: null,
        confidence: {
          state: 'insufficient_evidence',
          score: 0,
          coverage: 0,
          reasons: ['Catalog item not yet evaluated'],
        },
        parameters: [],
        limitations: ['Evaluation models scheduled for Phase B3/B4'],
        created_at: new Date().toISOString(),
      },
      price: null,
      match_state: 'unmatched',
    }));
  }

  async searchProducts(query: string, category?: Category): Promise<ProductSummary[]> {
    const catalog = await this.getCatalogProducts({ q: query, category });
    return catalog.items.map((item) => ({
      product: {
        id: item.id,
        name: item.name,
        manufacturer: item.manufacturer,
        model: item.name,
        category: item.category as Category,
        mpn: item.mpn ?? undefined,
      },
      variant: {
        id: `unevaluated-${item.id}`,
        product_id: item.id,
        label: 'Standard',
        configuration: {},
      },
      evaluation: {
        evaluation_id: `none-${item.id}`,
        variant_id: `unevaluated-${item.id}`,
        model: { name: 'Review Master V1', version: 'pending' },
        overall_score: null,
        confidence: {
          state: 'insufficient_evidence',
          score: 0,
          coverage: 0,
          reasons: ['Catalog item not yet evaluated'],
        },
        parameters: [],
        limitations: ['Evaluation models scheduled for Phase B3/B4'],
        created_at: new Date().toISOString(),
      },
      price: null,
      match_state: 'unmatched',
    }));
  }

  // --- Real Extraction & Evidence Endpoints (Phase B3) ---

  async submitExtraction(payload: unknown): Promise<unknown> {
    return this.request<unknown>('/api/v1/extractions/smartphones', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async matchExtracted(extracted: ExtractedSmartphone): Promise<MatchResult> {
    const searchTarget = extracted.model_name || extracted.brand || '';
    const catalog = await this.getCatalogProducts({ q: searchTarget, category: 'smartphone' });

    if (catalog.items.length === 0) {
      return {
        match_state: 'unmatched',
        candidates: [],
        reason: `No canonical product found matching "${searchTarget}".`,
      };
    }

    const exactProduct =
      catalog.items.find(
        (item) =>
          item.name.toLowerCase() === (extracted.model_name || '').toLowerCase() ||
          item.name.toLowerCase().includes((extracted.model_name || '').toLowerCase()),
      ) || catalog.items[0];

    const detail = await this.getCatalogProductDetail(exactProduct.id);

    const matchingVariants = detail.variants.filter((v) => {
      const cfg = v.configuration as Record<string, unknown>;
      const ramMatches =
        extracted.ram_gb === null || cfg.ram_gb === undefined || Number(cfg.ram_gb) === Number(extracted.ram_gb);
      const storageMatches =
        extracted.storage_gb === null ||
        cfg.storage_gb === undefined ||
        Number(cfg.storage_gb) === Number(extracted.storage_gb);
      return ramMatches && storageMatches;
    });

    const isConfirmed = matchingVariants.length === 1 && extracted.storage_gb !== null;
    const matchState = isConfirmed ? 'confirmed' : matchingVariants.length > 0 ? 'probable' : 'unmatched';

    const candidates: ProductSummary[] = (matchingVariants.length > 0 ? matchingVariants : detail.variants.slice(0, 1)).map(
      (v) => ({
        product: {
          id: detail.product.id,
          name: detail.product.name,
          manufacturer: detail.product.manufacturer,
          model: detail.product.name,
          category: detail.product.category as Category,
          mpn: detail.product.mpn ?? undefined,
        },
        variant: {
          id: v.id,
          product_id: v.product_id,
          label: v.label,
          configuration: v.configuration as Record<string, string | number>,
        },
        evaluation: {
          evaluation_id: `none-${v.id}`,
          variant_id: v.id,
          model: { name: 'Review Master V1', version: 'pending' },
          overall_score: null,
          confidence: {
            state: 'insufficient_evidence',
            score: 0,
            coverage: 0,
            reasons: ['Catalog item not yet evaluated'],
          },
          parameters: [],
          limitations: ['Evaluation pending laboratory test evidence'],
          created_at: new Date().toISOString(),
        },
        price: extracted.price_amount !== null ? extracted.price_amount : null,
        match_state: matchState,
      }),
    );

    return {
      match_state: matchState,
      candidates,
      reason: isConfirmed
        ? `Confirmed match for ${detail.product.name} (${matchingVariants[0].label}).`
        : `Identified product ${detail.product.name}, but exact hardware configuration requires confirmation.`,
    };
  }

  // --- Endpoints Deferred to Subsequent Phases ---

  async lookupIdentifier(_parsed: ParsedIdentifier): Promise<MatchResult> {
    throw new ApiError('not_implemented', 'Marketplace listing identifier lookup is scheduled for Phase B4.');
  }

  async getVariantView(_variantId: string): Promise<VariantView> {
    throw new ApiError('not_implemented', 'Variant evaluation view is scheduled for Phase B4.');
  }

  async getPriceHistory(_variantId: string): Promise<PriceHistory> {
    throw new ApiError('not_implemented', 'Price history tracking is scheduled for Phase B4.');
  }

  async getSummaries(_variantIds: string[]): Promise<ProductSummary[]> {
    throw new ApiError('not_implemented', 'Batch evaluated summaries are scheduled for Phase B4.');
  }

  async compare(_variantIds: string[]): Promise<ComparisonResult> {
    throw new ApiError('not_implemented', 'Product comparison service is scheduled for Phase B4.');
  }

  // --- Authentication Endpoints (Phase B4) ---

  async register(email: string, password: string, displayName?: string): Promise<AuthTokens> {
    return this.request<AuthTokens>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, display_name: displayName }),
    });
  }

  async login(email: string, password: string): Promise<AuthTokens> {
    return this.request<AuthTokens>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  }

  async logout(): Promise<{ status: string; message: string }> {
    return this.request<{ status: string; message: string }>('/api/v1/auth/logout', {
      method: 'POST',
    });
  }

  async refresh(): Promise<AuthTokens> {
    return this.request<AuthTokens>('/api/v1/auth/refresh', {
      method: 'POST',
    });
  }

  async getMe(): Promise<AuthUser> {
    return this.request<AuthUser>('/api/v1/auth/me');
  }
}

export const httpClient = new HttpClient();
