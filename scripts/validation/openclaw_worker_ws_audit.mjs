#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const root = process.cwd();
const sourcePath = path.join(root, 'cors-proxy/cors-proxy-worker-openclaw.js');
const source = fs.readFileSync(sourcePath, 'utf8');
const tmpPath = path.join(os.tmpdir(), `openclaw-worker-${process.pid}.mjs`);
fs.writeFileSync(tmpPath, source, 'utf8');

function fail(message) {
  console.error(message);
  process.exit(1);
}

try {
  const worker = (await import(pathToFileURL(tmpPath).href)).default;
  const calls = [];
  const wsMarker = { accepted: true };
  globalThis.fetch = async (target, init = {}) => {
    const headers = Object.fromEntries(new Headers(init.headers).entries());
    calls.push({ target, method: init.method, headers, redirect: init.redirect });
    const upstream = new Response(null, { status: 200 });
    Object.defineProperty(upstream, 'webSocket', { value: wsMarker });
    return upstream;
  };

  const req = new Request('https://openclaw-cors-proxy.test/https/nemoclaw-v6paslvp5.brevlab.com/cli/gateway?cf_access_jwt=test.jwt&keep=1', {
    method: 'GET',
    headers: { Upgrade: 'websocket', Origin: 'https://vkudlay.gitlab-master-pages.nvidia.com' },
  });
  const res = await worker.fetch(req, {});
  if (res.webSocket !== wsMarker) fail('worker did not return upstream WebSocket response directly');
  if (calls.length !== 1) fail(`expected one upstream fetch, saw ${calls.length}`);
  const call = calls[0];
  if (call.target !== 'https://nemoclaw-v6paslvp5.brevlab.com/cli/gateway?keep=1') fail(`bad upstream target: ${call.target}`);
  if (call.headers.cookie !== 'CF_Authorization=test.jwt') fail(`missing CF_Authorization cookie: ${JSON.stringify(call.headers)}`);
  if (call.headers.origin !== 'http://localhost:8088') fail(`bad pinned Origin: ${call.headers.origin}`);
  if (call.redirect !== 'manual') fail(`WS fetch should use manual redirect, got ${call.redirect}`);

  console.log('openclaw worker ws audit: ok');
} finally {
  try { fs.unlinkSync(tmpPath); } catch {}
}
