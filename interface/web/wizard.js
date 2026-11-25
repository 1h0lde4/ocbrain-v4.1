const API = '';
let state = null;
let selectedModels = new Set();

async function init() {
  try {
    // Check if wizard already done
    const r = await fetch(`${API}/api/wizard/status`);
    const s = await r.json();
    if (s.complete && !new URLSearchParams(location.search).has('force')) {
      location.href = '/';
      return;
    }
    // Start detection
    await runDetection();
  } catch (e) {
    document.getElementById('scan-status').textContent = 'Could not connect to OCBrain. Is it running?';
  }
}

async function runDetection() {
  document.getElementById('scan-status').textContent = 'Scanning GPU, CPU and RAM...';
  try {
    const r = await fetch(`${API}/api/wizard/detect`, { method: 'POST', headers: {'X-OCBrain-Local': '1'} });
    state = await r.json();
    showReview();
  } catch (e) {
    document.getElementById('scan-status').textContent = `Detection failed: ${e.message}`;
  }
}

function showReview() {
  setStep(1);
  hide('screen-detecting'); show('screen-review');

  const report = state.report;
  const rec    = state.recommendation;
  const grid   = document.getElementById('hw-grid');

  // GPU tile
  let gpuHtml = '';
  if (report.best_gpu) {
    const g = report.best_gpu;
    const cudaBadge = g.cuda_available
      ? `<span class="badge badge-ok">CUDA ${g.cuda_version || '✓'}</span>`
      : g.rocm_available ? `<span class="badge badge-ok">ROCm ✓</span>`
      : g.metal_available ? `<span class="badge badge-ok">Metal ✓</span>`
      : `<span class="badge badge-warn">Driver needed</span>`;
    gpuHtml = `<div class="hw-tile">
      <div class="hw-tile-label">GPU</div>
      <div class="hw-tile-value">${g.vendor} ${g.model} ${cudaBadge}</div>
      <div class="hw-tile-sub">${g.vram_gb.toFixed(1)} GB VRAM · Tier: ${g.tier}</div>
    </div>`;
  } else {
    gpuHtml = `<div class="hw-tile">
      <div class="hw-tile-label">GPU</div>
      <div class="hw-tile-value">No discrete GPU <span class="badge badge-na">CPU Mode</span></div>
      <div class="hw-tile-sub">AI will run on CPU</div>
    </div>`;
    document.getElementById('btn-gpu').disabled = true;
    document.getElementById('btn-gpu').title = 'No GPU detected';
  }

  // CPU tile
  const cpu = report.cpu;
  const cpuHtml = `<div class="hw-tile">
    <div class="hw-tile-label">CPU</div>
    <div class="hw-tile-value">${cpu.model.substring(0,42)}</div>
    <div class="hw-tile-sub">${cpu.physical_cores}c/${cpu.logical_cores}t</div>
  </div>`;

  // RAM tile
  const ramHtml = `<div class="hw-tile">
    <div class="hw-tile-label">System RAM</div>
    <div class="hw-tile-value">${cpu.ram_gb.toFixed(0)} GB</div>
    <div class="hw-tile-sub">Available for AI models</div>
  </div>`;

  // Tier tile
  const tierHtml = `<div class="hw-tile">
    <div class="hw-tile-label">Recommended Tier</div>
    <div class="hw-tile-value">${rec.tier.charAt(0).toUpperCase() + rec.tier.slice(1)}</div>
    <div class="hw-tile-sub">${rec.note}</div>
  </div>`;

  grid.innerHTML = gpuHtml + cpuHtml + ramHtml + tierHtml;

  // Benefits
  const hasGpu = !!report.best_gpu;
  document.getElementById('hw-benefits').innerHTML = hasGpu ? `
    <div style="font-size:13px;color:var(--sub);margin-top:4px;">
      Enabling GPU acceleration provides:&nbsp;
      <span style="color:var(--accent)">✓ Faster responses</span> &nbsp;
      <span style="color:var(--accent)">✓ Larger models</span> &nbsp;
      <span style="color:var(--accent)">✓ Reduced CPU load</span>
    </div>` : '';
}

async function chooseMode(mode) {
  setStep(2);
  hide('screen-review'); show('screen-configuring');
  const logBox = document.getElementById('config-log');
  logBox.innerHTML = '';

  const addLog = (msg, isErr=false) => {
    const line = document.createElement('div');
    line.className = 'log-line' + (isErr ? ' err' : '');
    line.textContent = '› ' + msg;
    logBox.appendChild(line);
    logBox.scrollTop = logBox.scrollHeight;
  };

  try {
    const r = await fetch(`${API}/api/wizard/configure`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-OCBrain-Local': '1' },
      body: JSON.stringify({ mode }),
    });
    const result = await r.json();

    for (const log of result.logs || []) addLog(log);
    for (const err of result.errors || []) addLog(err, true);
    state = { ...state, ...result };

    // Show models screen
    setTimeout(() => showModels(), 800);
  } catch (e) {
    addLog('Configuration error: ' + e.message, true);
  }
}

