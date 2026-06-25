// _diagram.js holds the data-driven diagram grammar that used to live in _shared.js.
// Cells call helpers.viz.diagram(spec) with nodes/edges instead of hand-rolled SVG.
const _DG_MONO = "ui-monospace, SFMono-Regular, Menlo, monospace";
const _DG_SANS = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
const _dgEsc = (s) => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

// SVG <text> does not wrap. Greedily pack words into lines of <= maxChars so a
// long caption stacks instead of overflowing the canvas width.
function _dgWrap(text, maxChars) {
  const words = String(text).split(/\s+/);
  const lines = [];
  let cur = "";
  for (const w of words) {
    if (cur && (cur.length + 1 + w.length) > maxChars) { lines.push(cur); cur = w; }
    else cur = cur ? cur + " " + w : w;
  }
  if (cur) lines.push(cur);
  return lines;
}

// Diagram colors are emitted as CSS var() references, never resolved at render time, so a figure
// re-themes the instant <html data-theme> flips, with no re-render. This is the same mechanism the
// inline var(--gfx-*) page figures use, and it covers BOTH always-on page diagrams AND diagrams
// rendered into cell output, which a render-time bake (the old getComputedStyle read) would leave
// frozen on whatever theme was active when the cell ran. Box/canvas tones reuse the page palette
// (--bg/--e1/--e2/--bd/--tx/--td/--tf); arrow and the kind hues are curated extras defined as --dg-*
// in _style.css (dark :root + the light override) and _lite_overlay.css (the baked edX export). The
// hex fallbacks hold a sane dark palette where no stylesheet is present (headless geometry checks).
function _dgTheme() {
  return {
    bg: "var(--bg,#0d0d0d)", e1: "var(--e1,#161616)", e2: "var(--e2,#1e1e1e)",
    bd: "var(--bd,#2a2a2a)", tx: "var(--tx,#f2f2f2)", td: "var(--td,#b0b0b0)",
    tf: "var(--tf,#6a6a6a)", arrow: "var(--dg-arrow,#8a8a8a)",
    kinds: {
      env: "var(--dg-env,#4b9fff)", agent: "var(--dg-agent,#8ecc2f)",
      tool: "var(--dg-tool,#a78bfa)", data: "var(--dg-data,#e0a83a)",
      model: "var(--dg-model,#2dd4bf)", neutral: "var(--dg-neutral,#9aa0a6)",
    },
  };
}

function _dgLayout(spec) {
  const boxW = spec.boxW || 240, boxH = spec.boxH || 140;
  const padX = 64, top = 28, rowGap = spec.rowGap || 48;
  const cols = Math.max(...spec.nodes.map((n) => n.x)) + 1;
  const rows = Math.max(...spec.nodes.map((n) => n.y)) + 1;
  const W = spec.width || Math.max(640, padX * 2 + cols * boxW + (cols - 1) * 152);
  const gapX = cols > 1 ? (W - padX * 2 - cols * boxW) / (cols - 1) : 0;
  // header band is gone, so explicit heights shed the ~64px it used to reserve.
  const H = spec.height ? spec.height - 64 : (top + rows * boxH + (rows - 1) * rowGap + 52);
  const at = {};
  for (const n of spec.nodes) {
    const x = cols > 1 ? padX + n.x * (boxW + gapX) : (W - boxW) / 2;
    const y = top + n.y * (boxH + rowGap);
    at[n.id] = { x, y, w: boxW, h: boxH, cx: x + boxW / 2, cy: y + boxH / 2 };
  }
  return { boxW, boxH, W, H, at };
}

