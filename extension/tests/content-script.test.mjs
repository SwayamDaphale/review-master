import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

describe('Content Script & Popup Integrity', () => {
  const contentScriptPath = resolve(__dirname, '../src/content-script.js');
  const contentScriptCode = readFileSync(contentScriptPath, 'utf8');

  it('content-script.js is syntactically valid and parses cleanly', () => {
    assert.doesNotThrow(() => {
      new vm.Script(contentScriptCode, { filename: 'content-script.js' });
    });
  });

  it('content-script.js defines extractAmazonSmartphoneData and runs in a browser sandbox', () => {
    const sandbox = {
      window: {
        location: {
          hostname: 'www.amazon.in',
          href: 'https://www.amazon.in/dp/B0H297XH3K'
        }
      },
      document: {
        title: 'REDMI Turbo 5 (8GB + 256GB) : Amazon.in',
        querySelector: (sel) => {
          if (sel === '#productTitle') return { textContent: 'REDMI Turbo 5 (8GB + 256GB)' };
          return null;
        },
        querySelectorAll: () => []
      },
      console: console
    };

    vm.createContext(sandbox);
    vm.runInContext(contentScriptCode, sandbox);

    assert.equal(typeof sandbox.extractAmazonSmartphoneData, 'function');
    assert.equal(typeof sandbox.window.extractAmazonSmartphoneData, 'function');

    const result = sandbox.extractAmazonSmartphoneData();
    assert.ok(result, 'Expected extraction result');
    assert.equal(result.schema_version, '1.0');
    assert.equal(result.normalized.ram_gb, 8);
    assert.equal(result.normalized.storage_gb, 256);
  });

  it('popup.js is syntactically valid and parses cleanly', () => {
    const popupScriptPath = resolve(__dirname, '../popup/popup.js');
    const popupScriptCode = readFileSync(popupScriptPath, 'utf8');
    assert.doesNotThrow(() => {
      new vm.Script(popupScriptCode, { filename: 'popup.js' });
    });
  });
});
