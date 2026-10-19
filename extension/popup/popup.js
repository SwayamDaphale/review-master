/**
 * Popup user interface logic for Review Master Extension
 */

let currentRecord = null;

const extractBtn = document.getElementById('extractBtn');
const downloadBtn = document.getElementById('downloadBtn');
const statusIndicator = document.getElementById('statusIndicator');
const messageContainer = document.getElementById('messageContainer');
const resultsContainer = document.getElementById('resultsContainer');
const validationBadge = document.getElementById('validationBadge');

// Summary elements
const productTitleSummary = document.getElementById('productTitleSummary');
const brandVal = document.getElementById('brandVal');
const modelVal = document.getElementById('modelVal');
const configVal = document.getElementById('configVal');
const priceVal = document.getElementById('priceVal');
const batteryVal = document.getElementById('batteryVal');
const displayVal = document.getElementById('displayVal');
const networkVal = document.getElementById('networkVal');
const processorVal = document.getElementById('processorVal');
const identityVal = document.getElementById('identityVal');

// Tab elements
const tabButtons = document.querySelectorAll('.tab-btn');
const tabContents = document.querySelectorAll('.tab-content');
const normalizedJson = document.getElementById('normalizedJson');
const rawJson = document.getElementById('rawJson');
const warningsList = document.getElementById('warningsList');
const warningCount = document.getElementById('warningCount');

// Tab switching
tabButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    tabButtons.forEach(b => b.classList.remove('active'));
    tabContents.forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    const tabId = btn.getAttribute('data-tab');
    document.getElementById(tabId).classList.add('active');
  });
});

function showMessage(text, type = 'error') {
  messageContainer.textContent = text;
  messageContainer.className = `message-container message-${type}`;
  messageContainer.classList.remove('hidden');
}

function clearMessage() {
  messageContainer.textContent = '';
  messageContainer.className = 'message-container hidden';
}

function updateStatus(status, label) {
  statusIndicator.className = `status-indicator status-${status}`;
  statusIndicator.textContent = label;
}

// Extraction click handler
extractBtn.addEventListener('click', async () => {
  clearMessage();
  resultsContainer.classList.add('hidden');
  downloadBtn.disabled = true;
  updateStatus('extracting', 'Extracting...');

  try {
    // 1. Identify active tab reliably
    let tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    let tab = tabs && tabs.length > 0 ? tabs[0] : null;

    if (!tab || !tab.id) {
      // Fallback for detached windows or popups
      tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
      tab = tabs && tabs.length > 0 ? tabs[0] : null;
    }

    if (!tab || !tab.id || !tab.url) {
      showMessage('Could not identify the active browser tab. Please ensure a tab is active.', 'error');
      updateStatus('invalid', 'Tab Error');
      return;
    }

    // 2. URL validation
    const tabUrl = tab.url;
    const isAmazonIn = tabUrl.startsWith('https://www.amazon.in/') || tabUrl.startsWith('https://amazon.in/');
    if (!isAmazonIn) {
      showMessage('Unsupported page: Review Master only operates on Amazon India (https://www.amazon.in/) smartphone pages.', 'error');
      updateStatus('invalid', 'Unsupported URL');
      return;
    }

    // 3. Check if tab is still loading
    if (tab.status === 'loading') {
      showMessage('Page is still loading. Please wait 2 seconds for the Amazon page to finish loading and try again.', 'warning');
      updateStatus('needs-review', 'Page Loading');
      return;
    }

    // 4. Execute content extraction in active tab
    // In MV3 chrome.scripting.executeScript, passing a func guarantees the return value
    // is serialized and received as firstResult.result across all Chromium browsers (Brave, Chrome, Edge).
    let injectionResults;
    try {
      const fn = (typeof extractAmazonSmartphoneData === 'function')
        ? extractAmazonSmartphoneData
        : (typeof window !== 'undefined' && typeof window.extractAmazonSmartphoneData === 'function')
          ? window.extractAmazonSmartphoneData
          : null;

      if (fn) {
        injectionResults = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: fn
        });
      } else {
        injectionResults = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ['src/content-script.js']
        });
      }
    } catch (injectErr) {
      console.error('[Review Master] Script injection failed:', injectErr);
      const msg = injectErr.message || String(injectErr);
      if (msg.includes('Cannot access') || msg.includes('permission')) {
        showMessage('Permission error: Unable to access this tab. Ensure the active tab is https://www.amazon.in/', 'error');
        updateStatus('invalid', 'Permission Denied');
      } else {
        showMessage(`Script injection failed: ${msg}`, 'error');
        updateStatus('invalid', 'Injection Error');
      }
      return;
    }

    // 5. Inspect returned payload
    if (!Array.isArray(injectionResults) || injectionResults.length === 0) {
      showMessage('No result received from content script execution. Try refreshing the Amazon tab.', 'error');
      updateStatus('invalid', 'Empty Result');
      return;
    }

    const firstResult = injectionResults[0];
    const payload = firstResult ? firstResult.result : null;

    if (!payload) {
      showMessage('Failed to inspect the page DOM. The content script returned no data. Ensure the product page is fully rendered.', 'error');
      updateStatus('invalid', 'No Data Returned');
      return;
    }

    if (payload.error) {
      const errType = payload.error;
      const errMsg = payload.message || 'Page is unsupported or extraction could not complete.';
      showMessage(`[${errType}] ${errMsg}`, 'error');
      updateStatus('invalid', errType);
      return;
    }

    // 6. Check if product title was found
    if (!payload.raw_extraction || !payload.raw_extraction.title) {
      showMessage('Product information not found: The page does not contain standard Amazon smartphone product markers. Please verify this is a single product listing.', 'warning');
      updateStatus('needs-review', 'Product Not Found');
      // Still allow previewing whatever was parsed
      currentRecord = payload;
      renderResults(currentRecord);
      downloadBtn.disabled = false;
      return;
    }

    currentRecord = payload;
    renderResults(currentRecord);
    downloadBtn.disabled = false;
  } catch (err) {
    console.error('[Review Master] Extraction error:', err);
    showMessage(`Unexpected extraction error: ${err.message || 'Unable to execute content script.'}`, 'error');
    updateStatus('invalid', 'Execution Error');
  }
});

