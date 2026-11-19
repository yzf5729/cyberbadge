const log = document.getElementById('log');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send');
const statusEl = document.getElementById('status');
const dot = document.getElementById('dot');

let ws = null;
let retry = 0;

function add(text, cls) {
  const el = document.createElement('div');
  el.className = 'msg ' + cls;
  el.textContent = text;
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
  return el;
}

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
  ws.send(JSON.stringify({ text }));
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
connect();
