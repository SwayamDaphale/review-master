import type { ApiClient } from './client';
import { mockApi } from './mockApi';

/**
 * The single place that decides which API implementation the app uses.
 * Replace `mockApi` with a client for /api/v1 (see architecture/api/openapi.yaml) when the backend is ready.
 */
export const api: ApiClient = mockApi;
export type { ApiClient } from './client';
