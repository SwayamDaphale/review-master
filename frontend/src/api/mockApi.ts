import type { ApiClient } from './client';
import { FIXTURES, type Fixture } from './mockData';
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
} from '../types/api';
import type { ParsedIdentifier } from '../lib/identifiers';

const LATENCY =
  import.meta.env.MODE === 'test' ? 0 : Number(import.meta.env.VITE_MOCK_LATENCY_MS ?? 180);

const wait = (): Promise<void> =>
  LATENCY > 0 ? new Promise((resolve) => setTimeout(resolve, LATENCY)) : Promise.resolve();

const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

function summary(f: Fixture): ProductSummary {
  return {
    product: f.product,
    variant: f.variant,
    evaluation: f.evaluation,
    price: f.price,
    match_state: f.match_state,
  };
}

function view(f: Fixture): VariantView {
  return {
    product: f.product,
    variant: f.variant,
    match_state: f.match_state,
    specs: f.specs,
    evaluation: f.evaluation,
    explanation: f.explanation,
    community: f.community,
    expert: f.expert,
    offers: f.offers,
    marketplace_rating: f.rating,
    sample: true,
  };
}

function findVariant(id: string): Fixture {
  const f = FIXTURES.find((x) => x.variant.id === id);
  if (!f) throw new ApiError('not_found', 'This product variant was not found.');
  return f;
}

const norm = (s: string | null | undefined) => (s ?? '').toLowerCase().replace(/\s+/g, ' ').trim();

export const mockApi: ApiClient = {
  async listProducts(category?: Category) {
    await wait();
    return clone(FIXTURES.filter((f) => !category || f.product.category === category).map(summary));
  },

  async searchProducts(query: string, category?: Category) {
    await wait();
    const tokens = norm(query).split(' ').filter(Boolean);
    const rows = FIXTURES.filter((f) => !category || f.product.category === category).filter((f) => {
      if (tokens.length === 0) return true;
      const haystack = norm(
        `${f.product.name} ${f.product.manufacturer} ${f.product.model} ${f.variant.label} ${f.product.asin ?? ''}`,
      );
      return tokens.every((t) => haystack.includes(t));
    });
    return clone(rows.map(summary));
  },

  async lookupIdentifier(parsed: ParsedIdentifier): Promise<MatchResult> {
    await wait();
    if (parsed.kind === 'text') {
      return { match_state: 'unmatched', candidates: [], reason: 'This is not a product link or product ID.' };
    }
    if (parsed.kind === 'url' && !/(^|\.)amazon\.in$/i.test(parsed.host)) {
      return {
        match_state: 'unmatched',
        candidates: [],
        reason: 'Only Amazon India links are supported for now.',
      };
    }
    const asin = parsed.asin;
    if (!asin) {
      return { match_state: 'unmatched', candidates: [], reason: 'No product ID was found in this link.' };
    }
    const hits = FIXTURES.filter((f) => f.product.asin === asin);
    if (hits.length === 0) {
      return {
        match_state: 'unmatched',
        candidates: [],
        reason: `No evaluation exists yet for product ID ${asin}.`,
      };
    }
    const first = hits[0] as Fixture;
    return {
      match_state: first.match_state,
      candidates: clone(hits.map(summary)),
      reason: 'Matched by marketplace product ID.',
    };
  },

  async getProduct(productId: string): Promise<ProductDetail> {
    await wait();
    const rows = FIXTURES.filter((f) => f.product.id === productId);
    const first = rows[0];
    if (!first) throw new ApiError('not_found', 'This product was not found.');
    return clone({ product: first.product, variants: rows.map((r) => r.variant) });
  },

  async getVariantView(variantId: string) {
    await wait();
    return clone(view(findVariant(variantId)));
  },

  async getPriceHistory(variantId: string): Promise<PriceHistory> {
    await wait();
    return clone(findVariant(variantId).history);
  },

  async getSummaries(variantIds: string[]) {
    await wait();
    const rows = variantIds
      .map((id) => FIXTURES.find((f) => f.variant.id === id))
      .filter((f): f is Fixture => f !== undefined);
    return clone(rows.map(summary));
  },

  async compare(variantIds: string[]): Promise<ComparisonResult> {
    await wait();
    if (variantIds.length < 2) throw new ApiError('too_few', 'Choose at least two products to compare.');
    if (variantIds.length > 3) throw new ApiError('too_many', 'You can compare up to three products at a time.');
    const rows = variantIds.map(findVariant);
    const category = (rows[0] as Fixture).product.category;
    if (rows.some((r) => r.product.category !== category)) {
      throw new ApiError(
        'different_categories',
        'These products are in different categories. Compare products from the same category.',
      );
    }
    return clone({ category, items: rows.map(summary), views: rows.map(view) });
  },

  async matchExtracted(x: ExtractedSmartphone): Promise<MatchResult> {
    await wait();
    const brand = norm(x.brand);
    const model = norm(x.model_name);
    const sameModel = FIXTURES.filter(
      (f) => norm(f.product.manufacturer) === brand && norm(f.product.model) === model,
    );
    if (sameModel.length === 0) {
      return {
        match_state: 'unmatched',
        candidates: [],
        reason: 'This model is not in the catalogue yet, so there is no evaluation to show.',
      };
    }
    const cfg = (f: Fixture, key: 'ram_gb' | 'storage_gb') => f.variant.configuration[key];
    const exact = sameModel.filter(
      (f) =>
        (x.storage_gb === null || cfg(f, 'storage_gb') === x.storage_gb) &&
        (x.ram_gb === null || cfg(f, 'ram_gb') === undefined || cfg(f, 'ram_gb') === x.ram_gb),
    );
    if (exact.length === 1) {
      const hit = exact[0] as Fixture;
      const processorClear = x.processor !== null && norm(x.processor) !== 'others';
      const certain =
        x.storage_gb !== null && (x.ram_gb !== null || cfg(hit, 'ram_gb') === undefined) && processorClear;
      return {
        match_state: certain ? 'confirmed' : 'probable',
        candidates: clone([summary(hit)]),
        reason: certain
          ? 'Brand, model, memory, storage and processor all match one catalogue variant.'
          : 'Brand, model and storage match, but some details (memory or processor) were not captured clearly. The match is not confirmed.',
      };
    }
    return {
      match_state: 'ambiguous',
      candidates: clone(sameModel.map(summary)),
      reason: 'The model matches, but more than one variant could fit. Choose the right one.',
    };
  },

  async getCatalogProducts(params) {
    await wait();
    const rows = FIXTURES.filter((f) => !params?.category || f.product.category === params.category);
    const items = rows.map((f) => ({
      id: f.product.id,
      name: f.product.name,
      manufacturer: f.product.manufacturer,
      category: f.product.category,
      mpn: null,
      generation: null,
    }));
    return { items: clone(items), next_cursor: null };
  },

  async getCatalogProductDetail(productId: string) {
    await wait();
    const rows = FIXTURES.filter((f) => f.product.id === productId);
    const first = rows[0];
    if (!first) throw new ApiError('not_found', 'Product not found');
    return clone({
      product: {
        id: first.product.id,
        name: first.product.name,
        manufacturer: first.product.manufacturer,
        category: first.product.category,
        mpn: null,
        generation: null,
      },
      variants: rows.map((r) => ({
        id: r.variant.id,
        product_id: r.product.id,
        configuration: r.variant.configuration,
        label: r.variant.label,
      })),
    });
  },
};
