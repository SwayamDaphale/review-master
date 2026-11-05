// Demo fixtures. EVERYTHING here is sample data used until the backend exists.
// Scores, evidence and explanations are placeholders and are labelled "Sample data" in the UI.
// Real product details come only from the user's own extension captures (S25 Ultra, iPhone 17 Pro Max).
import type {
  Category,
  CommunityInsights,
  Confidence,
  ConfidenceState,
  Evaluation,
  EvidenceRef,
  ExpertAssessmentSummary,
  Explanation,
  MarketplaceRating,
  MatchState,
  Offer,
  ParameterResult,
  PriceHistory,
  PricePoint,
  Product,
  SourceType,
  SpecItem,
  TrustTier,
  Variant,
  VerificationState,
} from '../types/api';

const DAY = 86_400_000;
const iso = (daysAgo: number, hoursAgo = 0): string =>
  new Date(Date.now() - daysAgo * DAY - hoursAgo * 3_600_000).toISOString();

const TIER: Record<SourceType, TrustTier> = {
  independent_test: 1,
  expert_test: 1,
  manufacturer: 2,
  marketplace: 2,
  other_authorized: 2,
  community: 3,
};

let evCounter = 0;
function ev(
  source_type: SourceType,
  label: string,
  daysAgo: number,
  verification: VerificationState = 'verified',
): EvidenceRef {
  evCounter += 1;
  return {
    evidence_id: `ev-${evCounter}`,
    source_type,
    trust_tier: TIER[source_type],
    label,
    observed_at: iso(daysAgo),
    verification_state: verification,
  };
}
const MKT = (d: number) => ev('marketplace', 'Amazon India listing (extension capture)', d, 'unverified');
const MFR = (d: number) => ev('manufacturer', 'Manufacturer specification sheet (sample)', d);
const LAB = (d: number) => ev('independent_test', 'Independent lab test (sample)', d);
const EXPT = (d: number) => ev('expert_test', 'Expert test (sample)', d);

interface ParamDef {
  key: string;
  name: string;
  weight: number;
  critical: boolean;
}

const PARAMS: Record<Category, ParamDef[]> = {
  smartphone: [
    { key: 'performance', name: 'Performance', weight: 0.22, critical: true },
    { key: 'battery_charging', name: 'Battery and charging', weight: 0.2, critical: true },
    { key: 'camera', name: 'Camera', weight: 0.2, critical: true },
    { key: 'display', name: 'Display', weight: 0.14, critical: false },
    { key: 'software_updates', name: 'Software and updates', weight: 0.1, critical: false },
    { key: 'build_durability', name: 'Build and durability', weight: 0.08, critical: false },
    { key: 'connectivity_features', name: 'Connectivity and features', weight: 0.06, critical: false },
  ],
  laptop: [
    { key: 'cpu', name: 'CPU', weight: 0.2, critical: true },
    { key: 'gpu', name: 'GPU', weight: 0.12, critical: false },
    { key: 'ram_storage', name: 'RAM and storage', weight: 0.14, critical: true },
    { key: 'display', name: 'Display', weight: 0.14, critical: false },
    { key: 'battery', name: 'Battery', weight: 0.16, critical: true },
    { key: 'thermal_sustained', name: 'Thermals and sustained performance', weight: 0.1, critical: false },
    { key: 'build_portability', name: 'Build and portability', weight: 0.08, critical: false },
    { key: 'connectivity_upgradeability', name: 'Connectivity and upgradeability', weight: 0.06, critical: false },
  ],
  external_ssd: [
    { key: 'sequential_rw', name: 'Sequential read and write', weight: 0.22, critical: true },
    { key: 'sustained_write', name: 'Sustained write', weight: 0.24, critical: true },
    { key: 'capacity', name: 'Capacity', weight: 0.16, critical: true },
    { key: 'interface_compat', name: 'Interface and compatibility', weight: 0.1, critical: false },
    { key: 'durability_thermal', name: 'Durability and thermal', weight: 0.12, critical: false },
    { key: 'warranty_endurance', name: 'Warranty and endurance', weight: 0.1, critical: false },
    { key: 'portability_build', name: 'Portability and build', weight: 0.06, critical: false },
  ],
};

const MODEL_NAME: Record<Category, string> = {
  smartphone: 'Smartphone model (sample)',
  laptop: 'Laptop model (sample)',
  external_ssd: 'External SSD model (sample)',
};

