import { describe, expect, it } from 'vitest';
import { decodeJwtPayload, isGoogleConfigured, sessionFromCredential } from './google';

function makeToken(payload: Record<string, unknown>): string {
  const enc = (o: unknown) => Buffer.from(JSON.stringify(o)).toString('base64url');
  return `${enc({ alg: 'RS256' })}.${enc(payload)}.signature`;
}

const NOW = Date.UTC(2026, 9, 21, 12, 0, 0);
const good = {
  iss: 'https://accounts.google.com',
  aud: 'client-1',
  sub: '1234567890',
  email: 'ananya@example.com',
  email_verified: true,
  name: 'Ananya Kulkarni',
  picture: 'https://example.com/a.png',
  exp: Math.floor(NOW / 1000) + 3600,
};

describe('google sign-in helpers', () => {
  it('decodes a token payload including non-ASCII names', () => {
    const p = decodeJwtPayload(makeToken({ ...good, name: 'अनन्या' }));
    expect(p.name).toBe('अनन्या');
  });

  it('builds a session from a valid token', () => {
    const s = sessionFromCredential(makeToken(good), 'client-1', NOW);
    expect(s).toMatchObject({ provider: 'google', sub: '1234567890', email: 'ananya@example.com', name: 'Ananya Kulkarni' });
  });

  it('rejects an expired token', () => {
    expect(() => sessionFromCredential(makeToken({ ...good, exp: Math.floor(NOW / 1000) - 5 }), 'client-1', NOW)).toThrow(/expired/i);
  });

  it('rejects a token issued for another app', () => {
    expect(() => sessionFromCredential(makeToken({ ...good, aud: 'other' }), 'client-1', NOW)).toThrow(/different app/i);
  });

  it('rejects a token that did not come from Google', () => {
    expect(() => sessionFromCredential(makeToken({ ...good, iss: 'https://evil.example' }), 'client-1', NOW)).toThrow(/Google/);
  });

  it('rejects an unverified email', () => {
    expect(() => sessionFromCredential(makeToken({ ...good, email_verified: false }), 'client-1', NOW)).toThrow(/unverified/i);
  });

  it('rejects something that is not a token', () => {
    expect(() => decodeJwtPayload('nonsense')).toThrow();
  });

  it('reports whether a client id is configured', () => {
    expect(isGoogleConfigured('')).toBe(false);
    expect(isGoogleConfigured('abc.apps.googleusercontent.com')).toBe(true);
  });
});