function _dgBox(n, g, t) {
  const kc = t.kinds[n.kind] || t.kinds.neutral;
  const { x, y, w } = g.at[n.id];
  const cx = x + w / 2;
  const lines = (n.lines || []).map((s, i) =>
    `<text x="${cx}" y="${y + 60 + i * 21}" text-anchor="middle" font-size="12" ` +
    `font-family="${_DG_MONO}" fill="${t.td}">${_dgEsc(s)}</text>`).join("");
  const socket = (() => {
    if (!n.socket) return "";
    // Size the pill to the label (not a fixed inset) so it never clips,
    // centered on the box and capped so it stays inside the card.
    const sw = Math.min(w - 12, Math.max(w - 84, n.socket.length * 7.0 + 24));
    const sx = cx - sw / 2;
    return `<rect x="${sx}" y="${y + g.boxH - 39}" width="${sw}" height="36" rx="18" ` +
      `fill="${t.bg}" stroke="${kc}" stroke-width="1.5" opacity="0.9"/>` +
      `<text x="${cx}" y="${y + g.boxH - 17}" text-anchor="middle" font-size="12" ` +
      `font-family="${_DG_MONO}" fill="${kc}" font-weight="700">${_dgEsc(n.socket)}</text>`;
  })();
  return (
    `<g filter="url(#fig-shadow)"><rect x="${x}" y="${y}" width="${w}" height="${g.boxH}" ` +
    `rx="14" fill="${t.e2}" stroke="${kc}" stroke-width="2"/></g>` +
    `<text x="${cx}" y="${y + 34}" text-anchor="middle" font-size="17" font-family="${_DG_MONO}" ` +
    `fill="${kc}" font-weight="800">${_dgEsc(n.label)}</text>` + lines + socket
  );
}

// An edge renders in two layers: the connector path (drawn under the boxes)
// and the label chip (drawn over the boxes so a tight layout never hides it).
// _dgEdge returns { path, chip } and diagramSVG composites the layers.
function _dgEdgeLabelChip(mx, my, label, kc, t) {
  if (!label) return "";
  // Size the pill to the text instead of a fixed 64px, so longer labels
  // ("read every turn", "denied: EACCES / 403") are not clipped.
  const w = Math.max(46, label.length * 7.1 + 18);
  return `<rect x="${mx - w / 2}" y="${my - 13}" width="${w}" height="26" rx="13" fill="${t.e1}" stroke="${t.bd}"/>` +
    `<text x="${mx}" y="${my + 4}" text-anchor="middle" font-size="12" font-family="${_DG_MONO}" ` +
    `fill="${kc}" font-style="italic">${_dgEsc(label)}</text>`;
}

function _dgEdge(e, g, t) {
  const a = g.at[e.from], b = g.at[e.to];
  const kc = t.kinds[e.tint] || t.arrow;
  if (e.from === e.to) {
    const rx = a.x + a.w - 4;
    return { path: `<path d="M ${rx} ${a.y + 74} C ${rx + 40} ${a.y + 80}, ${rx + 40} ${a.y + 118}, ${rx} ${a.y + 122}" ` +
      `stroke="${kc}" stroke-width="1.8" fill="none" marker-end="url(#fig-arrow)"/>`, chip: "" };
  }
  if (Math.abs(a.cx - b.cx) < 1) {
    const down = a.cy <= b.cy;
    const ax = a.cx, bx = b.cx;
    const ay = down ? a.y + a.h : a.y;
    const by = down ? b.y : b.y + b.h;
    const bend = down ? 34 : -34;
    const my = (ay + by) / 2;
    const path = `<path d="M ${ax} ${ay} C ${ax} ${ay + bend}, ${bx} ${by - bend}, ${bx} ${by}" ` +
      `stroke="${t.arrow}" stroke-width="2.2" fill="none" marker-end="url(#fig-arrow)"/>`;
    return { path, chip: _dgEdgeLabelChip(ax, my, e.label, kc, t) };
  }
  const aLeftOfB = a.cx <= b.cx;
  const top = e.side !== "bottom";
  const ay = top ? a.y + 32 : a.y + a.h - 32;
  const by = top ? b.y + 32 : b.y + b.h - 32;
  const ax = aLeftOfB ? a.x + a.w : a.x;
  const bx = aLeftOfB ? b.x : b.x + b.w;
  const dir = aLeftOfB ? 1 : -1;
  const lift = top ? -22 : 22;
  const mx = (ax + bx) / 2, my = ay + lift;
  const path = `<path d="M ${ax} ${ay} C ${ax + 32 * dir} ${ay + lift}, ${bx - 32 * dir} ${by + lift}, ${bx} ${by}" ` +
    `stroke="${t.arrow}" stroke-width="2.2" fill="none" marker-end="url(#fig-arrow)"/>`;
  return { path, chip: _dgEdgeLabelChip(mx, top ? my - 8 : my + 8, e.label, kc, t) };
}

