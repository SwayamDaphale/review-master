/**
 * Review Master API Client for Chromium Browser Extension.
 * Connects extension popup directly to the FastAPI backend ingestion pipeline.
 */

export const DEFAULT_API_BASE_URL = 'http://localhost:8000';

export class IngestionApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'IngestionApiError';
    this.status = status;
    this.details = details;
  }
}

/**
 * Submit an extracted product listing record to Review Master backend.
 *
 * @param {Object} record - Frozen Smartphone V1 or Generalized V1 extraction record
 * @param {Object} [options]
 * @param {string} [options.baseUrl] - Backend API base URL
 * @param {string} [options.token] - JWT authentication access token
 * @param {string} [options.idempotencyKey] - Custom idempotency key
 * @returns {Promise<Object>} Accepted ingestion job response
 */
export async function submitListingIngestion(record, options = {}) {
  const baseUrl = options.baseUrl || DEFAULT_API_BASE_URL;
  const headers = {
    'Content-Type': 'application/json',
  };

  if (options.token) {
    headers['Authorization'] = `Bearer ${options.token}`;
  }

  if (options.idempotencyKey) {
    headers['Idempotency-Key'] = options.idempotencyKey;
  }

  let response;
  try {
    response = await fetch(`${baseUrl}/api/v1/listings/ingest`, {
      method: 'POST',
      headers,
      body: JSON.stringify(record),
    });
  } catch (netErr) {
    throw new IngestionApiError(
      `Network error connecting to Review Master backend: ${netErr.message || 'Connection refused'}`,
      0,
      netErr
    );
  }

  let bodyData;
  try {
    bodyData = await response.json();
  } catch {
    bodyData = null;
  }

  if (!response.ok) {
    const errorMsg = bodyData && (bodyData.detail || bodyData.message)
      ? (typeof bodyData.detail === 'string' ? bodyData.detail : JSON.stringify(bodyData.detail))
      : `HTTP ${response.status} ${response.statusText}`;
    throw new IngestionApiError(errorMsg, response.status, bodyData);
  }

  return bodyData;
}

/**
 * Retrieve status of a background ingestion job.
 *
 * @param {string} jobId - UUID of the ingestion job
 * @param {Object} [options]
 * @param {string} [options.baseUrl] - Backend API base URL
 * @param {string} [options.token] - JWT authentication access token
 * @returns {Promise<Object>} Job status view
 */
export async function getIngestionJobStatus(jobId, options = {}) {
  const baseUrl = options.baseUrl || DEFAULT_API_BASE_URL;
  const headers = {};

  if (options.token) {
    headers['Authorization'] = `Bearer ${options.token}`;
  }

  let response;
  try {
    response = await fetch(`${baseUrl}/api/v1/ingestion-jobs/${jobId}`, {
      method: 'GET',
      headers,
    });
  } catch (netErr) {
    throw new IngestionApiError(`Failed to fetch job status: ${netErr.message}`, 0, netErr);
  }

  let bodyData;
  try {
    bodyData = await response.json();
  } catch {
    bodyData = null;
  }

  if (!response.ok) {
    const errorMsg = bodyData && (bodyData.detail || bodyData.message)
      ? (typeof bodyData.detail === 'string' ? bodyData.detail : JSON.stringify(bodyData.detail))
      : `HTTP ${response.status} ${response.statusText}`;
    throw new IngestionApiError(errorMsg, response.status, bodyData);
  }

  return bodyData;
}

/**
 * Resolve canonical product and variant identity from extraction signals (Module 11).
 *
 * @param {Object} payload - Raw/normalized extraction or ASIN signals
 * @param {Object} [options]
 * @returns {Promise<Object>} Identity resolution response
 */
