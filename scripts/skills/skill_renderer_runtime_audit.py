#!/usr/bin/env python3
"""Render every source SKILL.html with Playwright and fail on broken UI contracts."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "skills"))
import skill_audit

DEFAULT_IMAGE = "nemoclaw/lab-runtime-test:local"

RUNTIME_JS = r"""
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const root = process.env.SITE_ROOT || '/site';
const skillFiles = JSON.parse(fs.readFileSync(process.env.SKILL_FILES || '/tmp/skill-files.json', 'utf8'));
const port = 4214;
const mime = {
  '.html':'text/html; charset=utf-8', '.js':'text/javascript; charset=utf-8',
  '.mjs':'text/javascript; charset=utf-8', '.css':'text/css; charset=utf-8',
  '.json':'application/json; charset=utf-8', '.svg':'image/svg+xml',
  '.png':'image/png', '.jpg':'image/jpeg', '.jpeg':'image/jpeg', '.ico':'image/x-icon',
  '.md':'text/markdown; charset=utf-8', '.txt':'text/plain; charset=utf-8',
};

function safeJoin(urlPath) {
  const clean = decodeURIComponent(urlPath.split('?')[0]).replace(/^\/+/, '');
  const output = path.resolve(root, clean);
  if (!output.startsWith(path.resolve(root))) throw new Error('path escape');
  return output;
}

const server = http.createServer((request, response) => {
  let file;
  try { file = safeJoin(request.url || '/'); }
  catch (_) { response.writeHead(403); response.end('forbidden'); return; }
  if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
  fs.readFile(file, (error, data) => {
    if (error) { response.writeHead(404); response.end('not found'); return; }
    response.writeHead(200, { 'content-type': mime[path.extname(file).toLowerCase()] || 'application/octet-stream' });
    response.end(request.method === 'HEAD' ? undefined : data);
  });
});

