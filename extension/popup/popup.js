/**
 * Popup user interface logic for Review Master Extension
 */

let currentRecord = null;
let lastJobId = null;
let resolvedVariantId = null;

const extractBtn = document.getElementById('extractBtn');
const downloadBtn = document.getElementById('downloadBtn');
const openWebBtn = document.getElementById('openWebBtn');
const submitBtn = document.getElementById('submitBtn');
const compareBtn = document.getElementById('compareBtn');
const statusIndicator = document.getElementById('statusIndicator');
const messageContainer = document.getElementById('messageContainer');
const submitStatusContainer = document.getElementById('submitStatusContainer');
const submitStatusText = document.getElementById('submitStatusText');
const jobIdText = document.getElementById('jobIdText');
const identityMatchText = document.getElementById('identityMatchText');
const resolvedVariantRow = document.getElementById('resolvedVariantRow');
const resolvedVariantText = document.getElementById('resolvedVariantText');
const compareContainer = document.getElementById('compareContainer');
const compareSessionSelect = document.getElementById('compareSessionSelect');
const confirmCompareBtn = document.getElementById('confirmCompareBtn');
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
  if (openWebBtn) {
    openWebBtn.disabled = true;
    openWebBtn.classList.add('hidden');
  }
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.classList.add('hidden');
  }
  if (submitStatusContainer) {
    submitStatusContainer.classList.add('hidden');
  }
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
  if (openWebBtn) {
    openWebBtn.disabled = false;
    openWebBtn.classList.remove('hidden');
  }
  if (submitBtn) {
    submitBtn.disabled = false;
    submitBtn.classList.remove('hidden');
  }
}

// Backend API configuration for Review Master ingestion pipeline
const API_BASE_URL = 'http://localhost:8000';

