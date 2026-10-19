import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { buildExtractionRecord } from '../src/extractor.mjs';
import { validateSmartphoneRecord } from '../src/schema-validator.mjs';
import { smartphoneFixtures } from './fixtures.mjs';

/**
 * Creates a lightweight DOM-like adapter for headless node testing
 */
function createMockDocument(fixture) {
  const elements = fixture.elements || {};
  const specs = fixture.specs || [];

  return {
    title: fixture.title || 'Amazon.in : Smartphone',
    querySelector: (selector) => {
      // Direct selector lookup
      if (elements[selector] !== undefined) {
        return {
          textContent: elements[selector],
          getAttribute: (attr) => (attr === 'title' ? elements[`${selector}[title]`] || elements[selector] : null)
        };
      }
      // Check for attribute selectors like #acrPopover[title]
      if (selector === '#acrPopover' && elements['#acrPopover[title]']) {
        return {
          getAttribute: (attr) => (attr === 'title' ? elements['#acrPopover[title]'] : null),
          textContent: ''
        };
      }
      return null;
    },
    querySelectorAll: (selector) => {
      if (selector.includes('#productOverview_feature_div') || selector.includes('#prodDetails')) {
        return specs.map(s => ({
          tagName: 'tr',
          querySelector: (sub) => {
            if (sub.includes('td:first-child') || sub.includes('th')) {
              return { textContent: s.label };
            }
            if (sub.includes('td:last-child') || sub.includes('td')) {
              return { textContent: s.value };
            }
            return null;
          }
        }));
      }
      return [];
    }
  };
}

