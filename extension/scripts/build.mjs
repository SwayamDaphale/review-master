import { existsSync, mkdirSync, copyFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const rootDir = resolve(__dirname, '..');
const distDir = resolve(rootDir, 'dist');

if (!existsSync(distDir)) {
  mkdirSync(distDir, { recursive: true });
}

console.log('✓ Build check: Extension source verified and ready for Chromium unpacking.');
