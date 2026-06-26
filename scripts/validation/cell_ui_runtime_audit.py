#!/usr/bin/env python3
"""Browser-check the shared runnable-cell UI contract.

This is intentionally stricter than a page render smoke. It verifies the
consolidated CanvasFlow/RunCell abstraction across source or built pages,
multiple viewport/theme configurations, CodeMirror highlighting, hidden-code
heuristics, unified controls, and actual run output on the helper notebook.
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
DEFAULT_PAGES = (
    "/nemoclaw/scripts/SKILL.html",
    "/nemoclaw/01a-loop.html",
    "/nemoclaw/04b-modern-clis.html",
)

RUNTIME_JS = r"""
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const root = process.env.SITE_ROOT || '/site';
const pages = JSON.parse(process.env.CELL_UI_PAGES || '[]');
const screenshots = process.env.SCREENSHOT_DIR || '';
const port = Number(process.env.SITE_PORT || 4196);
const timeoutMs = Number(process.env.AUDIT_TIMEOUT_MS || 120000);
const mime = { '.html':'text/html; charset=utf-8', '.js':'text/javascript; charset=utf-8', '.css':'text/css; charset=utf-8', '.json':'application/json; charset=utf-8', '.svg':'image/svg+xml', '.png':'image/png', '.jpg':'image/jpeg', '.jpeg':'image/jpeg', '.woff2':'font/woff2' };
const viewports = [
  { name: 'desktop', width: 1440, height: 1000 },
  { name: 'narrow', width: 390, height: 900 },
];
const themes = ['dark', 'light'];

function safeJoin(base, urlPath) {
  const clean = decodeURIComponent(urlPath.split('?')[0]).replace(/^\/+/, '');
  const out = path.resolve(base, clean);
  if (!out.startsWith(path.resolve(base))) throw new Error('path escape');
  return out;
}
const server = http.createServer((req, res) => {
  let file;
  try { file = safeJoin(root, req.url || '/'); } catch (e) { res.writeHead(403); res.end('forbidden'); return; }
  if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404); res.end('not found'); return; }
    res.writeHead(200, { 'content-type': mime[path.extname(file)] || 'application/octet-stream' });
    res.end(data);
  });
});
function listen() { return new Promise(resolve => server.listen(port, '127.0.0.1', resolve)); }
function wait(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }

