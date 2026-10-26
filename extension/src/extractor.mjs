/**
 * Extraction logic for Amazon India smartphone product pages.
 * Handles DOM parsing and structured extraction without side effects.
 */

import {
  cleanText,
  extractAsinFromUrl,
  normalizePrice,
  normalizeRating,
  normalizeReviewCount,
  normalizeRam,
  normalizeStorage,
  normalizeDisplaySize,
  normalizeBattery,
  normalize5G,
  normalizeOperatingSystem,
  normalizeAvailability,
  extractConfigFromText,
  extractDisplayFromText,
  extractBatteryFromText,
  extractModelFromTitle,
  extractProcessorFromText
} from './normalizers.mjs';

/**
 * Extract specifications from Amazon technical detail tables, overview grids, and detail bullets
 */
export function extractRawSpecifications(doc) {
  const specs = [];
  const seenLabels = new Set();

  function addSpec(rawLabel, rawValue) {
    let label = cleanText(rawLabel);
    const value = cleanText(rawValue);
    if (!label || !value) return;

    // Strip trailing colons, dashes, and extra whitespace/non-breaking spaces
    label = label.replace(/[:\-\s\u00a0\u200b]+$/, '').trim();
    if (label.length > 0 && value.length > 0 && !seenLabels.has(label.toLowerCase())) {
      seenLabels.add(label.toLowerCase());
      specs.push({ label, value });
    }
  }

  // 1. Amazon product overview table (often at the top near the title)
  const overviewRows = doc.querySelectorAll('#productOverview_feature_div tr, table.a-normal.a-spacing-micro tr');
  overviewRows.forEach(row => {
    const labelEl = row.querySelector('td:first-child span, th');
    const valEl = row.querySelector('td:last-child span, td.a-span9 span');
    if (labelEl && valEl) {
      addSpec(labelEl.textContent, valEl.textContent);
    }
  });

  // 1b. Amazon div-based product overview grid (#productOverview_feature_div .a-row, #poExpander .a-row)
  const overviewDivRows = doc.querySelectorAll('#productOverview_feature_div .a-row, #poExpander .a-row');
  overviewDivRows.forEach(row => {
    const labelEl = row.querySelector('.a-column:first-child span, div[class*="a-span3"] span, .po-label');
    const valEl = row.querySelector('.a-column:last-child span, div[class*="a-span9"] span, .po-value, .po-break-word');
    if (labelEl && valEl) {
      addSpec(labelEl.textContent, valEl.textContent);
    }
  });

  // 2. Technical details tables (expanded, collapsible, or standard)
  const techRows = doc.querySelectorAll([
    '#prodDetails table tr',
    '#technicalSpecifications_section_1 tr',
    '#technicalSpecifications_section_2 tr',
    '#productDetails_techSpec_section_1 tr',
    '#productDetails_techSpec_section_2 tr',
    '#productDetails_feature_div table tr',
    'table.prodDetTable tr',
    'table.a-keyvalue tr',
    '#detailBullets_feature_div li',
    '#detailBulletsWrapper_feature_div li',
    'ul.detail-bullet-list li',
    '#HLCXComparisonTable tr',
    'table.comparison_table tr',
    '#comparison_table tr'
  ].join(', '));

  techRows.forEach(row => {
    if (row.tagName && row.tagName.toLowerCase() === 'li') {
      const labelEl = row.querySelector('.a-text-bold');
      if (labelEl) {
        const fullText = row.textContent || '';
        const parts = fullText.split(/:\s*/);
        if (parts.length >= 2) {
          addSpec(parts[0], parts.slice(1).join(': '));
        }
      }
    } else {
      const th = row.querySelector('th');
      const td = row.querySelector('td');
      if (th && td) {
        addSpec(th.textContent, td.textContent);
      }
    }
  });

  // 3. "About this item" feature bullets (#feature-bullets, #featurebullets_feature_div)
  const featureBullets = doc.querySelectorAll('#feature-bullets ul li, #featurebullets_feature_div ul li');
  featureBullets.forEach(li => {
    const text = cleanText(li.textContent);
    if (!text) return;
    const colonMatch = text.match(/^([A-Za-z0-9\s\&\/]+)\s*[:\-]\s*(.+)$/);
    if (colonMatch) {
      const candidateLabel = colonMatch[1].trim();
      const candidateVal = colonMatch[2].trim();
      if (candidateLabel.length > 0 && candidateLabel.length <= 40 && candidateVal.length > 0) {
        addSpec(candidateLabel, candidateVal);
      }
    }
  });

  return specs;
}

