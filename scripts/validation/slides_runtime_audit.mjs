#!/usr/bin/env node
/** Render every hosted repository-overview slide and reject visible overflow.
 *
 * This is the browser half of slides_audit.py. It checks the actual HTML deck:
 * every image decodes, every slide fits its 16:9 stage, navigation reaches each
 * hash, and speaker notes can be opened. Screenshots remain scratch evidence.
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
const url = opt.url || "http://127.0.0.1:8011/docs/repository-overview.html";
const outDir = path.resolve(opt.out || "/tmp/nemoclaw-slide-runtime");
const browserPath = opt.browser || process.env.PLAYWRIGHT_BROWSER || undefined;
const moduleName = opt.playwright || process.env.PLAYWRIGHT_CORE || "playwright-core";
const { chromium } = require(moduleName);

await fs.mkdir(outDir, { recursive: true });
const browser = await chromium.launch({ headless: true, executablePath: browserPath });
const context = await browser.newContext({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });
const page = await context.newPage();
await page.goto(url, { waitUntil: "networkidle" });
await page.waitForSelector(".slide.on");

const count = await page.locator(".slide").count();
const failures = [];
const records = [];
for (let index = 1; index <= count; index += 1) {
  await page.goto(`${url.split("#")[0]}#${index}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(400);
  const current = page.locator(".slide.on");
  const state = await current.evaluate((slide) => {
    const stage = document.getElementById("stage").getBoundingClientRect();
    const images = [...slide.querySelectorAll("img")].map((img) => ({
      src: img.getAttribute("src"), complete: img.complete, naturalWidth: img.naturalWidth,
      rect: img.getBoundingClientRect().toJSON(),
    }));
    const outside = [...slide.querySelectorAll("h1,h2,p,li,strong,code,img,figcaption")]
      .map((node) => ({ tag: node.tagName, text: (node.textContent || "").trim().slice(0, 90), rect: node.getBoundingClientRect().toJSON() }))
      .filter((item) => item.rect.left < stage.left - 1 || item.rect.right > stage.right + 1
        || item.rect.top < stage.top - 1 || item.rect.bottom > stage.bottom + 1);
    const title = slide.querySelector("h1,h2");
    const titleRange = document.createRange();
    titleRange.selectNodeContents(title);
    const titleLines = [...titleRange.getClientRects()].filter((rect) => rect.width > 0 && rect.height > 0).length;
    const visual = slide.querySelector(".visual > *");
    const header = slide.querySelector("header");
    const footer = slide.querySelector("footer");
    const visualRect = visual?.getBoundingClientRect().toJSON() || null;
    const headerRect = header?.getBoundingClientRect().toJSON() || null;
    const footerRect = footer?.getBoundingClientRect().toJSON() || null;
    const layout = [...slide.classList].find((name) => name.startsWith("layout-"))?.slice(7) || "title";
    return {
      id: slide.dataset.slideId,
      scrollWidth: slide.scrollWidth,
      clientWidth: slide.clientWidth,
      scrollHeight: slide.scrollHeight,
      clientHeight: slide.clientHeight,
      images,
      outside,
      title: (title.textContent || "").trim(),
      titleLines,
      visualRect,
      headerRect,
      footerRect,
      layout,
    };
  });
  const activeIndex = await page.locator(".slide").evaluateAll((slides) => slides.findIndex((slide) => slide.classList.contains("on")) + 1);
  if (activeIndex !== index) failures.push(`hash #${index} activated slide ${activeIndex}`);
  if (state.scrollWidth > state.clientWidth + 1 || state.scrollHeight > state.clientHeight + 1) {
    failures.push(`${state.id}: slide overflow ${state.scrollWidth}x${state.scrollHeight} > ${state.clientWidth}x${state.clientHeight}`);
  }
  if (state.titleLines !== 1) failures.push(`${state.id}: title spans ${state.titleLines} rendered lines: ${state.title}`);
  if (state.visualRect && state.headerRect && state.footerRect) {
    const stageHeight = state.clientHeight;
    const headerGap = state.visualRect.top - state.headerRect.bottom;
    const footerGap = state.footerRect.top - state.visualRect.bottom;
    const screenshot = state.layout === "screenshot";
    const maxGap = stageHeight * (screenshot ? 0.24 : 0.20);
    const minBody = stageHeight * (screenshot ? 0.25 : 0.30);
    if (headerGap > maxGap) failures.push(`${state.id}: excessive header-to-body gap ${headerGap.toFixed(1)}px`);
    if (footerGap > maxGap) failures.push(`${state.id}: excessive body-to-footer gap ${footerGap.toFixed(1)}px`);
    if (state.visualRect.height < minBody) failures.push(`${state.id}: visual body occupies only ${state.visualRect.height.toFixed(1)}px`);
  }
  for (const image of state.images) {
    if (!image.complete || image.naturalWidth < 1) failures.push(`${state.id}: image failed to decode: ${image.src}`);
  }
  for (const item of state.outside) failures.push(`${state.id}: ${item.tag} outside stage: ${item.text}`);
  const file = `slide-${String(index).padStart(2, "0")}-${state.id}.png`;
  await page.locator("#stage").screenshot({ path: path.join(outDir, file) });
  records.push({ index, file, ...state });
}

await page.goto(`${url.split("#")[0]}#1`, { waitUntil: "networkidle" });
await page.keyboard.press("n");
if (!(await page.locator("#notes").isVisible())) failures.push("speaker notes do not open with N");
await browser.close();

await fs.writeFile(path.join(outDir, "runtime.json"), JSON.stringify({ schema: "nemoclaw-slide-runtime/1", url, count, failures, slides: records }, null, 2) + "\n");
if (failures.length) {
  for (const failure of failures) process.stderr.write(`slides_runtime_audit: ${failure}\n`);
  process.exit(1);
}
process.stdout.write(`slides_runtime_audit: PASS (${count} slides)\n`);