function showModels() {
  setStep(3);
  hide('screen-configuring'); show('screen-models');

  const rec = state.recommendation;
  if (!rec) { proceedToValidation(); return; }

  document.getElementById('models-note').textContent = rec.note || 'Based on your hardware.';

  const list = document.getElementById('model-list');
  const allModels = [...(rec.primary || []), ...(rec.optional || [])];

  // Pre-select primary
  selectedModels = new Set(rec.primary?.map(m => m.name) || []);

  list.innerHTML = allModels.map(m => `
    <label class="model-item ${selectedModels.has(m.name) ? 'selected' : ''}" id="model-${m.name}">
      <input type="checkbox" ${selectedModels.has(m.name) ? 'checked' : ''}
             data-action="toggle-model" data-name="${escapeHtml(m.name)}">
      <div class="model-info">
        <div class="model-name">${m.display || m.name}</div>
        <div class="model-desc">${m.description || ''}</div>
      </div>
      <div class="model-meta">${m.disk_gb}GB disk<br>${m.vram_gb}GB VRAM</div>
    </label>`).join('');

  updateEstimates(rec);
}

function toggleModel(name, checked) {
  if (checked) selectedModels.add(name);
  else selectedModels.delete(name);
  const el = document.getElementById('model-' + name);
  if (el) el.classList.toggle('selected', checked);
}

function updateEstimates(rec) {
  const allModels = [...(rec.primary || []), ...(rec.optional || [])];
  const sel = allModels.filter(m => selectedModels.has(m.name));
  const disk = sel.reduce((s, m) => s + m.disk_gb, 0).toFixed(1);
  const ram  = sel.reduce((s, m) => s + m.vram_gb, 0).toFixed(1);
  document.getElementById('model-estimates').innerHTML =
    `Estimated disk usage: <strong>${disk} GB</strong>&nbsp; &nbsp;
     Estimated VRAM usage: <strong>${ram} GB</strong>`;
}

async function proceedToValidation() {
  setStep(4);
  hide('screen-models'); show('screen-validating');

  document.getElementById('val-results').innerHTML =
    '<div style="text-align:center;padding:24px"><div class="spinner" style="width:28px;height:28px;margin:0 auto 10px;border-width:3px;"></div><div style="font-size:13px;color:var(--sub)">Running tests...</div></div>';

  try {
    const r = await fetch(`${API}/api/wizard/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-OCBrain-Local': '1' },
      body: JSON.stringify({ models: [...selectedModels] }),
    });
    const result = await r.json();
    state = { ...state, ...result };
    renderValidation(result.validation || {});
  } catch (e) {
    document.getElementById('val-results').innerHTML =
      `<div style="color:var(--red);font-size:13px">Validation error: ${e.message}</div>`;
  }
}

function renderValidation(results) {
  const html = Object.entries(results).map(([test, status]) => {
    const isPass = status === 'PASS';
    const isFail = status.startsWith('FAIL');
    const cls = isPass ? 'val-pass' : isFail ? 'val-fail' : 'val-na';
    const icon = isPass ? '✓' : isFail ? '✗' : '–';
    return `<div class="val-row">
      <span>${test}</span>
      <span class="val-status ${cls}">${icon} ${status}</span>
    </div>`;
  }).join('');

  document.getElementById('val-results').innerHTML = html ||
    '<div style="color:var(--sub);font-size:13px;padding:10px 0">No tests ran.</div>';

  // Show complete after short delay
  setTimeout(() => {
    const allOk = Object.values(results).every(s => !s.startsWith('FAIL'));
    showComplete(allOk);
  }, 1000);
}

function showComplete(success) {
  setStep(5);
  hide('screen-validating'); show('screen-complete');
  const mode = state.chosen_mode || 'cpu';
  const profile = state.profile;
  let msg = success
    ? `Your system is configured for AI acceleration (${mode} mode).`
    : `Setup completed with some warnings. OCBrain will run in CPU mode.`;
  if (profile?.recommended_models?.length) {
    msg += ` Recommended models: ${profile.recommended_models.join(', ')}.`;
  }
  document.getElementById('complete-msg').textContent = msg;
}

function setStep(n) {
  for (let i = 0; i < 5; i++) {
    const dot = document.getElementById('dot-' + i);
    if (i < n)  dot.className = 'step-dot done';
    else if (i === n) dot.className = 'step-dot active';
    else dot.className = 'step-dot';
  }
}

function show(id) { document.getElementById(id).style.display = 'block'; }
function hide(id) { document.getElementById(id).style.display = 'none'; }

init();

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// ── Event wiring ──────────────────────────────────────────────
// No inline handlers: the page's CSP allows script from 'self' only (interface/headers.py).
document.addEventListener('click', ev => {
  const el = ev.target.closest('[data-action]');
  if (!el) return;
  if (el.dataset.action === 'choose-mode') chooseMode(el.dataset.mode);
  else if (el.dataset.action === 'proceed-validation') proceedToValidation();
});
document.addEventListener('change', ev => {
  const el = ev.target.closest('[data-action]');
  if (el && el.dataset.action === 'toggle-model') toggleModel(el.dataset.name, el.checked);
});
