#!/usr/bin/env node
// Browser runtime harness. Host entrypoint: scripts/runtime/lab_runtime_test.sh [--smoke] [url].
// Set CLAW_URL + CLAW_TOKEN to exercise OpenClaw gateway nodes.
// With OpenClaw credentials, zero tool frames is a hard failure.

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
const gatewayOnly = args.includes('--gateway-only');
const serveStatic = args.includes('--serve-static');
const DEFAULT_LAB_URL = 'http://nginx/lab/static/nemoclaw/01a-loop.html';
const STATIC_SERVER_URL = 'http://127.0.0.1:4173';
const LOOPBACK_ORIGIN = 'http:' + '//127.0.0.1';
const url = args.find(a => a !== '--smoke' && a !== '--render-only' && a !== '--gateway-only' && a !== '--serve-static') || DEFAULT_LAB_URL;
const CLAW_URL = process.env.CLAW_URL || '';
let CLAW_TOKEN = process.env.CLAW_TOKEN || '';
const CLAW_CF = process.env.CLAW_CF || '';
const NVIDIA_API_KEY = process.env.NVIDIA_API_KEY || '';
const DIRECT_API_URL = process.env.NVIDIA_API_URL || 'https://integrate.api.nvidia.com/v1';
const OPENCLAW_CORS_PROXY_BASE = 'https://openclaw-cors-proxy.experiments.courses.nvidia.com';
const OPENCLAW_BACKUP_HINT = 'Use backup OpenClaw: set CLAW_URL=https://nemoclaw-<id>.brevlab.com CLAW_TOKEN=<gateway token> CLAW_CF=<CF_Authorization>. If local OpenClaw shows EPERM, stop local probing and use the Brev session URL plus CF_Authorization.';

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


function withTimeout(ms) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(new Error(`timeout after ${ms}ms`)), ms);
  return { signal: controller.signal, done: () => clearTimeout(timer) };
}

function joinUrl(base, pathPart) {
  return base.replace(/\/+$/, '') + pathPart;
}

function openClawHttpUrl(pathPart) {
  const direct = joinUrl(CLAW_URL, pathPart);
  if (!CLAW_CF) return direct;
  try {
    const upstream = new URL(CLAW_URL);
    if (!/(^|\.)brevlab\.com$/i.test(upstream.hostname)) return direct;
    const proxy = new URL(OPENCLAW_CORS_PROXY_BASE);
    const upstreamPath = upstream.pathname.replace(/\/+$/, '');
    proxy.pathname = `/https/${upstream.host}${upstreamPath}${pathPart}`;
    return proxy.href;
  } catch (_) {
    return direct;
  }
}

