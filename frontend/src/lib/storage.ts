import { useCallback, useSyncExternalStore } from 'react';

// Tiny localStorage-backed store. Used until the backend and database exist.
// Values are JSON. Reads are cached so useSyncExternalStore gets stable snapshots.

type Listener = () => void;

const listeners = new Map<string, Set<Listener>>();
const cache = new Map<string, { raw: string | null; value: unknown }>();
const memory = new Map<string, string>(); // fallback when localStorage is blocked

function rawGet(key: string): string | null {
  try {
    const v = window.localStorage.getItem(key);
    if (v !== null) return v;
  } catch {
    /* storage blocked */
  }
  return memory.get(key) ?? null;
}

export function readStored<T>(key: string, fallback: T): T {
  const raw = rawGet(key);
  const hit = cache.get(key);
  if (hit && hit.raw === raw) return hit.value as T;
  let value: unknown = fallback;
  if (raw !== null) {
    try {
      value = JSON.parse(raw);
    } catch {
      value = fallback;
    }
  }
  cache.set(key, { raw, value });
  return value as T;
}

function emit(key: string) {
  listeners.get(key)?.forEach((l) => l());
}

export function writeStored<T>(key: string, value: T): void {
  const raw = JSON.stringify(value);
  try {
    window.localStorage.setItem(key, raw);
    memory.delete(key);
  } catch {
    memory.set(key, raw);
  }
  cache.set(key, { raw, value });
  emit(key);
}

export function removeStored(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
  memory.delete(key);
  cache.delete(key);
  emit(key);
}

function subscribe(key: string, listener: Listener): () => void {
  let set = listeners.get(key);
  if (!set) {
    set = new Set();
    listeners.set(key, set);
  }
  set.add(listener);
  return () => {
    set?.delete(listener);
  };
}

if (typeof window !== 'undefined') {
  window.addEventListener('storage', (e) => {
    if (e.key) {
      cache.delete(e.key);
      emit(e.key);
    } else {
      cache.clear();
      listeners.forEach((set) => set.forEach((l) => l()));
    }
  });
}

export function useStoredState<T>(
  key: string,
  initial: T,
): [T, (next: T | ((prev: T) => T)) => void] {
  const value = useSyncExternalStore(
    (l) => subscribe(key, l),
    () => readStored<T>(key, initial),
    () => initial,
  );
  const set = useCallback(
    (next: T | ((prev: T) => T)) => {
      const prev = readStored<T>(key, initial);
      const resolved = typeof next === 'function' ? (next as (p: T) => T)(prev) : next;
      writeStored(key, resolved);
    },
    [key, initial],
  );
  return [value, set];
}

export const STORAGE_KEYS = {
  theme: 'rm.theme',
  session: 'rm.session',
  adminSession: 'rm.admin',
  saved: 'rm.saved',
  alerts: 'rm.alerts',
  settings: 'rm.siteSettings',
  audit: 'rm.audit',
  adminModels: 'rm.admin.models',
  adminMappings: 'rm.admin.mappings',
  adminModeration: 'rm.admin.moderation',
  adminUsers: 'rm.admin.users',
} as const;

/** Removes every key this app created in the browser. Used by "Clear local data". */
export function clearAllAppStorage(): void {
  const keys = new Set<string>(Object.values(STORAGE_KEYS) as string[]);
  try {
    for (let i = 0; i < window.localStorage.length; i += 1) {
      const k = window.localStorage.key(i);
      if (k && k.startsWith('rm.')) keys.add(k);
    }
  } catch {
    /* storage blocked */
  }
  keys.forEach((k) => removeStored(k));
}
