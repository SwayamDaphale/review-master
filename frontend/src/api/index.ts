import type { ApiClient } from './client';
import { httpClient, HttpClient } from './httpClient';
import { mockApi } from './mockApi';

/**
 * The single place that decides which API implementation the app uses.
 * Configured via VITE_API_CLIENT:
 * - 'real' (default): Queries FastAPI backend (/api/v1).
 * - 'mock': Uses deterministic development-only demo fixtures.
 *
 * Strict Production Safety Rule:
 * Production builds strictly forbid demo mode.
 */
const isProduction = Boolean(import.meta.env.PROD);
const clientMode = import.meta.env.VITE_API_CLIENT;

if (isProduction && clientMode === 'mock') {
  throw new Error(
    'CRITICAL SECURITY CONFIGURATION ERROR: VITE_API_CLIENT="mock" is strictly forbidden in production builds. Production must connect to real Review Master APIs.',
  );
}

// In production builds, real API mode is mandatory.
// In development and test environments, real API is enabled via VITE_API_CLIENT=real.
export const isRealApiMode: boolean = isProduction || clientMode === 'real';
export const isDemoMode: boolean = !isRealApiMode;

export const api: ApiClient = isRealApiMode ? httpClient : mockApi;

export { httpClient, HttpClient, mockApi };
export type { ApiClient } from './client';
