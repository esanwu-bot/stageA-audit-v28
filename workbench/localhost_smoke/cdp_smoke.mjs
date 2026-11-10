// localhost UI 冒烟测试：Edge CDP 真实浏览器，不触发任何 PDF 解析。
// 采集：页面截图、Console、Network、文件选择交互、FROZEN 展示、Copy JSON 内容。
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';

const OUT = 'E:/workspace/icpdf-extractor/workbench/_smoke';
const PDF = 'E:/workspace/IcPdfParser/data/pdfs/CD4098BE-NG__cd4098b.pdf';
const URL = 'http://127.0.0.1:8765/';

function getJson(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (r) => {
      let s = '';
      r.on('data', (c) => (s += c));
      r.on('end', () => { try { resolve(JSON.parse(s)); } catch (e) { reject(e); } });
    }).on('error', reject);
  });
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  // 每次创建全新标签页，避免 CDP 重放上一次导航的 Log 事件。
  const created = await new Promise((resolve, reject) => {
    const req = http.request('http://127.0.0.1:9222/json/new?about:blank', { method: 'PUT' }, (r) => {
      let s = '';
      r.on('data', (c) => (s += c));
      r.on('end', () => { try { resolve(JSON.parse(s)); } catch (e) { reject(e); } });
    });
    req.on('error', reject);
    req.end();
  });
  const ws = new WebSocket(created.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener('open', resolve, { once: true });
    ws.addEventListener('error', reject, { once: true });
  });

  let seq = 0;
  const pending = new Map();
  const consoleEvents = [];
  const exceptions = [];
  const logEntries = [];
  const network = [];
  let loaded = false;

  ws.addEventListener('message', (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) {
      pending.get(m.id)(m);
      pending.delete(m.id);
      return;
    }
    if (!m.method) return;
    const p = m.params || {};
    if (m.method === 'Page.loadEventFired') loaded = true;
    if (m.method === 'Runtime.consoleAPICalled') {
      consoleEvents.push({ type: p.type, text: (p.args || []).map((a) => a.value ?? a.description ?? '').join(' ') });
    }
    if (m.method === 'Runtime.exceptionThrown') {
      exceptions.push(p.exceptionDetails?.text || JSON.stringify(p.exceptionDetails));
    }
    if (m.method === 'Log.entryAdded') {
      logEntries.push({ level: p.entry?.level, text: p.entry?.text, url: p.entry?.url });
    }
    if (m.method === 'Network.requestWillBeSent') {
      network.push({ phase: 'request', id: p.requestId, method: p.request?.method, url: p.request?.url });
    }
    if (m.method === 'Network.responseReceived') {
      network.push({ phase: 'response', id: p.requestId, status: p.response?.status,
                     mime: p.response?.mimeType, url: p.response?.url });
    }
    if (m.method === 'Network.loadingFailed') {
      network.push({ phase: 'failed', id: p.requestId, error: p.errorText });
    }
  });

  function send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = ++seq;
      const timer = setTimeout(() => { pending.delete(id); reject(new Error('timeout ' + method)); }, 20000);
      pending.set(id, (m) => { clearTimeout(timer); resolve(m); });
      ws.send(JSON.stringify({ id, method, params }));
    });
  }
  const evaluate = async (expression) => {
    const r = await send('Runtime.evaluate', {
      expression, returnByValue: true, awaitPromise: true,
    });
    if (r.result?.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails));
    return r.result?.result?.value;
  };
  const screenshot = async (name) => {
    const r = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
    fs.writeFileSync(path.join(OUT, name), Buffer.from(r.result.data, 'base64'));
  };

  await send('Page.enable');
  await send('Runtime.enable');
  await send('Log.enable');
  await send('Network.enable');
  await send('Page.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: URL });
  for (let i = 0; i < 40 && !loaded; i++) await sleep(150);
  await sleep(1200); // 等 /api/health 返回

  const landing = await evaluate(`({
    statusBar: document.getElementById('status-bar').textContent,
    statusClass: document.getElementById('status-bar').className,
    backendLine: document.getElementById('backend-line').textContent,
    title: document.title,
    hasMockVar: typeof mockJSON !== 'undefined',
    hasShowResultsFake: /setTimeout/.test(document.documentElement.outerHTML),
    hasLM358: /LM358|Texas Instruments|SOIC-8/.test(document.documentElement.outerHTML),
    uploadText: document.getElementById('upload-text').textContent,
    resultsVisible: getComputedStyle(document.getElementById('results-view')).display
  })`);
  await screenshot('01_landing_frozen.png');

  // 拦截 clipboard，便于校验 Copy JSON 的实际内容（不依赖真实剪贴板权限）。
  await evaluate(`(function(){
    window.__copied = null;
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: function(t){ window.__copied = t; return Promise.resolve(); } }
    });
    return true;
  })()`);

  // 真实文件选择：CDP 设置 input.files 后派发 change 事件。
  const doc = await send('DOM.getDocument', { depth: -1 });
  const q = await send('DOM.querySelector', { nodeId: doc.result.root.nodeId, selector: '#file-input' });
  await send('DOM.setFileInputFiles', { files: [PDF], nodeId: q.result.nodeId });
  // setFileInputFiles 本身可能已派发 change；只有尚未触发时才补一次，避免重复 POST。
  await sleep(600);
  const alreadyFired = await evaluate(`!!window.lastResponse`);
  if (!alreadyFired) {
    await evaluate(`document.getElementById('file-input').dispatchEvent(new Event('change', {bubbles:true}))`);
  }
  await sleep(1200);

  const afterUpload = await evaluate(`({
    uploadText: document.getElementById('upload-text').textContent,
    resultStatus: document.getElementById('result-status').textContent,
    resultClass: document.getElementById('result-status').className,
    headerTag: document.getElementById('header-tag').textContent,
    jsonHasFrozen: document.getElementById('json-display').textContent.indexOf('FROZEN') >= 0,
    jsonHasLM358: /LM358|Texas Instruments|Supply Voltage/.test(document.getElementById('json-display').textContent),
    responseStatus: window.lastResponse ? window.lastResponse.status : null,
    responseFrozen: window.lastResponse ? window.lastResponse.frozen : null,
    parsePdfCalls: window.lastResponse && window.lastResponse.diagnostics ? window.lastResponse.diagnostics.parse_pdf_calls : null,
    workerStarted: window.lastResponse && window.lastResponse.diagnostics ? window.lastResponse.diagnostics.parse_worker_started : null,
    parserOutputEmpty: window.lastResponse ? Object.keys(window.lastResponse.parser_output || {}).length === 0 : null,
    cardTitles: Array.from(document.querySelectorAll('.card h3')).map(function(e){return e.textContent;}),
    resultsVisible: getComputedStyle(document.getElementById('results-view')).display
  })`);
  await screenshot('02_results_frozen.png');

  // Copy JSON：点击按钮后比对捕获文本与后端真实响应。
  await evaluate(`document.querySelector('.btn-primary').click()`);
  await sleep(300);
  const copyCheck = await evaluate(`({
    buttonText: document.querySelector('.btn-primary').textContent,
    copiedLength: window.__copied ? window.__copied.length : null,
    copiedEqualsLastResponse: window.__copied ? window.__copied === JSON.stringify(window.lastResponse, null, 2) : null,
    copiedStatus: window.__copied ? JSON.parse(window.__copied).status : null
  })`);

  // Copy JSON 内容与 curl 取到的后端原始响应逐字段比对（允许缩进不同，不允许字段不同）。
  const copiedText = await evaluate(`window.__copied`);
  fs.writeFileSync(path.join(OUT, 'copied.json'), copiedText || '');
  const backendRaw = JSON.parse(fs.readFileSync(path.join(OUT, 'frozen_response.json'), 'utf8'));
  let copyMatchesBackend = false;
  try {
    const sortDeep = (v) => Array.isArray(v) ? v.map(sortDeep)
      : (v && typeof v === 'object') ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, sortDeep(v[k])])) : v;
    copyMatchesBackend = JSON.stringify(sortDeep(JSON.parse(copiedText)))
      === JSON.stringify(sortDeep(backendRaw));
  } catch (e) { copyMatchesBackend = false; }
  copyCheck.copyTextBytes = copiedText ? Buffer.byteLength(copiedText, 'utf8') : null;
  copyCheck.backendResponseBytes = fs.statSync(path.join(OUT, 'frozen_response.json')).size;
  copyCheck.copyMatchesBackendObject = copyMatchesBackend;

  // 拖放交互：复用 input 里已设置的真实 PDF File，走 dragover / dragleave / drop。
  const dragCheck = await evaluate(`(async function(){
    var f = document.getElementById('file-input').files[0];
    if (!f) return {ok:false, reason:'no file in input'};
    window.__dragFile = f;
    document.querySelector('.btn-ghost').click();
    var dz = document.getElementById('drop-zone');
    var dt = new DataTransfer(); dt.items.add(window.__dragFile);
    dz.dispatchEvent(new DragEvent('dragover', {bubbles:true, cancelable:true, dataTransfer:dt}));
    var dragoverClass = dz.className;
    dz.dispatchEvent(new DragEvent('dragleave', {bubbles:true, cancelable:true, dataTransfer:dt}));
    var dragleaveClass = dz.className;
    dz.dispatchEvent(new DragEvent('drop', {bubbles:true, cancelable:true, dataTransfer:dt}));
    await new Promise(function(r){ setTimeout(r, 900); });
    return {ok:true, fileName: f.name, dragoverClass: dragoverClass, dragleaveClass: dragleaveClass,
      uploadText: document.getElementById('upload-text').textContent,
      status: window.lastResponse ? window.lastResponse.status : null,
      parsePdfCalls: window.lastResponse && window.lastResponse.diagnostics ? window.lastResponse.diagnostics.parse_pdf_calls : null};
  })()`);

  const report = {
    url: URL,
    pdfSelectedButNotParsed: PDF,
    landing,
    afterUpload,
    copyCheck,
    dragCheck,
    consoleEvents,
    exceptions,
    logEntries,
    network,
    generatedAt: new Date().toISOString(),
  };
  fs.writeFileSync(path.join(OUT, 'cdp_report.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({
    landing, afterUpload, copyCheck, dragCheck,
    consoleCount: consoleEvents.length, exceptionCount: exceptions.length,
    logCount: logEntries.length, networkCount: network.length,
  }, null, 2));
  ws.close();
}

main().catch((e) => { console.error('SMOKE_FAILED', e); process.exit(1); });
