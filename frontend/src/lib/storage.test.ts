import { describe, expect, it, vi } from 'vitest';
import { readStored, removeStored, writeStored } from './storage';

describe('storage', () => {
  it('returns the fallback, and the same object each time, when nothing is stored', () => {
    const fallback = { a: 1 };
    expect(readStored('t.missing', fallback)).toBe(fallback);
    expect(readStored('t.missing', { a: 2 })).toBe(fallback);
  });

  it('round-trips JSON values', () => {
    writeStored('t.value', { list: [1, 2, 3] });
    expect(readStored('t.value', null)).toEqual({ list: [1, 2, 3] });
    removeStored('t.value');
    expect(readStored('t.value', 'gone')).toBe('gone');
  });

  it('falls back to memory when localStorage refuses writes', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    writeStored('t.blocked', 42);
    expect(readStored('t.blocked', 0)).toBe(42);
    spy.mockRestore();
    removeStored('t.blocked');
  });
});