interface ScoreSpec {
  score: number | null;
  evidence?: EvidenceRef[];
  note?: string;
}

/**
 * Stand-in for the backend's deterministic engine. It exists ONLY in the mock so the demo data is
 * internally consistent. The real engine runs on the server; the UI never does this.
 */
function buildEvaluation(
  variantId: string,
  category: Category,
  specs: Record<string, ScoreSpec>,
  conf: { state: ConfidenceState; score: number; reasons: string[] },
  limitations: string[],
): Evaluation {
  const defs = PARAMS[category];
  const parameters: ParameterResult[] = defs.map((d) => {
    const s = specs[d.key];
    const score = s?.score ?? null;
    return {
      key: d.key,
      name: d.name,
      status: score === null ? 'not_scored' : 'scored',
      score,
      weight: d.weight,
      is_critical: d.critical,
      evidence: s?.evidence ?? [],
      note: s?.note,
    };
  });
  const totalWeight = defs.reduce((a, d) => a + d.weight, 0);
  const scored = parameters.filter((p) => p.score !== null);
  const scoredWeight = scored.reduce((a, p) => a + (p.weight ?? 0), 0);
  const coverage = totalWeight === 0 ? 0 : scoredWeight / totalWeight;
  const weightedSum = scored.reduce((a, p) => a + (p.score ?? 0) * (p.weight ?? 0), 0);
  const overall =
    conf.state === 'insufficient_evidence' || scoredWeight === 0
      ? null
      : Math.round((weightedSum / scoredWeight) * 10) / 10;
  const confidence: Confidence = {
    state: conf.state,
    score: conf.score,
    coverage: Math.round(coverage * 100) / 100,
    reasons: conf.reasons,
  };
  return {
    evaluation_id: `eval-${variantId}`,
    variant_id: variantId,
    model: { name: MODEL_NAME[category], version: 'sample-0' },
    overall_score: overall,
    confidence,
    parameters,
    limitations,
    created_at: iso(1),
  };
}

function history(current: number, days: number, seed: number): PriceHistory {
  let s = seed * 9301 + 49297;
  const rnd = () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
  const points: PricePoint[] = [];
  for (let i = days - 1; i >= 0; i -= 1) {
    const wave = Math.sin((i + seed) / 7) * 0.035;
    const noise = (rnd() - 0.5) * 0.02;
    const price = i === 0 ? current : Math.round((current * (1 + wave + noise + 0.02)) / 10) * 10;
    points.push({ observed_at: iso(i), price });
  }
  const windowOf = (n: number) => {
    const slice = points.slice(-n).map((p) => p.price);
    if (slice.length === 0) return null;
    const sorted = [...slice].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    const median =
      sorted.length % 2 === 0 ? ((sorted[mid - 1] ?? 0) + (sorted[mid] ?? 0)) / 2 : (sorted[mid] ?? 0);
    return { min: sorted[0] ?? 0, median: Math.round(median), max: sorted[sorted.length - 1] ?? 0 };
  };
  return { points, windows: { '30': windowOf(30), '90': windowOf(90) }, coverage_days: days };
}

export interface Fixture {
  product: Product;
  variant: Variant;
  specs: SpecItem[];
  evaluation: Evaluation;
  explanation: Explanation;
  community: CommunityInsights;
  expert: ExpertAssessmentSummary;
  offers: Offer[];
  rating: MarketplaceRating | null;
  history: PriceHistory;
  price: number | null;
  match_state: MatchState;
}

const NONE_COMMUNITY = (n: number): CommunityInsights => ({
  status: 'not_enough_feedback',
  sample_size: n,
  themes: [],
  review_quality_signals: [],
  ai_generated: false,
});
const NO_EXPERT: ExpertAssessmentSummary = { status: 'none', findings: [] };
const spec = (key: string, label: string, value: string | null, source: string): SpecItem => ({ key, label, value, source });
const SRC_AMZ = 'Amazon India listing (extension capture)';
const SRC_SAMPLE = 'Sample specification';
let offerCounter = 0;
const offer = (seller: string, price: number, hoursAgo: number, source: string, stale = false): Offer => {
  offerCounter += 1;
  return {
    offer_id: `offer-${offerCounter}`,
    seller,
    price,
    currency: 'INR',
    availability: 'in_stock',
    source,
    observed_at: iso(0, hoursAgo),
    stale,
  };
};

