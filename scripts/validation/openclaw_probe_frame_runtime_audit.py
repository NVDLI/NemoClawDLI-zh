#!/usr/bin/env python3
"""Exercise the OpenClaw probe HTML-frame lifecycle in a real browser.

The probe may render an HTML response in a sandboxed iframe. Every later non-HTML,
network-error, Cloudflare-login, remount, or reload path must remove that response from
the learner's visible state. Run against both source ``web`` and a built Pages root.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

for _p in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
    if (_p / "scripts" / "_bootstrap.py").exists():
        sys.path.insert(0, str(_p / "scripts"))
        break
from _bootstrap import find_repo_root

ROOT = find_repo_root(Path(__file__).resolve())
DEFAULT_IMAGE = "nemoclaw/lab-runtime-test:local"

RUNTIME_JS = r"""
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const root = process.env.SITE_ROOT || '/site';
const pagePath = process.env.PAGE_PATH || '/nemoclaw/03a-kickstart.html';
const port = Number(process.env.SITE_PORT || 4197);
const timeoutMs = Number(process.env.AUDIT_TIMEOUT_MS || 120000);
const screenshot = process.env.SCREENSHOT_PATH || '';
const mime = { '.html':'text/html; charset=utf-8', '.js':'text/javascript; charset=utf-8', '.css':'text/css; charset=utf-8', '.json':'application/json; charset=utf-8', '.svg':'image/svg+xml', '.png':'image/png' };

function safeJoin(base, urlPath) {
  const clean = decodeURIComponent(urlPath.split('?')[0]).replace(/^\/+/, '');
  const out = path.resolve(base, clean);
  if (!out.startsWith(path.resolve(base))) throw new Error('path escape');
  return out;
}
const server = http.createServer((req, res) => {
  let file;
  try { file = safeJoin(root, req.url || '/'); } catch (_) { res.writeHead(403); res.end('forbidden'); return; }
  if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404); res.end('not found'); return; }
    res.writeHead(200, { 'content-type': mime[path.extname(file)] || 'application/octet-stream' });
    res.end(data);
  });
});
function listen() { return new Promise(resolve => server.listen(port, '127.0.0.1', resolve)); }

function fail(message) { throw new Error(message); }

