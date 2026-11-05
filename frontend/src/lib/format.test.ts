import { describe, expect, it } from 'vitest';
import { displayScore, formatINR, formatPercent01, initials } from './format';

describe('formatINR', () => {
  it('uses Indian digit grouping', () => {
    expect(formatINR(94999)).toBe('₹94,999');
    expect(formatINR(184900)).toBe('₹1,84,900');
  });
  it('does not turn a missing price into zero', () => {
    expect(formatINR(null)).toBe('Not available');
    expect(formatINR(undefined)).toBe('Not available');
  });
});

describe('displayScore', () => {
  it('converts the API 0-100 scale to 0-10 for display', () => {
    expect(displayScore(86.34)).toBe('8.6');
    expect(displayScore(100)).toBe('10.0');
  });
  it('keeps a real zero distinct from a missing score', () => {
    expect(displayScore(0)).toBe('0.0');
    expect(displayScore(null)).toBeNull();
    expect(displayScore(undefined)).toBeNull();
  });
});

describe('formatPercent01 and initials', () => {
  it('rounds confidence to a whole percent', () => {
    expect(formatPercent01(0.623)).toBe('62%');
    expect(formatPercent01(null)).toBe('n/a');
  });
  it('builds initials', () => {
    expect(initials('Asha Verma')).toBe('AV');
    expect(initials('Madonna')).toBe('M');
    expect(initials('')).toBe('?');
  });
});
