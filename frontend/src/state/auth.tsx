import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react';
import { STORAGE_KEYS, useStoredState } from '../lib/storage';
import { sessionFromCredential } from '../auth/google';
import { httpClient } from '../api/httpClient';
import type { Session } from './session';

const SESSION_DAYS = 7;

interface AuthContextValue {
  session: Session | null;
  signInWithGoogle: (credential: string) => { ok: true } | { ok: false; error: string };
  signInWithEmail: (email: string, password: string) => Promise<{ ok: true } | { ok: false; error: string }>;
  registerWithEmail: (
    email: string,
    password: string,
    displayName?: string,
  ) => Promise<{ ok: true } | { ok: false; error: string }>;
  signInDemo: () => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function isFresh(s: Session | null): s is Session {
  if (!s) return false;
  const age = Date.now() - Date.parse(s.signedInAt);
  return Number.isFinite(age) && age < SESSION_DAYS * 86_400_000;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [stored, setStored] = useStoredState<Session | null>(STORAGE_KEYS.session, null);
  const session = isFresh(stored) ? stored : null;

  const signInWithGoogle = useCallback(
    (credential: string) => {
      try {
        setStored(sessionFromCredential(credential));
        return { ok: true as const };
      } catch (e) {
        return { ok: false as const, error: e instanceof Error ? e.message : 'Sign-in failed.' };
      }
    },
    [setStored],
  );

  const signInWithEmail = useCallback(
    async (email: string, password: string) => {
      try {
        const tokens = await httpClient.login(email, password);
        setStored({
          provider: 'local',
          sub: tokens.user.id,
          email: tokens.user.email,
          name: tokens.user.display_name || tokens.user.email.split('@')[0],
          signedInAt: new Date().toISOString(),
          accessToken: tokens.access_token,
          roles: tokens.user.roles,
        });
        return { ok: true as const };
      } catch (e) {
        return { ok: false as const, error: e instanceof Error ? e.message : 'Authentication failed.' };
      }
    },
    [setStored],
  );

  const registerWithEmail = useCallback(
    async (email: string, password: string, displayName?: string) => {
      try {
        const tokens = await httpClient.register(email, password, displayName);
        setStored({
          provider: 'local',
          sub: tokens.user.id,
          email: tokens.user.email,
          name: tokens.user.display_name || tokens.user.email.split('@')[0],
          signedInAt: new Date().toISOString(),
          accessToken: tokens.access_token,
          roles: tokens.user.roles,
        });
        return { ok: true as const };
      } catch (e) {
        return { ok: false as const, error: e instanceof Error ? e.message : 'Registration failed.' };
      }
    },
    [setStored],
  );

  const signInDemo = useCallback(() => {
    setStored({
      provider: 'demo',
      sub: 'demo-user',
      email: 'demo@reviewmaster.local',
      name: 'Demo user',
      signedInAt: new Date().toISOString(),
      roles: ['consumer'],
    });
  }, [setStored]);

  const signOut = useCallback(() => {
    httpClient.logout().catch(() => {});
    window.google?.accounts?.id?.disableAutoSelect?.();
    setStored(null);
  }, [setStored]);

  const value = useMemo(
    () => ({
      session,
      signInWithGoogle,
      signInWithEmail,
      registerWithEmail,
      signInDemo,
      signOut,
    }),
    [session, signInWithGoogle, signInWithEmail, registerWithEmail, signInDemo, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
