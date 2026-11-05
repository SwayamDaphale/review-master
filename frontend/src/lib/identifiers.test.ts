import { describe, expect, it } from 'vitest';
import { parseIdentifier } from './identifiers';

describe('parseIdentifier', () => {
  it('recognises a bare ASIN', () => {
    expect(parseIdentifier(' b0dskmv3zc ')).toMatchObject({ kind: 'asin', asin: 'B0DSKMV3ZC' });
  });
  it('reads the ASIN from an Amazon India product link', () => {
    const r = parseIdentifier('https://www.amazon.in/Samsung-Galaxy/dp/B0DSKMV3ZC/ref=sr_1_4?crid=3B29');
    expect(r).toMatchObject({ kind: 'url', asin: 'B0DSKMV3ZC', host: 'www.amazon.in' });
  });
  it('reads /gp/product/ links', () => {
    expect(parseIdentifier('https://www.amazon.in/gp/product/B0FQFJKBVY')).toMatchObject({ asin: 'B0FQFJKBVY' });
  });
  it('returns a url with no ASIN when none is present', () => {
    expect(parseIdentifier('https://www.amazon.in/s?k=phone')).toMatchObject({ kind: 'url', asin: null });
  });
  it('treats ordinary words as text', () => {
    expect(parseIdentifier('galaxy s25 ultra')).toEqual({ kind: 'text', value: 'galaxy s25 ultra' });
  });
});
