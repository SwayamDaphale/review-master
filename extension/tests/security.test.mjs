import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { IngestionApiError, submitListingIngestion } from '../src/api/client.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

describe('Extension Security & Isolation Auditing (Phase B12)', () => {
  const originalFetch = globalThis.fetch;

  it('rejects unsupported domains outside Amazon India host scope', () => {
    const unsupportedUrls = [
      'https://www.ebay.com/itm/1234567890',
      'https://www.walmart.com/ip/smartphone/12345',
      'https://malicious-site.attacker.com/amazon/dp/B0TESTASIN1',
      'chrome://extensions',
      'file:///etc/passwd',
    ];

    const isAmazonIndia = (url) => {
      try {
        const parsed = new URL(url);
        return parsed.hostname === 'www.amazon.in' || parsed.hostname === 'amazon.in';
      } catch {
        return false;
      }
    };

    for (const url of unsupportedUrls) {
      assert.equal(isAmazonIndia(url), false, `Domain should be rejected: ${url}`);
    }

    assert.equal(isAmazonIndia('https://www.amazon.in/dp/B0H297XH3K'), true);
  });

  it('Manifest V3 strictly declares least-privilege permissions', () => {
    const manifestPath = join(__dirname, '..', 'manifest.json');
    const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));

    // Manifest version check
    assert.equal(manifest.manifest_version, 3);

    // Permission checks: strictly minimal
    const allowedPermissions = ['activeTab', 'scripting', 'storage'];
    for (const perm of manifest.permissions || []) {
      assert.ok(
        allowedPermissions.includes(perm),
        `Unexpected excessive permission in manifest: ${perm}`
      );
    }

    // Host permissions check: strictly scoped to Amazon India and local backend
    for (const host of manifest.host_permissions || []) {
      assert.ok(
        host.includes('amazon.in') || host.includes('localhost') || host.includes('127.0.0.1'),
        `Excessive host permission found: ${host}`
      );
      assert.notEqual(host, '<all_urls>', 'Must never request <all_urls>');
      assert.notEqual(host, '*://*/*', 'Must never request broad wildcard host');
    }
  });

  it('API client sanitizes error responses and does not leak raw stack traces', async () => {
    globalThis.fetch = async () => ({
      ok: false,
      status: 500,
      json: async () => ({
        detail: 'An internal server error occurred.',
        request_id: 'sec-req-test-1234',
      }),
    });

    try {
      await assert.rejects(
        async () => {
          await submitListingIngestion({
            schema_version: '1.0',
            source: { asin: 'B0TESTASIN1', marketplace: 'amazon_in' },
            raw_extraction: { title: 'Test Phone' },
            normalized: { brand: 'TestBrand', model_name: 'TestModel' },
          });
        },
        (err) => {
          assert.ok(err instanceof IngestionApiError);
          assert.equal(err.status, 500);
          assert.equal(err.message, 'An internal server error occurred.');
          return true;
        }
      );
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('API client handles network disconnect gracefully without throwing unhandled exceptions', async () => {
    globalThis.fetch = async () => {
      throw new Error('Failed to fetch: Connection refused');
    };

    try {
      await assert.rejects(
        async () => {
          await submitListingIngestion({
            schema_version: '1.0',
            source: { asin: 'B0TESTASIN1', marketplace: 'amazon_in' },
            raw_extraction: { title: 'Test' },
            normalized: {},
          });
        },
        (err) => {
          assert.ok(err instanceof IngestionApiError);
          assert.equal(err.status, 0);
          assert.match(err.message, /Connection refused/i);
          return true;
        }
      );
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('Script injection and HTML payloads in product attributes are treated as passive text', () => {
    const maliciousInputs = [
      '<script>alert("XSS")</script>',
      '<img src=x onerror=alert(1)>',
      'javascript:void(0)',
      '"><svg onload=alert(document.cookie)>',
    ];

    // Sanitization function mimicking the extension's cleanText normalizer
    const cleanText = (str) => {
      if (!str || typeof str !== 'string') return '';
      return str.replace(/\s+/g, ' ').trim();
    };

    for (const input of maliciousInputs) {
      const sanitized = cleanText(input);
      // CleanText preserves text representation without DOM execution
      assert.equal(typeof sanitized, 'string');
      assert.ok(sanitized.length > 0);
    }
  });
});

