// Types mirror docs/api/openapi.yaml (Evaluation, ParameterResult, EvidenceRef, Offer, ...).
// The UI only displays these values. It never computes a score.

export type Category = 'smartphone' | 'laptop' | 'external_ssd';

export const CATEGORY_LABEL: Record<Category, string> = {
  smartphone: 'Smartphones',
  laptop: 'Laptops',
  external_ssd: 'External SSDs',
};

export const CATEGORY_SINGULAR: Record<Category, string> = {
  smartphone: 'Smartphone',
  laptop: 'Laptop',
  external_ssd: 'External SSD',
};

export type ConfidenceState = 'high' | 'limited' | 'insufficient_evidence';
export type MatchState = 'confirmed' | 'probable' | 'ambiguous' | 'unmatched';
export type TrustTier = 1 | 2 | 3;
export type SourceType =
  | 'independent_test'
  | 'expert_test'
  | 'manufacturer'
  | 'marketplace'
  | 'community'
  | 'other_authorized';
export type VerificationState = 'unverified' | 'verified' | 'rejected' | 'withdrawn';

export interface EvidenceRef {
  evidence_id: string;
  source_type: SourceType;
  trust_tier: TrustTier;
  label: string;
  observed_at: string;
  verification_state: VerificationState;
}

export interface ParameterResult {
  key: string;
  name: string;
  status: 'scored' | 'not_scored' | 'conflicted';
  /** 0-100 as returned by the API, or null when not scored. Null is never shown as zero. */
  score: number | null;
  /** Share of the quality score this parameter carries (used only to size meter segments). */
  weight: number | null;
  is_critical: boolean;
  evidence: EvidenceRef[];
  note?: string;
}

export interface Confidence {
  state: ConfidenceState;
  /** 0-1 */
  score: number;
  /** 0-1 share of weight that has evidence */
  coverage: number;
  reasons: string[];
}

export interface Evaluation {
  evaluation_id: string;
  variant_id: string;
  model: { name: string; version: string };
  /** 0-100, or null when withheld (insufficient evidence) */
  overall_score: number | null;
  confidence: Confidence;
  parameters: ParameterResult[];
  limitations: string[];
  created_at: string;
}

export interface Explanation {
  text: string;
  ai_generated: boolean;
  mode: 'ai' | 'template';
  referenced_parameters: string[];
}

export interface Product {
  id: string;
  name: string;
  manufacturer: string;
  model: string;
  category: Category;
  asin?: string;
  mpn?: string;
  generation?: string;
}

export interface Variant {
  id: string;
  product_id: string;
  label: string;
  configuration: Record<string, string | number>;
}

export interface SpecItem {
  key: string;
  label: string;
  /** null means the value was not captured; shown as "Not captured", never as 0 */
  value: string | null;
  source: string;
}

export interface Offer {
  offer_id: string;
  seller: string;
  price: number;
  currency: string;
  availability: 'in_stock' | 'out_of_stock' | 'unknown';
  source: string;
  observed_at: string;
  stale: boolean;
}

export interface PricePoint {
  observed_at: string;
  price: number;
}

export interface PriceWindow {
  min: number;
  median: number;
  max: number;
}

export interface PriceHistory {
  points: PricePoint[];
  windows: { '30': PriceWindow | null; '90': PriceWindow | null };
  coverage_days: number;
}

export interface CommunityTheme {
  label: string;
  polarity: 'positive' | 'negative' | 'mixed';
  count: number;
}

export interface ReviewQualitySignal {
  signal_type: string;
  description: string;
  strength: 'low' | 'medium' | 'high';
}

export interface CommunityInsights {
  status: 'available' | 'not_enough_feedback' | 'unavailable';
  sample_size: number;
  themes: CommunityTheme[];
  review_quality_signals: ReviewQualitySignal[];
  ai_generated: boolean;
}

export interface ExpertAssessmentSummary {
  status: 'published' | 'none';
  expert_label?: string;
  published_at?: string;
  findings: { parameter: string; finding: string }[];
}

export interface MarketplaceRating {
  source: string;
  rating: number;
  count: number;
}

export interface ProductSummary {
  product: Product;
  variant: Variant;
  evaluation: Evaluation;
  price: number | null;
  match_state: MatchState;
}

export interface ProductDetail {
  product: Product;
  variants: Variant[];
}

