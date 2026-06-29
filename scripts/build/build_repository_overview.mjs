#!/usr/bin/env node
/** Build docs/repository-overview.pptx from the shared slide manifest.
 *
 * Run this module from an artifact-tool workspace initialized by the
 * Presentations skill. The HTML and PPTX builders deliberately share content,
 * evidence paths, screenshots, order, and speaker notes through one manifest.
 */
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

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
const root = path.resolve(opt.root || process.cwd());
const manifestPath = path.resolve(opt.manifest || path.join(root, "docs", "repository-overview.slides.json"));
const outputPath = path.resolve(opt.out || path.join(root, "docs", "repository-overview.pptx"));
const scratch = path.resolve(opt.scratch || path.join(process.cwd(), "output"));
const manifest = JSON.parse(await fs.readFile(manifestPath, "utf8"));

const C = {
  green: "#76b900", greenDark: "#4a7a00", greenSoft: "#eef6e4",
  ink: "#1a1a1a", gray: "#5e5e5e", faint: "#8c8c8c", line: "#d4d4d4",
  soft: "#f5f7f2", blue: "#0969da", purple: "#6f42c1", rust: "#c2410c", white: "#ffffff",
};
const W = 1280;
const H = 720;
const M = 76;

function addRect(slide, name, left, top, width, height, fill, line = "none", lineWidth = 0) {
  return slide.shapes.add({
    geometry: "rect", name, position: { left, top, width, height }, fill,
    line: { style: "solid", fill: line, width: lineWidth },
  });
}

