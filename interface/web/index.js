const API = '';

// ── Status polling ────────────────────────────────────────────
async function pollStatus() {
  try {
    const r = await ocFetch(`${API}/status`);
    const d = await readJsonResponse(r);
    const dot  = document.getElementById('status-dot');
    const txt  = document.getElementById('status-text');
    if (d.status === 'ok') {
      dot.style.background = '#1d9e75';
      txt.textContent = `${Object.keys(d.modules||{}).length} modules`;
    }
  } catch { document.getElementById('status-dot').style.background = '#ba7517'; }
}
setInterval(pollStatus, 5000);
pollStatus();

// ── View switching ────────────────────────────────────────────
function showView(name, btn) {
  ['chat','modules','settings'].forEach(v => {
    document.getElementById(`view-${v}`).style.display = v === name
      ? (v === 'chat' ? 'flex' : 'block') : 'none';
  });
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  if (name === 'modules') loadModules();
  if (name === 'settings') loadSettings();
}

// ── Chat ──────────────────────────────────────────────────────
let activeExecutionId = null;
let executionSnapshot = null;
let executionEvents = null;
let selectedNodeId = null;

function statusGlyph(status) {
  return {pending:'○', running:'⟳', completed:'✓', failed:'✕', stalled:'⚠',
    recovering:'↻', waiting:'⌛', blocked:'⚠', cancelled:'⊘'}[status] || '○';
}

function startInspection(executionId) {
  stopInspection();
  activeExecutionId = executionId;
  selectedNodeId = executionId;
  document.getElementById('thinking-control').classList.add('active');
  document.getElementById('thinking-label').textContent = 'Thinking...';
  executionEvents = ocEventStream(`${API}/executions/${encodeURIComponent(executionId)}/events`, async () => {
    await refreshInspection();
  });
  refreshInspection();
}

function stopInspection() {
  if (executionEvents) executionEvents.close();
  executionEvents = null;
}

async function refreshInspection() {
  if (!activeExecutionId) return;
  try {
    const r = await ocFetch(`${API}/executions/${encodeURIComponent(activeExecutionId)}`);
    if (!r.ok) return;
    executionSnapshot = await readJsonResponse(r);
    renderInspection();
  } catch {}
}

function renderInspection() {
  if (!executionSnapshot) return;
  const nodes = new Map(executionSnapshot.nodes.map(n => [n.id, n]));
  const tree = document.getElementById('task-tree');
  tree.innerHTML = '';
  function addNode(nodeId, depth) {
    const node = nodes.get(nodeId);
    if (!node) return;
    const button = document.createElement('button');
    button.className = `task-item ${selectedNodeId === node.id ? 'selected' : ''}`;
    button.dataset.depth = Math.min(depth, 1);
    button.onclick = () => { selectedNodeId = node.id; renderInspection(); };
    const status = document.createElement('span');
    status.className = `task-status status-${node.status}`;
    status.textContent = statusGlyph(node.status);
    const content = document.createElement('span');
    content.textContent = node.title || node.operation_type;
    if (node.summary) { const summary = document.createElement('span'); summary.className='task-summary'; summary.textContent=node.summary; content.appendChild(summary); }
    button.append(status, content); tree.appendChild(button);
    node.children.forEach(child => addNode(child, depth + 1));
  }
  addNode(executionSnapshot.root_id, 0);
  const selected = nodes.get(selectedNodeId) || nodes.get(executionSnapshot.root_id);
  if (selected) {
    selectedNodeId = selected.id;
    const detail = document.getElementById('task-detail');
    detail.innerHTML = `<h4>${escapeHtml(selected.title || selected.operation_type)}</h4>`;
    const rows = [['Status', selected.status], ['Action', selected.current_action || ''],
      ['Progress', formatProgress(selected)], ['Elapsed', formatElapsed(selected)],
      ['Last progress', formatLastProgress(selected)], ['Failure', selected.failure_message || ''],
      ['Recovery', selected.recovery_action || '']];
    rows.filter(row => row[1]).forEach(row => {
      const div = document.createElement('div'); div.className='detail-row';
      div.innerHTML = `<span>${escapeHtml(row[0])}</span><strong>${escapeHtml(String(row[1]))}</strong>`;
      detail.appendChild(div);
    });
    if (['completed','failed','cancelled'].includes(selected.status)) {
      document.getElementById('thinking-label').textContent = selected.status === 'completed' ? 'Complete' : 'Execution ended';
      stopInspection();
    }
  }
}

function formatProgress(node) {
  if (node.progress_units && Object.keys(node.progress_units).length) {
    const u = node.progress_units;
    if (u.completed != null && u.total != null) return `${u.completed} / ${u.total}`;
    if (u.tokens != null) return `${u.tokens} tokens`;
  }
  return node.progress == null ? '' : `${Math.round(node.progress * 100)}%`;
}
function formatElapsed(node) { return node.started_at ? `${Math.round((Date.now()/1000 - node.started_at))}s` : ''; }
function formatLastProgress(node) { return node.last_progress_at ? `${Math.max(0, Math.round(Date.now()/1000 - node.last_progress_at))}s ago` : ''; }
// The .stage-* rules in index.html. Anything else renders unstyled, as before.
const STAGE_CLASSES = ['bootstrap', 'shadow', 'native'];

