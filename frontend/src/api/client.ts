import type {
  ComparisonResult,
  ExtractedSmartphone,
  MatchResult,
  PriceHistory,
  ProductDetail,
  ProductSummary,
  VariantView,
  Category,
  CatalogSearchResult,
  CatalogProductDetail,
} from '../types/api';
import type { ParsedIdentifier } from '../lib/identifiers';

/**
 * The contract the UI depends on. It follows docs/api/openapi.yaml.
 * `mockApi` implements demo fixtures. `httpClient` communicates with FastAPI /api/v1.
 */
export interface ApiClient {
  listProducts(category?: Category): Promise<ProductSummary[]>;
  searchProducts(query: string, category?: Category): Promise<ProductSummary[]>;
  lookupIdentifier(parsed: ParsedIdentifier): Promise<MatchResult>;
  getProduct(productId: string): Promise<ProductDetail>;
  getVariantView(variantId: string): Promise<VariantView>;
  getPriceHistory(variantId: string): Promise<PriceHistory>;
  getSummaries(variantIds: string[]): Promise<ProductSummary[]>;
  compare(variantIds: string[]): Promise<ComparisonResult>;
  matchExtracted(extracted: ExtractedSmartphone): Promise<MatchResult>;
  submitExtraction?(payload: unknown): Promise<unknown>;

  // Catalog-specific endpoints (Phase B2)
  getCatalogProducts(params?: {
    q?: string;
    category?: Category;
    limit?: number;
    cursor?: string;
  }): Promise<CatalogSearchResult>;
  getCatalogProductDetail(productId: string): Promise<CatalogProductDetail>;

  // B10 Recommendations
  parseRequirements?(query: string, categoryHint?: string): Promise<unknown>;
  generateRecommendations?(payload: unknown): Promise<unknown>;
}
