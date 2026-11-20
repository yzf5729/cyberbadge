const viewsEl = document.getElementById('views');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send');
const statusEl = document.getElementById('status');
const dot = document.getElementById('dot');
const modal = document.getElementById('modal');
const modalBody = document.getElementById('modal-body');
const sModal = document.getElementById('smodal');
const sList = document.getElementById('session-list');
const effortSel = document.getElementById('effort');
const setModal = document.getElementById('setmodal');
const chipsEl = document.getElementById('chips');
const fileInput = document.getElementById('file-input');
const setMsg = document.getElementById('set-msg');

// ---------- 访问令牌 ----------
const qs = new URLSearchParams(location.search);
let TOKEN = qs.get('token') || localStorage.getItem('cb_token') || '';
if (qs.get('token')) {
  localStorage.setItem('cb_token', qs.get('token'));
  history.replaceState({}, '', location.pathname);
}
function api(path, opts = {}) {
  opts.headers = { ...(opts.headers || {}), ...(TOKEN ? { Authorization: 'Bearer ' + TOKEN } : {}) };
  return fetch(path, opts);
}

let ws = null;
let retry = 0;
let agents = [];
let activeAgent = 'builtin';
let sessions = [];
let currentSession = null;
let lastAssistantEl = null;
let pending = [];

// ---------- agent 视图 ----------

function ensureView(id) {
  let v = viewsEl.querySelector(`[data-agent="${id}"]`);
  if (v) return v;
  v = document.createElement('main');
  v.className = 'chat-view';
  v.dataset.agent = id;
  const a = agents.find((x) => x.id === id);
  if (a && a.demo) {
    const note = document.createElement('div');
    note.className = 'note';
    note.textContent = '模拟演示：这是假回复，用于预览远程 agent 的界面与切换效果。';
    v.appendChild(note);
  }
  if (a && a.kind === 'remote' && !a.demo) {
    const p = document.createElement('div');
    p.className = 'placeholder';
    p.textContent = `「${a.name}」远程接入将在 v1.5 上线。`;
    if (a.url) {
      const link = document.createElement('a');
      link.href = a.url; link.target = '_blank'; link.rel = 'noopener';
      link.textContent = '打开完整 WebUI ↗';
      p.append(document.createElement('br'), link);
    }
    v.appendChild(p);
  }
  viewsEl.appendChild(v);
  return v;
}

function showView(id) {
  viewsEl.querySelectorAll('.chat-view').forEach((v) => v.classList.toggle('active', v.dataset.agent === id));
}

function add(text, cls, atts) {
  const v = ensureView(activeAgent);
  const el = document.createElement('div');
  el.className = 'msg ' + cls;
  if (text) {
    const t = document.createElement('div');
    t.textContent = text;
    el.appendChild(t);
  }
  if (atts && atts.length) {
    const box = document.createElement('div');
    box.className = 'att-box';
    for (const a of atts) {
      if (a.kind === 'image' && a.url) {
        const img = document.createElement('img');
        img.className = 'thumb';
        img.src = a.url;
        img.alt = a.name || '图片';
        img.onclick = () => window.open(a.url, '_blank');
        box.appendChild(img);
      } else {
        const tag = document.createElement('span');
        tag.className = 'att-file';
        tag.textContent = '📄 ' + (a.name || '文件');
        box.appendChild(tag);
      }
    }
    el.appendChild(box);
  }
  v.appendChild(el);
  v.scrollTop = v.scrollHeight;
  lastAssistantEl = cls === 'assistant' ? el : lastAssistantEl;
  return el;
}

// ---------- 会话 ----------

async function loadSessions() {
  try {
    const r = await api('/api/sessions');
    sessions = (await r.json()).sessions || [];
    if (!currentSession && sessions.length) currentSession = sessions[0].id;
    renderSessions();
  } catch (e) { /* ignore */ }
}

function renderSessions() {
  sList.innerHTML = '';
  for (const s of sessions) {
    const item = document.createElement('div');
    item.className = 'session-row' + (s.id === currentSession ? ' active' : '');
    const t = document.createElement('span');
    t.className = 't';
    t.textContent = s.title;
    item.appendChild(t);
    const del = document.createElement('button');
    del.className = 'session-del';
    del.textContent = '🗑';
    del.title = '删除会话';
    del.onclick = async (e) => {
      e.stopPropagation();
      if (!confirm(`删除「${s.title}」？`)) return;
      await api('/api/sessions/' + s.id, { method: 'DELETE' });
      if (currentSession === s.id) currentSession = null;
      await loadSessions();
      await selectSession(currentSession || (sessions[0] && sessions[0].id));
    };
    item.appendChild(del);
    item.onclick = () => { selectSession(s.id); sModal.classList.remove('open'); };
    sList.appendChild(item);
  }
}

async function selectSession(sid) {
  currentSession = sid || null;
  const v = ensureView(activeAgent);
  v.innerHTML = '';
  if (sid) {
    try {
      const r = await api(`/api/sessions/${sid}/messages`);
      const msgs = (await r.json()).messages || [];
      for (const m of msgs) add(m.content, m.role === 'user' ? 'user' : 'assistant', (m.meta && m.meta.attachments) || []);
    } catch (e) { /* ignore */ }
  }
  renderSessions();
}

