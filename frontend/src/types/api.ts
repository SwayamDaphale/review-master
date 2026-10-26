export type Category = 'smartphone' | 'laptop' | 'ssd';

export const CATEGORY_SINGULAR: Record<Category, string> = {
  smartphone: 'Smartphone',
  laptop: 'Laptop',
  ssd: 'External SSD'
};

export const CATEGORY_PLURAL: Record<Category, string> = {
  smartphone: 'Smartphones',
  laptop: 'Laptops',
  ssd: 'External SSDs'
};

export type MatchState = 'confirmed' | 'probable' | 'ambiguous' | 'unconfirmed';

export type ConfidenceState = 'high' | 'moderate' | 'limited' | 'insufficient';

export interface Confidence {
  state: ConfidenceState;
  score: number;
  coverage_percent: number;
  evidence_count: number;
}

export type EvidenceTier = 'tier1' | 'tier2' | 'tier3' | 'tier4';

export interface EvidenceItem {
  id: string;
  parameter: string;
  tier: EvidenceTier;
  source_name: string;
  source_url?: string;
  citation: string;
  value: string | number;
  unit?: string;
  measured_at: string;
  reliability: 'verified_lab' | 'official_spec' | 'crowdsourced';
}

export interface EvaluationParameter {
  key: string;
  name: string;
  score: number | null;
  weight: number;
  unit?: string;
  raw_value?: string | number;
  status: 'scored' | 'insufficient_evidence';
  tier1_evidence_count: number;
}

export interface Evaluation {
  id: string;
  overall_score: number | null;
  confidence: Confidence;
  model_version: string;
  category: Category;
  computed_at: string;
  parameters: EvaluationParameter[];
  grounded_explanation: string;
}

export interface CommunitySignals {
  authentic_percentage: number;
  suspicious_percentage: number;
  total_reviews_analyzed: number;
  sentiment_distribution: { positive: number; neutral: number; negative: number };
  top_positive_themes: string[];
  top_criticisms: string[];
  price_history: Array<{ date: string; price: number; marketplace: string }>;
  buy_timing_recommendation: 'buy_now' | 'wait_for_sale' | 'fair_price';
  lowest_observed_price: number;
  highest_observed_price: number;
  current_price: number;
}

export interface Product {
  id: string;
  name: string;
  brand: string;
  category: Category;
  created_at: string;
  hero_image?: string;
}

export interface Variant {
  id: string;
  product_id: string;
  label: string;
  sku?: string;
  asin?: string;
  specs: Record<string, string | number | boolean | null>;
}

export interface ProductItem {
  product: Product;
  variant: Variant;
  match_state: MatchState;
  price: number;
  currency: string;
  evaluation: Evaluation;
  community: CommunitySignals;
  evidence: EvidenceItem[];
}
