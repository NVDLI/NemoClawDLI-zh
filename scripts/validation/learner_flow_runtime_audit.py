#!/usr/bin/env python3
"""Exercise prerequisite, run, stop, reset, error, and disclosure states in Chromium."""
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

const root = '/site';
const port = 4203;
const mime = { '.html':'text/html; charset=utf-8', '.js':'text/javascript; charset=utf-8', '.css':'text/css; charset=utf-8', '.json':'application/json' };
const fixture = `<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/nemoclaw/styles/_style.css"></head><body><main>
  <div id="run-cell"></div><div id="canvas"></div><div id="chat"></div><div id="console"></div>
</main><script type="module">
import { mountRunCell, mountCanvasFlow, mountChatUI, mountConsole } from "/nemoclaw/scripts/_shared.js";
window.fixtureReady = false;
window.runApi = mountRunCell("#run-cell", {
  label: "fixture run cell",
  intro: "Read the outcome first. Open code only to change the wait.",
  code: \`await new Promise((resolve, reject) => {\n  const timer = setTimeout(resolve, 5000);\n  AbortSignal.addEventListener("abort", () => { clearTimeout(timer); reject(new DOMException("stopped", "AbortError")); }, { once: true });\n});\nlog("finished");\`,
});
window.canvasApi = mountCanvasFlow("#canvas", {
  label: "fixture flow", intro: "One cancellable step.", nodes: [{ id:"wait", title:"Wait", x:0, y:0,
    code: \`await new Promise((resolve, reject) => {\n  const timer = setTimeout(resolve, 5000);\n  helpers.signal.addEventListener("abort", () => { clearTimeout(timer); reject(new DOMException("stopped", "AbortError")); }, { once: true });\n});\nhelpers.log("finished");\` }],
});
window.chatApi = mountChatUI("#chat", {
  disabled: () => !window.fixtureReady,
  disabledMsg: "Complete fixture setup.",
  greeting: "Fixture chat",
  respond: async (_text, ctx) => { await new Promise((resolve, reject) => { const timer = setTimeout(resolve, 5000); ctx.signal.addEventListener("abort", () => { clearTimeout(timer); reject(new DOMException("stopped", "AbortError")); }, { once:true }); }); },
});
window.consoleApi = mountConsole("#console", {
  greeting: "Fixture console",
  onSubmit: async (_line, _con, ctx) => { await new Promise((resolve, reject) => { const timer = setTimeout(resolve, 5000); ctx.signal.addEventListener("abort", () => { clearTimeout(timer); reject(new DOMException("stopped", "AbortError")); }, { once:true }); }); },
});
window.fixtureMounted = true;
</script></body></html>`;

function safeJoin(urlPath) {
  const clean = decodeURIComponent(urlPath.split('?')[0]).replace(/^\/+/, '');
  const out = path.resolve(root, clean);
  if (!out.startsWith(path.resolve(root))) throw new Error('path escape');
  return out;
}
const server = http.createServer((req, res) => {
  if ((req.url || '').split('?')[0] === '/fixture.html') { res.writeHead(200, { 'content-type':'text/html; charset=utf-8' }); res.end(fixture); return; }
  let file;
  try { file = safeJoin(req.url || '/'); } catch (_) { res.writeHead(403); res.end(); return; }
  if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
  fs.readFile(file, (err, data) => { if (err) { res.writeHead(404); res.end('not found'); return; } res.writeHead(200, { 'content-type':mime[path.extname(file)] || 'application/octet-stream' }); res.end(data); });
});

async function waitText(locator, pattern) {
  await locator.waitFor({ state:'visible' });
  await locator.evaluate((el, source) => new Promise((resolve, reject) => {
    const re = new RegExp(source, 'i');
    if (re.test(el.textContent || '')) return resolve();
    const observer = new MutationObserver(() => { if (re.test(el.textContent || '')) { observer.disconnect(); resolve(); } });
    observer.observe(el, { subtree:true, childList:true, characterData:true, attributes:true });
    setTimeout(() => { observer.disconnect(); reject(new Error(`timed out waiting for ${source}: ${el.textContent}`)); }, 10000);
  }), pattern.source);
}

