const API = '';
let cfg = {};

const DEFS = {
  privacy: [
    { key: 'privacy.save_history',        label: 'Save conversation history',   desc: 'Store turns in context.sqlite for multi-turn memory', type: 'toggle' },
    { key: 'privacy.save_training_pairs', label: 'Collect training pairs',       desc: 'Save query/answer pairs to train your own models', type: 'toggle' },
    { key: 'privacy.encrypt_context_db',  label: 'Encrypt context database',     desc: 'AES-256 encryption on context.sqlite (requires password on startup)', type: 'toggle' },
    { key: 'privacy.telemetry',           label: 'Anonymous telemetry',          desc: 'Send anonymous usage stats (no queries, no content)', type: 'toggle' },
  ],
  learning: [
    { key: 'learning.training_enabled',   label: 'Enable model training',        desc: 'Master switch — disables all LoRA fine-tuning', type: 'toggle' },
    { key: 'learning.crawl_interval_h',   label: 'Crawl interval (hours)',       desc: 'How often to fetch new content from trusted sources', type: 'number' },
    { key: 'learning.clean_interval_h',   label: 'Clean interval (hours)',       desc: 'How often to process and embed raw crawled content', type: 'number' },
    { key: 'learning.train_interval_h',   label: 'Training interval (hours)',    desc: 'How often to run a LoRA fine-tuning cycle', type: 'number' },
    { key: 'learning.min_pairs_to_train', label: 'Min pairs before training',    desc: 'Minimum query/answer pairs collected before first training run', type: 'number' },
    { key: 'learning.replay_ratio',       label: 'Replay ratio (0.0–1.0)',       desc: 'Fraction of previous pairs mixed in each training run (prevents forgetting)', type: 'number' },
  ],
  global: [
    { key: 'global.voice_enabled',        label: 'Voice input',                  desc: 'Enable speech-to-text via Ctrl+Shift+Space (requires Whisper)', type: 'toggle' },
    { key: 'global.fanout_on_ambiguity',  label: 'Fan-out on ambiguous queries', desc: 'When unsure, query all relevant modules instead of asking for clarification', type: 'toggle' },
    { key: 'global.confidence_floor',     label: 'Confidence floor (0.0–1.0)',   desc: 'Minimum classifier confidence required before routing to a module', type: 'number' },
    { key: 'global.context_window',       label: 'Context window (turns)',       desc: 'Number of previous conversation turns sent to the model as context', type: 'number' },
    { key: 'global.web_ui_port',          label: 'Web UI port',                  desc: 'Port for the local web interface (requires restart)', type: 'number' },
    { key: 'global.ollama_host',          label: 'Ollama host URL',              desc: 'Address of your Ollama instance', type: 'text' },
    { key: 'global.response_style',       label: 'Response style',               desc: 'Default verbosity of model responses', type: 'select',
      options: ['concise', 'detailed', 'technical'] },
    { key: 'global.log_level',            label: 'Log level',                    desc: 'Verbosity of server logs', type: 'select',
      options: ['DEBUG', 'INFO', 'WARNING', 'ERROR'] },
  ],
};

function getVal(key) {
  const parts = key.split('.');
  let v = cfg;
  for (const p of parts) v = v?.[p];
  return v;
}

function renderSection(title, defs) {
  const rows = defs.map(d => {
    const val = getVal(d.key);
    if (d.type === 'toggle') {
      const on = Boolean(val);
      return `<div class="setting-row">
        <div class="setting-info">
          <div class="setting-label">${d.label}</div>
          <div class="setting-desc">${d.desc}</div>
        </div>
        <div class="toggle ${on ? 'on' : ''}" data-key="${d.key}" data-action="toggle"></div>
      </div>`;
    }
    if (d.type === 'select') {
      const opts = d.options.map(o =>
        `<option value="${o}" ${o === val ? 'selected' : ''}>${o}</option>`
      ).join('');
      return `<div class="input-row">
        <div class="input-label">${d.label}</div>
        <select data-key="${d.key}" data-dirty><option value="">--</option>${opts}</select>
      </div>`;
    }
    return `<div class="input-row">
      <div class="input-label">${d.label}</div>
      <input type="${d.type === 'number' ? 'number' : 'text'}" value="${val ?? ''}"
             data-key="${d.key}" data-dirty step="${d.type === 'number' && String(val).includes('.') ? '0.05' : '1'}">
    </div>`;
  }).join('');

  return `<div class="section-title">${title}</div><div class="card">${rows}</div>`;
}

async function load() {
  try {
    const r = await ocFetch(`${API}/config`);
    cfg = await r.json();
    const c = document.getElementById('settings-container');
    c.innerHTML =
      renderSection('Privacy', DEFS.privacy) +
      renderSection('Learning & Training', DEFS.learning) +
      renderSection('General', DEFS.global) +
      `<div class="section-title">Danger Zone</div>
       <div class="card" style="padding:16px">
         <div style="font-size:13px; color:var(--sub); margin-bottom:10px;">
           These actions cannot be undone.
         </div>
         <button class="danger-btn" data-action="wipe-pairs">
           🗑 Wipe all training pairs
         </button>
       </div>
       <button class="save-btn" id="save-btn" data-action="save-all" disabled>Save Changes</button>`;
  } catch (e) {
    document.getElementById('settings-container').textContent = 'Could not load settings — is OCBrain running?';
  }
}

let dirty = false;
function markDirty() {
  dirty = true;
  const btn = document.getElementById('save-btn');
  if (btn) btn.disabled = false;
}

function toggleSetting(el) {
  el.classList.toggle('on');
  markDirty();
}

async function saveAll() {
  const updates = {};
  document.querySelectorAll('[data-key]').forEach(el => {
    const key = el.dataset.key;
    let val;
    if (el.classList.contains('toggle')) {
      val = el.classList.contains('on');
    } else if (el.tagName === 'SELECT') {
      val = el.value;
    } else {
      val = el.type === 'number' ? parseFloat(el.value) : el.value;
    }
    updates[key] = val;
  });

  try {
    await ocFetch(`${API}/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'X-OCBrain-Local': '1' },
      body: JSON.stringify(updates),
    });
    const toast = document.getElementById('toast');
    toast.style.display = 'block';
    setTimeout(() => toast.style.display = 'none', 2500);
    dirty = false;
    document.getElementById('save-btn').disabled = true;
  } catch (e) {
    alert('Failed to save: ' + e.message);
  }
}

async function wipePairs() {
  try {
    await ocFetch(`${API}/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'X-OCBrain-Local': '1' },
      body: JSON.stringify({ 'privacy.save_training_pairs': false }),
    });
    alert('Training pairs wiped (privacy flag set to false).');
  } catch (e) { alert(e.message); }
}

window.addEventListener('beforeunload', e => {
  if (dirty) e.preventDefault();
});

load();

// ── Event wiring ──────────────────────────────────────────────
// No inline handlers: the page's CSP allows script from 'self' only (interface/headers.py).
const OC_ACTIONS = {
  'toggle': el => toggleSetting(el),
  'wipe-pairs': () => { if (confirm('Wipe all training data?')) wipePairs(); },
  'save-all': () => saveAll(),
};
document.addEventListener('click', ev => {
  const el = ev.target.closest('[data-action]');
  const run = el && OC_ACTIONS[el.dataset.action];
  if (run) run(el);
});
for (const type of ['input', 'change']) {
  document.addEventListener(type, ev => {
    if (ev.target.closest('[data-dirty]')) markDirty();
  });
}
