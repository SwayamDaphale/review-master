import { useCallback, useMemo } from 'react';
import { STORAGE_KEYS, useStoredState } from '../lib/storage';

export interface SiteSettings {
  bannerEnabled: boolean;
  bannerText: string;
  maintenance: boolean;
  showSampleNotice: boolean;
  features: { compare: boolean; priceAlerts: boolean; importTool: boolean };
}

export const DEFAULT_SETTINGS: SiteSettings = {
  bannerEnabled: false,
  bannerText: '',
  maintenance: false,
  showSampleNotice: true,
  features: { compare: true, priceAlerts: true, importTool: true },
};

/** Settings are stored in this browser only until the backend exists. */
export function useSiteSettings(): [SiteSettings, (patch: Partial<SiteSettings>) => void, () => void] {
  const [stored, setStored] = useStoredState<Partial<SiteSettings>>(STORAGE_KEYS.settings, DEFAULT_SETTINGS);
  const settings = useMemo<SiteSettings>(
    () => ({ ...DEFAULT_SETTINGS, ...stored, features: { ...DEFAULT_SETTINGS.features, ...(stored.features ?? {}) } }),
    [stored],
  );
  const update = useCallback(
    (patch: Partial<SiteSettings>) => setStored((prev) => ({ ...prev, ...patch })),
    [setStored],
  );
  const reset = useCallback(() => setStored(DEFAULT_SETTINGS), [setStored]);
  return [settings, update, reset];
}