/**
 * Find spec value matching any of the candidate label regexes
 */
function findSpecValue(specs, regexes) {
  for (const regex of regexes) {
    for (const spec of specs) {
      if (regex.test(spec.label)) {
        return spec.value;
      }
    }
  }
  return null;
}

/**
 * Extract raw fields from an Amazon India page document
 */
export function extractRawFields(doc, url) {
  const title = cleanText(
    doc.querySelector('#productTitle')?.textContent ||
    doc.querySelector('meta[property="og:title"]')?.getAttribute('content')
  );

  // Brand text
  let brandText = cleanText(
    doc.querySelector('#bylineInfo')?.textContent ||
    doc.querySelector('a#bylineInfo')?.textContent ||
    doc.querySelector('#brand')?.textContent
  );
  if (brandText) {
    // Strip "Visit the ... Store" or "Brand: ..."
    brandText = brandText.replace(/^(?:Visit the\s+|Brand:\s*)/i, '').replace(/\s+Store$/i, '').trim();
  }

  // Price text
  let priceText = cleanText(
    doc.querySelector('.a-price .a-offscreen')?.textContent ||
    doc.querySelector('.apexPriceToPay .a-offscreen')?.textContent ||
    doc.querySelector('.priceToPay .a-offscreen')?.textContent ||
    doc.querySelector('#corePrice_desktop .a-price .a-offscreen')?.textContent ||
    doc.querySelector('#corePriceDisplay_desktop_feature_div .a-price .a-offscreen')?.textContent ||
    doc.querySelector('#priceblock_ourprice')?.textContent ||
    doc.querySelector('#priceblock_dealprice')?.textContent
  );

  // Rating text
  const ratingText = cleanText(
    doc.querySelector('#acrPopover')?.getAttribute('title') ||
    doc.querySelector('.a-icon-star-small .a-icon-alt')?.textContent ||
    doc.querySelector('.a-icon-star .a-icon-alt')?.textContent
  );

  // Review count text
  const reviewCountText = cleanText(
    doc.querySelector('#acrCustomerReviewText')?.textContent ||
    doc.querySelector('[data-hook="total-review-count"]')?.textContent
  );

  // Availability text
  const availabilityText = cleanText(
    doc.querySelector('#availability span')?.textContent ||
    doc.querySelector('#availability')?.textContent
  );

  // Raw specifications table
  const specificationsText = extractRawSpecifications(doc);

  // Model and variant text from overview or title
  const modelText = findSpecValue(specificationsText, [
    /^model\s*name[:\s]*$/i,
    /^item\s*model\s*name[:\s]*$/i,
    /^model[:\s]*$/i,
    /^series[:\s]*$/i,
    /^device\s*name[:\s]*$/i,
    /^phone\s*model[:\s]*$/i
  ]);

  const variantText = cleanText(
    doc.querySelector('#variation_size_name .selection')?.textContent ||
    doc.querySelector('#variation_style_name .selection')?.textContent ||
    doc.querySelector('#variation_configuration_name .selection')?.textContent ||
    doc.querySelector('#inline-twister-expanded-dimension-text-size_name')?.textContent ||
    doc.querySelector('#inline-twister-expanded-dimension-text-style_name')?.textContent ||
    doc.querySelector('#variation_color_name .selection')?.textContent
  );

  return {
    title: title || null,
    brand_text: brandText || null,
    model_text: modelText || null,
    variant_text: variantText || null,
    price_text: priceText || null,
    rating_text: ratingText || null,
    review_count_text: reviewCountText || null,
    availability_text: availabilityText || null,
    specifications_text: specificationsText
  };
}

/**
 * Validate and build normalized record according to smartphone-extraction-1.0.schema.json
 */