function addText(slide, name, text, left, top, width, height, size, color = C.ink, bold = false, alignment = "left") {
  const shape = slide.shapes.add({
    geometry: "textbox", name, position: { left, top, width, height }, fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = { fontSize: size, fontFamily: "Arial", color, bold, alignment };
  return shape;
}

async function bytes(rel) {
  const data = await fs.readFile(path.join(root, rel));
  return data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength);
}

function chrome(slide, slideSpec, index, total) {
  addText(slide, "brand", "NVIDIA Deep Learning Institute", M, 32, 420, 22, 13, C.ink, true);
  addRect(slide, "brand-green-rule", M, 62, 165, 3, C.green);
  addRect(slide, "brand-rule", M + 165, 62, W - 2 * M - 165, 2, "#e9e9e9");
  addText(slide, "kicker", slideSpec.kicker.toUpperCase(), M, 92, 1128, 24, 14, C.greenDark, true);
  addText(slide, "slide-title", slideSpec.title, M, 118, 1128, 90, 38, C.ink, true);
  if (slideSpec.lead) addText(slide, "slide-lead", slideSpec.lead, M, 207, 1128, 54, 18, C.gray);
  addText(slide, "footer-title", manifest.title, M, 689, 520, 16, 10, C.faint);
  addText(slide, "footer-number", `${index} / ${total}`, 1110, 689, 90, 16, 10, C.faint, false, "right");
  addRect(slide, "progress", 0, 716, W * index / total, 4, C.green);
}

function talkingPoints(slide, items, left, top, width, rowHeight = 58) {
  items.forEach((item, i) => {
    const y = top + i * rowHeight;
    addRect(slide, `point-${i + 1}-mark`, left, y + 9, 7, 7, C.green);
    addText(slide, `point-${i + 1}`, item, left + 22, y, width - 22, rowHeight - 4, 16, C.gray);
    addRect(slide, `point-${i + 1}-rule`, left + 22, y + rowHeight - 5, width - 22, 1, C.line);
  });
}

async function screenshotSlide(slide, spec) {
  const visual = spec.visual;
  addRect(slide, "screenshot-frame", M, 300, 735, 300, "#0d0d0d", "#3f3f3f", 1);
  slide.images.add({
    blob: await bytes(visual.asset), contentType: "image/png", alt: visual.alt, fit: "contain",
    position: { left: M + 8, top: 308, width: 719, height: 284 },
  });
  addText(slide, "screenshot-caption", visual.caption, M, 610, 735, 40, 16, C.faint);
  talkingPoints(slide, visual.points, 850, 322, 350, visual.points.length > 3 ? 54 : 70);
}

function sequenceSlide(slide, spec) {
  const items = spec.visual.items;
  const gap = 34;
  const boxW = (1128 - gap * (items.length - 1)) / items.length;
  items.forEach((item, i) => {
    const x = M + i * (boxW + gap);
    addRect(slide, `sequence-${i + 1}-box`, x, 320, boxW, 175, C.soft, C.line, 1);
    addRect(slide, `sequence-${i + 1}-rule`, x, 320, boxW, 5, C.green);
    addText(slide, `sequence-${i + 1}-label`, item.label, x + 18, 347, boxW - 36, 32, 20, C.ink, true);
    addText(slide, `sequence-${i + 1}-detail`, item.detail, x + 18, 389, boxW - 36, 86, 16, C.gray);
    if (i < items.length - 1) addText(slide, `sequence-${i + 1}-arrow`, "→", x + boxW + 4, 382, 26, 34, 24, C.greenDark, true, "center");
  });
  addText(slide, "sequence-outcome", spec.visual.outcome, 180, 535, 920, 54, 18, C.greenDark, true, "center");
}

async function comparisonSlide(slide, spec) {
  const visual = spec.visual;
  addRect(slide, "comparison-frame", M, 305, 650, 300, "#0d0d0d", "#3f3f3f", 1);
  const imageGap = 8;
  const imageW = (634 - imageGap) / 2;
  for (let i = 0; i < visual.images.length; i += 1) {
    const item = visual.images[i];
    slide.images.add({
      blob: await bytes(item.asset), contentType: "image/png", alt: item.alt, fit: "contain",
      position: { left: M + 8 + i * (imageW + imageGap), top: 313, width: imageW, height: 284 },
    });
  }
  addRect(slide, "comparison-rule", 760, 325, 4, 260, C.green);
  visual.items.forEach((item, i) => {
    const y = 325 + i * 86;
    addText(slide, `comparison-${i + 1}-label`, item.label, 785, y, 400, 28, 19, C.ink, true);
    addText(slide, `comparison-${i + 1}-detail`, item.detail, 785, y + 31, 400, 48, 16, C.gray);
    addRect(slide, `comparison-${i + 1}-line`, 785, y + 78, 400, 1, C.line);
  });
}

function gatesSlide(slide, spec) {
  const items = spec.visual.steps;
  const gap = 18;
  const boxW = (1128 - gap * (items.length - 1)) / items.length;
  items.forEach((item, i) => {
    const x = M + i * (boxW + gap);
    addRect(slide, `gate-${i + 1}`, x, 315, boxW, 245, C.white, C.line, 1);
    addRect(slide, `gate-${i + 1}-rule`, x, 315, boxW, 5, C.green);
    addText(slide, `gate-${i + 1}-number`, String(i + 1).padStart(2, "0"), x + 13, 338, boxW - 26, 34, 25, "#d8e8c6", true);
    addText(slide, `gate-${i + 1}-label`, item.label, x + 13, 380, boxW - 26, 30, 17, C.ink, true);
    addText(slide, `gate-${i + 1}-detail`, item.detail, x + 13, 422, boxW - 26, 110, 16, C.gray);
    if (i < items.length - 1) addText(slide, `gate-${i + 1}-arrow`, "→", x + boxW - 1, 409, gap + 2, 26, 17, C.faint, true, "center");
  });
}

function layersSlide(slide, spec) {
  spec.visual.items.forEach((item, i) => {
    const y = 305 + i * 73;
    addText(slide, `layer-${i + 1}-number`, String(i + 1), 92, y, 50, 42, 26, "#d8e8c6", true);
    addText(slide, `layer-${i + 1}-label`, item.label, 160, y + 3, 245, 32, 18, C.ink, true);
    addText(slide, `layer-${i + 1}-detail`, item.detail, 430, y + 2, 745, 52, 16, C.gray);
    addRect(slide, `layer-${i + 1}-rule`, 92, y + 61, 1083, 1, C.line);
  });
}

function treeSlide(slide, spec) {
  addRect(slide, "tree-rule", 170, 307, 5, 290, C.green);
  addText(slide, "tree-root", spec.visual.root, 205, 305, 900, 38, 23, C.ink, true);
  spec.visual.items.forEach((item, i) => {
    const y = 358 + i * 58;
    addText(slide, `tree-${i + 1}-label`, item.label, 205, y, 250, 28, 17, C.greenDark, true);
    addText(slide, `tree-${i + 1}-detail`, item.detail, 475, y, 660, 40, 16, C.gray);
    addRect(slide, `tree-${i + 1}-rule`, 205, y + 44, 930, 1, C.line);
  });
}

function lanesSlide(slide, spec) {
  const colors = [C.green, C.blue, C.rust];
  spec.visual.lanes.forEach((item, i) => {
    const y = 330 + i * 84;
    addRect(slide, `lane-${i + 1}`, 110, y, 1040, 68, C.soft);
    addRect(slide, `lane-${i + 1}-rule`, 110, y, 5, 68, colors[i]);
    addText(slide, `lane-${i + 1}-label`, item.label, 140, y + 17, 210, 28, 18, C.ink, true);
    addText(slide, `lane-${i + 1}-detail`, item.detail, 370, y + 12, 590, 44, 16, C.gray);
    addText(slide, `lane-${i + 1}-status`, item.status, 985, y + 20, 130, 24, 16, colors[i], true, "right");
  });
}

function reviewSlide(slide, spec) {
  addRect(slide, "review-rule", 100, 310, 5, 285, C.green);
  spec.visual.items.forEach((item, i) => {
    const y = 315 + i * 66;
    addText(slide, `review-${i + 1}-label`, item.label, 130, y, 180, 28, 18, C.ink, true);
    addText(slide, `review-${i + 1}-path`, item.path, 330, y + 2, 315, 25, 16, C.greenDark, true);
    addText(slide, `review-${i + 1}-detail`, item.detail, 670, y, 470, 42, 16, C.gray);
    addRect(slide, `review-${i + 1}-rule`, 130, y + 52, 1010, 1, C.line);
  });
}

const presentation = Presentation.create({ slideSize: { width: W, height: H } });
for (let index = 0; index < manifest.slides.length; index += 1) {
  const spec = manifest.slides[index];
  const slide = presentation.slides.add();
  slide.background.fill = C.white;
  if (spec.layout === "title") {
    addText(slide, "title-brand", spec.kicker, M, 54, 500, 28, 16, C.ink, true);
    addRect(slide, "title-rule", M, 260, 190, 6, C.green);
    addText(slide, "deck-title", spec.title, M, 318, 1128, 70, 50, C.ink, true);
    addText(slide, "deck-subtitle", spec.lead, M, 455, 1000, 45, 25, C.greenDark, true);
    addText(slide, "publication-note", spec.footer, M, 650, 880, 24, 12, C.faint);
    addRect(slide, "progress", 0, 716, W / manifest.slides.length, 4, C.green);
  } else {
    chrome(slide, spec, index + 1, manifest.slides.length);
    if (spec.layout === "screenshot") await screenshotSlide(slide, spec);
    else if (spec.layout === "sequence") sequenceSlide(slide, spec);
    else if (spec.layout === "comparison") await comparisonSlide(slide, spec);
    else if (spec.layout === "gates") gatesSlide(slide, spec);
    else if (spec.layout === "layers") layersSlide(slide, spec);
    else if (spec.layout === "tree") treeSlide(slide, spec);
    else if (spec.layout === "lanes") lanesSlide(slide, spec);
    else if (spec.layout === "review") reviewSlide(slide, spec);
  }
  slide.speakerNotes.textFrame.setText(spec.notes);
  slide.speakerNotes.setVisible(true);
}

await fs.mkdir(scratch, { recursive: true });
for (const [index, slide] of presentation.slides.items.entries()) {
  const stem = `slide-${String(index + 1).padStart(2, "0")}`;
  const png = await presentation.export({ slide, format: "png", scale: 1 });
  await fs.writeFile(path.join(scratch, `${stem}.png`), new Uint8Array(await png.arrayBuffer()));
  const layout = await slide.export({ format: "layout" });
  await fs.writeFile(path.join(scratch, `${stem}.layout.json`), await layout.text());
}
const montage = await presentation.export({ format: "webp", montage: true, scale: 1 });
await fs.writeFile(path.join(scratch, "deck-montage.webp"), new Uint8Array(await montage.arrayBuffer()));
const inspection = await presentation.inspect({ kind: "slide,textbox,shape,image,notes,layout", maxChars: 100000 });
await fs.writeFile(path.join(scratch, "inspect.ndjson"), inspection.ndjson);
const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(outputPath);
// artifact-tool may emit an inspection sidecar beside a saved PPTX. The builder
// already writes inspection data under scratch, so keep the repository output clean.
await fs.rm(`${outputPath}.inspect.ndjson`, { force: true });
process.stdout.write(`wrote ${outputPath}\n`);
