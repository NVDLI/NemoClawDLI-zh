#!/usr/bin/env node
// Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

/** Capture repository-owned browser surfaces used by the stakeholder deck.
 *
 * The captures are evidence, not decorative stock images. Each entry names the
 * exact page and viewport/element that the slide discusses. Run against a
 * Pages build so relative assets and generated report data match deployment.
 *
 * Usage:
 *   node scripts/build/capture_repository_overview.mjs \
 *     --base-url http://127.0.0.1:8012 \
 *     --out docs/assets/repository-overview \
 *     --browser /path/to/chromium
 */
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

function args(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 2) {
    const key = argv[i]?.replace(/^--/, "");
    if (!key || argv[i + 1] === undefined) throw new Error(`invalid argument near ${argv[i]}`);
    out[key] = argv[i + 1];
  }
  return out;
}

const opt = args(process.argv.slice(2));
const baseUrl = (opt["base-url"] || "http://127.0.0.1:8000").replace(/\/$/, "");
const outDir = path.resolve(opt.out || "docs/assets/repository-overview");
const browserPath = opt.browser || process.env.PLAYWRIGHT_BROWSER || undefined;
const moduleName = opt.playwright || process.env.PLAYWRIGHT_CORE || "playwright-core";
const { chromium } = require(moduleName);

const captures = [
  {
    file: "course-home.png",
    page: "/nemoclaw/index.html",
    wait: ".module-grid",
    selector: ".hero",
    talkingPoint: "The canonical title and course promise appear before setup or implementation detail.",
  },
  {
    file: "course-map.png",
    page: "/nemoclaw/index.html",
    wait: ".module-grid",
    selector: ".module-grid",
    talkingPoint: "Four modules carry the learner from an agent loop to runtime containment.",
  },
  {
    file: "module-2-workflow.png",
    page: "/nemoclaw/02a-routing.html",
    wait: ".pattern-grid",
    selector: ".pattern-grid",
    talkingPoint: "Part A compares when the model chooses work and when deterministic code executes it.",
  },
  {
    file: "module-2-deep-research.png",
    page: "/nemoclaw/02c-deep.html",
    wait: ".deep-stages",
    selector: ".deep-stages",
    talkingPoint: "Part C exposes planning, isolated investigation, shared evidence, and synthesis as separate stages.",
  },
  {
    file: "browser-artifact.png",
    page: "/nemoclaw/02c-deep.html",
    wait: "#deep-artifact > *",
    selector: "#deep-artifact",
    talkingPoint: "The browser exposes a runnable deep-research interface while keeping its source available in the adjacent RunCell.",
  },
  {
    file: "protocol-surfaces.png",
    page: "/nemoclaw/03a-kickstart.html",
    wait: ".hero figure svg",
    selector: ".hero figure",
    talkingPoint: "The rendered course page distinguishes request-response APIs, MCP tool transport, and the persistent OpenClaw gateway.",
  },
  {
    file: "openclaw-workspace.png",
    page: "/nemoclaw/03b-openclaw.html",
    wait: ".hero figure svg",
    selector: ".hero figure",
    talkingPoint: "Part 3b shows how OpenClaw workspace files shape the next agent turn.",
  },
  {
    file: "openclaw-triggers.png",
    page: "/nemoclaw/03c-always-on.html",
    wait: ".hero .fig-embed svg",
    selector: ".hero .fig-embed",
    talkingPoint: "Part 3c adds skills and scheduled triggers to the same persistent OpenClaw runtime.",
  },
  {
    file: "openshell-boundary.png",
    page: "/nemoclaw/04a-safety.html",
    wait: ".architecture-map svg",
    selector: ".architecture-map",
    talkingPoint: "OpenShell owns gateway, policy, network, model-routing, and tool boundaries outside the agent harness.",
  },
  {
    file: "localization-studio.png",
    page: "/nemoclaw/localization.html",
    wait: ".loc-page",
    talkingPoint: "Localization Studio compares English and Portuguese on the same branch and surfaces source drift.",
  },
  {
    file: "validation-report.png",
    page: "/validation.html",
    wait: ".rp-main",
    talkingPoint: "The browser report exposes the rule, implementation source, severity, and exact findings behind each gate.",
  },
];

await fs.mkdir(outDir, { recursive: true });
const browser = await chromium.launch({ headless: true, executablePath: browserPath });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
await context.addInitScript(() => {
  localStorage.setItem("theme", "dark");
});
const page = await context.newPage();
await page.route("**/*", async (route) => {
  const url = new URL(route.request().url());
  if (url.hostname === "127.0.0.1" || url.hostname === "localhost") await route.continue();
  else await route.abort();
});

const records = [];
for (const capture of captures) {
  const url = baseUrl + capture.page;
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await page.waitForSelector(capture.wait, { state: "visible", timeout: 15000 });
  await page.evaluate(() => window.scrollTo(0, 0));
  const target = path.join(outDir, capture.file);
  if (capture.selector) {
    const locator = page.locator(capture.selector).first();
    await locator.scrollIntoViewIfNeeded();
    await locator.screenshot({ path: target });
  } else {
    await page.screenshot({ path: target, fullPage: false });
  }
  const size = await fs.stat(target);
  records.push({ ...capture, url, bytes: size.size });
  process.stdout.write(`captured ${capture.file} (${size.size} bytes)\n`);
}

await browser.close();
await fs.writeFile(
  path.join(outDir, "captures.json"),
  JSON.stringify({ schema: "nemoclaw-slide-captures/1", baseUrl, captures: records }, null, 2) + "\n",
);