function mk(
  product: Product,
  variant: Variant,
  specs: SpecItem[],
  scoreSpecs: Record<string, ScoreSpec>,
  conf: { state: ConfidenceState; score: number; reasons: string[] },
  limitations: string[],
  explanation: Explanation,
  extras: Partial<Pick<Fixture, 'community' | 'expert' | 'offers' | 'rating' | 'match_state'>> & {
    price: number | null;
    historyDays: number;
    seed: number;
  },
): Fixture {
  const withIdentity: SpecItem[] = [...specs];
  if (!withIdentity.some((s) => s.key === 'model')) {
    withIdentity.unshift(spec('model', 'Model', product.model, SRC_SAMPLE));
  }
  if (!withIdentity.some((s) => s.key === 'brand')) {
    withIdentity.unshift(spec('brand', 'Brand', product.manufacturer, SRC_SAMPLE));
  }
  return {
    product,
    variant,
    specs: withIdentity,
    evaluation: buildEvaluation(variant.id, product.category, scoreSpecs, conf, limitations),
    explanation,
    community: extras.community ?? NONE_COMMUNITY(0),
    expert: extras.expert ?? NO_EXPERT,
    offers: extras.offers ?? [],
    rating: extras.rating ?? null,
    history: extras.price === null ? { points: [], windows: { '30': null, '90': null }, coverage_days: 0 } : history(extras.price, extras.historyDays, extras.seed),
    price: extras.price,
    match_state: extras.match_state ?? 'confirmed',
  };
}

const ai = (text: string, referenced: string[]): Explanation => ({
  text,
  ai_generated: true,
  mode: 'ai',
  referenced_parameters: referenced,
});

// ---------------- Smartphones ----------------
const s25u: Product = { id: 'p-galaxy-s25-ultra', name: 'Samsung Galaxy S25 Ultra', manufacturer: 'Samsung', model: 'Galaxy S25 Ultra', category: 'smartphone', asin: 'B0DSKMV3ZC' };
const iph: Product = { id: 'p-iphone-17-pro-max', name: 'Apple iPhone 17 Pro Max', manufacturer: 'Apple', model: 'iPhone 17 Pro Max', category: 'smartphone', asin: 'B0FQFJKBVY' };
const phoneC: Product = { id: 'p-sample-phone-c', name: 'Sample Phone C', manufacturer: 'Sample', model: 'Phone C', category: 'smartphone' };
const laptopA: Product = { id: 'p-sample-laptop-a', name: 'Sample Laptop A', manufacturer: 'Sample', model: 'Laptop A', category: 'laptop' };
const laptopB: Product = { id: 'p-sample-laptop-b', name: 'Sample Laptop B', manufacturer: 'Sample', model: 'Laptop B', category: 'laptop' };
const ssd1: Product = { id: 'p-sample-ssd-1tb', name: 'Sample Portable SSD 1 TB', manufacturer: 'Sample', model: 'Portable SSD 1 TB', category: 'external_ssd' };
const ssd2: Product = { id: 'p-sample-ssd-2tb', name: 'Sample Portable SSD 2 TB', manufacturer: 'Sample', model: 'Portable SSD 2 TB', category: 'external_ssd' };

const vr = (id: string, p: Product, label: string, configuration: Variant['configuration']): Variant => ({ id, product_id: p.id, label, configuration });

