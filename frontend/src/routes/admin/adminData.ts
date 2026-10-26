export interface MappingItem {
  id: string;
  listing: string;
  title: string;
  suggestion: string;
  reason: string;
  state: 'confirmed' | 'probable' | 'ambiguous';
  status: 'pending' | 'confirmed' | 'rejected';
}

export interface EvalParam {
  key: string;
  name: string;
  weight: number | null;
}

export interface EvalModel {
  id: string;
  category: string;
  version: string;
  status: 'draft' | 'published';
  domainApproved: boolean;
  engineeringApproved: boolean;
  params: EvalParam[];
}

export interface ModerationItem {
  id: string;
  target: string;
  author: string;
  text: string;
  flags: string[];
  state: 'pending' | 'approved' | 'rejected' | 'flagged';
}

export interface IntegrationStatus {
  name: string;
  status: 'healthy' | 'degraded' | 'disconnected';
  detail: string;
}

export const MAPPINGS_SEED: MappingItem[] = [
  {
    id: 'map-01',
    listing: 'ASIN B0GRDH5D6Z (Amazon India)',
    title: 'Nothing Phone 4a (12GB 256GB Black)',
    suggestion: 'Nothing Phone 4a — 12GB RAM · 256GB Storage (Black)',
    reason: 'Table RAM row mislabeled as 256 GB; title provides validated 12GB pair matching table storage.',
    state: 'probable',
    status: 'pending'
  },
  {
    id: 'map-02',
    listing: 'ASIN B0DSKMV3ZC (Amazon India)',
    title: 'Samsung Galaxy S25 Ultra 5G AI Smartphone (Titanium Black, 12GB RAM, 256GB Storage)',
    suggestion: 'Samsung Galaxy S25 Ultra — 12GB RAM · 256GB Storage',
    reason: 'Standing screen display size reported in metric (17.47 Centimetres) normalized to 6.88".',
    state: 'confirmed',
    status: 'confirmed'
  },
  {
    id: 'map-03',
    listing: 'ASIN B0FQFW4MVJ (Amazon India)',
    title: 'Apple iPhone 17 Pro Max 256 GB: 17.42 cm (6.9″) Display with Promotion, A19 Pro Chip',
    suggestion: 'Apple iPhone 17 Pro Max — 256GB Storage',
    reason: 'Table lists raw RAM 0.1 GB; correctly rejected as implausible. RAM marked insufficient evidence.',
    state: 'probable',
    status: 'pending'
  }
];

export const MODELS_SEED: EvalModel[] = [
  {
    id: 'model-smartphones',
    category: 'Smartphones',
    version: 'v1.0-draft',
    status: 'draft',
    domainApproved: false,
    engineeringApproved: true,
    params: [
      { key: 'display', name: 'Display Quality (Color accuracy, Peak Nits, Refresh rate)', weight: 0.25 },
      { key: 'performance', name: 'Sustained Compute & Benchmarks (Geekbench 6, AnTuTu)', weight: 0.25 },
      { key: 'battery', name: 'Battery Endurance & Charging Curves', weight: 0.20 },
      { key: 'camera', name: 'Camera Sensor Benchmarks & Optical Stabilization', weight: 0.20 },
      { key: 'thermal', name: 'Thermal Throttling & Stress Test Stability', weight: 0.10 }
    ]
  },
  {
    id: 'model-laptops',
    category: 'Laptops',
    version: 'v1.0-draft',
    status: 'draft',
    domainApproved: false,
    engineeringApproved: false,
    params: [
      { key: 'cpu_gpu', name: 'CPU/GPU Sustained Workload Benchmarks', weight: 0.35 },
      { key: 'battery_life', name: 'Real-world Web & Video Battery Life', weight: 0.25 },
      { key: 'display_accuracy', name: 'Color Gamut (DCI-P3/sRGB) & Brightness', weight: 0.20 },
      { key: 'thermals_noise', name: 'Acoustics & Surface Temperatures Under Load', weight: 0.10 },
      { key: 'portability', name: 'Weight & Charger Form Factor', weight: 0.10 }
    ]
  },
  {
    id: 'model-ssd',
    category: 'External SSDs',
    version: 'v1.0',
    status: 'published',
    domainApproved: true,
    engineeringApproved: true,
    params: [
      { key: 'seq_rw', name: 'Sequential Read/Write Speeds (MB/s)', weight: 0.30 },
      { key: 'sustained_write', name: 'Sustained Write Speed After SLC Cache Depletion', weight: 0.30 },
      { key: 'thermal_mgmt', name: 'Thermal Management & Throttling Onset', weight: 0.20 },
      { key: 'durability', name: 'IP Ingress Rating & Drop Protection', weight: 0.20 }
    ]
  }
];

export const MODERATION_SEED: ModerationItem[] = [
  {
    id: 'mod-01',
    target: 'Nothing Phone 4a',
    author: 'Buyer_IN_89',
    text: 'Battery holds up for 1.5 days easily. Clean OS without bloatware. Glyph lighting is much more subtle than phone 2.',
    flags: [],
    state: 'approved'
  },
  {
    id: 'mod-02',
    target: 'Samsung Galaxy S25 Ultra',
    author: 'Verified_Tech_Geek',
    text: 'BEST PHONE EVER BUY NOW 10/10 AMAZING DISCOUNTS AND GIFT CARD CLICK LINK TO CLAIM YOUR 5000 RUPEES CASHBACK TODAY!',
    flags: ['Spam keyword density', 'Repetitive capitalization', 'External voucher referral pattern'],
    state: 'flagged'
  },
  {
    id: 'mod-03',
    target: 'Redmi Turbo 5',
    author: 'GamerGuy_Delhi',
    text: 'Heats up a bit during prolonged BGMI sessions at 120fps, but frame rate holds reasonably stable.',
    flags: [],
    state: 'pending'
  }
];

export const INTEGRATIONS: IntegrationStatus[] = [
  {
    name: 'Amazon India Ingestion Adapter',
    status: 'healthy',
    detail: 'DOM extractor rules synced for Chromium MV3; permission gate verified on amazon.in'
  },
  {
    name: 'LiteLLM Gateway (AI Grounding)',
    status: 'healthy',
    detail: 'Deterministic explanation worker active with zero-score generation restriction'
  },
  {
    name: 'PostgreSQL 17 Primary Database',
    status: 'healthy',
    detail: 'Row-level security and schema migrations ready'
  },
  {
    name: 'Redis Cache & Outbox Queue',
    status: 'healthy',
    detail: 'Lookup latency targets < 2s; Celery dispatch queues operational'
  }
];

export function modelBlockers(m: EvalModel): string[] {
  const blockers: string[] = [];
  const hasNull = m.params.some((p) => p.weight === null);
  if (hasNull) {
    blockers.push('All parameters must have a numerical weight assigned.');
  }

  const sum = m.params.reduce((acc, p) => acc + (p.weight ?? 0), 0);
  if (Math.abs(sum - 1.0) > 0.001) {
    blockers.push(`Parameter weights must sum exactly to 1.00 (currently ${sum.toFixed(2)}).`);
  }

  if (!m.domainApproved) {
    blockers.push('Domain expert formal sign-off is required before publishing.');
  }

  if (!m.engineeringApproved) {
    blockers.push('Engineering architectural sign-off is required.');
  }

  return blockers;
}