export interface VariantView {
  product: Product;
  variant: Variant;
  match_state: MatchState;
  specs: SpecItem[];
  evaluation: Evaluation;
  explanation: Explanation;
  community: CommunityInsights;
  expert: ExpertAssessmentSummary;
  offers: Offer[];
  marketplace_rating: MarketplaceRating | null;
  /** True for demo fixtures. Real evaluations never set this. */
  sample: boolean;
}

export interface ComparisonResult {
  category: Category;
  items: ProductSummary[];
  views: VariantView[];
}

export interface ExtractedSmartphone {
  availability: string | null;
  battery_capacity_mah: number | null;
  brand: string | null;
  category: 'smartphone';
  currency: string | null;
  display_size_inches: number | null;
  model_name: string | null;
  model_number: string | null;
  operating_system: string | null;
  price_amount: number | null;
  processor: string | null;
  ram_gb: number | null;
  rating: number | null;
  review_count: number | null;
  storage_gb: number | null;
  supports_5g: boolean | null;
}

export interface MatchResult {
  match_state: MatchState;
  candidates: ProductSummary[];
  reason: string;
}

// --- B2 Catalog Schemas (directly mirroring PostgreSQL and FastAPI /api/v1/products) ---

export interface CatalogProduct {
  id: string;
  name: string;
  manufacturer: string;
  category: string;
  generation?: string | null;
  mpn?: string | null;
}

export interface CatalogVariant {
  id: string;
  product_id: string;
  configuration: Record<string, unknown>;
  label: string;
}

export interface CatalogProductDetail {
  product: CatalogProduct;
  variants: CatalogVariant[];
}

export interface CatalogSearchResult {
  items: CatalogProduct[];
  next_cursor: string | null;
}

export class ApiError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
  }
}

// --- B10 Comparison & Recommendation Schemas ---

export interface ApiComparisonMatrixResponse {
  session_id: string;
  title: string | null;
  status: string;
  category_id: string | null;
  category_name: string | null;
  category_key: string | null;
  item_count: number;
  specification_keys: { key: string; label: string }[];
  items: ApiComparisonMatrixItem[];
}

export interface ApiComparisonMatrixItem {
  variant_id: string;
  product_id: string;
  product_name: string;
  manufacturer: string;
  sku_label: string;
  position: number;
  specifications: Record<
    string,
    {
      key: string;
      display_label: string;
      raw_value: unknown;
      canonical_value: unknown;
      unit: string | null;
      is_missing: boolean;
    }
  >;
  evaluation: {
    evaluation_id: string | null;
    model_version: string | null;
    overall_score: number | null;
    confidence_state: string;
    confidence_score: number | null;
    coverage: number | null;
    parameters: {
      key: string;
      name: string;
      score: number | null;
      status: string;
      weight: number | null;
      is_critical: boolean;
    }[];
  };
  offer: {
    current_price: number | null;
    currency: string | null;
    seller: string | null;
    is_stale: boolean;
    is_available: boolean;
  };
  community: {
    total_reviews_analyzed: number;
    summary_text: string | null;
    key_pros: string[];
    key_cons: string[];
  };
}

export interface ApiRecommendationResponse {
  recommendation_id: string;
  category_id: string;
  category_key: string;
  query: string | null;
  parsed_requirements: {
    category_key: string;
    budget_max: number | null;
    budget_currency: string;
    hard_constraints: {
      attribute_key: string;
      operator: string;
      target_value: unknown;
      unit: string | null;
      description: string | null;
    }[];
    soft_preferences: {
      preference_key: string;
      preferred_direction: string;
      description: string | null;
    }[];
    excluded_brands: string[];
  };
  eligible_count: number;
  ineligible_count: number;
  ranked_recommendations: ApiRecommendedProductItem[];
  excluded_candidates: ApiExcludedProductItem[];
  ranking_policy_version: string;
  model_version: string | null;
  input_fingerprint: string;
  output_fingerprint: string;
  created_at: string;
}

export interface ApiRecommendedProductItem {
  rank: number;
  variant_id: string;
  product_id: string;
  product_name: string;
  manufacturer: string;
  sku_label: string;
  overall_score: number | null;
  confidence_state: string;
  confidence_score: number | null;
  coverage: number | null;
  current_price: number | null;
  currency: string | null;
  explanation: string;
  verified_specifications: Record<string, unknown>;
  community_summary: string | null;
}

export interface ApiExcludedProductItem {
  variant_id: string;
  product_id: string;
  product_name: string;
  sku_label: string;
  failed_constraints: string[];
  unknown_constraints: string[];
  reasons: string[];
}

