const viewsEl = document.getElementById('views');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send');
const statusEl = document.getElementById('status');
const dot = document.getElementById('dot');
const modal = document.getElementById('modal');
const modalBody = document.getElementById('modal-body');

let ws = null;
let retry = 0;
let agents = [];
let activeAgent = 'builtin';

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
      link.href = a.url;
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = '打开完整 WebUI ↗';
      p.append(document.createElement('br'), link);
    }
    v.appendChild(p);
  }
  viewsEl.appendChild(v);
  return v;
}

function showView(id) {
  viewsEl.querySelectorAll('.chat-view').forEach((v) => {
    v.classList.toggle('active', v.dataset.agent === id);
  });
}

function add(text, cls) {
  const v = ensureView(activeAgent);
  const el = document.createElement('div');
  el.className = 'msg ' + cls;
  el.textContent = text;
  v.appendChild(el);
  v.scrollTop = v.scrollHeight;
  return el;
}

// ---------- 头像条 ----------

async function loadAgents() {
  try {
    const r = await fetch('/api/agents');
    const data = await r.json();
    agents = data.agents || [];
    for (const a of agents) ensureView(a.id);
    renderAgents();
  } catch (e) { /* 离线时保持旧头像 */ }
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

// ---------- 基本信息弹窗 ----------

function openAgentInfo(a) {
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
    const kEl = document.createElement('span');
    kEl.className = 'k';
    kEl.textContent = k;
    const vEl = document.createElement('span');
    vEl.className = 'v';
    vEl.textContent = v;
    row.append(kEl, vEl);
    modalBody.appendChild(row);
  }
  if (a.kind === 'local') {
    const btn = document.createElement('button');
    btn.className = 'info-btn';
    btn.textContent = '重载 .env 配置';
    btn.onclick = async () => {
      btn.disabled = true;
      btn.textContent = '重载中…';
      try {
        const r = await fetch('/api/reload', { method: 'POST' });
        const d = await r.json();
        btn.textContent = `已重载：${d.model}`;
      } catch (e) { btn.textContent = '重载失败'; }
      setTimeout(() => { btn.disabled = false; btn.textContent = '重载 .env 配置'; }, 2500);
    };
    modalBody.appendChild(btn);
  }
  if (a.url) {
    const link = document.createElement('a');
    link.className = 'info-link';
    link.href = a.url;
    link.target = '_blank';
    link.rel = 'noopener';
    link.textContent = '打开完整 WebUI ↗';
    modalBody.appendChild(link);
  }
  modal.classList.add('open');
}

function closeModal() { modal.classList.remove('open'); }
document.getElementById('modal-close').onclick = closeModal;
modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });

// ---------- WebSocket ----------

function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => { retry = 0; dot.className = 'dot on'; statusEl.textContent = '已连接'; };
  ws.onclose = () => {
    dot.className = 'dot off'; statusEl.textContent = '已断开，重连中…';
    setTimeout(connect, Math.min(10000, 800 * 2 ** retry++));
  };
  ws.onerror = () => ws.close();
  ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    if (data.type === 'assistant') add(data.text, 'assistant');
    else if (data.type === 'tool') add(`⚙ 调用 ${data.name} ${JSON.stringify(data.args)}`, 'note');
    else if (data.type === 'tool_result') add(`↳ ${data.name}: ${data.text}`, 'note');
  };
}

function send() {
  const text = input.value.trim();
  if (!text) return;
  if (!ws || ws.readyState !== WebSocket.OPEN) { statusEl.textContent = '尚未连接'; return; }
  add(text, 'user');
  ws.send(JSON.stringify({ text, agent: activeAgent }));
  input.value = '';
  input.style.height = 'auto';
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
setInterval(loadAgents, 15000);
connect();
