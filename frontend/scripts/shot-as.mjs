#!/usr/bin/env node
// Screenshot a signed-in page through headless Chrome (CDP). Dev aid for the patient screens.
// Usage: node shot-as.mjs <path> <out.png> <persona> <lang> [width=390] [height=844] [evalFile]
import { spawn } from 'node:child_process';
import { writeFileSync, readFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

const [path, out, persona, lang, w = '390', h = '844', evalFile] = process.argv.slice(2);
const base = process.env.BASE || 'http://localhost:5173';
const chrome = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const proc = spawn(chrome, ['--headless=new', '--remote-debugging-port=0', '--no-first-run', '--hide-scrollbars', '--disable-gpu', 'about:blank'], { stdio: ['ignore', 'ignore', 'pipe'] });
const port = await new Promise((res, rej) => {
  let buf = ''; const t = setTimeout(() => rej(new Error('no port')), 15000);
  proc.stderr.on('data', d => { buf += d; const m = buf.match(/ws:\/\/127\.0\.0\.1:(\d+)\//); if (m) { clearTimeout(t); res(m[1]); } });
});
try {
  const page = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find(p => p.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
  let id = 0; const pending = new Map(); const events = new Map();
  ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { const { res, rej } = pending.get(m.id); pending.delete(m.id); m.error ? rej(new Error(m.error.message)) : res(m.result); } else if (m.method && events.has(m.method)) events.get(m.method)(m.params); };
  const send = (method, params = {}) => new Promise((res, rej) => { pending.set(++id, { res, rej }); ws.send(JSON.stringify({ id, method, params })); });
  const load = async url => { const l = new Promise(r => events.set('Page.loadEventFired', () => r())); await send('Page.navigate', { url }); await Promise.race([l, new Promise(r => setTimeout(r, 20000))]); };
  const ev = async expression => (await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })).result.value;
  await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: +w, height: +h, deviceScaleFactor: 2, mobile: +w < 500 });
  await load(base + '/');
  await ev(`(async()=>{const j=await fetch('/api/auth/guest',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({persona:'${persona}'})}).then(r=>r.json());sessionStorage.setItem('halqa.token',j.token);sessionStorage.setItem('halqa.user',JSON.stringify(j.user));localStorage.setItem('halqa.lang','${lang}');})()`);
  await load(base + '/' + path.replace(/^.*Git\//, '').replace(/^\/+/, ''));
  await new Promise(r => setTimeout(r, 2500));
  if (evalFile) { const r = await ev(readFileSync(evalFile, 'utf8')); if (r !== undefined) console.log(JSON.stringify(r)); await new Promise(r => setTimeout(r, 800)); }
  const over = await ev(`({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth,wide:[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>document.documentElement.clientWidth+1).slice(0,5).map(e=>e.tagName+'.'+String(e.className).slice(0,40))})`);
  console.log('overflow', JSON.stringify(over));
  const { data } = await send('Page.captureScreenshot', { format: 'png' });
  mkdirSync(dirname(resolve(out)), { recursive: true }); writeFileSync(out, Buffer.from(data, 'base64'));
  console.log('saved', out); ws.close();
} finally { proc.kill(); }
