#!/usr/bin/env python3
"""Render every HTML file with Playwright and fail on theme or SKILL UI drift.

HTML discovery is exhaustive under the served tree. Every page enters the desktop/narrow and
dark/light matrix; SKILL pages additionally receive their navigation, explorer, and export checks.
There is no file-level opt-in or exemption list.
"""
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


def discover_html(site: Path) -> list[str]:
    """Return every HTML path below the served tree; there is no exclusion mechanism."""
    return sorted(path.relative_to(site).as_posix() for path in site.rglob("*.html"))

RUNTIME_JS = r"""
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const root = process.env.SITE_ROOT || '/site';
const htmlFiles = JSON.parse(fs.readFileSync(process.env.HTML_FILES || '/tmp/html-files.json', 'utf8'));
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
  const isSkill = /(?:^|\/)SKILL\.html$/.test(file);
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  page.on('pageerror', error => errors.push(`pageerror: ${error.message || String(error)}`));
  page.on('console', message => {
    if (message.type() !== 'error') return;
    const text = message.text();
    if (/^Failed to load resource: the server responded with a status of \d+/.test(text)) return;
    errors.push(`console: ${text}`);
  });
  try {
    const response = await page.goto(`http://127.0.0.1:${port}/${file}`, { waitUntil:'domcontentloaded', timeout:30000 });
    await page.waitForTimeout(500);
    if (isSkill) await page.waitForFunction(() => {
      let meta;
      try { meta = JSON.parse(document.getElementById('skill-meta')?.textContent || '{}'); }
      catch (_) { return true; }
      return (meta.exports || []).every(item => {
        const mount = document.getElementById(item.preview_mount);
        return mount && (mount.dataset.exportReady === '1' || mount.dataset.exportError);
      }) && (() => {
        const evidence = document.getElementById('sbom-evidence-preview');
        return !evidence || evidence.dataset.sbomEvidenceReady === '1' || evidence.dataset.sbomEvidenceError;
      })();
    }, null, { timeout:10000 }).catch(() => {});
    // Asset and link integrity are separate blocking gates. This audit deliberately records
    // only a failed document navigation here so a mirrored source file still receives its
    // color test even when its build-time overlay assets are not colocated in the mirror.
    if (!response || !response.ok()) errors.push(`document HTTP ${response && response.status()}`);
    const state = await page.evaluate(async ({ isSkill }) => {
      const parse = id => { try { return JSON.parse(document.getElementById(id)?.textContent || ''); } catch (_) { return null; } };
      const config = document.getElementById('explorer-config');
      const meta = parse('skill-meta');
      const sbomEvidence = document.getElementById('sbom-evidence-preview');
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
      const parseColor = value => {
        const match = String(value || '').match(/rgba?\(([^)]+)\)/i);
        if (!match) return null;
        const parts = match[1].split(',').map(Number);
        return { r:parts[0], g:parts[1], b:parts[2], a:parts.length > 3 ? parts[3] : 1 };
      };
      const composite = (top, bottom) => {
        const alpha = top.a + bottom.a * (1 - top.a);
        if (!alpha) return {r:255,g:255,b:255,a:1};
        return {
          r:(top.r * top.a + bottom.r * bottom.a * (1 - top.a)) / alpha,
          g:(top.g * top.a + bottom.g * bottom.a * (1 - top.a)) / alpha,
          b:(top.b * top.a + bottom.b * bottom.a * (1 - top.a)) / alpha,
          a:alpha,
        };
      };
      const background = node => {
        const layers = [];
        for (let current=node; current; current=current.parentElement) {
          const color = parseColor(getComputedStyle(current).backgroundColor);
          if (color && color.a) layers.push(color);
        }
        let result = {r:255,g:255,b:255,a:1};
        for (let index=layers.length - 1; index >= 0; index--) result = composite(layers[index], result);
        return result;
      };
      const luminance = color => {
        const channel = value => {
          const normalized = value / 255;
          return normalized <= .03928 ? normalized / 12.92 : Math.pow((normalized + .055) / 1.055, 2.4);
        };
        return .2126 * channel(color.r) + .7152 * channel(color.g) + .0722 * channel(color.b);
      };
      const ratio = (foreground, backdrop) => {
        const a = luminance(foreground), b = luminance(backdrop);
        return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
      };
      const label = node => {
        const classes = Array.from(node.classList || []).slice(0, 2).join('.');
        const text = String(node.innerText || node.value || node.getAttribute?.('aria-label') || '').trim().replace(/\s+/g,' ').slice(0,48);
        return `${node.tagName.toLowerCase()}${node.id ? '#' + node.id : ''}${classes ? '.' + classes : ''}${text ? ' “' + text + '”' : ''}`;
      };
      const visible = node => {
        const style = getComputedStyle(node), box = node.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > .02 && box.width > 0 && box.height > 0;
      };
      const hasOwnText = node => Array.from(node.childNodes).some(child => child.nodeType === Node.TEXT_NODE && child.textContent.trim())
        || /^(INPUT|SELECT|TEXTAREA)$/.test(node.tagName);
      const auditStyle = document.createElement('style');
      auditStyle.textContent = '*,*::before,*::after{transition:none!important;animation:none!important}';
      document.head.appendChild(auditStyle);
      const themeSnapshot = mode => {
        document.documentElement.setAttribute('data-theme', mode);
        void document.documentElement.offsetWidth;
        const candidates = Array.from(document.querySelectorAll(
          'h1,h2,h3,h4,h5,h6,p,li,a,b,strong,em,small,code,pre,span,label,summary,button,th,td,input,select,textarea'
        ));
        const contrast = [];
        for (let index = 0; index < candidates.length; index++) {
          const node = candidates[index];
          if (!visible(node) || !hasOwnText(node) || node.closest('.CodeMirror, [aria-hidden="true"]')) continue;
          if ((node.closest('pre') && node.tagName !== 'PRE') || Array.from(node.classList || []).some(name => name.startsWith('hljs-'))) continue;
          const style = getComputedStyle(node), foreground = parseColor(style.color);
          if (!foreground || foreground.a < .5) continue;
          const score = ratio(foreground, background(node));
          contrast.push({index,label:label(node),ratio:Number(score.toFixed(2))});
        }
        const viewportWidth = document.documentElement.clientWidth;
        const overflowElements = Array.from(document.body.querySelectorAll('*')).flatMap(node => {
          if (!visible(node)) return [];
          const box = node.getBoundingClientRect();
          if (box.right <= viewportWidth + 2 && box.left >= -2) return [];
          for (let parent=node.parentElement; parent && parent !== document.body; parent=parent.parentElement) {
            const parentBox = parent.getBoundingClientRect();
            const overflow = getComputedStyle(parent).overflowX;
            if (/auto|scroll|hidden|clip/.test(overflow) && parentBox.left >= -2 && parentBox.right <= viewportWidth + 2) return [];
          }
          return [`${label(node)} (left ${Math.round(box.left)}px; right ${Math.round(box.right)}px; width ${Math.round(box.width)}px)`];
        }).slice(0,5);
        return {
          mode,
          viewportWidth,
          documentWidth:document.documentElement.scrollWidth,
          overflowElements,
          bodyBackground:getComputedStyle(document.body).backgroundColor,
          surfaceBackground:getComputedStyle(document.querySelector('.skill-static,main,body')).backgroundColor,
          contrast,
        };
      };
      const compareThemes = (dark, light) => dark.contrast.flatMap(item => {
        const other = light.contrast.find(candidate => candidate.index === item.index);
        if (!other) return [];
        const low = Math.min(item.ratio, other.ratio), high = Math.max(item.ratio, other.ratio);
        return low < 3 && high - low >= 1.5
          ? [`${item.label} (dark ${item.ratio.toFixed(2)}:1; light ${other.ratio.toFixed(2)}:1)`]
          : [];
      }).slice(0,12);
      window.__nemoclawThemeSnapshot = themeSnapshot;
      window.__nemoclawCompareThemes = compareThemes;
      const originalTheme = document.documentElement.getAttribute('data-theme');
      const dark = themeSnapshot('dark');
      const light = themeSnapshot('light');
      if (originalTheme === null) document.documentElement.removeAttribute('data-theme');
      else document.documentElement.setAttribute('data-theme', originalTheme);
      const themeCapable = Array.from(document.styleSheets).some(sheet => {
          try { return Array.from(sheet.cssRules || []).some(rule => String(rule.cssText || '').includes('data-theme')); }
          catch (_) { return false; }
        });
      const softwareMount = document.getElementById('third-party-export-preview');
      const localCategory = softwareMount?.querySelector('[data-export-category-group] input[value="local-authoring"]');
      let noAssertionView = null;
      if (localCategory) {
        softwareMount.querySelectorAll('[data-export-category-group] input[type="checkbox"]').forEach(input => {
          input.checked = input === localCategory;
        });
        localCategory.dispatchEvent(new Event('change', {bubbles:true}));
        const rows = Array.from(softwareMount.querySelectorAll('tbody tr'));
        const unresolved = rows.filter(row => row.querySelector('td[data-label="License"]')?.innerText.includes('NOASSERTION'));
        noAssertionView = {
          rows:rows.length,
          unresolved:unresolved.length,
          coveredSubjects:sbomEvidence?.querySelectorAll('tr[data-sbom-subject="1"]').length || 0,
          brokenLicenseLinks:unresolved.filter(row => row.querySelector('td[data-label="License"] a')).length,
          usefulEvidence:unresolved.every(row => /learners do not receive[\s\S]*scan the exact image/i.test(
            row.querySelector('td[data-label="Evidence"]')?.textContent || ''
          )),
        };
      }
      const evidenceAnchors = Array.from(document.querySelectorAll('a[data-evidence-link]'));
      const invalidEvidenceLinks = evidenceAnchors.filter(anchor => {
        const raw = anchor.getAttribute('href') || '';
        return !raw || raw === '#' || /^javascript:/i.test(raw);
      }).map(anchor => anchor.textContent.trim());
      const localEvidenceChecks = await Promise.all(evidenceAnchors.filter(anchor =>
        anchor.dataset.evidenceLink === 'local' && new URL(anchor.href).origin === location.origin
      ).map(async anchor => {
        try {
          const response = await fetch(anchor.href, {method:'HEAD'});
          return response.ok ? '' : `${anchor.textContent.trim()} HTTP ${response.status}`;
        } catch (error) {
          return `${anchor.textContent.trim()} ${error.message || String(error)}`;
        }
      }));
      return {
        isSkill,
        meta: !isSkill || !!meta,
        config: !config || !!parse('explorer-config'),
        navigationHeader: !!document.querySelector('header[data-skill-header="1"] nav'),
        navigationLinks: document.querySelectorAll('header[data-skill-header="1"] nav a[href]').length,
        visibleNavigationRegions: Array.from(document.querySelectorAll('header[data-skill-header="1"], .sx-topbar')).filter(node => getComputedStyle(node).display !== 'none').length,
        duplicateExplorerHeading: !!document.querySelector('.skill-static') && !!document.querySelector('#explorer .sx-head'),
        themeCapable,
        themes:{dark,light},
        themeChanged:dark.bodyBackground !== light.bodyBackground || dark.surfaceBackground !== light.surfaceBackground,
        colorDependencies:compareThemes(dark, light),
        visibleText: (document.body?.innerText || '').trim().length,
        explorer: !!config,
        mounted: !!document.querySelector('.sx-topbar') && !!document.querySelector('.sx-main'),
        gone: document.querySelectorAll('.sx-dot.gone').length,
        exports,
        sbomEvidence: sbomEvidence ? {
          ready:sbomEvidence.dataset.sbomEvidenceReady === '1',
          error:sbomEvidence.dataset.sbomEvidenceError || '',
          cards:sbomEvidence.querySelectorAll('.sbom-card').length,
          componentRows:sbomEvidence.querySelectorAll('.sbom-components tbody tr').length,
          subjectRows:sbomEvidence.querySelectorAll('tr[data-sbom-subject="1"]').length,
          subjectHints:sbomEvidence.querySelectorAll('tr[data-sbom-subject="1"] [data-license-hint="1"]').length,
          subjectLinks:Array.from(sbomEvidence.querySelectorAll('tr[data-sbom-subject="1"]')).map(row => row.querySelectorAll('a[data-evidence-link]').length),
          ciLinksState:sbomEvidence.querySelector('[data-ci-links-state]')?.dataset.ciLinksState || '',
          ciArtifactLinks:sbomEvidence.querySelectorAll('a[data-evidence-link="ci-artifact"]').length,
          ciComponentRows:sbomEvidence.querySelectorAll('[data-ci-component-preview="1"] tbody tr').length,
          clarificationRows:sbomEvidence.querySelectorAll('[data-license-clarification="1"] tbody tr').length,
          invalidEvidenceLinks,
          deadLocalEvidenceLinks:localEvidenceChecks.filter(Boolean),
          text:sbomEvidence.innerText || '',
          visibleTechnicalTerms:['security_deep_sca','security_image_sca','CycloneDX','SHA-256','artifact path'].filter(term =>
            (sbomEvidence.innerText || '').includes(term)
          ),
        } : null,
        noAssertionView,
      };
    }, { isSkill });
    await page.setViewportSize({ width:390, height:844 });
    await page.waitForTimeout(50);
    const narrow = await page.evaluate(() => {
      const originalTheme = document.documentElement.getAttribute('data-theme');
      const dark = window.__nemoclawThemeSnapshot('dark');
      const light = window.__nemoclawThemeSnapshot('light');
      if (originalTheme === null) document.documentElement.removeAttribute('data-theme');
      else document.documentElement.setAttribute('data-theme', originalTheme);
      return {
        themes:{dark,light},
        themeChanged:dark.bodyBackground !== light.bodyBackground || dark.surfaceBackground !== light.surfaceBackground,
        colorDependencies:window.__nemoclawCompareThemes(dark, light),
        overflows:dark.documentWidth > dark.viewportWidth + 2 || light.documentWidth > light.viewportWidth + 2,
      };
    });
    if (state.isSkill && !state.meta) errors.push('skill-meta did not parse');
    if (state.isSkill && !state.config) errors.push('explorer-config did not parse');
    if (state.isSkill && (!state.navigationHeader || state.navigationLinks < 2)) errors.push('semantic skill navigation header is incomplete');
    if (state.isSkill && state.visibleNavigationRegions !== 1) errors.push(`renderer produced ${state.visibleNavigationRegions} visible navigation headers`);
    if (state.isSkill && state.duplicateExplorerHeading) errors.push('renderer repeated the static SKILL heading');
    if (state.themeCapable && (!state.themeChanged || !narrow.themeChanged)) errors.push('declared theme controls do not change the page palette at every viewport');
    if (state.colorDependencies.length) errors.push(`desktop theme-dependent contrast: ${state.colorDependencies.join('; ')}`);
    if (narrow.colorDependencies.length) errors.push(`narrow theme-dependent contrast: ${narrow.colorDependencies.join('; ')}`);
    if (narrow.overflows) {
      const offenders = narrow.themes.dark.overflowElements.length ? narrow.themes.dark.overflowElements : narrow.themes.light.overflowElements;
      errors.push(`narrow layout overflows 390px viewport (dark ${narrow.themes.dark.documentWidth}px; light ${narrow.themes.light.documentWidth}px): ${offenders.join('; ') || 'unattributed root overflow'}`);
    }
    if (!state.visibleText) errors.push('renderer produced no visible text');
    if (state.isSkill && state.explorer && !state.mounted) errors.push('shared explorer did not mount');
    if (state.isSkill && state.gone) errors.push(`${state.gone} configured file(s) did not load`);
    if (state.isSkill) state.exports.forEach(item => {
      if (!item.present) errors.push(`export ${item.id} preview mount is missing`);
      else if (item.error) errors.push(`export ${item.id} preview failed: ${item.error}`);
      else if (!item.ready) errors.push(`export ${item.id} preview did not become ready`);
      else if (!item.rows) errors.push(`export ${item.id} preview rendered no component rows`);
      else if (item.choiceGroups < 3 || item.choiceCount < 3) errors.push(`export ${item.id} lacks multi-select filter groups`);
      else if (!item.multiChanged) errors.push(`export ${item.id} multi-select filters did not change the visible rows`);
      else if (item.sortButtons !== item.headerCount || !item.allSortDirections) errors.push(`export ${item.id} does not toggle every column between ascending and descending`);
    });
    if (state.sbomEvidence) {
      if (state.sbomEvidence.error) errors.push(`SBOM evidence preview failed: ${state.sbomEvidence.error}`);
      else if (!state.sbomEvidence.ready) errors.push('SBOM evidence preview did not become ready');
      else if (state.sbomEvidence.cards < 3) errors.push('SBOM evidence preview does not distinguish all evidence states');
      else if (!state.sbomEvidence.componentRows) errors.push('linked SBOM rendered no component licenses');
      else if (!state.sbomEvidence.subjectRows
          || state.sbomEvidence.subjectHints !== state.sbomEvidence.subjectRows
          || state.sbomEvidence.subjectLinks.some(count => count < 3)) {
        errors.push('conditional SBOM rows lack declaration, upstream, or license-hint evidence');
      } else if (state.sbomEvidence.invalidEvidenceLinks.length) {
        errors.push(`SBOM evidence contains unusable links: ${state.sbomEvidence.invalidEvidenceLinks.join('; ')}`);
      } else if (state.sbomEvidence.deadLocalEvidenceLinks.length) {
        errors.push(`SBOM evidence contains dead local links: ${state.sbomEvidence.deadLocalEvidenceLinks.join('; ')}`);
      } else if (state.sbomEvidence.ciLinksState === 'available' && state.sbomEvidence.ciArtifactLinks < 3) {
        errors.push('available CI evidence does not link all three generated artifacts');
      } else if (state.sbomEvidence.ciLinksState === 'available' && !state.sbomEvidence.ciComponentRows) {
        errors.push('available CI evidence does not render the linked SBOM component licenses');
      } else if (state.sbomEvidence.ciLinksState === 'available' && !state.sbomEvidence.clarificationRows) {
        errors.push('available CI evidence does not foreground packages needing license clarification');
      } else if (!['available', 'incomplete', 'unavailable'].includes(state.sbomEvidence.ciLinksState)) {
        errors.push('CI artifact evidence lacks an explicit availability state');
      } else if (!/Learners receive these \d+ packages/.test(state.sbomEvidence.text)
          || !state.sbomEvidence.text.includes('Learners do not receive these packages')
          || !state.sbomEvidence.text.includes('Learners do not receive these tools')
          || !state.sbomEvidence.text.includes('Files for auditors and automation')) {
        errors.push('software review does not answer learner delivery before exposing audit detail');
      } else if (state.sbomEvidence.ciLinksState === 'available'
          && (!state.sbomEvidence.text.includes('packages checked')
            || !state.sbomEvidence.text.includes('need package-by-package review'))) {
        errors.push('available package scan does not summarize useful review outcomes');
      } else if (state.sbomEvidence.visibleTechnicalTerms.length) {
        errors.push(`software review exposes implementation jargon before disclosure: ${state.sbomEvidence.visibleTechnicalTerms.join(', ')}`);
      }
    }
    if (state.noAssertionView) {
      if (!state.noAssertionView.unresolved) errors.push('local-authoring view rendered no NOASSERTION rows');
      else if (state.noAssertionView.unresolved !== state.noAssertionView.coveredSubjects) {
        errors.push('NOASSERTION rows and conditional SBOM subjects do not match');
      } else if (state.noAssertionView.brokenLicenseLinks) {
        errors.push('NOASSERTION is rendered as a dead license link');
      } else if (!state.noAssertionView.usefulEvidence) {
        errors.push('NOASSERTION rows omit distribution or immutable-scan guidance');
      }
    }
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
    while (cursor < htmlFiles.length) {
      const file = htmlFiles[cursor++];
      const result = await inspect(browser, file);
      if (result.errors.length) findings.push(result);
    }
  }
  await Promise.all(Array.from({ length: 4 }, worker));
  await browser.close();
  server.close();
  console.log(JSON.stringify({ files:htmlFiles.length, findings }, null, 2));
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
    # Audit the tree actually being served. A Pages build contains projected pages beyond the
    # source set, so reusing a source manifest or a hand-maintained allowlist would silently miss
    # them. Every HTML file is included by default; SKILL-specific assertions are conditional in
    # the browser script, but desktop/narrow theme and layout checks are universal.
    files = discover_html(site)
    if not files:
        print(f"skill_renderer_runtime_audit: FAIL\n  - no HTML files under {site}")
        return 1
    temp_parent = site.parent if args.engine == "apple" else None
    with tempfile.TemporaryDirectory(prefix="skill-renderer-audit-", dir=temp_parent) as temp:
        temp_path = Path(temp)
        script = temp_path / "audit.js"
        manifest = temp_path / "html-files.json"
        script.write_text(RUNTIME_JS, encoding="utf-8")
        manifest.write_text(json.dumps(files), encoding="utf-8")
        if args.engine == "apple":
            command = [
                "container", "machine", "run", "--root", "--name", args.machine,
                "--workdir", str(site),
                "--env", f"NODE_PATH={args.node_path}",
                "--env", f"CHROME_BIN={'' if args.chrome_bin == 'auto' else args.chrome_bin}",
                "--env", f"SITE_ROOT={site}",
                "--env", f"HTML_FILES={manifest}",
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
                "-e", "HTML_FILES=/tmp/html-files.json",
                "-v", f"{site}:/site:ro",
                "-v", f"{script}:/tmp/skill-renderer-audit.js:ro",
                "-v", f"{manifest}:/tmp/html-files.json:ro",
                args.image,
                "/tmp/skill-renderer-audit.js",
            ]
        try:
            environment = os.environ.copy()
            if args.engine == "current":
                environment.update({
                    "NODE_PATH": args.node_path,
                    "CHROME_BIN": "" if args.chrome_bin == "auto" else args.chrome_bin,
                    "SITE_ROOT": str(site),
                    "HTML_FILES": str(manifest),
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
