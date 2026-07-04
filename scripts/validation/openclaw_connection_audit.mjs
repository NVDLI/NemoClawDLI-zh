#!/usr/bin/env node
import fs from 'node:fs';

const storage = new Map();
globalThis.localStorage = {
  getItem: key => storage.get(key) || null,
  setItem: (key, value) => storage.set(key, String(value)),
  removeItem: key => storage.delete(key),
};
globalThis.location = new URL('https://course.example.test/nemoclaw/03a-kickstart.html');

const source = fs.readFileSync('web/nemoclaw/scripts/_connection.js', 'utf8');
const mod = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const approved = 'https://openclaw-cors-proxy.experiments.courses.nvidia.com';
const launchable = 'https://nemoclaw-test123.brevlab.com';
const retired = 'https://retired-personal-relay.' + 'workers.dev/https/nemoclaw-test123.brevlab.com';

function ok(condition, message) {
  if (!condition) throw new Error(message);
}

ok(mod.getOpenClawProxyConfig().enabled, 'hosted relay must default enabled');
ok(mod.getOpenClawProxyConfig().base === approved, 'hosted relay default drifted');

let rejected = false;
try { mod.normalizeOpenClawProxyBase('https://personal.' + 'workers.dev'); }
catch (_) { rejected = true; }
ok(rejected, 'personal worker relay was accepted');

storage.delete('nemoclaw_clawrawurl');
storage.set('nemoclaw_clawurl', retired);
const migration = mod.migrateOpenClawConnectionStorage();
ok(migration.rawUrl === launchable, `retired relay did not unwrap: ${migration.rawUrl}`);
ok(storage.get('nemoclaw_clawrawurl') === launchable, 'raw launchable URL was not healed');
ok(storage.get('nemoclaw_clawurl') === approved + '/https/nemoclaw-test123.brevlab.com',
  'healed effective URL does not use approved relay');
ok(!storage.get('nemoclaw_clawurl').includes('workers.dev'), 'retired relay survived migration');

const registered = mod.setOpenClawConnection({
  rawUrl: launchable,
  token: 'test-token',
  accessJwt: 'test.jwt',
});
const reread = mod.getOpenClawConnection();
ok(registered.rawUrl === launchable && reread.rawUrl === launchable,
  'OpenClaw registry did not preserve the launchable URL');
ok(reread.effectiveUrl === approved + '/https/nemoclaw-test123.brevlab.com',
  'OpenClaw registry did not derive the approved relay URL');
ok(reread.token === 'test-token' && reread.accessJwt === 'test.jwt',
  'OpenClaw registry did not preserve credentials');

const http = mod.openclawHttpUrl(launchable, '/api/agent');
ok(http.viaProxy && http.url === approved + '/https/nemoclaw-test123.brevlab.com/api/agent',
  `cross-origin HTTP route bypassed relay: ${http.url}`);
const ws = mod.openclawWebSocketUrl(launchable, '/cli/gateway', 'test.jwt');
ok(ws.viaProxy && ws.url === 'wss://openclaw-cors-proxy.experiments.courses.nvidia.com/https/nemoclaw-test123.brevlab.com/cli/gateway?cf_access_jwt=test.jwt',
  `cross-origin WebSocket route bypassed relay: ${ws.url}`);
ok(ws.displayUrl.includes('cf_access_jwt=...') && !ws.displayUrl.includes('test.jwt'),
  'display URL exposes access assertion');

mod.setOpenClawProxyConfig({ enabled: false });
const direct = mod.openclawWebSocketUrl(launchable, '/cli/gateway', 'test.jwt');
ok(!direct.viaProxy && direct.url === 'wss://nemoclaw-test123.brevlab.com/cli/gateway',
  `relay toggle did not select direct route: ${direct.url}`);

mod.setOpenClawProxyConfig({ enabled: true });
globalThis.location = new URL(launchable + '/course/03a-kickstart.html');
const sameOrigin = mod.openclawWebSocketUrl(launchable, '/cli/gateway', 'test.jwt');
ok(!sameOrigin.viaProxy, 'same-origin vendored course must bypass relay');

const openshell = fs.readFileSync('web/nemoclaw/scripts/_openshell.js', 'utf8');
ok(openshell.includes('openclawWebSocketUrl(rawUrl, "/ws/terminal?cmd="'),
  'terminal helper bypasses shared launchable routing');
ok(openshell.includes('[direct.url, routed.url]') && openshell.includes('{ enabled: false, base: "" }'),
  'terminal helper lost authenticated direct-first routing with relay fallback');
const openclaw = fs.readFileSync('web/nemoclaw/scripts/_openclaw.js', 'utf8');
ok(openclaw.includes('if (route.viaProxy && cfJwt) headers["CF-Access-Jwt-Assertion"] = cfJwt;'),
  'direct HTTP mode sends the relay-only Access assertion');
ok(openclaw.includes('getOpenClawConnection()') && openclaw.includes('setOpenClawConnection({'),
  'OpenClaw widgets bypass the shared connection registry');
for (const path of [
  'web/nemoclaw/04b-modern-clis.html',
  'i18n/pt/web/nemoclaw/04b-modern-clis.html',
  'i18n/es/web/nemoclaw/04b-modern-clis.html',
]) {
  const page = fs.readFileSync(path, 'utf8');
  ok(page.includes('helpers.openclawGatewayWsUrl(c.rawUrl, c.accessJwt).url'), `${path} bypasses shared gateway routing`);
  ok(!page.includes('return u + "/cli/gateway"'), `${path} rebuilt a direct gateway URL`);
}

storage.clear();
globalThis.location = new URL('https://course.example.test/nemoclaw/03a-kickstart.html?' + new URLSearchParams({
  openclaw_url: launchable,
  openclaw_proxy: '0',
  openclaw_proxy_base: 'https://relay.example.test',
}));
const queryMod = await import('data:text/javascript;base64,' + Buffer.from(source + '\n// query-prefill-fixture').toString('base64'));
ok(storage.get('nemoclaw_clawrawurl') === launchable, 'openclaw_url query prefill was ignored');
ok(queryMod.getOpenClawProxyConfig().enabled === false, 'openclaw_proxy=0 query prefill was ignored');
ok(queryMod.getOpenClawProxyConfig().base === 'https://relay.example.test',
  'openclaw_proxy_base query prefill was ignored');

console.log('openclaw connection audit: ok');
