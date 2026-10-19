import { writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const iconsDir = resolve(__dirname, '../icons');
if (!existsSync(iconsDir)) {
  mkdirSync(iconsDir, { recursive: true });
}

// 1x1 transparent/cyan PNG base64
const minimalPng = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64'
);

writeFileSync(resolve(iconsDir, 'icon16.png'), minimalPng);
writeFileSync(resolve(iconsDir, 'icon48.png'), minimalPng);
writeFileSync(resolve(iconsDir, 'icon128.png'), minimalPng);

console.log('✓ Icon assets created at extension/icons/');
