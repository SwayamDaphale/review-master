import { describe, expect, it } from 'vitest';
import { SAMPLE_EXTRACTION, SAMPLE_EXTRACTION_PARTIAL, parseExtractedJson } from './extensionImport';

describe('parseExtractedJson', () => {
  it('accepts the extension output and lists what was not captured', () => {
    const r = parseExtractedJson(SAMPLE_EXTRACTION);
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.value.brand).toBe('Samsung');
      expect(r.value.ram_gb).toBe(12);
      expect(r.missing).toContain('model_number');
      expect(r.missing).not.toContain('battery_capacity_mah');
    }
  });

  it('keeps missing values as null, never zero', () => {
    const r = parseExtractedJson(SAMPLE_EXTRACTION_PARTIAL);
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.value.battery_capacity_mah).toBeNull();
      expect(r.value.ram_gb).toBeNull();
      expect(r.missing).toEqual(expect.arrayContaining(['battery_capacity_mah', 'ram_gb', 'operating_system']));
    }
  });

  it('rejects text that is not JSON', () => {
    const r = parseExtractedJson('not json');
    expect(r.ok).toBe(false);
  });

  it('rejects other categories', () => {
    const r = parseExtractedJson(JSON.stringify({ category: 'laptop', brand: 'X', model_name: 'Y' }));
    expect(r).toMatchObject({ ok: false });
  });

  it('rejects wrong field types', () => {
    const r = parseExtractedJson(JSON.stringify({ category: 'smartphone', brand: 'X', model_name: 'Y', ram_gb: '12' }));
    expect(r).toMatchObject({ ok: false });
  });

  it('needs a brand and model to identify the product', () => {
    const r = parseExtractedJson(JSON.stringify({ category: 'smartphone', brand: null, model_name: null }));
    expect(r).toMatchObject({ ok: false });
  });

  it('accepts full extension snapshot containing normalized sub-object', () => {
    const fullSnapshot = JSON.stringify({
      schema_version: '1.0',
      source: {
        marketplace: 'amazon.in',
        product_url: 'https://www.amazon.in/dp/B0CX8BC2MW',
        extracted_at: '2026-11-05T12:00:00Z',
        extraction_method: 'browser_extension_user_initiated',
        extension_version: '1.0.0',
        page_title: 'Samsung Galaxy S24 5G',
        asin: 'B0CX8BC2MW'
      },
      raw_extraction: { title: 'Samsung Galaxy S24 5G' },
      normalized: {
        category: 'smartphone',
        brand: 'Samsung',
        model_name: 'Galaxy S24',
        model_number: 'SM-S921B',
        ram_gb: 8,
        storage_gb: 128,
        display_size_inches: 6.2,
        battery_capacity_mah: 4000,
        operating_system: 'Android 14',
        supports_5g: true,
        price_amount: 74999,
        currency: 'INR',
        availability: 'in_stock',
        rating: 4.5,
        review_count: 1200
      },
      validation: { status: 'valid', identity_status: 'identified', warnings: [], errors: [] }
    });
    const r = parseExtractedJson(fullSnapshot);
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.value.brand).toBe('Samsung');
      expect(r.value.model_name).toBe('Galaxy S24');
      expect(r.value.ram_gb).toBe(8);
      expect(r.value.storage_gb).toBe(128);
    }
  });
});
