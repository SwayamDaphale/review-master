import { readFileSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const manifestPath = resolve(__dirname, '../manifest.json');

if (!existsSync(manifestPath)) {
  console.error(`ERROR: manifest.json not found at ${manifestPath}`);
  process.exit(1);
}

const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));

// Check permissions against project requirements
const DISALLOWED_PERMISSIONS = [
  'cookies',
  'history',
  'webRequest',
  'webRequestBlocking',
  'tabs',
  'management',
  'geolocation',
  'debugger'
];

const disallowedFound = (manifest.permissions || []).filter(p => DISALLOWED_PERMISSIONS.includes(p));
if (disallowedFound.length > 0) {
  console.error(`PERMISSION GATE FAILURE: Disallowed permissions found: ${disallowedFound.join(', ')}`);
  process.exit(1);
}

const hostPermissions = manifest.host_permissions || [];
const ALLOWED_HOSTS = [
  'https://www.amazon.in/*',
  'https://amazon.in/*'
];

for (const host of hostPermissions) {
  if (host === '<all_urls>' || host.includes('*://*/*')) {
    console.error(`PERMISSION GATE FAILURE: Broad wildcard host permission detected: ${host}`);
    process.exit(1);
  }
  const isAllowed = ALLOWED_HOSTS.some(allowed => host === allowed || host.startsWith('https://www.amazon.in'));
  if (!isAllowed) {
    console.error(`PERMISSION GATE FAILURE: Unauthorized host permission: ${host}`);
    process.exit(1);
  }
}

if (manifest.manifest_version !== 3) {
  console.error(`PERMISSION GATE FAILURE: manifest_version must be 3, found: ${manifest.manifest_version}`);
  process.exit(1);
}

console.log('✓ Permission gate check passed: minimal permissions and host scope verified.');
