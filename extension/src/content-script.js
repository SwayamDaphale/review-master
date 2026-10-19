/**
 * In-browser content script extraction runner.
 * Executed on demand via chrome.scripting.executeScript.
 * Uses vanilla DOM inspection without external libraries.
 */

function extractAmazonSmartphoneData() {
  try {
    // Check if this is an Amazon India page
    if (!window.location.hostname.endsWith('amazon.in')) {
      return {
        error: 'UNSUPPORTED_PAGE',
        message: 'This extension only operates on Amazon India (amazon.in) product pages.'
      };
    }

    // Safely expand collapsed product-specification sections if present
    // Only product detail controls are touched; purchase, cart, and variant controls are strictly avoided.
    try {
      const safeExpanderSelectors = [
        '#productOverview_feature_div .a-expander-collapsed-bottom a',
        '#productOverview_feature_div [data-action="a-expander-toggle"]',
        '#productDetails_seeMore_feature_div a',
        '#poExpander.a-expander-collapsed [data-action="a-expander-toggle"]',
        '#featurebullets_feature_div .a-expander-collapsed-bottom a'
      ];
      for (const sel of safeExpanderSelectors) {
        const el = document.querySelector(sel);
        if (el && typeof el.click === 'function') {
          const form = el.closest('form');
          if (!form || (!form.id.includes('buy') && !form.id.includes('cart'))) {
            el.click();
          }
        }
      }
    } catch (expErr) {
      // Safe to proceed if expander click throws
    }

    // Helper functions matching extractor logic
    function cleanText(str) {
      if (typeof str !== 'string') return null;
      const cleaned = str.replace(/[\s\u00a0\u200b]+/g, ' ').trim();
      return cleaned.length > 0 ? cleaned : null;
    }

    function extractAsinFromUrl(url) {
      if (!url) return null;
      const match = url.match(/(?:\/dp\/|\/gp\/product\/|\/ASIN\/)([A-Z0-9]{10})/i);
      return match ? match[1].toUpperCase() : null;
    }

    function normalizePrice(priceText) {
      if (!priceText) return { amount: null, currency: null };
      const cleaned = priceText.replace(/,/g, '').trim();
      const match = cleaned.match(/(?:₹|Rs\.?|INR)?\s*([0-9]+(?:\.[0-9]+)?)/i);
      if (!match) return { amount: null, currency: null };
      const amount = parseFloat(match[1]);
      return isNaN(amount) || amount < 0 ? { amount: null, currency: null } : { amount, currency: 'INR' };
    }

    function normalizeRating(ratingText) {
      if (!ratingText) return null;
      const match = ratingText.match(/([0-9](?:\.[0-9]+)?)\s*(?:out of 5|\/5|\s*stars)?/i);
      if (!match) return null;
      const val = parseFloat(match[1]);
      return isNaN(val) || val < 0 || val > 5 ? null : val;
    }

    function normalizeReviewCount(reviewCountText) {
      if (!reviewCountText) return null;
      const digitsOnly = reviewCountText.replace(/,/g, '');
      const match = digitsOnly.match(/([0-9]+)/);
      if (!match) return null;
      const val = parseInt(match[1], 10);
      return !isNaN(val) && val >= 0 ? val : null;
    }

    function normalizeRam(ramText) {
      if (!ramText || typeof ramText !== 'string') return null;
      const cleaned = cleanText(ramText);
      if (!cleaned) return null;
      const tbMatch = cleaned.match(/([0-9]+(?:\.[0-9]+)?)\s*TB/i);
      if (tbMatch) return parseFloat(tbMatch[1]) * 1024;
      const gbMatch = cleaned.match(/([0-9]+(?:\.[0-9]+)?)\s*GB/i);
      if (gbMatch) {
        const val = parseFloat(gbMatch[1]);
        return val >= 1 && val <= 64 ? val : null;
      }
      const mbMatch = cleaned.match(/([0-9]+(?:\.[0-9]+)?)\s*MB/i);
      if (mbMatch) {
        const val = parseFloat((parseFloat(mbMatch[1]) / 1024).toFixed(3));
        return val >= 1 ? val : null;
      }
      const numMatch = cleaned.match(/^([0-9]+(?:\.[0-9]+)?)$/);
      if (numMatch) {
        const val = parseFloat(numMatch[1]);
        return val >= 1 && val <= 64 ? val : null;
      }
      return null;
    }

    function normalizeStorage(storageText) {
      if (!storageText) return null;
      const cleaned = cleanText(storageText);
      if (!cleaned) return null;
      const tbMatch = cleaned.match(/([0-9]+(?:\.[0-9]+)?)\s*TB/i);
      if (tbMatch) return parseFloat(tbMatch[1]) * 1024;
      const gbMatch = cleaned.match(/([0-9]+(?:\.[0-9]+)?)\s*GB/i);
      if (gbMatch) return parseFloat(gbMatch[1]);
      const mbMatch = cleaned.match(/([0-9]+(?:\.[0-9]+)?)\s*MB/i);
      if (mbMatch) return parseFloat((parseFloat(mbMatch[1]) / 1024).toFixed(3));
      return null;
    }

    function normalizeDisplaySize(displayText) {
      if (!displayText || typeof displayText !== 'string') return null;
      const cleaned = cleanText(displayText);
      if (!cleaned) return null;

      // 1. Parenthetical inches inside cm spec: e.g. 17.42 cm (6.9"), 17.47 cm (6.88"), 16.75cm(6.59), 17.27 cm (6.8 inch)
      const parenInchMatch = cleaned.match(/([0-9]+(?:\.[0-9]+)?)\s*cm\s*\(\s*([0-9]+(?:\.[0-9]+)?)\s*(?:inch|inches|["”″″'’′]|\-inch)?\s*\)/i);
      if (parenInchMatch) {
        const inches = parseFloat(parenInchMatch[2]);
        if (inches >= 3.0 && inches <= 15.0) return inches;
      }

      // 2. Explicit inches: e.g. 6.8 Inches, 6.67", 6.8 inch, 6.9”
      const inchMatch = cleaned.match(/([0-9]+(?:\.[0-9]+)?)\s*(?:inches|inch|["”″″'’′]|\-inch)/i);
      if (inchMatch) {
        const val = parseFloat(inchMatch[1]);
        if (val >= 3.0 && val <= 15.0) return val;
      }

      // 3. Standalone cm: e.g. 15.54 cm -> 15.54 / 2.54 = 6.12
      const cmMatch = cleaned.match(/([0-9]+(?:\.[0-9]+)?)\s*cm/i);
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

    function extractDisplayFromText(text) {
      if (!text || typeof text !== 'string') return null;
      const cleaned = cleanText(text);
      if (!cleaned) return null;
      const parenMatch = cleaned.match(/([0-9]+(?:\.[0-9]+)?)\s*cm\s*\(\s*([0-9]+(?:\.[0-9]+)?)\s*(?:inch|inches|["”″″'’′]|\-inch)?\s*\)/i);
      if (parenMatch) {
        const inches = parseFloat(parenMatch[2]);
        if (inches >= 3.0 && inches <= 15.0) return inches;
      }
      const inchMatch = cleaned.match(/([0-9]+(?:\.[0-9]+)?)\s*(?:inches|inch|["”″″'’′]|\-inch)\s*(?:Super\s*Retina|AMOLED|OLED|LCD|FHD|QHD|HD\+|Screen|Display)?/i);
      if (inchMatch) {
        const inches = parseFloat(inchMatch[1]);
        if (inches >= 3.0 && inches <= 15.0) return inches;
      }
      return null;
    }

    function normalizeBattery(batteryText) {
      if (!batteryText || typeof batteryText !== 'string') return null;
      const cleaned = batteryText.replace(/,/g, '');
      const match = cleaned.match(/([0-9]{4,5})\s*(?:mAh|Milliamp\s*Hours|milliampere-hours)/i);
      if (match) {
        const val = parseInt(match[1], 10);
        return val >= 1000 && val <= 30000 ? val : null;
      }
      const bareMatch = cleaned.match(/([0-9]{4,5})/);
      if (bareMatch) {
        const val = parseInt(bareMatch[1], 10);
        return val >= 1000 && val <= 30000 ? val : null;
      }
      return null;
    }

    function extractBatteryFromText(text) {
      if (!text || typeof text !== 'string') return null;
      const match = text.replace(/,/g, '').match(/([0-9]{4,5})\s*mAh/i);
      if (match) {
        const val = parseInt(match[1], 10);
        if (val >= 1000 && val <= 30000) return val;
      }
      return null;
    }

    function extractModelFromTitle(title, brand) {
      if (!title || typeof title !== 'string' || !brand || typeof brand !== 'string') return null;
      const cleaned = cleanText(title);
      if (!cleaned) return null;

      let leadSegment = cleaned.split(/[\(\,\|\:]/)[0].trim();
      const brandRegex = new RegExp(`^${brand}\\s+`, 'i');
      leadSegment = leadSegment.replace(brandRegex, '').trim();
      leadSegment = leadSegment.replace(/\b[0-9]+(?:\.[0-9]+)?\s*(?:GB|TB)\b.*$/i, '').trim();
      leadSegment = leadSegment
        .replace(/\b(?:5G\s+AI\s+Smartphone|AI\s+Smartphone|5G\s+Smartphone|Smartphone|5G\s+Mobile\s+Phone|Mobile\s+Phone|5G\s+Phone|Phone|5G|4G\s+LTE|4G)\b.*$/i, '')
        .trim();

      return leadSegment.length > 0 ? leadSegment : null;
    }

    function extractProcessorFromText(text) {
      if (!text || typeof text !== 'string') return null;
      const cleaned = cleanText(text);
      if (!cleaned) return null;

      function stripSuffix(val) {
        if (!val) return null;
        return cleanText(val.replace(/\b(?:Mobile\s+Platform|Platform|Processor|Chipset|Chip)\b.*$/i, ''));
      }

      const snapdragonMatch = cleaned.match(/(?:Qualcomm\s+)?(Snapdragon\s*[0-9A-Za-z\s\+\-]+(?:\bGen\s*[0-9]+)?)/i);
      if (snapdragonMatch) return stripSuffix(snapdragonMatch[1]);

      const dimensityMatch = cleaned.match(/(?:MediaTek\s+)?(Dimensity\s*[0-9]+(?:\s*(?:Ultra|Max|Plus|\+))?)/i);
      if (dimensityMatch) return stripSuffix(dimensityMatch[0]);

      const helioMatch = cleaned.match(/(?:MediaTek\s+)?(Helio\s*[A-Za-z0-9]+)/i);
      if (helioMatch) return stripSuffix(helioMatch[0]);

      const appleMatch = cleaned.match(/\b(A[0-9]{1,2}\s*(?:Pro\s*Max|Pro|Bionic|Max)?)\b/i);
      if (appleMatch) return stripSuffix(appleMatch[1]);

      const tensorMatch = cleaned.match(/(?:Google\s+)?(Tensor\s*G[0-9]+)/i);
      if (tensorMatch) return stripSuffix(tensorMatch[0]);

      const exynosMatch = cleaned.match(/(?:Samsung\s+)?(Exynos\s*[0-9]+)/i);
      if (exynosMatch) return stripSuffix(exynosMatch[0]);

      const unisocMatch = cleaned.match(/(?:Unisoc\s+)?([T|SC][0-9]{3,4}[A-Za-z0-9]*)/i);
      if (unisocMatch) return stripSuffix(unisocMatch[0]);

      return null;
    }

    function extractConfigFromText(text) {
      if (!text || typeof text !== 'string') return { ram_gb: null, storage_gb: null };
      const ramLabeled = text.match(/([0-9]+(?:\.[0-9]+)?)\s*(?:GB|MB|TB)?\s*RAM/i);
      const storageLabeled = text.match(/([0-9]+(?:\.[0-9]+)?)\s*(?:GB|TB)\s*(?:Storage|ROM|Internal(?:\s*Storage)?)/i);
      let ram_gb = ramLabeled ? normalizeRam(ramLabeled[0]) : null;
      let storage_gb = storageLabeled ? normalizeStorage(storageLabeled[0]) : null;

      const pairedMatch = text.match(/([0-9]+(?:\.[0-9]+)?)\s*(?:GB)?\s*[\+\/\-]\s*([0-9]+(?:\.[0-9]+)?)\s*(GB|TB)/i);
      if (pairedMatch) {
        const candidateRam = parseFloat(pairedMatch[1]);
        const isTb = (pairedMatch[3] || '').toUpperCase() === 'TB';
        const candidateStorage = isTb ? parseFloat(pairedMatch[2]) * 1024 : parseFloat(pairedMatch[2]);
        if (candidateRam >= 1 && candidateRam <= 64 && candidateStorage >= 16 && candidateStorage <= 2048) {
          if (ram_gb === null) ram_gb = candidateRam;
          if (storage_gb === null) storage_gb = candidateStorage;
        }
      }

      const parenMatch = text.match(/\(\s*([0-9]+)\s*GB\s*[\,\+\/]\s*([0-9]+)\s*(GB|TB)\s*\)/i);
      if (parenMatch) {
        const cRam = parseFloat(parenMatch[1]);
        const isTb = (parenMatch[3] || '').toUpperCase() === 'TB';
        const cStorage = isTb ? parseFloat(parenMatch[2]) * 1024 : parseFloat(parenMatch[2]);
        if (cRam >= 1 && cRam <= 64 && cStorage >= 16 && cStorage <= 2048) {
          if (ram_gb === null) ram_gb = cRam;
          if (storage_gb === null) storage_gb = cStorage;
        }
      }

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

    function normalize5G(textList) {
      const combined = (Array.isArray(textList) ? textList.join(' ') : String(textList || '')).toLowerCase();
      if (combined.includes('5g')) return true;
      if (combined.includes('4g lte') || combined.includes('4g only') || combined.includes('cellular 4g')) {
        if (!combined.includes('5g')) return false;
      }
      if (/\biphone\s*(?:1[2-9]|[2-9][0-9])/i.test(combined)) {
        return true;
      }
      return null;
    }

    function normalizeOperatingSystem(osText) {
      if (!osText) return null;
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

    function normalizeAvailability(availText) {
      if (!availText) return null;
      const lower = availText.toLowerCase();
      if (lower.includes('in stock') || lower.includes('available to ship') || lower.includes('usually dispatched in')) {
        return 'in_stock';
      }
      if (lower.includes('out of stock') || lower.includes('currently unavailable') || lower.includes('temporarily out of stock')) {
        return 'out_of_stock';
      }
      return 'unknown';
    }

    // Extract raw specifications from overview, technical tables, and bullet points
    const specs = [];
    const seenLabels = new Set();
    function addSpec(rawLabel, rawValue) {
      let label = cleanText(rawLabel);
      const value = cleanText(rawValue);
      if (!label || !value) return;

      label = label.replace(/[:\-\s\u00a0\u200b]+$/, '').trim();
      if (label.length > 0 && value.length > 0 && !seenLabels.has(label.toLowerCase())) {
        seenLabels.add(label.toLowerCase());
        specs.push({ label, value });
      }
    }

    // 1. Amazon product overview table (often at top near title)
    document.querySelectorAll('#productOverview_feature_div tr, table.a-normal.a-spacing-micro tr').forEach(row => {
      const labelEl = row.querySelector('td:first-child span, th');
      const valEl = row.querySelector('td:last-child span, td.a-span9 span');
      if (labelEl && valEl) addSpec(labelEl.textContent, valEl.textContent);
    });

    // 1b. Amazon div-based product overview grid (#productOverview_feature_div .a-row, #poExpander .a-row)
    document.querySelectorAll('#productOverview_feature_div .a-row, #poExpander .a-row').forEach(row => {
      const labelEl = row.querySelector('.a-column:first-child span, div[class*="a-span3"] span, .po-label');
      const valEl = row.querySelector('.a-column:last-child span, div[class*="a-span9"] span, .po-value, .po-break-word');
      if (labelEl && valEl) addSpec(labelEl.textContent, valEl.textContent);
    });

    // 2. Technical details tables (expanded, collapsible, or standard)
    const techRows = document.querySelectorAll([
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
          const parts = (row.textContent || '').split(/:\s*/);
          if (parts.length >= 2) addSpec(parts[0], parts.slice(1).join(': '));
        }
      } else {
        const th = row.querySelector('th');
        const td = row.querySelector('td');
        if (th && td) addSpec(th.textContent, td.textContent);
      }
    });

    // 3. "About this item" feature bullets (#feature-bullets, #featurebullets_feature_div)
    document.querySelectorAll('#feature-bullets ul li, #featurebullets_feature_div ul li').forEach(li => {
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

    function findSpecValue(regexes) {
      for (const regex of regexes) {
        for (const s of specs) {
          if (regex.test(s.label)) return s.value;
        }
      }
      return null;
    }

    const title = cleanText(
      document.querySelector('#productTitle')?.textContent ||
      document.querySelector('meta[property="og:title"]')?.getAttribute('content')
    );

    let brandText = cleanText(
      document.querySelector('#bylineInfo')?.textContent ||
      document.querySelector('a#bylineInfo')?.textContent ||
      document.querySelector('#brand')?.textContent
    );
    if (brandText) {
      brandText = brandText.replace(/^(?:Visit the\s+|Brand:\s*)/i, '').replace(/\s+Store$/i, '').trim();
    }

    const priceText = cleanText(
      document.querySelector('.a-price .a-offscreen')?.textContent ||
      document.querySelector('.apexPriceToPay .a-offscreen')?.textContent ||
      document.querySelector('.priceToPay .a-offscreen')?.textContent ||
      document.querySelector('#corePrice_desktop .a-price .a-offscreen')?.textContent ||
      document.querySelector('#corePriceDisplay_desktop_feature_div .a-price .a-offscreen')?.textContent ||
      document.querySelector('#priceblock_ourprice')?.textContent ||
      document.querySelector('#priceblock_dealprice')?.textContent
    );

    const ratingText = cleanText(
      document.querySelector('#acrPopover')?.getAttribute('title') ||
      document.querySelector('.a-icon-star-small .a-icon-alt')?.textContent ||
      document.querySelector('.a-icon-star .a-icon-alt')?.textContent
    );

    const reviewCountText = cleanText(
      document.querySelector('#acrCustomerReviewText')?.textContent ||
      document.querySelector('[data-hook="total-review-count"]')?.textContent
    );

    const availabilityText = cleanText(
      document.querySelector('#availability span')?.textContent ||
      document.querySelector('#availability')?.textContent
    );

    const modelText = findSpecValue([
      /^model\s*name[:\s]*$/i,
      /^item\s*model\s*name[:\s]*$/i,
      /^model[:\s]*$/i,
      /^series[:\s]*$/i,
      /^device\s*name[:\s]*$/i,
      /^phone\s*model[:\s]*$/i
    ]);

    const variantText = cleanText(
      document.querySelector('#variation_size_name .selection')?.textContent ||
      document.querySelector('#variation_color_name .selection')?.textContent ||
      document.querySelector('#inline-twister-expanded-dimension-text-size_name')?.textContent
    );

    const url = window.location.href;
    const asin = extractAsinFromUrl(url);

    const priceNorm = normalizePrice(priceText);
    const ratingNorm = normalizeRating(ratingText);
    const reviewCountNorm = normalizeReviewCount(reviewCountText);
    const availNorm = normalizeAvailability(availabilityText);

    const rawBrand = brandText || findSpecValue([/^brand[:\s]*$/i, /^manufacturer[:\s]*$/i]);
    const titleText = title || '';

    let rawModelName = modelText || findSpecValue([
      /^model\s*name[:\s]*$/i,
      /^item\s*model\s*name[:\s]*$/i,
      /^model[:\s]*$/i,
      /^series[:\s]*$/i,
      /^device\s*name[:\s]*$/i,
      /^phone\s*model[:\s]*$/i
    ]);

    if (!rawModelName && rawBrand && titleText) {
      rawModelName = extractModelFromTitle(titleText, rawBrand);
    }

    const rawModelNumber = findSpecValue([
      /^item\s*model\s*number[:\s]*$/i,
      /^model\s*number[:\s]*$/i,
      /^part\s*number[:\s]*$/i,
      /^item\s*part\s*number[:\s]*$/i
    ]);

    const rawRam = findSpecValue([
      /^ram(?:\s+memory)?[:\s]*$/i,
      /^ram\s*size[:\s]*$/i,
      /^installed\s*ram(?:\s*size)?[:\s]*$/i,
      /^ram\s*memory\s*installed\s*size[:\s]*$/i,
      /^memory\s*ram\s*installed\s*size[:\s]*$/i,
      /^computer\s*memory\s*size[:\s]*$/i,
      /^system\s*ram[:\s]*$/i,
      /^installed\s*memory[:\s]*$/i,
      /^ram[:\s]*$/i
    ]);

    const rawStorage = findSpecValue([
      /^storage(?:\s+capacity)?[:\s]*$/i,
      /^memory\s*storage\s*capacity[:\s]*$/i,
      /^internal\s*storage[:\s]*$/i,
      /^rom[:\s]*$/i,
      /^hard\s*disk\s*size[:\s]*$/i,
      /^flash\s*memory\s*installed\s*size[:\s]*$/i,
      /^digital\s*storage\s*capacity[:\s]*$/i,
      /^built-in\s*storage[:\s]*$/i,
      /^internal\s*memory[:\s]*$/i
    ]);

    const rawDisplay = findSpecValue([
      /^screen\s*size[:\s]*$/i,
      /^display\s*size[:\s]*$/i,
      /^standing\s*screen\s*display\s*size[:\s]*$/i,
      /^screen\s*dimensions[:\s]*$/i,
      /^display[:\s]*$/i,
      /^screen[:\s]*$/i
    ]);

    const rawBattery = findSpecValue([
      /^battery\s*capacity[:\s]*$/i,
      /^battery\s*power\s*rating[:\s]*$/i,
      /^battery\s*power[:\s]*$/i,
      /^battery(?:\s*capacity)?\s*\(mah\)[:\s]*$/i,
      /^battery[:\s]*$/i
    ]);

    const rawOS = findSpecValue([
      /^operating\s*system[:\s]*$/i,
      /^os[:\s]*$/i,
      /^software\s*platform[:\s]*$/i
    ]);

    let rawProcessor = findSpecValue([
      /^processor[:\s]*$/i,
      /^cpu\s*model[:\s]*$/i,
      /^processor\s*type[:\s]*$/i,
      /^chipset[:\s]*$/i,
      /^processor\s*brand[:\s]*$/i
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

    let ram_gb = normalizeRam(rawRam);
    let storage_gb = normalizeStorage(rawStorage);

    const warnings = [];
    const errors = [];

    const variantConfig = extractConfigFromText(variantText);
    const titleConfig = extractConfigFromText(titleText);

    if (variantConfig.ram_gb !== null && variantConfig.storage_gb !== null) {
      if (ram_gb !== null && ram_gb !== variantConfig.ram_gb) {
        warnings.push(`Selected variant RAM (${variantConfig.ram_gb} GB) takes precedence over table RAM (${ram_gb} GB).`);
      }
      if (storage_gb !== null && storage_gb !== variantConfig.storage_gb) {
        warnings.push(`Selected variant storage (${variantConfig.storage_gb} GB) takes precedence over table storage (${storage_gb} GB).`);
      }
      ram_gb = variantConfig.ram_gb;
      storage_gb = variantConfig.storage_gb;
    } else {
      if (ram_gb === null && variantConfig.ram_gb !== null) {
        ram_gb = variantConfig.ram_gb;
      }
      if (storage_gb === null && variantConfig.storage_gb !== null) {
        storage_gb = variantConfig.storage_gb;
      }

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
        const titleRamMatch = titleText.match(/([0-9]+)\s*GB\s*RAM/i);
        if (titleRamMatch) ram_gb = parseFloat(titleRamMatch[1]);
      }

      if (storage_gb === null && titleConfig.storage_gb !== null) {
        storage_gb = titleConfig.storage_gb;
      } else if (storage_gb === null && titleText) {
        const titleStorageMatch = titleText.match(/([0-9]+(?:\.[0-9]+)?)\s*(?:GB|TB)\s*(?:Storage|ROM|Internal)/i) ||
                                   titleText.match(/\(\s*([0-9]+(?:\.[0-9]+)?)\s*(?:GB|TB)/i) ||
                                   titleText.match(/\b(16|32|64|128|256|512)\s*(GB|TB)\b/i) ||
                                   titleText.match(/\b([1-2])\s*TB\b/i);
        if (titleStorageMatch) storage_gb = normalizeStorage(titleStorageMatch[0]);
      }
    }

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
    if (!operating_system && (brandText === 'Apple' || /^iPhone\b/i.test(titleText || ''))) {
      operating_system = 'iOS';
    }
    const spec5GValues = specs
      .filter(s => /cellular|network|wireless|connectivity/i.test(s.label))
      .map(s => s.value);
    const supports_5g = normalize5G([titleText, rawModelName, ...spec5GValues]);

    if (!title) {
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

    return {
      schema_version: '1.0',
      record_id: null,
      source: {
        marketplace: 'amazon.in',
        product_url: url,
        extracted_at: new Date().toISOString(),
        extraction_method: 'browser_extension_user_initiated',
        extension_version: '1.0.0',
        page_title: cleanText(document.title) || null,
        asin: asin
      },
      raw_extraction: {
        title: title || null,
        brand_text: brandText || null,
        model_text: modelText || null,
        variant_text: variantText || null,
        price_text: priceText || null,
        rating_text: ratingText || null,
        review_count_text: reviewCountText || null,
        availability_text: availabilityText || null,
        specifications_text: specs
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
  } catch (err) {
    return {
      error: 'DOM_INSPECTION_EXCEPTION',
      message: `Failed while inspecting page DOM: ${err && err.message ? err.message : String(err)}`
    };
  }
}

// Expose globally for popup and return result when injected as a file
if (typeof window !== 'undefined') {
  window.extractAmazonSmartphoneData = extractAmazonSmartphoneData;
}

// If executed directly on an Amazon India tab via executeScript({ files: [...] })
(typeof window !== 'undefined' && window.location && window.location.hostname.endsWith('amazon.in'))
  ? extractAmazonSmartphoneData()
  : null;