function escapeHtml(value) { return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function toggleInspection() { document.getElementById('inspection').classList.toggle('open'); }
function closeInspection() { document.getElementById('inspection').classList.remove('open'); }

async function readJsonResponse(response) {
  const body = await response.text();
  if (!body.trim()) {
    throw new Error(`OCBrain returned an empty response (HTTP ${response.status}).`);
  }
  try {
    return JSON.parse(body);
  } catch {
    throw new Error(`OCBrain returned invalid JSON (HTTP ${response.status}).`);
  }
}

async function consumeQueryStream(response, message) {
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`OCBrain request failed (HTTP ${response.status})${body ? `: ${body.slice(0, 160)}` : '.'}`);
  }
  if (!response.body) throw new Error('OCBrain returned no response stream.');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let answer = '';
  let finished = false;
  while (!finished) {
    const chunk = await reader.read();
    buffer += decoder.decode(chunk.value || new Uint8Array(), {stream: !chunk.done});
    const events = buffer.split('\n\n');
    buffer = events.pop() || '';
    for (const event of events) {
      const data = event.split('\n').find(line => line.startsWith('data: '));
      if (!data) continue;
      const payload = data.slice(6);
      if (payload === '[DONE]') { finished = true; break; }
      let item;
      try { item = JSON.parse(payload); }
      catch { continue; }
      if (item.error) throw new Error(item.error);
      if (item.token) {
        answer += item.token;
        message.textContent = answer;
        document.getElementById('messages').scrollTop = document.getElementById('messages').scrollHeight;
      }
    }
    if (chunk.done) break;
  }
  if (!answer) message.textContent = 'No response.';
  return answer;
}

function addMessage(text, role, meta) {
  const box = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  // Render code blocks
  const escaped = text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  const rendered = escaped.replace(/```(\w*)\n?([\s\S]*?)```/g,
    (_,lang,code) => `<pre><code>${code.trim()}</code></pre>`);
  div.innerHTML = rendered;
  if (meta) {
    const m = document.createElement('div');
    m.className = 'msg-meta';
    m.textContent = meta;
    div.appendChild(m);
  }
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
  return div;
}

