#!/usr/bin/env node
// Checks the runtime-rendered figures (mountDiagram + mountPolicyMap) that the static
// figure_audit never sees, because they are built by _shared.js in the browser.
//
// Detects:
//   - text that overlaps other text (the policy-map label collision)
//   - text that runs past the figure's own bounds
//   - a connector that crosses a box it does not link, or overlapping node boxes
//   - a "useless" diagram: >=3 boxes, no edges, but framing that implies a relationship
//     (path / trajectory / flow / sequence) and shows none -- a bordered list, not a diagram
//
// SELF-TESTS every detector against a known-bad input and refuses to report clean if any
// fails to fire (a check that cannot fail is a lie). --json prints {checked, findings};
// exits nonzero on any finding.
import fs from "fs"; import path from "path"; import { fileURLToPath } from "url";
import { createRequire } from "module";

const require = createRequire(import.meta.url);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const NEMO = process.env.FIG_NEMO || path.resolve(HERE, "..", "web", "nemoclaw");
// _shared.js must load as ESM (node reads a bare .js as CJS without a package "type"), so we stage
// a .mjs shim of it. The shim has to sit BESIDE the real course modules, not in /tmp: _shared.js
// imports siblings (./_diagram.js, ./_chat.js, ...) by relative path, and those resolve only from
// inside the course dir. Staging in /tmp is what broke once _shared.js was split into modules
// (ERR_MODULE_NOT_FOUND ./_diagram.js). Write it here, import it, and always remove it.
const tmp = path.join(NEMO, ".figcheck_shared.mjs");
fs.writeFileSync(tmp, fs.readFileSync(path.join(NEMO, "_shared.js")));
let shared;
try { shared = await import("file://" + tmp); }
finally { try { fs.unlinkSync(tmp); } catch { /* best-effort cleanup */ } }
const { diagramSVG } = shared;

// jsdom is CJS and ESM import() ignores NODE_PATH, so resolve it via require (FIG_JSDOM = its
// absolute path when installed into a side dir by run_figcheck.sh).
let JSDOM = null;
try { ({ JSDOM } = require(process.env.FIG_JSDOM || "jsdom")); } catch (e) { /* surfaced as a finding below */ }