async function newSession() {
  const r = await api('/api/sessions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  const s = await r.json();
  sessions.unshift(s);
  currentSession = s.id;
  renderSessions();
  await selectSession(s.id);
  sModal.classList.remove('open');
}

document.getElementById('sessions-btn').onclick = () => { renderSessions(); sModal.classList.add('open'); };
document.getElementById('new-session').onclick = newSession;
document.getElementById('smodal-close').onclick = () => sModal.classList.remove('open');
sModal.addEventListener('click', (e) => { if (e.target === sModal) sModal.classList.remove('open'); });

// ---------- 头像条 ----------

async function loadAgents() {
  try {
    const r = await api('/api/agents');
    agents = (await r.json()).agents || [];
    for (const a of agents) ensureView(a.id);
    renderAgents();
  } catch (e) { /* ignore */ }
}

function renderAgents() {
  const bar = document.getElementById('agents');
  bar.innerHTML = '';
  for (const a of agents) {
    const btn = document.createElement('button');
    btn.className = 'agent ' + a.status + (a.id === activeAgent ? ' active' : '');
    btn.title = `${a.name} · ${a.status}${a.demo ? '（模拟）' : ''}`;
    btn.onclick = () => selectAgent(a);
    const ava = document.createElement('span');
    ava.className = 'ava';
    ava.textContent = a.icon || '🤖';
    const name = document.createElement('span');
    name.textContent = a.name;
    btn.append(ava, name);
    bar.appendChild(btn);
  }
}

function selectAgent(a) {
  if (a.id === activeAgent) { openAgentInfo(a); return; }
  activeAgent = a.id;
  showView(a.id);
  renderAgents();
  statusEl.textContent = `当前：${a.name}`;
}

// ---------- 信息弹窗 ----------

async function openAgentInfo(a) {
  const rows = [
    ['名称', a.name],
    ['ID', a.id],
    ['类型', a.kind === 'local' ? '本地（胸牌）' : (a.demo ? '远程（模拟演示）' : '远程')],
    ['状态', { online: '在线', busy: '忙碌', offline: '离线' }[a.status] || a.status],
    ['地址', a.url || '—'],
    ['能力', (a.capabilities || []).join('、') || '—'],
    ['最近心跳', a.last_seen ? new Date(a.last_seen * 1000).toLocaleString() : '—'],
  ];
  modalBody.innerHTML = '';
  for (const [k, v] of rows) {
    const row = document.createElement('div');
    row.className = 'info-row';
    const kEl = document.createElement('span'); kEl.className = 'k'; kEl.textContent = k;
    const vEl = document.createElement('span'); vEl.className = 'v'; vEl.textContent = v;
    row.append(kEl, vEl);
    modalBody.appendChild(row);
  }

  if (a.kind === 'local') {
    const btn = document.createElement('button');
    btn.className = 'info-btn';
    btn.textContent = '重载 .env 配置';
    btn.onclick = async () => {
      btn.disabled = true; btn.textContent = '重载中…';
      try {
        const d = await (await api('/api/reload', { method: 'POST' })).json();
        btn.textContent = `已重载：${d.model}`;
      } catch (e) { btn.textContent = '重载失败'; }
      setTimeout(() => { btn.disabled = false; btn.textContent = '重载 .env 配置'; }, 2500);
    };
    modalBody.appendChild(btn);

    const head = document.createElement('div');
    head.className = 'info-sub';
    head.textContent = '技能';
    modalBody.appendChild(head);
    try {
      const data = await (await api('/api/skills')).json();
      for (const s of data.skills || []) {
        const row = document.createElement('div');
        row.className = 'skill-row';
        const n = document.createElement('span');
        n.textContent = s.title || s.name;
        const tg = document.createElement('input');
        tg.type = 'checkbox'; tg.checked = !!s.enabled;
        tg.onchange = () => api(`/api/skills/${encodeURIComponent(s.name)}/toggle`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: tg.checked }),
        });
        row.append(n, tg);
        modalBody.appendChild(row);
      }
    } catch (e) { /* ignore */ }
  }

  if (a.url) {
    const link = document.createElement('a');
    link.className = 'info-link';
    link.href = a.url; link.target = '_blank'; link.rel = 'noopener';
    link.textContent = '打开完整 WebUI ↗';
    modalBody.appendChild(link);
  }
  modal.classList.add('open');
}

function closeModal() { modal.classList.remove('open'); }
document.getElementById('modal-close').onclick = closeModal;
modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') { closeModal(); sModal.classList.remove('open'); }
});

// ---------- 上传 ----------

function renderChips() {
  chipsEl.innerHTML = '';
  for (let i = 0; i < pending.length; i++) {
    const a = pending[i];
    const chip = document.createElement('span');
    chip.className = 'chip';
    chip.textContent = (a.kind === 'image' ? '🖼 ' : '📄 ') + a.name;
    const x = document.createElement('button');
    x.textContent = '✕';
    x.onclick = () => { pending.splice(i, 1); renderChips(); };
    chip.appendChild(x);
    chipsEl.appendChild(chip);
  }
}