function showTyping() {
  const box = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'typing';
  div.id = 'typing-indicator';
  div.innerHTML = '<span></span><span></span><span></span>';
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function hideTyping() {
  const t = document.getElementById('typing-indicator');
  if (t) t.remove();
}

async function sendQuery() {
  const input = document.getElementById('query-input');
  const query = input.value.trim();
  if (!query) return;

  addMessage(query, 'user');
  input.value = '';
  input.style.height = '44px';

  document.getElementById('send-btn').disabled = true;
  showTyping();
  const executionId = crypto.randomUUID();
  startInspection(executionId);

  try {
    const r = await ocFetch(`${API}/query`, {
      method: 'POST',
      headers: {'Content-Type':'application/json', 'X-OCBrain-Local': '1'},
      body: JSON.stringify({ query, stream: true, execution_id: executionId }),
    });
    hideTyping();
    const message = addMessage('', 'bot');
    await consumeQueryStream(r, message);
    await refreshInspection();
  } catch (e) {
    hideTyping();
    // Show a useful error — HTTP errors have empty .message, so include status
    const msg = e.message
      ? `Error: ${e.message}`
      : `Could not reach OCBrain. Is "python main.py" still running?`;
    addMessage(msg, 'bot');
  }
  document.getElementById('send-btn').disabled = false;
}

// ── Modules ───────────────────────────────────────────────────
async function loadModules() {
  try {
    const r = await ocFetch(`${API}/modules`);
    const modules = await readJsonResponse(r);
    const grid = document.getElementById('module-grid');
    grid.innerHTML = '';
    for (const [name, info] of Object.entries(modules)) {
      const score = Math.round((info.maturity_score||0) * 100);
      const stage = info.stage || 'bootstrap';
      const stageClass = `stage-${STAGE_CLASSES.includes(stage) ? stage : 'unknown'}`;  // never raw data in a class attribute
      const card = document.createElement('div');
      card.className = 'module-card';
      card.innerHTML = `
        <div class="module-name">${escapeHtml(name)}</div>
        <div class="module-stage ${stageClass}">${escapeHtml(stage)}</div>
        <div class="progress-label">Maturity — ${score}%</div>
        <div class="progress-track"><div class="progress-fill" style="width:${score}%"></div></div>
        <div class="module-stats">
          <span>📦 ${info.kb_chunks||0} chunks</span>
          <span>🔄 ${info.query_count||0} queries</span>
        </div>
        <button data-action="train-module" data-name="${escapeHtml(name)}" style="margin-top:10px;background:none;border:1px solid var(--border);color:var(--sub);padding:4px 10px;border-radius:4px;cursor:pointer;font-size:11px;">▶ Train now</button>
      `;
      grid.appendChild(card);
    }
    const addBtn = document.createElement('div');
    addBtn.className = 'add-module-btn';
    addBtn.textContent = '+ Add custom module';
    addBtn.onclick = () => document.getElementById('new-module-modal').classList.add('open');
    grid.appendChild(addBtn);
  } catch (e) {
    document.getElementById('module-grid').innerHTML = `<div style="color:var(--sub)">${e.message}</div>`;
  }
}

async function trainModule(name) {
  if (!confirm(`Trigger training for '${name}'?`)) return;
  try {
    const r = await ocFetch(`${API}/train/${name}`, {method:'POST', headers: {'X-OCBrain-Local': '1'}});
    const d = await readJsonResponse(r);
    alert(d.result);
  } catch (e) { alert(e.message); }
}

// ── Settings ──────────────────────────────────────────────────
const SETTINGS_DEFS = [
  { key:'privacy.save_history',        label:'Save conversation history',  desc:'Store turns in context.sqlite' },
  { key:'privacy.save_training_pairs', label:'Collect training pairs',     desc:'Enable model learning from queries' },
  { key:'privacy.encrypt_context_db',  label:'Encrypt context database',   desc:'AES-256 encryption on local SQLite' },
  { key:'learning.training_enabled',   label:'Enable model training',      desc:'Master switch for all LoRA fine-tuning' },
  { key:'global.voice_enabled',        label:'Voice input',                desc:'Whisper STT via Ctrl+Shift+Space' },
];

async function loadSettings() {
  try {
    const r = await ocFetch(`${API}/config`);
    const cfg = await readJsonResponse(r);
    const list = document.getElementById('settings-list');
    list.innerHTML = '';
    for (const s of SETTINGS_DEFS) {
      const parts = s.key.split('.');
      let val = cfg;
      for (const p of parts) val = val?.[p];
      const enabled = Boolean(val);
      const row = document.createElement('div');
      row.className = 'setting-row';
      row.innerHTML = `
        <div class="setting-info">
          <div class="setting-label">${s.label}</div>
          <div class="setting-desc">${s.desc}</div>
        </div>
        <div class="toggle ${enabled ? 'on' : ''}" data-action="toggle-setting" data-key="${escapeHtml(s.key)}"></div>
      `;
      list.appendChild(row);
    }
  } catch {}
}

async function toggleSetting(key, el) {
  el.classList.toggle('on');
  const val = el.classList.contains('on');
  try {
    await ocFetch(`${API}/config`, {
      method: 'PUT',
      headers: {'Content-Type':'application/json', 'X-OCBrain-Local': '1'},
      body: JSON.stringify({ [key]: val }),
    });
  } catch {}
}

// ── New module modal ──────────────────────────────────────────
function closeModal() {
  document.getElementById('new-module-modal').classList.remove('open');
}

async function createModule() {
  const name     = document.getElementById('nm-name').value.trim();
  const desc     = document.getElementById('nm-desc').value.trim();
  const model    = document.getElementById('nm-model').value;
  const kwStr    = document.getElementById('nm-keywords').value;
  const srcStr   = document.getElementById('nm-sources').value;
  const keywords = kwStr.split(',').map(s=>s.trim()).filter(Boolean);
  const sources  = srcStr.split(',').map(s=>s.trim()).filter(Boolean);
  if (!name || !desc) { alert('Name and description are required.'); return; }
  try {
    const r = await ocFetch(`${API}/modules/new`, {
      method: 'POST',
      headers: {'Content-Type':'application/json', 'X-OCBrain-Local': '1'},
      body: JSON.stringify({ name, desc, model, keywords, sources }),
    });
    if (!r.ok) { const e = await readJsonResponse(r); throw new Error(e.detail); }
    closeModal();
    showView('modules', document.querySelectorAll('.nav-btn')[1]);
  } catch (e) { alert(`Error: ${e.message}`); }
}

document.getElementById('new-module-modal').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeModal();
});

// ── Event wiring ──────────────────────────────────────────────
// No inline handlers: the page's CSP allows script from 'self' only (interface/headers.py).
const OC_ACTIONS = {
  'show-view': el => showView(el.dataset.view, el),
  'toggle-inspection': () => toggleInspection(),
  'close-inspection': () => closeInspection(),
  'send-query': () => sendQuery(),
  'close-modal': () => closeModal(),
  'create-module': () => createModule(),
  'train-module': el => trainModule(el.dataset.name),
  'toggle-setting': el => toggleSetting(el.dataset.key, el),
};
document.addEventListener('click', ev => {
  const el = ev.target.closest('[data-action]');
  const run = el && OC_ACTIONS[el.dataset.action];
  if (run) run(el);
});
const queryInput = document.getElementById('query-input');
queryInput.addEventListener('keydown', ev => {
  if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); sendQuery(); }
});
queryInput.addEventListener('input', () => {
  queryInput.style.height = '44px';
  queryInput.style.height = Math.min(queryInput.scrollHeight, 120) + 'px';
});