async function inspect(browser, file) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  page.on('pageerror', error => errors.push(`pageerror: ${error.message || String(error)}`));
  page.on('console', message => {
    if (message.type() !== 'error') return;
    const text = message.text();
    if (/^Failed to load resource: the server responded with a status of 404/.test(text)) return;
    errors.push(`console: ${text}`);
  });
  page.on('response', response => {
    const type = response.request().resourceType();
    if (response.status() >= 400 && ['document', 'script', 'stylesheet', 'image', 'font'].includes(type)) {
      errors.push(`${type} HTTP ${response.status()}: ${response.url()}`);
    }
  });
  try {
    const response = await page.goto(`http://127.0.0.1:${port}/${file}`, { waitUntil:'domcontentloaded', timeout:30000 });
    await page.waitForTimeout(500);
    await page.waitForFunction(() => {
      let meta;
      try { meta = JSON.parse(document.getElementById('skill-meta')?.textContent || '{}'); }
      catch (_) { return true; }
      return (meta.exports || []).every(item => {
        const mount = document.getElementById(item.preview_mount);
        return mount && (mount.dataset.exportReady === '1' || mount.dataset.exportError);
      });
    }, null, { timeout:10000 }).catch(() => {});
    if (!response || !response.ok()) errors.push(`document HTTP ${response && response.status()}`);
    const state = await page.evaluate(() => {
      const parse = id => { try { return JSON.parse(document.getElementById(id)?.textContent || ''); } catch (_) { return null; } };
      const config = document.getElementById('explorer-config');
      const meta = parse('skill-meta');
      const exports = (meta?.exports || []).map(item => {
        const mount = document.getElementById(item.preview_mount);
        const categoryGroup = mount?.querySelector('.filter-choice-group');
        const categoryBoxes = Array.from(categoryGroup?.querySelectorAll('input[type="checkbox"]') || []);
        const before = mount?.querySelectorAll('tbody tr').length || 0;
        const toggle = categoryBoxes.find(input => !input.checked) || categoryBoxes[categoryBoxes.length - 1];
        if (toggle) { toggle.checked = !toggle.checked; toggle.dispatchEvent(new Event('change', {bubbles:true})); }
        const after = mount?.querySelectorAll('tbody tr').length || 0;
        const sortButtons = Array.from(mount?.querySelectorAll('th button[data-sort-index]') || []);
        const sortDirections = sortButtons.map(button => {
          button.click();
          const ascending = button.closest('th')?.getAttribute('aria-sort') === 'ascending';
          button.click();
          const descending = button.closest('th')?.getAttribute('aria-sort') === 'descending';
          return ascending && descending;
        });
        return {
          id:item.id,
          present:!!mount,
          ready:mount?.dataset.exportReady === '1',
          error:mount?.dataset.exportError || '',
          rows:mount?.querySelectorAll('tbody tr').length || 0,
          choiceGroups:mount?.querySelectorAll('.filter-choice-group').length || 0,
          choiceCount:mount?.querySelectorAll('.filter-choice-group input[type="checkbox"]').length || 0,
          headerCount:mount?.querySelectorAll('thead th').length || 0,
          sortButtons:sortButtons.length,
          multiChanged:before !== after,
          allSortDirections:sortDirections.length > 0 && sortDirections.every(Boolean),
        };
      });
      return {
        meta: !!meta,
        config: !config || !!parse('explorer-config'),
        navigationHeader: !!document.querySelector('header[data-skill-header="1"] nav'),
        navigationLinks: document.querySelectorAll('header[data-skill-header="1"] nav a[href]').length,
        visibleNavigationRegions: Array.from(document.querySelectorAll('header[data-skill-header="1"], .sx-topbar')).filter(node => getComputedStyle(node).display !== 'none').length,
        duplicateExplorerHeading: !!document.querySelector('.skill-static') && !!document.querySelector('#explorer .sx-head'),
        themeUnified: (() => {
          const surface = document.querySelector('.skill-static');
          const button = document.querySelector('.sx-theme');
          if (!surface || !button) return true;
          const colors = () => [getComputedStyle(document.body).backgroundColor, getComputedStyle(surface).backgroundColor];
          const before = colors(); button.click(); const after = colors(); button.click();
          return before[0] === before[1] && after[0] === after[1] && before[0] !== after[0];
        })(),
        themeContrast: (() => {
          const surface = document.querySelector('.skill-static');
          const button = document.querySelector('.sx-theme');
          if (!surface || !button) return true;
          const rgb = value => (value.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
          const luminance = value => {
            const channels = rgb(value).map(channel => {
              const normalized = channel / 255;
              return normalized <= .03928 ? normalized / 12.92 : Math.pow((normalized + .055) / 1.055, 2.4);
            });
            return .2126 * channels[0] + .7152 * channels[1] + .0722 * channels[2];
          };
          const ratio = (foreground, background) => {
            const a = luminance(foreground), b = luminance(background);
            return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
          };
          const readable = () => Array.from(surface.querySelectorAll('h1, p, .skill-cmd code')).every(node => {
            const backgroundNode = node.closest('.skill-cmd') || surface;
            return ratio(getComputedStyle(node).color, getComputedStyle(backgroundNode).backgroundColor) >= 4.5;
          });
          const before = readable(); button.click(); const after = readable(); button.click();
          return before && after;
        })(),
        visibleText: (document.body?.innerText || '').trim().length,
        explorer: !!config,
        mounted: !!document.querySelector('.sx-topbar') && !!document.querySelector('.sx-main'),
        gone: document.querySelectorAll('.sx-dot.gone').length,
        exports,
      };
    });
    if (!state.meta) errors.push('skill-meta did not parse');
    if (!state.config) errors.push('explorer-config did not parse');
    if (!state.navigationHeader || state.navigationLinks < 2) errors.push('semantic skill navigation header is incomplete');
    if (state.visibleNavigationRegions !== 1) errors.push(`renderer produced ${state.visibleNavigationRegions} visible navigation headers`);
    if (state.duplicateExplorerHeading) errors.push('renderer repeated the static SKILL heading');
    if (!state.themeUnified) errors.push('static SKILL body and explorer do not share one light/dark theme');
    if (!state.themeContrast) errors.push('static SKILL body loses readable contrast in light or dark theme');
    if (!state.visibleText) errors.push('renderer produced no visible text');
    if (state.explorer && !state.mounted) errors.push('shared explorer did not mount');
    if (state.gone) errors.push(`${state.gone} configured file(s) did not load`);
    state.exports.forEach(item => {
      if (!item.present) errors.push(`export ${item.id} preview mount is missing`);
      else if (item.error) errors.push(`export ${item.id} preview failed: ${item.error}`);
      else if (!item.ready) errors.push(`export ${item.id} preview did not become ready`);
      else if (!item.rows) errors.push(`export ${item.id} preview rendered no component rows`);
      else if (item.choiceGroups < 3 || item.choiceCount < 3) errors.push(`export ${item.id} lacks multi-select filter groups`);
      else if (!item.multiChanged) errors.push(`export ${item.id} multi-select filters did not change the visible rows`);
      else if (item.sortButtons !== item.headerCount || !item.allSortDirections) errors.push(`export ${item.id} does not toggle every column between ascending and descending`);
    });
  } catch (error) {
    errors.push(`navigation: ${error.message || String(error)}`);
  }
  await page.close();
  return { file, errors: [...new Set(errors)] };
}

