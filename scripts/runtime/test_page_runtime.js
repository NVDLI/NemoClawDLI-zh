#!/usr/bin/env node
// Browser runtime harness. Host entrypoint: scripts/runtime/lab_runtime_test.sh [--smoke] [url].
// Set CLAW_URL + CLAW_TOKEN to exercise OpenClaw gateway nodes.
// A green page with zero tool frames reports WARN, not PASS.

const fs = require('fs');
const http = require('http');
const path = require('path');
let pw;
try {
  pw = require('/usr/lib/node_modules/openclaw/node_modules/playwright-core');
} catch (_) {
  pw = require('playwright-core');
}

const args = process.argv.slice(2);
const smoke = args.includes('--smoke');
const renderOnly = args.includes('--render-only');
const serveStatic = args.includes('--serve-static');
const DEFAULT_LAB_URL = 'http://nginx/lab/static/nemoclaw/01a-loop.html';
const STATIC_SERVER_URL = 'http://127.0.0.1:4173';
const LOOPBACK_ORIGIN = 'http:' + '//127.0.0.1';
const url = args.find(a => a !== '--smoke' && a !== '--render-only' && a !== '--serve-static') || DEFAULT_LAB_URL;
const CLAW_URL = process.env.CLAW_URL || '';
const CLAW_TOKEN = process.env.CLAW_TOKEN || '';
const NVIDIA_API_KEY = process.env.NVIDIA_API_KEY || '';
const DIRECT_API_URL = process.env.NVIDIA_API_URL || 'https://integrate.api.nvidia.com/v1';

// Locate the chromium-headless-shell binary.
// The install path moves between playwright versions, so glob the known roots instead of hardcoding one.
function contentType(file) {
  if (/\.html?$/.test(file)) return 'text/html; charset=utf-8';
  if (/\.m?js$/.test(file)) return 'text/javascript; charset=utf-8';
  if (/\.css$/.test(file)) return 'text/css; charset=utf-8';
  if (/\.json$/.test(file)) return 'application/json; charset=utf-8';
  if (/\.svg$/.test(file)) return 'image/svg+xml';
  if (/\.png$/.test(file)) return 'image/png';
  if (/\.jpe?g$/.test(file)) return 'image/jpeg';
  if (/\.webp$/.test(file)) return 'image/webp';
  return 'application/octet-stream';
}

function startStaticServer() {
  const roots = ['/workspace/web', '/workspace'];
  const server = http.createServer((req, res) => {
    try {
      const parsed = new URL(req.url, LOOPBACK_ORIGIN);
      let rel = decodeURIComponent(parsed.pathname);
      if (rel.startsWith('/lab/static/')) rel = rel.slice('/lab/static/'.length);
      else rel = rel.replace(/^\/+/, '');
      if (!rel || rel.endsWith('/')) rel += 'index.html';
      for (const root of roots) {
        const candidate = path.resolve(root, rel);
        if (!candidate.startsWith(root + path.sep) && candidate !== root) continue;
        if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
          res.writeHead(200, { 'Content-Type': contentType(candidate) });
          fs.createReadStream(candidate).pipe(res);
          return;
        }
      }
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('not found');
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end(e.message);
    }
  });
  return new Promise(resolve => {
    server.listen(4173, '127.0.0.1', () => resolve(server));
  });
}

function findChrome() {
  if (process.env.CHROME_BIN && fs.existsSync(process.env.CHROME_BIN)) return process.env.CHROME_BIN;
  const roots = [
    process.env.PLAYWRIGHT_BROWSERS_PATH || '/tmp/pw-browsers',
    '/sandbox/.cache/ms-playwright',
    `${process.env.HOME || '/root'}/.cache/ms-playwright`,
  ];
  for (const root of roots) {
    let dirs = [];
    try { dirs = fs.readdirSync(root); } catch { continue; }
    for (const d of dirs) {
      const candidates = [
        `${root}/${d}/chrome-headless-shell-linux64/chrome-headless-shell`,
        `${root}/${d}/chrome-linux/chrome`,
        `${root}/${d}/chrome-linux64/chrome`,
      ];
      for (const bin of candidates) if (fs.existsSync(bin)) return bin;
    }
  }
  for (const bin of ['/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome']) {
    if (fs.existsSync(bin)) return bin;
  }
  return null;
}