(async () => {
  await listen();
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const pageErrors = [];
  const consoleErrors = [];
  page.on('pageerror', err => pageErrors.push(err.message || String(err)));
  page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
  const url = `http://127.0.0.1:${port}${pagePath}`;
  await page.goto(url, { waitUntil: 'networkidle', timeout: timeoutMs });

  const result = await page.evaluate(async () => {
    const host = document.createElement('section');
    host.id = 'frame-lifecycle-audit';
    (document.querySelector('main') || document.body).prepend(host);
    const mod = await import('/nemoclaw/scripts/_openclaw.js?frame-lifecycle-audit=' + Date.now());
    const realFetch = window.fetch;
    let queued = [];
    window.fetch = async () => {
      const next = queued.shift();
      if (next instanceof Error) throw next;
      if (!next) throw new Error('audit response queue exhausted');
      return next;
    };
    const probe = mod.mountClawProbe(host, {
      defaultUrl: 'https://frame-audit.example.test',
      defaultToken: '',
      intro: '',
      actions: [],
    });
    const action = { path: '/probe' };
    const frameState = () => {
      const frame = host.querySelector('.claw-html-frame');
      if (!frame) return { exists: false, hidden: false, srcdoc: false, display: '', width: 0, height: 0 };
      const rect = frame.getBoundingClientRect();
      return {
        exists: true,
        hidden: frame.hidden,
        srcdoc: frame.hasAttribute('srcdoc') && frame.getAttribute('srcdoc').length > 0,
        display: getComputedStyle(frame).display,
        width: rect.width,
        height: rect.height,
      };
    };
    const assertVisible = (label, state) => {
      if (!state.exists || state.hidden || !state.srcdoc || state.display === 'none' || !state.width || !state.height)
        throw new Error(label + ' should show the HTML frame: ' + JSON.stringify(state));
    };
    const assertCleared = (label, state) => {
      if (!state.exists || !state.hidden || state.srcdoc || state.display !== 'none' || state.width || state.height)
        throw new Error(label + ' left stale frame state: ' + JSON.stringify(state));
    };

    queued.push(new Response('<!doctype html><title>dashboard</title><p>dashboard body</p>', {
      status: 200, headers: { 'content-type': 'text/html' },
    }));
    await probe.run(action);
    const html = frameState();
    assertVisible('HTML response', html);

    queued.push(new Response(JSON.stringify({ ok: true }), {
      status: 200, headers: { 'content-type': 'application/json' },
    }));
    await probe.run(action);
    const json = frameState();
    assertCleared('JSON response', json);

    queued.push(new Response('<!doctype html><p>second dashboard</p>', {
      status: 200, headers: { 'content-type': 'text/html' },
    }));
    await probe.run(action);
    assertVisible('second HTML response', frameState());
    queued.push(new Error('synthetic network failure'));
    await probe.run(action);
    const networkError = frameState();
    assertCleared('network error', networkError);

    queued.push(new Response('<!doctype html><p>third dashboard</p>', {
      status: 200, headers: { 'content-type': 'text/html' },
    }));
    await probe.run(action);
    assertVisible('third HTML response', frameState());
    queued.push(new Response('<!doctype html><title>Cloudflare Access</title><p>Sign in ・ Cloudflare Access</p>', {
      status: 200, headers: { 'content-type': 'text/html' },
    }));
    await probe.run(action);
    const accessWarning = frameState();
    assertCleared('Cloudflare login warning', accessWarning);

    mod.mountClawProbe(host, {
      defaultUrl: 'https://frame-audit.example.test',
      defaultToken: '',
      intro: '',
      actions: [],
    });
    const remount = frameState();
    if (remount.exists) throw new Error('remount retained an HTML frame: ' + JSON.stringify(remount));
    window.fetch = realFetch;
    return { html, json, networkError, accessWarning, remount };
  });

  await page.reload({ waitUntil: 'networkidle', timeout: timeoutMs });
  const reloadFrames = await page.locator('.claw-html-frame').count();
  if (reloadFrames) fail(`reload retained ${reloadFrames} HTML frame(s)`);
  if (pageErrors.length) fail(`page errors: ${JSON.stringify(pageErrors)}`);
  if (consoleErrors.length) fail(`console errors: ${JSON.stringify(consoleErrors)}`);
  if (screenshot) await page.screenshot({ path: screenshot, fullPage: true });
  await page.close();
  await browser.close();
  server.close();
  console.log(JSON.stringify({ ok: true, root, pagePath, result, reloadFrames, consoleErrors }, null, 2));
})().catch(err => {
  try { server.close(); } catch (_) {}
  console.error(err && err.stack || String(err));
  process.exit(1);
});
"""


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Validate OpenClaw probe HTML-frame cleanup in Chromium")
    ap.add_argument("--site-root", default="web", help="source or built site root")
    ap.add_argument("--page", default="/nemoclaw/03a-kickstart.html", help="page under site root")
    ap.add_argument("--image", default=DEFAULT_IMAGE, help="browser runtime image")
    ap.add_argument("--engine", default=os.environ.get("CONTAINER_ENGINE") or "podman", help="container engine")
    ap.add_argument("--timeout-ms", type=int, default=120000, help="browser timeout")
    ap.add_argument("--screenshot", default="", help="optional screenshot output")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    site_arg = Path(args.site_root)
    site_root = site_arg.resolve() if site_arg.is_absolute() else (ROOT / site_arg).resolve()
    if not site_root.exists():
        print(f"openclaw_probe_frame_runtime_audit: FAIL\n  - site root missing: {site_root}")
        return 1
    screenshot_dir = None
    screenshot_path = ""
    if args.screenshot:
        screenshot = Path(args.screenshot)
        if not screenshot.is_absolute():
            screenshot = ROOT / screenshot
        screenshot.parent.mkdir(parents=True, exist_ok=True)
        screenshot_dir = screenshot.parent.resolve()
        screenshot_path = "/screenshots/" + screenshot.name
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(RUNTIME_JS)
        script = Path(fh.name)
    cmd = [args.engine, "run", "--rm", "--entrypoint", "node"]
    if args.engine.endswith("podman"):
        cmd.append("--userns=keep-id")
    cmd += [
        "-e", "NODE_PATH=/opt/nemoclaw-runtime/node_modules",
        "-e", "SITE_ROOT=/site",
        "-e", f"PAGE_PATH={args.page}",
        "-e", f"AUDIT_TIMEOUT_MS={args.timeout_ms}",
        "-v", f"{site_root}:/site:ro",
        "-v", f"{script}:/tmp/openclaw_probe_frame_runtime_audit.js:ro",
    ]
    if screenshot_dir:
        cmd += ["-e", f"SCREENSHOT_PATH={screenshot_path}", "-v", f"{screenshot_dir}:/screenshots"]
    cmd += [args.image, "/tmp/openclaw_probe_frame_runtime_audit.js"]
    try:
        proc = subprocess.run(
            cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=args.timeout_ms / 1000 + 60,
        )
    except FileNotFoundError:
        print(f"openclaw_probe_frame_runtime_audit: FAIL\n  - container engine not found: {args.engine}")
        return 1
    except subprocess.TimeoutExpired as exc:
        print(f"openclaw_probe_frame_runtime_audit: FAIL\n  - timed out after {exc.timeout}s")
        if exc.stdout:
            print(exc.stdout)
        return 1
    finally:
        try:
            script.unlink()
        except OSError:
            pass
    print(proc.stdout.rstrip())
    print("openclaw_probe_frame_runtime_audit: " + ("OK" if proc.returncode == 0 else "FAIL"))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
