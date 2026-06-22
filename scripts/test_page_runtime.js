#!/usr/bin/env node
// Runtime test for browser course pages via playwright-core in the openclaw container.
// Run from the HOST (not inside the container):
//   docker cp test_page_runtime.js <stack>-task1-openclaw-1:/tmp/
//   docker exec \
//     -e CLAW_URL=http://localhost:8995 -e CLAW_TOKEN=dli-openclaw-token \
//     <stack>-task1-openclaw-1 node /tmp/test_page_runtime.js [url]
// Default URL: http://nginx/lab/static/nemoclaw/01a-loop.html
//
// Credentials: set CLAW_URL + CLAW_TOKEN to drive the OpenClaw gateway nodes
// (03a/03c/04a). They are injected into sessionStorage under the keys the pages
// read (nemoclaw_clawrawurl / _clawtoken) before any script runs, so
// the Connect nodes succeed against the local gateway instead of stalling on the
// "fill in the probe" guard.
//
// WebSocket monitoring: every /cli/gateway frame is parsed. The run is only
// considered to exercise the agent loop if event:"agent" tool/command frames
// actually arrive. A green page with zero tool frames is reported as a WARN,
// because that is exactly the silent-failure mode this harness exists to catch.
//
// Deps (one-time, inside openclaw):
//   apt-get install -y libglib2.0-0 libnspr4 libnss3 libatk1.0-0 libatk-bridge2.0-0 \
//     libcups2 libdrm2 libgbm1 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
//     libxrandr2 libxext6 libx11-6 libpangocairo-1.0-0 libasound2t64 fonts-liberation
//   PLAYWRIGHT_BROWSERS_PATH=/tmp/pw-browsers \
//     npx playwright install chromium-headless-shell

const fs = require('fs');
const pw = require('/usr/lib/node_modules/openclaw/node_modules/playwright-core');

const url = process.argv[2] || 'http://nginx/lab/static/nemoclaw/01a-loop.html';
const CLAW_URL = process.env.CLAW_URL || '';
const CLAW_TOKEN = process.env.CLAW_TOKEN || '';

// Locate the chromium-headless-shell binary.
// The install path moves between playwright versions, so glob the known roots instead of hardcoding one.
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
      if (!d.startsWith('chromium_headless_shell')) continue;
      const bin = `${root}/${d}/chrome-headless-shell-linux64/chrome-headless-shell`;
      if (fs.existsSync(bin)) return bin;
    }
  }
  return null;
}

(async () => {
  const executablePath = findChrome();
  if (!executablePath) {
    console.error('FATAL: chrome-headless-shell not found. Install with:');
    console.error('  PLAYWRIGHT_BROWSERS_PATH=/tmp/pw-browsers npx playwright install chromium-headless-shell');
    process.exit(1);
  }
  console.log('CHROME:', executablePath);

  const browser = await pw.chromium.launch({ headless: true, executablePath, args: ['--no-sandbox'] });
  const page = await browser.newPage();

  // Local-test only: the gateway's controlUi.allowedOrigins won't contain the
  // origin nginx serves the page from (http://nginx), so the WS handshake is
  // rejected with "origin not allowed". On the real interface the page is served
  // from an allowed origin, so this never triggers. CLAW_ORIGIN lets the harness
  // present an allowlisted Origin (e.g. http://localhost:8088) for the handshake.
  if (process.env.CLAW_ORIGIN) {
    await page.setExtraHTTPHeaders({ Origin: process.env.CLAW_ORIGIN });
    console.log('ORIGIN: overridden ->', process.env.CLAW_ORIGIN);
  }

  const errors = [];
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
  page.on('pageerror', err => errors.push('PAGE_ERROR: ' + err.message));
  if (process.env.DEBUG_WS) {
    page.on('console', msg => console.log('  [console.' + msg.type() + ']', msg.text()));
    page.on('websocket', s => console.log('  [ws.open]', s.url()));
  }

  // ── WebSocket frame monitoring ──────────────────────────────────────────────
  // Tally gateway frames by kind. Tool/command frames are the signal that the
  // agent loop actually ran; their absence is the bug this harness guards.
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

  // For a remote *.brevlab.com launchable, the browser needs the CF_Authorization
  // cookie to clear Cloudflare Access before the WS upgrade. Set it for the
  // launchable host (derived from CLAW_URL) so the headless browser authenticates
  // exactly like a logged-in student.
  if (process.env.CLAW_CF && CLAW_URL) {
    try {
      const host = new URL(CLAW_URL).hostname;
      // SameSite=None + Secure so the browser sends it on the cross-site wss
      // upgrade (the page origin differs from the launchable). A Lax cookie is
      // withheld cross-site and CF 302s the handshake, so no challenge arrives.
      await page.context().addCookies([{ name: 'CF_Authorization', value: process.env.CLAW_CF, domain: host, path: '/', secure: true, sameSite: 'None' }]);
      console.log('CF_COOKIE: set for', host);
    } catch (e) { console.log('CF_COOKIE: skipped (' + e.message + ')'); }
  }

  // Model endpoint: the released course is "direct + your nvapi- key" out in the
  // wild, but the lab ships a keyless LLM proxy at /lab/svc/llm. Pre-seed getConfig's cache
  // (CONFIG_KEY = __nv_slim_cfg_v1) to point at it, so this harness can actually
  // run model cells (helpers.chat / ChatOpenAI / createReactAgent) without a
  // student key. We are validating the cell LOGIC, namely tool calls, loops, and agents,
  // not the production auth path. Set before any page script reads the config.
  await page.addInitScript(() => {
    try {
      sessionStorage.setItem("__nv_slim_cfg_v1", JSON.stringify({
        mode: "proxy", url: "/lab/svc/llm/v1",
        model: "nvidia/nemotron-3-nano-30b-a3b", needsKey: false,
      }));
    } catch (_) {}
  });

  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 });
  await page.waitForTimeout(2000);

  // Inject gateway credentials AFTER the probe widget mounts. The widget rewrites
  // the token key to "" on mount, so an addInitScript value gets clobbered; set
  // the keys here, after it has settled and before we click Run.
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

  // Click "Run all" on every canvas flow. Each flow runs its nodes sequentially
  // (connect → … → chat) on a shared state, so this drives the full handshake.
  const flowCount = await page.evaluate(() => {
    const btns = document.querySelectorAll('.cf-btn-run');
    btns.forEach(b => b.click());
    return btns.length;
  });
  console.log('FLOWS:', flowCount);

  // Settle: agent runs that call tools take longer than plain LLM calls, and the
  // chat node's own timeout is 90s, so allow up to 120s.
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
  const hardFail = errors.length > 0 || nodeErr || !settled;
  // If credentials were supplied, the run should have produced tool frames.
  const expectedTools = !!(CLAW_URL && CLAW_TOKEN);
  const toolsMissing = expectedTools && ws.toolStarts.length === 0 && ws.cmdEnds.length === 0;

  if (hardFail) console.log('RESULT: FAIL (errors / unsettled nodes)');
  else if (toolsMissing) console.log('RESULT: WARN (page green but NO tool/command frames, so the agent loop was not observed)');
  else console.log('RESULT: PASS' + (expectedTools ? ` (${ws.toolStarts.length} tool starts, ${ws.cmdEnds.length} command ends)` : ''));

  await browser.close();
  process.exit(hardFail ? 1 : 0);
})().catch(e => { console.error('FATAL:', e.message); process.exit(1); });
