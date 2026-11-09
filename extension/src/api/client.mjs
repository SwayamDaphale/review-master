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
  } catch (parseErr) {
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

