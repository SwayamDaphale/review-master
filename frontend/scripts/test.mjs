import { spawnSync } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const testFile = resolve(__dirname, '../tests/trust.test.mjs');

const result = spawnSync('node', ['--test', testFile], { stdio: 'inherit' });
if (result.status !== 0) {
  process.exit(result.status || 1);
}
console.log('✓ All frontend unit tests passed.');
process.exit(0);
