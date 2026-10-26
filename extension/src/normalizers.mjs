/**
 * Normalization utilities for Amazon India smartphone extraction
 * Conforming strictly to smartphone-extraction-1.0.schema.json
 */

/**
 * Clean and trim text
 */
export function cleanText(str) {
  if (typeof str !== 'string') return null;
  const cleaned = str.replace(/[\s\u00a0\u200b]+/g, ' ').trim();
  return cleaned.length > 0 ? cleaned : null;
}

/**
 * Extract ASIN from URL
 * Amazon ASIN format: 10 alphanumeric characters (often /dp/B0XXXXXXXX or /gp/product/B0XXXXXXXX)
 */
export function extractAsinFromUrl(url) {
  if (!url || typeof url !== 'string') return null;
  const match = url.match(/(?:\/dp\/|\/gp\/product\/|\/ASIN\/)([A-Z0-9]{10})/i);
  return match ? match[1].toUpperCase() : null;
}

/**
 * Normalize price in INR from raw price string
 * Example: "₹ 54,999.00", "54,999", "Rs. 18,499" -> 54999
 */
export function normalizePrice(priceText) {
  if (!priceText || typeof priceText !== 'string') return { amount: null, currency: null };
  const cleaned = priceText.replace(/,/g, '').trim();
  const match = cleaned.match(/(?:₹|Rs\.?|INR)?\s*([0-9]+(?:\.[0-9]+)?)/i);
  if (!match) return { amount: null, currency: null };
  const amount = parseFloat(match[1]);
  if (isNaN(amount) || amount < 0) return { amount: null, currency: null };
  return {
    amount,
    currency: 'INR'
  };
}

/**
 * Normalize rating (e.g. "4.2 out of 5 stars", "4.2") -> 4.2
 */
export function normalizeRating(ratingText) {
  if (!ratingText || typeof ratingText !== 'string') return null;
  const match = ratingText.match(/([0-9](?:\.[0-9]+)?)\s*(?:out of 5|\/5|\s*stars)?/i);
  if (!match) return null;
  const val = parseFloat(match[1]);
  if (isNaN(val) || val < 0 || val > 5) return null;
  return val;
}

/**
 * Normalize review count (e.g. "1,420 ratings", "(1420)") -> 1420
 */
export function normalizeReviewCount(reviewCountText) {
  if (!reviewCountText || typeof reviewCountText !== 'string') return null;
  const digitsOnly = reviewCountText.replace(/,/g, '');
  const match = digitsOnly.match(/([0-9]+)/);
  if (!match) return null;
  const val = parseInt(match[1], 10);
  return !isNaN(val) && val >= 0 ? val : null;
}

/**
 * Normalize RAM in GB
 * e.g. "8 GB", "8GB", "12 GB RAM", "128MB" -> 8, 12, etc. (exclusiveMinimum: 0)
 *
 * Supported units per schema: GB, MB, TB.
 * Documented smartphone plausibility range: 1 GB <= RAM <= 64 GB.
 * Values outside this range (e.g. "0.1 GB", "256 GB") are rejected as implausible.
 */
export function normalizeRam(ramText) {
  if (!ramText || typeof ramText !== 'string') return null;
  const cleaned = cleanText(ramText);
  if (!cleaned) return null;

  // 1. TB branch (convert to GB: 1 TB = 1024 GB, plausible smartphone range: 1-64 GB)
  const tbMatch = cleaned.match(/([0-9]+(?:\.[0-9]+)?)\s*TB/i);
  if (tbMatch) {
    const val = parseFloat(tbMatch[1]) * 1024;
    return val >= 1 && val <= 64 ? val : null;
  }

  // 2. GB branch (plausible smartphone range: 1-64 GB)
  const gbMatch = cleaned.match(/([0-9]+(?:\.[0-9]+)?)\s*GB/i);
  if (gbMatch) {
    const val = parseFloat(gbMatch[1]);
    return val >= 1 && val <= 64 ? val : null;
  }

  // 3. MB branch (convert to GB: e.g. 1024 MB = 1 GB; plausible range: 1-64 GB)
  const mbMatch = cleaned.match(/([0-9]+(?:\.[0-9]+)?)\s*MB/i);
  if (mbMatch) {
    const val = parseFloat((parseFloat(mbMatch[1]) / 1024).toFixed(3));
    return val >= 1 && val <= 64 ? val : null;
  }

  // 4. Bare number branch (plausible range: 1-64 GB)
  const numMatch = cleaned.match(/^([0-9]+(?:\.[0-9]+)?)$/);
  if (numMatch) {
    const val = parseFloat(numMatch[1]);
    return val >= 1 && val <= 64 ? val : null;
  }

  return null;
}

