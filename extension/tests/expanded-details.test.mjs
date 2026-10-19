import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { buildExtractionRecord, extractRawSpecifications } from '../src/extractor.mjs';
import { validateSmartphoneRecord } from '../src/schema-validator.mjs';
import {
  normalizeDisplaySize,
  extractDisplayFromText,
  extractBatteryFromText,
  extractModelFromTitle,
  extractProcessorFromText
} from '../src/normalizers.mjs';

describe('Expanded Amazon India Layouts & Specification Extraction', () => {

  it('correctly resolves Samsung Galaxy S25 Ultra model and display size from title and expanded specs', () => {
    // Problem scenario: Model Name missing from spec table, but title has model and 12GB RAM;
    // technical specifications table has "Standing screen display size: 17.47 cm (6.88")"
    const mockDoc = {
      title: "Samsung Galaxy S25 Ultra 5G AI Smartphone (Titanium Black, 12GB RAM, 256GB Storage) : Amazon.in",
      querySelector: (sel) => {
        if (sel === '#productTitle') return { textContent: "Samsung Galaxy S25 Ultra 5G AI Smartphone (Titanium Black, 12GB RAM, 256GB Storage)" };
        if (sel === '#bylineInfo') return { textContent: "Brand: Samsung" };
        if (sel === '.a-price .a-offscreen') return { textContent: "₹1,29,999" };
        if (sel === '#acrPopover') return { getAttribute: () => "4.8 out of 5 stars", textContent: '' };
        if (sel === '#acrCustomerReviewText') return { textContent: "340 ratings" };
        if (sel === '#availability span') return { textContent: "In stock." };
        if (sel === '#variation_size_name .selection') return { textContent: "12GB+256GB" };
        return null;
      },
      querySelectorAll: (sel) => {
        if (sel.includes('#prodDetails') || sel.includes('#technicalSpecifications_section_1')) {
          return [
            { label: "Brand", value: "Samsung" },
            { label: "Standing screen display size", value: '17.47 cm (6.88")' },
            { label: "Battery Capacity", value: "5000 mAh" },
            { label: "Processor", value: "Snapdragon 8 Elite" },
            { label: "Operating System", value: "Android 15.0" },
            { label: "Cellular Technology", value: "5G" }
          ].map(s => ({
            tagName: 'tr',
            querySelector: (sub) => {
              if (sub.includes('th') || sub.includes('first-child')) return { textContent: s.label };
              if (sub.includes('td') || sub.includes('last-child')) return { textContent: s.value };
              return null;
            }
          }));
        }
        return [];
      }
    };

    const record = buildExtractionRecord({
      url: 'https://www.amazon.in/Samsung-Galaxy-Ultra-Titanium-Storage/dp/B0D1234567',
      doc: mockDoc
    });

    const valResult = validateSmartphoneRecord(record);
    assert.equal(valResult.valid, true, `Validation errors: ${JSON.stringify(valResult.errors)}`);

    // Model name unambiguously resolved from title fallback
    assert.equal(record.normalized.brand, 'Samsung');
    assert.equal(record.normalized.model_name, 'Galaxy S25 Ultra');
    assert.equal(record.normalized.ram_gb, 12);
    assert.equal(record.normalized.storage_gb, 256);
    // Display size extracted from parenthetical inches inside cm spec
    assert.equal(record.normalized.display_size_inches, 6.88);
    assert.equal(record.normalized.battery_capacity_mah, 5000);
    assert.equal(record.normalized.processor, 'Snapdragon 8 Elite');
    assert.equal(record.validation.status, 'valid');
    assert.equal(record.validation.identity_status, 'identified');
  });

  it('extracts RAM when label contains colon or spacing like "RAM Memory: 8 GB"', () => {
    // Problem scenario: Table has "RAM Memory:" with colon, which previously broke exact regex match
    const mockDoc = {
      title: "REDMI Turbo 5 (8GB + 256GB) Asphalt Black",
      querySelector: (sel) => {
        if (sel === '#productTitle') return { textContent: "REDMI Turbo 5 (8GB + 256GB) Asphalt Black" };
        if (sel === '#bylineInfo') return { textContent: "Brand: Redmi" };
        if (sel === '.a-price .a-offscreen') return { textContent: "₹40,999" };
        return null;
      },
      querySelectorAll: (sel) => {
        if (sel.includes('#prodDetails')) {
          return [
            { label: "Brand: ", value: "Redmi" },
            { label: "Model Name", value: "Turbo 5" },
            { label: "RAM Memory: ", value: "8 GB" },
            { label: "Memory Storage Capacity: ", value: "256 GB" },
            { label: "Screen Size: ", value: "6.59 Inches" },
            { label: "Battery Capacity: ", value: "7540 mAh" },
            { label: "Processor: ", value: "MediaTek Dimensity 8500 Ultra" }
          ].map(s => ({
            tagName: 'tr',
            querySelector: (sub) => {
              if (sub.includes('th') || sub.includes('first-child')) return { textContent: s.label };
              if (sub.includes('td') || sub.includes('last-child')) return { textContent: s.value };
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

    assert.equal(record.normalized.ram_gb, 8);
    assert.notEqual(record.normalized.ram_gb, null);
    assert.equal(record.normalized.storage_gb, 256);
    assert.equal(record.normalized.display_size_inches, 6.59);
    assert.equal(record.normalized.battery_capacity_mah, 7540);
    assert.equal(record.normalized.processor, 'MediaTek Dimensity 8500 Ultra');
    assert.equal(record.validation.status, 'valid');
  });

  it('extracts specs from div-based product overview grid (.a-row)', () => {
    const mockDoc = {
      title: "OnePlus Nord CE4 5G (Dark Chrome, 8GB RAM, 128GB Storage)",
      querySelector: (sel) => {
        if (sel === '#productTitle') return { textContent: "OnePlus Nord CE4 5G (Dark Chrome, 8GB RAM, 128GB Storage)" };
        if (sel === '#bylineInfo') return { textContent: "Brand: OnePlus" };
        return null;
      },
      querySelectorAll: (sel) => {
        if (sel.includes('#productOverview_feature_div .a-row')) {
          return [
            { label: "Brand", value: "OnePlus" },
            { label: "Model Name", value: "Nord CE4" },
            { label: "Operating System", value: "OxygenOS 14.0" },
            { label: "RAM Memory Installed Size", value: "8 GB" },
            { label: "CPU Model", value: "Snapdragon 7 Gen 3" },
            { label: "Memory Storage Capacity", value: "128 GB" },
            { label: "Screen Size", value: "6.7 Inches" }
          ].map(s => ({
            querySelector: (sub) => {
              if (sub.includes('first-child') || sub.includes('a-span3')) return { textContent: s.label };
              if (sub.includes('last-child') || sub.includes('a-span9')) return { textContent: s.value };
              return null;
            }
          }));
        }
        return [];
      }
    };

    const specs = extractRawSpecifications(mockDoc);
    assert.ok(specs.some(s => s.label === 'RAM Memory Installed Size' && s.value === '8 GB'));
    assert.ok(specs.some(s => s.label === 'Screen Size' && s.value === '6.7 Inches'));
    assert.ok(specs.some(s => s.label === 'CPU Model' && s.value === 'Snapdragon 7 Gen 3'));
  });

  it('extracts specs from "About this item" feature bullets when table is minimal', () => {
    const mockDoc = {
      title: "Xiaomi 14 Ultra (Black, 16GB RAM, 512GB Storage)",
      querySelector: (sel) => {
        if (sel === '#productTitle') return { textContent: "Xiaomi 14 Ultra (Black, 16GB RAM, 512GB Storage)" };
        if (sel === '#bylineInfo') return { textContent: "Brand: Xiaomi" };
        return null;
      },
      querySelectorAll: (sel) => {
        if (sel.includes('#feature-bullets')) {
          return [
            { textContent: "Processor: Snapdragon 8 Gen 3 Mobile Platform" },
            { textContent: "Display: 17.09cm (6.73 inch) WQHD+ 120Hz AMOLED" },
            { textContent: "Battery: 5000mAh high-density battery with 90W HyperCharge" },
            { textContent: "Camera: 50MP Quad Camera with Leica Optics" }
          ];
        }
        return [];
      }
    };

    const record = buildExtractionRecord({
      url: 'https://www.amazon.in/dp/B0D5555555',
      doc: mockDoc
    });

    assert.equal(record.normalized.brand, 'Xiaomi');
    assert.equal(record.normalized.model_name, '14 Ultra');
    assert.equal(record.normalized.ram_gb, 16);
    assert.equal(record.normalized.storage_gb, 512);
    assert.equal(record.normalized.display_size_inches, 6.73);
    assert.equal(record.normalized.battery_capacity_mah, 5000);
    assert.equal(record.normalized.processor, 'Snapdragon 8 Gen 3');
  });

  it('strictly ignores irrelevant page content like sponsored items and recommendations', () => {
    const mockDoc = {
      title: "Redmi A3 (Midnight Black, 3GB RAM, 64GB Storage)",
      querySelector: (sel) => {
        if (sel === '#productTitle') return { textContent: "Redmi A3 (Midnight Black, 3GB RAM, 64GB Storage)" };
        if (sel === '#bylineInfo') return { textContent: "Brand: Redmi" };
        // Irrelevant sponsored elements that must NEVER be parsed
        if (sel === '#sp_detail') return { textContent: "iPhone 15 Pro Max 1TB" };
        return null;
      },
      querySelectorAll: (sel) => {
        // Only return specs when targeting product overview or product details
        if (sel.includes('#prodDetails')) {
          return [
            { label: "Brand", value: "Redmi" },
            { label: "Model Name", value: "Redmi A3" },
            { label: "RAM", value: "3 GB" },
            { label: "Storage", value: "64 GB" }
          ].map(s => ({
            tagName: 'tr',
            querySelector: (sub) => {
              if (sub.includes('th') || sub.includes('first-child')) return { textContent: s.label };
              if (sub.includes('td') || sub.includes('last-child')) return { textContent: s.value };
              return null;
            }
          }));
        }
        return [];
      }
    };

    const record = buildExtractionRecord({
      url: 'https://www.amazon.in/dp/B0CXREDMIA3',
      doc: mockDoc
    });

    assert.equal(record.normalized.brand, 'Redmi');
    assert.equal(record.normalized.model_name, 'Redmi A3');
    assert.equal(record.normalized.ram_gb, 3);
    assert.equal(record.normalized.storage_gb, 64);
    // Does not touch iPhone from sponsored ad
    assert.notEqual(record.normalized.brand, 'Apple');
  });

  it('handles conflicting evidence between selected variant and table specs safely', () => {
    const mockDoc = {
      title: "Motorola Edge 50 Pro (8GB RAM, 256GB Storage)",
      querySelector: (sel) => {
        if (sel === '#productTitle') return { textContent: "Motorola Edge 50 Pro (8GB RAM, 256GB Storage)" };
        if (sel === '#bylineInfo') return { textContent: "Brand: Motorola" };
        // User selected the 12GB+256GB variant on the page
        if (sel === '#variation_size_name .selection') return { textContent: "12GB + 256GB" };
        return null;
      },
      querySelectorAll: (sel) => {
        if (sel.includes('#prodDetails')) {
          return [
            { label: "Brand", value: "Motorola" },
            { label: "Model Name", value: "Edge 50 Pro" },
            { label: "RAM", value: "8 GB" }, // Table was for 8GB
            { label: "Storage", value: "256 GB" }
          ].map(s => ({
            tagName: 'tr',
            querySelector: (sub) => {
              if (sub.includes('th') || sub.includes('first-child')) return { textContent: s.label };
              if (sub.includes('td') || sub.includes('last-child')) return { textContent: s.value };
              return null;
            }
          }));
        }
        return [];
      }
    };

    const record = buildExtractionRecord({
      url: 'https://www.amazon.in/dp/B0D1MOTO50',
      doc: mockDoc
    });

    // Selected variant 12 GB takes precedence
    assert.equal(record.normalized.ram_gb, 12);
    assert.equal(record.normalized.storage_gb, 256);
    // Warning recorded regarding table precedence
    assert.ok(record.validation.warnings.some(w => w.includes('precedence')));
  });

  it('keeps unavailable fields as null and never substitutes zero', () => {
    const mockDoc = {
      title: "Feature Phone Basic (No Camera)",
      querySelector: (sel) => {
        if (sel === '#productTitle') return { textContent: "Feature Phone Basic (No Camera)" };
        if (sel === '#bylineInfo') return { textContent: "Brand: Generic" };
        return null;
      },
      querySelectorAll: () => []
    };

    const record = buildExtractionRecord({
      url: 'https://www.amazon.in/dp/B0D0000000',
      doc: mockDoc
    });

    assert.equal(record.normalized.ram_gb, null);
    assert.notEqual(record.normalized.ram_gb, 0);
    assert.equal(record.normalized.storage_gb, null);
    assert.notEqual(record.normalized.storage_gb, 0);
    assert.equal(record.normalized.display_size_inches, null);
    assert.notEqual(record.normalized.display_size_inches, 0);
    assert.equal(record.normalized.battery_capacity_mah, null);
    assert.notEqual(record.normalized.battery_capacity_mah, 0);
    assert.equal(record.normalized.price_amount, null);
    assert.notEqual(record.normalized.price_amount, 0);

    assert.equal(record.validation.status, 'needs_review');
  });

  it('correctly extracts iPhone 17 Pro Max with unicode curly quotes, A-series processor, and filters placeholder specs', () => {
    // Exact scenario from user:
    // Title: Apple iPhone 17 Pro Max 256 GB: 17.42 cm (6.9") Display with Promotion, A19 Pro Chip...
    // Specs table has CPU Speed: 0.1 GHz and RAM: 0.1 (bogus seller placeholder)
    const mockDoc = {
      title: 'Apple iPhone 17 Pro Max 256 GB: 17.42 cm (6.9") Display with Promotion, A19 Pro Chip : Amazon.in',
      querySelector: (sel) => {
        if (sel === '#productTitle') {
          return { textContent: 'Apple iPhone 17 Pro Max 256 GB: 17.42 cm (6.9") Display with Promotion, A19 Pro Chip, Best Battery Life in Any iPhone Ever, Pro Fusion Camera System, Center Stage Front Camera; Silver' };
        }
        if (sel === '#bylineInfo') return { textContent: 'Visit the Apple Store' };
        if (sel === '.a-price .a-offscreen') return { textContent: '₹ 1,44,900' };
        if (sel === '#availability span') return { textContent: 'In stock.' };
        return null;
      },
      querySelectorAll: (sel) => {
        if (sel.includes('#prodDetails') || sel.includes('table.a-keyvalue')) {
          return [
            { label: 'Brand', value: 'Apple' },
            { label: 'Operating System', value: 'iOS' },
            { label: 'CPU Speed', value: '0.1 GHz' }, // Bogus speed that should not replace processor
            { label: 'RAM Memory Installed Size', value: '0.1' }, // Bogus RAM placeholder < 1 GB
            { label: 'Standing screen display size', value: '17.42 cm (6.9")' },
            { label: 'Cellular Technology', value: '5G' }
          ].map(s => ({
            tagName: 'tr',
            querySelector: (sub) => {
              if (sub.includes('th') || sub.includes('first-child')) return { textContent: s.label };
              if (sub.includes('td') || sub.includes('last-child')) return { textContent: s.value };
              return null;
            }
          }));
        }
        return [];
      }
    };

    const record = buildExtractionRecord({
      url: 'https://www.amazon.in/iPhone-Pro-Max-256-Promotion/dp/B0FQFW4MVJ',
      doc: mockDoc
    });

    const valResult = validateSmartphoneRecord(record);
    assert.equal(valResult.valid, true, `Validation errors: ${JSON.stringify(valResult.errors)}`);

    // Model name cleanly extracted without storage or colon text
    assert.equal(record.normalized.brand, 'Apple');
    assert.equal(record.normalized.model_name, 'iPhone 17 Pro Max');

    // Storage cleanly extracted as 256 GB
    assert.equal(record.normalized.storage_gb, 256);

    // RAM is null because 0.1 is rejected as invalid smartphone RAM (Apple does not state RAM on Amazon)
    assert.equal(record.normalized.ram_gb, null);

    // Display size extracted from 17.42 cm (6.9")
    assert.equal(record.normalized.display_size_inches, 6.9);

    // Processor correctly extracted as A19 Pro (not 0.1 GHz from CPU speed row)
    assert.equal(record.normalized.processor, 'A19 Pro');

    // 5G recognized
    assert.equal(record.normalized.supports_5g, true);

    // OS is iOS
    assert.equal(record.normalized.operating_system, 'iOS');

    // Price is ₹1,44,900
    assert.equal(record.normalized.price_amount, 144900);
  });
});
