#!/usr/bin/env node
// Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import fs from 'node:fs';

const src = fs.readFileSync('web/nemoclaw/scripts/_openclaw.js', 'utf8');
const m = src.match(/export const GW_CONNECT = `([\s\S]*?)`;\n/);
if (!m) throw new Error('GW_CONNECT not found');
const code = Function('return `' + m[1].replace(/`/g, '\\`') + '`')();

const logs = [];
const storage = new Map([
  ['nemoclaw_clawrawurl', 'https://nemoclaw-v6paslvp5.brevlab.com'],
  ['nemoclaw_clawtoken', 'test-token'],
  ['nemoclaw_clawcfjwt', 'test.jwt'],
]);

globalThis.localStorage = { getItem: k => storage.get(k) || '', setItem: (k, v) => storage.set(k, String(v)) };
globalThis.location = new URL('https://course.example.test/nemoclaw/03a-kickstart.html');
const connectionSource = fs.readFileSync('web/nemoclaw/scripts/_connection.js', 'utf8');
const connection = await import('data:text/javascript;base64,' + Buffer.from(connectionSource).toString('base64'));
const opened = [];
class FakeWebSocket {
  constructor(url) {
    this.url = url;
    this.readyState = 1;
    opened.push(url);
    setTimeout(() => this.onmessage && this.onmessage({ data: JSON.stringify({ event: 'connect.challenge' }) }), 0);
  }
  send(raw) {
    const msg = JSON.parse(raw);
    if (msg.method === 'connect') {
      setTimeout(() => this.onmessage && this.onmessage({ data: JSON.stringify({
        type: 'res', id: msg.id, ok: true,
        payload: { server: { version: 'test' }, auth: { scopes: ['operator.admin'] } },
      }) }), 0);
    }
  }
  close() { this.readyState = 3; }
}
globalThis.WebSocket = FakeWebSocket;

const helpers = {
  log: msg => logs.push(String(msg)),
  fetch: async () => { throw new Error('GW_CONNECT must not probe a retired metadata route'); },
  getOpenClawConnection: () => connection.getOpenClawConnection(),
  openclawGatewayWsUrl: (raw, jwt) => connection.openclawWebSocketUrl(raw, '/cli/gateway', jwt),
  signal: null,
};
const state = {};
const fn = new Function('state', 'helpers', 'h', 'console', '"use strict"; return (async () => {\n' + code + '\n})();');
await fn(state, helpers, helpers, console);

if (opened.length !== 1) throw new Error(`expected one WebSocket, saw ${opened.length}`);
const expected = 'wss://openclaw-cors-proxy.experiments.courses.nvidia.com/https/nemoclaw-v6paslvp5.brevlab.com/cli/gateway?cf_access_jwt=test.jwt';
if (opened[0] !== expected) throw new Error(`expected hosted relay ${expected}, got ${opened[0]}`);
if (!logs.some(x => x.includes('via hosted relay'))) throw new Error('missing hosted-relay transport log');
console.log('gw connect transport audit: ok');
