import { useState, useEffect } from 'react';

export const STORAGE_KEYS = {
  adminModels: 'rm_admin_models',
  adminMappings: 'rm_admin_mappings',
  adminModeration: 'rm_admin_moderation',
  auditLog: 'rm_audit_log',
  savedProducts: 'rm_saved_products',
  priceAlerts: 'rm_price_alerts',
  compareList: 'rm_compare_list'
};

export function useStoredState<T>(key: string, defaultValue: T): [T, (val: T | ((prev: T) => T)) => void] {
  const [state, setState] = useState<T>(() => {
    try {
      if (typeof window === 'undefined') return defaultValue;
      const raw = localStorage.getItem(key);
      if (!raw) return defaultValue;
      return JSON.parse(raw);
    } catch {
      return defaultValue;
    }
  });

  useEffect(() => {
    try {
      if (typeof window !== 'undefined') {
        localStorage.setItem(key, JSON.stringify(state));
      }
    } catch {
      // storage quota or private browsing safeguard
    }
  }, [key, state]);

  return [state, setState];
}
