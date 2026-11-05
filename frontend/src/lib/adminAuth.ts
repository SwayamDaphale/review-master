import { useCallback } from 'react';
import { STORAGE_KEYS, useStoredState } from './storage';

/**
 * DEVELOPMENT-ONLY admin gate. The password is compiled into the browser bundle, so it is not
 * security. It exists so the admin screens can be built before the backend has real admin auth.
 */
export const ADMIN_PASSWORD: string = (import.meta.env.VITE_ADMIN_PASSWORD ?? '').trim() || 'admin123';

export function checkAdminPassword(input: string, expected: string = ADMIN_PASSWORD): boolean {
  return input.length > 0 && input === expected;
}

interface AdminSession {
  expiresAt: string;
}

const EIGHT_HOURS = 8 * 3_600_000;

export function useAdmin() {
  const [session, setSession] = useStoredState<AdminSession | null>(STORAGE_KEYS.adminSession, null);
  const isAdmin = session !== null && Date.parse(session.expiresAt) > Date.now();

  const login = useCallback(
    (password: string): boolean => {
      if (!checkAdminPassword(password)) return false;
      setSession({ expiresAt: new Date(Date.now() + EIGHT_HOURS).toISOString() });
      return true;
    },
    [setSession],
  );
  const logout = useCallback(() => setSession(null), [setSession]);
  return { isAdmin, login, logout };
}
