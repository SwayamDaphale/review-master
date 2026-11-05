import { describe, expect, it } from 'vitest';
import { checkAdminPassword } from './adminAuth';

describe('checkAdminPassword', () => {
  it('accepts only the exact password', () => {
    expect(checkAdminPassword('secret', 'secret')).toBe(true);
    expect(checkAdminPassword('Secret', 'secret')).toBe(false);
    expect(checkAdminPassword('', 'secret')).toBe(false);
    expect(checkAdminPassword('', '')).toBe(false);
  });
});