function gatewayTokenFromDashboardUrl(raw) {
  if (!raw) return '';
  try {
    const parsed = new URL(String(raw), 'https://nemoclaw.invalid/');
    const fragment = new URLSearchParams(parsed.hash.replace(/^#/, ''));
    return fragment.get('token') || parsed.searchParams.get('token') || '';
  } catch (_) {
    return '';
  }
}

async function resolveOpenClawToken() {
  if (CLAW_TOKEN || !(CLAW_URL && CLAW_CF)) return;
  const timeout = withTimeout(8000);
  try {
    const resp = await fetch(openClawHttpUrl('/api/agent'), {
      headers: { Accept: 'application/json, text/plain, */*', 'CF-Access-Jwt-Assertion': CLAW_CF },
      signal: timeout.signal,
    });
    const body = await resp.text();
    let discovered = '';
    try { discovered = gatewayTokenFromDashboardUrl(JSON.parse(body)?.agent?.dashboardUrl); } catch (_) {}
    if (resp.ok && discovered) {
      CLAW_TOKEN = discovered;
      console.log('OPENCLAW_TOKEN: discovered from /api/agent');
    } else {
      console.log('OPENCLAW_TOKEN: not discovered from /api/agent (' + resp.status + ')');
    }
  } catch (e) {
    console.log('OPENCLAW_TOKEN: discovery failed (' + (e && e.message ? e.message : String(e)) + ')');
  } finally {
    timeout.done();
  }
}

async function preflightOpenClaw() {
  await resolveOpenClawToken();
  if (!(CLAW_URL && CLAW_TOKEN)) return;
  const headers = { Accept: 'application/json, text/plain, */*', Authorization: `Bearer ${CLAW_TOKEN}` };
  if (CLAW_CF) headers['CF-Access-Jwt-Assertion'] = CLAW_CF;
  const targets = ['/health', '/healthz', '/api/agent'];
  const attempts = [];
  for (const pathPart of targets) {
    const timeout = withTimeout(6000);
    const target = openClawHttpUrl(pathPart);
    try {
      const resp = await fetch(target, { headers, signal: timeout.signal });
      attempts.push(`${resp.status} ${target}`);
      if (resp.ok || [401, 403].includes(resp.status)) {
        console.log('OPENCLAW_PREFLIGHT:', attempts.join(' | '));
        return;
      }
    } catch (e) {
      attempts.push(`${target} -> ${e && e.message ? e.message : String(e)}`);
    } finally {
      timeout.done();
    }
  }
  throw new Error(`OpenClaw preflight failed. ${attempts.join(' | ')}. ${OPENCLAW_BACKUP_HINT}`);
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

  if (!smoke && !renderOnly) await preflightOpenClaw();

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
  if (CLAW_CF && CLAW_URL) {
    try {
      const host = new URL(CLAW_URL).hostname;
      // SameSite=None + Secure so the browser sends it on the cross-site wss upgrade (the page origin differs from the launchable).
      // A Lax cookie is withheld cross-site and CF 302s the handshake, so no challenge arrives.
      await page.context().addCookies([{ name: 'CF_Authorization', value: CLAW_CF, domain: host, path: '/', secure: true, sameSite: 'None' }]);
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
      const textStartsCode = el => /^code\b/i.test((el.textContent || '').trim());
      return {
        title: title.trim(),
        heading: heading.trim(),
        hasMain: !!main,
        flows: document.querySelectorAll('.cf-btn-run').length,
        panels: document.querySelectorAll('.cf-panel').length,
        runCells: document.querySelectorAll('.rc-card').length,
        unifiedButtons: document.querySelectorAll('.cell-btn').length,
        unifiedLangChips: document.querySelectorAll('.cell-lang-chip').length,
        uglyCellButtons: document.querySelectorAll('.rc-run:not(.cell-btn),.rc-reset:not(.cell-btn),.cf-panel-runone:not(.cell-btn),.cf-panel-reset:not(.cell-btn)').length,
        plainCodeLabels: Array.from(document.querySelectorAll('.rc-code-det > summary,.cf-panel-code-det > summary')).filter(textStartsCode).length,
        codeBlocks: document.querySelectorAll('pre code, pre').length,
      };
    });
    console.log('PAGE_INFO:', JSON.stringify(pageInfo, null, 2));
    console.log('PAGE_ERRORS:', JSON.stringify(errors));
    console.log('RESOURCE_ERRORS:', JSON.stringify(resourceErrors));
    const significantResourceErrors = resourceErrors.filter(x => !/favicon\.ico/.test(x) && !/integrate\.api\.nvidia\.com\/v1\/models/.test(x));
    const fail = errors.length > 0 || significantResourceErrors.length > 0 || !pageInfo.hasMain
      || pageInfo.uglyCellButtons > 0 || pageInfo.plainCodeLabels > 0;
    console.log(fail ? 'RESULT: FAIL (render errors)' : 'RESULT: PASS (static render)');
    await browser.close();
    if (staticServer) staticServer.close();
    process.exit(fail ? 1 : 0);
  }

  if (gatewayOnly) {
    if (!(CLAW_URL && CLAW_CF)) {
      throw new Error('--gateway-only requires CLAW_URL and CLAW_CF');
    }
    const result = await page.evaluate(async ({ clawUrl, cfJwt, proxyBase }) => {
      const output = {
        httpStatus: 0,
        token: false,
        viaProxy: false,
        challenge: false,
        connect: false,
        rpc: false,
        error: '',
      };
      try {
        const mod = await import(new URL('./scripts/_shared.js', location.href).href);
        const upstream = new URL(clawUrl);
        const gateway = mod.openclawGatewayWsUrl(clawUrl, cfJwt, proxyBase);
        output.viaProxy = gateway.viaProxy;
        if (!gateway.viaProxy) throw new Error('course helper did not select hosted relay');
        const proxy = new URL(proxyBase);
        proxy.pathname = `/https/${upstream.host}${upstream.pathname.replace(/\/+$/, '')}/api/agent`;
        const response = await fetch(proxy, {
          headers: { Accept: 'application/json', 'CF-Access-Jwt-Assertion': cfJwt },
        });
        output.httpStatus = response.status;
        if (!response.ok) throw new Error(`agent metadata returned HTTP ${response.status}`);
        const token = mod.gatewayTokenFromAgentMetadata(await response.json());
        output.token = !!token;
        if (!token) throw new Error('agent metadata omitted a gateway token');

        await new Promise((resolve, reject) => {
          const socket = new WebSocket(gateway.url);
          const timer = setTimeout(() => reject(new Error('gateway check timed out')), 20000);
          const finish = error => {
            clearTimeout(timer);
            try { socket.close(); } catch (_) {}
            error ? reject(error) : resolve();
          };
          socket.onerror = () => finish(new Error('gateway WebSocket error'));
          socket.onmessage = event => {
            let data;
            try { data = JSON.parse(event.data); } catch (_) { return; }
            if (data.event === 'connect.challenge') {
              output.challenge = true;
              socket.send(JSON.stringify({
                type: 'req', id: 'browser-connect', method: 'connect',
                params: {
                  minProtocol: 4, maxProtocol: 4,
                  client: { id: 'openclaw-control-ui', version: '0.1.0', platform: 'browser', mode: 'webchat' },
                  caps: ['tool-events'], role: 'operator',
                  scopes: ['operator.read', 'operator.write', 'operator.admin'],
                  auth: { token },
                },
              }));
              return;
            }
            if (data.type !== 'res') return;
            if (data.id === 'browser-connect') {
              if (!data.ok) return finish(new Error(data.error?.message || 'gateway connect rejected'));
              output.connect = true;
              socket.send(JSON.stringify({ type: 'req', id: 'browser-rpc', method: 'models.list', params: {} }));
              return;
            }
            if (data.id === 'browser-rpc') {
              if (!data.ok) return finish(new Error(data.error?.message || 'gateway RPC rejected'));
              output.rpc = true;
              finish();
            }
          };
        });
      } catch (error) {
        output.error = error?.message || String(error);
      }
      return output;
    }, { clawUrl: CLAW_URL, cfJwt: CLAW_CF, proxyBase: OPENCLAW_CORS_PROXY_BASE });
    console.log('GATEWAY_CHECK:', JSON.stringify(result));
    const passed = result.httpStatus === 200 && result.token && result.viaProxy
      && result.challenge && result.connect && result.rpc && !result.error;
    console.log(passed ? 'RESULT: PASS (hosted OpenClaw relay)' : 'RESULT: FAIL (hosted OpenClaw relay)');
    await browser.close();
    if (staticServer) staticServer.close();
    process.exit(passed ? 0 : 1);
  }

  // Inject credentials after the probe widget mounts, or it clears them.
  if (CLAW_URL && CLAW_TOKEN) {
    await page.evaluate(([u, t, cf]) => {
      localStorage.setItem('nemoclaw_clawrawurl', u);
      localStorage.setItem('nemoclaw_clawurl', u);
      localStorage.setItem('nemoclaw_clawtoken', t);
      if (cf) localStorage.setItem('nemoclaw_clawcfjwt', cf);
    }, [CLAW_URL, CLAW_TOKEN, CLAW_CF]);
    console.log('CREDS: injected', CLAW_URL, CLAW_CF ? '(CF JWT stored for gateway proxy)' : '');
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
  else if (toolsMissing) console.log('RESULT: FAIL (OpenClaw credentials supplied but NO tool/command frames observed). ' + OPENCLAW_BACKUP_HINT);
  else console.log('RESULT: PASS' + (expectedTools ? ` (${ws.toolStarts.length} tool starts, ${ws.cmdEnds.length} command ends)` : ''));

  await browser.close();
  if (staticServer) staticServer.close();
  process.exit((hardFail || toolsMissing) ? 1 : 0);
})().catch(e => { console.error('FATAL:', e.message); process.exit(1); });