const MONO = 0.6, SANS = 0.52;       // em-width per char; monospace is wider
// Parse each <text> into an estimated rendered bounding box {l,r,t,b}. The overlap and out-of-bounds
// checks need where text actually lands on screen, which the SVG only gives indirectly (anchor + font
// size + char count), so this reconstructs it. Width is char-count * font-size * an em-width factor.
function textBoxes(svg) {
  const out = [];
  for (const m of svg.matchAll(/<text\b([^>]*)>([^<]*)<\/text>/g)) {
    const a = m[1], txt = m[2].replace(/&[a-z]+;|&#\d+;/g, "x").trim();   // attrs, and entity-normalized text
    if (!txt) continue;
    const fs2 = +(a.match(/font-size="?([\d.]+)/) || [])[1] || 12;
    const x = +(a.match(/\bx="([\d.-]+)"/) || [])[1] || 0;
    const y = +(a.match(/\by="([\d.-]+)"/) || [])[1] || 0;
    const anc = /text-anchor="middle"/.test(a) ? "middle" : /text-anchor="end"/.test(a) ? "end" : "start";
    const w = txt.length * fs2 * (/mono/i.test(a) ? MONO : SANS);   // estimated text width
    const l = anc === "middle" ? x - w / 2 : anc === "end" ? x - w : x;   // left edge depends on the anchor
    out.push({ l, r: l + w, t: y - fs2 * 0.8, b: y + fs2 * 0.25, txt });   // box: y is the baseline, so t is above it
  }
  return out;
}
// The node boxes of a relational diagram: <rect> with the diagram's rounded corner (rx="14").
// Used to test box-on-box overlap and whether a connector passes through a box it does not link.
function boxes14(svg) {
  return [...svg.matchAll(/<rect[^>]*\bx="([\d.]+)"[^>]*\by="([\d.]+)"[^>]*\bwidth="([\d.]+)"[^>]*\bheight="([\d.]+)"[^>]*rx="14"/g)]
    .map((m) => ({ x: +m[1], y: +m[2], w: +m[3], h: +m[4] }));
}
// Cubic bezier point at parameter t, given the 4 control points P.
// Used to sample a connector curve so we can test whether it runs through an unrelated box.
function bez(P, t) { const m = 1 - t; return [
  m*m*m*P[0][0] + 3*m*m*t*P[1][0] + 3*m*t*t*P[2][0] + t*t*t*P[3][0],
  m*m*m*P[0][1] + 3*m*m*t*P[1][1] + 3*m*t*t*P[2][1] + t*t*t*P[3][1]]; }

// Geometry checks on one rendered figure's SVG. This is the core detector: it catches the visual
// defects a student would see but no static text scan can (labels colliding, text spilling past the
// frame, a connector cutting through an unrelated box, overlapping node boxes). Returns a list of
// human-readable problem strings; edge checks run only when the figure is a relational diagram.
function svgProblems(svg, { checkEdges = false } = {}) {
  const out = [], T = textBoxes(svg), E = 1.5;   // erode 1.5px so merely-touching text is fine
  // every pair of text boxes: report if their eroded rectangles intersect (a label collision)
  for (let i = 0; i < T.length; i++) for (let j = i + 1; j < T.length; j++) {
    const A = T[i], B = T[j];
    if (A.l < B.r - E && B.l < A.r - E && A.t < B.b - E && B.t < A.b - E)
      out.push(`text overlaps text: "${A.txt.slice(0, 26)}" / "${B.txt.slice(0, 26)}"`);
  }
  const vb = svg.match(/viewBox="\s*([\d.-]+)\s+([\d.-]+)\s+([\d.]+)\s+([\d.]+)/);
  if (vb) {
    const minx = +vb[1], miny = +vb[2], W = +vb[3], H = +vb[4];   // the figure's own coordinate bounds
    // any text box reaching outside the viewBox (with a 2px tolerance) is clipped on screen
    for (const t of T) if (t.l < minx - 2 || t.r > minx + W + 2 || t.t < miny - 2 || t.b > miny + H + 2)
      out.push(`text past figure bounds: "${t.txt.slice(0, 26)}"`);
  }
  if (checkEdges) {
    const B = boxes14(svg);                       // the diagram's node boxes
    // every pair of boxes: report if they overlap (nodes drawn on top of each other)
    for (let a = 0; a < B.length; a++) for (let b = a + 1; b < B.length; b++) {
      const A = B[a], C = B[b];
      if (A.x < C.x+C.w && C.x < A.x+A.w && A.y < C.y+C.h && C.y < A.y+A.h) out.push("node boxes overlap");
    }
    // each connector path: sample the curve and flag if it passes through a box that is not its endpoint
    for (const m of svg.matchAll(/<path d="M ([\d.]+) ([\d.]+) C ([\d.]+) ([\d.]+), ([\d.]+) ([\d.]+), ([\d.]+) ([\d.]+)"/g)) {
      const P = [[+m[1],+m[2]], [+m[3],+m[4]], [+m[5],+m[6]], [+m[7],+m[8]]];   // the 4 bezier control points
      // the boxes this connector actually links (its start/end land on or near them)
      const ends = B.filter((bx) => { const near = (p) => p[0] >= bx.x-3 && p[0] <= bx.x+bx.w+3 && p[1] >= bx.y-3 && p[1] <= bx.y+bx.h+3; return near(P[0]) || near(P[3]); });
      for (let t = 0.1; t <= 0.9; t += 0.1) { const [x, y] = bez(P, t);   // walk along the curve
        for (const bx of B) { if (ends.includes(bx)) continue;            // skip the boxes it legitimately links
          if (x > bx.x && x < bx.x+bx.w && y > bx.y && y < bx.y+bx.h) { out.push("a connector crosses a box it does not link"); t = 9; break; } } }
    }
  }
  return out;
}

const FLOW = /\b(path|paths|trajector\w*|flow|pipeline|sequence|steps?|then|leads?|chain|into|through|cycle|loop|stages?)\b/i;
// Catch a "diagram" that is really a bordered list: 3+ boxes, zero edges, yet its title/caption
// promises a relationship (path, flow, sequence...). Drawing no edges there teaches the student
// nothing the prose did not, so this flags it for either real edges or a plain list instead.
function uselessSpec(spec) {
  const nodes = spec.nodes || [], edges = spec.edges || [];
  if (nodes.length >= 3 && edges.length === 0) {                 // enough boxes to imply structure, but no connections
    const framing = [spec.kicker, spec.title, spec.caption, spec.aria].filter(Boolean).join(" ");
    const m = framing.match(FLOW);                              // does the framing language promise a relationship?
    if (m) return `${nodes.length} boxes, no edges, but the framing implies a relationship ("${m[0]}") and draws none -- a bordered list, not a diagram`;
  }
  return null;
}

// ---- self-tests: each detector MUST fire on a known-bad input ----
const stOverlap = svgProblems('<svg viewBox="0 0 200 50"><text x="10" y="20" font-size="14" font-family="monospace">overlapping aaa</text><text x="40" y="22" font-size="14" font-family="monospace">overlapping bbb</text></svg>');
const OLD_DOF = { width: 1180, height: 320, boxW: 200, boxH: 96, nodes: [0,1,2,3,4].map((i) => ({ id: "n"+i, label: "n"+i, kind: "data", x: i, y: 0, lines: ["a","b"] })), edges: [{ from: "n0", to: "n2" }, { from: "n2", to: "n4" }] };
const stEdge = svgProblems(diagramSVG(OLD_DOF), { checkEdges: true });
const OLD_TRAJ = { kicker: "A GRANTED CAPABILITY BECOMES A BREACH ALONG A PATH", title: "Three action trajectories",
  nodes: [{ id: "a", label: "a", x: 0, y: 0 }, { id: "b", label: "b", x: 1, y: 0 }, { id: "c", label: "c", x: 2, y: 0 }], edges: [] };
const selftests = [
  ["text-overlap", stOverlap.some((p) => /text overlaps text/.test(p))],
  ["edge-cross-box", stEdge.some((p) => /crosses a box/.test(p))],
  ["useless-diagram", !!uselessSpec(OLD_TRAJ)],
];
const broken = selftests.filter(([, ok]) => !ok);
if (broken.length) { console.error("check_figures: SELF-TEST FAILED for " + broken.map((b) => b[0]).join(", ") + "; refusing to report clean."); process.exit(2); }

function extract(src) {
  const out = []; let i = 0;
  while ((i = src.indexOf("mountDiagram(", i)) >= 0) {
    let j = src.indexOf("{", i); if (j < 0) break; let d = 0, k = j, s = null;
    for (; k < src.length; k++) { const c = src[k];
      if (s) { if (c === "\\") { k++; continue; } if (c === s) s = null; continue; }
      if (c === '"' || c === "'" || c === "`") { s = c; continue; }
      if (c === "{") d++; else if (c === "}") { d--; if (d === 0) { k++; break; } } }
    const sel = (src.slice(i, j).match(/["'`](#[^"'`]+)/) || [])[1] || "?";
    try { out.push({ sel, spec: (0, eval)("(" + src.slice(j, k) + ")") }); }
    catch (e) { out.push({ sel, err: String(e.message || e).slice(0, 80) }); }
    i = k;
  }
  return out;
}

const findings = []; let checked = 0;
for (const f of fs.readdirSync(NEMO).filter((f) => /\.html$/.test(f)).sort()) {
  const pageSrc = fs.readFileSync(path.join(NEMO, f), "utf8");
  for (const { sel, spec, err } of extract(pageSrc)) {
    checked++; const page = "web/nemoclaw/" + f;
    if (err) { findings.push({ page, sel, detail: "spec did not parse: " + err }); continue; }
    // a mount whose target div is absent renders nothing -- a dead call, or a leftover after
    // the figure was replaced (e.g. by a table). Flag it and do not "validate" a phantom.
    if (sel.startsWith("#") && !pageSrc.includes(`id="${sel.slice(1)}"`)) {
      findings.push({ page, sel, detail: `mount target ${sel} has no element on the page; this figure never renders (dead mount or leftover after a replacement)` });
      continue;
    }
    const u = uselessSpec(spec); if (u) findings.push({ page, sel, detail: u });
    for (const p of svgProblems(diagramSVG(spec), { checkEdges: true })) findings.push({ page, sel, detail: p });
  }
}

// mountPolicyMap is built from the DOM, so it needs jsdom; failing to check it is loud, not silent.
const PM = { page: "web/nemoclaw/_shared.js", sel: "mountPolicyMap" };
if (!JSDOM) {
  findings.push({ ...PM, detail: "could not check: jsdom unavailable (install it so the policy map is rendered and verified)" });
} else {
  try {
    const dom = new JSDOM('<!doctype html><div id="pm"></div>', { pretendToBeVisual: true });
    global.window = dom.window; global.document = dom.window.document; global.navigator = dom.window.navigator;
    shared.mountPolicyMap("#pm");
    const wrap = dom.window.document.querySelector("#pm .pmap-svg");
    const svg = wrap ? wrap.innerHTML : "";
    if (!svg) findings.push({ ...PM, detail: "produced no SVG" });
    else { checked++; for (const p of svgProblems(svg)) findings.push({ ...PM, detail: p }); }
  } catch (e) { findings.push({ ...PM, detail: "render error: " + String(e.message || e).slice(0, 80) }); }
}

if (process.argv.includes("--json")) process.stdout.write(JSON.stringify({ checked, findings }) + "\n");
else { for (const x of findings) console.log(`  ${x.page} ${x.sel}: ${x.detail}`); console.log(`\ncheck_figures: ${checked} figure(s), ${findings.length} problem(s)`); }
process.exit(findings.length ? 1 : 0);