async function inspectPage(page, pagePath, vp, theme) {
  const url = `http://127.0.0.1:${port}${pagePath}`;
  const pageErrors = [];
  const consoleErrors = [];
  page.on('pageerror', err => pageErrors.push(err.message || String(err)));
  page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
  await page.setViewportSize({ width: vp.width, height: vp.height });
  await page.addInitScript((themeName) => {
    try { document.documentElement.setAttribute('data-theme', themeName); } catch (_) {}
  }, theme);
  await page.goto(url, { waitUntil: 'networkidle', timeout: timeoutMs });
  await page.evaluate((themeName) => document.documentElement.setAttribute('data-theme', themeName), theme);
  await wait(600);

  const visibility = await page.evaluate(() => ({
    canvasLongOpen: Array.from(document.querySelectorAll('.cf-panel-code-det[open] .cf-panel-code')).filter(ta => (ta.value || '').split('\n').length >= 40).length,
    runCellOpenDefault: document.querySelectorAll('.rc-code-det[open]').length,
  }));
  const initial = await page.evaluate((visibility) => {
    const codeDetails = Array.from(document.querySelectorAll('.cf-panel-code-det,.rc-code-det'));
    const codeSummaries = codeDetails.map(det => (det.querySelector('summary')?.textContent || '').trim());
    const canvasLongOpen = Array.from(document.querySelectorAll('.cf-panel-code-det[open] .cf-panel-code')).filter(ta => (ta.value || '').split('\n').length >= 40).length;
    const runCellOpenDefault = document.querySelectorAll('.rc-code-det[open]').length;
    const cms = Array.from(document.querySelectorAll('.CodeMirror'));
    const output = {
      title: document.title,
      main: !!document.querySelector('main'),
      flows: document.querySelectorAll('.cf-btn-run').length,
      panels: document.querySelectorAll('.cf-panel').length,
      runCells: document.querySelectorAll('.rc-card').length,
      unifiedButtons: document.querySelectorAll('.cell-btn').length,
      unifiedLangChips: document.querySelectorAll('.cell-lang-chip').length,
      uglyCellButtons: document.querySelectorAll('.rc-run:not(.cell-btn),.rc-reset:not(.cell-btn),.cf-panel-runone:not(.cell-btn),.cf-panel-reset:not(.cell-btn)').length,
      plainCodeLabels: codeSummaries.filter(t => /^code\b/i.test(t)).length,
      canvasLongOpen: visibility.canvasLongOpen,
      runCellOpenDefault: visibility.runCellOpenDefault,
      codeMirrorCount: cms.length,
      cmTokenCount: document.querySelectorAll('.CodeMirror .cm-keyword,.CodeMirror .cm-string,.CodeMirror .cm-property,.CodeMirror .cm-def').length,
      pageOverflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      badOverflow: Array.from(document.querySelectorAll('body *')).filter(el => {
        const r = el.getBoundingClientRect();
        if (r.right <= document.documentElement.clientWidth + 2) return false;
        if (el.closest('.topbar nav,.cf-stage,.CodeMirror,.CodeMirror-scroll,.cf-helpers-scroll,.cell-log-json,.cf-panel-log-json,.cf-log-json,pre')) return false;
        return true;
      }).slice(0, 8).map(el => ({ tag: el.tagName, cls: String(el.className || '').slice(0, 80), text: (el.textContent || '').trim().slice(0, 80) })),
      minCellButton: Math.min(...Array.from(document.querySelectorAll('.cell-btn')).map(b => Math.min(b.getBoundingClientRect().width, b.getBoundingClientRect().height)).filter(Number.isFinite), 999),
    };
    return output;
  }, visibility);

  const runSelectors = await page.evaluate(() => {
    if (!document.querySelector('.helper-notebook')) return [];
    return ['#helper-map-cell .cf-btn-run', '#helper-retrieval-cell .cf-btn-run', '#helper-live-cell .cf-btn-run', '#helper-ui-cell .rc-run'];
  });
  if (runSelectors.length) {
    await page.evaluate(() => document.querySelectorAll('.cf-panel-code-det,.rc-code-det').forEach(det => { det.open = false; }));
    await wait(150);
  }
  const runResults = [];
  for (const sel of runSelectors) {
    const loc = page.locator(sel).first();
    if (!await loc.count()) throw new Error(`missing helper run selector ${sel}`);
    await loc.click();
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const txt = await loc.innerText().catch(() => '');
      if (!/stop|running|⏹/i.test(txt)) break;
      await wait(250);
    }
    const rootSel = sel.replace(/ .*/, '');
    const text = await page.locator(rootSel).innerText().catch(() => '');
    runResults.push({ sel, hasOutput: /(returned value|wrote into state|helper|mounted|liveSkipped|labSkipped|traceEvents)/i.test(text), badText: /TypeError|ReferenceError|helpers\.log\.[a-z]+ is not a function|✗ stopped:/i.test(text) });
  }
  await page.evaluate(() => document.querySelectorAll('.cf-panel-code-det,.rc-code-det').forEach(det => { det.open = true; }));
  await wait(250);
  if (screenshots) {
    fs.mkdirSync(screenshots, { recursive: true });
    const safe = pagePath.replace(/[^a-z0-9]+/gi, '_').replace(/^_+|_+$/g, '').slice(0, 80);
    await page.screenshot({ path: path.join(screenshots, `${safe}_${vp.name}_${theme}.png`), fullPage: true });
  }
  const finalInfo = await page.evaluate(() => ({
    codeMirrorCount: document.querySelectorAll('.CodeMirror').length,
    cmTokenCount: document.querySelectorAll('.CodeMirror .cm-keyword,.CodeMirror .cm-string,.CodeMirror .cm-property,.CodeMirror .cm-def').length,
    outputs: document.querySelectorAll('.cf-panel-output:not(:empty),.rc-out:not(:empty)').length,
    logHeadings: document.querySelectorAll('.cell-log-heading').length,
    jsonBlocks: document.querySelectorAll('.cell-log-json,.cf-panel-output-pre code.language-json').length,
    detailsBlocks: document.querySelectorAll('.cell-log-details, .cf-panel-log-details').length,
    htmlBlocks: document.querySelectorAll('.cell-log-html,.cf-panel-log-html').length,
  }));

  const failures = [];
  if (!initial.main) failures.push('missing <main>');
  if (initial.flows + initial.runCells > 0 && initial.unifiedButtons < (initial.flows * 2 + initial.panels * 2 + initial.runCells * 2)) failures.push('too few unified .cell-btn controls');
  if (initial.flows + initial.runCells > 0 && initial.unifiedLangChips < initial.panels + initial.runCells) failures.push('too few unified JS chips');
  if (initial.uglyCellButtons) failures.push(`ugly legacy buttons ${initial.uglyCellButtons}`);
  if (initial.plainCodeLabels) failures.push(`plain code labels ${initial.plainCodeLabels}`);
  if (initial.canvasLongOpen) failures.push(`long CanvasFlow code open by default ${initial.canvasLongOpen}`);
  if (initial.flows + initial.runCells > 0 && finalInfo.codeMirrorCount < initial.panels + initial.runCells) failures.push('CodeMirror did not mount for every opened editor');
  if (initial.flows + initial.runCells > 0 && finalInfo.cmTokenCount < finalInfo.codeMirrorCount) failures.push('CodeMirror syntax tokens missing');
  if (initial.badOverflow.length) failures.push(`uncontained horizontal overflow ${JSON.stringify(initial.badOverflow)}`);
  if (initial.minCellButton < 28) failures.push(`tiny cell button dimension ${initial.minCellButton}`);
  const badRuns = runResults.filter(r => !r.hasOutput || r.badText);
  if (badRuns.length) failures.push(`helper run output failed ${JSON.stringify(badRuns)}`);
  if (pageErrors.length) failures.push(`page errors ${JSON.stringify(pageErrors)}`);
  return { pagePath, viewport: vp.name, theme, initial, runResults, finalInfo, consoleErrors, failures };
}