export function buildExtractionRecord({
  url,
  doc,
  extensionVersion = '1.0.0',
  extractedAt = new Date().toISOString()
}) {
  const asin = extractAsinFromUrl(url);
  const raw = extractRawFields(doc, url);
  const specs = raw.specifications_text;

  // Normalizations
  const priceNorm = normalizePrice(raw.price_text);
  const ratingNorm = normalizeRating(raw.rating_text);
  const reviewCountNorm = normalizeReviewCount(raw.review_count_text);
  const availNorm = normalizeAvailability(raw.availability_text);

  // Specs lookup
  const rawBrand = raw.brand_text || findSpecValue(specs, [/^brand[:\s]*$/i, /^manufacturer[:\s]*$/i]);
  const titleText = raw.title || '';
  const variantText = raw.variant_text || '';

  let rawModelName = raw.model_text || findSpecValue(specs, [
    /^model\s*name[:\s]*$/i,
    /^item\s*model\s*name[:\s]*$/i,
    /^model[:\s]*$/i,
    /^series[:\s]*$/i,
    /^device\s*name[:\s]*$/i,
    /^phone\s*model[:\s]*$/i
  ]);

  // Unambiguous title fallback for model name if absent from specs table
  if (!rawModelName && rawBrand && titleText) {
    rawModelName = extractModelFromTitle(titleText, rawBrand);
  }

  const rawModelNumber = findSpecValue(specs, [
    /^item\s*model\s*number[:\s]*$/i,
    /^model\s*number[:\s]*$/i,
    /^part\s*number[:\s]*$/i,
    /^item\s*part\s*number[:\s]*$/i
  ]);

  const rawRam = findSpecValue(specs, [
    /^ram(?:\s+(?:memory|capacity|size))?(?:\s*\([^\)]+\))?[:\s]*$/i,
    /^ram\s*memory\s*(?:installed\s*)?size[:\s]*$/i,
    /^ram\s*capacity[:\s]*$/i,
    /^installed\s*ram(?:\s*size)?[:\s]*$/i,
    /^memory\s*ram\s*installed\s*size[:\s]*$/i,
    /^computer\s*memory\s*size[:\s]*$/i,
    /^system\s*ram[:\s]*$/i,
    /^installed\s*memory[:\s]*$/i,
    /^internal\s*ram[:\s]*$/i,
    /^memory\s*\(ram\)[:\s]*$/i,
    /^ram[:\s]*$/i
  ]);
  const rawStorage = findSpecValue(specs, [
    /^storage(?:\s+capacity)?(?:\s*\([^\)]+\))?[:\s]*$/i,
    /^memory\s*storage\s*capacity(?:\s*\([^\)]+\))?[:\s]*$/i,
    /^internal\s*storage(?:\s*\([^\)]+\))?[:\s]*$/i,
    /^rom(?:\s*\([^\)]+\))?[:\s]*$/i,
    /^hard\s*disk\s*size(?:\s*\([^\)]+\))?[:\s]*$/i,
    /^flash\s*memory\s*installed\s*size(?:\s*\([^\)]+\))?[:\s]*$/i,
    /^digital\s*storage\s*capacity(?:\s*\([^\)]+\))?[:\s]*$/i,
    /^built-in\s*storage(?:\s*\([^\)]+\))?[:\s]*$/i,
    /^internal\s*memory(?:\s*\([^\)]+\))?[:\s]*$/i
  ]);
  const rawDisplay = findSpecValue(specs, [
    /^standing\s*screen\s*display\s*size(?:\s*\([^\)]+\))?[:\s]*$/i,
    /^screen\s*size(?:\s*\([^\)]+\))?[:\s]*$/i,
    /^display\s*size(?:\s*\([^\)]+\))?[:\s]*$/i,
    /^screen\s*dimensions(?:\s*\([^\)]+\))?[:\s]*$/i,
    /^display(?:\s*\([^\)]+\))?[:\s]*$/i,
    /^screen(?:\s*\([^\)]+\))?[:\s]*$/i
  ]);
  const rawBattery = findSpecValue(specs, [
    /^battery(?:\s+capacity)?(?:\s*\([^\)]+\))?[:\s]*$/i,
    /^battery\s*power(?:\s*rating)?(?:\s*\([^\)]+\))?[:\s]*$/i,
    /^battery\s*size[:\s]*$/i,
    /^battery[:\s]*$/i
  ]);
  const rawOS = findSpecValue(specs, [
    /^operating\s*system[:\s]*$/i,
    /^os[:\s]*$/i,
    /^software\s*platform[:\s]*$/i
  ]);

  // Processor lookup from specs table, title, or bullets
  let rawProcessor = findSpecValue(specs, [
    /^processor[:\s]*$/i,
    /^cpu\s*model[:\s]*$/i,
    /^processor\s*type[:\s]*$/i,
    /^chipset[:\s]*$/i,
    /^processor\s*brand[:\s]*$/i,
    /^processor\s*model[:\s]*$/i,
    /^processor\s*name[:\s]*$/i
  ]);
  if (rawProcessor) {
    rawProcessor = extractProcessorFromText(rawProcessor) || cleanText(rawProcessor);
  }
  if (!rawProcessor && titleText) {
    rawProcessor = extractProcessorFromText(titleText);
  }
  if (!rawProcessor) {
    for (const spec of specs) {
      if (/processor|cpu|chip/i.test(spec.label) || /processor|chipset/i.test(spec.value)) {
        const val = extractProcessorFromText(spec.value);
        if (val) {
          rawProcessor = val;
          break;
        }
      }
    }
  }
  const processor = cleanText(rawProcessor) || null;
  if (processor && !specs.some(s => /^processor$/i.test(s.label))) {
    specs.push({ label: 'Processor', value: processor });
  }

  // Initial normalization from specs
  let ram_gb = normalizeRam(rawRam);
  let storage_gb = normalizeStorage(rawStorage);

  const warnings = [];
  const errors = [];

  // If a specification-table RAM value was provided but rejected by normalizeRam
  // (e.g. implausible "0.1 GB", "256 GB"), preserve raw row and emit an explicit warning.
  if (rawRam && ram_gb === null) {
    warnings.push(`Implausible or mislabeled RAM value in specs table ("${rawRam}"); rejected as valid RAM.`);
  }

  const variantConfig = extractConfigFromText(variantText);
  const titleConfig = extractConfigFromText(titleText);

  // If the page exposes a selected variant (e.g. Size: "8GB+256GB" or "8GB RAM, 128GB Storage"),
  // prefer it for the currently selected variant!
  if (variantConfig.ram_gb !== null && variantConfig.storage_gb !== null) {
    // Both RAM and storage specified in selected variant
    if (ram_gb !== null && ram_gb !== variantConfig.ram_gb) {
      warnings.push(`Selected variant RAM (${variantConfig.ram_gb} GB) takes precedence over table RAM (${ram_gb} GB).`);
    }
    if (storage_gb !== null && storage_gb !== variantConfig.storage_gb) {
      warnings.push(`Selected variant storage (${variantConfig.storage_gb} GB) takes precedence over table storage (${storage_gb} GB).`);
    }
    ram_gb = variantConfig.ram_gb;
    storage_gb = variantConfig.storage_gb;
  } else {
    // Check if variant text provides RAM or storage individually
    if (ram_gb === null && variantConfig.ram_gb !== null) {
      ram_gb = variantConfig.ram_gb;
    }
    if (storage_gb === null && variantConfig.storage_gb !== null) {
      storage_gb = variantConfig.storage_gb;
    }

    // A title-derived RAM value may be used only when deterministic parsing identifies
    // a valid configuration and there is no unresolved conflict about the selected variant.
    const hasVariantConflict = (variantConfig.storage_gb !== null && titleConfig.storage_gb !== null && variantConfig.storage_gb !== titleConfig.storage_gb) ||
                               (variantConfig.ram_gb !== null && titleConfig.ram_gb !== null && variantConfig.ram_gb !== titleConfig.ram_gb);

    if (hasVariantConflict) {
      warnings.push(`Selected variant dimension (${variantText}) conflicts with title configuration (${titleText}); title config not applied.`);
    } else {
      // Fallback to title configuration if RAM or storage is still missing
      if (ram_gb === null && titleConfig.ram_gb !== null) {
        if (storage_gb === null) {
          ram_gb = titleConfig.ram_gb;
          storage_gb = titleConfig.storage_gb;
        } else if (titleConfig.storage_gb === null || titleConfig.storage_gb === storage_gb) {
          ram_gb = titleConfig.ram_gb;
        } else {
          warnings.push(`RAM found in title (${titleConfig.ram_gb} GB) accompanies ${titleConfig.storage_gb} GB storage, but specs table indicates ${storage_gb} GB.`);
          ram_gb = titleConfig.ram_gb;
        }
      } else if (ram_gb === null && titleText) {
        // Additional targeted fallback for explicit RAM mention in title: e.g. "8GB RAM"
        const titleRamMatch = titleText.match(/([0-9]+(?:\.[0-9]+)?)\s*GB\s*RAM/i);
        if (titleRamMatch) {
          const parsedTitleRam = normalizeRam(titleRamMatch[0]);
          if (parsedTitleRam !== null) {
            ram_gb = parsedTitleRam;
          }
        }
      }

      if (storage_gb === null && titleConfig.storage_gb !== null) {
        storage_gb = titleConfig.storage_gb;
      } else if (storage_gb === null && titleText) {
        const titleStorageMatch = titleText.match(/([0-9]+(?:\.[0-9]+)?)\s*(?:GB|TB)\s*(?:Storage|ROM|Internal)/i) ||
                                   titleText.match(/\(\s*([0-9]+(?:\.[0-9]+)?)\s*(?:GB|TB)/i) ||
                                   titleText.match(/\b(16|32|64|128|256|512)\s*(GB|TB)\b/i) ||
                                   titleText.match(/\b([1-2])\s*TB\b/i);
        if (titleStorageMatch) {
          storage_gb = normalizeStorage(titleStorageMatch[0]);
        }
      }
    }
  }

  // Display size resolution: table spec -> title -> feature bullets
  let display_size_inches = normalizeDisplaySize(rawDisplay);
  if (display_size_inches === null && titleText) {
    display_size_inches = extractDisplayFromText(titleText);
  }
  if (display_size_inches === null) {
    for (const spec of specs) {
      if (/display|screen/i.test(spec.label)) {
        const val = normalizeDisplaySize(spec.value) || extractDisplayFromText(spec.value);
        if (val !== null) {
          display_size_inches = val;
          break;
        }
      }
    }
  }

  // Battery capacity resolution: table spec -> title -> feature bullets
  let battery_capacity_mah = normalizeBattery(rawBattery);
  if (battery_capacity_mah === null && titleText) {
    battery_capacity_mah = extractBatteryFromText(titleText);
  }
  if (battery_capacity_mah === null) {
    for (const spec of specs) {
      if (/battery|power/i.test(spec.label)) {
        const val = normalizeBattery(spec.value) || extractBatteryFromText(spec.value);
        if (val !== null) {
          battery_capacity_mah = val;
          break;
        }
      }
    }
  }

  let operating_system = normalizeOperatingSystem(rawOS);
  if (!operating_system && (rawBrand === 'Apple' || /^iPhone\b/i.test(titleText || ''))) {
    operating_system = 'iOS';
  }
  const spec5GValues = specs
    .filter(s => /cellular|network|wireless|connectivity/i.test(s.label))
    .map(s => s.value);
  const supports_5g = normalize5G([titleText, rawModelName, ...spec5GValues]);

  // Required field checks
  if (!raw.title) {
    errors.push('Missing product title: page structure may not be recognized as a product.');
  }

  if (priceNorm.amount === null) {
    warnings.push('Price not available or unparseable. Price is left as null; not assumed zero.');
  }

  if (ram_gb === null) {
    warnings.push('RAM capacity not clearly identified in listing or specs table.');
  }

  if (storage_gb === null) {
    warnings.push('Storage capacity not clearly identified in listing or specs table.');
  }

  if (battery_capacity_mah === null) {
    warnings.push('Battery capacity not clearly identified.');
  }

  if (display_size_inches === null) {
    warnings.push('Display size not clearly identified.');
  }

  // Identity ambiguity checks
  let identity_status = 'identified';
  if (!rawBrand || (!rawModelName && !rawModelNumber)) {
    identity_status = 'ambiguous';
    warnings.push('Brand or model name/number is ambiguous or missing.');
  } else if (ram_gb === null || storage_gb === null) {
    identity_status = 'probable';
    warnings.push('Variant hardware configuration (RAM or storage) is uncertain; marked as probable match.');
  }

  let validation_status = 'valid';
  if (errors.length > 0) {
    validation_status = 'invalid';
  } else if (warnings.length > 0) {
    validation_status = 'needs_review';
  }

  const record = {
    schema_version: '1.0',
    record_id: null,
    source: {
      marketplace: 'amazon.in',
      product_url: url,
      extracted_at: extractedAt,
      extraction_method: 'browser_extension_user_initiated',
      extension_version: extensionVersion,
      page_title: cleanText(doc.title) || null,
      asin: asin
    },
    raw_extraction: {
      title: raw.title,
      brand_text: raw.brand_text,
      model_text: raw.model_text,
      variant_text: raw.variant_text,
      price_text: raw.price_text,
      rating_text: raw.rating_text,
      review_count_text: raw.review_count_text,
      availability_text: raw.availability_text,
      specifications_text: raw.specifications_text
    },
    normalized: {
      category: 'smartphone',
      brand: rawBrand ? cleanText(rawBrand) : null,
      model_name: rawModelName ? cleanText(rawModelName) : null,
      model_number: rawModelNumber ? cleanText(rawModelNumber) : null,
      ram_gb: ram_gb,
      storage_gb: storage_gb,
      display_size_inches: display_size_inches,
      battery_capacity_mah: battery_capacity_mah,
      operating_system: operating_system,
      processor: processor,
      supports_5g: supports_5g,
      price_amount: priceNorm.amount,
      currency: priceNorm.currency,
      rating: ratingNorm,
      review_count: reviewCountNorm,
      availability: availNorm
    },
    validation: {
      status: validation_status,
      identity_status: identity_status,
      warnings: warnings,
      errors: errors
    }
  };

  return record;
}