export async function resolveIdentity(payload, options = {}) {
  const baseUrl = options.baseUrl || DEFAULT_API_BASE_URL;
  const headers = { 'Content-Type': 'application/json' };
  if (options.token) headers['Authorization'] = `Bearer ${options.token}`;

  let response;
  try {
    response = await fetch(`${baseUrl}/api/v1/identity/resolve`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
  } catch (netErr) {
    throw new IngestionApiError(`Failed to resolve identity: ${netErr.message}`, 0, netErr);
  }

  let bodyData;
  try {
    bodyData = await response.json();
  } catch {
    bodyData = null;
  }

  if (!response.ok) {
    const errorMsg = bodyData && (bodyData.detail || bodyData.message)
      ? (typeof bodyData.detail === 'string' ? bodyData.detail : JSON.stringify(bodyData.detail))
      : `HTTP ${response.status} ${response.statusText}`;
    throw new IngestionApiError(errorMsg, response.status, bodyData);
  }

  return bodyData;
}

/**
 * Create a secure single-use import handoff token (Module 13).
 *
 * @param {Object} payload - { job_id, listing_id, context_data }
 * @param {Object} [options]
 * @returns {Promise<{ import_code: string, expires_at: string }>}
 */
export async function createHandoffToken(payload, options = {}) {
  const baseUrl = options.baseUrl || DEFAULT_API_BASE_URL;
  const headers = { 'Content-Type': 'application/json' };
  if (options.token) headers['Authorization'] = `Bearer ${options.token}`;

  let response;
  try {
    response = await fetch(`${baseUrl}/api/v1/import-tokens`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
  } catch (netErr) {
    throw new IngestionApiError(`Failed to create handoff token: ${netErr.message}`, 0, netErr);
  }

  let bodyData;
  try {
    bodyData = await response.json();
  } catch {
    bodyData = null;
  }

  if (!response.ok) {
    const errorMsg = bodyData && (bodyData.detail || bodyData.message)
      ? (typeof bodyData.detail === 'string' ? bodyData.detail : JSON.stringify(bodyData.detail))
      : `HTTP ${response.status} ${response.statusText}`;
    throw new IngestionApiError(errorMsg, response.status, bodyData);
  }

  return bodyData;
}

/**
 * List active comparison sessions for the user (Module 12).
 *
 * @param {Object} [options]
 * @returns {Promise<Array<Object>>}
 */
export async function listComparisonSessions(options = {}) {
  const baseUrl = options.baseUrl || DEFAULT_API_BASE_URL;
  const headers = {};
  if (options.token) headers['Authorization'] = `Bearer ${options.token}`;

  let response;
  try {
    response = await fetch(`${baseUrl}/api/v1/comparisons?status=active`, {
      method: 'GET',
      headers,
    });
  } catch (netErr) {
    throw new IngestionApiError(`Failed to fetch comparison sessions: ${netErr.message}`, 0, netErr);
  }

  let bodyData;
  try {
    bodyData = await response.json();
  } catch {
    bodyData = null;
  }

  if (!response.ok) {
    const errorMsg = bodyData && (bodyData.detail || bodyData.message)
      ? (typeof bodyData.detail === 'string' ? bodyData.detail : JSON.stringify(bodyData.detail))
      : `HTTP ${response.status} ${response.statusText}`;
    throw new IngestionApiError(errorMsg, response.status, bodyData);
  }

  return bodyData;
}

/**
 * Add a resolved variant to a comparison session (Module 12).
 *
 * @param {string} sessionId
 * @param {string} variantId
 * @param {Object} [options]
 * @returns {Promise<Object>}
 */
export async function addVariantToComparison(sessionId, variantId, options = {}) {
  const baseUrl = options.baseUrl || DEFAULT_API_BASE_URL;
  const headers = { 'Content-Type': 'application/json' };
  if (options.token) headers['Authorization'] = `Bearer ${options.token}`;

  let response;
  try {
    response = await fetch(`${baseUrl}/api/v1/comparisons/${sessionId}/items`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ variant_id: variantId }),
    });
  } catch (netErr) {
    throw new IngestionApiError(`Failed to add variant to comparison: ${netErr.message}`, 0, netErr);
  }

  let bodyData;
  try {
    bodyData = await response.json();
  } catch {
    bodyData = null;
  }

  if (!response.ok) {
    const errorMsg = bodyData && (bodyData.detail || bodyData.message)
      ? (typeof bodyData.detail === 'string' ? bodyData.detail : JSON.stringify(bodyData.detail))
      : `HTTP ${response.status} ${response.statusText}`;
    throw new IngestionApiError(errorMsg, response.status, bodyData);
  }

  return bodyData;
}

/**
 * Create a new comparison session from extension (Module 12).
 *
 * @param {string} title
 * @param {string} [categoryId]
 * @param {Object} [options]
 * @returns {Promise<Object>}
 */
export async function createComparisonSession(title, categoryId, options = {}) {
  const baseUrl = options.baseUrl || DEFAULT_API_BASE_URL;
  const headers = { 'Content-Type': 'application/json' };
  if (options.token) headers['Authorization'] = `Bearer ${options.token}`;

  let response;
  try {
    response = await fetch(`${baseUrl}/api/v1/comparisons`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ title, category_id: categoryId }),
    });
  } catch (netErr) {
    throw new IngestionApiError(`Failed to create comparison session: ${netErr.message}`, 0, netErr);
  }

  let bodyData;
  try {
    bodyData = await response.json();
  } catch {
    bodyData = null;
  }

  if (!response.ok) {
    const errorMsg = bodyData && (bodyData.detail || bodyData.message)
      ? (typeof bodyData.detail === 'string' ? bodyData.detail : JSON.stringify(bodyData.detail))
      : `HTTP ${response.status} ${response.statusText}`;
    throw new IngestionApiError(errorMsg, response.status, bodyData);
  }

  return bodyData;
}