(async () => {
  await new Promise(resolve => server.listen(port, '127.0.0.1', resolve));
  const browser = await chromium.launch({ headless:true });
  const page = await browser.newPage({ viewport:{ width:1100, height:900 } });
  const pageErrors = [];
  page.on('pageerror', error => pageErrors.push(error.message || String(error)));
  await page.goto(`http://127.0.0.1:${port}/fixture.html`, { waitUntil:'networkidle' });
  await page.waitForFunction(() => window.fixtureMounted === true);

  const intro = await page.locator('#run-cell .rc-intro').innerText();
  if (!/Read the outcome first/.test(intro)) throw new Error('RunCell intro did not render');
  if (await page.locator('#run-cell .rc-code-det').getAttribute('open') !== null) throw new Error('RunCell code opened by default');

  const chatState = page.locator('#chat .chatui-state');
  await waitText(chatState, /Prerequisite:/);
  if (!await page.locator('#chat .chatui-send').isDisabled()) throw new Error('chat Send enabled before prerequisite');
  await page.evaluate(() => { window.fixtureReady = true; window.dispatchEvent(new Event('nemoclaw:prerequisites')); });
  await waitText(chatState, /^Ready$/);
  if (await page.locator('#chat .chatui-send').isDisabled()) throw new Error('chat Send stayed disabled after prerequisite');

  await page.locator('#chat .chatui-text').fill('reset this run');
  await page.locator('#chat .chatui-send').click();
  await waitText(chatState, /Running/);
  await page.locator('#chat .chatui-reset').click();
  await waitText(chatState, /^Ready$/);
  if (/reset this run/.test(await page.locator('#chat .chatui-log').innerText())) throw new Error('chat Reset left the in-flight turn');
  await page.locator('#chat .chatui-text').fill('stop this run');
  await page.locator('#chat .chatui-send').click();
  await waitText(chatState, /Running/);
  await page.locator('#chat .chatui-send').click();
  await waitText(chatState, /Stopped.*Ready/);
  await page.locator('#chat .chatui-reset').click();
  await waitText(chatState, /^Ready$/);

  const runButton = page.locator('#run-cell .rc-run');
  await runButton.click();
  await waitText(runButton, /Stop/);
  await page.locator('#run-cell .rc-reset').click();
  await waitText(page.locator('#run-cell .rc-out'), /reset.*empty/i);
  await waitText(runButton, /Run$/);
  await page.waitForTimeout(100);
  if (!/reset.*empty/i.test(await page.locator('#run-cell .rc-out').innerText())) throw new Error('RunCell stale completion overwrote Reset');
  await runButton.click();
  await waitText(runButton, /Stop/);
  await runButton.click();
  await waitText(page.locator('#run-cell .rc-out'), /stopped/);
  await waitText(runButton, /Run$/);
  await page.locator('#run-cell .rc-code').evaluate(el => { el.value = 'throw new Error("fixture boom")'; });
  await runButton.click();
  await waitText(page.locator('#run-cell .rc-out'), /fixture boom/);
  if (await page.locator('#run-cell .rc-code-det').getAttribute('open') === null) throw new Error('RunCell error did not reveal code');
  await page.locator('#run-cell .rc-reset').click();
  await waitText(page.locator('#run-cell .rc-out'), /reset.*empty/i);

  const flowButton = page.locator('#canvas .cf-btn-run');
  await flowButton.click();
  await waitText(flowButton, /Stop/);
  await page.locator('#canvas .cf-btn-reset').click();
  await waitText(page.locator('#canvas .cf-status-bar'), /^reset$/);
  await waitText(flowButton, /Run all$/);
  await page.waitForTimeout(100);
  if ((await page.locator('#canvas .cf-status-bar').innerText()).trim() !== 'reset') throw new Error('CanvasFlow stale completion overwrote Reset');
  await flowButton.click();
  await waitText(flowButton, /Stop/);
  await flowButton.click();
  await waitText(page.locator('#canvas .cf-status-bar'), /stopped/);
  await page.locator('#canvas .cf-btn-reset').click();
  await waitText(page.locator('#canvas .cf-status-bar'), /^reset$/);

  const consoleInput = page.locator('#console .da-in');
  await consoleInput.scrollIntoViewIfNeeded();
  const scrollBeforeConsoleRun = await page.evaluate(() => window.scrollY);
  await consoleInput.fill('wait');
  await consoleInput.press('Enter');
  await waitText(page.locator('#console .da-console-state'), /Running/);
  await page.locator('#console .da-stop').click();
  await waitText(page.locator('#console .da-console-state'), /Stopped.*Ready/);
  await waitText(page.locator('#console .da-out'), /stopped/);
  const scrollAfterConsoleRun = await page.evaluate(() => window.scrollY);
  if (Math.abs(scrollAfterConsoleRun - scrollBeforeConsoleRun) > 2) throw new Error(`console run moved viewport: ${scrollBeforeConsoleRun} -> ${scrollAfterConsoleRun}`);
  await page.locator('#console .da-clear').click();
  if ((await page.locator('#console .da-out').innerText()).trim()) throw new Error('console Clear left output');

  if (pageErrors.length) throw new Error(`page errors: ${JSON.stringify(pageErrors)}`);
  const result = await page.evaluate(() => ({
    intro: document.querySelector('#run-cell .rc-intro')?.textContent.trim(),
    run: document.querySelector('#run-cell .rc-out')?.textContent.trim(),
    flow: document.querySelector('#canvas .cf-status-bar')?.textContent.trim(),
    chat: document.querySelector('#chat .chatui-state')?.textContent.trim(),
    console: document.querySelector('#console .da-console-state')?.textContent.trim(),
  }));
  console.log(JSON.stringify({ ok:true, states:result }, null, 2));
  await browser.close();
  server.close();
})().catch(error => { try { server.close(); } catch (_) {} console.error(error.stack || String(error)); process.exit(1); });
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root", default="web")
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--engine", default=os.environ.get("CONTAINER_ENGINE") or "podman")
    args = parser.parse_args()
    site_arg = Path(args.site_root)
    site_root = site_arg.resolve() if site_arg.is_absolute() else (ROOT / site_arg).resolve()
    if not (site_root / "nemoclaw/scripts/_shared.js").is_file():
        print(f"learner_flow_runtime_audit: FAIL\n  - incomplete site root: {site_root}")
        return 1
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(RUNTIME_JS)
        script = Path(handle.name)
    cmd = [args.engine, "run", "--rm", "--entrypoint", "node"]
    if args.engine.endswith("podman"):
        cmd.append("--userns=keep-id")
    cmd += [
        "-e", "NODE_PATH=/opt/nemoclaw-runtime/node_modules",
        "-v", f"{site_root}:/site:ro",
        "-v", f"{script}:/tmp/learner_flow_runtime_audit.js:ro",
        args.image,
        "/tmp/learner_flow_runtime_audit.js",
    ]
    try:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(f"learner_flow_runtime_audit: FAIL\n  - {exc}")
        return 1
    finally:
        try:
            script.unlink()
        except OSError:
            pass
    print(proc.stdout.rstrip())
    print("learner_flow_runtime_audit: " + ("OK" if proc.returncode == 0 else "FAIL"))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