(async () => {
  await new Promise(resolve => server.listen(port, '127.0.0.1', resolve));
  const browser = await chromium.launch({
    headless:true,
    executablePath:process.env.CHROME_BIN || undefined,
  });
  const findings = [];
  let cursor = 0;
  async function worker() {
    while (cursor < skillFiles.length) {
      const file = skillFiles[cursor++];
      const result = await inspect(browser, file);
      if (result.errors.length) findings.push(result);
    }
  }
  await Promise.all(Array.from({ length: 4 }, worker));
  await browser.close();
  server.close();
  console.log(JSON.stringify({ files:skillFiles.length, findings }, null, 2));
  if (findings.length) process.exit(1);
})().catch(error => {
  try { server.close(); } catch (_) {}
  console.error(error.stack || String(error));
  process.exit(1);
});
"""


def run(args: argparse.Namespace) -> int:
    site = Path(args.site_root).resolve()
    if not site.is_dir():
        print(f"skill_renderer_runtime_audit: FAIL\n  - site root missing: {site}")
        return 1
    # Audit the tree actually being served. A Pages build contains projected contracts
    # beyond the source set, so reusing only the source manifest would silently miss them.
    files = sorted(path.relative_to(site).as_posix() for path in site.rglob("SKILL.html"))
    if not files:
        print(f"skill_renderer_runtime_audit: FAIL\n  - no SKILL.html files under {site}")
        return 1
    temp_parent = site.parent if args.engine == "apple" else None
    with tempfile.TemporaryDirectory(prefix="skill-renderer-audit-", dir=temp_parent) as temp:
        temp_path = Path(temp)
        script = temp_path / "audit.js"
        manifest = temp_path / "skill-files.json"
        script.write_text(RUNTIME_JS, encoding="utf-8")
        manifest.write_text(json.dumps(files), encoding="utf-8")
        if args.engine == "apple":
            command = [
                "container", "machine", "run", "--root", "--name", args.machine,
                "--workdir", str(site),
                "--env", f"NODE_PATH={args.node_path}",
                "--env", f"CHROME_BIN={args.chrome_bin}",
                "--env", f"SITE_ROOT={site}",
                "--env", f"SKILL_FILES={manifest}",
                "--", "node", str(script),
            ]
        elif args.engine == "current":
            command = ["node", str(script)]
        else:
            command = [args.engine, "run", "--rm", "--entrypoint", "node"]
            if args.engine.endswith("podman"):
                command.append("--userns=keep-id")
            command += [
                "-e", "NODE_PATH=/opt/nemoclaw-runtime/node_modules",
                "-e", "SITE_ROOT=/site",
                "-e", "SKILL_FILES=/tmp/skill-files.json",
                "-v", f"{site}:/site:ro",
                "-v", f"{script}:/tmp/skill-renderer-audit.js:ro",
                "-v", f"{manifest}:/tmp/skill-files.json:ro",
                args.image,
                "/tmp/skill-renderer-audit.js",
            ]
        try:
            environment = os.environ.copy()
            if args.engine == "current":
                environment.update({
                    "NODE_PATH": args.node_path,
                    "CHROME_BIN": args.chrome_bin,
                    "SITE_ROOT": str(site),
                    "SKILL_FILES": str(manifest),
                })
            result = subprocess.run(
                command,
                cwd=ROOT,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=args.timeout_seconds,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            print(f"skill_renderer_runtime_audit: FAIL\n  - {exc}")
            return 1
    print(result.stdout.rstrip())
    print("skill_renderer_runtime_audit: " + ("OK" if result.returncode == 0 else "FAIL"))
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", default=str(ROOT))
    default_engine = os.environ.get("CONTAINER_ENGINE") or ("apple" if shutil.which("container") else "docker")
    parser.add_argument("--engine", default=default_engine, help="apple, current, docker, or podman")
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--machine", default=os.environ.get("APPLE_CONTAINER_MACHINE") or "nemoclaw-test")
    parser.add_argument("--node-path", default=os.environ.get("APPLE_CONTAINER_NODE_PATH") or "/opt/nemoclaw-runtime/node_modules")
    parser.add_argument("--chrome-bin", default=os.environ.get("APPLE_CONTAINER_CHROME_BIN") or "/opt/nemoclaw-runtime/chromium-1187/chrome-linux/headless_shell")
    parser.add_argument("--timeout-seconds", type=int, default=240)
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
