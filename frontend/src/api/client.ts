import type {
  ComparisonResult,
  ExtractedSmartphone,
  MatchResult,
  PriceHistory,
  ProductDetail,
  ProductSummary,
  VariantView,
  Category,
} from '../types/api';
import type { ParsedIdentifier } from '../lib/identifiers';

/**
 * The contract the UI depends on. It follows architecture/api/openapi.yaml.
 * Today `mockApi` implements it. When the FastAPI backend exists, write an
 * implementation that calls /api/v1 and switch it in src/api/index.ts.
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
}
