/**
 * Pure JavaScript JSON Schema Draft 2020-12 validator tailored for smartphone-extraction-1.0.schema.json
 * Runs with 0 external npm dependencies for lightweight, zero-overhead testing and verification.
 */

export function validateSmartphoneRecord(record) {
  const errors = [];

  function err(path, message) {
    errors.push({ path, message });
  }

  if (typeof record !== 'object' || record === null) {
    return { valid: false, errors: [{ path: '', message: 'Record must be a non-null object' }] };
  }

  // Root required fields
  const rootRequired = ['schema_version', 'source', 'raw_extraction', 'normalized', 'validation'];
  for (const field of rootRequired) {
    if (!(field in record)) {
      err(field, `Missing required root property: ${field}`);
    }
  }

  if (record.schema_version !== '1.0') {
    err('schema_version', `Expected const "1.0", got "${record.schema_version}"`);
  }

  // Source object
  if (record.source && typeof record.source === 'object') {
    const src = record.source;
    if (src.marketplace !== 'amazon.in') {
      err('source.marketplace', `Expected const "amazon.in", got "${src.marketplace}"`);
    }
    if (typeof src.product_url !== 'string' || !src.product_url.startsWith('https://www.amazon.in/')) {
      err('source.product_url', `product_url must start with https://www.amazon.in/`);
    }
    if (typeof src.extracted_at !== 'string' || isNaN(Date.parse(src.extracted_at))) {
      err('source.extracted_at', `extracted_at must be an ISO date-time string`);
    }
    if (src.extraction_method !== 'browser_extension_user_initiated') {
      err('source.extraction_method', `Expected "browser_extension_user_initiated"`);
    }
    if (typeof src.extension_version !== 'string' || src.extension_version.length < 1) {
      err('source.extension_version', `extension_version must be a non-empty string`);
    }
    if (src.asin !== null && (typeof src.asin !== 'string' || !/^[A-Z0-9]{10}$/.test(src.asin))) {
      err('source.asin', `asin must be null or 10 alphanumeric characters`);
    }
  }

  // Raw extraction
  if (record.raw_extraction && typeof record.raw_extraction === 'object') {
    const raw = record.raw_extraction;
    const rawRequired = ['title', 'brand_text', 'model_text', 'variant_text', 'price_text', 'rating_text', 'review_count_text', 'specifications_text'];
    for (const f of rawRequired) {
      if (!(f in raw)) err(`raw_extraction.${f}`, `Missing required field: ${f}`);
    }
    if (!Array.isArray(raw.specifications_text)) {
      err('raw_extraction.specifications_text', 'specifications_text must be an array');
    } else {
      raw.specifications_text.forEach((item, idx) => {
        if (typeof item !== 'object' || item === null || typeof item.label !== 'string' || typeof item.value !== 'string') {
          err(`raw_extraction.specifications_text[${idx}]`, 'Must contain string label and value');
        }
      });
    }
  }

  // Normalized
  if (record.normalized && typeof record.normalized === 'object') {
    const norm = record.normalized;
    const normRequired = [
      'category', 'brand', 'model_name', 'model_number',
      'ram_gb', 'storage_gb', 'display_size_inches', 'battery_capacity_mah',
      'operating_system', 'supports_5g', 'price_amount', 'currency', 'rating', 'review_count'
    ];
    for (const f of normRequired) {
      if (!(f in norm)) err(`normalized.${f}`, `Missing required field: ${f}`);
    }

    if (norm.category !== 'smartphone') {
      err('normalized.category', `Expected "smartphone", got "${norm.category}"`);
    }

    if (norm.ram_gb !== null && (typeof norm.ram_gb !== 'number' || norm.ram_gb <= 0)) {
      err('normalized.ram_gb', 'ram_gb must be null or > 0');
    }
    if (norm.storage_gb !== null && (typeof norm.storage_gb !== 'number' || norm.storage_gb <= 0)) {
      err('normalized.storage_gb', 'storage_gb must be null or > 0');
    }
    if (norm.display_size_inches !== null && (typeof norm.display_size_inches !== 'number' || norm.display_size_inches <= 0)) {
      err('normalized.display_size_inches', 'display_size_inches must be null or > 0');
    }
    if (norm.battery_capacity_mah !== null && (!Number.isInteger(norm.battery_capacity_mah) || norm.battery_capacity_mah <= 0)) {
      err('normalized.battery_capacity_mah', 'battery_capacity_mah must be null or integer > 0');
    }
    if (norm.price_amount !== null && (typeof norm.price_amount !== 'number' || norm.price_amount < 0)) {
      err('normalized.price_amount', 'price_amount must be null or >= 0');
    }
    if (norm.currency !== null && norm.currency !== 'INR') {
      err('normalized.currency', 'currency must be "INR" or null');
    }
    if (norm.rating !== null && (typeof norm.rating !== 'number' || norm.rating < 0 || norm.rating > 5)) {
      err('normalized.rating', 'rating must be null or between 0 and 5');
    }
    if (norm.review_count !== null && (!Number.isInteger(norm.review_count) || norm.review_count < 0)) {
      err('normalized.review_count', 'review_count must be null or integer >= 0');
    }
    if ('availability' in norm && norm.availability !== null) {
      const allowed = ['in_stock', 'out_of_stock', 'unknown'];
      if (!allowed.includes(norm.availability)) {
        err('normalized.availability', `availability must be in ${allowed.join(', ')} or null`);
      }
    }
    if ('processor' in norm && norm.processor !== null && typeof norm.processor !== 'string') {
      err('normalized.processor', 'processor must be string or null');
    }
  }

  // Validation
  if (record.validation && typeof record.validation === 'object') {
    const val = record.validation;
    if (!['valid', 'needs_review', 'invalid'].includes(val.status)) {
      err('validation.status', 'status must be valid, needs_review, or invalid');
    }
    if (!['identified', 'probable', 'ambiguous', 'unmatched'].includes(val.identity_status)) {
      err('validation.identity_status', 'identity_status must be identified, probable, ambiguous, or unmatched');
    }
    if (!Array.isArray(val.warnings)) err('validation.warnings', 'warnings must be array');
    if (!Array.isArray(val.errors)) err('validation.errors', 'errors must be array');
  }

  return {
    valid: errors.length === 0,
    errors
  };
}
