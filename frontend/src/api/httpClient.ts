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
  type Offer,
  type SpecItem,
  type Evaluation,
  type CatalogSearchResult,
  type CatalogProductDetail,
  type ApiComparisonMatrixResponse,
  type ApiRecommendationResponse,
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

interface LatestEvalResponse {
  id?: string;
  calculation_policy_version?: string;
  overall_score?: number | string | null;
  confidence_state?: string;
  confidence_score?: number | string | null;
  coverage?: number | string | null;
  limitations?: { reasons?: string[]; notes?: string[] };
  parameter_results?: Array<{
    parameter_key: string;
    status: string;
    score: number | string | null;
    weight: number | string | null;
    effective_weight: number | string | null;
    is_critical: boolean;
    evidence_ids?: string[];
    explanation_data?: { summary?: string };
  }>;
  created_at?: string;
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
        let detail = response.statusText;
        try {
          const body = await response.json();
          if (body?.detail) {
            detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
          }
        } catch {
          // ignore json parse error on error body
        }

        if (response.status === 400) {
          throw new ApiError('bad_request', detail);
        }
        if (response.status === 401) {
          // Attempt auto-refresh for expired bearer token if not an auth endpoint
          if (!(options as { _isRetry?: boolean })._isRetry && !path.startsWith('/api/v1/auth/')) {
            try {
              const newTokens = await this.refresh();
              if (newTokens?.access_token) {
                const currentSession = readStored<{ accessToken?: string } | null>(STORAGE_KEYS.session, null);
                if (currentSession) {
                  currentSession.accessToken = newTokens.access_token;
                  localStorage.setItem(STORAGE_KEYS.session, JSON.stringify(currentSession));
                }
                return await this.request<T>(path, { ...options, _isRetry: true } as RequestInit);
              }
            } catch {
              // Refresh failed, proceed with unauthorized error
            }
          }
          throw new ApiError('unauthorized', detail || 'Authentication required.');
        }
        if (response.status === 403) {
          throw new ApiError('forbidden', detail || 'Access forbidden.');
        }
        if (response.status === 404) {
          throw new ApiError('not_found', detail || `Resource at ${path} was not found.`);
        }
        if (response.status === 409) {
          throw new ApiError('conflict', detail || 'Resource state conflict.');
        }
        if (response.status === 422) {
          throw new ApiError('validation_error', detail || 'Request validation error.');
        }
        if (response.status === 429) {
          throw new ApiError('rate_limited', 'Too many requests. Please try again shortly.');
        }
        if (response.status >= 500) {
          throw new ApiError('server_error', `Backend error (${response.status}): ${response.statusText}`);
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

  // --- Real Identifier, Variant & Summary Endpoints ---

  async lookupIdentifier(parsed: ParsedIdentifier): Promise<MatchResult> {
    const catalog = await this.getCatalogProducts({ q: parsed.value });
    if (!catalog.items || catalog.items.length === 0) {
      return {
        match_state: 'unmatched',
        candidates: [],
        reason: `No canonical product found for identifier "${parsed.value}".`,
      };
    }
    const product = catalog.items[0];
    const detail = await this.getCatalogProductDetail(product.id);
    const candidates = detail.variants.map((v) => ({
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
        evaluation_id: `eval-${v.id}`,
        variant_id: v.id,
        model: { name: 'Review Master V1', version: 'pending' },
        overall_score: null,
        confidence: {
          state: 'insufficient_evidence' as const,
          score: 0,
          coverage: 0,
          reasons: ['Evaluation pending evidence collection'],
        },
        parameters: [],
        limitations: [],
        created_at: new Date().toISOString(),
      },
      price: null,
      match_state: 'probable' as const,
    }));
    return {
      match_state: 'probable',
      candidates,
      reason: `Found matching product family for ${product.name}.`,
    };
  }

