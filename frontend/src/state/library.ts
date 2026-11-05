import { useCallback } from 'react';
import { STORAGE_KEYS, useStoredState } from '../lib/storage';
import { useAuth } from './auth';

export interface PriceAlert {
  id: string;
  variantId: string;
  target: number;
  createdAt: string;
}

const EMPTY_IDS: string[] = [];
const EMPTY_ALERTS: PriceAlert[] = [];

/** Saved products and price alerts, kept per signed-in user in this browser until the backend exists. */
export function useLibrary() {
  const { session } = useAuth();
  const owner = session?.sub ?? 'guest';
  const [saved, setSaved] = useStoredState<string[]>(`${STORAGE_KEYS.saved}.${owner}`, EMPTY_IDS);
  const [alerts, setAlerts] = useStoredState<PriceAlert[]>(`${STORAGE_KEYS.alerts}.${owner}`, EMPTY_ALERTS);

  const isSaved = useCallback((variantId: string) => saved.includes(variantId), [saved]);
  const toggleSaved = useCallback(
    (variantId: string) =>
      setSaved((prev) => (prev.includes(variantId) ? prev.filter((id) => id !== variantId) : [...prev, variantId])),
    [setSaved],
  );
  const addAlert = useCallback(
    (variantId: string, target: number) =>
      setAlerts((prev) => [
        ...prev.filter((a) => a.variantId !== variantId),
        { id: `alert-${Date.now()}`, variantId, target, createdAt: new Date().toISOString() },
      ]),
    [setAlerts],
  );
  const removeAlert = useCallback((id: string) => setAlerts((prev) => prev.filter((a) => a.id !== id)), [setAlerts]);

  return { saved, alerts, isSaved, toggleSaved, addAlert, removeAlert, signedIn: session !== null };
}