(async () => {
  let staticServer = null;
  if (serveStatic) {
    staticServer = await startStaticServer();
    console.log('STATIC_SERVER: ' + STATIC_SERVER_URL);
  }

  const executablePath = findChrome();
  if (!executablePath) {
    console.error('FATAL: chrome-headless-shell not found. Install with:');
    console.error('  PLAYWRIGHT_BROWSERS_PATH=/tmp/pw-browsers npx playwright install chromium-headless-shell');
    process.exit(1);
  }
  console.log('CHROME:', executablePath || 'playwright default');

  const launchOptions = { headless: true, args: ['--no-sandbox'] };
  if (executablePath) launchOptions.executablePath = executablePath;
  const browser = await pw.chromium.launch(launchOptions);
  const page = await browser.newPage();

  await page.route('**/*', route => {
    const reqUrl = route.request().url();
    try {
      const host = new URL(reqUrl).hostname;
      if (/^(cdnjs\.cloudflare\.com|cdn\.jsdelivr\.net|unpkg\.com)$/.test(host)) {
        if (/\.css(?:$|\?)/.test(reqUrl)) {
          return route.fulfill({ status: 200, contentType: 'text/css', body: '' });
        }
        if (/highlight\.min\.js/.test(reqUrl)) {
          return route.fulfill({ status: 200, contentType: 'text/javascript', body: 'window.hljs={highlightAll(){},highlightElement(){},highlight(){return {value:""}}};' });
        }
        if (/codemirror\.min\.js/.test(reqUrl)) {
          return route.fulfill({ status: 200, contentType: 'text/javascript', body: 'window.CodeMirror={fromTextArea(){return {setValue(){},getValue(){return ""},on(){},refresh(){},setSize(){}}}};' });
        }
        return route.fulfill({ status: 200, contentType: 'text/javascript', body: '' });
      }
    } catch (_) {}
    return route.continue();
  });

  if (smoke) {
    await page.goto('data:text/html,<main id="ok">lab runtime smoke</main>');
    const ok = await page.textContent('#ok');
    console.log('SMOKE_TEXT:', ok);
    console.log('RESULT: PASS (node + playwright + chromium runtime)');
    await browser.close();
    if (staticServer) staticServer.close();
    process.exit(0);
  }

  // Local harness may need an allowlisted Origin for gateway WS handshakes.
  if (process.env.CLAW_ORIGIN) {
    await page.setExtraHTTPHeaders({ Origin: process.env.CLAW_ORIGIN });
    console.log('ORIGIN: overridden ->', process.env.CLAW_ORIGIN);
  }

  const errors = [];
  const resourceErrors = [];
  page.on('console', msg => {
    if (msg.type() !== 'error') return;
    const text = msg.text();
    if (/^Failed to load resource:/.test(text)) return;
    if (/integrate\.api\.nvidia\.com\/v1\/models/.test(text)) return;
    errors.push(text);
  });
  page.on('pageerror', err => errors.push('PAGE_ERROR: ' + err.message));
  page.on('requestfailed', req => {
    const failure = req.failure();
    resourceErrors.push(`FAILED ${req.url()} ${failure ? failure.errorText : ''}`.trim());
  });
  page.on('response', resp => {
    if (resp.status() >= 400) resourceErrors.push(`${resp.status()} ${resp.url()}`);
  });
  if (process.env.DEBUG_WS) {
    page.on('console', msg => console.log('  [console.' + msg.type() + ']', msg.text()));
    page.on('websocket', s => console.log('  [ws.open]', s.url()));
  }

  // Gateway frame counts prove the agent loop actually ran.
  const ws = { sockets: 0, allFrames: 0, evtKinds: {}, resErr: [], agentFrames: 0, toolStarts: [], cmdEnds: [], chatFinals: 0, errors: 0 };
  page.on('websocket', sock => {
    if (!/\/cli\/gateway/.test(sock.url())) return;
    ws.sockets++;
    sock.on('framereceived', f => {
      ws.allFrames++;
      let d; try { d = JSON.parse(typeof f.payload === 'string' ? f.payload : f.payload.toString()); } catch { return; }
      if (d.type === 'res' && d.ok === false) { ws.errors++; ws.resErr.push((d.error && d.error.message) || '?'); }
      if (d.event) ws.evtKinds[d.event] = (ws.evtKinds[d.event] || 0) + 1;
      if (d.type !== 'event') return;
      if (d.event === 'chat' && d.payload && d.payload.state === 'final') ws.chatFinals++;
      if (d.event !== 'agent') return;
      ws.agentFrames++;
      const data = (d.payload && d.payload.data) || {};
      const iid = data.itemId || '';
      if (iid.startsWith('tool:') && data.phase === 'start') ws.toolStarts.push(data.name || 'tool');
      else if (iid.startsWith('command:') && data.phase === 'end' && 'exitCode' in data)
        ws.cmdEnds.push({ exit: data.exitCode, ms: data.durationMs });
    });
  });

  // For a remote *.brevlab.com launchable, the browser needs the CF_Authorization cookie to clear Cloudflare Access before the WS upgrade.
  // Set it for the launchable host (derived from CLAW_URL) so the headless browser authenticates exactly like a logged-in student.
  if (process.env.CLAW_CF && CLAW_URL) {
    try {
      const host = new URL(CLAW_URL).hostname;
      // SameSite=None + Secure so the browser sends it on the cross-site wss upgrade (the page origin differs from the launchable).
      // A Lax cookie is withheld cross-site and CF 302s the handshake, so no challenge arrives.
      await page.context().addCookies([{ name: 'CF_Authorization', value: process.env.CLAW_CF, domain: host, path: '/', secure: true, sameSite: 'None' }]);
      console.log('CF_COOKIE: set for', host);
    } catch (e) { console.log('CF_COOKIE: skipped (' + e.message + ')'); }
  }

  // The web course is remote-service-only: browser pages call integrate.api.nvidia.com directly with the learner's nvapi key.
  // The harness mirrors that path.
  await page.addInitScript(({ apiKey, apiUrl }) => {
    try {
      sessionStorage.setItem("__nv_slim_cfg_v1", JSON.stringify({
        mode: "direct", url: apiUrl,
        model: "nvidia/nemotron-3-nano-30b-a3b", needsKey: true, iframeProxy: false,
      }));
      if (apiKey) localStorage.setItem("nvapi", apiKey);
    } catch (_) {}
  }, { apiKey: NVIDIA_API_KEY, apiUrl: DIRECT_API_URL });

  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 });
  await page.waitForTimeout(2000);

  if (renderOnly) {
    const pageInfo = await page.evaluate(() => {
      const main = document.querySelector('main');
      const title = document.title || '';
      const heading = (document.querySelector('h1') || document.querySelector('h2') || {}).textContent || '';
      return {
        title: title.trim(),
        heading: heading.trim(),
        hasMain: !!main,
        flows: document.querySelectorAll('.cf-btn-run').length,
        panels: document.querySelectorAll('.cf-panel').length,
        codeBlocks: document.querySelectorAll('pre code, pre').length,
      };
    });
    console.log('PAGE_INFO:', JSON.stringify(pageInfo, null, 2));
    console.log('PAGE_ERRORS:', JSON.stringify(errors));
    console.log('RESOURCE_ERRORS:', JSON.stringify(resourceErrors));
    const significantResourceErrors = resourceErrors.filter(x => !/favicon\.ico/.test(x) && !/integrate\.api\.nvidia\.com\/v1\/models/.test(x));
    const fail = errors.length > 0 || significantResourceErrors.length > 0 || !pageInfo.hasMain;
    console.log(fail ? 'RESULT: FAIL (render errors)' : 'RESULT: PASS (static render)');
    await browser.close();
    if (staticServer) staticServer.close();
    process.exit(fail ? 1 : 0);
  }

  // Inject credentials after the probe widget mounts, or it clears them.
  if (CLAW_URL && CLAW_TOKEN) {
    await page.evaluate(([u, t]) => {
      sessionStorage.setItem('nemoclaw_clawrawurl', u);
      sessionStorage.setItem('nemoclaw_clawurl', u);
      sessionStorage.setItem('nemoclaw_clawtoken', t);
    }, [CLAW_URL, CLAW_TOKEN]);
    console.log('CREDS: injected', CLAW_URL);
  } else {
    console.log('CREDS: none (gateway nodes will short-circuit on the probe guard)');
  }

  // Click "Run all" on every canvas flow.
  // Each flow runs its nodes sequentially (connect → … → chat) on a shared state, so this drives the full handshake.
  const flowCount = await page.evaluate(() => {
    const btns = document.querySelectorAll('.cf-btn-run');
    btns.forEach(b => b.click());
    return btns.length;
  });
  console.log('FLOWS:', flowCount);

  // Settle: agent runs that call tools take longer than plain LLM calls, and the chat node's own timeout is 90s, so allow up to 120s.
  let settled = false;
  for (let i = 0; i < 240; i++) {
    await page.waitForTimeout(500);
    settled = await page.evaluate(() => document.querySelectorAll('.cf-panel.cf-running').length === 0);
    if (settled) break;
  }
  console.log('SETTLED:', settled);

  // Per-node status: error text + how many <details> blocks rendered (tool trace).
  const nodeStatus = await page.evaluate(() => {
    const result = {};
    document.querySelectorAll('[data-id].cf-panel').forEach(p => {
      const errEl = p.querySelector('.cf-panel-error');
      const outEl = p.querySelector('.cf-panel-log');
      result[p.dataset.id] = {
        error: errEl ? errEl.textContent.trim().slice(0, 200) : null,
        details: p.querySelectorAll('details').length,
        log: outEl ? outEl.textContent.trim().slice(0, 300) : null,
      };
    });
    return result;
  });

  console.log('PAGE_ERRORS:', JSON.stringify(errors));
  console.log('NODE_STATUS:', JSON.stringify(nodeStatus, null, 2));
  console.log('WS_STATS:', JSON.stringify(ws, null, 2));

  const nodeErr = Object.values(nodeStatus).some(v => v.error);
  const noFlows = flowCount === 0;
  const hardFail = errors.length > 0 || nodeErr || !settled || noFlows;
  // If credentials were supplied, the run should have produced tool frames.
  const expectedTools = !!(CLAW_URL && CLAW_TOKEN);
  const toolsMissing = expectedTools && ws.toolStarts.length === 0 && ws.cmdEnds.length === 0;

  if (hardFail) console.log('RESULT: FAIL (errors / unsettled nodes / no flows)');
  else if (toolsMissing) console.log('RESULT: WARN (page green but NO tool/command frames, so the agent loop was not observed)');
  else console.log('RESULT: PASS' + (expectedTools ? ` (${ws.toolStarts.length} tool starts, ${ws.cmdEnds.length} command ends)` : ''));

  await browser.close();
  if (staticServer) staticServer.close();
  process.exit(hardFail ? 1 : 0);
})().catch(e => { console.error('FATAL:', e.message); process.exit(1); });