export const FIXTURES: Fixture[] = [
  mk(
    s25u,
    vr('v-s25u-12-256', s25u, '12 GB RAM / 256 GB', { ram_gb: 12, storage_gb: 256 }),
    [
      spec('brand', 'Brand', 'Samsung', SRC_AMZ),
      spec('model', 'Model', 'Galaxy S25 Ultra', SRC_AMZ),
      spec('ram', 'RAM', '12 GB', SRC_AMZ),
      spec('storage', 'Storage', '256 GB', SRC_AMZ),
      spec('display', 'Display size', '6.9 in', SRC_AMZ),
      spec('battery', 'Battery capacity', '5,000 mAh', SRC_AMZ),
      spec('processor', 'Processor', 'Snapdragon 8 Elite', SRC_AMZ),
      spec('os', 'Operating system', 'Android 16', SRC_AMZ),
      spec('5g', '5G support', 'Yes', SRC_AMZ),
    ],
    {
      performance: { score: 91, evidence: [MKT(2)] },
      battery_charging: { score: 78, evidence: [MKT(2)] },
      camera: { score: 88, evidence: [MKT(2)] },
      display: { score: 90, evidence: [MKT(2)] },
      software_updates: { score: 86, evidence: [MKT(2)] },
      build_durability: { score: 80, evidence: [MKT(2)] },
      connectivity_features: { score: 92, evidence: [MKT(2)] },
    },
    { state: 'limited', score: 0.62, reasons: ['No independent lab test is linked to performance, battery or camera yet.', 'Every input comes from the marketplace listing.'] },
    ['Scores rest on listed specifications, not measured results.'],
    ai('From the listed specifications, this phone scores well on performance, display and connectivity. The overall score is held back because no lab measurement is attached yet, so battery and camera results come only from the listing. Treat it as a starting point until test evidence is added.', ['performance', 'display', 'connectivity_features', 'battery_charging', 'camera']),
    { price: 94999, historyDays: 90, seed: 3, community: NONE_COMMUNITY(3), offers: [offer('Amazon India', 94999, 2, 'Amazon India (extension capture)')], rating: { source: 'Amazon India (external)', rating: 4.4, count: 3492 } },
  ),
  mk(
    iph,
    vr('v-iphone17pm-1tb', iph, '1 TB', { storage_gb: 1024 }),
    [
      spec('brand', 'Brand', 'Apple', SRC_AMZ),
      spec('model', 'Model', 'iPhone 17 Pro Max', SRC_AMZ),
      spec('ram', 'RAM', null, SRC_AMZ),
      spec('storage', 'Storage', '1 TB', SRC_AMZ),
      spec('display', 'Display size', '6.9 in', SRC_AMZ),
      spec('battery', 'Battery capacity', null, SRC_AMZ),
      spec('processor', 'Processor', 'Others (needs review)', SRC_AMZ),
      spec('os', 'Operating system', null, SRC_AMZ),
      spec('5g', '5G support', 'Yes', SRC_AMZ),
    ],
    {
      performance: { score: 94, evidence: [MKT(1)] },
      battery_charging: { score: null, note: 'Battery capacity was not captured from the listing.' },
      camera: { score: 90, evidence: [MKT(1)] },
      display: { score: 92, evidence: [MKT(1)] },
      software_updates: { score: 90, evidence: [MKT(1)] },
      build_durability: { score: 86, evidence: [MKT(1)] },
      connectivity_features: { score: 88, evidence: [MKT(1)] },
    },
    { state: 'limited', score: 0.51, reasons: ['A critical parameter (battery and charging) is not scored.', 'The processor read as "Others" on the listing and needs review.', 'No independent lab test is linked yet.'] },
    ['The overall score covers only the parameters that have data.'],
    ai('Performance, camera and display score highly on the listed specifications. Battery and charging is not scored because the listing did not give a battery capacity, so the overall score covers only the parameters that have data. Adding battery evidence would raise confidence.', ['performance', 'camera', 'display', 'battery_charging']),
    { price: 184900, historyDays: 12, seed: 5, match_state: 'probable', offers: [offer('Amazon India', 184900, 1, 'Amazon India (extension capture)')], rating: { source: 'Amazon India (external)', rating: 4.6, count: 682 } },
  ),
  mk(
    phoneC,
    vr('v-phone-c-12-256', phoneC, '12 GB RAM / 256 GB', { ram_gb: 12, storage_gb: 256 }),
    [
      spec('ram', 'RAM', '12 GB', SRC_SAMPLE),
      spec('storage', 'Storage', '256 GB', SRC_SAMPLE),
      spec('display', 'Display size', '6.7 in', SRC_SAMPLE),
      spec('battery', 'Battery capacity', '5,000 mAh', SRC_SAMPLE),
      spec('processor', 'Processor', 'Sample chipset', SRC_SAMPLE),
      spec('5g', '5G support', 'Yes', SRC_SAMPLE),
    ],
    {
      performance: { score: 84, evidence: [LAB(20), MFR(30)] },
      battery_charging: { score: 82, evidence: [LAB(20)] },
      camera: { score: 79, evidence: [LAB(18)] },
      display: { score: 81, evidence: [MFR(30)] },
      software_updates: { score: 70, evidence: [MFR(30)] },
      build_durability: { score: 72, evidence: [MFR(30)] },
      connectivity_features: { score: 75, evidence: [MFR(30)] },
    },
    { state: 'high', score: 0.83, reasons: ['Critical parameters are backed by independent lab tests.', 'Evidence is recent and consistent.'] },
    [],
    ai('Backed by independent lab tests for performance, battery and camera, this variant scores consistently across the board. Software updates and build score lower because they rest on the manufacturer sheet alone.', ['performance', 'battery_charging', 'camera', 'software_updates', 'build_durability']),
    {
      price: 41999,
      historyDays: 90,
      seed: 7,
      community: {
        status: 'available',
        sample_size: 14,
        themes: [
          { label: 'Battery lasts a full day', polarity: 'positive', count: 9 },
          { label: 'Camera is good in daylight', polarity: 'positive', count: 7 },
          { label: 'Gets warm while charging', polarity: 'negative', count: 4 },
        ],
        review_quality_signals: [{ signal_type: 'similar_text', description: 'Several reviews use almost identical wording in the same week.', strength: 'medium' }],
        ai_generated: true,
      },
      offers: [offer('Sample Seller A', 41999, 3, 'Sample feed'), offer('Sample Seller B', 42499, 9 * 24, 'Sample feed', true)],
    },
  ),
  mk(
    phoneC,
    vr('v-phone-c-8-128', phoneC, '8 GB RAM / 128 GB', { ram_gb: 8, storage_gb: 128 }),
    [
      spec('ram', 'RAM', '8 GB', SRC_SAMPLE),
      spec('storage', 'Storage', '128 GB', SRC_SAMPLE),
      spec('display', 'Display size', '6.7 in', SRC_SAMPLE),
      spec('battery', 'Battery capacity', '5,000 mAh', SRC_SAMPLE),
      spec('processor', 'Processor', 'Sample chipset', SRC_SAMPLE),
      spec('5g', '5G support', 'Yes', SRC_SAMPLE),
    ],
    {
      performance: { score: null, note: 'No evidence available yet.' },
      battery_charging: { score: null, note: 'No evidence available yet.' },
      camera: { score: null, note: 'No evidence available yet.' },
      display: { score: 70, evidence: [MFR(30)] },
      software_updates: { score: null, note: 'No evidence available yet.' },
      build_durability: { score: 68, evidence: [MFR(30)] },
      connectivity_features: { score: 72, evidence: [MFR(30)] },
    },
    { state: 'insufficient_evidence', score: 0.31, reasons: ['Only 28% of the model weight has any evidence.', 'Critical parameters have no evidence.'] },
    ['The overall score is withheld until more evidence exists.'],
    { mode: 'template', ai_generated: false, referenced_parameters: ['display', 'build_durability', 'connectivity_features'], text: 'There is not enough evidence to score this variant. Display, build and connectivity have listed specifications, but performance, battery and camera have no evidence yet.' },
    { price: 24999, historyDays: 45, seed: 9, offers: [offer('Sample Seller A', 24999, 3, 'Sample feed')] },
  ),
  // ---------------- Laptops ----------------
  mk(
    laptopA,
    vr('v-laptop-a-16-512', laptopA, '16 GB RAM / 512 GB', { ram_gb: 16, storage_gb: 512 }),
    [
      spec('cpu', 'Processor', 'Sample 8-core CPU', SRC_SAMPLE),
      spec('ram', 'RAM', '16 GB', SRC_SAMPLE),
      spec('storage', 'Storage', '512 GB SSD', SRC_SAMPLE),
      spec('display', 'Display', '14 in, 2.2K', SRC_SAMPLE),
      spec('battery', 'Battery capacity', '70 Wh', SRC_SAMPLE),
      spec('weight', 'Weight', '1.4 kg', SRC_SAMPLE),
    ],
    {
      cpu: { score: 86, evidence: [LAB(15), MFR(30)] },
      gpu: { score: 70, evidence: [LAB(15)] },
      ram_storage: { score: 78, evidence: [MFR(30)] },
      display: { score: 82, evidence: [LAB(15)] },
      battery: { score: 84, evidence: [EXPT(10)] },
      thermal_sustained: { score: 76, evidence: [EXPT(10)] },
      build_portability: { score: 80, evidence: [MFR(30)] },
      connectivity_upgradeability: { score: 66, evidence: [MFR(30)] },
    },
    { state: 'high', score: 0.8, reasons: ['Most of the weight is backed by independent or expert tests.', 'Evidence is recent and consistent.'] },
    [],
    ai('Strong CPU and battery results come from independent and expert tests. Connectivity and upgradeability score lower because they rest on the manufacturer sheet.', ['cpu', 'battery', 'thermal_sustained', 'connectivity_upgradeability']),
    {
      price: 72990,
      historyDays: 90,
      seed: 11,
      community: {
        status: 'available',
        sample_size: 22,
        themes: [
          { label: 'Battery lasts a work day', polarity: 'positive', count: 14 },
          { label: 'Keyboard is comfortable', polarity: 'positive', count: 9 },
          { label: 'Fan noise under load', polarity: 'negative', count: 5 },
        ],
        review_quality_signals: [],
        ai_generated: true,
      },
      expert: {
        status: 'published',
        expert_label: 'Independent tester (sample)',
        published_at: iso(10),
        findings: [
          { parameter: 'Battery', finding: 'Lasted 11.4 hours in a web-browsing loop at 150 nits (sample result).' },
          { parameter: 'Thermals and sustained performance', finding: 'Kept 88% of peak CPU speed after 20 minutes of load (sample result).' },
        ],
      },
      offers: [offer('Sample Seller A', 72990, 5, 'Sample feed')],
    },
  ),
  mk(
    laptopB,
    vr('v-laptop-b-16-512', laptopB, '16 GB RAM / 512 GB', { ram_gb: 16, storage_gb: 512 }),
    [
      spec('cpu', 'Processor', 'Sample 6-core CPU', SRC_SAMPLE),
      spec('ram', 'RAM', '16 GB', SRC_SAMPLE),
      spec('storage', 'Storage', '512 GB SSD', SRC_SAMPLE),
      spec('display', 'Display', '15.6 in, Full HD', SRC_SAMPLE),
      spec('battery', 'Battery capacity', '56 Wh', SRC_SAMPLE),
      spec('weight', 'Weight', '1.8 kg', SRC_SAMPLE),
    ],
    {
      cpu: { score: 74, evidence: [MFR(30)] },
      gpu: { score: null, note: 'No graphics evidence yet.' },
      ram_storage: { score: 72, evidence: [MFR(30)] },
      display: { score: 68, evidence: [MFR(30)] },
      battery: { score: 70, evidence: [MFR(30)] },
      thermal_sustained: { score: null, note: 'No sustained-load test yet.' },
      build_portability: { score: 75, evidence: [MFR(30)] },
      connectivity_upgradeability: { score: 80, evidence: [MFR(30)] },
    },
    { state: 'limited', score: 0.55, reasons: ['Graphics and sustained performance have no evidence.', 'All scored inputs come from the manufacturer sheet.'] },
    ['Scores rest on listed specifications, not measured results.'],
    ai('The scored parameters rest on the manufacturer sheet only. Graphics and sustained performance have no evidence, so this laptop should be read as a partial picture.', ['cpu', 'ram_storage', 'battery', 'gpu', 'thermal_sustained']),
    { price: 58990, historyDays: 60, seed: 13, offers: [offer('Sample Seller A', 58990, 6, 'Sample feed')] },
  ),
  mk(
    laptopB,
    vr('v-laptop-b-32-1024', laptopB, '32 GB RAM / 1 TB', { ram_gb: 32, storage_gb: 1024 }),
    [
      spec('cpu', 'Processor', 'Sample 6-core CPU', SRC_SAMPLE),
      spec('ram', 'RAM', '32 GB', SRC_SAMPLE),
      spec('storage', 'Storage', '1 TB SSD', SRC_SAMPLE),
      spec('display', 'Display', '15.6 in, Full HD', SRC_SAMPLE),
      spec('battery', 'Battery capacity', '56 Wh', SRC_SAMPLE),
      spec('weight', 'Weight', '1.8 kg', SRC_SAMPLE),
    ],
    {
      cpu: { score: 74, evidence: [MFR(30)] },
      gpu: { score: null, note: 'No graphics evidence yet.' },
      ram_storage: { score: 90, evidence: [MFR(30)] },
      display: { score: 68, evidence: [MFR(30)] },
      battery: { score: 70, evidence: [MFR(30)] },
      thermal_sustained: { score: null, note: 'No sustained-load test yet.' },
      build_portability: { score: 75, evidence: [MFR(30)] },
      connectivity_upgradeability: { score: 80, evidence: [MFR(30)] },
    },
    { state: 'limited', score: 0.58, reasons: ['Graphics and sustained performance have no evidence.', 'All scored inputs come from the manufacturer sheet.'] },
    ['Scores rest on listed specifications, not measured results.'],
    ai('The larger memory and storage lift the RAM and storage result, while the other parameters match the smaller variant. Missing graphics and sustained-load evidence keep confidence limited.', ['ram_storage', 'cpu', 'gpu', 'thermal_sustained']),
    { price: 79990, historyDays: 60, seed: 15, offers: [offer('Sample Seller A', 79990, 6, 'Sample feed')] },
  ),
  // ---------------- External SSDs ----------------
  mk(
    ssd1,
    vr('v-ssd-1tb', ssd1, '1 TB', { capacity_gb: 1000 }),
    [
      spec('capacity', 'Capacity', '1 TB', SRC_SAMPLE),
      spec('interface', 'Interface', 'USB 3.2 Gen 2', SRC_SAMPLE),
      spec('read', 'Rated read speed', '1,050 MB/s', 'Manufacturer claim (sample)'),
      spec('write', 'Rated write speed', '1,000 MB/s', 'Manufacturer claim (sample)'),
      spec('weight', 'Weight', '58 g', SRC_SAMPLE),
    ],
    {
      sequential_rw: { score: 82, evidence: [MFR(30)] },
      sustained_write: { score: 60, evidence: [MFR(30)], note: 'Manufacturer claim only.' },
      capacity: { score: 70, evidence: [MFR(30)] },
      interface_compat: { score: 85, evidence: [MFR(30)] },
      durability_thermal: { score: 74, evidence: [MFR(30)] },
      warranty_endurance: { score: 66, evidence: [MFR(30)] },
      portability_build: { score: 88, evidence: [MFR(30)] },
    },
    { state: 'limited', score: 0.6, reasons: ['Sustained write is a manufacturer claim and has not been measured.', 'No independent test is linked.'] },
    ['Rated speeds are claims, not measured results.'],
    ai('Rated speeds are strong, but they are manufacturer claims. Sustained write, the figure that matters for large transfers, has not been measured, so confidence stays limited.', ['sequential_rw', 'sustained_write']),
    { price: 7499, historyDays: 90, seed: 17, offers: [offer('Sample Seller A', 7499, 4, 'Sample feed')] },
  ),
  mk(
    ssd2,
    vr('v-ssd-2tb', ssd2, '2 TB', { capacity_gb: 2000 }),
    [
      spec('capacity', 'Capacity', '2 TB', SRC_SAMPLE),
      spec('interface', 'Interface', 'USB 3.2 Gen 2x2', SRC_SAMPLE),
      spec('read', 'Measured read speed', '1,980 MB/s', 'Independent lab test (sample)'),
      spec('write', 'Measured write speed', '1,850 MB/s', 'Independent lab test (sample)'),
      spec('weight', 'Weight', '62 g', SRC_SAMPLE),
    ],
    {
      sequential_rw: { score: 88, evidence: [LAB(14)] },
      sustained_write: { score: 84, evidence: [LAB(14)] },
      capacity: { score: 85, evidence: [MFR(30)] },
      interface_compat: { score: 90, evidence: [MFR(30)] },
      durability_thermal: { score: 78, evidence: [LAB(14)] },
      warranty_endurance: { score: 72, evidence: [MFR(30)] },
      portability_build: { score: 82, evidence: [MFR(30)] },
    },
    { state: 'high', score: 0.78, reasons: ['Speed and thermal results are backed by an independent lab test.', 'Evidence is recent and consistent.'] },
    [],
    ai('Measured speeds hold up well, including sustained write after the cache fills. Warranty and build score lower and rest on the manufacturer sheet.', ['sequential_rw', 'sustained_write', 'durability_thermal', 'warranty_endurance']),
    {
      price: 12999,
      historyDays: 90,
      seed: 19,
      community: {
        status: 'available',
        sample_size: 11,
        themes: [
          { label: 'Fast on large file copies', polarity: 'positive', count: 8 },
          { label: 'Gets warm during long transfers', polarity: 'mixed', count: 3 },
        ],
        review_quality_signals: [],
        ai_generated: true,
      },
      offers: [offer('Sample Seller A', 12999, 2, 'Sample feed')],
    },
  ),
];
