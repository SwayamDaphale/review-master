import { useCallback } from 'react';
import { STORAGE_KEYS, useStoredState } from './storage';

export interface AuditEntry {
  id: string;
  at: string;
  actor: string;
  action: string;
  object: string;
  detail?: string;
}

const EMPTY: AuditEntry[] = [];
const MAX_ENTRIES = 500;

/** Admin actions are recorded here (browser only for now). The real audit log is append-only in PostgreSQL. */
export function useAudit() {
  const [entries, setEntries] = useStoredState<AuditEntry[]>(STORAGE_KEYS.audit, EMPTY);
  const log = useCallback(
    (action: string, object: string, detail?: string) =>
      setEntries((prev) =>
        [
          {
            id: `a-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
            at: new Date().toISOString(),
            actor: 'admin (dev password)',
            action,
            object,
            detail,
          },
          ...prev,
        ].slice(0, MAX_ENTRIES),
      ),
    [setEntries],
  );
  const clear = useCallback(() => setEntries(EMPTY), [setEntries]);
  return { entries, log, clear };
}
