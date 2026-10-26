import type { ProductItem } from '../types/api';

export const MOCK_PRODUCTS: ProductItem[] = [
  {
    product: {
      id: 'prod-s25-ultra',
      name: 'Samsung Galaxy S25 Ultra',
      brand: 'Samsung',
      category: 'smartphone',
      created_at: '2026-02-10T08:00:00Z',
      hero_image: 'https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?auto=format&fit=crop&w=800&q=80'
    },
    variant: {
      id: 'var-s25-ultra-256',
      product_id: 'prod-s25-ultra',
      label: 'Titanium Black · 12GB RAM · 256GB Storage',
      asin: 'B0DSKMV3ZC',
      sku: 'SM-S938B',
      specs: {
        ram_gb: 12,
        storage_gb: 256,
        display_size_inches: 6.88,
        battery_capacity_mah: 5000,
        processor: 'Snapdragon 8 Elite',
        operating_system: 'Android 15',
        supports_5g: true
      }
    },
    match_state: 'confirmed',
    price: 129999,
    currency: 'INR',
    evaluation: {
      id: 'eval-s25-01',
      overall_score: 8.8,
      category: 'smartphone',
      model_version: 'smartphones-v1.0',
      computed_at: '2026-10-25T12:00:00Z',
      confidence: {
        state: 'high',
        score: 0.95,
        coverage_percent: 96,
        evidence_count: 14
      },
      parameters: [
        { key: 'display', name: 'Display Quality & Calibrated Accuracy', score: 9.3, weight: 0.25, unit: 'nits / deltaE', raw_value: '2600 nits peak · 0.9 dE', status: 'scored', tier1_evidence_count: 4 },
        { key: 'performance', name: 'Sustained Compute (Geekbench 6)', score: 9.4, weight: 0.25, unit: 'pts', raw_value: '3120 Single / 9850 Multi', status: 'scored', tier1_evidence_count: 3 },
        { key: 'battery', name: 'Battery Endurance & Drain Rate', score: 8.5, weight: 0.20, unit: 'hours', raw_value: '17.2h active web browsing', status: 'scored', tier1_evidence_count: 3 },
        { key: 'camera', name: 'Optics & Low Light Stabilization', score: 8.9, weight: 0.20, unit: 'sensor score', raw_value: '200MP f/1.7 5x Periscope', status: 'scored', tier1_evidence_count: 2 },
        { key: 'thermal', name: 'Thermal Throttling & Stability Under Load', score: 7.8, weight: 0.10, unit: '% stability', raw_value: '78.4% 3DMark Stress loop', status: 'scored', tier1_evidence_count: 2 }
      ],
      grounded_explanation: 'The Galaxy S25 Ultra demonstrates category-leading display luminance (2,600 nits peak with anti-reflective armor) and sustained multicore compute from the Snapdragon 8 Elite. Thermal throttling stabilizes at 78% retention during heavy 3D gaming loops.'
    },
    community: {
      authentic_percentage: 89,
      suspicious_percentage: 11,
      total_reviews_analyzed: 1420,
      sentiment_distribution: { positive: 76, neutral: 14, negative: 10 },
      top_positive_themes: ['Display legibility under bright Indian sunlight', 'S-Pen latency reduction', 'Consistent day-long battery'],
      top_criticisms: ['Substantial device weight (232g)', 'Charging capped at 45W'],
      price_history: [
        { date: '2026-08-01', price: 134999, marketplace: 'Amazon India' },
        { date: '2026-09-01', price: 131999, marketplace: 'Amazon India' },
        { date: '2026-10-01', price: 129999, marketplace: 'Amazon India' },
        { date: '2026-10-25', price: 129999, marketplace: 'Amazon India' }
      ],
      buy_timing_recommendation: 'fair_price',
      lowest_observed_price: 124999,
      highest_observed_price: 134999,
      current_price: 129999
    },
    evidence: [
      { id: 'ev-01', parameter: 'display', tier: 'tier1', source_name: 'DisplayMate Lab Test', citation: 'Lab Report #DM-S25U: 2600 nits peak brightness, 0.9 JNCD color accuracy', value: '2600 nits', measured_at: '2026-02-15T00:00:00Z', reliability: 'verified_lab' },
      { id: 'ev-02', parameter: 'performance', tier: 'tier1', source_name: 'Geekbench Benchmark Database', citation: 'Run ID #998341: Geekbench 6 64-bit multi-core verification', value: '9850 pts', measured_at: '2026-02-18T00:00:00Z', reliability: 'verified_lab' },
      { id: 'ev-03', parameter: 'battery', tier: 'tier1', source_name: 'GSMArena Lab Endurance Protocol', citation: 'Active Use Test v2: 17h 12m continuous web & video playback', value: '17.2 hours', measured_at: '2026-02-22T00:00:00Z', reliability: 'verified_lab' }
    ]
  },
  {
    product: {
      id: 'prod-nothing-4a',
      name: 'Nothing Phone 4a',
      brand: 'Nothing',
      category: 'smartphone',
      created_at: '2026-03-01T08:00:00Z',
      hero_image: 'https://images.unsplash.com/photo-1598327105666-5b89351aff97?auto=format&fit=crop&w=800&q=80'
    },
    variant: {
      id: 'var-nothing-4a-256',
      product_id: 'prod-nothing-4a',
      label: 'Black · 12GB RAM · 256GB Storage',
      asin: 'B0GRDH5D6Z',
      sku: 'NT-P4A-BLK',
      specs: {
        ram_gb: 12,
        storage_gb: 256,
        display_size_inches: null,
        battery_capacity_mah: 5080,
        processor: 'Snapdragon 7 Series',
        operating_system: 'Android 16',
        supports_5g: true
      }
    },
    match_state: 'probable',
    price: 43930,
    currency: 'INR',
    evaluation: {
      id: 'eval-nothing-01',
      overall_score: 8.1,
      category: 'smartphone',
      model_version: 'smartphones-v1.0',
      computed_at: '2026-10-25T14:00:00Z',
      confidence: {
        state: 'moderate',
        score: 0.78,
        coverage_percent: 78,
        evidence_count: 8
      },
      parameters: [
        { key: 'display', name: 'Display Quality & Calibrated Accuracy', score: null, weight: 0.25, unit: 'inches', raw_value: 'Unspecified in table', status: 'insufficient_evidence', tier1_evidence_count: 0 },
        { key: 'performance', name: 'Sustained Compute (Geekbench 6)', score: 8.2, weight: 0.25, unit: 'pts', raw_value: '1940 Single / 5800 Multi', status: 'scored', tier1_evidence_count: 2 },
        { key: 'battery', name: 'Battery Endurance & Drain Rate', score: 8.7, weight: 0.20, unit: 'hours', raw_value: '15.6h web browsing (5080mAh)', status: 'scored', tier1_evidence_count: 2 },
        { key: 'camera', name: 'Optics & Low Light Stabilization', score: 7.9, weight: 0.20, unit: 'sensor score', raw_value: '50MP OIS primary', status: 'scored', tier1_evidence_count: 1 },
        { key: 'thermal', name: 'Thermal Throttling & Stability Under Load', score: 8.6, weight: 0.10, unit: '% stability', raw_value: '88% stability in sustained loop', status: 'scored', tier1_evidence_count: 1 }
      ],
      grounded_explanation: 'The Nothing Phone 4a offers robust midrange power via the Snapdragon 7 Series and a high-capacity 5080 mAh cell. Note: Display size is marked Insufficient Evidence due to lack of verified screen diagonal in marketplace listing.'
    },
    community: {
      authentic_percentage: 85,
      suspicious_percentage: 15,
      total_reviews_analyzed: 54,
      sentiment_distribution: { positive: 80, neutral: 12, negative: 8 },
      top_positive_themes: ['Distinctive transparent aesthetic', 'Clean Nothing OS without ads', 'Fast tactile response'],
      top_criticisms: ['Plastic mid-frame feel', 'No in-box charger'],
      price_history: [
        { date: '2026-09-15', price: 45999, marketplace: 'Amazon India' },
        { date: '2026-10-01', price: 44499, marketplace: 'Amazon India' },
        { date: '2026-10-25', price: 43930, marketplace: 'Amazon India' }
      ],
      buy_timing_recommendation: 'buy_now',
      lowest_observed_price: 43930,
      highest_observed_price: 45999,
      current_price: 43930
    },
    evidence: [
      { id: 'ev-11', parameter: 'performance', tier: 'tier1', source_name: 'AnTuTu V10 Benchmarks', citation: 'Tested on Padget manufacturing batch: 890,400 overall score', value: '890k pts', measured_at: '2026-03-10T00:00:00Z', reliability: 'verified_lab' },
      { id: 'ev-12', parameter: 'battery', tier: 'tier2', source_name: 'Nothing Official Technical Sheet', citation: 'Rated 5080 mAh battery capacity @ 3.87V', value: '5080 mAh', measured_at: '2026-02-28T00:00:00Z', reliability: 'official_spec' }
    ]
  },
  {
    product: {
      id: 'prod-redmi-turbo-5',
      name: 'Redmi Turbo 5',
      brand: 'Redmi',
      category: 'smartphone',
      created_at: '2026-01-20T08:00:00Z',
      hero_image: 'https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=800&q=80'
    },
    variant: {
      id: 'var-redmi-turbo5-256',
      product_id: 'prod-redmi-turbo-5',
      label: 'Asphalt Black · 8GB RAM · 256GB Storage',
      asin: 'B0H297XH3K',
      sku: 'RD-TB5-BLK',
      specs: {
        ram_gb: 8,
        storage_gb: 256,
        display_size_inches: 6.59,
        battery_capacity_mah: 7540,
        processor: 'Dimensity 8500 Ultra',
        operating_system: 'Android 16',
        supports_5g: true
      }
    },
    match_state: 'confirmed',
    price: 40999,
    currency: 'INR',
    evaluation: {
      id: 'eval-redmi-01',
      overall_score: 8.4,
      category: 'smartphone',
      model_version: 'smartphones-v1.0',
      computed_at: '2026-10-25T11:00:00Z',
      confidence: {
        state: 'high',
        score: 0.92,
        coverage_percent: 94,
        evidence_count: 11
      },
      parameters: [
        { key: 'display', name: 'Display Quality & Calibrated Accuracy', score: 8.5, weight: 0.25, unit: 'inches / nits', raw_value: '6.59" 120Hz 1400 nits', status: 'scored', tier1_evidence_count: 2 },
        { key: 'performance', name: 'Sustained Compute (Geekbench 6)', score: 8.6, weight: 0.25, unit: 'pts', raw_value: '2210 Single / 7100 Multi', status: 'scored', tier1_evidence_count: 3 },
        { key: 'battery', name: 'Battery Endurance & Drain Rate', score: 9.7, weight: 0.20, unit: 'hours', raw_value: '22.4h continuous video (7540mAh)', status: 'scored', tier1_evidence_count: 3 },
        { key: 'camera', name: 'Optics & Low Light Stabilization', score: 7.4, weight: 0.20, unit: 'sensor score', raw_value: '50MP Sony Sensor', status: 'scored', tier1_evidence_count: 1 },
        { key: 'thermal', name: 'Thermal Throttling & Stability Under Load', score: 7.9, weight: 0.10, unit: '% stability', raw_value: '79% stability under load', status: 'scored', tier1_evidence_count: 2 }
      ],
      grounded_explanation: 'The Redmi Turbo 5 earns an exceptional 9.7 in Battery Endurance thanks to its class-leading 7,540 mAh silicon-carbon cell, delivering over 22 hours of active playback. Dimensity 8500 Ultra delivers competitive mid-range compute.'
    },
    community: {
      authentic_percentage: 82,
      suspicious_percentage: 18,
      total_reviews_analyzed: 887,
      sentiment_distribution: { positive: 72, neutral: 18, negative: 10 },
      top_positive_themes: ['Unmatched battery life that lasts 2 full days', '120W HyperCharge speed', '120Hz smooth animations'],
      top_criticisms: ['Preloaded third-party applications', 'Night camera soft edges'],
      price_history: [
        { date: '2026-08-01', price: 42999, marketplace: 'Amazon India' },
        { date: '2026-09-01', price: 41999, marketplace: 'Amazon India' },
        { date: '2026-10-25', price: 40999, marketplace: 'Amazon India' }
      ],
      buy_timing_recommendation: 'fair_price',
      lowest_observed_price: 39999,
      highest_observed_price: 42999,
      current_price: 40999
    },
    evidence: [
      { id: 'ev-21', parameter: 'battery', tier: 'tier1', source_name: 'BatteryBenchmark Labs', citation: 'Independent discharge test: 22h 15m screen-on time @ 200 nits', value: '22.4 hours', measured_at: '2026-02-05T00:00:00Z', reliability: 'verified_lab' }
    ]
  },
  {
    product: {
      id: 'prod-iphone-17-pro-max',
      name: 'Apple iPhone 17 Pro Max',
      brand: 'Apple',
      category: 'smartphone',
      created_at: '2026-09-20T08:00:00Z',
      hero_image: 'https://images.unsplash.com/photo-1591337676887-a217a6970a8a?auto=format&fit=crop&w=800&q=80'
    },
    variant: {
      id: 'var-iphone-17-pm-256',
      product_id: 'prod-iphone-17-pro-max',
      label: 'Silver · 256GB Storage',
      asin: 'B0FQFW4MVJ',
      sku: 'MFYM4HN/A',
      specs: {
        ram_gb: null,
        storage_gb: 256,
        display_size_inches: 6.9,
        battery_capacity_mah: null,
        processor: 'A19 Pro',
        operating_system: 'iOS',
        supports_5g: true
      }
    },
    match_state: 'probable',
    price: 144900,
    currency: 'INR',
    evaluation: {
      id: 'eval-iphone-01',
      overall_score: 9.1,
      category: 'smartphone',
      model_version: 'smartphones-v1.0',
      computed_at: '2026-10-25T15:00:00Z',
      confidence: {
        state: 'high',
        score: 0.96,
        coverage_percent: 92,
        evidence_count: 16
      },
      parameters: [
        { key: 'display', name: 'Display Quality & Calibrated Accuracy', score: 9.6, weight: 0.25, unit: 'nits / Hz', raw_value: '6.9" 120Hz ProMotion 3000 nits', status: 'scored', tier1_evidence_count: 4 },
        { key: 'performance', name: 'Sustained Compute (Geekbench 6)', score: 9.8, weight: 0.25, unit: 'pts', raw_value: '3850 Single / 11200 Multi', status: 'scored', tier1_evidence_count: 4 },
        { key: 'battery', name: 'Battery Endurance & Drain Rate', score: 8.9, weight: 0.20, unit: 'hours', raw_value: '19.8h video streaming', status: 'scored', tier1_evidence_count: 3 },
        { key: 'camera', name: 'Optics & Low Light Stabilization', score: 9.4, weight: 0.20, unit: 'sensor score', raw_value: '48MP Pro Fusion 4K120 ProRes', status: 'scored', tier1_evidence_count: 3 },
        { key: 'thermal', name: 'Thermal Throttling & Stability Under Load', score: 7.7, weight: 0.10, unit: '% stability', raw_value: 'Vapor chamber 77% stability', status: 'scored', tier1_evidence_count: 2 }
      ],
      grounded_explanation: 'Apple A19 Pro leads in single-thread IPC and neural processing. 6.9-inch display features 3,000 nits peak outdoor brightness. Note: RAM is unlisted by manufacturer (raw marketplace 0.1 GB placeholder rejected as implausible).'
    },
    community: {
      authentic_percentage: 91,
      suspicious_percentage: 9,
      total_reviews_analyzed: 693,
      sentiment_distribution: { positive: 84, neutral: 10, negative: 6 },
      top_positive_themes: ['Best-in-class 4K video recording with Center Stage', 'Impressive 6.9 inch bezel-less screen', 'Battery lasts well into second day'],
      top_criticisms: ['Substantial pricing', 'Slow wired charging (27W peak)'],
      price_history: [
        { date: '2026-09-25', price: 144900, marketplace: 'Amazon India' },
        { date: '2026-10-10', price: 144900, marketplace: 'Amazon India' },
        { date: '2026-10-25', price: 144900, marketplace: 'Amazon India' }
      ],
      buy_timing_recommendation: 'fair_price',
      lowest_observed_price: 144900,
      highest_observed_price: 144900,
      current_price: 144900
    },
    evidence: [
      { id: 'ev-31', parameter: 'performance', tier: 'tier1', source_name: 'AnandTech Architecture Teardown', citation: 'A19 Pro Die Analysis: 2x Performance + 6x Efficiency cores @ 4.2GHz', value: '11,200 multi', measured_at: '2026-09-28T00:00:00Z', reliability: 'verified_lab' }
    ]
  },
  {
    product: {
      id: 'prod-samsung-t9-ssd',
      name: 'Samsung T9 Portable SSD',
      brand: 'Samsung',
      category: 'ssd',
      created_at: '2025-11-10T08:00:00Z',
      hero_image: 'https://images.unsplash.com/photo-1597872200969-2b65d56bd16b?auto=format&fit=crop&w=800&q=80'
    },
    variant: {
      id: 'var-samsung-t9-2tb',
      product_id: 'prod-samsung-t9-ssd',
      label: '2TB USB 3.2 Gen 2x2',
      asin: 'B0CHKBX48S',
      sku: 'MU-PG2T0B',
      specs: {
        storage_gb: 2048,
        interface: 'USB 3.2 Gen 2x2 (20Gbps)',
        max_read_mb_s: 2000,
        max_write_mb_s: 2000,
        weight_grams: 122
      }
    },
    match_state: 'confirmed',
    price: 18499,
    currency: 'INR',
    evaluation: {
      id: 'eval-t9-01',
      overall_score: 8.9,
      category: 'ssd',
      model_version: 'ssd-v1.0',
      computed_at: '2026-10-18T10:00:00Z',
      confidence: {
        state: 'high',
        score: 0.94,
        coverage_percent: 98,
        evidence_count: 12
      },
      parameters: [
        { key: 'seq_rw', name: 'Sequential Read/Write Speeds (MB/s)', score: 9.5, weight: 0.30, unit: 'MB/s', raw_value: '2015 MB/s Read / 1980 MB/s Write', status: 'scored', tier1_evidence_count: 4 },
        { key: 'sustained_write', name: 'Sustained Write Speed (Post-SLC cache)', score: 8.6, weight: 0.30, unit: 'MB/s', raw_value: '1020 MB/s steady state', status: 'scored', tier1_evidence_count: 3 },
        { key: 'thermal_mgmt', name: 'Thermal Management & Dynamic Thermal Guard', score: 8.7, weight: 0.20, unit: 'temp °C', raw_value: 'Max 48°C exterior under 1TB continuous write', status: 'scored', tier1_evidence_count: 3 },
        { key: 'durability', name: 'Drop Resistance & Rubberized Ingress', score: 8.8, weight: 0.20, unit: 'meters', raw_value: '3-meter drop test verified', status: 'scored', tier1_evidence_count: 2 }
      ],
      grounded_explanation: 'Samsung T9 delivers top-tier 20Gbps sustained performance over USB 3.2 Gen 2x2. Dynamic Thermal Guard keeps enclosure temperatures below 49°C even when transferring 1TB file libraries.'
    },
    community: {
      authentic_percentage: 94,
      suspicious_percentage: 6,
      total_reviews_analyzed: 320,
      sentiment_distribution: { positive: 88, neutral: 8, negative: 4 },
      top_positive_themes: ['Fast transfers for ProRes 4K footage', 'Grippy silicone casing', 'Backwards compatible with Mac and PC'],
      top_criticisms: ['Needs a dedicated USB 3.2 Gen 2x2 port for full 2000MB/s speed'],
      price_history: [
        { date: '2026-08-01', price: 19999, marketplace: 'Amazon India' },
        { date: '2026-09-01', price: 18999, marketplace: 'Amazon India' },
        { date: '2026-10-25', price: 18499, marketplace: 'Amazon India' }
      ],
      buy_timing_recommendation: 'buy_now',
      lowest_observed_price: 17999,
      highest_observed_price: 21999,
      current_price: 18499
    },
    evidence: [
      { id: 'ev-ssd-01', parameter: 'seq_rw', tier: 'tier1', source_name: 'StorageReview Enterprise Lab', citation: 'CrystalDiskMark v8.0.4: 2018.4 MB/s Read, 1984.1 MB/s Write', value: '2018 MB/s', measured_at: '2026-01-14T00:00:00Z', reliability: 'verified_lab' }
    ]
  }
];
