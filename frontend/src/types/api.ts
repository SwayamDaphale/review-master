// Types mirror architecture/api/openapi.yaml (Evaluation, ParameterResult, EvidenceRef, Offer, ...).
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

export class ApiError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
  }
}