async function uploadFiles(fileList) {
  for (const f of fileList) {
    if (f.size > 32 * 1024 * 1024) { statusEl.textContent = `${f.name} 超过 32MB`; continue; }
    const fd = new FormData();
    fd.append('file', f);
    if (currentSession) fd.append('session_id', currentSession);
    statusEl.textContent = `上传 ${f.name}…`;
    try {
      const r = await api('/api/upload', { method: 'POST', body: fd });
      const d = await r.json();
      if (!r.ok) { statusEl.textContent = d.error || '上传失败'; continue; }
      pending.push(d);
      renderChips();
      statusEl.textContent = '已连接';
    } catch (e) { statusEl.textContent = '上传失败'; }
  }
}

document.getElementById('attach-btn').onclick = () => fileInput.click();
fileInput.onchange = () => { uploadFiles(fileInput.files); fileInput.value = ''; };

// ---------- 设置 ----------

async function openSettings() {
  setMsg.textContent = '';
  try {
    const d = await (await api('/api/settings')).json();
    document.getElementById('set-model').value = d.model || '';
    document.getElementById('set-effort').value = d.effort || '';
    document.getElementById('set-key').textContent = d.key_set ? '已配置' : '未配置（演示模式）';
    document.getElementById('set-token').textContent = d.token_masked || '—';
    document.getElementById('set-workdir').textContent = d.workdir || '—';
  } catch (e) { setMsg.textContent = '读取设置失败'; }
  setModal.classList.add('open');
}

document.getElementById('settings-btn').onclick = openSettings;
document.getElementById('set-close').onclick = () => setModal.classList.remove('open');
setModal.addEventListener('click', (e) => { if (e.target === setModal) setModal.classList.remove('open'); });

document.getElementById('set-save').onclick = async () => {
  const model = document.getElementById('set-model').value.trim();
  const effort = document.getElementById('set-effort').value;
  try {
    const r = await api('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, effort }) });
    const d = await r.json();
    setMsg.textContent = `已保存：${d.model || '默认'}${d.effort ? ' · ' + d.effort : ''}`;
    effortSel.value = effort;
  } catch (e) { setMsg.textContent = '保存失败'; }
};

document.getElementById('set-reload').onclick = async () => {
  setMsg.textContent = '重载中…';
  try {
    const d = await (await api('/api/reload', { method: 'POST' })).json();
    setMsg.textContent = `已重载：${d.model}`;
  } catch (e) { setMsg.textContent = '重载失败'; }
};

document.getElementById('set-rotate').onclick = async () => {
  if (!confirm('轮换后当前所有设备都需要重新用新令牌打开，继续？')) return;
  try {
    const d = await (await api('/api/settings/token/rotate', { method: 'POST' })).json();
    if (!d.token) { setMsg.textContent = '轮换失败'; return; }
    TOKEN = d.token;
    localStorage.setItem('cb_token', TOKEN);
    if (ws) ws.close();
    connect();
    setMsg.textContent = '令牌已轮换（已自动重连）';
  } catch (e) { setMsg.textContent = '轮换失败'; }
};

// ---------- WebSocket ----------

function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(TOKEN)}`);
  ws.onopen = () => { retry = 0; dot.className = 'dot on'; statusEl.textContent = '已连接'; loadSessions(); };
  ws.onclose = () => {
    dot.className = 'dot off'; statusEl.textContent = '已断开，重连中…';
    setTimeout(connect, Math.min(10000, 800 * 2 ** retry++));
  };
  ws.onerror = () => ws.close();
  ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    if (data.type === 'assistant') { add(data.text, 'assistant'); setTimeout(loadSessions, 600); }
    else if (data.type === 'tool') add(`⚙ 调用 ${data.name} ${JSON.stringify(data.args)}`, 'note');
    else if (data.type === 'tool_result') add(`↳ ${data.name}: ${data.text}`, 'note');
  };
}

async function send() {
  const text = input.value.trim();
  const atts = pending.slice();
  if (!text && !atts.length) return;
  if (!ws || ws.readyState !== WebSocket.OPEN) { statusEl.textContent = '尚未连接'; return; }
  if (!currentSession) {
    const r = await api('/api/sessions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    const s = await r.json();
    sessions.unshift(s); currentSession = s.id; renderSessions();
  }
  add(text, 'user', atts);
  ws.send(JSON.stringify({ text, agent: activeAgent, session_id: currentSession,
                           effort: effortSel.value, attachments: atts }));
  input.value = '';
  input.style.height = 'auto';
  pending = [];
  renderChips();
}

sendBtn.onclick = send;
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
});
input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = Math.min(120, input.scrollHeight) + 'px';
});

if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js');
ensureView('builtin');
showView('builtin');
loadAgents();
loadSessions();
connect();
setInterval(loadAgents, 15000);
