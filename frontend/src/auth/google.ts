import type { Session } from '../state/session';

/** Client ID from Google Cloud Console, set in frontend/.env.local as VITE_GOOGLE_CLIENT_ID. */
export const GOOGLE_CLIENT_ID: string = (import.meta.env.VITE_GOOGLE_CLIENT_ID ?? '').trim();

export function isGoogleConfigured(clientId: string = GOOGLE_CLIENT_ID): boolean {
  return clientId.length > 0;
}

interface GoogleIdTokenPayload {
  iss?: string;
  aud?: string;
  sub?: string;
  email?: string;
  email_verified?: boolean;
  name?: string;
  picture?: string;
  exp?: number;
}

/** Decodes (does NOT verify) the payload of a JWT. Verification must happen on the server. */
export function decodeJwtPayload(token: string): GoogleIdTokenPayload {
  const parts = token.split('.');
  const body = parts[1];
  if (parts.length !== 3 || !body) throw new Error('The sign-in response was not a valid token.');
  const b64 = body.replace(/-/g, '+').replace(/_/g, '/');
  const padded = b64 + '='.repeat((4 - (b64.length % 4)) % 4);
  const bytes = Uint8Array.from(atob(padded), (c) => c.charCodeAt(0));
  const json = new TextDecoder().decode(bytes);
  return JSON.parse(json) as GoogleIdTokenPayload;
}

/**
 * Turns a Google ID token into a local session after basic sanity checks.
 * IMPORTANT: this is not authentication. Until the backend verifies the token signature
 * (POST /api/v1/auth/google), anyone can forge a browser session. Fine for a demo, not for real data.
 */
export function sessionFromCredential(
  credential: string,
  clientId: string = GOOGLE_CLIENT_ID,
  now: number = Date.now(),
): Session {
  const p = decodeJwtPayload(credential);
  if (p.iss !== 'accounts.google.com' && p.iss !== 'https://accounts.google.com') {
    throw new Error('The sign-in response did not come from Google.');
  }
  if (clientId && p.aud !== clientId) {
    throw new Error('The sign-in response was issued for a different app.');
  }
  if (typeof p.exp !== 'number' || p.exp * 1000 <= now) {
    throw new Error('The sign-in response has expired. Try again.');
  }
  if (!p.sub || !p.email) throw new Error('Google did not return an email address for this account.');
  if (p.email_verified === false) throw new Error('This Google account has an unverified email address.');
  return {
    provider: 'google',
    sub: p.sub,
    email: p.email,
    name: p.name ?? p.email,
    picture: p.picture,
    signedInAt: new Date(now).toISOString(),
  };
}

let scriptPromise: Promise<void> | null = null;

export function loadGoogleScript(): Promise<void> {
  if (typeof window === 'undefined') return Promise.reject(new Error('No browser'));
  if (window.google?.accounts?.id) return Promise.resolve();
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise<void>((resolve, reject) => {
    const el = document.createElement('script');
    el.src = 'https://accounts.google.com/gsi/client';
    el.async = true;
    el.defer = true;
    el.onload = () => resolve();
    el.onerror = () => {
      scriptPromise = null;
      reject(new Error('Google sign-in script could not be loaded.'));
    };
    document.head.appendChild(el);
  });
  return scriptPromise;
}