/**
 * Extract paired RAM and Storage from text strings like "8GB + 256GB", "12GB/256GB",
 * "12GB 256GB", "(8GB RAM, 128GB Storage)", "8 GB RAM, 256 GB storage"
 * Returns { ram_gb: number | null, storage_gb: number | null }
 */
export function extractConfigFromText(text) {
  if (!text || typeof text !== 'string') return { ram_gb: null, storage_gb: null };

  // 1. Explicit labels: e.g. "8GB RAM, 256GB Storage" or "8 GB RAM, 128 GB ROM"
  const ramLabeled = text.match(/([0-9]+(?:\.[0-9]+)?)\s*(?:GB|MB|TB)?\s*RAM/i);
  const storageLabeled = text.match(/([0-9]+(?:\.[0-9]+)?)\s*(?:GB|TB)\s*(?:Storage|ROM|Internal(?:\s*Storage)?)/i);
  let ram_gb = ramLabeled ? normalizeRam(ramLabeled[0]) : null;
  let storage_gb = storageLabeled ? normalizeStorage(storageLabeled[0]) : null;

  // 2a. Unambiguous paired pattern with punctuation: e.g. "8GB + 256GB", "8GB+256GB", "12GB/256GB", "12GB / 512GB", "12GB-256GB",
  // "8GB, 256GB", "(Black, 8GB, 256GB)", "(8GB, 256GB, Black)", "8 + 256 GB"
  const pairedMatch = text.match(/\b([0-9]+(?:\.[0-9]+)?)\s*(?:GB)?\s*[\+\/\-\,]\s*([0-9]+(?:\.[0-9]+)?)\s*(GB|TB)\b/i);
  if (pairedMatch) {
    const candidateRam = parseFloat(pairedMatch[1]);
    const isTb = (pairedMatch[3] || '').toUpperCase() === 'TB';
    const candidateStorage = isTb ? parseFloat(pairedMatch[2]) * 1024 : parseFloat(pairedMatch[2]);
    // Validate typical smartphone ranges: RAM 1-64 GB, Storage 16-2048 GB, RAM strictly less than Storage
    if (candidateRam >= 1 && candidateRam <= 64 && candidateStorage >= 16 && candidateStorage <= 2048 && candidateRam < candidateStorage) {
      if (ram_gb === null) ram_gb = candidateRam;
      if (storage_gb === null) storage_gb = candidateStorage;
    }
  }

  // 2b. Unambiguous paired pattern with whitespace: e.g. "12GB 256GB", "12 GB 256 GB", "(12GB 256GB Black)"
  if (ram_gb === null || storage_gb === null) {
    const wsPairedMatch = text.match(/\b([0-9]+(?:\.[0-9]+)?)\s*GB\s+([0-9]+(?:\.[0-9]+)?)\s*(GB|TB)\b/i);
    if (wsPairedMatch) {
      const candidateRam = parseFloat(wsPairedMatch[1]);
      const isTb = (wsPairedMatch[3] || '').toUpperCase() === 'TB';
      const candidateStorage = isTb ? parseFloat(wsPairedMatch[2]) * 1024 : parseFloat(wsPairedMatch[2]);
      if (candidateRam >= 1 && candidateRam <= 64 && candidateStorage >= 16 && candidateStorage <= 2048 && candidateRam < candidateStorage) {
        if (ram_gb === null) ram_gb = candidateRam;
        if (storage_gb === null) storage_gb = candidateStorage;
      }
    }
  }

  // 3. Parenthetical pairs: e.g. "(8GB, 128GB)" or "(8GB/128GB)"
  const parenMatch = text.match(/\(\s*([0-9]+)\s*GB\s*[\,\+\/]\s*([0-9]+)\s*(GB|TB)\s*\)/i);
  if (parenMatch) {
    const cRam = parseFloat(parenMatch[1]);
    const isTb = (parenMatch[3] || '').toUpperCase() === 'TB';
    const cStorage = isTb ? parseFloat(parenMatch[2]) * 1024 : parseFloat(parenMatch[2]);
    if (cRam >= 1 && cRam <= 64 && cStorage >= 16 && cStorage <= 2048 && cRam < cStorage) {
      if (ram_gb === null) ram_gb = cRam;
      if (storage_gb === null) storage_gb = cStorage;
    }
  }

  // 4. Standalone explicit RAM candidate if still missing: e.g. "8GB RAM"
  if (ram_gb === null) {
    const explicitRam = text.match(/\b([0-9]+(?:\.[0-9]+)?)\s*GB\s*RAM\b/i);
    if (explicitRam) {
      ram_gb = normalizeRam(explicitRam[0]);
    }
  }

  // 5. Single parenthetical or standalone storage without RAM: e.g. "(128 GB)", "(256GB Storage)", "256 GB", "1 TB"
  if (storage_gb === null) {
    const singleStorageMatch = text.match(/\(\s*([0-9]+(?:\.[0-9]+)?)\s*(GB|TB)\s*\)/i) ||
      text.match(/\b(16|32|64|128|256|512)\s*(GB|TB)\b/i) ||
      text.match(/\b([1-2])\s*(TB)\b/i);
    if (singleStorageMatch) {
      const num = parseFloat(singleStorageMatch[1]);
      const unit = (singleStorageMatch[2] || '').toUpperCase();
      if (!isNaN(num)) {
        storage_gb = unit === 'TB' ? num * 1024 : num;
      }
    }
  }

  return { ram_gb, storage_gb };
}

