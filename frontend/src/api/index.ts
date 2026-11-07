import type { ApiClient } from './client';
import { httpClient, HttpClient } from './httpClient';
import { mockApi } from './mockApi';

/**
 * The single place that decides which API implementation the app uses.
 * Configured via VITE_API_CLIENT:
 * - 'real': Queries FastAPI backend (/api/v1) for catalog data.
 * - 'mock' (default): Uses deterministic demo fixtures.
 */
const clientMode = import.meta.env.VITE_API_CLIENT;
export const isRealApiMode = clientMode === 'real';

export const api: ApiClient = isRealApiMode ? httpClient : mockApi;

export { httpClient, HttpClient, mockApi };
export type { ApiClient } from './client';