function renderResults(record) {
  const norm = record.normalized;
  const val = record.validation;

  productTitleSummary.textContent = record.raw_extraction.title || 'Untitled Product';
  brandVal.textContent = norm.brand || '(Not found)';
  modelVal.textContent = norm.model_name || norm.model_number || '(Not found)';

  const ramStr = norm.ram_gb ? `${norm.ram_gb} GB RAM` : null;
  const storStr = norm.storage_gb ? `${norm.storage_gb} GB` : null;
  configVal.textContent = [ramStr, storStr].filter(Boolean).join(' / ') || 'null';

  priceVal.textContent = norm.price_amount !== null ? `₹ ${norm.price_amount.toLocaleString('en-IN')}` : 'Price unavailable';
  batteryVal.textContent = norm.battery_capacity_mah ? `${norm.battery_capacity_mah} mAh` : 'null';
  displayVal.textContent = norm.display_size_inches ? `${norm.display_size_inches}"` : 'null';
  networkVal.textContent = norm.supports_5g === true ? '5G Yes' : (norm.supports_5g === false ? '4G Only' : 'Unknown');
  if (processorVal) {
    processorVal.textContent = norm.processor || '(Not found)';
  }
  identityVal.textContent = (val && val.identity_status) ? val.identity_status.toUpperCase() : 'UNKNOWN';

  // Status and badge
  validationBadge.textContent = (val && val.status) ? val.status : 'unknown';
  validationBadge.className = `badge badge-${(val && val.status) ? val.status : 'invalid'}`;
  updateStatus(
    (val && val.status === 'valid') ? 'valid' : ((val && val.status === 'needs_review') ? 'needs-review' : 'invalid'),
    (val && val.status) ? val.status.toUpperCase() : 'UNKNOWN'
  );

  // JSON tabs
  normalizedJson.textContent = JSON.stringify(record.normalized, null, 2);
  rawJson.textContent = JSON.stringify(record.raw_extraction, null, 2);

  // Warnings tab
  warningsList.innerHTML = '';
  const allIssues = [...(val.errors || []).map(e => `[ERROR] ${e}`), ...(val.warnings || [])];
  warningCount.textContent = allIssues.length;

  if (allIssues.length === 0) {
    warningsList.innerHTML = '<div style="color: #94a3b8; font-size: 11px;">No warnings or missing critical parameters.</div>';
  } else {
    allIssues.forEach(w => {
      const div = document.createElement('div');
      div.className = 'warning-item';
      div.textContent = w;
      warningsList.appendChild(div);
    });
  }

  resultsContainer.classList.remove('hidden');
}

// Download JSON handler
downloadBtn.addEventListener('click', () => {
  if (!currentRecord) return;

  const asin = currentRecord.source.asin || 'record';
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const filename = `smartphone-extraction-${asin}-${timestamp}.json`;

  const blob = new Blob([JSON.stringify(currentRecord, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
});
