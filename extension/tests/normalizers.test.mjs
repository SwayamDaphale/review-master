import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  cleanText,
  extractAsinFromUrl,
  normalizePrice,
  normalizeRating,
  normalizeReviewCount,
  normalizeRam,
  normalizeStorage,
  normalizeDisplaySize,
  normalizeBattery,
  normalize5G,
  normalizeOperatingSystem,
  normalizeAvailability,
  extractConfigFromText,
  extractDisplayFromText,
  extractBatteryFromText,
  extractModelFromTitle,
  extractProcessorFromText
} from '../src/normalizers.mjs';

describe('Normalizers Unit Tests', () => {
  it('cleanText trims and collapses whitespace', () => {
    assert.equal(cleanText('  Samsung   Galaxy   S24  '), 'Samsung Galaxy S24');
    assert.equal(cleanText('   '), null);
    assert.equal(cleanText(null), null);
  });

  it('extractAsinFromUrl extracts standard 10-char ASINs', () => {
    assert.equal(
      extractAsinFromUrl('https://www.amazon.in/dp/B0CX58S72W/ref=sr_1_1'),
      'B0CX58S72W'
    );
    assert.equal(
      extractAsinFromUrl('https://www.amazon.in/Samsung-Galaxy-Storage-Graphite-SM-S921BZKDINS/dp/B0CS571XMS'),
      'B0CS571XMS'
    );
    assert.equal(
      extractAsinFromUrl('https://www.amazon.in/gp/product/B09G9FPHP6'),
      'B09G9FPHP6'
    );
    assert.equal(extractAsinFromUrl('https://www.amazon.in/'), null);
  });

  it('normalizePrice handles commas, currency symbols and decimal amounts', () => {
    assert.deepEqual(normalizePrice('₹ 54,999.00'), { amount: 54999, currency: 'INR' });
    assert.deepEqual(normalizePrice('₹18,499'), { amount: 18499, currency: 'INR' });
    assert.deepEqual(normalizePrice('Rs. 1,29,900.50'), { amount: 129900.5, currency: 'INR' });
    assert.deepEqual(normalizePrice('Currently unavailable'), { amount: null, currency: null });
    assert.deepEqual(normalizePrice(''), { amount: null, currency: null });
  });

  it('normalizeRating parses star ratings accurately', () => {
    assert.equal(normalizeRating('4.2 out of 5 stars'), 4.2);
    assert.equal(normalizeRating('4.5'), 4.5);
    assert.equal(normalizeRating('5.0 out of 5 stars'), 5.0);
    assert.equal(normalizeRating('No ratings yet'), null);
  });

  it('normalizeReviewCount removes commas and handles parentheses', () => {
    assert.equal(normalizeReviewCount('1,420 ratings'), 1420);
    assert.equal(normalizeReviewCount('(24,519)'), 24519);
    assert.equal(normalizeReviewCount(''), null);
  });

  it('normalizeRam converts GB, TB and MB to GB numbers', () => {
    assert.equal(normalizeRam('8 GB'), 8);
    assert.equal(normalizeRam('12GB RAM'), 12);
    assert.equal(normalizeRam('16'), 16);
    assert.equal(normalizeRam('1 TB'), 1024);
    assert.equal(normalizeRam('Not mentioned'), null);
  });

  it('normalizeStorage converts GB and TB to GB numbers', () => {
    assert.equal(normalizeStorage('128 GB'), 128);
    assert.equal(normalizeStorage('256GB Storage'), 256);
    assert.equal(normalizeStorage('512 GB'), 512);
    assert.equal(normalizeStorage('1 TB'), 1024);
    assert.equal(normalizeStorage(null), null);
  });

  it('normalizeDisplaySize parses inches and converts cm to inches', () => {
    assert.equal(normalizeDisplaySize('6.67 inches'), 6.67);
    assert.equal(normalizeDisplaySize('6.7" AMOLED'), 6.7);
    assert.equal(normalizeDisplaySize('16.94 cm'), 6.67);
    assert.equal(normalizeDisplaySize('unknown'), null);
  });

  it('normalizeBattery parses integer mAh', () => {
    assert.equal(normalizeBattery('5000 mAh'), 5000);
    assert.equal(normalizeBattery('5,000 Milliamp Hours'), 5000);
    assert.equal(normalizeBattery('6000mAh Lithium Ion'), 6000);
    assert.equal(normalizeBattery('Battery not specified'), null);
  });

  it('normalize5G accurately identifies 5G vs 4G LTE indicators', () => {
    assert.equal(normalize5G(['Samsung Galaxy M34 5G']), true);
    assert.equal(normalize5G(['Redmi 13C (4G only)']), false);
    assert.equal(normalize5G(['Cellular 4G LTE']), false);
    assert.equal(normalize5G(['Basic Feature Phone']), null);
  });

  it('normalizeOperatingSystem cleans and formats OS tags', () => {
    assert.equal(normalizeOperatingSystem('Android 14.0'), 'Android 14.0');
    assert.equal(normalizeOperatingSystem('iOS 17'), 'iOS 17');
    assert.equal(normalizeOperatingSystem('OxygenOS based on Android 14'), 'Android 14');
    assert.equal(normalizeOperatingSystem(null), null);
  });

  it('normalizeAvailability identifies stock states without assuming availability', () => {
    assert.equal(normalizeAvailability('In stock.'), 'in_stock');
    assert.equal(normalizeAvailability('Usually dispatched in 2 to 3 days.'), 'in_stock');
    assert.equal(normalizeAvailability('Currently unavailable.'), 'out_of_stock');
    assert.equal(normalizeAvailability('Random text'), 'unknown');
  });

  it('extractConfigFromText parses paired configurations reliably', () => {
    assert.deepEqual(extractConfigFromText('8GB + 256GB'), { ram_gb: 8, storage_gb: 256 });
    assert.deepEqual(extractConfigFromText('8GB+256GB'), { ram_gb: 8, storage_gb: 256 });
    assert.deepEqual(extractConfigFromText('12GB/256GB'), { ram_gb: 12, storage_gb: 256 });
    assert.deepEqual(extractConfigFromText('16GB-512GB'), { ram_gb: 16, storage_gb: 512 });
    assert.deepEqual(extractConfigFromText('8 GB RAM, 256 GB storage'), { ram_gb: 8, storage_gb: 256 });
    assert.deepEqual(extractConfigFromText('REDMI Turbo 5 (8GB + 256GB) Asphalt Black'), { ram_gb: 8, storage_gb: 256 });
    assert.deepEqual(extractConfigFromText('Apple iPhone 15 (128 GB) - Blue'), { ram_gb: null, storage_gb: 128 });
    assert.deepEqual(extractConfigFromText('Just a phone title'), { ram_gb: null, storage_gb: null });
  });

  it('normalizeDisplaySize handles parenthetical inches, explicit inch, and cm', () => {
    assert.equal(normalizeDisplaySize('17.47 cm (6.88")'), 6.88);
    assert.equal(normalizeDisplaySize('16.74cm (6.59")'), 6.59);
    assert.equal(normalizeDisplaySize('16.75cm(6.59)'), 6.59);
    assert.equal(normalizeDisplaySize('17.27 cm (6.8 inch)'), 6.8);
    assert.equal(normalizeDisplaySize('6.67 inches'), 6.67);
    assert.equal(normalizeDisplaySize('6.8" FHD+'), 6.8);
    assert.equal(normalizeDisplaySize('15.54 cm'), 6.12);
  });

  it('extractDisplayFromText extracts display size from title and bullet snippets', () => {
    assert.equal(extractDisplayFromText('Compact 16.75cm(6.59) 120Hz AMOLED Screen'), 6.59);
    assert.equal(extractDisplayFromText('16.74cm(6.59") 120Hz AMOLED Display'), 6.59);
    assert.equal(extractDisplayFromText('6.8" Quad HD+ Dynamic AMOLED 2X Display'), 6.8);
    assert.equal(extractDisplayFromText('Generic non-display text'), null);
  });

  it('extractBatteryFromText extracts battery mAh from text', () => {
    assert.equal(extractBatteryFromText('Mega 7540mAh Battery'), 7540);
    assert.equal(extractBatteryFromText('Massive 7540 mAh Battery'), 7540);
    assert.equal(extractBatteryFromText('5000mAh'), 5000);
    assert.equal(extractBatteryFromText('No battery mentioned'), null);
  });

  it('extractModelFromTitle extracts model name given a verified brand', () => {
    assert.equal(
      extractModelFromTitle('Samsung Galaxy S25 Ultra 5G AI Smartphone (Titanium Black, 12GB RAM, 256GB Storage)', 'Samsung'),
      'Galaxy S25 Ultra'
    );
    assert.equal(
      extractModelFromTitle('REDMI Turbo 5 (8GB + 256GB) Asphalt Black | Dimensity 8500 Ultra', 'Redmi'),
      'Turbo 5'
    );
    assert.equal(
      extractModelFromTitle('Apple iPhone 15 (128 GB) - Blue', 'Apple'),
      'iPhone 15'
    );
    assert.equal(
      extractModelFromTitle('OnePlus 12R (Cool Blue, 16GB RAM, 256GB Storage)', 'OnePlus'),
      '12R'
    );
    // When brand is absent, should never guess
    assert.equal(extractModelFromTitle('Smartphone with camera', null), null);
  });

  it('extractProcessorFromText identifies mobile processors reliably', () => {
    assert.equal(extractProcessorFromText('Snapdragon 8 Elite Mobile Platform'), 'Snapdragon 8 Elite');
    assert.equal(extractProcessorFromText('MediaTek Dimensity 8500 Ultra (4nm)'), 'MediaTek Dimensity 8500 Ultra');
    assert.equal(extractProcessorFromText('Powered by 4G MediaTek Helio G85'), 'MediaTek Helio G85');
    assert.equal(extractProcessorFromText('A17 Pro chip with 6-core GPU'), 'A17 Pro');
    assert.equal(extractProcessorFromText('Google Tensor G4 processor'), 'Google Tensor G4');
    assert.equal(extractProcessorFromText('Unrelated features'), null);
  });
});
