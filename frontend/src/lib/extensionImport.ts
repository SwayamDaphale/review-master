import type { ExtractedSmartphone } from '../types/api';

export type ImportResult =
  | { ok: true; value: ExtractedSmartphone; missing: string[] }
  | { ok: false; error: string };

const NUMBER_FIELDS = [
  'battery_capacity_mah',
  'display_size_inches',
  'price_amount',
  'ram_gb',
  'rating',
  'review_count',
  'storage_gb',
] as const;

const STRING_FIELDS = [
  'availability',
  'brand',
  'currency',
  'model_name',
  'model_number',
  'operating_system',
  'processor',
] as const;

export const FIELD_LABEL: Record<string, string> = {
  availability: 'Availability',
  battery_capacity_mah: 'Battery capacity',
  brand: 'Brand',
  currency: 'Currency',
  display_size_inches: 'Display size',
  model_name: 'Model',
  model_number: 'Model number',
  operating_system: 'Operating system',
  price_amount: 'Price',
  processor: 'Processor',
  ram_gb: 'RAM',
  rating: 'Marketplace rating',
  review_count: 'Marketplace rating count',
  storage_gb: 'Storage',
  supports_5g: '5G support',
};

/** Validates the JSON produced by the Review Master browser extension. Nulls are kept as null. */
export function parseExtractedJson(text: string): ImportResult {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    return { ok: false, error: 'This is not valid JSON. Paste the file exactly as the extension downloaded it.' };
  }
  if (typeof data !== 'object' || data === null || Array.isArray(data)) {
    return { ok: false, error: 'Expected one JSON object describing one product.' };
  }
  let obj = data as Record<string, unknown>;
  // Unwrap full extension snapshot ({ schema_version, source, normalized: { ... } }) if present
  if (obj.normalized && typeof obj.normalized === 'object' && !Array.isArray(obj.normalized)) {
    obj = obj.normalized as Record<string, unknown>;
  }
  if (obj.category !== 'smartphone') {
    return { ok: false, error: 'Only smartphone data is supported right now (category must be "smartphone").' };
  }

  const out: Record<string, unknown> = { category: 'smartphone' };
  const missing: string[] = [];

  for (const key of NUMBER_FIELDS) {
    const v = obj[key];
    if (v === undefined || v === null) {
      out[key] = null;
      missing.push(key);
    } else if (typeof v === 'number' && Number.isFinite(v)) {
      out[key] = v;
    } else {
      return { ok: false, error: `Field "${key}" must be a number or null.` };
    }
  }
  for (const key of STRING_FIELDS) {
    const v = obj[key];
    if (v === undefined || v === null || v === '') {
      out[key] = null;
      missing.push(key);
    } else if (typeof v === 'string') {
      out[key] = v;
    } else {
      return { ok: false, error: `Field "${key}" must be text or null.` };
    }
  }
  const g = obj.supports_5g;
  if (g === undefined || g === null) {
    out.supports_5g = null;
    missing.push('supports_5g');
  } else if (typeof g === 'boolean') {
    out.supports_5g = g;
  } else {
    return { ok: false, error: 'Field "supports_5g" must be true, false or null.' };
  }

  if (!out.brand || !out.model_name) {
    return { ok: false, error: 'The data needs at least a brand and a model name to be identified.' };
  }
  return { ok: true, value: out as unknown as ExtractedSmartphone, missing };
}

/** The sample from the extension screenshot (Samsung Galaxy S25 Ultra on Amazon India). */
export const SAMPLE_EXTRACTION = JSON.stringify(
  {
    availability: 'in_stock',
    battery_capacity_mah: 5000,
    brand: 'Samsung',
    category: 'smartphone',
    currency: 'INR',
    display_size_inches: 6.9,
    model_name: 'Galaxy S25 Ultra',
    model_number: null,
    operating_system: 'Android 16',
    price_amount: 94999,
    processor: 'Snapdragon 8 Elite',
    ram_gb: 12,
    rating: 4.4,
    review_count: 3492,
    storage_gb: 256,
    supports_5g: true,
  },
  null,
  2,
);

/** Second sample: iPhone 17 Pro Max where battery was not captured and the processor read as "Others". */
export const SAMPLE_EXTRACTION_PARTIAL = JSON.stringify(
  {
    availability: 'in_stock',
    battery_capacity_mah: null,
    brand: 'Apple',
    category: 'smartphone',
    currency: 'INR',
    display_size_inches: 6.9,
    model_name: 'iPhone 17 Pro Max',
    model_number: null,
    operating_system: null,
    price_amount: 184900,
    processor: 'Others',
    ram_gb: null,
    rating: 4.6,
    review_count: 682,
    storage_gb: 1024,
    supports_5g: true,
  },
  null,
  2,
);