function _dgDefs(t) {
  return `<defs>` +
    `<marker id="fig-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto">` +
    `<path d="M0,0 L10,5 L0,10 Z" fill="${t.arrow}"/></marker>` +
    `<filter id="fig-shadow" x="-20%" y="-20%" width="140%" height="140%">` +
    `<feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#000000" flood-opacity="0.28"/></filter>` +
    `</defs>`;
}

export function diagramSVG(spec) {
  /* @doc <code>helpers.diagramSVG(spec)</code> ::
       Returns a themed node/edge figure as an SVG string (the string form of
       <code>helpers.viz.diagram</code>), so a live artifact can render a diagram with
       <code>view.html(...)</code>. Same <code>spec</code>: <code>{title?, caption?, nodes:[{id,
       label, kind, x, y, lines?}], edges:[{from, to, label?}]}</code>; <code>kind &isin;
       env|agent|tool|data|model|neutral</code>.
  */
  const t = _dgTheme();
  const g = _dgLayout(spec);
  const capLines = spec.caption ? _dgWrap(spec.caption, Math.floor(g.W / 6.6)) : [];
  // Grow the canvas downward if the caption wrapped past the one line the
  // default height budgets for, so extra lines never collide with the boxes.
  const capH = capLines.length > 1 ? (capLines.length - 1) * 17 : 0;
  const H = g.H + capH;
  const capTop = H - 24 - (capLines.length - 1) * 17;
  const caption = capLines.map((ln, i) =>
    `<text x="${g.W / 2}" y="${capTop + i * 17}" text-anchor="middle" font-size="12" ` +
    `font-family="${_DG_SANS}" fill="${t.td}">${_dgEsc(ln)}</text>`).join("");
  const edges = (spec.edges || []).map((e) => _dgEdge(e, g, t));
  const edgePaths = edges.map((x) => x.path).join("");
  const edgeChips = edges.map((x) => x.chip).join("");
  const boxes = spec.nodes.map((n) => _dgBox(n, g, t)).join("");
  return (
    `<svg viewBox="0 0 ${g.W} ${H}" xmlns="http://www.w3.org/2000/svg" role="img" ` +
    `aria-label="${_dgEsc(spec.aria || spec.title || "diagram")}" ` +
    `style="width:100%;max-width:${spec.maxWidth || 1100}px;height:auto;display:block;margin:1.2em auto;border-radius:12px">` +
    _dgDefs(t) +
    // explicit bg rect: a CSS `background:` on the <svg> is dropped by some
    // renderers/exporters, and a hardcoded light bg would fight the dark lab.
    `<rect x="0" y="0" width="${g.W}" height="${H}" rx="12" fill="${t.bg}" stroke="${t.bd}"/>` +
    // paths under boxes, boxes, then chips on top so no label hides behind a node.
    edgePaths + boxes + edgeChips + caption + `</svg>`
  );
}

// Render a static node/edge figure into a page element on load (the canvas pages use the same API).
// Same data grammar as helpers.viz.diagram, but for a always-on page diagram rather than a cell-rendered one.
// Colors are var()-driven (see _dgTheme), so the figure follows the theme toggle on its own; no re-render.
export function mountDiagram(targetSel, spec) {
  const host = typeof targetSel === "string" ? document.querySelector(targetSel) : targetSel;
  if (!host) return;
  host.style.width = "100%";
  host.innerHTML = diagramSVG(spec);
}