(async () => {
  await listen();
  const browser = await chromium.launch({ headless: true });
  const results = [];
  for (const pagePath of pages) {
    for (const vp of viewports) {
      for (const theme of themes) {
        const page = await browser.newPage();
        try { results.push(await inspectPage(page, pagePath, vp, theme)); }
        finally { await page.close().catch(() => {}); }
      }
    }
  }
  await browser.close();
  server.close();
  const failed = results.filter(r => r.failures.length);
  console.log(JSON.stringify({ ok: failed.length === 0, root, screenshots: screenshots || null, results }, null, 2));
  process.exit(failed.length ? 1 : 0);
})().catch(err => {
  try { server.close(); } catch (_) {}
  console.error(err && err.stack || String(err));
  process.exit(1);
});
"""


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Validate shared CanvasFlow/RunCell UI in a browser container")
    ap.add_argument("--site-root", default="web", help="site root to serve, usually web or public")
    ap.add_argument("--page", action="append", dest="pages", help="page path under site root; repeatable")
    ap.add_argument("--screenshots", default="", help="directory for full-page PNG screenshots")
    ap.add_argument("--image", default=DEFAULT_IMAGE, help="browser runtime image")
    ap.add_argument("--engine", default=os.environ.get("CONTAINER_ENGINE") or "podman", help="container engine")
    ap.add_argument("--timeout-ms", type=int, default=120000, help="browser timeout")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    site_root = (ROOT / args.site_root).resolve() if not Path(args.site_root).is_absolute() else Path(args.site_root).resolve()
    if not site_root.exists():
        print(f"cell_ui_runtime_audit: FAIL\n  - site root missing: {site_root}")
        return 1
    pages = args.pages or list(DEFAULT_PAGES)
    screenshot_dir = ""
    if args.screenshots:
        out = Path(args.screenshots)
        if not out.is_absolute():
            out = ROOT / out
        out.mkdir(parents=True, exist_ok=True)
        screenshot_dir = "/screenshots"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(RUNTIME_JS)
        script = Path(fh.name)
    cmd = [args.engine, "run", "--rm", "--entrypoint", "node"]
    if args.engine.endswith("podman"):
        cmd.append("--userns=keep-id")
    cmd += [
        "-e", "NODE_PATH=/opt/nemoclaw-runtime/node_modules",
        "-e", "SITE_ROOT=/site",
        "-e", f"CELL_UI_PAGES={__import__('json').dumps(pages)}",
        "-e", f"AUDIT_TIMEOUT_MS={args.timeout_ms}",
        "-v", f"{site_root}:/site:ro",
        "-v", f"{script}:/tmp/cell_ui_runtime_audit.js:ro",
    ]
    if args.screenshots:
        host_out = (ROOT / args.screenshots).resolve() if not Path(args.screenshots).is_absolute() else Path(args.screenshots).resolve()
        cmd += ["-e", f"SCREENSHOT_DIR={screenshot_dir}", "-v", f"{host_out}:{screenshot_dir}"]
    cmd += [args.image, "/tmp/cell_ui_runtime_audit.js"]
    try:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=(args.timeout_ms / 1000) * max(1, len(pages)) * 4 + 60)
    except FileNotFoundError:
        print(f"cell_ui_runtime_audit: FAIL\n  - container engine not found: {args.engine}")
        return 1
    except subprocess.TimeoutExpired as exc:
        print("cell_ui_runtime_audit: FAIL")
        print(f"  - timed out after {exc.timeout}s")
        if exc.stdout:
            print(exc.stdout)
        return 1
    finally:
        try:
            script.unlink()
        except OSError:
            pass
    print(proc.stdout.rstrip())
    print("cell_ui_runtime_audit: " + ("OK" if proc.returncode == 0 else "FAIL"))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