if (submitBtn) {
  submitBtn.addEventListener('click', async () => {
    if (!currentRecord) return;
    clearMessage();
    submitBtn.disabled = true;
    if (submitStatusContainer) {
      submitStatusContainer.classList.remove('hidden');
      submitStatusText.textContent = 'Submitting to Review Master backend...';
      jobIdText.textContent = 'Allocating...';
      if (identityMatchText) identityMatchText.textContent = 'Pending Ingestion';
      if (resolvedVariantRow) resolvedVariantRow.classList.add('hidden');
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/listings/ingest`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(currentRecord),
      });

      const data = await response.json().catch(() => null);

      if (!response.ok) {
        const errorMsg = data && data.detail
          ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))
          : `HTTP ${response.status} ${response.statusText}`;
        showMessage(`Backend submission rejected: ${errorMsg}`, 'error');
        if (submitStatusText) {
          submitStatusText.textContent = `Rejected (${response.status})`;
        }
        submitBtn.disabled = false;
        return;
      }

      lastJobId = data.job_id || null;
      if (submitStatusText) {
        submitStatusText.textContent = data.is_duplicate
          ? 'Accepted (Duplicate / Idempotent Cached)'
          : 'Accepted (Processing Scheduled)';
      }
      if (jobIdText) {
        jobIdText.textContent = data.job_id || 'N/A';
      }

      // Poll for job completion if job_id exists
      if (data.job_id) {
        let pollCount = 0;
        const maxPolls = 15;
        const pollInterval = setInterval(async () => {
          pollCount++;
          try {
            const statusRes = await fetch(`${API_BASE_URL}/api/v1/ingestion-jobs/${data.job_id}`);
            if (statusRes.ok) {
              const statusData = await statusRes.json();
              if (submitStatusText) {
                submitStatusText.textContent = `Job ${statusData.status.toUpperCase()}`;
              }

              if (statusData.status === 'completed' || statusData.status === 'failed') {
                clearInterval(pollInterval);

                // Run deterministic identity resolution to resolve product/variant match
                try {
                  const resolvePayload = {
                    marketplace_code: 'amazon_in',
                    asin: currentRecord.source?.asin || 'UNKNOWN',
                    raw_title: currentRecord.raw_extraction?.title || '',
                    brand: currentRecord.normalized?.brand || null,
                    model_name: currentRecord.normalized?.model_name || null,
                    ram_gb: currentRecord.normalized?.ram_gb || null,
                    storage_gb: currentRecord.normalized?.storage_gb || null,
                  };

                  const idRes = await fetch(`${API_BASE_URL}/api/v1/identity/resolve`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(resolvePayload),
                  });

                  if (idRes.ok) {
                    const idData = await idRes.json();
                    const outcomeLabel = idData.outcome ? idData.outcome.replace('MATCH_', '') : 'RESOLVED';
                    if (identityMatchText) {
                      identityMatchText.textContent = outcomeLabel;
                    }

                    if (idData.variant_id) {
                      resolvedVariantId = idData.variant_id;
                      if (resolvedVariantRow && resolvedVariantText) {
                        resolvedVariantRow.classList.remove('hidden');
                        resolvedVariantText.textContent = String(idData.variant_id);
                      }
                      if (compareBtn) {
                        compareBtn.disabled = false;
                        compareBtn.classList.remove('hidden');
                      }
                    } else if (idData.product_id && !idData.variant_id) {
                      if (identityMatchText) {
                        identityMatchText.textContent = 'Product Family Matched (New Variant)';
                      }
                    }
                  }
                } catch {
                  // Ignore identity resolution error in UI
                }

                // Persist state in local extension storage if supported
                if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                  chrome.storage.local.set({
                    rm_last_record: currentRecord,
                    rm_last_job_id: data.job_id,
                    rm_resolved_variant_id: resolvedVariantId,
                  }).catch(() => {});
                }
              }
            }
          } catch {
            // Ignore polling errors
          }
          if (pollCount >= maxPolls) {
            clearInterval(pollInterval);
          }
        }, 1500);
      }
    } catch (netErr) {
      showMessage(`Network error connecting to backend: ${netErr.message || 'Connection refused at localhost:8000'}`, 'error');
      if (submitStatusText) {
        submitStatusText.textContent = 'Network Connection Failed';
      }
      submitBtn.disabled = false;
    }
  });
}

// Add to Compare click handler (Module 12)
if (compareBtn) {
  compareBtn.addEventListener('click', async () => {
    if (!resolvedVariantId) {
      showMessage('No resolved variant available to compare.', 'warning');
      return;
    }
    clearMessage();
    if (compareContainer) {
      compareContainer.classList.remove('hidden');
    }

    try {
      // Query active comparison sessions
      const sessionsRes = await fetch(`${API_BASE_URL}/api/v1/comparisons?status=active`);
      if (sessionsRes.ok) {
        const sessions = await sessionsRes.json();
        if (compareSessionSelect) {
          compareSessionSelect.innerHTML = '<option value="new">+ Create New Active Session</option>';
          if (Array.isArray(sessions)) {
            sessions.forEach((s) => {
              const opt = document.createElement('option');
              opt.value = s.id;
              opt.textContent = `${s.title || 'Comparison'} (${s.item_count || 0} items)`;
              compareSessionSelect.appendChild(opt);
            });
          }
        }
      }
    } catch {
      // Session fetch error, fallback to creating new session
    }
  });
}

if (confirmCompareBtn) {
  confirmCompareBtn.addEventListener('click', async () => {
    if (!resolvedVariantId) return;
    clearMessage();
    confirmCompareBtn.disabled = true;

    try {
      let targetSessionId = compareSessionSelect ? compareSessionSelect.value : 'new';
      if (targetSessionId === 'new') {
        const title = `Comparison: ${currentRecord?.normalized?.model_name || 'Product'}`;
        const newSessionRes = await fetch(`${API_BASE_URL}/api/v1/comparisons`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title }),
        });
        if (!newSessionRes.ok) {
          const errData = await newSessionRes.json().catch(() => null);
          const detail = errData?.detail || `HTTP ${newSessionRes.status}`;
          showMessage(`Could not create comparison session: ${detail}`, 'error');
          confirmCompareBtn.disabled = false;
          return;
        }
        const newSession = await newSessionRes.json();
        targetSessionId = newSession.id;
      }

      // Add variant to comparison session
      const addRes = await fetch(`${API_BASE_URL}/api/v1/comparisons/${targetSessionId}/items`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ variant_id: resolvedVariantId }),
      });

      if (!addRes.ok) {
        const errData = await addRes.json().catch(() => null);
        const detail = errData?.detail || `HTTP ${addRes.status}`;
        showMessage(`Could not add to compare: ${detail}`, 'error');
      } else {
        showMessage('Successfully added product variant to comparison session!', 'info');
        if (compareContainer) compareContainer.classList.add('hidden');
      }
    } catch (err) {
      showMessage(`Comparison error: ${err.message || 'Connection failed'}`, 'error');
    } finally {
      confirmCompareBtn.disabled = false;
    }
  });
}

// Open in Review Master Web app handler with Secure Single-Use Handoff (Module 13)
if (openWebBtn) {
  openWebBtn.addEventListener('click', async () => {
    if (!currentRecord) return;
    clearMessage();
    openWebBtn.disabled = true;

    try {
      // Request secure single-use handoff code from backend
      const tokenRes = await fetch(`${API_BASE_URL}/api/v1/import-tokens`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: lastJobId || undefined,
          context_data: {
            asin: currentRecord.source?.asin || 'UNKNOWN',
            title: currentRecord.raw_extraction?.title || '',
          },
        }),
      });

      if (!tokenRes.ok) {
        throw new Error('Failed to create single-use handoff token.');
      }

      const tokenData = await tokenRes.json();
      const code = tokenData.import_code;
      const targetUrl = `http://localhost:5173/app/import?code=${encodeURIComponent(code)}`;

      if (typeof chrome !== 'undefined' && chrome.tabs && typeof chrome.tabs.create === 'function') {
        chrome.tabs.create({ url: targetUrl });
      } else if (typeof window !== 'undefined') {
        window.open(targetUrl, '_blank');
      }
      showMessage('Secure single-use handoff initiated. Opening web application...', 'info');
    } catch (err) {
      showMessage(`Handoff error: ${err.message}. Ensure Review Master backend is running.`, 'error');
    } finally {
      openWebBtn.disabled = false;
    }
  });
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