/**
 * Normalize Storage in GB
 * e.g. "128 GB", "256GB", "1 TB", "512 GB Storage"
 */
export function normalizeStorage(storageText) {
  if (!storageText || typeof storageText !== 'string') return null;
  const tbMatch = storageText.match(/([0-9]+(?:\.[0-9]+)?)\s*TB/i);
  if (tbMatch) return parseFloat(tbMatch[1]) * 1024;
  const gbMatch = storageText.match(/([0-9]+(?:\.[0-9]+)?)\s*GB/i);
  if (gbMatch) return parseFloat(gbMatch[1]);
  const mbMatch = storageText.match(/([0-9]+(?:\.[0-9]+)?)\s*MB/i);
  if (mbMatch) return parseFloat((parseFloat(mbMatch[1]) / 1024).toFixed(3));
  return null;
}

/**
 * Normalize Display Size in inches
 * e.g. '6.67 inches', '6.67" FHD+', '16.94 cm (6.67 inch)', '17.47 cm (6.88")', '17.42 cm (6.9") Display', '16.75cm(6.59)',
 * '17.47 Centimetres', '17.47 Centimeters', '6.88 in', '6.9 in.'
 */
export function normalizeDisplaySize(displayText) {
  if (!displayText || typeof displayText !== 'string') return null;
  const cleaned = cleanText(displayText);
  if (!cleaned) return null;

  // 1. Parenthetical inches inside cm spec: e.g. 17.42 cm (6.9"), 17.47 cm (6.88"), 16.75cm(6.59), 17.27 cm (6.8 inch)
  const parenInchMatch = cleaned.match(/([0-9]+(?:\.[0-9]+)?)\s*(?:cm|centimetres|centimeters)\s*\(\s*([0-9]+(?:\.[0-9]+)?)\s*(?:inch|inches|\bin\.?(?=\s|$)|["”″″'’′]|\-inch)?\s*\)/i);
  if (parenInchMatch) {
    const inches = parseFloat(parenInchMatch[2]);
    if (inches >= 3.0 && inches <= 15.0) return inches;
  }

  // 2. Explicit inches: e.g. 6.8 Inches, 6.67", 6.8 inch, 6.9”, 6.88 in, 6.9 in.
  const inchMatch = cleaned.match(/([0-9]+(?:\.[0-9]+)?)\s*(?:inches|inch|\bin\.?(?=\s|$)|["”″″'’′]|\-inch)/i);
  if (inchMatch) {
    const val = parseFloat(inchMatch[1]);
    if (val >= 3.0 && val <= 15.0) return val;
  }

  // 3. Standalone cm or centimetres / centimeters: e.g. 15.54 cm -> 15.54 / 2.54 = 6.12, 17.47 Centimetres -> 6.88
  const cmMatch = cleaned.match(/([0-9]+(?:\.[0-9]+)?)\s*(?:cm|centimetres|centimeters)\b/i);
  if (cmMatch) {
    const inches = parseFloat((parseFloat(cmMatch[1]) / 2.54).toFixed(2));
    if (inches >= 3.0 && inches <= 15.0) return inches;
  }

  // 4. Bare number in typical smartphone display range (4.0 - 9.0)
  const bareMatch = cleaned.match(/^([4-9](?:\.[0-9]{1,2})?)$/);
  if (bareMatch) {
    return parseFloat(bareMatch[1]);
  }

  return null;
}

/**
 * Extract Display Size from descriptive text (e.g. title or "About this item" bullet)
 * e.g. 'Compact 16.75cm(6.59) 120Hz AMOLED Screen', '17.42 cm (6.9") Display', '6.8" Quad HD+ Dynamic AMOLED'
 */
export function extractDisplayFromText(text) {
  if (!text || typeof text !== 'string') return null;
  const cleaned = cleanText(text);
  if (!cleaned) return null;

  // Pattern: cm with parenthetical inches: 17.42 cm (6.9") or 16.74cm(6.59) or 17.47 cm (6.88 inch)
  const parenMatch = cleaned.match(/([0-9]+(?:\.[0-9]+)?)\s*(?:cm|centimetres|centimeters)\s*\(\s*([0-9]+(?:\.[0-9]+)?)\s*(?:inch|inches|\bin\.?(?=\s|$)|["”″″'’′]|\-inch)?\s*\)/i);
  if (parenMatch) {
    const inches = parseFloat(parenMatch[2]);
    if (inches >= 3.0 && inches <= 15.0) return inches;
  }

  // Pattern: inches with display terms: 6.8" AMOLED, 6.9" Display, 6.67 inch FHD+, 6.8 inches
  const inchMatch = cleaned.match(/([0-9]+(?:\.[0-9]+)?)\s*(?:inches|inch|\bin\.?(?=\s|$)|["”″″'’′]|\-inch)\s*(?:Super\s*Retina|AMOLED|OLED|LCD|FHD|QHD|HD\+|Screen|Display)?/i);
  if (inchMatch) {
    const inches = parseFloat(inchMatch[1]);
    if (inches >= 3.0 && inches <= 15.0) return inches;
  }

  return null;
}

/**
 * Extract Battery Capacity from descriptive text (e.g. title or bullet point)
 * e.g. 'Mega 7540mAh Battery', '5000 mAh'
 */
export function extractBatteryFromText(text) {
  if (!text || typeof text !== 'string') return null;
  const match = text.replace(/,/g, '').match(/([0-9]{4,5})\s*mAh/i);
  if (match) {
    const val = parseInt(match[1], 10);
    if (val >= 1000 && val <= 30000) return val;
  }
  return null;
}

/**
 * Extract Model Name unambiguously from product title when specs table omits it
 * e.g. "Apple iPhone 17 Pro Max 256 GB: 17.42 cm (6.9") Display..." -> "iPhone 17 Pro Max"
 * e.g. "Samsung Galaxy S25 Ultra 5G AI Smartphone (Titanium Black, 12GB RAM, 256GB Storage)" -> "Galaxy S25 Ultra"
 * e.g. "REDMI Turbo 5 (8GB + 256GB) Asphalt Black" -> "Turbo 5"
 * e.g. "Nothing Phone 4a (12GB 256GB Black)" -> "Phone 4a"
 * e.g. "ASUS ROG Phone 8 (16GB RAM, 512GB Storage)" -> "ROG Phone 8"
 * Requires verified brand to avoid guessing on ambiguous titles.
 */
export function extractModelFromTitle(title, brand) {
  if (!title || typeof title !== 'string' || !brand || typeof brand !== 'string') return null;
  const cleaned = cleanText(title);
  if (!cleaned) return null;

  // Check if first parenthetical is a Nothing Phone model designator like "(1)", "(2)", "(2a)"
  let leadSegment;
  const nothingModelParenMatch = cleaned.match(/^Nothing\s+Phone\s*\(([0-9]+[a-z]?)\)/i);
  if (nothingModelParenMatch) {
    leadSegment = `Nothing Phone (${nothingModelParenMatch[1]})`;
  } else {
    // Take the lead segment before the first opening parenthesis, bracket, comma, pipe, or colon
    leadSegment = cleaned.split(/[\(\[\,\|\:]/)[0].trim();
  }

  // Strip brand prefix if present
  const brandRegex = new RegExp(`^${brand}\\s+`, 'i');
  leadSegment = leadSegment.replace(brandRegex, '').trim();

  // Strip trailing dash + variant/color details (e.g. "Galaxy S25 Ultra - Titanium Silver" -> "Galaxy S25 Ultra")
  leadSegment = leadSegment.replace(/\s+-\s+.*$/, '').trim();

  // Strip trailing marketing phrase like "with Galaxy AI" or "with AI"
  leadSegment = leadSegment.replace(/\s+with\s+(?:Galaxy\s+)?AI\b.*$/i, '').trim();

  // Strip trailing storage if appended (e.g. "iPhone 17 Pro Max 256 GB" -> "iPhone 17 Pro Max")
  leadSegment = leadSegment.replace(/\b[0-9]+(?:\.[0-9]+)?\s*(?:GB|TB)\b.*$/i, '').trim();

  // Remove common trailing smartphone category/marketing terms at the end of the lead segment
  // (e.g. "Galaxy S25 Ultra 5G AI Smartphone" -> "Galaxy S25 Ultra")
  // Do NOT strip "Phone" when it is followed by a model designation (e.g. "Nothing Phone 4a", "ROG Phone 8")
  leadSegment = leadSegment
    .replace(/\b(?:5G\s+AI\s+Smartphone|AI\s+Smartphone|5G\s+Smartphone|Smartphone|5G\s+Mobile\s+Phone|Mobile\s+Phone|5G\s+Phone)\s*$/i, '')
    .trim();

  // Remove trailing generic "Phone" only if at the end of the string and not part of a brand/series
  // (e.g. "Galaxy M35 5G Phone" -> "Galaxy M35 5G", but keep "Phone 4a" or "ROG Phone 8")
  if (!/^Phone\b/i.test(leadSegment) && !/\bROG\s+Phone\b/i.test(leadSegment)) {
    leadSegment = leadSegment.replace(/\bPhone\s*$/i, '').trim();
  }

  // Remove trailing connectivity indicators at the end of the model string
  leadSegment = leadSegment.replace(/\b(?:5G|4G\s+LTE|4G)\s*$/i, '').trim();

  return leadSegment.length > 0 ? leadSegment : null;
}

/**
 * Extract Processor from text (title, table row, or bullet point)
 * Recognizes common mobile chipsets (Snapdragon, Dimensity, Helio, Apple A-series, Tensor, Exynos, Unisoc)
 */
export function extractProcessorFromText(text) {
  if (!text || typeof text !== 'string') return null;
  const cleaned = cleanText(text);
  if (!cleaned) return null;

  function stripSuffix(val) {
    if (!val) return null;
    return cleanText(val.replace(/\b(?:Mobile\s+Platform|Platform|Processor|Chipset|Chip)\b.*$/i, ''));
  }

  // 1. Snapdragon models: e.g. Snapdragon 8 Elite, Snapdragon 8 Gen 3, Snapdragon 7s Gen 2, Snapdragon 695
  const snapdragonMatch = cleaned.match(/(?:Qualcomm\s+)?(Snapdragon\s*[0-9A-Za-z\s\+\-]+(?:\bGen\s*[0-9]+)?)/i);
  if (snapdragonMatch) return stripSuffix(snapdragonMatch[1]);

  // 2. Dimensity models: e.g. MediaTek Dimensity 8500 Ultra, Dimensity 9300
  const dimensityMatch = cleaned.match(/(?:MediaTek\s+)?(Dimensity\s*[0-9]+(?:\s*(?:Ultra|Max|Plus|\+))?)/i);
  if (dimensityMatch) return stripSuffix(dimensityMatch[0]);

  // 3. Helio models: e.g. MediaTek Helio G85
  const helioMatch = cleaned.match(/(?:MediaTek\s+)?(Helio\s*[A-Za-z0-9]+)/i);
  if (helioMatch) return stripSuffix(helioMatch[0]);

  // 4. Apple Silicon: e.g. A19 Pro, A18 Pro, A17 Pro, A16 Bionic
  const appleMatch = cleaned.match(/\b(A[0-9]{1,2}\s*(?:Pro\s*Max|Pro|Bionic|Max)?)\b/i);
  if (appleMatch) return stripSuffix(appleMatch[1]);

  // 5. Google Tensor: e.g. Google Tensor G3, Tensor G4
  const tensorMatch = cleaned.match(/(?:Google\s+)?(Tensor\s*G[0-9]+)/i);
  if (tensorMatch) return stripSuffix(tensorMatch[0]);

  // 6. Samsung Exynos: e.g. Exynos 2400
  const exynosMatch = cleaned.match(/(?:Samsung\s+)?(Exynos\s*[0-9]+)/i);
  if (exynosMatch) return stripSuffix(exynosMatch[0]);

  // 7. Unisoc: e.g. Unisoc T612
  const unisocMatch = cleaned.match(/(?:Unisoc\s+)?([T|SC][0-9]{3,4}[A-Za-z0-9]*)/i);
  if (unisocMatch) return stripSuffix(unisocMatch[0]);

  return null;
}


/**
 * Normalize Battery capacity in mAh (integer)
 * e.g. "5000 mAh", "5,000 Milliamp Hours", "5000mAh Lithium Ion"
 */
export function normalizeBattery(batteryText) {
  if (!batteryText || typeof batteryText !== 'string') return null;
  const cleaned = batteryText.replace(/,/g, '');
  const match = cleaned.match(/([0-9]+)\s*(?:mAh|Milliamp\s*Hours|milliampere-hours)/i);
  if (match) {
    const val = parseInt(match[1], 10);
    return val > 0 ? val : null;
  }
  const bareMatch = cleaned.match(/([0-9]{4,5})/);
  if (bareMatch) {
    const val = parseInt(bareMatch[1], 10);
    return val >= 1000 && val <= 30000 ? val : null;
  }
  return null;
}

/**
 * Normalize 5G support
 */
export function normalize5G(textList) {
  const combined = (Array.isArray(textList) ? textList.join(' ') : String(textList || '')).toLowerCase();
  if (combined.includes('5g')) return true;
  if (combined.includes('4g lte') || combined.includes('4g only') || combined.includes('cellular 4g')) {
    if (!combined.includes('5g')) return false;
  }
  // All Apple iPhone models from iPhone 12 onwards are 5G devices
  if (/\biphone\s*(?:1[2-9]|[2-9][0-9])/i.test(combined)) {
    return true;
  }
  return null;
}

/**
 * Normalize Operating System
 * e.g. "Android 14", "iOS 17", "Funtouch OS 14 based on Android 14"
 */
export function normalizeOperatingSystem(osText) {
  if (!osText || typeof osText !== 'string') return null;
  const cleaned = cleanText(osText);
  if (!cleaned) return null;
  if (/iOS/i.test(cleaned)) {
    const match = cleaned.match(/iOS\s*([0-9]+(?:\.[0-9]+)?)?/i);
    return match ? (match[1] ? `iOS ${match[1]}` : 'iOS') : 'iOS';
  }
  if (/Android/i.test(cleaned)) {
    const match = cleaned.match(/Android\s*([0-9]+(?:\.[0-9]+)?)?/i);
    return match ? (match[1] ? `Android ${match[1]}` : 'Android') : cleaned;
  }
  return cleaned;
}

/**
 * Normalize Availability status
 * enum: "in_stock", "out_of_stock", "unknown", null
 */
export function normalizeAvailability(availText) {
  if (!availText || typeof availText !== 'string') return null;
  const lower = availText.toLowerCase();
  if (lower.includes('in stock') || lower.includes('available to ship') || lower.includes('usually dispatched in')) {
    return 'in_stock';
  }
  if (lower.includes('out of stock') || lower.includes('currently unavailable') || lower.includes('temporarily out of stock')) {
    return 'out_of_stock';
  }
  return 'unknown';
}
