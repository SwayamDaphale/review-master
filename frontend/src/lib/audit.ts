import { STORAGE_KEYS, useStoredState } from './storage';

export interface AuditEntry {
  id: string;
  at: string;
  actor: string;
  action: string;
  object: string;
  detail?: string;
}

const SEED_AUDIT_LOG: AuditEntry[] = [
  {
    id: 'aud-01',
    at: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
    actor: 'Lead Admin (you)',
    action: 'Verified Extension Export',
    object: 'Nothing Phone 4a (B0GRDH5D6Z)',
    detail: 'Validated 12GB RAM title fallback & casing dimension decoupling'
  },
  {
    id: 'aud-02',
    at: new Date(Date.now() - 1000 * 60 * 180).toISOString(),
    actor: 'Domain Lead',
    action: 'Reviewed Draft Model',
    object: 'Smartphones v1.0',
    detail: 'Verified thermal throttling & benchmark coverage rules'
  }
];

export function useAudit() {
  const [entries, setEntries] = useStoredState<AuditEntry[]>(STORAGE_KEYS.auditLog, SEED_AUDIT_LOG);

  const log = (action: string, object: string, detail?: string) => {
    const newEntry: AuditEntry = {
      id: `aud-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
      at: new Date().toISOString(),
      actor: 'Admin User',
      action,
      object,
      detail
    };
    setEntries((prev) => [newEntry, ...prev]);
  };

  const clear = () => setEntries([]);

  return { entries, log, clear };
}