  async getVariantView(variantId: string): Promise<VariantView> {
    // 1. Fetch variant and parent product
    const variantData = await this.request<{
      variant: { id: string; product_id: string; label: string; configuration: Record<string, unknown> };
      product: { id: string; name: string; manufacturer: string; category: string; mpn?: string; generation?: string };
    }>(`/api/v1/products/variants/${encodeURIComponent(variantId)}`);

    const product = variantData.product;
    const variant = variantData.variant;
    const categoryKey = (product.category || 'smartphone') as Category;

    // 2. Fetch latest evaluation (if available)
    let evalData: LatestEvalResponse | null = null;
    try {
      evalData = await this.request<LatestEvalResponse>(
        `/api/v1/variants/${encodeURIComponent(variantId)}/evaluations/latest`
      );
    } catch {
      evalData = null;
    }

    // 3. Fetch evidence records (if available)
    let evidenceItems: Array<{ parameter_key?: string; raw_value?: unknown; source_type?: string }> = [];
    try {
      const evRes = await this.request<{ items: typeof evidenceItems }>(
        `/api/v1/evidence?variant_id=${encodeURIComponent(variantId)}`
      );
      evidenceItems = evRes.items || [];
    } catch {
      evidenceItems = [];
    }

    // 4. Fetch marketplace listings/offers (if available)
    let listings: Array<{
      id?: string;
      listing_id?: string;
      seller_name?: string;
      marketplace_name?: string;
      price?: number | string;
      currency?: string;
      is_available?: boolean;
      marketplace_code?: string;
      observed_at?: string;
      created_at?: string;
    }> = [];
    try {
      listings = await this.request<typeof listings>(
        `/api/v1/products/${encodeURIComponent(product.id)}/listings`
      );
    } catch {
      listings = [];
    }

    const offers: Offer[] = (listings || []).map((l) => ({
      offer_id: l.id || l.listing_id || 'offer-1',
      seller: l.seller_name || l.marketplace_name || 'Marketplace Seller',
      price: l.price ? Number(l.price) : 0,
      currency: l.currency || 'INR',
      availability: l.is_available ? 'in_stock' : 'out_of_stock',
      source: l.marketplace_code || 'amazon_in',
      observed_at: l.observed_at || l.created_at || new Date().toISOString(),
      stale: false,
    }));

    // 5. Build specs from variant configuration and evidence
    const specs: SpecItem[] = [];
    const cfg = (variant.configuration || {}) as Record<string, unknown>;
    for (const [k, v] of Object.entries(cfg)) {
      if (v !== undefined) {
        specs.push({
          key: k,
          label: k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
          value: v === null ? null : String(v),
          source: 'canonical_catalog',
        });
      }
    }
    for (const ev of evidenceItems) {
      if (ev.parameter_key && !specs.some((s) => s.key === ev.parameter_key)) {
        specs.push({
          key: ev.parameter_key,
          label: ev.parameter_key.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()),
          value: ev.raw_value ? String(ev.raw_value) : null,
          source: `evidence_${ev.source_type || 'external'}`,
        });
      }
    }