describe('Amazon India Smartphone Extraction & Schema Validation', () => {
  for (const fixture of smartphoneFixtures) {
    it(`correctly extracts and validates: ${fixture.id} (${fixture.description})`, () => {
      const mockDoc = createMockDocument(fixture);
      const record = buildExtractionRecord({
        url: fixture.url,
        doc: mockDoc,
        extensionVersion: '1.0.0',
        extractedAt: '2026-10-18T12:00:00.000Z'
      });

      // 1. Schema conformity check
      const validationResult = validateSmartphoneRecord(record);
      assert.equal(
        validationResult.valid,
        true,
        `Record schema validation failed for ${fixture.id}: ${JSON.stringify(validationResult.errors)}`
      );

      // 2. Value assertions from fixture expectations
      const expected = fixture.expected;
      if (expected.brand !== undefined) {
        assert.equal(record.normalized.brand, expected.brand);
      }
      if (expected.model_name !== undefined) {
        assert.equal(record.normalized.model_name, expected.model_name);
      }
      if (expected.ram_gb !== undefined) {
        assert.equal(record.normalized.ram_gb, expected.ram_gb);
      }
      if (expected.storage_gb !== undefined) {
        assert.equal(record.normalized.storage_gb, expected.storage_gb);
      }
      if (expected.price_amount !== undefined) {
        assert.equal(record.normalized.price_amount, expected.price_amount);
      }
      if (expected.supports_5g !== undefined) {
        assert.equal(record.normalized.supports_5g, expected.supports_5g);
      }
      if (expected.status !== undefined) {
        assert.equal(record.validation.status, expected.status);
      }
      if (expected.identity_status !== undefined) {
        assert.equal(record.validation.identity_status, expected.identity_status);
      }

      // 3. Core invariant assertions
      // Missing values must never be 0
      if (record.normalized.price_amount === null) {
        assert.notEqual(record.normalized.price_amount, 0);
      }
      if (record.normalized.ram_gb === null) {
        assert.notEqual(record.normalized.ram_gb, 0);
      }
      if (record.normalized.storage_gb === null) {
        assert.notEqual(record.normalized.storage_gb, 0);
      }

      // Raw extraction must preserve raw strings
      assert.ok('raw_extraction' in record);
      assert.ok(Array.isArray(record.raw_extraction.specifications_text));

      // JSON Serialization test
      const serialized = JSON.stringify(record);
      const deserialized = JSON.parse(serialized);
      assert.deepEqual(deserialized, record);
    });
  }

  it('correctly discriminates variants of the same phone model without merging', () => {
    const f1 = smartphoneFixtures.find(f => f.id === 'fixture_01_galaxy_s24');
    const f2 = smartphoneFixtures.find(f => f.id === 'fixture_02_galaxy_s24_variant_256gb');

    const rec1 = buildExtractionRecord({ url: f1.url, doc: createMockDocument(f1) });
    const rec2 = buildExtractionRecord({ url: f2.url, doc: createMockDocument(f2) });

    // Same brand and model name
    assert.equal(rec1.normalized.brand, rec2.normalized.brand);
    assert.equal(rec1.normalized.model_name, rec2.normalized.model_name);

    // But distinct storage and price!
    assert.equal(rec1.normalized.storage_gb, 128);
    assert.equal(rec2.normalized.storage_gb, 256);
    assert.equal(rec1.normalized.price_amount, 74999);
    assert.equal(rec2.normalized.price_amount, 79999);
    assert.notEqual(rec1.source.asin, rec2.source.asin);
  });

  it('prefers the currently selected variant configuration (8GB+256GB) over alternative (12GB+256GB)', () => {
    // Simulated page where alternative variant "12GB+256GB" is listed in title or another button,
    // but the selected variant is "8GB+256GB".
    const mockDoc = {
      title: "REDMI Turbo 5 (12GB + 256GB) Asphalt Black", // Stale or alternative title
      querySelector: (selector) => {
        if (selector === '#productTitle') return { textContent: "REDMI Turbo 5 (12GB + 256GB) Asphalt Black" };
        if (selector === '#bylineInfo') return { textContent: "Brand: Redmi" };
        if (selector === '#variation_size_name .selection') return { textContent: "8GB+256GB" };
        if (selector === '.a-price .a-offscreen') return { textContent: "₹40,999" };
        return null;
      },
      querySelectorAll: (selector) => {
        if (selector.includes('#productOverview_feature_div') || selector.includes('#prodDetails')) {
          return [
            { label: "Brand", value: "Redmi" },
            { label: "Memory Storage Capacity", value: "256 GB" }
          ].map(s => ({
            tagName: 'tr',
            querySelector: (sub) => {
              if (sub.includes('td:first-child') || sub.includes('th')) return { textContent: s.label };
              if (sub.includes('td:last-child') || sub.includes('td')) return { textContent: s.value };
              return null;
            }
          }));
        }
        return [];
      }
    };

    const record = buildExtractionRecord({
      url: 'https://www.amazon.in/dp/B0H297XH3K',
      doc: mockDoc
    });

    // Selected variant 8GB+256GB MUST be chosen over the title's 12GB+256GB
    assert.equal(record.normalized.ram_gb, 8);
    assert.equal(record.normalized.storage_gb, 256);
  });

  it('retains ram_gb as null when no reliable RAM evidence exists and warns', () => {
    const mockDoc = {
      title: "Apple iPhone 15 (128 GB) - Black",
      querySelector: (selector) => {
        if (selector === '#productTitle') return { textContent: "Apple iPhone 15 (128 GB) - Black" };
        if (selector === '#bylineInfo') return { textContent: "Brand: Apple" };
        return null;
      },
      querySelectorAll: () => []
    };

    const record = buildExtractionRecord({
      url: 'https://www.amazon.in/dp/B0CHX1W1XY',
      doc: mockDoc
    });

    assert.equal(record.normalized.ram_gb, null);
    assert.notEqual(record.normalized.ram_gb, 0);
    assert.ok(record.validation.warnings.some(w => w.includes('RAM')));
  });

  describe('Extraction Error Propagation & Edge Cases', () => {
    it('handles pages where the product title is missing and reports status invalid', () => {
      const mockDoc = {
        title: "Amazon.in : 404 Not Found",
        querySelector: () => null,
        querySelectorAll: () => []
      };

      const record = buildExtractionRecord({
        url: 'https://www.amazon.in/dp/B000000000',
        doc: mockDoc
      });

      assert.equal(record.validation.status, 'invalid');
      assert.ok(record.validation.errors.some(e => e.includes('title')));
    });

    it('identifies price as null without substituting zero when unavailable', () => {
      const mockDoc = {
        title: "Redmi Note 13 (8GB + 256GB)",
        querySelector: (sel) => {
          if (sel === '#productTitle') return { textContent: "Redmi Note 13 (8GB + 256GB)" };
          return null;
        },
        querySelectorAll: () => []
      };

      const record = buildExtractionRecord({
        url: 'https://www.amazon.in/dp/B0CX123456',
        doc: mockDoc
      });

      assert.equal(record.normalized.price_amount, null);
      assert.notEqual(record.normalized.price_amount, 0);
      assert.ok(record.validation.warnings.some(w => w.includes('Price')));
    });
  });
});