    // 6. Assemble Evaluation object
    let evaluation: Evaluation;
    if (evalData) {
      evaluation = {
        evaluation_id: evalData.id || `eval-${variantId}`,
        variant_id: variantId,
        model: {
          name: 'Review Master Evaluation Model',
          version: evalData.calculation_policy_version || 'v1.0',
        },
        overall_score: evalData.overall_score !== null && evalData.overall_score !== undefined ? Number(evalData.overall_score) : null,
        confidence: {
          state: (evalData.confidence_state as any) || 'insufficient_evidence',
          score: evalData.confidence_score !== null && evalData.confidence_score !== undefined ? Number(evalData.confidence_score) : 0,
          coverage: evalData.coverage !== null && evalData.coverage !== undefined ? Number(evalData.coverage) : 0,
          reasons: Array.isArray(evalData.limitations?.reasons) ? evalData.limitations.reasons : [],
        },
        parameters: (evalData.parameter_results || []).map((p) => ({
          key: p.parameter_key,
          name: p.parameter_key.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()),
          status: p.status === 'scored' ? 'scored' : p.status === 'conflicted' ? 'conflicted' : 'not_scored',
          score: p.score !== null && p.score !== undefined ? Number(p.score) : null,
          weight: p.effective_weight !== null && p.effective_weight !== undefined
            ? Number(p.effective_weight)
            : (p.weight !== null && p.weight !== undefined ? Number(p.weight) : null),
          is_critical: Boolean(p.is_critical),
          evidence: (p.evidence_ids || []).map((eid: string) => ({
            evidence_id: eid,
            source_type: 'independent_test' as const,
            trust_tier: 1 as const,
            label: 'Laboratory Benchmark / Specification Evidence',
            observed_at: evalData?.created_at || new Date().toISOString(),
            verification_state: 'verified' as const,
          })),
          note: p.explanation_data?.summary || undefined,
        })),
        limitations: Array.isArray(evalData.limitations?.notes) ? evalData.limitations.notes : [],
        created_at: evalData.created_at || new Date().toISOString(),
      };
    } else {
      evaluation = {
        evaluation_id: `pending-${variantId}`,
        variant_id: variantId,
        model: { name: 'Review Master Evaluation Engine', version: 'pending' },
        overall_score: null,
        confidence: {
          state: 'insufficient_evidence',
          score: 0,
          coverage: 0,
          reasons: ['Variant not yet evaluated by laboratory testing pipeline'],
        },
        parameters: [],
        limitations: ['Evaluation pending evidence ingestion and quality scoring'],
        created_at: new Date().toISOString(),
      };
    }

    return {
      product: {
        id: product.id,
        name: product.name,
        manufacturer: product.manufacturer,
        model: product.name,
        category: categoryKey,
        mpn: product.mpn,
        generation: product.generation,
      },
      variant: {
        id: variant.id,
        product_id: variant.product_id,
        label: variant.label,
        configuration: variant.configuration as Record<string, string | number>,
      },
      match_state: 'confirmed',
      specs,
      evaluation,
      explanation: {
        text: 'Review Master scores are determined mathematically from verified hardware evidence and empirical tests.',
        ai_generated: false,
        mode: 'template',
        referenced_parameters: [],
      },
      community: {
        status: 'unavailable',
        sample_size: 0,
        themes: [],
        review_quality_signals: [],
        ai_generated: false,
      },
      expert: {
        status: 'published',
        findings: [],
      },
      offers,
      marketplace_rating: null,
      sample: false,
    };
  }

  async getPriceHistory(variantId: string): Promise<PriceHistory> {
    try {
      const view = await this.getVariantView(variantId);
      const points = (view.offers || [])
        .filter((o) => o.price > 0)
        .map((o) => ({ observed_at: o.observed_at, price: o.price }));
      return {
        points,
        windows: { '30': null, '90': null },
        coverage_days: points.length > 0 ? 1 : 0,
      };
    } catch {
      return {
        points: [],
        windows: { '30': null, '90': null },
        coverage_days: 0,
      };
    }
  }

  async getSummaries(variantIds: string[]): Promise<ProductSummary[]> {
    const views = await Promise.all(
      variantIds.map((id) =>
        this.getVariantView(id).catch(() => null)
      )
    );
    return views
      .filter((v): v is VariantView => v !== null)
      .map((v) => ({
        product: v.product,
        variant: v.variant,
        evaluation: v.evaluation,
        price: v.offers[0]?.price ?? null,
        match_state: 'confirmed',
      }));
  }

  async compare(variantIds: string[]): Promise<ComparisonResult> {
    if (!variantIds || variantIds.length === 0) {
      throw new ApiError('invalid_argument', 'Select at least one product to compare.');
    }
    const session = await this.request<{ id: string; status: string }>('/api/v1/comparisons', {
      method: 'POST',
      body: JSON.stringify({ title: 'Product Comparison' }),
    });

    for (const vId of variantIds) {
      await this.request(`/api/v1/comparisons/${session.id}/items`, {
        method: 'POST',
        body: JSON.stringify({ variant_id: vId }),
      });
    }

    const matrix = await this.request<ApiComparisonMatrixResponse>(
      `/api/v1/comparisons/${session.id}/matrix`
    );

    const categoryKey = (matrix.category_key || 'smartphone') as Category;
    const items: ProductSummary[] = matrix.items.map((i) => ({
      product: {
        id: i.product_id,
        category: categoryKey,
        name: i.product_name,
        manufacturer: i.manufacturer,
        model: i.product_name,
        model_name: i.product_name,
        generation: undefined,
        model_number: undefined,
      },
      variant: {
        id: i.variant_id,
        product_id: i.product_id,
        label: i.sku_label,
        configuration: {},
      },
      evaluation: {
        evaluation_id: i.evaluation.evaluation_id || i.variant_id,
        variant_id: i.variant_id,
        model: { name: 'Category Evaluation Model', version: i.evaluation.model_version || 'v1' },
        overall_score: i.evaluation.overall_score,
        confidence: {
          state: (i.evaluation.confidence_state as any) || 'unavailable',
          score: i.evaluation.confidence_score ?? 0,
          coverage: i.evaluation.coverage ?? 0,
          reasons: [],
        },
        parameters: i.evaluation.parameters.map((p) => ({
          key: p.key,
          name: p.name,
          score: p.score,
          weight: p.weight ?? 0,
          status: (p.status as any) || (p.score !== null ? 'scored' : 'not_scored'),
          is_critical: p.is_critical,
          evidence: [],
        })),
        limitations: [],
        created_at: new Date().toISOString(),
      },
      price: i.offer.current_price,
      match_state: 'exact' as any,
    }));

    const views: VariantView[] = matrix.items.map((i) => ({
      product: {
        id: i.product_id,
        category: categoryKey,
        name: i.product_name,
        manufacturer: i.manufacturer,
        model: i.product_name,
        model_name: i.product_name,
        generation: undefined,
        model_number: undefined,
      },
      variant: {
        id: i.variant_id,
        product_id: i.product_id,
        label: i.sku_label,
        configuration: {},
      },
      match_state: 'exact' as any,
      specs: Object.values(i.specifications).map((s) => ({
        key: s.key,
        label: s.display_label,
        value: s.is_missing ? null : String(s.canonical_value ?? s.raw_value ?? ''),
        unit: s.unit ?? undefined,
        source: 'catalog',
      })),
      evaluation: {
        evaluation_id: i.evaluation.evaluation_id || i.variant_id,
        variant_id: i.variant_id,
        model: { name: 'Category Evaluation Model', version: i.evaluation.model_version || 'v1' },
        overall_score: i.evaluation.overall_score,
        confidence: {
          state: (i.evaluation.confidence_state as any) || 'unavailable',
          score: i.evaluation.confidence_score ?? 0,
          coverage: i.evaluation.coverage ?? 0,
          reasons: [],
        },
        parameters: i.evaluation.parameters.map((p) => ({
          key: p.key,
          name: p.name,
          score: p.score,
          weight: p.weight ?? 0,
          status: (p.status as any) || (p.score !== null ? 'scored' : 'not_scored'),
          is_critical: p.is_critical,
          evidence: [],
        })),
        limitations: [],
        created_at: new Date().toISOString(),
      },
      explanation: {
        text: 'Scores are generated deterministically from verified evidence.',
        ai_generated: false,
        mode: 'template',
        referenced_parameters: [],
      },
      community: {
        status: i.community.total_reviews_analyzed > 0 ? 'available' : 'unavailable',
        sample_size: i.community.total_reviews_analyzed,
        themes: [],
        review_quality_signals: [],
        ai_generated: false,
      },
      expert: {
        status: 'published',
        findings: [],
      },
      offers: [],
      marketplace_rating: null,
      sample: false,
    }));

    return {
      category: categoryKey,
      items,
      views,
    };
  }

  // --- B10 Comparison & Recommendation Endpoints ---

  async createComparisonSession(title?: string, categoryId?: string) {
    return this.request('/api/v1/comparisons', {
      method: 'POST',
      body: JSON.stringify({ title, category_id: categoryId }),
    });
  }

  async listComparisonSessions(status?: string) {
    const q = status ? `?status=${encodeURIComponent(status)}` : '';
    return this.request(`/api/v1/comparisons${q}`);
  }

  async archiveComparisonSession(sessionId: string) {
    return this.request(`/api/v1/comparisons/${sessionId}/archive`, {
      method: 'POST',
    });
  }

  async getComparisonMatrix(sessionId: string, recalculate?: boolean): Promise<ApiComparisonMatrixResponse> {
    const q = recalculate ? '?recalculate=true' : '';
    return this.request<ApiComparisonMatrixResponse>(`/api/v1/comparisons/${sessionId}/matrix${q}`);
  }

  async parseRequirements(query: string, categoryHint?: string) {
    return this.request('/api/v1/recommendations/parse', {
      method: 'POST',
      body: JSON.stringify({ query, category_hint: categoryHint }),
    });
  }

  async generateRecommendations(payload: {
    query?: string;
    requirements?: unknown;
    category_key?: string;
    category_id?: string;
    limit?: number;
  }): Promise<ApiRecommendationResponse> {
    return this.request<ApiRecommendationResponse>('/api/v1/recommendations', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getRecommendation(recommendationId: string): Promise<ApiRecommendationResponse> {
    return this.request<ApiRecommendationResponse>(`/api/v1/recommendations/${recommendationId}`);
  }

  // --- B11 Secure Import-Code Handoff Endpoints ---

  async createImportToken(payload: {
    job_id?: string;
    listing_id?: string;
    context_data?: Record<string, unknown>;
  }): Promise<{ import_code: string; expires_at: string }> {
    return this.request<{ import_code: string; expires_at: string }>('/api/v1/import-tokens', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async consumeImportToken(importCode: string): Promise<{
    status: string;
    job_id?: string;
    listing_id?: string;
    context?: string;
    job_status?: string;
    payload?: unknown;
    consumed_at: string;
  }> {
    return this.request<{
      status: string;
      job_id?: string;
      listing_id?: string;
      context?: string;
      job_status?: string;
      payload?: unknown;
      consumed_at: string;
    }>('/api/v1/import-tokens/consume', {
      method: 'POST',
      body: JSON.stringify({ import_code: importCode }),
    });
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
