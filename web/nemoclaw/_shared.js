// ─── Shared runtime for the nemoclaw web course (frontend track) ─────────────
// REMOTE-SERVICE-ONLY. The web experience is first-class frontend + remote
// services and assumes NO local microservice. Every model call goes to
// build.nvidia.com through the hosted Cloudflare CORS worker (authenticated with
// the student's own nvapi- key); the only other remote dependency is the
// student's OpenClaw launchable on Brev (a remote gateway, reached by URL). There
// is no lab proxy, no llm_client:9000, no in-browser Python kernel. The web pages
// ARE the course narrative; there is no companion notebook track to defer to. The
// same page HTML works in the lab static host, an external iframe, or opened as a
// local file, all identically, because it only ever talks to remotes.

const DIRECT_URL = "https://nvidia-api-cors-proxy.vkudlay.workers.dev/v1";
// Web-cell model contract. The short course standardises on the fast Nemotron
// nano model: it carries the reasoning channel and is quick enough for live
// browser cells. DEFAULT_MODEL is what chat() uses when a cell passes no model;
// REASONING_MODEL is the explicit handle for reasoning-channel lessons. Both are
// injected into every run-cell sandbox (see runCell), so a cell can write
// `model: REASONING_MODEL` without redeclaring it. Keep these in sync with the
// skill-meta models block in nemoclaw/SKILL.html.
const DEFAULT_MODEL   = "nvidia/nemotron-3-nano-30b-a3b";
const REASONING_MODEL = "nvidia/nemotron-3-nano-30b-a3b";

// ── Lab-only step detection ─────────────────────────────────────────────────
// Some steps reach services that exist only inside the student's lab container:
// OpenClaw, the sandbox controller, the search cache, the RAG index, the
// visualizer, the service controller. Those are http + private + gated on a
// per-session token. The model calls fall back to a hosted CORS proxy with the
// student's own key, but these private services have no such fallback, so they
// cannot be reached from the edX
// iframe (https page, cross-origin). When the lab is unreachable (getConfig
// resolves to "direct" mode) we badge such a step and explain it, instead of
// letting it fail with a cryptic "Failed to fetch". In the lab (proxy mode)
// everything runs normally.
// Self-contained course: model calls (Cloudflare worker) and web search (DDG
// Instant Answer) run from any page. The only steps that need an external system
// are the OpenClaw agent ones, which connect to the NemoClaw launchable the
// student deploys on Brev. Those steps get badged and explained instead of failing.
const LAB_ONLY_RE = /\/lab\/openclaw|open(?:shell|claw):8995|\/lab\/svc\/sandbox-admin|sandbox-admin:8099/;
function _stepSource(node) { return node ? (String(node.code || "") + "\n" + String(node.python || "")) : ""; }
function _stepLabOnly(node) { return LAB_ONLY_RE.test(_stepSource(node)); }
function _labOnlyService(node) {
  const s = _stepSource(node);
  if (/\/lab\/openclaw|open(?:shell|claw):8995/.test(s))        return "OpenClaw, the sandboxed agent in your NemoClaw launchable";
  if (/sandbox-admin/.test(s))                                  return "the sandbox controller in your NemoClaw launchable";
  return "your NemoClaw launchable";
}

// ── Data-driven diagram grammar (ported from web/_shared.js) ────────────────
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

// Theme is read from the page's CSS vars at runtime, so a figure renders DARK in
// the lab and LIGHT in the edX export with no per-figure work. Kind hues are
// curated per-theme (CSS vars don't carry them) and chosen to read on both
// backgrounds. _shared/diagram_dev.js is the node-testable twin (DARK/LIGHT).
const _DG_DARK = {
  bg: "#0d0d0d", e1: "#161616", e2: "#1e1e1e", bd: "#2a2a2a",
  tx: "#f2f2f2", td: "#b0b0b0", tf: "#6a6a6a", arrow: "#8a8a8a",
  kinds: { env: "#4b9fff", agent: "#8ecc2f", tool: "#a78bfa", data: "#e0a83a",
           model: "#2dd4bf", neutral: "#9aa0a6" },
};
const _DG_LIGHT = {
  bg: "#ffffff", e1: "#f6f8fa", e2: "#eef1f4", bd: "#d0d7de",
  tx: "#1a1a1a", td: "#3b3b3b", tf: "#57606a", arrow: "#57606a",
  kinds: { env: "#0969da", agent: "#4a7a00", tool: "#7c3aed", data: "#9a6700",
           model: "#0d9488", neutral: "#57606a" },
};
// Luminance of a CSS color string (#rgb, #rrggbb, or rgb(...)); used to decide
// which kind-hue set reads against the live --bg.
function _dgLum(c) {
  if (!c) return 0;
  c = c.trim();
  let r, g, b;
  if (c[0] === "#") {
    let h = c.slice(1);
    if (h.length === 3) h = h.split("").map((x) => x + x).join("");
    r = parseInt(h.slice(0, 2), 16); g = parseInt(h.slice(2, 4), 16); b = parseInt(h.slice(4, 6), 16);
  } else {
    const m = c.match(/(\d+)\D+(\d+)\D+(\d+)/);
    if (!m) return 0;
    r = +m[1]; g = +m[2]; b = +m[3];
  }
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
}
// Build the active theme from CSS vars, falling back to the dark palette (the
// lab default). Box/canvas tones come from the vars; kind hues are picked by
// background luminance so they stay legible in either theme.
function _dgTheme() {
  const base = (typeof document === "undefined") ? _DG_DARK : (() => {
    const cs = getComputedStyle(document.documentElement);
    const v = (name, fb) => (cs.getPropertyValue(name).trim() || fb);
    return {
      bg: v("--bg", _DG_DARK.bg), e1: v("--e1", _DG_DARK.e1), e2: v("--e2", _DG_DARK.e2),
      bd: v("--bd", _DG_DARK.bd), tx: v("--tx", _DG_DARK.tx), td: v("--td", _DG_DARK.td),
      tf: v("--tf", _DG_DARK.tf),
    };
  })();
  const light = _dgLum(base.bg) > 0.5;
  const pal = light ? _DG_LIGHT : _DG_DARK;
  return { ...base, arrow: pal.arrow, kinds: pal.kinds };
}

function _dgLayout(spec) {
  const boxW = spec.boxW || 240, boxH = spec.boxH || 140;
  const padX = 64, top = 92, rowGap = spec.rowGap || 48;
  const cols = Math.max(...spec.nodes.map((n) => n.x)) + 1;
  const rows = Math.max(...spec.nodes.map((n) => n.y)) + 1;
  const W = spec.width || Math.max(640, padX * 2 + cols * boxW + (cols - 1) * 152);
  const gapX = cols > 1 ? (W - padX * 2 - cols * boxW) / (cols - 1) : 0;
  const H = spec.height || (top + rows * boxH + (rows - 1) * rowGap + 68);
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
  /* @doc <code>helpers.diagramSVG(spec)</code> :: Returns a themed node/edge figure as an SVG string (the string form of <code>helpers.viz.diagram</code>), so a live artifact can render a diagram with <code>view.html(...)</code>. Same <code>spec</code>: <code>{title?, caption?, nodes:[{id, label, kind, x, y, lines?}], edges:[{from, to, label?}]}</code>; <code>kind &isin; env|agent|tool|data|model|neutral</code>. */
  const t = _dgTheme();
  const g = _dgLayout(spec);
  const head =
    (spec.kicker ? `<text x="32" y="32" font-size="11" font-family="${_DG_MONO}" fill="${t.tf}" ` +
      `letter-spacing="1.2">${_dgEsc(spec.kicker)}</text>` : "") +
    (spec.title ? `<text x="32" y="58" font-size="17" font-family="${_DG_SANS}" fill="${t.tx}" ` +
      `font-weight="700">${_dgEsc(spec.title)}</text>` : "");
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
    // Layer order: connector paths under the boxes, boxes, then label chips on
    // top so a label never disappears behind an adjacent node.
    head + edgePaths + boxes + edgeChips + caption + `</svg>`
  );
}

export function ganttBarsSVG(workers, wallSeconds, title = "Concurrency vs serial time") {
  /* @doc <code>helpers.ganttBarsSVG(workers, wallSeconds, title)</code> :: Returns a Gantt-style concurrency chart as an SVG string (the string form of <code>helpers.viz.ganttBars</code>), for rendering in a live artifact with <code>view.html(...)</code>. <code>workers</code>: array of <code>{label, dt}</code> (seconds); compares the per-worker bars and their serial sum against the real <code>wallSeconds</code>. */
  const W = 560, BAR_H = 26, GAP = 8, PAD_L = 130, PAD_T = 52, PAD_B = 44, PAD_R = 60;
  const maxBarW = W - PAD_L - PAD_R;
  const serialTotal = workers.reduce((s, w) => s + (w.dt || 0), 0);
  const scale = dt => Math.round((dt / Math.max(serialTotal, 0.001)) * maxBarW);
  const H = PAD_T + (workers.length + 2) * (BAR_H + GAP) + PAD_B;
  const esc = t => String(t || "").replace(/[<>&]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[c]));
  let body = "";
  workers.forEach((w, i) => {
    const y = PAD_T + i * (BAR_H + GAP);
    const bw = scale(w.dt || 0);
    body += `<text x="${PAD_L - 6}" y="${y + BAR_H / 2 + 4}" text-anchor="end" font-size="11" font-family="ui-monospace,monospace" fill="#b0b0b0">${esc(w.label || `worker ${i + 1}`)}</text>`;
    body += `<rect x="${PAD_L}" y="${y}" width="${maxBarW}" height="${BAR_H}" rx="3" fill="#161616"/>`;
    body += `<rect x="${PAD_L}" y="${y}" width="${bw}" height="${BAR_H}" rx="3" fill="#3b82f6" opacity="0.75"/>`;
    body += `<text x="${PAD_L + bw + 5}" y="${y + BAR_H / 2 + 4}" font-size="11" font-family="ui-monospace,monospace" fill="#7eb8ff">${(w.dt || 0).toFixed(2)}s</text>`;
  });
  const serY = PAD_T + workers.length * (BAR_H + GAP) + GAP;
  body += `<text x="${PAD_L - 6}" y="${serY + BAR_H / 2 + 4}" text-anchor="end" font-size="11" font-family="ui-monospace,monospace" fill="#d49c2c" font-weight="700">serial total</text>`;
  body += `<rect x="${PAD_L}" y="${serY}" width="${maxBarW}" height="${BAR_H}" rx="3" fill="#161616"/>`;
  body += `<rect x="${PAD_L}" y="${serY}" width="${maxBarW}" height="${BAR_H}" rx="3" fill="#d49c2c" opacity="0.35"/>`;
  body += `<text x="${PAD_L + maxBarW + 5}" y="${serY + BAR_H / 2 + 4}" font-size="11" font-family="ui-monospace,monospace" fill="#e8c87a">${serialTotal.toFixed(2)}s</text>`;
  const wallY = serY + BAR_H + GAP;
  const wallW = scale(wallSeconds);
  body += `<text x="${PAD_L - 6}" y="${wallY + BAR_H / 2 + 4}" text-anchor="end" font-size="11" font-family="ui-monospace,monospace" fill="#76b900" font-weight="700">wall time</text>`;
  body += `<rect x="${PAD_L}" y="${wallY}" width="${maxBarW}" height="${BAR_H}" rx="3" fill="#161616"/>`;
  body += `<rect x="${PAD_L}" y="${wallY}" width="${wallW}" height="${BAR_H}" rx="3" fill="#76b900" opacity="0.75"/>`;
  body += `<text x="${PAD_L + wallW + 5}" y="${wallY + BAR_H / 2 + 4}" font-size="11" font-family="ui-monospace,monospace" fill="#aee23a">${wallSeconds.toFixed(2)}s</text>`;
  const speedup = serialTotal / Math.max(wallSeconds, 0.001);
  return `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;background:#0d0d0d;border:1px solid #2a2a2a;border-radius:6px">
    <text x="${W / 2}" y="22" text-anchor="middle" font-size="12" font-family="ui-monospace,monospace" fill="#aee23a" font-weight="700">${esc(title)}</text>
    <text x="${W / 2}" y="38" text-anchor="middle" font-size="10" font-family="ui-monospace,monospace" fill="#6a6a6a">parallel speedup: ${speedup.toFixed(2)}x  (serial ${serialTotal.toFixed(2)}s / wall ${wallSeconds.toFixed(2)}s)</text>
    ${body}</svg>`;
}

const LAB_MODEL     = "nvidia/nemotron-3-nano-30b-a3b"; // proxy-mode default (cfg.model in the lab)
const CONFIG_KEY    = "__nv_slim_cfg_v1";

// ── Python mode (removed) ───────────────────────────────────────────────────
// The web course runs JavaScript only; the in-browser Python / JupyterLab-kernel
// path was removed. _pythonModeActive is pinned false so no toggle, body class,
// or kernel branch can ever activate, and getPythonMode() is a harmless internal
// stub for the remaining call sites that read it. Python lives in the notebooks.
const _pythonModeActive = false;
function getPythonMode() { return false; }

// Render a static node/edge figure into a page element on load (the canvas
// pages use the same API). Same data grammar as helpers.viz.diagram, but for a
// always-on page diagram rather than a cell-rendered one.
export function mountDiagram(targetSel, spec) {
  const host = typeof targetSel === "string" ? document.querySelector(targetSel) : targetSel;
  if (!host) return;
  host.style.width = "100%";
  host.innerHTML = diagramSVG(spec);
}


// ── Endpoint discovery ────────────────────────────────────────────────────────
let _cfgPromise = null;

export async function getConfig() {
  /* @doc <code>helpers.getConfig()</code> :: Returns the active endpoint config <code>{ mode, url, model, needsKey }</code>. This course resolves it to build.nvidia.com through the hosted proxy, so you rarely need it directly. */
  if (_cfgPromise) return _cfgPromise;
  _cfgPromise = (async () => {
    // Return cached result for this tab
    try {
      const c = sessionStorage.getItem(CONFIG_KEY);
      if (c) return JSON.parse(c);
    } catch (_) {}

    // Self-contained course: there is no DLI lab and no proxy to probe. Every
    // model call goes to build.nvidia.com through the hosted Cloudflare worker,
    // authenticated with the student's own nvapi- key (kept in localStorage).
    const cfg = { mode: "direct", url: DIRECT_URL, model: DEFAULT_MODEL, needsKey: true };

    try { sessionStorage.setItem(CONFIG_KEY, JSON.stringify(cfg)); } catch (_) {}
    return cfg;
  })();
  return _cfgPromise;
}

// ── Key management (used in direct mode only) ─────────────────────────────────
export function getKey() { /* @doc <code>helpers.getKey()</code> :: Returns the <code>nvapi-</code> key saved in this browser (<code>localStorage</code>; persists across tabs and reloads), or <code>null</code>. Model calls use it automatically; read it only if you call an endpoint by hand. */ return localStorage.getItem("nvapi"); }
export function setKey(k) { localStorage.setItem("nvapi", k.trim()); }
export function hasKey() { return !!getKey(); }

// The OpenAI JS SDK (what ChatOpenAI uses) attaches x-stainless-* platform
// headers to every request. The build CORS proxy's preflight allow-list does
// not include them, so the browser blocks the call ("x-stainless-os is not
// allowed by Access-Control-Allow-Headers"). This fetch wrapper strips them so
// a browser-built ChatOpenAI works against the proxy. Pass it as
// configuration.fetch when you construct ChatOpenAI in a cell.
export function browserChatFetch() {
  /* @doc <code>helpers.browserChatFetch()</code> :: Returns a <code>fetch</code> that strips the OpenAI SDK's <code>x-stainless-*</code> headers (the build CORS proxy rejects them in preflight). Pass it as <code>configuration.fetch</code> when constructing a browser <code>ChatOpenAI</code>. */
  return (url, init) => {
    if (init && init.headers) {
      const h = init.headers instanceof Headers ? init.headers : new Headers(init.headers);
      for (const k of [...h.keys()]) { if (k.startsWith("x-stainless")) h.delete(k); }
      init = { ...init, headers: h };
    }
    return fetch(url, init);
  };
}

export function requireKey(returnUrl) {
  // In proxy mode a key is never required, so skip the check
  getConfig().then(cfg => {
    if (!cfg.needsKey) return;
    if (!hasKey()) location.href = `index.html?next=${encodeURIComponent(returnUrl || location.pathname)}`;
  });
}

// Retry a fetch on transient failure: network error, 502 / 503 / 504 / 524.
// Backs off 250ms, 500ms, 1000ms. Returns the final Response or rethrows
// after the last attempt. Use this for API calls that may hit a momentarily
// flaky remote (the CORS worker occasionally returns 502 when its upstream
// restarts). Streaming calls only retry the headers
// phase; once the stream starts, callers are committed.
//
// The optional `timeoutMs` aborts the underlying fetch if it hasn't received
// headers in time. Without this, a Cloudflare 524 origin-timeout can leave
// the cell "running" for a hundred-plus seconds before failing visibly.
async function fetchRetry(url, opts = {}, { retries = 2, backoffMs = 250, timeoutMs = 60000 } = {}) {
  /* @doc <code>helpers.fetchRetry(url, opts)</code> :: Like <code>helpers.fetch</code>, but retries up to 2 times on 5xx or network errors with exponential backoff (250 / 500 / 1000 ms). Reach for it when you call an endpoint by hand (e.g. the Responses API) and want resilience without writing the retry loop. */
  let lastErr = null;
  for (let attempt = 0; attempt <= retries; attempt++) {
    // Stitch in an AbortController so we don't sit on a half-dead socket.
    // Honour any external signal the caller passed in too.
    const ac = new AbortController();
    const onAbort = () => ac.abort();
    if (opts.signal) opts.signal.addEventListener("abort", onAbort, { once: true });
    const timer = setTimeout(() => ac.abort(new Error(`timeout after ${timeoutMs}ms`)), timeoutMs);
    try {
      const r = await fetch(url, { ...opts, signal: ac.signal });
      clearTimeout(timer);
      if (r.ok) return r;
      // 5xx (including 524 origin-timeout from Cloudflare) is transient
      // upstream; 4xx is the caller's fault, don't retry.
      if (r.status >= 500 && r.status < 600 && attempt < retries) {
        await new Promise(res => setTimeout(res, backoffMs * (2 ** attempt)));
        continue;
      }
      return r;  // 4xx or a final 5xx. The caller handles these.
    } catch (e) {
      clearTimeout(timer);
      lastErr = e;
      // Aborted by caller? Don't retry, because they asked us to stop.
      if (opts.signal && opts.signal.aborted) throw e;
      if (attempt < retries) {
        await new Promise(res => setTimeout(res, backoffMs * (2 ** attempt)));
        continue;
      }
      throw e;
    }
  }
  throw lastErr || new Error("fetchRetry exhausted");
}
export { fetchRetry };

// ── Core API call ─────────────────────────────────────────────────────────────
export async function chat({ messages, tools = null, model = null, temperature = 0.1, max_tokens = 1024, response_format = null, tool_choice = null, signal = null }) {
  /* @doc <code>helpers.chat(opts)</code> :: One-shot chat completion. Non-streaming. Returns the raw OpenAI-shape response. Use when you just want the final message. */
  const cfg = await getConfig();
  const useModel = model || cfg.model;
  const body = { model: useModel, messages, temperature, max_tokens };
  if (tools?.length)   body.tools           = tools;
  if (response_format) body.response_format = response_format;
  if (tool_choice)     body.tool_choice     = tool_choice;

  const headers = { "Content-Type": "application/json" };
  if (cfg.needsKey) headers["Authorization"] = `Bearer ${getKey()}`;

  const resp = await fetchRetry(`${cfg.url}/chat/completions`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    credentials: "same-origin",
    signal,
  });
  if (!resp.ok) {
    const txt = await resp.text();
    // 524 is Cloudflare's origin-timeout. Surface that explicitly, because the
    // generic "524: <html>…" body isn't helpful for a student debugging
    // their cell. Tell them what to try.
    if (resp.status === 524) {
      throw new Error(
        "524 origin timeout: the model took too long to respond (Cloudflare cut the connection). " +
        "This usually clears on retry; if it persists, the upstream model may be cold-starting. " +
        "Try again in 10–20 seconds."
      );
    }
    throw new Error(`${resp.status}: ${txt.slice(0, 400)}`);
  }
  return resp.json();
}

// Streaming wrapper.
//
// Backward compatible: `onChunk(text)` still receives the user-facing
// content delta as a string. New callers may pass a second arg:
//
//   chatStream(opts, onContent, { onReasoning, onMeta })
//
// where `onReasoning(text)` fires for each reasoning_content delta and
// `onMeta(obj)` fires once at the end with { usage, finish_reason, model,
// raw } (raw is the last frame containing usage if the upstream emitted it).
//
// The function also returns a final summary object with the same fields,
// so callers that want the totals after the stream completes do not need
// callbacks at all.
export async function chatStream(opts, onChunk, extra = {}) {
  /* @doc <code>helpers.chatStream(opts)</code> :: Streaming chat completion. Tokens flow into this panel's results view as they arrive. Returns a summary with <code>.content</code>, <code>.reasoning</code>, <code>.tool_calls</code>, <code>.finish_reason</code>, <code>.usage</code>. Pass <code>null</code> as the second arg to suppress streaming. */
  const { messages, model = null, temperature = 0.1, max_tokens = 1024, tools = null, response_format = null, tool_choice = null, signal = null } = opts;
  const onReasoning = extra.onReasoning || null;
  const onMeta = extra.onMeta || null;
  const cfg = await getConfig();
  const useModel = model || cfg.model;

  const headers = { "Content-Type": "application/json" };
  if (cfg.needsKey) headers["Authorization"] = `Bearer ${getKey()}`;

  const body = { model: useModel, messages, temperature, max_tokens, stream: true };
  if (tools?.length)    body.tools           = tools;
  if (response_format)  body.response_format = response_format;
  if (tool_choice)      body.tool_choice     = tool_choice;
  if (opts.extra_body)  Object.assign(body, opts.extra_body);

  const resp = await fetchRetry(`${cfg.url}/chat/completions`, {
    method: "POST", headers, body: JSON.stringify(body), credentials: "same-origin", signal,
  });
  if (!resp.ok) {
    const txt = await resp.text();
    if (resp.status === 524) {
      throw new Error(
        "524 origin timeout (streaming): the model didn't start responding in time. " +
        "Try again in 10–20 seconds. This usually clears on retry."
      );
    }
    throw new Error(`${resp.status}: ${txt.slice(0, 400)}`);
  }

  const reader = resp.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  let usage = null, finishReason = null, lastRaw = null;
  let content = "", reasoning = "";
  // tool_calls arrive fragmented across frames; the streaming API splits the
  // function.arguments JSON into multiple deltas. Each tool_calls entry in a
  // delta has an `index` field that identifies which call this fragment
  // belongs to. We accumulate by index here so the caller sees a flat
  // [{id, function: {name, arguments}}] array at the end.
  const toolCalls = [];
  function accumulateToolCalls(deltaTcs) {
    if (!deltaTcs) return;
    for (const tc of deltaTcs) {
      const i = tc.index ?? 0;
      const cur = (toolCalls[i] ||= { index: i, id: "", type: "function",
                                       function: { name: "", arguments: "" } });
      if (tc.id) cur.id = tc.id;
      if (tc.type) cur.type = tc.type;
      if (tc.function?.name) cur.function.name += tc.function.name;
      if (tc.function?.arguments) cur.function.arguments += tc.function.arguments;
    }
  }

  // Boundary-safe SSE frame parser: only consume complete "data: ...\n\n"
  // frames; partial frames stay buffered for the next read.
  outer: while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      for (const raw of frame.split("\n")) {
        if (!raw.startsWith("data: ")) continue;
        const payload = raw.slice(6).trim();
        if (payload === "[DONE]") break outer;
        let obj;
        try { obj = JSON.parse(payload); } catch (_) { continue; }
        lastRaw = obj;
        const choice = obj?.choices?.[0];
        const delta = choice?.delta;
        if (delta?.content) { content += delta.content; if (onChunk) onChunk(delta.content); }
        if (delta?.reasoning_content) {
          reasoning += delta.reasoning_content;
          if (onReasoning) onReasoning(delta.reasoning_content);
        }
        if (delta?.tool_calls) accumulateToolCalls(delta.tool_calls);
        if (choice?.finish_reason) finishReason = choice.finish_reason;
        if (obj?.usage) usage = obj.usage;
      }
    }
  }

  const summary = {
    content, reasoning,
    tool_calls: toolCalls.filter(Boolean),
    finish_reason: finishReason, usage, model: useModel, raw: lastRaw,
  };
  if (onMeta) onMeta(summary);
  return summary;
}


// ── Error-line helpers (used by mountCanvasFlow + mountRunCell) ──────────────────
// Chrome V8 formats new Function headers across two lines ("function anonymous(...\n) {"),
// so user code starts at stack line 4 (2 header + 1 body-wrapper + user line 1).
// CM is 0-indexed → cmLine = stackLine - 4.
function _parseErrLine(e) {
  if (!e || !e.stack) return null;
  for (const row of e.stack.split("\n")) {
    let m = row.match(/<anonymous>:(\d+):(\d+)/);
    if (!m) m = row.match(/@[^@\n]*:(\d+):(\d+)\s*$/);
    if (m) {
      return { cmLine: Math.max(0, parseInt(m[1]) - 4), cmCol: Math.max(0, parseInt(m[2]) - 1) };
    }
  }
  return null;
}

function _markCMErr(cm, ep) {
  const safeL = Math.min(ep.cmLine, Math.max(0, cm.lineCount() - 1));
  const marker = cm.getWrapperElement().ownerDocument.createElement("span");
  marker.className = "cm-err-gutter";
  marker.title = "Error at line " + (safeL + 1);
  cm.setGutterMarker(safeL, "CodeMirror-linenumbers", marker);
  cm.addLineClass(safeL, "background", "cm-err-line");
  cm.addLineClass(safeL, "wrap", "cm-err-wrap");
  if (!cm._errLines) cm._errLines = [];
  cm._errLines.push(safeL);
  cm.scrollIntoView({ line: safeL, ch: 0 }, 100);
}

function _clearCMErrs(cm) {
  if (!cm || !cm._errLines) return;
  for (const ln of cm._errLines) {
    try {
      cm.setGutterMarker(ln, "CodeMirror-linenumbers", null);
      cm.removeLineClass(ln, "background", "cm-err-line");
      cm.removeLineClass(ln, "wrap", "cm-err-wrap");
    } catch (_) { /**/ }
  }
  cm._errLines = [];
}

function _buildDebugDet(e, code, ep) {
  const _e = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const det = document.createElement("details");
  det.className = "cf-debug-det";
  const sum = document.createElement("summary");
  sum.className = "cf-debug-sum";
  sum.textContent = "Debug info";
  det.appendChild(sum);
  const msg = document.createElement("div");
  msg.className = "cf-debug-type";
  msg.textContent = (e.name || "Error") + ": " + e.message;
  det.appendChild(msg);
  if (ep !== null && code) {
    const lines = code.split("\n");
    const li = ep.cmLine;
    const from = Math.max(0, li - 1);
    const to   = Math.min(lines.length - 1, li + 1);
    const snip = document.createElement("div");
    snip.className = "cf-debug-snippet";
    for (let i = from; i <= to; i++) {
      const row = document.createElement("div");
      row.className = "cf-debug-codeline" + (i === li ? " cf-debug-codeline-err" : "");
      const num = document.createElement("span");
      num.className = "cf-debug-lineno";
      num.textContent = String(i + 1);
      const src = document.createElement("code");
      src.textContent = lines[i] || "";
      row.appendChild(num); row.appendChild(src);
      snip.appendChild(row);
    }
    det.appendChild(snip);
  }
  if (e.stack) {
    const filtered = e.stack.split("\n")
      .filter(l => l.trim() && !l.includes("_shared.js") && !l.includes("at async Function."))
      .slice(0, 6).join("\n");
    const st = document.createElement("pre");
    st.className = "cf-debug-stack";
    st.textContent = filtered || e.stack.split("\n").slice(0, 5).join("\n");
    det.appendChild(st);
  }
  return det;
}


// ── mountCanvasFlow: a 2D graph view of an exercise ─────────────────────────────
// Renders an exercise as nodes on a 2D canvas with curved SVG edges between
// them. Each node is a CodeMirror cell with editable code; the code can read
// and write a shared `state` object so later nodes use earlier results.
// Run-all executes the nodes in declared order; each node can also be run
// in isolation from inside its detail panel.
//
//   mountCanvasFlow("#cell", {
//     label: "M2 P4 · real web_search",
//     intro: "Edit any node's code, then hit Run all.",
//     nodes: [
//       { id: "input", icon: "👤", title: "User input", x: 0, y: 0,
//         summary: "The question the user types",
//         code: "state.question = 'What is...';\nreturn { ok: true };" },
//       { id: "tool",  icon: "📄", title: "Tool spec",  x: 1, y: 0, ... },
//       { id: "llm1",  icon: "🧠", title: "LLM #1",     x: 0, y: 1, ... },
//       ...
//     ],
//     edges: [
//       { from: "input", to: "llm1" },
//       { from: "tool",  to: "llm1" },
//       { from: "llm1",  to: "search" },
//     ],
//   });
//
// The code in each node runs as: async (state, h) => { ...code... }
// where h is { chat, chatStream, webSearch, formatSearchResults, log }.
// log(string) appends a line under the node; the returned value becomes
// the node's "result" pretty-printed under the editor.
//
// Layout: nodes render as compact icon-and-title cards inside a relative
// "stage" wrapper, joined by SVG cubic Bezier edges. Editable code lives
// OUTSIDE the canvas frame, in a vertical stack of "code panels" below.
// Clicking a node in the canvas scrolls to and highlights the matching
// panel. Each panel pairs a CodeMirror editor with its log + last output.
// The stack order matches declared node order, which is also the run order,
// so a student reading top-to-bottom sees the chain as a sequence of
// functions, each writing into shared state.
//
// Per-node code can call `await h.chatStream(opts)` (with no second arg)
// to get token-by-token streaming into the panel's results view; the
// returned summary still carries the full content for the next node to
// consume. Pass `null` as the second arg to suppress streaming.
//
// Each panel exposes two collapsed-by-default <details> dropdowns: one
// for the editable code, one for the streamed output / log lines / final
// result. The results dropdown auto-opens when a node starts running so
// the stream is visible; it stays open after the run completes.
export function mountCanvasFlow(targetSel, opts) {
  const target = typeof targetSel === "string" ? document.querySelector(targetSel) : targetSel;
  if (!target) return;
  const { label, intro, nodes, edges = [], minHeight = 320 } = opts;

  const ns = {};
  for (const n of nodes) ns[n.id] = { code: n.code || "", status: "idle", output: null, logs: [], cm: null };
  const shared = {};

  const maxX = Math.max(0, ...nodes.map(n => n.x ?? 0));
  const maxY = Math.max(0, ...nodes.map(n => n.y ?? 0));
  const cols = maxX + 1, rows = maxY + 1;
  const markerId = "cf-arr-" + Math.random().toString(36).slice(2, 8);

  const wrap = document.createElement("div");
  wrap.className = "cf-wrap";
  wrap.innerHTML = `
    <div class="cf-header">
      <span class="cf-label">${label || ""}</span>
      <div class="cf-actions">
        <button type="button" class="cf-btn cf-btn-reset" title="Restore every node's code to its original">↺ Reset code</button>
        <button type="button" class="cf-btn cf-btn-run">▶ Run all</button>
      </div>
    </div>
    ${intro ? `<div class="cf-intro">${intro}</div>` : ""}
    <details class="cf-helpers">
      <summary>
        <span class="cf-helpers-chip">helpers</span>
        <span class="cf-helpers-sig">in scope inside every node: <code>state</code>, <code>helpers</code></span>
        <span class="cf-helpers-meta">click a row to inspect &amp; edit its source</span>
      </summary>
      <div class="cf-helpers-scroll">
      <table class="cf-helpers-table">
        <tbody>
          ${_buildHelperRows().map(r => {
            if (r.sectionHead) return `<tr class="cf-helpers-section-head"><td colspan="2">${r.sectionHead}</td></tr>`;
            const editable = r.editable !== false;
            // Prefer the helper's own @doc comment (tied to the code); fall back
            // to the curated text only where a function has no @doc yet.
            const _d = _docFor(r.row);
            const _s = SPECIALS[r.row] || {};
            const sig = _d.sig || _s.sig || `<code>helpers.${r.row}(…)</code>`;
            const desc = _d.desc || _s.desc || "";
            return `<tr data-helper="${r.row}"><td>${sig}</td><td>${desc}</td></tr>
              <tr class="cf-helpers-source-row" data-helper-source="${r.row}" hidden>
                <td colspan="2">
                  <div class="cf-helpers-src-head">
                    source · <code>${r.row}</code>
                    ${editable ? `<button type="button" class="cf-helpers-apply" data-apply="${r.row}" title="Compile your edits and override the helper for this canvas">apply override</button>
                    <button type="button" class="cf-helpers-revert" data-revert="${r.row}" title="Restore the original source">revert</button>` : ""}
                    <span class="cf-helpers-status" data-status-of="${r.row}"></span>
                  </div>
                  <textarea class="cf-helpers-src-editor" data-src-for="${r.row}" spellcheck="false" ${editable ? "" : "readonly"}></textarea>
                </td>
              </tr>`;
          }).join("")}
        </tbody>
      </table>
      </div>
    </details>
    <div class="cf-stage">
      <svg class="cf-svg" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <defs>
          <marker id="${markerId}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M0,0 L10,5 L0,10 Z" fill="#76b900"/>
          </marker>
        </defs>
      </svg>
      <div class="cf-canvas" style="min-height:${minHeight}px;grid-template-columns:repeat(${cols},minmax(170px,1fr));grid-template-rows:repeat(${rows},auto);"></div>
    </div>
    <div class="cf-status-bar"></div>
    <div class="cf-panels"></div>
  `;
  target.appendChild(wrap);

  const stage     = wrap.querySelector(".cf-stage");
  const svg       = wrap.querySelector(".cf-svg");
  const canvas    = wrap.querySelector(".cf-canvas");
  const statusBar = wrap.querySelector(".cf-status-bar");
  const panelsHost = wrap.querySelector(".cf-panels");

  // Helper source discovery: click a row in the helpers table to reveal
  // the source of that helper. Uses Function.prototype.toString for live
  // functions; `state` and `log` are described inline since they're not
  // module-level functions.
  const HELPER_SRC = {
    state: `// 'state' is a plain object created fresh for each Run-all.
// Set a field in one node, read it from any later node.
// Example:
//   state.question = "What is the capital of France?";  // in node 1
//   await helpers.chat({ messages: [{role:"user", content: state.question}] });  // in node 2`,
    chat:                chat.toString(),
    chatStream:          chatStream.toString(),
    webSearch:           webSearch.toString(),
    instantAnswer:       instantAnswer.toString(),
    formatSearchResults: formatSearchResults.toString(),
    embed:               embed.toString(),
    cosineSim:           cosineSim.toString(),
    trace: `// 'helpers.trace' is per-node and appends to a shared in-page trace store.
// Each emit becomes a span: { ts, name, attrs }.
// Read state.__trace from any later node to see every emit so far.
// Visualized in Module 5 (Observability).
helpers.trace("llm.chat", { model, tokens: usage.total_tokens });`,
    log: `// 'helpers.log' is per-node: it appends a line to THIS panel's log area
// (under the streamed content, above the final returned value).
// Pass any number of args; objects are JSON-stringified.
helpers.log("step 1 done", { count: 42 });`,
    "viz.scoreBarChart": `// helpers.viz.scoreBarChart(scored, opts)
// scored: array of { score: 1-5, label?: string, note?: string }
// opts:   { threshold?: number (default 3), title?: string, width?: number }
// Renders an SVG bar chart via helpers.log.svg().
// Bars: green (>=threshold), amber (=3), red (<3). Threshold + mean overlay.
// Example:
helpers.viz.scoreBarChart(
  [{ score: 5, label: "accuracy" }, { score: 3, label: "relevance" }, { score: 2, label: "concision" }],
  { threshold: 3, title: "Rubric scores" }
);`,
    "viz.messageList": `// helpers.viz.messageList(messages, title?)
// messages: array with same shape as the LLM API messages array:
//   [{ role: "user"|"assistant"|"tool"|"system", content?: string, tool_calls?: [...] }]
// Renders color-coded cards: USER=blue, ASSISTANT=green, TOOL=amber, SYSTEM=purple.
// Calls helpers.log.svg() internally.
// Example:
helpers.viz.messageList(state.messages, "Memory grows with each turn");`,
    "viz.ganttBars": `// helpers.viz.ganttBars(workers, wallSeconds, title?)
// workers:     array of { label: string, dt: number } (duration in seconds each)
// wallSeconds: total elapsed wall-clock time (from Date.now() or performance.now())
// Renders a Gantt-style chart showing per-worker time + serial total + wall time.
// speedup = serialTotal / wallSeconds is overlaid.
// Example:
const t0 = performance.now();
const results = await Promise.all(tasks.map(doWork));
helpers.viz.ganttBars(
  results.map((r, i) => ({ label: \`worker \${i+1}\`, dt: r.elapsed })),
  (performance.now() - t0) / 1000,
  "Parallel vs serial"
);`,
    "viz.retrievalBars": `// helpers.viz.retrievalBars(scored, topK?, title?)
// scored: array of { text: string, score: number, parent?: string }
//         sorted descending by score (the retrieval order).
// topK:   how many top entries to highlight green (default 3).
// Renders horizontal bars; top-k green, rest dimmed.
// Example:
helpers.viz.retrievalBars(
  results.map(r => ({ text: r.chunk.slice(0, 80), score: r.similarity })),
  3, "Cosine similarity · top-3 retrieved"
);`,
    fetchRetry:          fetchRetry.toString(),
    getConfig:           getConfig.toString(),
    getKey:              getKey.toString(),
    "viz.diagram": `// helpers.viz.diagram(spec)
// Render a node/edge figure from a data spec (no hand-written SVG).
// spec: { title?, caption?, kicker?, nodes:[{id, label, kind, x, y, lines?, socket?}],
//         edges:[{from, to, label?, side?, tint?}] }
//   kind ∈ env | agent | tool | data | model | neutral ; x/y are grid columns/rows.
// Auto-themed and laid out. Example:
helpers.viz.diagram({
  title: "One agent call",
  nodes: [{ id: "you", label: "your code", kind: "data",  x: 0, y: 0 },
          { id: "gw",  label: "gateway",   kind: "agent", x: 1, y: 0 }],
  edges: [{ from: "you", to: "gw", label: "POST" }],
});`,
    "viz.diffTable": `// helpers.viz.diffTable(spec, opts?)
// Before/after comparison table. spec.rows entries are either:
//   { kind: "check", label, left, right }                                   // ✓/✗ booleans
//   { kind: "num", label, left, right, betterWhen: "up"|"down", fmt? }       // colored deltas
// opts: { leftTitle?, rightTitle?, footer?, verdict?({rows}) -> {ok, text} }
// Example:
helpers.viz.diffTable({ rows: [
  { kind: "num",   label: "latency (s)", left: 4.1,   right: 1.2,  betterWhen: "down" },
  { kind: "check", label: "schema ok",   left: false, right: true },
]}, { leftTitle: "before", rightTitle: "after" });`,
    "viz.chat": `// helpers.viz.chat(turns, opts?)
// Render a transcript as colour-coded bubbles.
// turns: array of [role, content] pairs; role ∈ { user, assistant|ai, system, tool }.
// opts:  { maxChars? }  (truncate each turn). Example:
helpers.viz.chat([
  ["system", "You are terse."],
  ["user", "Hi"],
  ["assistant", "Hello."],
], { maxChars: 200 });`,
    "viz.sideBySide": `// helpers.viz.sideBySide(leftLines, rightLines, opts?)
// Two text columns side by side.
// leftLines / rightLines: arrays of strings (one per row).
// opts: { leftTitle?, rightTitle?, footer? }. Example:
helpers.viz.sideBySide(
  ["plan: search", "plan: summarize"],
  ["ran: search ✓", "ran: summarize ✓"],
  { leftTitle: "planned", rightTitle: "executed" }
);`,
  };
  // Per-canvas helper overrides: { [helperName]: compiledFunction }.
  // Empty by default; populated when the student clicks "apply override"
  // on an editable helper source.  Read by runNode below before calling
  // the user's code.
  const helperOverrides = {};
  const helperEditors   = {};  // { [helperName]: CodeMirror instance }
  let _liveHelpers = null, _liveViz = null;  // the live helper set, captured per run (see runNode)

  // Resolve a helper's source LIVE from the code, so the menu can never drift:
  // top-level helpers from the HELPER_FNS registry via Function.toString(), viz.*
  // from VIZ_BUILDERS (or the live viz once a node has run), and the value/native/
  // closure ones (state, fetch, trace, log) from SPECIALS.src.
  function _resolveHelperSrc(name) {
    if (HELPER_FNS[name]) return HELPER_FNS[name].toString();
    if (name.startsWith("viz.")) {
      const k = name.slice(4);
      if (typeof VIZ_BUILDERS !== "undefined" && typeof VIZ_BUILDERS[k] === "function") return VIZ_BUILDERS[k].toString();
      if (_liveViz && typeof _liveViz[k] === "function") return _liveViz[k].toString();
    }
    if (SPECIALS[name]) return SPECIALS[name].src;
    return "// (source unavailable)";
  }

  // Structural self-check: the menu rows must match exactly what the live
  // helpers object exposes. Warns once on any drift, so a helper added to
  // baseHelpers without a row, or a stale row, surfaces immediately in the
  // console instead of silently showing "source not available".
  let _menuAudited = false;
  function _auditHelperMenu(live) {
    if (_menuAudited || !helpersTable) return;
    _menuAudited = true;
    const rows = new Set([...helpersTable.querySelectorAll("tr[data-helper]")].map(r => r.dataset.helper));
    const callable = [...Object.keys(live).filter(k => k !== "viz"),
                      ...Object.keys(live.viz || {}).map(k => "viz." + k), "state"];
    const undocumented = callable.filter(n => !rows.has(n));
    const phantom = [...rows].filter(n => n !== "state" && !callable.includes(n));
    if (undocumented.length) console.warn("[helpers menu] callable but no row:", undocumented);
    if (phantom.length)      console.warn("[helpers menu] row but not callable:", phantom);
  }

  const helpersTable = wrap.querySelector(".cf-helpers-table");
  if (helpersTable) {
    // Click a helper row → toggle its inline source row directly below.
    // Only one source row open at a time keeps the menu compact.
    helpersTable.addEventListener("click", (ev) => {
      const tr = ev.target.closest("tr[data-helper]");
      if (!tr) return;
      // ignore clicks on the source row's controls (handled separately)
      if (ev.target.closest("tr.cf-helpers-source-row")) return;
      const name = tr.dataset.helper;
      const srcRow = helpersTable.querySelector(`tr[data-helper-source="${name}"]`);
      const wasOpen = srcRow && !srcRow.hidden;
      // Collapse any currently-open row.
      helpersTable.querySelectorAll("tr.cf-helpers-source-row").forEach(r => r.hidden = true);
      helpersTable.querySelectorAll("tr[data-helper]").forEach(r => r.classList.remove("selected"));
      if (wasOpen || !srcRow) return;
      srcRow.hidden = false;
      tr.classList.add("selected");
      _initHelperEditor(name);
    });

    // Apply / revert buttons inside source rows.
    helpersTable.addEventListener("click", (ev) => {
      const apply = ev.target.closest("[data-apply]");
      if (apply) {
        ev.stopPropagation();
        _applyHelperOverride(apply.dataset.apply);
        return;
      }
      const revert = ev.target.closest("[data-revert]");
      if (revert) {
        ev.stopPropagation();
        _revertHelperOverride(revert.dataset.revert);
      }
    });
  }


  function _initHelperEditor(name) {
    const ta = helpersTable.querySelector(`textarea[data-src-for="${name}"]`);
    if (!ta) return;
    // Seed with current value (override if present, otherwise the live source).
    const original = _resolveHelperSrc(name);
    if (helperEditors[name]) {
      setTimeout(() => helperEditors[name].refresh(), 30);
      return;
    }
    ta.value = (helperOverrides[name]?.src) || original;
    if (window.CodeMirror) {
      helperEditors[name] = window.CodeMirror.fromTextArea(ta, {
        mode: "javascript",
        theme: "monokai",
        lineNumbers: true,
        lineWrapping: true,
        tabSize: 2,
        indentUnit: 2,
        readOnly: ta.hasAttribute("readonly"),
        viewportMargin: Infinity,
      });
      helperEditors[name].setSize("100%", "auto");
      setTimeout(() => helperEditors[name].refresh(), 30);
    }
  }

  function _applyHelperOverride(name) {
    const editor = helperEditors[name];
    if (!editor) return;
    const src = editor.getValue();
    const status = helpersTable.querySelector(`[data-status-of="${name}"]`);
    try {
      // Compile the edited source as an expression.  Source must evaluate
      // to a function: either `function (…) {…}`, `async function (…) {…}`,
      // or an arrow function.  We wrap in parens for robustness.
      const fn = new Function(`"use strict"; return (${src});`)();
      if (typeof fn !== "function") {
        throw new Error("source must evaluate to a function");
      }
      helperOverrides[name] = { fn, src };
      if (status) {
        status.textContent = "✓ override active";
        status.className = "cf-helpers-status ok";
      }
    } catch (e) {
      if (status) {
        status.textContent = `✗ ${e.message}`;
        status.className = "cf-helpers-status err";
      }
    }
  }

  function _revertHelperOverride(name) {
    delete helperOverrides[name];
    const editor = helperEditors[name];
    const original = _resolveHelperSrc(name);
    if (editor) editor.setValue(original);
    const status = helpersTable.querySelector(`[data-status-of="${name}"]`);
    if (status) { status.textContent = ""; status.className = "cf-helpers-status"; }
  }

  // Compact node cards on the canvas.
  for (const node of nodes) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "cf-node";
    card.dataset.id = node.id;
    card.style.gridColumn = (node.x ?? 0) + 1;
    card.style.gridRow    = (node.y ?? 0) + 1;
    card.innerHTML = `
      <span class="cf-node-icon">${node.icon || "●"}</span>
      <span class="cf-node-title">${node.title || ""}</span>
      <span class="cf-node-status-dot" data-status></span>
    `;
    card.addEventListener("click", () => focusPanel(node.id));
    canvas.appendChild(card);
  }

  // One <details> for code (view-switches between JS and Python based on mode)
  // and one <details> for results.  Both collapsed by default.
  for (const node of nodes) {
    const panel = document.createElement("div");
    panel.className = "cf-panel";
    panel.dataset.id = node.id;
    panel.dataset.hasPython = node.python ? "1" : "0";
    const usePy = _pythonModeActive && node.python;
    panel.innerHTML = `
      <div class="cf-panel-head">
        <span class="cf-panel-icon">${node.icon || "●"}</span>
        <span class="cf-panel-title">${node.title || ""}</span>
        ${node.summary ? `<span class="cf-panel-summary">${node.summary}</span>` : ""}
        <span class="cf-panel-status-dot" data-status></span>
        <button type="button" class="cf-panel-runone" data-runmode="${usePy ? "python" : "js"}">${usePy ? "▶ Run Python" : "▶ Run JS"}</button>
      </div>
      <div class="cf-panel-overview"></div>
      <details class="cf-panel-det cf-panel-code-det">
        <summary>
          <span class="cf-det-chip" data-lang-chip${node.python ? ' data-py-toggle title="click to switch JS / Python"' : ''}>${usePy ? "Python" : "JS"}</span>
          <span class="cf-det-sig" data-lang-sig>"async (state, helpers) =&gt; { … }"</span>
          <span class="cf-det-meta" data-code-meta>click to expand</span>
        </summary>
        <div class="cf-panel-code-body">
          <div class="cf-code-view" data-lang="js">
            <textarea class="cf-panel-code" spellcheck="false">${escapeHtml(node.code || "")}</textarea>
          </div>
          ${node.python ? `<div class="cf-code-view" data-lang="python">
            <textarea class="cf-panel-code-py" spellcheck="false">${escapeHtml(node.python)}</textarea>
          </div>` : ""}
          <button type="button" class="cf-code-copy" title="Copy code to clipboard" aria-label="Copy code">⎘</button>
        </div>
      </details>
      <details class="cf-panel-det cf-panel-results-det">
        <summary>
          <span class="cf-det-chip cf-det-chip-alt">results</span>
          <span class="cf-det-sig">stream · log · return value</span>
          <span class="cf-det-meta" data-results-meta>not yet run</span>
        </summary>
        <div class="cf-panel-stream"></div>
        <div class="cf-panel-log"></div>
        <div class="cf-panel-output"></div>
      </details>
    `;
    panelsHost.appendChild(panel);

    // Floating copy button that copies the currently-active source.
    const copyBtn = panel.querySelector(".cf-code-copy");
    if (copyBtn) {
      copyBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        e.preventDefault();
        const src = (_pythonModeActive && node.python) ? node.python : (ns[node.id].cm ? ns[node.id].cm.getValue() : node.code);
        navigator.clipboard.writeText(src || "").then(() => {
          const orig = copyBtn.textContent;
          copyBtn.textContent = "✓";
          copyBtn.classList.add("ok");
          setTimeout(() => { copyBtn.textContent = orig; copyBtn.classList.remove("ok"); }, 1500);
        });
      });
    }

    panel.querySelector(".cf-panel-runone").addEventListener("click", async (e) => {
      e.stopPropagation();
      if (running) { stopRun(); return; }   // a run is in flight: this click stops it
      if (_pythonModeActive && node.python) {
        // Python mode: execute the Python code on the JupyterLab kernel and
        // stream output into the shared results buffer.
        runPythonNode(node.id).catch(err => {
          const logEl = panel.querySelector(".cf-panel-log");
          if (logEl) logEl.textContent = `Execution error: ${err.message}`;
        });
        return;
      }
      // Run this one node under the shared cancellation, so the Run-all button
      // flips to "⏹ Stop" and can abort even a single-node run.
      beginRun();
      try { await runNode(node.id); } catch (_) {} finally { endRun(); }
    });

    // CodeMirror is initialized lazily, the first time the code dropdown is opened.
    // We init whichever language is active (JS or Python) at open time, and
    // also refresh layout so wrapped lines render correctly.
    const codeDet = panel.querySelector(".cf-panel-code-det");
    codeDet.addEventListener("toggle", () => {
      if (!codeDet.open) return;
      if (_pythonModeActive && node.python) {
        ensurePythonCM(node.id);
        if (ns[node.id].pyCm) setTimeout(() => ns[node.id].pyCm.refresh(), 30);
      } else {
        ensureCM(node.id);
        if (ns[node.id].cm) setTimeout(() => ns[node.id].cm.refresh(), 30);
      }
    });
  }

  // ── Lab-only gating ──────────────────────────────────────────────────────
  // When the lab is unreachable (getConfig resolves to "direct" mode, as in the
  // edX iframe), steps that talk to lab-only services are badged 🔒 and explained
  // rather than run, so the student never hits a cryptic "Failed to fetch".
  let _labReachable = true;
  function _labBadgeCard(node) {
    const card = canvas.querySelector(`.cf-node[data-id="${node.id}"]`);
    if (card && !card.querySelector(".cf-node-lab")) {
      const b = document.createElement("span");
      b.className = "cf-node-lab"; b.textContent = "🔒";
      b.title = "Runs in your launchable only"; b.style.cssText = "margin-left:3px;font-size:.7em;opacity:.85";
      (card.querySelector(".cf-node-title") || card).appendChild(b);
    }
  }
  function _labOnlyNotice(node, panel) {
    if (!panel) return;
    _labBadgeCard(node);
    const det = panel.querySelector(".cf-panel-results-det"); if (det) det.open = true;
    const streamEl = panel.querySelector(".cf-panel-stream"); if (streamEl) streamEl.textContent = "";
    const logEl = panel.querySelector(".cf-panel-log"); if (logEl) logEl.innerHTML = "";
    const outEl = panel.querySelector(".cf-panel-output");
    if (outEl) {
      outEl.innerHTML = "";
      const div = document.createElement("div");
      div.className = "cf-panel-error";
      div.style.cssText = "border-left:3px solid #d49c2c;background:rgba(212,156,44,.10);color:#3b3b3b";
      div.innerHTML = "🔒 <strong>This step runs in your launchable.</strong> It uses " + escapeHtml(_labOnlyService(node)) +
        ", which is gated on your launchable's token and can't be reached from this edX page. Open this page from inside your " +
        "NemoClaw launchable to run it, or run the step in your launchable's OpenClaw chat. The model steps on this page work here once you set your <code>nvapi-</code> key.";
      outEl.appendChild(div);
    }
    const meta = panel.querySelector("[data-results-meta]");
    if (meta) { meta.textContent = "lab only"; meta.className = "cf-det-meta err"; }
    setStatus(node.id, "idle");
  }
  function _applyLabBadges() {
    let any = false;
    for (const node of nodes) {
      if (!_stepLabOnly(node)) continue;
      any = true;
      _labBadgeCard(node);
      const panel = panelsHost.querySelector(`.cf-panel[data-id="${node.id}"]`);
      const ov = panel && panel.querySelector(".cf-panel-overview");
      if (ov && !ov.querySelector(".cf-lab-note")) {
        const n = document.createElement("div");
        n.className = "cf-lab-note";
        n.style.cssText = "font-size:.78rem;color:#3b3b3b;border-left:3px solid #d49c2c;background:rgba(212,156,44,.08);padding:6px 10px;border-radius:0 4px 4px 0;margin:.3em 0";
        n.innerHTML = "🔒 Runs in your launchable. Uses " + escapeHtml(_labOnlyService(node)) + ". Open this page from your launchable to run it.";
        ov.appendChild(n);
      }
    }
    if (any && !document.querySelector(".cf-lab-banner")) {
      const banner = document.createElement("div");
      banner.className = "cf-lab-banner";
      banner.style.cssText = "font-size:.82rem;color:#3b3b3b;border:1px solid #d49c2c;background:rgba(212,156,44,.08);padding:8px 12px;border-radius:6px;margin:0 0 .8em";
      banner.innerHTML = "🔒 Some steps here run <strong>only inside your launchable</strong> (marked 🔒): they use services gated on your launchable's token. Open this page from your launchable to run those; the model steps work here with your <code>nvapi-</code> key.";
      target.insertBefore(banner, wrap);
    }
  }
  getConfig().then(cfg => { _labReachable = !!(cfg && cfg.mode === "proxy"); if (!_labReachable) _applyLabBadges(); }).catch(() => {});

  // ── CodeMirror Python mode loader (lazy) ─────────────────────────────────
  // Only fetched once per page when Python mode first opens a code panel.
  let _cmPythonPromise = null;
  function _loadCMPython() {
    if (window.CodeMirror?.modes?.python) return Promise.resolve();
    if (_cmPythonPromise) return _cmPythonPromise;
    _cmPythonPromise = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/python/python.min.js";
      s.async = true;
      s.onload  = resolve;
      s.onerror = reject;
      document.head.appendChild(s);
    });
    return _cmPythonPromise;
  }

  // ── JupyterLab kernel execution ──────────────────────────────────────────
  // Each canvas flow on the page claims its own kernel so state from one
  // flow does not leak into another.  The kernel persists across runs
  // within the same canvas (so `question` from node 1 is available in
  // node 2), and is cleared when the user clicks the canvas's "reset
  // kernel" control.  Different canvases get different kernels.

  // window.__nv_claimed_kernels__ is a Set of kernel IDs already claimed
  // by some canvas on this page.  Shared so canvas A doesn't reuse canvas
  // B's kernel.
  if (!window.__nv_claimed_kernels__) window.__nv_claimed_kernels__ = new Set();
  let _pyKernelId = null;

  async function _findOrCreateKernel() {
    if (_pyKernelId) {
      try {
        const info = await fetch(`/lab/api/kernels/${_pyKernelId}`, { credentials: "include" }).then(r => r.ok ? r.json() : null);
        if (info?.id) return _pyKernelId;
      } catch (_) {}
      window.__nv_claimed_kernels__.delete(_pyKernelId);
      _pyKernelId = null;
    }
    const kernels = await fetch("/lab/api/kernels", { credentials: "include" })
      .then(r => r.ok ? r.json() : [])
      .catch(() => []);
    if (!Array.isArray(kernels) || !kernels.length) {
      throw new Error("No active kernels found. Open any notebook in JupyterLab to start one, then try again.");
    }
    const pythonKernels = kernels.filter(k => k.name === "python3" || k.name === "python");
    if (!pythonKernels.length) {
      throw new Error("No python3 kernels found in JupyterLab.");
    }
    // Skip kernels claimed by other canvases on this page; among remaining,
    // prefer idle ones.  If every kernel is already claimed, fall back to
    // sharing the least-recently-claimed one rather than refusing to run.
    const unclaimed = pythonKernels.filter(k => !window.__nv_claimed_kernels__.has(k.id));
    const pool      = unclaimed.length ? unclaimed : pythonKernels;
    const kernel    = pool.find(k => k.execution_state === "idle") || pool[0];
    _pyKernelId = kernel.id;
    window.__nv_claimed_kernels__.add(_pyKernelId);
    _updateKernelIndicator();
    return _pyKernelId;
  }

  function _updateKernelIndicator() {
    const ind = wrap.querySelector(".cf-kernel-indicator");
    if (ind && _pyKernelId) ind.textContent = `kernel ${_pyKernelId.slice(0, 6)}`;
  }

  // Reset the canvas's kernel namespace.  Wipes user-defined names while
  // keeping the kernel itself alive.  Sent as an IPython magic to the
  // kernel; non-Python kernels would error out (we only support python3).
  async function resetKernelState() {
    if (!_pyKernelId) return;
    return new Promise((resolve) => {
      _execOnKernel(_pyKernelId, "%reset -f", {
        onStream() {}, onLog() {}, onResult() {}, onDone: resolve,
      });
    });
  }

  function _execOnKernel(kernelId, code, { onStream, onLog, onResult, onDone }) {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${proto}//${location.host}/lab/api/kernels/${kernelId}/channels`;
    const ws = new WebSocket(wsUrl);
    const msgId = "canvas-" + Math.random().toString(36).slice(2, 10);

    ws.onopen = () => {
      ws.send(JSON.stringify({
        header: { msg_id: msgId, msg_type: "execute_request", username: "canvas",
                  session: msgId, version: "5.2", date: new Date().toISOString() },
        parent_header: {}, metadata: {},
        content: { code, silent: false, store_history: false,
                   allow_stdin: false, stop_on_error: false },
      }));
    };

    ws.onmessage = ev => {
      let msg; try { msg = JSON.parse(ev.data); } catch (_) { return; }
      if (msg.parent_header.msg_id !== msgId) return;
      const { msg_type, content } = msg;
      if (msg_type === "stream") {
        if (content.name === "stderr") onLog(content.text);
        else onStream(content.text);
      } else if (msg_type === "execute_result" || msg_type === "display_data") {
        const txt = (content.data || {})["text/plain"] || "";
        if (txt) onResult(txt);
      } else if (msg_type === "error") {
        onLog(`${content.ename}: ${content.evalue}\n${(content.traceback || []).join("\n")}`);
      } else if (msg_type === "status" && content.execution_state === "idle") {
        ws.close(); onDone();
      }
    };
    ws.onerror = () => { onLog("[kernel WebSocket error]"); onDone(); };
    ws.onclose  = () => onDone();
    // Safety timeout: 60 s
    const tid = setTimeout(() => { ws.close(); onLog("[timeout: 60 s]"); onDone(); }, 60000);
    ws.addEventListener("close", () => clearTimeout(tid), { once: true });
    return ws;
  }

  // Run Python code for a specific node, streaming into the same results buffer
  // that JS execution uses.  Called when "▶ Run Python" is clicked.
  async function runPythonNode(nodeId) {
    const s = ns[nodeId];
    const panel = panelsHost.querySelector(`.cf-panel[data-id="${nodeId}"]`);
    if (!panel || !s) return;

    const node = nodes.find(n => n.id === nodeId);
    if (!node?.python) return;
    // Lab-only steps can't run outside the lab; explain instead of failing.
    const _cfgPy = await getConfig();
    if (_cfgPy.mode !== "proxy" && _stepLabOnly(node)) { _labReachable = false; _labOnlyNotice(node, panel); return; }

    // Mirror the JS runNode state machine: set status → running, reset output areas.
    s.status = "running";
    _updateStatus(panel, nodeId);
    const streamEl  = panel.querySelector(".cf-panel-stream");
    const logEl     = panel.querySelector(".cf-panel-log");
    const outputEl  = panel.querySelector(".cf-panel-output");
    const resultsDet = panel.querySelector(".cf-panel-results-det");
    if (streamEl)  streamEl.textContent  = "";
    if (logEl)     logEl.textContent     = "";
    if (outputEl)  outputEl.textContent  = "";
    if (resultsDet) resultsDet.open = true;

    // Update meta label
    const meta = panel.querySelector("[data-results-meta]");
    if (meta) { meta.textContent = "running…"; meta.className = "cf-det-meta running"; }

    let kernelId;
    try {
      kernelId = await _findOrCreateKernel();
    } catch (e) {
      if (logEl) logEl.textContent = `${e.message}\n\nOpen any notebook in JupyterLab (↗ JupyterLab in the Python panel) then come back and run again.`;
      s.status = "error";
      _updateStatus(panel, nodeId);
      if (meta) { meta.textContent = "kernel error"; meta.className = "cf-det-meta err"; }
      return;
    }

    let resultLines = [];
    _execOnKernel(kernelId, node.python, {
      onStream(text) { if (streamEl) streamEl.textContent += text; },
      onLog(text)    { if (logEl)    logEl.textContent    += text; },
      onResult(text) { resultLines.push(text); if (outputEl) outputEl.textContent = resultLines.join("\n"); },
      onDone() {
        s.status = resultLines.length || (logEl?.textContent.trim()) ? "ok" : "ok";
        const hasErr = logEl?.textContent.includes("Error") || logEl?.textContent.includes("Traceback");
        s.status = hasErr ? "error" : "ok";
        _updateStatus(panel, nodeId);
        if (meta) {
          meta.textContent = hasErr ? "error" : "done";
          meta.className   = `cf-det-meta ${hasErr ? "err" : "ok"}`;
        }
      },
    });
  }

  // Helper: sync status dots from ns[nodeId].status ("idle"|"running"|"ok"|"error")
  function _updateStatus(panel, nodeId) {
    const s = ns[nodeId];
    const dots = panel.querySelectorAll("[data-status]");
    dots.forEach(d => { d.dataset.status = s.status || "idle"; });
    const card = canvas.querySelector(`.cf-node[data-id="${nodeId}"] [data-status]`);
    if (card) card.dataset.status = s.status || "idle";
  }

  // pythonModeChange: update all panels in this flow when the mode toggles.
  document.addEventListener("pythonModeChange", () => {
    for (const node of nodes) {
      const panel = panelsHost.querySelector(`.cf-panel[data-id="${node.id}"]`);
      if (!panel) continue;

      const isPython = _pythonModeActive && node.python;

      // Update run button label
      const btn = panel.querySelector(".cf-panel-runone");
      if (btn) {
        btn.textContent = isPython ? "▶ Run Python" : "▶ Run JS";
        btn.dataset.runmode = isPython ? "python" : "js";
      }

      // Update code panel chip + sig to reflect the active language.
      const chip = panel.querySelector("[data-lang-chip]");
      const sig  = panel.querySelector("[data-lang-sig]");
      if (chip) chip.textContent = isPython ? "Python" : "JS";
      if (sig)  sig.innerHTML    = isPython
        ? "→ remote model API"
        : "async (state, helpers) =&gt; { … }";

      // If the code <details> is open, ensure the right CodeMirror is initialised
      // and refreshed. The JS editor is laid out while hidden (display:none during
      // Python mode), so its measurements go stale; refresh() fixes the garbled
      // rendering you would otherwise see when switching back to JS.
      const codeDet = panel.querySelector(".cf-panel-code-det");
      if (codeDet?.open) {
        if (isPython && node.python) {
          ensurePythonCM(node.id);
          if (ns[node.id].pyCm) setTimeout(() => ns[node.id].pyCm.refresh(), 30);
        } else {
          const cm = ensureCM(node.id);
          if (cm) setTimeout(() => cm.refresh(), 30);
        }
      }

      // Restore the results meta label to current node state (buffer is shared).
      const resultsMeta = panel.querySelector("[data-results-meta]");
      if (resultsMeta) {
        const s = ns[node.id];
        resultsMeta.textContent = s.status === "running" ? "running…"
                                : s.status === "error"   ? "error"
                                : s.status === "ok"      ? "done"
                                :                          "not yet run";
        resultsMeta.className = `cf-det-meta ${s.status === "running" ? "running" : s.status === "error" ? "err" : s.status === "ok" ? "ok" : ""}`.trim();
      }
    }
  });

  function ensureCM(nodeId) {
    const s = ns[nodeId];
    if (s.cm) return s.cm;
    const panel = panelsHost.querySelector(`.cf-panel[data-id="${nodeId}"]`);
    const ta    = panel.querySelector('.cf-code-view[data-lang="js"] .cf-panel-code');
    if (window.CodeMirror && ta) {
      s.cm = window.CodeMirror.fromTextArea(ta, {
        mode: "javascript",
        theme: "monokai",
        lineNumbers: true,
        lineWrapping: true,
        viewportMargin: Infinity,
        tabSize: 2,
        indentUnit: 2,
      });
      s.cm.setSize("100%", "auto");
      s.cm.on("change", () => { s.code = s.cm.getValue(); });
    }
    return s.cm;
  }

  // Init CodeMirror in Python mode for syntax highlighting.  Lazy-loaded
  // so the JS-only path doesn't pay for the Python mode script.
  function ensurePythonCM(nodeId) {
    const s = ns[nodeId];
    if (s.pyCm) return s.pyCm;
    const panel = panelsHost.querySelector(`.cf-panel[data-id="${nodeId}"]`);
    const ta    = panel.querySelector('.cf-code-view[data-lang="python"] .cf-panel-code-py');
    if (!ta || !window.CodeMirror) return null;
    // Ensure python mode script is loaded.
    _loadCMPython().then(() => {
      if (s.pyCm) return;
      s.pyCm = window.CodeMirror.fromTextArea(ta, {
        mode: "python",
        theme: "monokai",
        lineNumbers: true,
        lineWrapping: true,
        viewportMargin: Infinity,
        tabSize: 4,
        indentUnit: 4,
        readOnly: false,
      });
      s.pyCm.setSize("100%", "auto");
      s.pyCm.on("change", () => { s.python = s.pyCm.getValue(); });
    });
    return null;
  }

  function focusPanel(nodeId) {
    canvas.querySelectorAll(".cf-node").forEach(c => c.classList.toggle("active", c.dataset.id === nodeId));
    panelsHost.querySelectorAll(".cf-panel").forEach(p => p.classList.toggle("focus", p.dataset.id === nodeId));
    const p = panelsHost.querySelector(`.cf-panel[data-id="${nodeId}"]`);
    if (p) p.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // Edge geometry: prefer vertical routing whenever the target sits on a
  // different row than the source (i.e. dy != 0). Source exits bottom (if
  // dy>0) or top (if dy<0); target enters opposite side. Bezier control
  // points pull straight down/up from each port, producing an S-curve
  // whenever the nodes are diagonally offset (e.g. input at (0,0) and tool
  // at (2,0) both flowing into LLM at (1,1)).
  function relayoutEdges() {
    [...svg.querySelectorAll("path.cf-edge")].forEach(p => p.remove());
    const stageBox = stage.getBoundingClientRect();
    if (stageBox.width < 2 || stageBox.height < 2) {
      requestAnimationFrame(relayoutEdges);
      return;
    }
    svg.setAttribute("viewBox", `0 0 ${stageBox.width} ${stageBox.height}`);
    svg.setAttribute("width",  stageBox.width);
    svg.setAttribute("height", stageBox.height);

    for (const edge of edges) {
      const a = canvas.querySelector(`[data-id="${edge.from}"]`);
      const b = canvas.querySelector(`[data-id="${edge.to}"]`);
      if (!a || !b) continue;
      const ra = a.getBoundingClientRect();
      const rb = b.getBoundingClientRect();
      const cAy = ra.top + ra.height/2, cBy = rb.top + rb.height/2;
      const cAx = ra.left + ra.width/2, cBx = rb.left + rb.width/2;
      const dy = cBy - cAy;
      const dx = cBx - cAx;

      let p1x, p1y, p2x, p2y, vertical;
      if (Math.abs(dy) >= 8) {
        // Different rows → vertical-leaning routing (top/bottom ports).
        vertical = true;
        if (dy > 0) { p1x = cAx; p1y = ra.bottom; p2x = cBx; p2y = rb.top; }
        else        { p1x = cAx; p1y = ra.top;    p2x = cBx; p2y = rb.bottom; }
      } else {
        // Same row → horizontal-leaning routing (left/right ports).
        vertical = false;
        if (dx > 0) { p1x = ra.right; p1y = cAy; p2x = rb.left;  p2y = cBy; }
        else        { p1x = ra.left;  p1y = cAy; p2x = rb.right; p2y = cBy; }
      }
      p1x -= stageBox.left; p1y -= stageBox.top;
      p2x -= stageBox.left; p2y -= stageBox.top;

      let d;
      if (vertical) {
        const cdy = Math.max(28, Math.abs(p2y - p1y) * 0.5);
        // Control points pull straight away from each port; horizontal
        // offset between p1.x and p2.x produces the S-curve.
        d = `M ${p1x} ${p1y} C ${p1x} ${p1y + (p2y > p1y ? cdy : -cdy)}, ${p2x} ${p2y - (p2y > p1y ? cdy : -cdy)}, ${p2x} ${p2y}`;
      } else {
        const cdx = Math.max(40, Math.abs(p2x - p1x) * 0.5);
        d = `M ${p1x} ${p1y} C ${p1x + (p2x > p1x ? cdx : -cdx)} ${p1y}, ${p2x - (p2x > p1x ? cdx : -cdx)} ${p2y}, ${p2x} ${p2y}`;
      }
      const el = document.createElementNS("http://www.w3.org/2000/svg", "path");
      el.setAttribute("d", d);
      el.setAttribute("class", "cf-edge");
      el.setAttribute("data-from", edge.from);
      el.setAttribute("data-to",   edge.to);
      el.setAttribute("marker-end", `url(#${markerId})`);
      svg.appendChild(el);
    }
  }

  const ro = new ResizeObserver(() => relayoutEdges());
  ro.observe(stage);
  window.addEventListener("resize", relayoutEdges, { passive: true });
  setTimeout(relayoutEdges, 0);
  setTimeout(relayoutEdges, 100);

  // Cancellation: one AbortController per run. The Run-all button toggles to
  // "⏹ Stop" while running; clicking it aborts in-flight helpers (chat,
  // chatStream, and terminal all honour the signal) and closes any open
  // gateway/terminal socket the cell parked on state._ws.
  let runAC = null, running = false;
  const _runBtn = () => wrap.querySelector(".cf-btn-run");
  function beginRun() {
    running = true; runAC = new AbortController();
    const b = _runBtn();
    if (b) { b.textContent = "⏹ Stop"; b.disabled = false; b.style.background = "#d1242f"; b.style.color = "#fff"; }
  }
  function endRun() {
    running = false; runAC = null;
    const b = _runBtn();
    if (b) { b.textContent = "▶ Run all"; b.disabled = false; b.style.background = ""; b.style.color = ""; }
  }
  function stopRun() {
    if (!running || !runAC) return;
    try { runAC.abort(); } catch (_) {}
    try { if (shared._ws) shared._ws.close(); } catch (_) {}
    const b = _runBtn(); if (b) b.textContent = "⏹ stopping…";
  }

  async function runNode(nodeId) {
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return;
    const s = ns[nodeId];
    const panel = panelsHost.querySelector(`.cf-panel[data-id="${nodeId}"]`);
    // Lab-only steps can't run outside the lab; explain instead of failing.
    const _cfg = await getConfig();
    if (_cfg.mode !== "proxy" && _stepLabOnly(node)) { _labReachable = false; _labOnlyNotice(node, panel); return; }
    setStatus(nodeId, "running");
    flowEdgesInto(nodeId, true);
    const t0 = performance.now();

    // Update the meta badge on the results dropdown so the run state is
    // visible even while the dropdown is collapsed.
    const metaEl = panel.querySelector("[data-results-meta]");
    if (metaEl) { metaEl.textContent = "streaming…"; metaEl.className = "cf-det-meta running"; }

    // Auto-open results so streaming output is visible while the node runs.
    const resultsDet = panel.querySelector(".cf-panel-results-det");
    if (resultsDet) resultsDet.open = true;

    const streamEl = panel.querySelector(".cf-panel-stream"); streamEl.textContent = "";
    const logEl    = panel.querySelector(".cf-panel-log");    logEl.innerHTML = ""; s.logs = [];
    const outEl    = panel.querySelector(".cf-panel-output"); outEl.innerHTML = "";

    const log = (...args) => {
      const line = args.map(a => typeof a === "object" ? JSON.stringify(a) : String(a)).join(" ");
      s.logs.push(line);
      const div = document.createElement("div");
      div.className = "cf-panel-log-line";
      div.textContent = line;
      logEl.appendChild(div);
    };
    // Capture a cell's console.{log,warn,error,info} into the panel log so a
    // student who adds console statements while editing a cell sees them here,
    // not just in devtools. Warnings/errors are tinted. We mirror to the real
    // console too. This is injected as a `console` parameter that shadows the
    // global only inside the cell (no global override), so it cannot leak to
    // or mis-attribute logs from other code.
    const _capLine = (kind, args) => {
      const line = args.map(a => (a && typeof a === "object")
        ? (() => { try { return JSON.stringify(a); } catch (_) { return String(a); } })()
        : String(a)).join(" ");
      s.logs.push(line);
      const div = document.createElement("div");
      div.className = "cf-panel-log-line";
      if (kind === "warn")       { div.style.color = "#e8c87a"; div.textContent = "⚠ " + line; }
      else if (kind === "error") { div.style.color = "#ff9a9a"; div.textContent = "✗ " + line; }
      else                       { div.textContent = line; }
      logEl.appendChild(div);
      try { (console[kind] || console.log).apply(console, args); } catch (_) {}
    };
    const cellConsole = {
      log:   (...a) => _capLine("log", a),
      info:  (...a) => _capLine("log", a),
      debug: (...a) => _capLine("log", a),
      warn:  (...a) => _capLine("warn", a),
      error: (...a) => _capLine("error", a),
    };
    // log.html(htmlString) appends rendered HTML (e.g. an inline SVG) to
    // the panel's log area. Used by visualization nodes that want to show
    // a chart or diagram inside the cell's results dropdown.
    log.html = (html) => {
      const div = document.createElement("div");
      div.className = "cf-panel-log-html";
      div.innerHTML = String(html);
      logEl.appendChild(div);
    };
    // log.svg(svgString) emits raw SVG into the panel log. When iframed
    // (i.e. the lite-mode edX export), we run a substitution pass mirroring
    // bundle_standalone.py's SVG_SUBS over the incoming string. This catches
    // dark-theme colors that the bundler couldn't reach because they live
    // in JS template literals (helpers.viz.* charts, hand-rolled cell SVG)
    // instead of static <svg>…</svg> tags. Lab view is unaffected.
    const _LITE_VIZ_SUBS = (typeof window !== "undefined" && window.parent !== window) ? [
      // Backgrounds / panel surfaces
      ['#161616', '#eef1f4'], ['#1e1e1e', '#f6f8fa'], ['#0d0d0d', '#f6f8fa'],
      ['#0a0a0a', '#f6f8fa'], ['#1c1c1c', '#eef1f4'], ['#262626', '#e1e6eb'],
      ['#131313', '#eef1f4'], ['#1a1a2e', '#dfeaf5'], ['#0d2a0d', '#e6f3d4'],
      ['#1a3a2a', '#daeec1'], ['#1e3a1e', '#daeec1'], ['#141f04', '#e6f3d4'],
      ['#111a11', '#e6f3d4'], ['#1a2820', '#daeec1'], ['#1e1e3a', '#dfeaf5'],
      ['#3a2e1e', '#f7e3c5'], ['#3a1e1e', '#fadcdc'], ['#1f1a2e', '#eadfff'],
      ['#0d1828', '#dfeaf5'], ['#0d2b40', '#dfeaf5'], ['#141f3a', '#cad7e8'],
      ['#1a2850', '#b5c6db'], ['#211b12', '#f7e3c5'], ['#0f1a22', '#dfeaf5'],
      // Light-on-dark token colors → readable on light
      ['#aee23a', '#4a7a00'], ['#7eb8ff', '#0969da'], ['#7eb6ff', '#0969da'],
      ['#e8c87a', '#8b6914'], ['#f2cc60', '#8b6914'], ['#d2b9ff', '#6f42c1'],
      ['#c4b5fd', '#6f42c1'], ['#a78bfa', '#6f42c1'], ['#c084fc', '#6f42c1'],
      ['#ff9a9a', '#d1242f'], ['#ff6b6b', '#d1242f'],
      ['#e0eec8', '#3b6500'], ['#c8d8f0', '#0969da'], ['#88aacc', '#0969da'],
      ['#f8f8f2', '#1f2328'], ['#f2f2f2', '#1a1a1a'], ['#e8e8e8', '#1a1a1a'],
      // Mid-grays that read OK on dark but vanish on light
      ['#a5a5a5', '#57606a'], ['#b0b0b0', '#3b3b3b'], ['#6a6a6a', '#57606a'],
      ['#6f6f6f', '#57606a'],
      // Strokes
      ['stroke="#2a2a2a"', 'stroke="#d0d7de"'], ['stroke="#3a3a3a"', 'stroke="#b0b8c0"'],
      ['stroke="#4a4a4a"', 'stroke="#a5a5a5"'], ['stroke="#3a6080"', 'stroke="#0969da"'],
      ['stroke="#58a6ff"', 'stroke="#0969da"'], ['stroke="#76b900"', 'stroke="#4a7a00"'],
    ] : null;
    function _flipDarkSvg(s) {
      if (!_LITE_VIZ_SUBS) return s;
      for (const [from, to] of _LITE_VIZ_SUBS) {
        // Plain string replace is fine because we're targeting concrete hex literals.
        s = s.split(from).join(to);
      }
      return s;
    }
    log.svg = (html) => {
      const div = document.createElement("div");
      div.className = "cf-panel-log-html";
      div.innerHTML = _flipDarkSvg(String(html));
      logEl.appendChild(div);
    };
    // log.draw(W, H, body, opts). Hand-written cells used to repeat the
    // same <svg viewBox=… xmlns=… style="background:#0d0d0d…"> boilerplate
    // every time. This wraps the body in that boilerplate so cells only
    // declare their actual marks (rects, text, lines). opts: { title,
    // bg = "#0d0d0d", border = "#2a2a2a", radius = 6 }.
    log.draw = (W, H, body, opts = {}) => {
      const title  = opts.title || null;
      const bg     = opts.bg     || "#0d0d0d";
      const border = opts.border || "#2a2a2a";
      const radius = opts.radius != null ? opts.radius : 6;
      const titleEl = title
        ? `<text x="${W / 2}" y="22" text-anchor="middle" font-size="11" font-family="ui-monospace,monospace" fill="#6f6f6f" letter-spacing="0.08em">${String(title)
            .replace(/[<>&]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[c]))}</text>`
        : "";
      log.svg(`<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;background:${bg};border:1px solid ${border};border-radius:${radius}px">${titleEl}${body}</svg>`);
    };
    // log.details(summary, body) appends a collapsible <details> block to the
    // panel log. An object body renders as pretty JSON (syntax-highlighted when
    // highlight.js is present); a string body renders as plain text. Lets a cell
    // tuck a raw wire frame or tool trace behind a one-line summary so the log
    // stays scannable while the full detail is one click away. Mirrors the
    // mountRunCell helper of the same name so cells behave identically in both.
    log.details = (summary, body) => {
      const det = document.createElement("details");
      det.className = "cf-panel-log-details";
      det.style.cssText = "margin:4px 0 6px;border:1px solid #2a2a2a;border-radius:4px;background:#0a0a0a;";
      const sum = document.createElement("summary");
      sum.style.cssText = "padding:6px 10px;cursor:pointer;font-family:ui-monospace,monospace;font-size:.78rem;color:#a5a5a5;";
      sum.textContent = String(summary);
      det.appendChild(sum);
      const inner = document.createElement("div");
      inner.style.cssText = "padding:8px 12px;font-family:ui-monospace,monospace;font-size:.78rem;line-height:1.5;color:#e6edf3;white-space:pre-wrap;word-break:break-word;";
      if (body && typeof body === "object") {
        const pre = document.createElement("pre");
        pre.style.cssText = "margin:0;background:transparent;border:0;padding:0;overflow-x:auto;";
        const code = document.createElement("code");
        code.className = "language-json";
        code.textContent = JSON.stringify(body, null, 2);
        pre.appendChild(code);
        inner.appendChild(pre);
        det.appendChild(inner);
        logEl.appendChild(det);
        if (typeof window.hljs !== "undefined") { try { window.hljs.highlightElement(code); } catch (_) {} }
      } else {
        inner.textContent = String(body);
        det.appendChild(inner);
        logEl.appendChild(det);
      }
    };

    // ── helpers.viz: per-run viz utilities (capture the per-run log) ───────────
    const viz = makeViz(log);

    // Wrapper around chatStream: if the user passes no callback, route
    // tokens into the panel's streaming view. Pass `null` explicitly to
    // suppress streaming. The full content is still returned via the
    // summary so the next node can read state.s1.content etc.
    // When the cell calls chatStream multiple times we DIVIDE the stream
    // pane into one labeled section per call so the user can tell which
    // tokens came from which call. Used to be: tokens just concatenated
    // and looked duplicated when a cell did two LLM calls.
    let streamCallIdx = 0;
    const streamingChatStream = (opts, onChunk, extra) => {
      if (onChunk === undefined) {
        streamCallIdx++;
        const hdr = document.createElement("div");
        hdr.className = "cf-panel-stream-head";
        hdr.textContent = "── call " + streamCallIdx + " ──";
        streamEl.appendChild(hdr);
        const span = document.createElement("span");
        span.className = "cf-panel-stream-tokens";
        streamEl.appendChild(span);
        onChunk = (text) => {
          span.textContent += text;
          streamEl.scrollTop = streamEl.scrollHeight;
        };
      } else if (onChunk === null) {
        onChunk = null;
      }
      return chatStream(opts, onChunk, extra);
    };

    // Surface the node's persistent state values (anything assigned to
    // state.X during this run) so the student can see the actual inputs
    // and computed values without expanding the results dropdown. The
    // overview lives between the panel header and the code/results
    // dropdowns. Cleared each run; populated after the code finishes.
    const overviewEl = panel.querySelector(".cf-panel-overview");
    if (overviewEl) overviewEl.innerHTML = "";

    try {
      const codeText = (s.cm ? s.cm.getValue() : s.code) || "";
      // Snapshot keys the cell adds to `state` so we can highlight them.
      const stateKeysBefore = new Set(Object.keys(shared));
      // The user's code runs as `async (state, helpers) => { ... }`. The
      // older one-letter `h` alias is also exposed for backward compat,
      // but every node template uses `helpers.foo()` so newcomers can
      // discover what's available without reading the runtime.
      const fn = new Function("state", "helpers", "h", "console",
        `"use strict"; return (async () => {\n${codeText}\n})();`);
      // helpers.trace emits an OTel-shaped span event into a shared in-page
      // trace store the student can read from any node. Module 5 surfaces this.
      const trace = (name, attrs = {}) => {
        if (!shared.__trace) shared.__trace = [];
        shared.__trace.push({ ts: Date.now(), name, attrs });
      };
      // Wrap each network helper so any error it throws is logged into the
      // panel's per-run log BEFORE bubbling up. Without this, a student who
      // wrote `try { await helpers.chat(...) } catch (_) {}` would silence
      // every transient failure, including 524s, JSON errors, and malformed
      // tool calls, and have no way to debug. The wrapper still rethrows
      // so user code that DOES care can react.
      // Sync-transparent: a sync helper stays sync (returns its value), an async
      // one keeps its promise. Either way a thrown/rejected error is logged to
      // this node, then re-thrown. _raw exposes the unwrapped fn for the menu.
      function withErrLog(label, fn) {
        const wrapped = function (...args) {
          let r;
          try { r = fn.apply(this, args); }
          catch (e) { try { log(`✗ ${label} error: ${e.message || e}`); } catch (_) {} throw e; }
          if (r && typeof r.then === "function")
            return r.catch(e => { try { log(`✗ ${label} error: ${e.message || e}`); } catch (_) {} throw e; });
          return r;
        };
        wrapped._raw = fn;
        return wrapped;
      }
      // baseHelpers is built FROM the HELPER_FNS registry, so the menu (which
      // enumerates the same registry) can never list a helper the runtime lacks
      // or miss one it has. chatStream is the single per-node variant (it needs
      // this node's streaming target), so it overrides the registry's module fn.
      const baseHelpers = {};
      for (const [k, fn] of Object.entries(HELPER_FNS)) baseHelpers[k] = withErrLog(k, fn);
      baseHelpers.chatStream = withErrLog("chatStream", streamingChatStream);
      baseHelpers.trace = trace;
      baseHelpers.log   = log;
      baseHelpers.viz   = viz;
      baseHelpers.fetch = (...a) => fetch(...a);   // the platform fetch; see fetchRetry for auto-retry
      // Apply any per-canvas helper overrides the student set via the
      // helpers menu (click a row → edit source → "apply override").
      // Override entries can replace top-level helpers or nested viz.*.
      const helpers = { ...baseHelpers, viz: { ...viz } };
      // Cancellation wiring: expose the current run's signal, and auto-inject it
      // into the network helpers so a cell aborts on Stop WITHOUT the student
      // having to thread `signal` by hand. Cells that DO pass an explicit signal
      // keep theirs (we only fill when absent).
      const _sig = runAC ? runAC.signal : null;
      helpers.signal = _sig || undefined;
      if (_sig) {
        const _withSig = (o) => (o && typeof o === "object" && o.signal == null) ? { ...o, signal: _sig } : o;
        const _chat = helpers.chat, _stream = helpers.chatStream, _term = helpers.terminal;
        if (_chat)   helpers.chat       = (o, ...r) => _chat(_withSig(o), ...r);
        if (_stream) helpers.chatStream = (o, ...r) => _stream(_withSig(o), ...r);
        if (_term)   helpers.terminal   = (cmd, o = {}, ...r) => _term(cmd, _withSig(o), ...r);
      }
      _liveHelpers = helpers; _liveViz = helpers.viz;   // expose to the self-deriving helper menu
      _auditHelperMenu(helpers);
      for (const [name, { fn: override }] of Object.entries(helperOverrides)) {
        if (name.startsWith("viz.")) {
          helpers.viz[name.slice(4)] = override;
        } else if (name in helpers) {
          helpers[name] = override;
        }
      }
      const result = await fn(shared, helpers, helpers, cellConsole);
      s.output = result;

      // Render the return value, but de-duplicate against the stream view:
      // if the return is a string that's already most of what streamed,
      // omit the redundant pre (avoids "same content shown twice" when a
      // cell streams an LLM reply and then returns that same content).
      // Objects / arrays go through highlight.js with a `language-json`
      // hint so keys, strings, numbers, booleans get coloured tokens
      // instead of a flat wall of monochrome text.
      const renderResultPre = (val) => {
        const pre = document.createElement("pre");
        pre.className = "cf-panel-output-pre";
        if (val !== null && (typeof val === "object" || typeof val === "boolean" || typeof val === "number")) {
          const code = document.createElement("code");
          code.className = "language-json hljs";
          code.textContent = typeof val === "object" ? JSON.stringify(val, null, 2) : JSON.stringify(val);
          pre.appendChild(code);
          if (typeof window.hljs !== "undefined") {
            try { window.hljs.highlightElement(code); } catch (_) {}
          }
        } else {
          pre.textContent = String(val);
        }
        outEl.appendChild(pre);
      };
      if (result !== undefined) {
        const streamedText = (streamEl.textContent || "")
          .replace(/── call \d+ ──/g, "")
          .trim();
        const resultText = typeof result === "string" ? result.trim() : "";
        const isRedundant = streamedText.length > 60 && resultText.length > 60 &&
                            (streamedText === resultText
                             || streamedText.includes(resultText)
                             || resultText.includes(streamedText));
        if (!isRedundant) renderResultPre(result);
      }

      // Surface fresh state keys the cell just wrote. This gives the panel an
      // always-visible view of inputs and computed values without needing
      // to expand the results details. Shows the first ~80 chars per key.
      if (overviewEl) {
        const freshKeys = Object.keys(shared).filter(k =>
          !k.startsWith("__") && !stateKeysBefore.has(k));
        if (freshKeys.length) {
          const rows = freshKeys.slice(0, 6).map(k => {
            const v = shared[k];
            let preview;
            if (typeof v === "string") preview = v.slice(0, 120) + (v.length > 120 ? "…" : "");
            else if (typeof v === "number" || typeof v === "boolean") preview = String(v);
            else if (Array.isArray(v))  preview = "[" + v.length + " items]";
            else if (v && typeof v === "object") {
              const keys = Object.keys(v);
              preview = "{ " + keys.slice(0, 5).join(", ") + (keys.length > 5 ? ", …" : "") + " }";
            } else preview = String(v);
            return `<div class="cf-overview-row"><span class="cf-overview-key">state.${k}</span><span class="cf-overview-val">${escapeHtml(preview)}</span></div>`;
          }).join("");
          overviewEl.innerHTML = `<div class="cf-overview-label">wrote into state</div>${rows}`;
        }
      }

      // A clean run wipes any error marks from a previous failed run, so a
      // fixed cell stops showing the old red line instead of accumulating marks.
      if (s.cm) _clearCMErrs(s.cm);
      setStatus(nodeId, "complete");
      if (metaEl) {
        const dt = ((performance.now() - t0) / 1000).toFixed(2);
        metaEl.textContent = "done in " + dt + "s";
        metaEl.className = "cf-det-meta ok";
      }
    } catch (e) {
      // A Stop press aborts the run; show it as stopped, not a red code error.
      if (runAC && runAC.signal.aborted) {
        setStatus(nodeId, "idle");
        if (metaEl) { metaEl.textContent = "stopped"; metaEl.className = "cf-det-meta"; }
        flowEdgesInto(nodeId, false);
        throw e;
      }
      const err = document.createElement("div");
      err.className = "cf-panel-error";
      err.textContent = "✗ " + (e.name || "Error") + ": " + e.message;
      outEl.appendChild(err);
      // Surface WHERE it failed: map the stack to a CodeMirror line, mark it,
      // open the code dropdown, and append a Debug-info panel (snippet + stack).
      const _ep = _parseErrLine(e);
      const _codeForErr = (s.cm ? s.cm.getValue() : s.code) || "";
      if (_ep !== null) {
        const _cm = ensureCM(nodeId);
        if (_cm) {
          _clearCMErrs(_cm); _markCMErr(_cm, _ep);
          const _cd = panel.querySelector(".cf-panel-code-det");
          if (_cd && !_cd.open) _cd.open = true;
          setTimeout(() => { try { _cm.refresh(); _cm.scrollIntoView({ line: _ep.cmLine, ch: 0 }, 100); } catch (_) {} }, 60);
        }
      }
      outEl.appendChild(_buildDebugDet(e, _codeForErr, _ep));
      setStatus(nodeId, "error");
      if (metaEl) { metaEl.textContent = "error"; metaEl.className = "cf-det-meta err"; }
      flowEdgesInto(nodeId, false);
      throw e;
    } finally {
      flowEdgesInto(nodeId, false);
    }
  }

  function setStatus(nodeId, status) {
    ns[nodeId].status = status;
    const card  = canvas.querySelector(`.cf-node[data-id="${nodeId}"]`);
    const panel = panelsHost.querySelector(`.cf-panel[data-id="${nodeId}"]`);
    [card, panel].forEach(el => {
      if (!el) return;
      el.classList.remove("running", "complete", "error");
      if (status !== "idle") el.classList.add(status);
      el.querySelectorAll("[data-status]").forEach(d => {
        d.className = (el === card ? "cf-node-status-dot " : "cf-panel-status-dot ") + status;
      });
    });
  }

  function flowEdgesInto(nodeId, on) {
    svg.querySelectorAll(`path.cf-edge[data-to="${nodeId}"], path.cf-edge[data-from="${nodeId}"]`).forEach(p => {
      if (on) p.classList.add("flowing"); else p.classList.remove("flowing");
    });
  }

  wrap.querySelector(".cf-btn-run").addEventListener("click", async () => {
    if (running) { stopRun(); return; }   // the button is "⏹ Stop" mid-run
    beginRun();
    statusBar.textContent = ""; statusBar.className = "cf-status-bar";
    for (const n of nodes) setStatus(n.id, "idle");
    for (const k of Object.keys(shared)) delete shared[k];
    let ran = 0;
    try {
      for (const node of nodes) {
        if (runAC.signal.aborted) break;
        await runNode(node.id);
        ran++;
      }
      if (runAC && runAC.signal.aborted) {
        statusBar.textContent = "⏹ stopped after " + ran + " of " + nodes.length + " nodes";
        statusBar.className = "cf-status-bar";
      } else {
        statusBar.textContent = "✓ ran " + nodes.length + " nodes";
        statusBar.className = "cf-status-bar ok";
      }
    } catch (e) {
      if (runAC && runAC.signal.aborted) {
        statusBar.textContent = "⏹ stopped after " + ran + " of " + nodes.length + " nodes";
        statusBar.className = "cf-status-bar";
      } else {
        statusBar.textContent = "✗ stopped: " + e.message;
        statusBar.className = "cf-status-bar err";
      }
    } finally {
      endRun();
    }
  });

  wrap.querySelector(".cf-btn-reset").addEventListener("click", () => {
    for (const node of nodes) {
      ns[node.id].code = node.code || "";
      if (ns[node.id].cm) ns[node.id].cm.setValue(node.code || "");
      setStatus(node.id, "idle");
      const panel = panelsHost.querySelector(`.cf-panel[data-id="${node.id}"]`);
      panel.querySelector(".cf-panel-stream").textContent = "";
      panel.querySelector(".cf-panel-log").innerHTML = "";
      panel.querySelector(".cf-panel-output").innerHTML = "";
    }
    for (const k of Object.keys(shared)) delete shared[k];
    statusBar.textContent = "reset";
    statusBar.className = "cf-status-bar";
  });

}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

// ── Web search (Wikipedia's key-less, CORS-open API) ─────────────────────────
// A real, ranked search that runs from any page with no key and no lab service.
// One `generator=search` call returns the top matching articles, and `extracts`
// gives each a short plain-text intro of grounded, real content the model can
// actually answer from. We use Wikipedia (not a general web crawler) because it
// is the only source that is simultaneously key-less, CORS-open (origin=*), and
// reliable from a static browser page. DuckDuckGo's Instant Answer API (see
// `instantAnswer` below) is also key-less, but returns nothing for most real
// queries; this returns ranked results instead. Shape:
// { results:[{title, body, href}], count, unreachable }.
export async function webSearch(query, { maxResults = 5, timeoutMs = 12000 } = {}) {
  /* @doc <code>helpers.webSearch(q, {maxResults})</code> :: Key-less, CORS-open web search over Wikipedia (one ranked <code>generator=search</code> + <code>extracts</code> call), so it runs from any page with no key and no lab. Returns <code>{ results: [{title, body, href}], count, unreachable }</code>, which is the shape <code>formatSearchResults</code> expects. */
  const ctrl = new AbortController();
  const t    = setTimeout(() => ctrl.abort(), timeoutMs);
  const url  = "https://en.wikipedia.org/w/api.php?" + new URLSearchParams({
    action: "query", format: "json", origin: "*", redirects: "1",
    generator: "search", gsrsearch: query, gsrlimit: String(maxResults),
    prop: "extracts|info", inprop: "url", exintro: "1", explaintext: "1", exsentences: "3",
  });
  try {
    const r = await fetch(url, { signal: ctrl.signal });
    if (!r.ok) return { unreachable: true, source: "wikipedia", status: r.status, query, results: [], count: 0 };
    const d = await r.json();
    const pages = Object.values((d.query && d.query.pages) || {}).sort((a, b) => (a.index || 0) - (b.index || 0));
    const results = pages
      .map(p => ({ title: p.title, body: (p.extract || "").trim(),
                   href: p.fullurl || ("https://en.wikipedia.org/wiki/" + encodeURIComponent(String(p.title).replace(/ /g, "_"))) }))
      .filter(x => x.body);
    return { unreachable: false, source: "wikipedia", query, results, count: results.length };
  } catch (e) {
    return { unreachable: true, source: "wikipedia", error: e.message, query, results: [] };
  } finally {
    clearTimeout(t);
  }
}

// ── Instant Answers (DuckDuckGo's free, key-less, CORS-open endpoint) ─────────
// A second, very different search experience from `webSearch` above. This is
// DuckDuckGo's Instant Answer API: https://api.duckduckgo.com/?format=json.
// It needs no key, sends CORS headers, and so runs anywhere. The trade-off is
// shape AND coverage: it returns one curated answer (a definition, an abstract,
// a computed result) plus a few related topics ONLY for queries it recognizes
// as an entity, so most real research queries come back empty. Use `webSearch`
// for grounding; reach for this only to demonstrate a narrow instant-answer
// lookup. Same {results:[{title,body,href}], count, unreachable} shape.
export async function instantAnswer(query, { maxResults = 5, timeoutMs = 12000 } = {}) {
  /* @doc <code>helpers.instantAnswer(q, {maxResults})</code> :: DuckDuckGo's free, key-less <a href='https://api.duckduckgo.com/?q=nvidia&format=json' target='_blank'>Instant Answer API</a>. Same return shape as <code>webSearch</code>. It returns one curated answer plus related topics rather than a ranked page, and it is CORS-open, so it runs anywhere, including the web view with no lab. The black-box-tool counterpart to <code>webSearch</code>. */
  const ctrl = new AbortController();
  const t    = setTimeout(() => ctrl.abort(), timeoutMs);
  const url  = "https://api.duckduckgo.com/?" + new URLSearchParams({
    q: query, format: "json", no_html: "1", skip_disambig: "1",
  });
  try {
    const r = await fetch(url, { signal: ctrl.signal });
    if (!r.ok) return { unreachable: true, source: "instant", status: r.status, query, results: [], count: 0 };
    const d = await r.json();
    const results = [];
    // The headline answer comes back under one of a few keys depending on the
    // query type (a definition, a computed Answer, or a topic abstract).
    const lead = d.Answer || d.AbstractText || d.Definition || "";
    if (lead) {
      results.push({
        title: d.Heading || query,
        body:  String(lead),
        href:  d.AbstractURL || d.DefinitionURL || "https://duckduckgo.com/?q=" + encodeURIComponent(query),
      });
    }
    // RelatedTopics fills out the rest. Some entries are nested topic groups
    // (they carry a `Topics` array instead of `Text`); flatten one level.
    const flat = [];
    for (const rt of (d.RelatedTopics || [])) {
      if (rt.Text) flat.push(rt);
      else if (Array.isArray(rt.Topics)) flat.push(...rt.Topics);
    }
    for (const rt of flat) {
      if (results.length >= maxResults) break;
      if (!rt.Text) continue;
      results.push({ title: rt.Text.split(" - ")[0], body: rt.Text, href: rt.FirstURL || "" });
    }
    return { unreachable: false, source: "instant", query, results, count: results.length };
  } catch (e) {
    return { unreachable: true, source: "instant", error: e.message, query, results: [] };
  } finally {
    clearTimeout(t);
  }
}

// Embed a string (or list of strings) via the remote build endpoint
// (cfg.url is the CORS worker; /embeddings is proxied through). NVIDIA embed
// models require an input_type ("query" or "passage").
// Returns a list of vectors (numbers[]). Single-string input still returns a
// list of length 1 so the call shape is uniform.
export async function embed(input, { model = "nvidia/llama-nemotron-embed-1b-v2", inputType = "query" } = {}) {
  /* @doc <code>helpers.embed(text, {model, inputType})</code> :: POST to the remote build endpoint <code>{cfg.url}/embeddings</code> (the CORS worker). Returns an array of vectors (numbers[]). NVIDIA embed models require <code>inputType: "query"</code> or <code>"passage"</code>. */
  const cfg = await getConfig();
  const headers = { "Content-Type": "application/json" };
  if (cfg.needsKey) headers["Authorization"] = `Bearer ${getKey()}`;
  const body = {
    input: Array.isArray(input) ? input : [input],
    model,
    input_type: inputType,
  };
  const r = await fetchRetry(`${cfg.url}/embeddings`, {
    method: "POST", headers, body: JSON.stringify(body), credentials: "same-origin",
  });
  if (!r.ok) throw new Error(`embeddings ${r.status}: ${(await r.text()).slice(0, 300)}`);
  const data = await r.json();
  return data.data.map(d => d.embedding);
}

// Cosine similarity between two equal-length vectors. The standard
// retrieval primitive, where score(query_emb, doc_emb) closer to 1 = closer match.
export function cosineSim(a, b) {
  /* @doc <code>helpers.cosineSim(a, b)</code> :: Cosine similarity between two vectors. Closer to 1 = closer match. The standard retrieval primitive. */
  let dot = 0, na = 0, nb = 0;
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) { dot += a[i] * b[i]; na += a[i] * a[i]; nb += b[i] * b[i]; }
  return dot / (Math.sqrt(na) * Math.sqrt(nb) + 1e-12);
}

// Open a PTY over the launchable's /ws/terminal WebSocket and run a command.
// This is the operator terminal Cloudflare puts in front of every NemoClaw
// launchable: `cmd=bash` is the VM shell, `cmd=openshell sandbox connect <agent>`
// drops you inside the agent's sandbox. Auth is the browser's Cloudflare Access
// cookie (the same one the gateway cells ride), so JS sets nothing on the socket.
export async function terminal(cmd, { send = [], idleMs = 5000, totalMs = 25000, onChunk = null, baseUrl = null, signal = null } = {}) {
  /* @doc <code>helpers.terminal(cmd, {send, idleMs, totalMs, onChunk})</code> :: Open a PTY over your launchable's <code>/ws/terminal</code> WebSocket and run <code>cmd</code>. Use <code>"bash"</code> for the VM shell, or <code>"openshell sandbox connect &lt;agent&gt;"</code> to drop inside the kernel-sandboxed agent. <code>send</code> is an array of shell lines typed into the PTY in order (each gets Enter). Auth rides your browser's Cloudflare Access cookie, so keep your launchable open in another tab. Returns <code>{ output, raw, frames }</code> (<code>output</code> is ANSI-stripped). Reads the launchable URL from the OpenClaw probe. Launchable only. */
  const rawUrl = (baseUrl
    || localStorage.getItem("nemoclaw_clawrawurl")
    || localStorage.getItem("nemoclaw_clawurl") || "").replace(/\/+$/, "");
  if (!rawUrl) throw new Error("No launchable URL set. Connect on the Kickstart page (Module 3a) first, or pass { baseUrl }.");
  const wsUrl = rawUrl.replace(/^https/, "wss").replace(/^http(?!s)/, "ws")
    + "/ws/terminal?cmd=" + encodeURIComponent(cmd);
  // Drop xterm control sequences so the returned text reads like a transcript.
  const strip = s => String(s)
    .replace(/\x1b\[[0-9;?]*[A-Za-z]/g, "").replace(/\x1b\][^\x07]*\x07/g, "")
    .replace(/\x1b[()][AB0]/g, "").replace(/[\r\x07]/g, "");
  return await new Promise((resolve, reject) => {
    let raw = "", frames = 0, opened = false, idleT = null;
    let ws; try { ws = new WebSocket(wsUrl); } catch (e) { return reject(e); }
    const totalT = setTimeout(() => finish(), totalMs);
    const openT  = setTimeout(() => {
      if (!opened) { try { ws.close(); } catch (_) {} reject(new Error(
        "Terminal did not open in 12s. Your Cloudflare Access session likely expired. " +
        "Open your launchable URL (https://nemoclaw-<id>.brevlab.com) in a new tab to re-authenticate, then re-run.")); }
    }, 12000);
    let finished = false;
    function finish() {
      if (finished) return; finished = true;
      clearTimeout(idleT); clearTimeout(totalT); clearTimeout(openT);
      try { ws.close(); } catch (_) {}
      resolve({ output: strip(raw), raw, frames });
    }
    const bump = () => { clearTimeout(idleT); idleT = setTimeout(finish, idleMs); };
    // External cancellation (e.g. the cell's Stop button): close the socket and
    // resolve with whatever we have so far.
    if (signal) {
      if (signal.aborted) { try { ws.close(); } catch (_) {} return finish(); }
      signal.addEventListener("abort", () => { try { ws.close(); } catch (_) {} finish(); }, { once: true });
    }
    ws.onopen = () => {
      opened = true; clearTimeout(openT); bump();
      let i = 0;
      (function pump() {
        if (i >= send.length) return;
        setTimeout(() => { try { ws.send(send[i] + "\n"); } catch (_) {} i++; pump(); }, 1500);
      })();
    };
    ws.onmessage = ev => {
      frames++;
      let t; try { const j = JSON.parse(ev.data); t = (j.data != null ? j.data : ""); }
      catch (_) { t = String(ev.data || ""); }
      raw += t; if (onChunk) { try { onChunk(strip(t)); } catch (_) {} }
      bump();
    };
    ws.onerror = () => {};
    ws.onclose = () => { if (opened) finish(); };
  });
}

// ── Course content as a tool ─────────────────────────────────────────────────
// The short course's own pages, by file id. One source of truth for the module
// dropdown on 01b and the read_course_page tool's enum.
export const COURSE_PAGES = [
  { id: "overview",          title: "0 · Course overview (home)" },
  { id: "01a-loop",          title: "1a · The Agent (the loop)" },
  { id: "01b-react",         title: "1b · The ReAct Loop" },
  { id: "01c-tools",         title: "1c · Tools at Scale" },
  { id: "02a-routing",       title: "2a · Workflows & routing" },
  { id: "02b-rag",           title: "2b · The Index Agent (RAG)" },
  { id: "02c-deep",          title: "2c · Deep Agents" },
  { id: "03a-kickstart",     title: "3a · Kickstart" },
  { id: "03b-openclaw",      title: "3b · The OpenClaw Agent" },
  { id: "03c-always-on",     title: "3c · The Always-On Agent" },
  { id: "04a-safety",        title: "4a · The NemoClaw Sandbox" },
  { id: "04b-modern-clis",   title: "4b · Modern CLI Agents" },
  { id: "04c-going-further", title: "4c · Going Further" },
];

// Convert a course page's HTML to readable markdown: keep the prose (headings,
// paragraphs, lists, code, callouts), drop the chrome (nav, scripts, SVGs, the
// interactive canvas widgets). Good enough for a model to ingest and reason over.
function _htmlToMarkdown(html) {
  const doc = new DOMParser().parseFromString(html, "text/html");
  const root = doc.querySelector("main") || doc.body;
  if (!root) return "";
  root.querySelectorAll(
    "script,style,noscript,svg,.topbar,#nav,#journey-map,.key-pill,.foot-nav," +
    ".references,.claw-probe,.gw-panel,[id^='cell-'],[id^='gw-'],[id^='bench-']," +
    "[id^='probe-'],[id^='fig-'],[id$='-recover']"
  ).forEach(e => e.remove());
  const inline = (el) => {
    let s = "";
    el.childNodes.forEach(n => {
      if (n.nodeType === 3) { s += n.textContent; return; }
      if (n.nodeType !== 1) return;
      const t = n.tagName.toLowerCase();
      if (t === "code") s += "`" + n.textContent + "`";
      else if (t === "strong" || t === "b") s += "**" + inline(n) + "**";
      else if (t === "em" || t === "i") s += "*" + inline(n) + "*";
      else if (t === "br") s += "\n";
      else s += inline(n);
    });
    return s;
  };
  const clean = (s) => s.replace(/[ \t]+/g, " ").replace(/ *\n */g, "\n").trim();
  const out = [];
  const walk = (el) => {
    el.childNodes.forEach(n => {
      if (n.nodeType !== 1) return;
      const t = n.tagName.toLowerCase();
      if (/^h[1-6]$/.test(t)) out.push("\n" + "#".repeat(+t[1]) + " " + clean(inline(n)));
      else if (t === "p") { const x = clean(inline(n)); if (x) out.push(x); }
      else if (t === "ul" || t === "ol") {
        n.querySelectorAll(":scope > li").forEach(li => { const x = clean(inline(li)); if (x) out.push("- " + x); });
      }
      else if (t === "pre") out.push("```\n" + n.textContent.trim() + "\n```");
      else if (t === "blockquote" || (n.classList && n.classList.contains("callout"))) {
        const x = clean(inline(n)); if (x) out.push("> " + x.replace(/\n/g, "\n> "));
      }
      else walk(n);
    });
  };
  walk(root);
  // No truncation: the agent reads the whole page. Length is surfaced as a
  // context-budget readout in the artifact, not silently clipped here.
  return out.join("\n\n").replace(/\n{3,}/g, "\n\n").trim();
}

export async function coursePage(pageId) {
  /* @doc <code>helpers.coursePage(id)</code> :: Fetch one of this course's pages and return its prose as markdown (headings, paragraphs, lists, code, callouts; chrome and interactive widgets stripped). <code>id</code> is a page file id like <code>"01b-react"</code>, which you can list with <code>helpers.coursePages()</code>. Same-origin fetch, no key. Use it as the body of a <code>read_course_page</code> tool so an agent can ground answers in the real course content. */
  const id = String(pageId || "").trim().replace(/\.html$/, "");
  if (!COURSE_PAGES.some(p => p.id === id)) {
    return `(unknown page "${id}". Choose one of: ${COURSE_PAGES.map(p => p.id).join(", ")})`;
  }
  // "overview" is the course home (one level up from the page directory): the
  // global map, what-you'll-build, and what-it-runs-on. Read it for course-wide
  // questions instead of guessing at a single module page.
  const path = id === "overview" ? "../../index.html" : id + ".html";
  const r = await fetch(path, { credentials: "same-origin" });
  if (!r.ok) throw new Error(`coursePage("${id}") → ${r.status}`);
  const md = _htmlToMarkdown(await r.text());
  const title = (COURSE_PAGES.find(p => p.id === id) || {}).title || id;
  return `# ${title}  (course page: ${id})\n\n${md}`;
}

// Advertised context windows for the models the artifacts expose, so the chat
// can show how full the window is and warn before it overflows (rather than
// silently dropping tokens). Both Nemotron-3 models ship a 256K window.
export const CONTEXT_WINDOWS = {
  "nvidia/nemotron-3-nano-30b-a3b":    262144,
  "nvidia/nemotron-3-super-120b-a12b": 262144,
};
export function contextWindow(model) {
  /* @doc <code>helpers.contextWindow(model)</code> :: The advertised context-window size (in tokens) for a model id, used to drive the artifact's context-budget readout. Falls back to 131072 for unknown models. */
  return CONTEXT_WINDOWS[model] || 131072;
}
// Cheap token estimate (≈4 chars/token) for a pre-flight budget check before a
// turn is sent. The real count comes back in usage_metadata afterward.
export function estimateTokens(textOrMessages) {
  /* @doc <code>helpers.estimateTokens(textOrMessages)</code> :: Rough token estimate (≈4 chars/token) for a string or an array of <code>{content}</code> messages. For a pre-flight context-budget check; the authoritative count is the model's <code>usage_metadata</code>. */
  const s = Array.isArray(textOrMessages)
    ? textOrMessages.map(m => (typeof m === "string" ? m : (m && m.content) || "")).join("\n")
    : String(textOrMessages || "");
  return Math.ceil(s.length / 4);
}

export function coursePages() {
  /* @doc <code>helpers.coursePages()</code> :: The course's page list as <code>[{ id, title }]</code>, the single source for a module menu or a <code>read_course_page</code> tool's <code>enum</code>. */
  return COURSE_PAGES.map(p => ({ ...p }));
}

// ── A live chat artifact ─────────────────────────────────────────────────────
// Renders a persistent, interactive chat panel (controls + transcript + input)
// into `container`. The caller owns the agent and supplies `respond(text, ctx)`,
// which streams its reply into `ctx.view` (token by token, with tool chips). This
// is the "artifact" half: the agent's run produces an interactive UI, not a log.
export function mountChatUI(container, opts = {}) {
  /* @doc <code>helpers.mountChatUI(el, opts)</code> :: Render a live, observable chat artifact (controls + streaming transcript + input) into <code>el</code>. <code>opts</code>: <code>{ modules:[{id,title}], models:[{id,label}], intro, greeting, respond(text, ctx), onReset() }</code>. <code>respond</code> streams into <code>ctx.view</code>: <code>view.token(t)</code> (answer, rendered as markdown), <code>view.reasoning(t)</code> (a collapsible thinking trace), <code>view.tool(label, detail)</code> (a tool chip that expands to show <code>detail</code>), <code>view.usage({input, output})</code> (per-turn tokens + running context), <code>view.html(h)</code>, <code>view.error(msg)</code>. <code>ctx</code> has <code>{ module, modules, model, thread, turn }</code>, where <code>modules</code> is the array of pinned page ids (empty = auto). Returns <code>{ thread, reset(), ctx }</code>. */
  const el = typeof container === "string" ? document.querySelector(container) : container;
  if (!el) return null;
  // Markdown: load marked once (cached on window); render answers as HTML + hljs.
  if (!window.__markedP) window.__markedP = import("https://cdn.jsdelivr.net/npm/marked@14/+esm").then(m => m.marked || m.default).catch(() => null);
  let MARKED = null; window.__markedP.then(m => { MARKED = m; });
  const _sanitize = (html) => { const d = document.createElement("div"); d.innerHTML = html;
    d.querySelectorAll("script,iframe,style,object,embed,link,meta,form").forEach(n => n.remove());
    d.querySelectorAll("*").forEach(n => [...n.attributes].forEach(a => { if (/^on/i.test(a.name) || /javascript:/i.test(a.value)) n.removeAttribute(a.name); }));
    return d.innerHTML; };
  const renderMd = (elm, t) => { if (MARKED) { elm.innerHTML = _sanitize(MARKED.parse(t)); if (window.hljs) elm.querySelectorAll("pre code").forEach(b => { try { window.hljs.highlightElement(b); } catch (_) {} }); } else { elm.textContent = t; } };
  if (!document.head.querySelector('style[data-chat-ui="3"]')) {
    const s = document.createElement("style"); s.dataset.chatUi = "3";
    s.textContent = `
      .chatui{border:1px solid var(--bd,#2a2a2a);border-radius:10px;background:var(--e1,#161616);overflow:hidden;margin:1em 0}
      .chatui-bar{display:flex;align-items:center;flex-wrap:wrap;gap:8px;padding:10px 12px;border-bottom:1px solid var(--bd,#2a2a2a);background:var(--e2,#1e1e1e)}
      .chatui-bar label{font-family:var(--mono,monospace);font-size:.7rem;color:var(--tf,#8a8a8a);text-transform:uppercase;letter-spacing:.05em}
      .chatui-bar select{background:var(--e1,#161616);color:var(--tx,#f2f2f2);border:1px solid var(--bd,#2a2a2a);border-radius:6px;padding:5px 8px;font-family:var(--mono,monospace);font-size:.78rem}
      .chatui-bar .sp{flex:1}
      .chatui-ctx{font-family:var(--mono,monospace);font-size:.7rem;color:var(--tf,#8a8a8a)}
      .chatui-reset{background:var(--e1,#161616);color:var(--td,#b0b0b0);border:1px solid var(--bd,#2a2a2a);border-radius:6px;padding:5px 11px;font-size:.76rem;cursor:pointer}
      .chatui-reset:hover{border-color:var(--g,#76b900);color:var(--gs,#aee23a)}
      .chatui-mods{display:flex;align-items:center;flex-wrap:wrap;gap:5px;width:100%;margin-top:2px}
      .chatui-modchip{font-family:var(--mono,monospace);font-size:.68rem;color:var(--td,#b0b0b0);background:var(--e1,#161616);border:1px solid var(--bd,#2a2a2a);border-radius:999px;padding:2px 9px;cursor:pointer}
      .chatui-modchip:hover{border-color:var(--g,#76b900)}
      .chatui-modchip.on{background:var(--g,#76b900);color:#0a0a0a;border-color:var(--g,#76b900);font-weight:700}
      .chatui-log{padding:14px 14px 6px;max-height:480px;overflow-y:auto;display:flex;flex-direction:column;gap:9px}
      .chatui-intro{font-size:.84rem;color:var(--tf,#8a8a8a);line-height:1.5}
      .chatui-examples{display:flex;flex-wrap:wrap;gap:6px;align-self:flex-start;max-width:100%}
      .chatui-ex{text-align:left;font-size:.78rem;color:var(--gs,#aee23a);background:rgba(118,185,0,.06);border:1px solid rgba(118,185,0,.28);border-radius:14px;padding:5px 11px;cursor:pointer;line-height:1.35}
      .chatui-ex:hover{background:rgba(118,185,0,.14);border-color:var(--g,#76b900)}
      .chatui-msg{max-width:90%;padding:9px 13px;border-radius:12px;font-size:.9rem;line-height:1.6;word-wrap:break-word;overflow-wrap:anywhere}
      .chatui-user{align-self:flex-end;background:var(--g,#76b900);color:#0a0a0a;border-bottom-right-radius:3px;white-space:pre-wrap}
      .chatui-bot{align-self:flex-start;background:var(--e2,#1e1e1e);color:var(--tx,#f2f2f2);border:1px solid var(--bd,#2a2a2a);border-bottom-left-radius:3px}
      .chatui-bot.err{border-color:#f87171;color:#fca5a5;white-space:pre-wrap}
      .chatui-bot>:first-child{margin-top:0}.chatui-bot>:last-child{margin-bottom:0}
      .chatui-bot p{margin:.5em 0}.chatui-bot ul,.chatui-bot ol{margin:.5em 0;padding-left:1.4em}.chatui-bot li{margin:.2em 0}
      .chatui-bot h1,.chatui-bot h2,.chatui-bot h3{margin:.6em 0 .3em;line-height:1.3}.chatui-bot h1{font-size:1.15rem}.chatui-bot h2{font-size:1.05rem}.chatui-bot h3{font-size:.98rem}
      .chatui-bot code{font-family:var(--mono,monospace);font-size:.85em;background:#0d0d0d;padding:1px 5px;border-radius:4px;color:var(--gs,#aee23a)}
      .chatui-bot pre{background:#0d0d0d;border:1px solid var(--bd,#2a2a2a);border-radius:6px;padding:10px 12px;overflow-x:auto;margin:.5em 0}.chatui-bot pre code{background:none;padding:0;color:var(--tx,#f2f2f2)}
      .chatui-bot table{border-collapse:collapse;font-size:.85em;margin:.4em 0}.chatui-bot td,.chatui-bot th{border:1px solid var(--bd,#2a2a2a);padding:3px 8px}
      .chatui-bot a{color:var(--gs,#aee23a)}
      .chatui-tool,.chatui-think{align-self:flex-start;max-width:90%;font-family:var(--mono,monospace);font-size:.74rem;color:var(--gs,#aee23a);background:rgba(118,185,0,.07);border:1px solid rgba(118,185,0,.22);border-radius:8px;padding:4px 10px}
      details.chatui-tool>summary,details.chatui-think>summary{cursor:pointer;list-style:none}
      details.chatui-tool>summary::-webkit-details-marker,details.chatui-think>summary::-webkit-details-marker{display:none}
      .chatui-tool-body,.chatui-think-body{margin-top:6px;padding-top:6px;border-top:1px solid rgba(118,185,0,.18);color:var(--td,#b0b0b0);white-space:pre-wrap;max-height:340px;overflow:auto}
      .chatui-tool.err{color:#fca5a5;background:rgba(248,113,113,.07);border-color:rgba(248,113,113,.3)}
      .chatui-tool.err .chatui-tool-body{border-top-color:rgba(248,113,113,.2)}
      .chatui-think{color:#c4b5fd;background:rgba(130,80,223,.06);border-color:rgba(130,80,223,.28)}
      .chatui-think-body{border-top-color:rgba(130,80,223,.2)}
      .chatui-warn{align-self:flex-start;max-width:90%;font-family:var(--mono,monospace);font-size:.72rem;color:#e8c87a;background:rgba(212,156,44,.08);border:1px solid rgba(212,156,44,.3);border-radius:8px;padding:4px 10px;white-space:pre-wrap}
      .chatui-usage{align-self:flex-start;font-family:var(--mono,monospace);font-size:.68rem;color:var(--tf,#8a8a8a)}
      .chatui-turn{display:flex;flex-direction:column;gap:9px;align-self:stretch}
      .chatui-turn.chatui-cursor::after{content:"▍";color:var(--g,#76b900);animation:chatui-blink 1s steps(2) infinite;align-self:flex-start;font-family:var(--mono,monospace)}
      .chatui-ctxwrap{display:inline-flex;align-items:center;gap:6px}
      .chatui-ctxbar{width:70px;height:6px;border-radius:3px;background:var(--e1,#161616);border:1px solid var(--bd,#2a2a2a);overflow:hidden}
      .chatui-ctxfill{height:100%;width:0;background:var(--g,#76b900);transition:width .2s}
      .chatui-ctx.warn{color:#ff9a9a}.chatui-ctx.warn .chatui-ctxfill{background:#d74e4e}
      .chatui-viz{align-self:stretch;max-width:100%}
      .chatui-viz svg{display:block;width:100%;height:auto}
      .chatui-viz table{width:100%;border-collapse:collapse;font-size:.8rem}
      .chatui-viz td,.chatui-viz th{padding:3px 8px;border-bottom:1px solid var(--bd,#2a2a2a);text-align:left}
      .chatui-cursor::after{content:"▍";color:var(--g,#76b900);animation:chatui-blink 1s steps(2) infinite}
      @keyframes chatui-blink{50%{opacity:0}}
      .chatui-in{display:flex;gap:8px;padding:10px 12px;border-top:1px solid var(--bd,#2a2a2a)}
      .chatui-in textarea{flex:1;resize:none;background:var(--e2,#1e1e1e);color:var(--tx,#f2f2f2);border:1px solid var(--bd,#2a2a2a);border-radius:8px;padding:8px 11px;font-family:inherit;font-size:.9rem;line-height:1.4;min-height:20px;max-height:120px}
      .chatui-in textarea:focus{outline:none;border-color:var(--g,#76b900)}
      .chatui-send{background:var(--g,#76b900);color:#0a0a0a;border:0;border-radius:8px;padding:0 18px;font-weight:700;font-size:.85rem;cursor:pointer}
      .chatui-send:hover{background:var(--gs,#aee23a)}
      .chatui-send:disabled{opacity:.5;cursor:wait}
      .chatui-send.stop{background:#d1242f;color:#fff}.chatui-send.stop:hover{background:#e5484d}`;
    document.head.appendChild(s);
  }
  const modules = opts.modules || [];
  const models  = opts.models || [];
  const modelSel = models.length
    ? `<label>Model</label><select class="chatui-model">${models.map(m => `<option value="${escHtml(m.id)}">${escHtml(m.label || m.id)}</option>`).join("")}</select>` : "";
  const modChips = modules.length
    ? `<div class="chatui-mods"><label>Pages</label>${modules.map(m => `<button type="button" class="chatui-modchip" data-id="${escHtml(m.id)}" title="${escHtml(m.title || m.id)}">${escHtml(m.id)}</button>`).join("")}<span class="chatui-ctx" data-pinhint>none pinned = auto-select</span></div>` : "";
  el.innerHTML = `<div class="chatui">
      <div class="chatui-bar">${modelSel}<span class="chatui-ctx chatui-ctxwrap" data-ctx hidden><span data-ctxtext></span><span class="chatui-ctxbar"><span class="chatui-ctxfill"></span></span></span><span class="sp"></span><button class="chatui-reset" type="button">↺ New chat</button>${modChips}</div>
      <div class="chatui-log"></div>
      <div class="chatui-in"><textarea class="chatui-text" rows="1" placeholder="Ask a question…"></textarea><button class="chatui-send" type="button">Send</button></div>
    </div>`;
  const log = el.querySelector(".chatui-log");
  const text = el.querySelector(".chatui-text");
  const sendBtn = el.querySelector(".chatui-send");
  const resetBtn = el.querySelector(".chatui-reset");
  const modelEl = el.querySelector(".chatui-model");
  const ctxEl = el.querySelector("[data-ctx]");
  const chips = [...el.querySelectorAll(".chatui-modchip")];
  chips.forEach(c => c.addEventListener("click", () => c.classList.toggle("on")));
  const selectedModules = () => chips.filter(c => c.classList.contains("on")).map(c => c.dataset.id);
  const ctx = { thread: "chat-" + Math.random().toString(36).slice(2, 9), turn: 0, _ctx: 0,
                get modules() { return selectedModules(); },
                get module() { const s = selectedModules(); return s[0] || "auto"; },   // back-compat
                get model()  { return modelEl ? modelEl.value : (models[0] && models[0].id) || null; },
                get window() { return contextWindow(ctx.model); } };
  const ctxText = el.querySelector("[data-ctxtext]");
  const ctxFill = el.querySelector(".chatui-ctxfill");
  const ctxBar  = el.querySelector(".chatui-ctxbar");
  const k = (n) => n >= 1000 ? (n / 1000).toFixed(n >= 100000 ? 0 : 1) + "k" : String(n);
  // The persistent context-budget readout in the bar. If we know the model's
  // window (a course model in CONTEXT_WINDOWS) show how full it is, red past 90%.
  // If the window is unknown (e.g. the OpenClaw gateway's own model) show the
  // honest absolute count with no fabricated denominator.
  const setBudget = (used, model, winOverride) => {
    const win = winOverride || CONTEXT_WINDOWS[model || ctx.model]; ctx._ctx = used;
    if (!ctxEl) return;
    if (!used) { ctxEl.hidden = true; return; }
    ctxEl.hidden = false;
    if (win) {
      const pct = Math.min(100, Math.round((used / win) * 100));
      ctxText.textContent = "context " + k(used) + " / " + k(win) + " (" + pct + "%)";
      ctxBar.style.display = ""; ctxFill.style.width = pct + "%";
      ctxEl.classList.toggle("warn", pct >= 90);
    } else {
      ctxText.textContent = "context " + k(used) + " tok";
      ctxBar.style.display = "none"; ctxEl.classList.remove("warn");
    }
  };
  if (opts.intro) { const i = document.createElement("div"); i.className = "chatui-intro"; i.textContent = opts.intro; log.appendChild(i); }
  if (opts.greeting) { const g = document.createElement("div"); g.className = "chatui-msg chatui-bot"; g.textContent = opts.greeting; log.appendChild(g); }
  const scroll = () => { log.scrollTop = log.scrollHeight; };
  const bubble = (cls, txt) => { const d = document.createElement("div"); d.className = "chatui-msg " + cls; if (txt != null) d.textContent = txt; log.appendChild(d); scroll(); return d; };
  // Clickable starter prompts: one-click fills the box (the student can edit
  // before sending), so the artifact invites a real first interaction.
  const addExamples = () => { if (!opts.examples || !opts.examples.length) return;
    const ex = document.createElement("div"); ex.className = "chatui-examples";
    opts.examples.forEach(s => { const b = document.createElement("button"); b.type = "button"; b.className = "chatui-ex"; b.textContent = s;
      b.addEventListener("click", () => { text.value = s; text.style.height = "auto"; text.style.height = Math.min(text.scrollHeight, 120) + "px"; text.focus(); });
      ex.appendChild(b); });
    log.appendChild(ex); };
  addExamples();

  let running = false, curAC = null;
  async function send() {
    const q = text.value.trim();
    if (!q || running) return;
    text.value = ""; text.style.height = "auto";
    bubble("chatui-user", q);
    // One container per turn. Blocks (reasoning, tool, answer) are appended in
    // the order they stream, so the transcript reads exactly as the agent ran:
    // reason → act → observe → reason → answer. No fixed slots, no reordering.
    const turn = document.createElement("div"); turn.className = "chatui-turn chatui-cursor";
    log.appendChild(turn); scroll();
    // The Send button becomes a Stop button for the duration of the turn; its
    // AbortController is handed to respond as ctx.signal so a long agent or
    // gateway run can actually be cancelled, not just waited out.
    running = true; curAC = new AbortController();
    sendBtn.textContent = "⏹ Stop"; sendBtn.classList.add("stop");
    let cur = null;         // the currently-open streaming block: {kind, el, body?, _t, _raf}
    let answered = false, errored = false;
    // A reasoning block stays open while it streams, then folds shut once the
    // agent advances to its next act/answer, so you watch it think, then the
    // focus moves to what it did. Still expandable.
    const endThink = () => { if (cur && cur.kind === "think") { cur.el.open = false;
      const s = cur.el.querySelector("summary"); if (s) s.textContent = "🧠 reasoning · ~" + estimateTokens(cur._t) + " tok"; } };
    const newThink = () => { const d = document.createElement("details"); d.className = "chatui-think"; d.open = true;
      d.innerHTML = '<summary>🧠 reasoning</summary><div class="chatui-think-body"></div>';
      turn.appendChild(d); cur = { kind: "think", el: d, body: d.querySelector(".chatui-think-body"), _t: "" }; return cur; };
    const newAnswer = () => { endThink(); const d = document.createElement("div"); d.className = "chatui-msg chatui-bot";
      turn.appendChild(d); cur = { kind: "answer", el: d, _t: "", _raf: 0 }; answered = true; return cur; };
    const flush = () => { if (cur && cur.kind === "answer") { if (cur._raf) { cancelAnimationFrame(cur._raf); cur._raf = 0; } renderMd(cur.el, cur._t); } };
    const view = {
      reasoning(t) { if (!cur || cur.kind !== "think") newThink(); cur._t += t; cur.body.textContent = cur._t; scroll(); },
      token(t) { if (!cur || cur.kind !== "answer") newAnswer(); const c = cur; c._t += t;
        if (!c._raf) c._raf = requestAnimationFrame(() => { c._raf = 0; renderMd(c.el, c._t); scroll(); }); },
      // A tool call closes the current streaming block and appends its own, so a
      // read that happens AFTER some reasoning renders BELOW that reasoning.
      tool(label, detail) { endThink(); flush(); cur = null; let c;
        if (detail != null) { c = document.createElement("details"); c.className = "chatui-tool";
          c.innerHTML = "<summary>🔧 " + escHtml(String(label)) + "</summary>";
          const b = document.createElement("div"); b.className = "chatui-tool-body"; b.textContent = String(detail); c.appendChild(b);
        } else { c = document.createElement("div"); c.className = "chatui-tool"; c.textContent = "🔧 " + label; }
        turn.appendChild(c); scroll(); return c; },
      warn(msg) { endThink(); flush(); cur = null; const d = document.createElement("div"); d.className = "chatui-warn"; d.textContent = "⚠ " + msg; turn.appendChild(d); scroll(); return d; },
      note(msg) { flush(); cur = null; const d = document.createElement("div"); d.className = "chatui-usage"; d.textContent = msg; turn.appendChild(d); scroll(); return d; },
      usage(u) { u = u || {};
        const f = document.createElement("div"); f.className = "chatui-usage";
        if (u.context != null) {            // absolute context size + (optionally) the source's own window
          const win = u.window || CONTEXT_WINDOWS[u.model || ctx.model];
          f.textContent = "context " + u.context + (win ? " / " + win : "") + " tok" + (u.model ? " · " + u.model : "");
          setBudget(u.context, u.model, u.window);
        } else {
          const total = (u.input || 0) + (u.output || 0);
          const win = CONTEXT_WINDOWS[u.model || ctx.model];
          f.textContent = "↑ " + (u.input || 0) + " in · ↓ " + (u.output || 0) + " out" + (total ? " · context " + total + " tok" + (win ? " of " + win : "") : "");
          if (total) setBudget(total, u.model);   // bar matches the footer's context total
        }
        turn.appendChild(f); scroll(); },
      html(h) { endThink(); flush(); cur = null; const d = document.createElement("div"); d.className = "chatui-viz"; turn.appendChild(d); d.innerHTML = h; scroll(); return d; },
      error(msg) { errored = true; flush(); cur = null; const d = document.createElement("div"); d.className = "chatui-msg chatui-bot err"; d.textContent = "⚠ " + msg; turn.appendChild(d); scroll(); },
    };
    try { await opts.respond(q, { module: ctx.module, modules: ctx.modules, model: ctx.model, thread: ctx.thread, turn: ctx.turn, window: ctx.window, signal: curAC.signal, view }); }
    catch (e) { if (!curAC.signal.aborted) view.error(e && e.message ? e.message : String(e)); }
    finally {
      flush(); endThink();
      turn.classList.remove("chatui-cursor");
      if (curAC.signal.aborted) view.note("⏹ stopped");
      else if (!answered && !errored) { const d = document.createElement("div"); d.className = "chatui-msg chatui-bot"; d.textContent = "(no answer)"; turn.appendChild(d); }
      running = false; curAC = null;
      sendBtn.textContent = "Send"; sendBtn.classList.remove("stop");
      ctx.turn++; text.focus();
    }
  }
  sendBtn.addEventListener("click", () => { if (running) { try { curAC.abort(); } catch (_) {} } else send(); });
  text.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (!running) send(); } });
  text.addEventListener("input", () => { text.style.height = "auto"; text.style.height = Math.min(text.scrollHeight, 120) + "px"; });
  function reset() {
    if (curAC) { try { curAC.abort(); } catch (_) {} }
    log.querySelectorAll(".chatui-msg, .chatui-turn, .chatui-examples").forEach(n => n.remove());
    if (opts.greeting) bubble("chatui-bot", opts.greeting);
    addExamples();
    ctx.thread = "chat-" + Math.random().toString(36).slice(2, 9); ctx.turn = 0; setBudget(0);
    if (opts.onReset) try { opts.onReset(ctx); } catch (_) {}
  }
  resetBtn.addEventListener("click", reset);
  return { thread: ctx.thread, reset, ctx };
}

// Mount a live chat artifact backed by LangChain's createReactAgent. Handles the
// CDN load, one agent per model (each with its own MemorySaver), token + tool
// streaming, and the no-key guard, so a page only declares its tools + prompt.
export async function mountAgentChat(container, opts = {}) {
  /* @doc <code>helpers.mountAgentChat(el, opts)</code> :: Live chat artifact on LangChain <code>createReactAgent</code>. <code>opts</code>: <code>{ models:[{id,label}], system, buildTools({tool,z,coursePage,coursePages,webSearch,formatSearchResults}), greeting, modules, recursionLimit }</code>. Loads LangChain from a CDN, builds one agent per model (MemorySaver for multi-turn), streams tokens + tool chips, guards the missing key. The off-the-shelf companion to <code>mountChatUI</code>. */
  const el = typeof container === "string" ? document.querySelector(container) : container;
  if (!el) return null;
  let LC = null;
  async function deps() {
    if (!LC) {
      const [oai, core, prebuilt, lg, zod] = await Promise.all([
        import("https://cdn.jsdelivr.net/npm/@langchain/openai@1.4.7/+esm"),
        import("https://cdn.jsdelivr.net/npm/@langchain/core@1.1.48/tools/+esm"),
        import("https://cdn.jsdelivr.net/npm/@langchain/langgraph@1/prebuilt/+esm"),
        import("https://cdn.jsdelivr.net/npm/@langchain/langgraph@1/+esm"),
        import("https://cdn.jsdelivr.net/npm/zod@3/+esm"),
      ]);
      LC = { ChatOpenAI: oai.ChatOpenAI, tool: core.tool, createReactAgent: prebuilt.createReactAgent, MemorySaver: lg.MemorySaver, z: zod.z };
    }
    return LC;
  }
  const agents = {};
  async function getAgent(model) {
    if (!agents[model]) {
      const d = await deps();
      const cfg = await getConfig();
      const baseURL = cfg.url.startsWith("http") ? cfg.url : (window.location.origin + cfg.url);
      // The OpenAI SDK adds x-stainless-* platform headers that the CORS proxy
      // rejects in preflights. Strip them with a custom fetch wrapper.
      const _fetchNoStainless = (url, init) => {
        if (init && init.headers) {
          const h = init.headers instanceof Headers ? init.headers : new Headers(init.headers);
          for (const k of [...h.keys()]) { if (k.startsWith("x-stainless")) h.delete(k); }
          init = { ...init, headers: h };
        }
        return fetch(url, init);
      };
      const llm = new d.ChatOpenAI({ configuration: { baseURL, dangerouslyAllowBrowser: true,
        fetch: _fetchNoStainless },
        apiKey: cfg.needsKey ? getKey() : "no-key-needed", model, temperature: 0, maxTokens: 16384 });
      const tools = opts.buildTools
        ? opts.buildTools({ tool: d.tool, z: d.z, coursePage, coursePages, webSearch, formatSearchResults }) : [];
      agents[model] = d.createReactAgent({ llm, tools, checkpointer: new d.MemorySaver() });
    }
    return agents[model];
  }
  return mountChatUI(el, {
    modules: opts.modules, models: opts.models, intro: opts.intro, greeting: opts.greeting, examples: opts.examples,
    respond: async (text, ctx) => {
      const cfg = await getConfig();
      if (cfg.needsKey && !getKey()) { ctx.view.error("Add your nvapi- key on the course home, then chat."); return; }
      const agent = await getAgent(ctx.model);
      const messages = [];
      if (ctx.turn === 0 && opts.system) messages.push({ role: "system", content: typeof opts.system === "function" ? opts.system(ctx) : opts.system });
      // Pin one or more course pages chosen via the "Pages" chips (turn 0 only,
      // because later turns reuse the thread's checkpointed context). The whole page
      // is pinned and the whole page is shown in the chip, so nothing is clipped.
      if (ctx.turn === 0 && opts.modules) {
        for (const id of (ctx.modules || [])) {
          const body = await coursePage(id);
          ctx.view.tool("pinned " + id + " · " + estimateTokens(body) + " tok", body);
          messages.push({ role: "system", content: "Pinned course page (" + id + "):\n\n" + body });
        }
      }
      messages.push({ role: "user", content: text });
      // Pre-flight context-budget check: warn before the call if the turn 0
      // prompt alone would overflow the window, instead of letting the endpoint
      // drop tokens silently. (Later turns live in the checkpointed thread.)
      if (ctx.turn === 0) {
        const est = estimateTokens(messages);
        if (est > ctx.window) ctx.view.warn("This prompt is ~" + est + " tokens but " + ctx.model + " holds ~" + ctx.window + ". Unpin a page or split the question.");
      }
      const stream = await agent.stream({ messages },
        { streamMode: "messages", configurable: { thread_id: ctx.thread }, recursionLimit: opts.recursionLimit || 12, signal: ctx.signal });
      // Treat the trace as a stack: every tool call PUSHES its own chip, in the
      // order the agent makes it, and a chip is never reused. Chips are keyed by
      // the tool call's unique id (the streamed arg-delta chunks reset their
      // index to 0 on each new model message, so keying by index would make a
      // later read overwrite an earlier one). Reasoning, tool calls, and answer
      // tokens go to ctx.view as they arrive, so the transcript = the real run.
      const byId = {}, activeByIndex = {};
      let lastInput = 0, totalOutput = 0, sawUsage = false;
      const labelFor = (name, args) => {
        let a = ""; try { const o = JSON.parse(args || "{}"); a = o.page || o.id || o.query || o.expression || Object.values(o)[0] || ""; } catch (_) {}
        return a ? name + " · " + a : name;
      };
      const markErr = (c) => { if (c && c.el) { c.el.classList.add("err"); if (c.sumEl && !/^✗/.test(c.sumEl.textContent)) c.sumEl.textContent = "✗ " + c.sumEl.textContent.replace(/^🔧 /, ""); } };
      for await (const part of stream) {
        const chunk = Array.isArray(part) ? part[0] : part;
        const meta  = Array.isArray(part) ? part[1] : null;
        const node  = meta && meta.langgraph_node;
        // tool RESULT messages arrive on the "tools" node. Fill the matching
        // chip's body with the full text the tool returned (no clipping). If the
        // tool errored, mark the chip so the failure is shown, not hidden.
        if (node === "tools" && chunk.tool_call_id && byId[chunk.tool_call_id]) {
          const c = byId[chunk.tool_call_id];
          c.result = (c.result || "") + (typeof chunk.content === "string" ? chunk.content : JSON.stringify(chunk.content));
          if (c.bodyEl) c.bodyEl.textContent = c.result;
          if (chunk.status === "error" || /^\(unknown page|→ \d{3}$/.test(c.result.trim())) markErr(c);
          continue;
        }
        for (const tc of (chunk.tool_call_chunks || [])) {
          const idx = tc.index == null ? 0 : tc.index;
          let c;
          if (tc.id) {   // first chunk of a NEW call → push a fresh chip
            c = { name: tc.name || "tool", args: "" };
            c.el = ctx.view.tool((tc.name || "tool") + " …", "(running)");
            c.bodyEl = c.el.querySelector(".chatui-tool-body");
            c.sumEl = c.el.querySelector("summary");
            byId[tc.id] = c; activeByIndex[idx] = c;
          } else { c = activeByIndex[idx]; }   // arg-delta → the call open at this index
          if (!c) continue;
          if (tc.name) c.name = tc.name;
          c.args += (tc.args || "");
          if (c.sumEl) c.sumEl.textContent = "🔧 " + labelFor(c.name, c.args);
        }
        // reasoning deltas (nemotron exposes them on additional_kwargs)
        const rc = chunk.additional_kwargs && (chunk.additional_kwargs.reasoning_content || chunk.additional_kwargs.reasoning);
        if (rc && node === "agent") ctx.view.reasoning(typeof rc === "string" ? rc : String(rc));
        if (chunk.usage_metadata) { sawUsage = true; lastInput = chunk.usage_metadata.input_tokens || lastInput; totalOutput += chunk.usage_metadata.output_tokens || 0; }
        if (typeof chunk.content === "string" && chunk.content && node === "agent")
          ctx.view.token(chunk.content);
      }
      if (sawUsage) ctx.view.usage({ input: lastInput, output: totalOutput });
    },
    onReset: opts.onReset,
  });
}

// Render a list of search results into a single text blob the LLM can read.
// The shape mirrors what most search APIs return: numbered snippets with
// title + body + url. Pass this directly back to the model as a tool result.
export function formatSearchResults(searchOut) {
  /* @doc <code>helpers.formatSearchResults(out)</code> :: Turn a <code>webSearch</code> or <code>instantAnswer</code> result into a numbered text block the LLM can read as a tool message. */
  if (searchOut.unreachable) {
    const api = searchOut.source === "instant" ? "DuckDuckGo Instant Answer API" : "Wikipedia API";
    return `(search unavailable: ${searchOut.error || "HTTP " + searchOut.status}. ` +
           `The ${api} is public and CORS-open; this is usually a transient network error, so try again.)`;
  }
  if (!searchOut.results.length) {
    return `(no results for "${searchOut.query}". Tell the user you could not find current information on this; do not answer from memory.)`;
  }
  return searchOut.results.map((r, i) =>
    `[${i + 1}] ${r.title}\n    ${r.body}\n    ${r.href}`
  ).join("\n\n");
}

// viz builders, lifted to module scope so the helper menu can enumerate them
// and read their source at mount. runNode binds the per-node `log`; the menu
// uses VIZ_BUILDERS (a no-op-log instance) for names + source only.
function makeViz(log) {
  return {
      // Node/edge diagram from a data spec, so a cell never hand-writes SVG.
      // spec: { title?, caption?, nodes:[{id,label,kind,x,y,lines?}], edges:[{from,to,label?}] }
      // kind in env|agent|tool|data|model|neutral; x/y are grid columns/rows.
      diagram(spec) { /* @doc <code>helpers.viz.diagram(spec)</code> :: Render a node/edge figure from a data spec, so a cell never hand-writes SVG. <code>spec</code>: <code>{title?, caption?, nodes:[{id, label, kind, x, y, lines?}], edges:[{from, to, label?}]}</code>; <code>kind &isin; env|agent|tool|data|model|neutral</code>; <code>x</code>/<code>y</code> are grid columns/rows. Auto-themed and laid out. Use this instead of <code>log.draw</code> for boxes-and-arrows diagrams. */ log.svg(diagramSVG(spec)); },
      scoreBarChart(scored, opts = {}) {
        /* @doc <code>helpers.viz.scoreBarChart(scored, opts)</code> :: Render a 1-to-5 score bar chart with threshold and mean overlay. Pass an array of <code>{score, label?}</code> objects and optional <code>{threshold, title, width}</code>. */
        const { threshold = 3, title = "Score comparison", width = 560 } = opts;
        const BAR_H = 28, GAP = 8, PAD_L = 130, PAD_T = 48, PAD_B = 40, PAD_R = 80;
        const maxBarW = width - PAD_L - PAD_R;
        const H = PAD_T + scored.length * (BAR_H + GAP) + PAD_B;
        const mean = scored.reduce((s, x) => s + (x.score || 0), 0) / (scored.length || 1);
        const colorFor = s => s >= threshold ? "#76b900" : s === 3 ? "#d49c2c" : "#d74e4e";
        const textFor  = s => s >= threshold ? "#aee23a" : s === 3 ? "#e8c87a" : "#ff9a9a";
        const esc = t => String(t || "").replace(/[<>&]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[c]));
        let rows = "";
        scored.forEach((item, i) => {
          const y = PAD_T + i * (BAR_H + GAP);
          const sc = item.score || 0;
          const bw = Math.round((sc / 5) * maxBarW);
          const col = colorFor(sc);
          const tc  = textFor(sc);
          rows += `<text x="${PAD_L - 8}" y="${y + BAR_H / 2 + 4}" text-anchor="end" font-size="11" font-family="ui-monospace,monospace" fill="#b0b0b0">${esc(item.label || `item ${i + 1}`)}</text>`;
          rows += `<rect x="${PAD_L}" y="${y}" width="${maxBarW}" height="${BAR_H}" rx="3" fill="#161616"/>`;
          rows += `<rect x="${PAD_L}" y="${y}" width="${bw}" height="${BAR_H}" rx="3" fill="${col}" opacity="0.85"/>`;
          rows += `<text x="${PAD_L + bw + 6}" y="${y + BAR_H / 2 + 4}" font-size="12" font-family="ui-monospace,monospace" font-weight="700" fill="${tc}">${sc}/5</text>`;
          if (item.note) rows += `<text x="${PAD_L}" y="${y + BAR_H + 6}" font-size="9" font-family="ui-monospace,monospace" fill="#6a6a6a">${esc(item.note.slice(0, 70))}</text>`;
        });
        const thX = PAD_L + Math.round((threshold / 5) * maxBarW);
        rows += `<line x1="${thX}" y1="${PAD_T - 8}" x2="${thX}" y2="${PAD_T + scored.length * (BAR_H + GAP) - GAP + 4}" stroke="#d49c2c" stroke-width="1.5" stroke-dasharray="4 3"/>`;
        rows += `<text x="${thX + 3}" y="${PAD_T - 10}" font-size="9" font-family="ui-monospace,monospace" fill="#d49c2c">threshold ${threshold}</text>`;
        const meanX = PAD_L + Math.round((mean / 5) * maxBarW);
        rows += `<line x1="${meanX}" y1="${PAD_T - 8}" x2="${meanX}" y2="${PAD_T + scored.length * (BAR_H + GAP) - GAP + 4}" stroke="#76b900" stroke-width="1" stroke-dasharray="3 3" opacity="0.6"/>`;
        rows += `<text x="${meanX + 3}" y="${H - PAD_B / 2 + 4}" font-size="9" font-family="ui-monospace,monospace" fill="#76b900">mean ${mean.toFixed(2)}</text>`;
        log.svg(`<svg viewBox="0 0 ${width} ${H}" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;background:#0d0d0d;border:1px solid #2a2a2a;border-radius:6px">
          <text x="${width / 2}" y="22" text-anchor="middle" font-size="12" font-family="ui-monospace,monospace" fill="#aee23a" font-weight="700">${esc(title)}</text>
          ${rows}</svg>`);
      },

      messageList(messages, title = "Message sequence") {
        /* @doc <code>helpers.viz.messageList(messages, title)</code> :: Render a color-coded message sequence (USER=blue, ASSISTANT=green, TOOL=amber). Same shape the LLM API returns. Works with OpenAI <code>messages</code> arrays directly. */
        const W = 560, ROW_H = 58, PAD_T = 36, PAD_L = 20;
        const H = PAD_T + messages.length * ROW_H + 28;
        const esc = t => String(t || "").replace(/[<>&]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[c]));
        const colorFor = role => {
          if (role === "user")      return { bg: "#1e1e3a", border: "#3b82f6", text: "#7eb8ff" };
          if (role === "tool")      return { bg: "#3a2e1e", border: "#d49c2c", text: "#e8c87a" };
          if (role === "assistant") return { bg: "#1e3a1e", border: "#76b900", text: "#aee23a" };
          if (role === "system")    return { bg: "#2a1e3a", border: "#a78bfa", text: "#c4b5fd" };
          return { bg: "#1e1e1e", border: "#a5a5a5", text: "#a5a5a5" };
        };
        let body = "";
        messages.forEach((m, i) => {
          const y = PAD_T + i * ROW_H;
          const c = colorFor(m.role);
          let preview = "";
          let tag = m.role.toUpperCase();
          if (m.tool_calls && m.tool_calls.length) {
            tag = "ASSISTANT · tool_calls";
            const tc = m.tool_calls[0];
            preview = "calls " + (tc.function?.name || "?") + "(" + (tc.function?.arguments || "").slice(0, 55) + ")";
          } else if (m.content) {
            preview = String(m.content).slice(0, 90).replace(/\s+/g, " ");
          }
          body += `<circle cx="${PAD_L + 16}" cy="${y + 26}" r="14" fill="${c.bg}" stroke="${c.border}" stroke-width="2"/>`;
          body += `<text x="${PAD_L + 16}" y="${y + 31}" text-anchor="middle" font-size="11" font-family="ui-monospace,monospace" fill="${c.text}" font-weight="700">${i + 1}</text>`;
          if (i > 0) body += `<line x1="${PAD_L + 16}" y1="${y - 4}" x2="${PAD_L + 16}" y2="${y + 8}" stroke="#3a3a3a" stroke-width="1.2"/>`;
          body += `<rect x="${PAD_L + 38}" y="${y + 6}" width="${W - PAD_L - 48}" height="${ROW_H - 16}" rx="5" fill="${c.bg}" stroke="${c.border}"/>`;
          body += `<text x="${PAD_L + 48}" y="${y + 21}" font-size="10" font-family="ui-monospace,monospace" fill="${c.text}" font-weight="700">${esc(tag)}</text>`;
          body += `<text x="${PAD_L + 48}" y="${y + 37}" font-size="10" font-family="ui-monospace,monospace" fill="#e8e8e8">${esc(preview)}${preview.length > 80 ? "…" : ""}</text>`;
        });
        log.svg(`<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;background:#0d0d0d;border:1px solid #2a2a2a;border-radius:6px">
          <text x="${W / 2}" y="22" text-anchor="middle" font-size="11" font-family="ui-monospace,monospace" fill="#aee23a" font-weight="700">${esc(title)}</text>
          ${body}
          <text x="${W - 10}" y="${H - 8}" text-anchor="end" font-size="9" font-family="ui-monospace,monospace" fill="#6f6f6f">USER=blue · ASSISTANT=green · TOOL=amber · SYSTEM=purple</text></svg>`);
      },

      ganttBars(workers, wallSeconds, title = "Concurrency vs serial time") {
        /* @doc <code>helpers.viz.ganttBars(workers, wallSeconds, title)</code> :: Gantt-style bar chart comparing per-worker duration vs total wall time. Makes concurrency wins visible instantly. */
        log.svg(ganttBarsSVG(workers, wallSeconds, title));
      },

      retrievalBars(scored, topK = 3, title = "Retrieval scores") {
        /* @doc <code>helpers.viz.retrievalBars(scored, topK, title)</code> :: Horizontal score bars for retrieval results. Top-k entries highlighted green; the rest dimmed. Shows the semantic distance landscape. */
        const W = 560, BAR_H = 26, GAP = 8, PAD_L = 20, PAD_T = 48, PAD_B = 24, PAD_R = 70;
        const maxBarW = W - PAD_L - PAD_R;
        const maxScore = Math.max(...scored.map(x => x.score || 0), 1);
        const H = PAD_T + scored.length * (BAR_H + GAP) + PAD_B;
        const esc = t => String(t || "").replace(/[<>&]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[c]));
        let body = "";
        scored.forEach((item, i) => {
          const y = PAD_T + i * (BAR_H + GAP);
          const bw = Math.round((item.score / maxScore) * maxBarW);
          const isTop = i < topK;
          const col  = isTop ? "#76b900" : "#2a2a2a";
          const tCol = isTop ? "#aee23a" : "#6a6a6a";
          const preview = String(item.text || "").slice(0, 58).replace(/\s+/g, " ");
          body += `<rect x="${PAD_L}" y="${y}" width="${maxBarW}" height="${BAR_H}" rx="3" fill="#161616"/>`;
          body += `<rect x="${PAD_L}" y="${y}" width="${bw}" height="${BAR_H}" rx="3" fill="${col}" opacity="${isTop ? 0.8 : 0.4}"/>`;
          body += `<text x="${PAD_L + 6}" y="${y + BAR_H / 2 + 4}" font-size="10" font-family="ui-monospace,monospace" fill="${tCol}">${isTop ? "★ " : ""}${esc(preview)}</text>`;
          body += `<text x="${PAD_L + maxBarW + 5}" y="${y + BAR_H / 2 + 4}" font-size="11" font-family="ui-monospace,monospace" fill="${tCol}" font-weight="700">${(item.score || 0).toFixed(3)}</text>`;
        });
        log.svg(`<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;background:#0d0d0d;border:1px solid #2a2a2a;border-radius:6px">
          <text x="${W / 2}" y="22" text-anchor="middle" font-size="12" font-family="ui-monospace,monospace" fill="#aee23a" font-weight="700">${esc(title)}</text>
          <text x="${PAD_L}" y="38" font-size="9" font-family="ui-monospace,monospace" fill="#6a6a6a">top-${topK} highlighted · score normalized to max=${maxScore.toFixed(3)}</text>
          ${body}</svg>`);
      },

      // helpers.viz.diffTable({ left, right, rows, notes?, verdict? }, opts?)
      //
      // Before/after comparison table for one rotation of an eval / flywheel
      // / "did this change help?" cell. Hides ~50 lines of inline SVG plumbing
      // the cells used to repeat. Row shapes:
      //
      //   { kind: "check", label, left, right }              ✓ / ✗ per side
      //   { kind: "num",   label, left, right,
      //     betterWhen: "up" | "down" | null,                colour the delta
      //     fmt: (v) => string }                             optional formatter
      //
      // opts: { title?, width? }. The title shows at top, and width defaults to 760.
      diffTable(spec = {}, opts = {}) {
        /* @doc <code>helpers.viz.diffTable(spec, opts)</code> :: Before/after comparison table. <code>spec.rows</code> entries are <code>{kind:"check", label, left, right}</code> or <code>{kind:"num", label, left, right, betterWhen:"up"|"down", fmt?}</code>. Colour-coded deltas, check marks, footer notes, and an optional <code>verdict({rows})</code> returning <code>{ok, text}</code>. */
        const rows  = Array.isArray(spec.rows) ? spec.rows : [];
        const notes = Array.isArray(spec.notes) ? spec.notes : [];
        const verdict = typeof spec.verdict === "function" ? spec.verdict : null;
        const left   = spec.left  || "before";
        const right  = spec.right || "after";
        const title  = opts.title || "Before / after";
        const W      = opts.width || 760;
        const ROW_H  = 24;
        const PAD_T  = 60;
        const COL1   = 40, COL2 = 290, COL3 = 510, COL4 = 640;
        const escTxt = t => String(t == null ? "" : t).replace(/[<>&]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[c]));
        const fmtNum = (v, fmt) => fmt ? fmt(v) : (typeof v === "number" ? (Number.isInteger(v) ? String(v) : v.toFixed(2)) : String(v));

        // Pre-compute deltas + good/bad colour per row
        const rendered = rows.map(r => {
          const o = { ...r };
          if (r.kind === "num" && typeof r.left === "number" && typeof r.right === "number") {
            o.delta = r.right - r.left;
            const fmt = r.fmt || (v => fmtNum(v, null));
            o.deltaStr = (o.delta > 0 ? "+" : "") + fmt(o.delta);
            o.deltaCol = "#6f6f6f";
            if (r.betterWhen === "up")   o.deltaCol = o.delta >= 0 ? "#aee23a" : "#d74e4e";
            if (r.betterWhen === "down") o.deltaCol = o.delta <= 0 ? "#aee23a" : "#d74e4e";
          }
          return o;
        });

        const checksH = ROW_H * rendered.filter(r => r.kind === "check").length;
        const numsH   = ROW_H * rendered.filter(r => r.kind === "num").length;
        const notesH  = (notes.length + (verdict ? 1 : 0)) * 18 + 12;
        const H       = PAD_T + checksH + (checksH && numsH ? 12 : 0) + numsH + (notesH ? notesH + 8 : 0) + 18;

        let body = "";
        body += `<text x="20" y="22" font-size="11" font-family="ui-monospace,monospace" fill="#6f6f6f" font-weight="700">${escTxt(title)}</text>`;
        body += `<text x="${COL2}" y="48" text-anchor="middle" font-size="11" font-family="ui-monospace,monospace" fill="#a5a5a5" font-weight="700">${escTxt(left)}</text>`;
        body += `<text x="${COL3}" y="48" text-anchor="middle" font-size="11" font-family="ui-monospace,monospace" fill="#aee23a" font-weight="700">${escTxt(right)}</text>`;
        body += `<line x1="20" y1="58" x2="${W - 20}" y2="58" stroke="#2a2a2a"/>`;

        let y = PAD_T + 12;
        const checks = rendered.filter(r => r.kind === "check");
        checks.forEach(r => {
          body += `<text x="${COL1}" y="${y}" font-size="10" font-family="ui-monospace,monospace" fill="#a5a5a5">${escTxt(r.label)}</text>`;
          body += `<text x="${COL2}" y="${y}" text-anchor="middle" font-size="11" font-family="ui-monospace,monospace" fill="${r.left ? "#aee23a" : "#d74e4e"}" font-weight="700">${r.left ? "✓" : "✗"}</text>`;
          body += `<text x="${COL3}" y="${y}" text-anchor="middle" font-size="11" font-family="ui-monospace,monospace" fill="${r.right ? "#aee23a" : "#d74e4e"}" font-weight="700">${r.right ? "✓" : "✗"}</text>`;
          y += ROW_H;
        });
        if (checks.length && rendered.some(r => r.kind === "num")) {
          body += `<line x1="20" y1="${y - 8}" x2="${W - 20}" y2="${y - 8}" stroke="#2a2a2a"/>`;
          y += 4;
        }
        rendered.filter(r => r.kind === "num").forEach(r => {
          body += `<text x="${COL1}" y="${y}" font-size="10" font-family="ui-monospace,monospace" fill="#a5a5a5">${escTxt(r.label)}</text>`;
          body += `<text x="${COL2}" y="${y}" text-anchor="middle" font-size="12" font-family="ui-monospace,monospace" fill="#7eb8ff">${escTxt(fmtNum(r.left, r.fmt))}</text>`;
          body += `<text x="${COL3}" y="${y}" text-anchor="middle" font-size="12" font-family="ui-monospace,monospace" fill="#aee23a">${escTxt(fmtNum(r.right, r.fmt))}</text>`;
          if (r.deltaStr) body += `<text x="${COL4}" y="${y}" font-size="11" font-family="ui-monospace,monospace" fill="${r.deltaCol}">${escTxt(r.deltaStr)}</text>`;
          y += ROW_H;
        });

        y += 8;
        notes.forEach(n => {
          body += `<text x="20" y="${y}" font-size="10" font-family="ui-monospace,monospace" fill="#6f6f6f">${escTxt(n)}</text>`;
          y += 18;
        });
        if (verdict) {
          const v = verdict({ rows: rendered });
          const ok = v && v.ok !== false;
          const txt = (v && v.text) || (typeof v === "string" ? v : "");
          body += `<text x="20" y="${y}" font-size="10" font-family="ui-monospace,monospace" fill="${ok ? "#aee23a" : "#e8c87a"}" font-weight="700">verdict: ${escTxt(txt)}</text>`;
        }

        log.draw(W, H, body, { title: null });
      },

      // chat(turns, opts?) renders a flat chat transcript.
      // turns: array of [role, content] pairs, role ∈ {user|assistant|ai|system|tool}.
      // opts: { title?, maxChars = 240 per turn, width = 720 }.
      chat(turns = [], opts = {}) {
        /* @doc <code>helpers.viz.chat(turns, opts?)</code> :: Render a chat transcript as colour-coded bubbles. <code>turns</code>: array of <code>[role, content]</code> pairs; <code>role &isin; {user, assistant|ai, system, tool}</code>. <code>opts.maxChars</code> truncates per turn. Replaces hand-rolled chat-output text loops. */
        const W = opts.width || 720;
        const PAD_T = 40, PAD = 18, GAP = 8;
        const maxChars = opts.maxChars || 240;
        const escTxt = t => String(t == null ? "" : t).replace(/[<>&]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[c]));
        const palette = {
          user:      { bg: "#1e1e3a", border: "#3b82f6", lbl: "#7eb8ff", txt: "#e8e8e8", tag: "USER" },
          system:    { bg: "#2a1e3a", border: "#a78bfa", lbl: "#c4b5fd", txt: "#e8e8e8", tag: "SYSTEM" },
          tool:      { bg: "#3a2e1e", border: "#d49c2c", lbl: "#e8c87a", txt: "#e8e8e8", tag: "TOOL" },
          ai:        { bg: "#1e3a1e", border: "#76b900", lbl: "#aee23a", txt: "#e8e8e8", tag: "ASSISTANT" },
          assistant: { bg: "#1e3a1e", border: "#76b900", lbl: "#aee23a", txt: "#e8e8e8", tag: "ASSISTANT" },
        };
        const linesOf = (s, perLine = 70) => {
          const t = String(s || "").replace(/\s+/g, " ").slice(0, maxChars);
          const lines = [];
          for (let i = 0; i < t.length; i += perLine) lines.push(t.slice(i, i + perLine));
          if (String(s || "").length > maxChars) lines[lines.length - 1] = (lines[lines.length - 1] || "") + "…";
          return lines.length ? lines : ["(empty)"];
        };
        let y = PAD_T;
        let body = "";
        for (const [rawRole, content] of turns) {
          const p = palette[String(rawRole || "").toLowerCase()] || palette.user;
          const lines = linesOf(content);
          const bubbleH = 22 + lines.length * 14 + 6;
          body += `<rect x="${PAD}" y="${y}" width="${W - 2 * PAD}" height="${bubbleH}" rx="6" fill="${p.bg}" stroke="${p.border}"/>`;
          body += `<text x="${PAD + 10}" y="${y + 16}" font-size="10" font-family="ui-monospace,monospace" fill="${p.lbl}" font-weight="700" letter-spacing="0.08em">${p.tag}</text>`;
          lines.forEach((l, i) => {
            body += `<text x="${PAD + 10}" y="${y + 32 + i * 14}" font-size="11" font-family="ui-monospace,monospace" fill="${p.txt}">${escTxt(l)}</text>`;
          });
          y += bubbleH + GAP;
        }
        log.draw(W, y + PAD, body, { title: opts.title || null });
      },

      // sideBySide(leftLines, rightLines, opts?) renders two columns of text.
      // opts: { leftTitle, rightTitle, footer }.
      sideBySide(leftLines = [], rightLines = [], opts = {}) {
        /* @doc <code>helpers.viz.sideBySide(leftLines, rightLines, opts?)</code> :: Two text columns. <code>opts</code>: <code>{leftTitle, rightTitle, footer}</code>. */
        const W = 760, COL_GAP = 18, colW = (W - 24 - COL_GAP) / 2;
        const esc = t => String(t == null ? "" : t).replace(/[<>&]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[c]));
        const rows = Math.max(leftLines.length, rightLines.length, 1);
        const bodyH = 60 + rows * 16;
        const H = bodyH + (opts.footer ? 24 : 0) + 12;
        const col = (x, title, lines) => {
          let out = `<text x="${x + 10}" y="32" font-size="11" font-family="ui-monospace,monospace" fill="#7eb8ff" font-weight="700">${esc(title || "")}</text>`;
          out += `<rect x="${x}" y="42" width="${colW}" height="${bodyH - 42}" rx="6" fill="#0d0d0d" stroke="#3a3a3a"/>`;
          (lines || []).forEach((line, i) => {
            out += `<text x="${x + 10}" y="${62 + i * 16}" font-size="10" font-family="ui-monospace,monospace" fill="#a5a5a5">${esc(line)}</text>`;
          });
          return out;
        };
        let body = col(12, opts.leftTitle,  leftLines)
                 + col(12 + colW + COL_GAP, opts.rightTitle, rightLines);
        if (opts.footer) {
          body += `<text x="${W / 2}" y="${H - 12}" text-anchor="middle" font-size="10" font-family="ui-monospace,monospace" fill="#a5a5a5">${esc(opts.footer)}</text>`;
        }
        log.draw(W, H, body, { title: opts.title || null });
      },
  };
}
const VIZ_BUILDERS = makeViz(() => {});

// ── Helper registry (single source of truth for the canvas helper menu) ───────
// The menu enumerates these and reads each one's source via Function.toString(),
// so the inspectable source can never drift from the actual definition. Add a
// helper to this object (and to baseHelpers below) and it documents itself.
// `viz.*` source comes from the live viz object once a node has run; `state`,
// `fetch`, `trace`, and `log` are described by SPECIALS (they are a value, the
// platform primitive, and per-node closures, not plain module functions).
const HELPER_FNS = {
  chat, chatStream, webSearch, instantAnswer, formatSearchResults,
  embed, cosineSim, fetchRetry, getConfig, getKey, terminal,
  coursePage, coursePages, contextWindow, estimateTokens, browserChatFetch, diagramSVG, ganttBarsSVG, mountChatUI, mountAgentChat, mountKeyPanel, openclawChat,
};
// SPECIALS: the menu entries that are not plain module functions. They are a value
// (state), the platform primitive (fetch), and per-node closures (trace, log).
// Each carries the row's sig + desc and the source shown in the editor. The menu
// reads sig/desc from a helper's @doc when it is a function, and from here
// otherwise, so there is exactly one place to look for any given row.
const SPECIALS = {
  state: {
    sig: "<code>state</code>",
    desc: `Plain object shared across every node. Set a field in one node (e.g. <code>state.question = "…"</code>) and any later node reads it. Reset when you click <strong>▶ Run all</strong>.`,
    src: `// 'state' is a plain object, created fresh for each Run-all.\n// Write a field in one node, read it from any later node:\nstate.docVectors = await helpers.embed(chunks, { inputType: "passage" });\n// ...then, in a downstream node:\nconst hits = rank(state.docVectors, queryVector);`,
  },
  fetch: {
    sig: "<code>helpers.fetch(url, opts)</code>",
    desc: `The browser's native <code>fetch</code>, exposed unchanged so a node can call any HTTP endpoint directly. Same arguments and same <code>Response</code> as the platform API. It does <em>not</em> retry and does <em>not</em> attach a key: for flaky upstreams use <code>helpers.fetchRetry</code>, and for model, search, or embedding calls prefer the dedicated helpers above (they add the route and the key for you).`,
    src: `// helpers.fetch === the browser fetch, unwrapped. You own retries and auth.\nconst r = await helpers.fetch("https://api.example.com/v1/items", {\n  method: "POST",\n  headers: { "Content-Type": "application/json" },\n  body: JSON.stringify({ q: "hello" }),\n});\nif (!r.ok) throw new Error("HTTP " + r.status);\nconst data = await r.json();\n\n// Prefer the purpose-built helpers when you can:\n//   helpers.chat / chatStream  for model calls (key + route attached)\n//   helpers.webSearch / embed   for search + embeddings\n//   helpers.fetchRetry          like fetch, but retries 5xx / network errors`,
  },
  trace: {
    sig: "<code>helpers.trace(name, attrs)</code>",
    desc: `Emit an OTel-shaped span event into a per-canvas trace store. Instrument any step that does work, not just LLM calls. Read <code>state.__trace</code> from a later node to inspect every emit.`,
    src: `// helpers.trace(name, attrs) appends a span to state.__trace.\nhelpers.trace("retrieve", { k: 5, ms: 42, hits: hits.length });\n// ...inspect them later:\nconsole.table(state.__trace);`,
  },
  log: {
    sig: "<code>helpers.log(...args)</code>",
    desc: `Append a line to this node's <em>log</em> area (under the streamed output). Also exposes <code>log.html(html)</code>, <code>log.svg(svgString)</code>, and <code>log.draw(W, H, body, opts)</code>, which wraps the SVG frame boilerplate so a cell only declares its marks.`,
    src: `// helpers.log writes to THIS node's log area.\nhelpers.log("retrieved", hits.length, "chunks");\nhelpers.log.html("<b>done</b>");\nhelpers.log.svg("<svg viewBox='0 0 80 80'>...</svg>");\nhelpers.log.draw(320, 120, '<circle cx="60" cy="60" r="40" fill="#76b900"/>', { title: "demo" });`,
  },
};

// Parse a helper's self-doc from its definition: a leading `/* @doc <sig> :: <desc> */`
// comment inside the function body. Read via Function.toString(), so it is tied to
// the code and works both in the lab and in the inlined standalone build. The menu
// prefers this over any curated fallback, so the docs cannot drift from the source.
function _docFor(name) {
  let fn = HELPER_FNS[name];
  if (!fn && name.startsWith("viz.") && typeof VIZ_BUILDERS !== "undefined") fn = VIZ_BUILDERS[name.slice(4)];
  if (typeof fn !== "function") return {};
  const m = fn.toString().match(/\/\*\s*@doc\b([\s\S]*?)\*\//);
  if (!m) return {};
  const body = m[1].trim();
  const i = body.indexOf("::");
  return i >= 0 ? { sig: body.slice(0, i).trim(), desc: body.slice(i + 2).trim() } : { desc: body };
}

// Build the helper-menu rows by enumerating everything the runtime exposes, in a
// fixed logical order. The category map below is only a grouping decision; the
// NAMES come from the live registries (HELPER_FNS, VIZ_BUILDERS) plus the SPECIALS,
// so the menu can neither omit a helper nor list one that does not exist. Anything
// exposed but not categorized still shows (under "Other") and warns, so nothing drops silently.
function _buildHelperRows() {
  const CATS = [
    ["Shared state",            ["state"]],
    ["Model calls",             ["chat", "chatStream"]],
    ["Web search",              ["webSearch", "instantAnswer", "formatSearchResults"]],
    ["Embeddings & similarity", ["embed", "cosineSim"]],
    ["Raw HTTP",                ["fetch", "fetchRetry"]],
    ["Launchable terminal",     ["terminal"]],
    ["Course content",          ["coursePage", "coursePages"]],
    ["Live artifacts",          ["mountChatUI", "mountAgentChat", "mountKeyPanel"]],
    ["OpenClaw gateway",        ["openclawChat"]],
    ["Config",                  ["getConfig", "getKey"]],
    ["Instrumentation",         ["trace", "log"]],
  ];
  const universe = new Set([
    "state",
    ...Object.keys(HELPER_FNS),
    "fetch", "trace", "log",
    ...(typeof VIZ_BUILDERS !== "undefined" ? Object.keys(VIZ_BUILDERS).map(k => "viz." + k) : []),
  ]);
  const placed = new Set();
  const out = [];
  const push = (name) => { placed.add(name); out.push({ row: name, editable: name !== "state" }); };
  for (const [head, names] of CATS) {
    const present = names.filter(n => universe.has(n));
    if (!present.length) continue;
    out.push({ sectionHead: head });
    present.forEach(push);
  }
  const vizNames = typeof VIZ_BUILDERS !== "undefined" ? Object.keys(VIZ_BUILDERS).map(k => "viz." + k) : [];
  if (vizNames.length) { out.push({ sectionHead: "Visualization · <code>helpers.viz.*</code>" }); vizNames.forEach(push); }
  const orphans = [...universe].filter(n => !placed.has(n));
  if (orphans.length) {
    console.warn("[helpers menu] uncategorized helpers (add to _buildHelperRows CATS):", orphans);
    out.push({ sectionHead: "Other" });
    orphans.forEach(push);
  }
  return out;
}

// ── UI helpers ────────────────────────────────────────────────────────────────
export function $ (sel) { return document.querySelector(sel); }
export function $$ (sel) { return [...document.querySelectorAll(sel)]; }

export function renderOutput(el, content, type = "text") {
  if (!el) return;
  el.innerHTML = "";
  el.className = `output ${type}`;
  if (type === "json") {
    const pre = document.createElement("pre");
    pre.textContent = typeof content === "string" ? content : JSON.stringify(content, null, 2);
    el.appendChild(pre);
  } else {
    el.textContent = content;
  }
}

export function setRunning(btn, running) {
  btn.disabled = running;
  btn.textContent = running ? "⏳ Running…" : "▶ Run";
}

export function showError(el, msg) {
  if (!el) return;
  el.innerHTML = `<span class="err">⚠ ${escHtml(msg)}</span>`;
  el.className = "output error";
}

function escHtml(s) { return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

// ── Page nav ──────────────────────────────────────────────────────────────────
// Deliberately empty. All in-course navigation lives in the journey-map widget
// below the topbar: it shows the current section, prev/next links to the
// adjacent pages, and a "Course map" toggle that reveals the full staircase.
// The topbar carries the brand and the key-pill only.
export function buildNav(_currentFile) {
  return "";
}

// ── Journey map ─────────────────────────────────────────────────────────────
// Per-page progression: every sub-page is its own box. Three boxes per row, and
// each row offsets right by STAIR pixels so the whole figure cascades down a
// staircase. Each section (1, 2, 3, 4) fills one row exactly; the final row
// holds Section 5 + Lab & Cert + Going Further.
//
//   mountJourneyMap("#journey", "2b");    // highlights the 2b box
//   mountJourneyMap("#journey", "cert");  // highlights Lab & Cert
//   mountJourneyMap("#journey", "next");  // highlights Going Further
//
// Done boxes get a dim "✓ Done"; the current box gets a green "★ You are here";
// pending boxes stay neutral. Resilient: if the target element is missing the
// call is a no-op.
const _JM_STEPS = [
  // Row 1 · Module 1 · The Loop
  { id: "1a",   href: "01a-loop.html",        title: "The Agent",       sub: "loop · LLM as function" },
  { id: "1b",   href: "01b-react.html",       title: "The ReAct Loop",  sub: "tools · finish_reason" },
  { id: "1c",   href: "01c-tools.html",       title: "Tools at Scale",  sub: "JSON · MCP · routing" },
  // Row 2 · Module 2 · Coordination
  { id: "2a",   href: "02a-routing.html",     title: "Workflows",       sub: "router · planner · ReWOO" },
  { id: "2b",   href: "02b-rag.html",         title: "The Index Agent", sub: "embed · retrieve · bundle" },
  { id: "2c",   href: "02c-deep.html",        title: "Deep Agents",     sub: "planner · sub-agents · VFS" },
  // Row 3 · Module 3 · Environment + OpenClaw
  { id: "3a",   href: "03a-kickstart.html",   title: "Kickstart",       sub: "paste key · first call" },
  { id: "3b",   href: "03b-openclaw.html",    title: "OpenClaw",        sub: "file-as-context · paste URL" },
  { id: "3c",   href: "03c-always-on.html",   title: "Always-On",       sub: "skills · cron" },
  // Row 4 · Module 4 · Safety + Modern CLIs
  { id: "4a",   href: "04a-safety.html",      title: "NemoClaw",        sub: "sandbox · policy · CI gate" },
  { id: "4b",   href: "04b-modern-clis.html", title: "Modern CLIs",     sub: "Claude Code · Codex · Cursor" },
  { id: "4c",   href: "04c-going-further.html", title: "Going Further", sub: "Brev · NIMs · Blueprints" },
];

// Friendly label for the "Module N" banner on the left of the bar. Sections
// (1-4) get a "Section N" label; Going Further is the end of the course (this
// short course has no separate assessment, so the cert belongs to the long course).
function _jmSectionLabel(stepId) {
  if (stepId === "next") return "Going Further";
  const m = String(stepId).match(/^(\d)/);
  return m ? `Section ${m[1]}` : "";
}

function _escAttr(s) {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;");
}

export function mountJourneyMap(targetSel, current) {
  const target = typeof targetSel === "string" ? document.querySelector(targetSel) : targetSel;
  if (!target) return;
  const idx  = _JM_STEPS.findIndex(s => s.id === current);
  const cur  = idx >= 0 ? _JM_STEPS[idx] : null;
  const prev = idx > 0                       ? _JM_STEPS[idx - 1] : null;
  const next = idx >= 0 && idx < _JM_STEPS.length - 1 ? _JM_STEPS[idx + 1] : null;
  const sectionLabel = cur ? _jmSectionLabel(cur.id) : "Section";

  // ── Full-staircase SVG (revealed when the section banner is clicked) ──
  const W      = 210;
  const H      = 56;
  const GAP_X  = 16;
  const GAP_Y  = 16;
  const PAD    = 12;
  const STAIR  = 64;
  const perRow = 3;
  const rows   = Math.ceil(_JM_STEPS.length / perRow);
  const viewW  = PAD * 2 + perRow * W + (perRow - 1) * GAP_X + (rows - 1) * STAIR;
  const viewH  = PAD * 2 + rows * H + (rows - 1) * GAP_Y;

  const boxes = _JM_STEPS.map((step, i) => {
    const row = Math.floor(i / perRow);
    const col = i % perRow;
    const x = PAD + col * (W + GAP_X) + row * STAIR;
    const y = PAD + row * (H + GAP_Y);
    const isCurrent = i === idx;
    const isDone    = idx >= 0 && i < idx;
    const fill   = isCurrent ? "#2a3a16" : (isDone ? "#1a2912" : "#161616");
    const stroke = isCurrent ? "#76b900" : (isDone ? "#4a7a00" : "#2a2a2a");
    const sw     = isCurrent ? 2.2 : 1.1;
    const titleColor = isCurrent ? "#aee23a" : (isDone ? "#7a8a7a" : "#e8e8e8");
    const subColor   = isCurrent ? "#76b900" : (isDone ? "#5a5a5a" : "#a5a5a5");
    const titlePrefix = isCurrent ? "★ " : (isDone ? "✓ " : "");
    return `
      <a href="${step.href}" style="text-decoration:none;">
        <g>
          <rect x="${x}" y="${y}" width="${W}" height="${H}" rx="8"
                fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>
          <text x="${x + W/2}" y="${y + 24}" text-anchor="middle"
                style="font:700 13.5px -apple-system,'Segoe UI',sans-serif;fill:${titleColor};">${titlePrefix}${step.title}</text>
          <text x="${x + W/2}" y="${y + 42}" text-anchor="middle"
                style="font:400 10.5px -apple-system,'Segoe UI',sans-serif;fill:${subColor};">${step.sub || ""}</text>
        </g>
      </a>`;
  }).join("");

  // Right-arrows between consecutive boxes within the same row.
  const arrows = [];
  for (let i = 0; i < _JM_STEPS.length - 1; i++) {
    const row1 = Math.floor(i / perRow), col1 = i % perRow;
    const row2 = Math.floor((i + 1) / perRow);
    if (row1 !== row2) continue;
    const x1 = PAD + col1 * (W + GAP_X) + row1 * STAIR + W;
    const x2 = x1 + GAP_X;
    const cy = PAD + row1 * (H + GAP_Y) + H / 2;
    arrows.push(`<path d="M ${x1} ${cy} L ${x2} ${cy}" stroke="#6f6f6f" stroke-width="1.4" fill="none" marker-end="url(#jm-arr)"/>`);
  }
  const fullSvg = `
    <svg viewBox="0 0 ${viewW} ${viewH}" preserveAspectRatio="xMidYMid meet"
         xmlns="http://www.w3.org/2000/svg"
         role="img" aria-label="Course progression; current step highlighted."
         class="cf-jm-svg" style="display:block;width:100%;height:auto;">
      <defs>
        <marker id="jm-arr" viewBox="0 0 10 10" refX="9" refY="5"
                markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0,0 L10,5 L0,10 Z" fill="#6f6f6f"/>
        </marker>
      </defs>
      ${arrows.join("")}
      ${boxes}
    </svg>`;

  // ── Slim bar: [Section banner] [current page info] [prev] [next] ──
  // For pages that don't pass a known current id (e.g. index.html passes null),
  // collapse to a single "Course map · click to expand" banner with no
  // prev/next stubs.
  let barInner;
  if (!cur) {
    barInner = `
      <button class="cf-jm-mod cf-jm-mod-wide" type="button" aria-expanded="false"
              title="Show the whole course map">
        <span class="cf-jm-mod-label">Course map</span>
        <span class="cf-jm-current-title" style="color:var(--td);font-weight:500;font-size:.92rem;margin-left:14px;">click to see all sections</span>
        <span class="cf-jm-mod-chevron" aria-hidden="true" style="margin-left:auto;">▾</span>
      </button>`;
  } else {
    const curId    = cur.id;
    const curTitle = cur.title;
    const curSub   = cur.sub || "";
    const prevLink = prev
      ? `<a class="cf-jm-prev" href="${_escAttr(prev.href)}" title="Previous: ${_escAttr(prev.title)}">
           <span class="cf-jm-nav-arrow">←</span>
           <span class="cf-jm-nav-text">
             <span class="cf-jm-nav-id">${prev.id}</span>
             <span class="cf-jm-nav-title">${prev.title}</span>
           </span>
         </a>`
      : `<span class="cf-jm-prev cf-jm-disabled" aria-hidden="true">
           <span class="cf-jm-nav-arrow">←</span>
           <span class="cf-jm-nav-text"><span class="cf-jm-nav-id">start</span></span>
         </span>`;
    const nextLink = next
      ? `<a class="cf-jm-next" href="${_escAttr(next.href)}" title="Next: ${_escAttr(next.title)}">
           <span class="cf-jm-nav-text">
             <span class="cf-jm-nav-id">${next.id}</span>
             <span class="cf-jm-nav-title">${next.title}</span>
           </span>
           <span class="cf-jm-nav-arrow">→</span>
         </a>`
      : `<span class="cf-jm-next cf-jm-disabled" aria-hidden="true">
           <span class="cf-jm-nav-text"><span class="cf-jm-nav-id">end</span></span>
           <span class="cf-jm-nav-arrow">→</span>
         </span>`;
    barInner = `
      <button class="cf-jm-mod" type="button" aria-expanded="false"
              title="Show the whole course map">
        <span class="cf-jm-mod-label">${sectionLabel}</span>
        <span class="cf-jm-mod-chevron" aria-hidden="true">▾</span>
      </button>
      <div class="cf-jm-current">
        <span class="cf-jm-current-id">${curId.toUpperCase()}</span>
        <span class="cf-jm-current-title">${curTitle}</span>
        ${curSub ? `<span class="cf-jm-current-sub">${curSub}</span>` : ""}
      </div>
      <div class="cf-jm-nav-group">
        ${prevLink}
        ${nextLink}
      </div>`;
  }

  target.innerHTML = `
    <div class="cf-jm-wrap">
      <div class="cf-jm-bar">
        ${barInner}
      </div>
      <div class="cf-jm-full" hidden>
        ${fullSvg}
      </div>
    </div>`;

  // Click handler: toggle the full staircase.
  const modBtn = target.querySelector(".cf-jm-mod");
  const full   = target.querySelector(".cf-jm-full");
  const chev   = target.querySelector(".cf-jm-mod-chevron");
  if (modBtn && full) {
    modBtn.addEventListener("click", () => {
      const expanded = full.hidden;
      full.hidden = !expanded;
      modBtn.setAttribute("aria-expanded", String(expanded));
      if (chev) chev.textContent = expanded ? "▴" : "▾";
    });
  }
}

// ── runCell: editable in-page code sandbox with syntax highlighting ─────────
//
// Mounts an editable JavaScript textarea in the page. When the student clicks
// Run, the textarea's contents execute in an async sandbox with chat,
// chatStream, log, clear, MODEL, ui, schemas in scope. Pattern matches the
// edx-track runner so the two tracks share semantics.
//
// Uses CodeMirror 5 when it's loaded (the page should include the cdnjs
// codemirror.min.{css,js}, theme/monokai.min.css, and the javascript mode).
// Falls back to a plain textarea if CodeMirror is unavailable (offline lab).
//
//   const cell = mountRunCell("#cell-1", {
//     code: "const r = await chatStream({messages:[{role:'user',content:'hi'}]}, log);",
//     schemas: { CALC_SCHEMA: [{ type: "function", function: {...} }] },
//   });
//
// `schemas` becomes an editable JSON block inside the cell. The student edits
// it and the parsed object is passed to the sandboxed code as a named variable
// (e.g. `CALC_SCHEMA`). If parsing fails, the cell shows the parse error
// instead of running, so the student gets the actual error message.
const _runCellAborts = new Map();

// ── Kernel execution for editable run-cells in Python mode ───────────────────
// mountCanvasFlow keeps its own per-canvas kernel machinery; this is a
// self-contained copy so a run-cell can execute its Python variant on a
// JupyterLab kernel without coupling to a canvas. Same Jupyter websocket
// protocol. Claims an unclaimed python3 kernel (sharing the page-wide
// __nv_claimed_kernels__ set so it does not steal a canvas's kernel) and
// reuses it across re-runs so state persists within the cell.
let _rcKernelId = null;
async function _rcFindKernel() {
  if (_rcKernelId) {
    try {
      const info = await fetch(`/lab/api/kernels/${_rcKernelId}`, { credentials: "include" }).then(r => r.ok ? r.json() : null);
      if (info?.id) return _rcKernelId;
    } catch (_) {}
    if (window.__nv_claimed_kernels__) window.__nv_claimed_kernels__.delete(_rcKernelId);
    _rcKernelId = null;
  }
  const kernels = await fetch("/lab/api/kernels", { credentials: "include" })
    .then(r => r.ok ? r.json() : []).catch(() => []);
  if (!Array.isArray(kernels) || !kernels.length) {
    throw new Error("No active kernels found. Open any notebook in JupyterLab to start one, then try again.");
  }
  const py = kernels.filter(k => k.name === "python3" || k.name === "python");
  if (!py.length) throw new Error("No python3 kernels found in JupyterLab.");
  if (!window.__nv_claimed_kernels__) window.__nv_claimed_kernels__ = new Set();
  const unclaimed = py.filter(k => !window.__nv_claimed_kernels__.has(k.id));
  const pool = unclaimed.length ? unclaimed : py;
  const kernel = pool.find(k => k.execution_state === "idle") || pool[0];
  _rcKernelId = kernel.id;
  window.__nv_claimed_kernels__.add(_rcKernelId);
  return _rcKernelId;
}
function _rcExecOnKernel(kernelId, code, { onStream, onLog, onResult, onDone }) {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${proto}//${location.host}/lab/api/kernels/${kernelId}/channels`;
  const ws = new WebSocket(wsUrl);
  const msgId = "runcell-" + Math.random().toString(36).slice(2, 10);
  ws.onopen = () => {
    ws.send(JSON.stringify({
      header: { msg_id: msgId, msg_type: "execute_request", username: "runcell",
                session: msgId, version: "5.2", date: new Date().toISOString() },
      parent_header: {}, metadata: {},
      content: { code, silent: false, store_history: false,
                 allow_stdin: false, stop_on_error: false },
    }));
  };
  ws.onmessage = ev => {
    let msg; try { msg = JSON.parse(ev.data); } catch (_) { return; }
    if (msg.parent_header.msg_id !== msgId) return;
    const { msg_type, content } = msg;
    if (msg_type === "stream") {
      if (content.name === "stderr") onLog(content.text);
      else onStream(content.text);
    } else if (msg_type === "execute_result" || msg_type === "display_data") {
      const txt = (content.data || {})["text/plain"] || "";
      if (txt) onResult(txt);
    } else if (msg_type === "error") {
      onLog(`${content.ename}: ${content.evalue}\n${(content.traceback || []).join("\n")}`);
    } else if (msg_type === "status" && content.execution_state === "idle") {
      ws.close(); onDone();
    }
  };
  ws.onerror = () => { onLog("[kernel WebSocket error]"); onDone(); };
  ws.onclose  = () => onDone();
  const tid = setTimeout(() => { ws.close(); onLog("[timeout: 60 s]"); onDone(); }, 60000);
  ws.addEventListener("close", () => clearTimeout(tid), { once: true });
  return ws;
}

export function mountRunCell(targetSel, opts) {
  const target = typeof targetSel === "string" ? document.querySelector(targetSel) : targetSel;
  if (!target) return null;
  const cellId = target.id || `cell-${Math.random().toString(36).slice(2, 8)}`;
  target.id = cellId;
  const code = opts.code || "";
  const pyCode = typeof opts.python === "string" ? opts.python : "";
  const hasPython = pyCode.length > 0;
  // Separate buffers so a student's edits in one language survive a toggle to
  // the other and back. The active buffer is whatever language is showing.
  let jsBuffer = code, pyBuffer = pyCode;
  let _rcLang = (hasPython && getPythonMode()) ? "python" : "js";
  const runLabel = () => (_rcLang === "python" ? "▶ Run Python" : "▶ Run");
  const langSub  = () => (_rcLang === "python"
    ? "python · editable · runs on a JupyterLab kernel"
    : "javascript · editable · re-run");
  const schemas = opts.schemas || {};
  const label = opts.label || "editable cell";
  const showSchemas = Object.keys(schemas).length > 0;

  // Outer card
  target.innerHTML = `
    <div style="background:#161616;border:1px solid #2a2a2a;border-radius:8px;overflow:hidden;">
      <div style="display:flex;align-items:center;gap:10px;padding:8px 12px;background:#1e1e1e;border-bottom:1px solid #2a2a2a;font-family:var(--mono);font-size:.78rem;">
        <span style="color:#aee23a;text-transform:uppercase;letter-spacing:.06em;">${label}</span>
        <span class="rc-lang" style="color:#6a6a6a;">${langSub()}</span>
        <span style="flex:1;"></span>
        <button class="rc-run" style="background:#76b900;color:#0a0a0a;border:none;border-radius:4px;padding:5px 14px;font-family:var(--mono);font-weight:700;font-size:.82rem;cursor:pointer;">${runLabel()}</button>
      </div>
      ${showSchemas ? `<div class="rc-schemas" style="border-bottom:1px solid #2a2a2a;"></div>` : ""}
      <div style="padding:0;">
        <textarea class="rc-code" spellcheck="false"
          style="width:100%;min-height:140px;background:#0d0d0d;color:#e6edf3;border:none;outline:none;padding:12px 14px;
                 font-family:ui-monospace,monospace;font-size:.84rem;line-height:1.55;resize:vertical;tab-size:2;"></textarea>
      </div>
      <div class="rc-out" style="background:#0a0a0a;border-top:1px solid #2a2a2a;padding:10px 14px;font-family:ui-monospace,monospace;font-size:.82rem;color:#a5a5a5;white-space:pre-wrap;min-height:48px;">empty until you Run</div>
    </div>`;
  const ta = target.querySelector(".rc-code");
  ta.value = (_rcLang === "python" ? pyBuffer : jsBuffer);
  // Auto-grow the textarea to fit its initial content height (fallback path).
  ta.style.height = "auto";
  ta.style.height = (Math.max(140, ta.scrollHeight + 6)) + "px";

  // CodeMirror upgrade: if the CDN script is loaded, convert the JS textarea
  // into a syntax-highlighted editor that auto-grows with content.
  let cm = null;
  function attachCM(textarea, mode, opts = {}) {
    if (typeof window.CodeMirror !== "function") return null;
    const editor = window.CodeMirror.fromTextArea(textarea, {
      mode,
      theme: "monokai",
      lineNumbers: true,
      indentUnit: 2,
      tabSize: 2,
      indentWithTabs: false,
      lineWrapping: true,                 // wrap long lines instead of per-cell horizontal scroll
      viewportMargin: Infinity,           // render full content; no inner scrollbar
      extraKeys: {
        "Ctrl-Enter": () => run(),
        "Cmd-Enter":  () => run(),
        "Tab":         e => e.execCommand("indentMore"),
        "Shift-Tab":   e => e.execCommand("indentLess"),
      },
      ...opts,
    });
    editor.setSize("100%", "auto");
    // Refresh once shortly after mount so layout settles correctly when the
    // cell is in a hidden tab on first render.
    setTimeout(() => editor.refresh(), 0);
    return editor;
  }
  cm = attachCM(ta, _rcLang === "python" ? "text/x-python" : "javascript");

  // Optional schemas section: one editable JSON textarea per schema name.
  // Also upgraded to CodeMirror with json mode when available.
  const schemaTAs = {};
  const schemaEditors = {};
  if (showSchemas) {
    const wrap = target.querySelector(".rc-schemas");
    for (const [name, value] of Object.entries(schemas)) {
      const block = document.createElement("div");
      block.style.cssText = "padding:8px 14px;border-bottom:1px solid #2a2a2a;background:#161616;";
      block.innerHTML = `
        <div style="display:flex;align-items:center;gap:10px;font-family:ui-monospace,monospace;font-size:.74rem;color:#aee23a;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;">
          <span>${name}</span>
          <span style="color:#6a6a6a;">json · editable · referenced as <code style="color:#aee23a;">${name}</code> inside the code below</span>
        </div>
        <textarea class="rc-schema" spellcheck="false"
          style="width:100%;min-height:80px;background:#0d0d0d;color:#e6edf3;border:1px solid #2a2a2a;border-radius:4px;outline:none;padding:8px 10px;
                 font-family:ui-monospace,monospace;font-size:.78rem;line-height:1.5;resize:vertical;"></textarea>`;
      wrap.appendChild(block);
      const sta = block.querySelector(".rc-schema");
      sta.value = JSON.stringify(value, null, 2);
      sta.style.height = "auto";
      sta.style.height = (Math.max(80, sta.scrollHeight + 6)) + "px";
      schemaTAs[name] = sta;
      schemaEditors[name] = attachCM(sta, { name: "javascript", json: true });
    }
    wrap.lastElementChild.style.borderBottom = "none";
  }

  const out = target.querySelector(".rc-out");
  // Reset out to a flex container that can hold structured blocks.
  out.innerHTML = "";
  out.style.padding = "0";
  out.style.cssText += "display:flex;flex-direction:column;gap:0;";
  function _emptyState(msg) {
    out.innerHTML = `<div style="padding:10px 14px;color:#6a6a6a;font-family:ui-monospace,monospace;font-size:.82rem;">${msg}</div>`;
  }
  _emptyState("empty until you Run");
  const btn = target.querySelector(".rc-run");

  async function run() {
    if (_runCellAborts.get(cellId)) { _runCellAborts.get(cellId).abort(); }
    const ac = new AbortController();
    _runCellAborts.set(cellId, ac);
    btn.textContent = "⏹ Stop";
    btn.onclick = () => ac.abort();
    out.innerHTML = "";

    // Parse schemas first; if any fails, show the parse error and bail.
    const schemaVars = {};
    for (const [name, sta] of Object.entries(schemaTAs)) {
      // Read from CodeMirror if present; otherwise from the textarea.
      const text = schemaEditors[name] ? schemaEditors[name].getValue() : sta.value;
      try { schemaVars[name] = JSON.parse(text); }
      catch (e) {
        const err = document.createElement("div");
        err.style.cssText = "padding:10px 14px;color:#ef4444;font-family:ui-monospace,monospace;font-size:.82rem;white-space:pre-wrap;";
        err.textContent = `schema parse error in ${name}: ${e.message}\n\nFix the JSON in the schema block above, then Run again.`;
        out.appendChild(err);
        btn.textContent = runLabel(); btn.onclick = run;
        return;
      }
    }

    // ── Structured log API ────────────────────────────────────────────────
    // log(...args)            : concatenated text line
    // log.h(title)            : section header
    // log.json(label?, obj)   : pretty-printed JSON, syntax-highlighted
    // log.details(summary,    : collapsible block; body can be string or object
    //             body)
    // log.kv({k1:v1, k2:v2})  : inline key→value row (good for stats)
    // log.html(htmlString)    : raw HTML (use sparingly)
    // log.clear()             : reset the output pane
    //
    // Strings are appended as-is; objects auto-render as syntax-highlighted JSON.
    let outputCount = 0;
    function _appendText(text, color = "#e6edf3") {
      const div = document.createElement("div");
      div.style.cssText = `padding:6px 14px;font-family:ui-monospace,monospace;font-size:.84rem;line-height:1.55;color:${color};white-space:pre-wrap;word-break:break-word;`;
      div.textContent = text;
      out.appendChild(div);
      outputCount++;
    }
    function _appendJson(obj, label = null) {
      if (label) _appendHeading(label);
      const pre = document.createElement("pre");
      pre.style.cssText = "margin:4px 14px 8px;padding:10px 12px;background:#0a0a0a;border:1px solid #2a2a2a;border-radius:4px;font-size:.78rem;line-height:1.5;overflow-x:auto;";
      const code = document.createElement("code");
      code.className = "language-json";
      code.textContent = JSON.stringify(obj, null, 2);
      pre.appendChild(code);
      out.appendChild(pre);
      if (typeof window.hljs !== "undefined") {
        try { window.hljs.highlightElement(code); } catch (_) {}
      }
      outputCount++;
    }
    function _appendHeading(title) {
      const div = document.createElement("div");
      div.style.cssText = "padding:10px 14px 2px;font-family:ui-monospace,monospace;font-size:.72rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#aee23a;";
      div.textContent = title;
      out.appendChild(div);
      outputCount++;
    }
    function _appendDetails(summary, body) {
      const det = document.createElement("details");
      det.style.cssText = "margin:4px 14px 6px;border:1px solid #2a2a2a;border-radius:4px;background:#0a0a0a;";
      const sum = document.createElement("summary");
      sum.style.cssText = "padding:6px 10px;cursor:pointer;font-family:ui-monospace,monospace;font-size:.78rem;color:#a5a5a5;";
      sum.textContent = summary;
      det.appendChild(sum);
      const inner = document.createElement("div");
      inner.style.cssText = "padding:8px 12px;font-family:ui-monospace,monospace;font-size:.78rem;line-height:1.5;color:#e6edf3;white-space:pre-wrap;word-break:break-word;";
      if (typeof body === "object" && body !== null) {
        const code = document.createElement("code");
        code.className = "language-json";
        code.textContent = JSON.stringify(body, null, 2);
        const pre = document.createElement("pre");
        pre.style.cssText = "margin:0;background:transparent;border:0;padding:0;overflow-x:auto;";
        pre.appendChild(code);
        inner.appendChild(pre);
        det.appendChild(inner);
        det.open = false;
        out.appendChild(det);
        if (typeof window.hljs !== "undefined") {
          try { window.hljs.highlightElement(code); } catch (_) {}
        }
      } else {
        inner.textContent = String(body);
        det.appendChild(inner);
        out.appendChild(det);
      }
      outputCount++;
    }
    function _appendKv(obj) {
      const div = document.createElement("div");
      div.style.cssText = "padding:6px 14px;display:flex;flex-wrap:wrap;gap:14px;font-family:ui-monospace,monospace;font-size:.78rem;";
      for (const [k, v] of Object.entries(obj)) {
        const pair = document.createElement("span");
        pair.innerHTML = `<span style="color:#6a6a6a;">${k}:</span> <span style="color:#aee23a;">${typeof v === "object" ? JSON.stringify(v) : String(v)}</span>`;
        div.appendChild(pair);
      }
      out.appendChild(div);
      outputCount++;
    }
    function _appendHtml(html) {
      const div = document.createElement("div");
      div.style.cssText = "padding:6px 14px;font-family:inherit;";
      div.innerHTML = html;
      out.appendChild(div);
      outputCount++;
    }
    const log = (...args) => {
      // If a single object is passed, render it as JSON. Otherwise concat to text.
      if (args.length === 1 && typeof args[0] === "object" && args[0] !== null) {
        _appendJson(args[0]);
      } else {
        _appendText(args.map(v => typeof v === "object" && v !== null ? JSON.stringify(v) : String(v)).join(" "));
      }
    };
    log.h = (title) => _appendHeading(title);
    log.json = (a, b) => (b === undefined ? _appendJson(a) : _appendJson(b, a));
    log.details = (summary, body) => _appendDetails(summary, body);
    log.kv = (obj) => _appendKv(obj);
    log.html = (htmlString) => _appendHtml(htmlString);
    const clear = () => { out.innerHTML = ""; outputCount = 0; };
    log.clear = clear;

    // Python mode: run the cell's Python variant on a JupyterLab kernel,
    // streaming into the same results buffer. Only run-cells given an
    // opts.python ever set _rcLang to "python" (see the toggle handler below).
    if (_rcLang === "python") {
      const codeText = cm ? cm.getValue() : ta.value;
      pyBuffer = codeText;  // preserve the student's edits across re-runs/toggles
      let _ws = null;
      ac.signal.addEventListener("abort", () => { try { _ws && _ws.close(); } catch (_) {} }, { once: true });
      try {
        const kernelId = await _rcFindKernel();
        await new Promise((resolve) => {
          _ws = _rcExecOnKernel(kernelId, codeText, {
            onStream: (t) => _appendText(t),
            onResult: (t) => _appendText(t, "#aee23a"),
            onLog: (t) => {
              const err = document.createElement("div");
              err.style.cssText = "padding:8px 14px;color:#ef4444;font-family:ui-monospace,monospace;font-size:.82rem;white-space:pre-wrap;word-break:break-word;";
              err.textContent = t; out.appendChild(err); outputCount++;
            },
            onDone: resolve,
          });
        });
        if (!ac.signal.aborted && outputCount === 0) _emptyState("(completed; no output)");
      } catch (e) {
        const err = document.createElement("div");
        err.style.cssText = "padding:10px 14px;color:#ef4444;font-family:ui-monospace,monospace;font-size:.82rem;white-space:pre-wrap;";
        err.textContent = `Error: ${e.message}`;
        out.appendChild(err);
      } finally {
        _runCellAborts.delete(cellId);
        btn.textContent = runLabel();
        btn.onclick = run;
      }
      return;
    }

    if (cm) _clearCMErrs(cm);
    try {
      const argNames = ["chat", "chatStream", "webSearch", "instantAnswer", "formatSearchResults", "log", "clear", "MODEL", "REASONING_MODEL", "AbortSignal", ...Object.keys(schemaVars)];
      const argVals  = [chat,    chatStream,   webSearch,   instantAnswer,   formatSearchResults,   log,   clear,   null,    REASONING_MODEL,  ac.signal,    ...Object.values(schemaVars)];
      // Read from CodeMirror if present; otherwise from the textarea.
      const codeText = cm ? cm.getValue() : ta.value;
      jsBuffer = codeText;  // preserve the student's edits across re-runs/toggles
      const fn = new Function(...argNames,
        `"use strict"; return (async () => {\n${codeText}\n})();`);
      const result = await fn(...argVals);
      if (!ac.signal.aborted && outputCount === 0) {
        if (result === undefined) {
          _emptyState("(completed; no log output and no returned value)");
        } else if (typeof result === "object" && result !== null) {
          _appendJson(result, "returned value");
        } else {
          _appendText(String(result));
        }
      }
    } catch (e) {
      if (!ac.signal.aborted) {
        const err = document.createElement("div");
        err.style.cssText = "padding:10px 14px;color:#ef4444;font-family:ui-monospace,monospace;font-size:.82rem;white-space:pre-wrap;";
        err.textContent = "✗ " + (e.name || "Error") + ": " + e.message;
        out.appendChild(err);
        // Mark the failing line in the editor and show a Debug-info panel with a
        // code snippet + filtered stack, mirroring the canvas-cell behaviour.
        const _ep = _parseErrLine(e);
        const _rcCode = cm ? cm.getValue() : ta.value;
        if (_ep !== null && cm) {
          _clearCMErrs(cm); _markCMErr(cm, _ep);
          setTimeout(() => { try { cm.refresh(); cm.scrollIntoView({ line: _ep.cmLine, ch: 0 }, 100); } catch (_) {} }, 60);
        }
        const dbg = _buildDebugDet(e, _rcCode, _ep);
        dbg.style.cssText = "margin:0 14px 8px;border-radius:0 0 5px 5px;";
        out.appendChild(dbg);
      }
    } finally {
      _runCellAborts.delete(cellId);
      btn.textContent = runLabel();
      btn.onclick = run;
    }
  }
  btn.onclick = run;

  // Live language swap when the page-wide Python-mode toggle flips. Only
  // run-cells that were given an opts.python participate; others stay JS.
  if (hasPython) {
    document.addEventListener("pythonModeChange", (e) => {
      const wantPy = !!(e.detail && e.detail.on);
      const nextLang = wantPy ? "python" : "js";
      if (nextLang === _rcLang) return;
      // Save the current editor contents into the active buffer, then load
      // the other language's buffer and switch the editor mode + chrome.
      const cur = cm ? cm.getValue() : ta.value;
      if (_rcLang === "python") pyBuffer = cur; else jsBuffer = cur;
      _rcLang = nextLang;
      const nextText = _rcLang === "python" ? pyBuffer : jsBuffer;
      if (cm) {
        cm.setOption("mode", _rcLang === "python" ? "text/x-python" : "javascript");
        cm.setValue(nextText);
      } else {
        ta.value = nextText;
      }
      const sub = target.querySelector(".rc-lang");
      if (sub) sub.textContent = langSub();
      btn.textContent = runLabel();
    });
  }

  return { run, ta, out, schemaTAs };
}

// ── Mode indicator. Call on page load to update key-pill ────────────────────
export async function updateKeyPill(pill) {
  if (!pill) return;
  const cfg = await getConfig();
  if (cfg.mode === "proxy") {
    pill.textContent = "Lab proxy ✓";
    pill.classList.add("set");
    pill.title = "Model calls route through the hosted build CORS worker with your nvapi- key.";
  } else if (hasKey()) {
    pill.textContent = "Key set ✓";
    pill.classList.add("set");
  } else {
    pill.textContent = "No API key";
    pill.classList.remove("set");
  }
}

// ── OpenClaw indicator. Call on page load and after probe success ────────────
export function updateClawPill(pill) {
  if (!pill) return;
  const url   = localStorage.getItem("nemoclaw_clawurl")   || "";
  const token = localStorage.getItem("nemoclaw_clawtoken") || "";
  if (url && token) {
    const host = url.replace(/^https?:\/\//, "").replace(/\/.*$/, "");
    pill.textContent = "OpenClaw ✓";
    pill.classList.add("set");
    pill.title = host;
  } else {
    pill.textContent = "No OpenClaw";
    pill.classList.remove("set");
  }
}

// ── Inline API-key setup panel ───────────────────────────────────────────────
export function mountKeyPanel(container, opts = {}) {
  /* @doc <code>helpers.mountKeyPanel(el)</code> :: Renders an inline API-key setup panel using the existing <code>.key-panel</code> CSS classes. When a key is saved it shows a compact "✓ saved" row with a Change button. On save, strips invisible Unicode, verifies live, then updates the topbar <code>#key-status</code> pill. */
  const el = typeof container === "string" ? document.querySelector(container) : container;
  if (!el) return null;
  const _clean = raw => raw.trim().replace(/[^\x20-\x7E]/g, "");
  function _draw() {
    if (hasKey()) {
      el.innerHTML = `<div class="key-panel" style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;padding:16px 24px">
        <span style="color:var(--gs,#aee23a);font-family:var(--mono,monospace);font-size:.88rem">&#10003; API key saved for this session</span>
        <button class="btn" style="margin:0;padding:7px 16px;font-size:.82rem">Change</button>
      </div>`;
      el.querySelector(".btn").onclick = () => {
        localStorage.removeItem("nvapi");
        const pill = document.getElementById("key-status");
        if (pill) updateKeyPill(pill);
        if (opts.onClear) opts.onClear();
        _draw();
      };
    } else {
      el.innerHTML = `<div class="key-panel">
        <label>NVIDIA API key (starts with <code>nvapi-</code>)</label>
        <input type="password" placeholder="nvapi-&hellip;" autocomplete="off" spellcheck="false"/>
        <button class="btn">Save &amp; verify</button>
        <div class="status"></div>
        <p style="margin:.8em 0 0;font-size:.8rem;color:var(--tf,#8a8a8a)">
          No key yet? <a href="https://build.nvidia.com" target="_blank" rel="noopener">Sign up at build.nvidia.com &rarr;</a>
          Free-tier models cover every exercise.
        </p>
      </div>`;
      const input = el.querySelector("input");
      const status = el.querySelector(".status");
      const btn = el.querySelector(".btn");
      async function save() {
        const key = _clean(input.value);
        if (!key.startsWith("nvapi-")) {
          status.className = "status err"; status.textContent = "Key should start with nvapi-"; return;
        }
        status.className = "status"; status.textContent = "Verifying…";
        try {
          setKey(key);
          const r = await chat({ messages: [{ role: "user", content: "Reply with the single word: ready" }], max_tokens: 10 });
          const reply = r.choices?.[0]?.message?.content?.trim() || "(empty)";
          status.className = "status ok"; status.textContent = `✓ Connected. Model replied: "${reply}"`;
          const pill = document.getElementById("key-status");
          if (pill) updateKeyPill(pill);
          if (opts.onSave) opts.onSave(key);
          setTimeout(_draw, 1400);
        } catch (e) {
          localStorage.removeItem("nvapi");
          status.className = "status err"; status.textContent = `Connection failed: ${e.message}`;
        }
      }
      btn.addEventListener("click", save);
      input.addEventListener("keydown", ev => { if (ev.key === "Enter") save(); });
    }
  }
  _draw();
  return { update: _draw };
}

// ── ClawGateway widget ───────────────────────────────────────────────────────
// Live WebSocket gateway client. Reads URL + token from localStorage (set by
// a sibling mountClawProbe with syncCanvas:true). Connects directly to the
// gateway (wss://rawUrl/cli/gateway). The browser's CF_Authorization cookie
// handles Cloudflare Access for *.brevlab.com launchables; no proxy hop needed.
// Protocol: challenge → connect(type:req, auth:{token}, scopes:[...admin]) →
// subscribe → method calls.
export function mountClawGateway(targetSel, opts = {}) {
  const target = typeof targetSel === "string" ? document.querySelector(targetSel) : targetSel;
  if (!target) return;

  const label      = opts.label      || "OpenClaw Gateway";
  const intro      = opts.intro      !== undefined ? opts.intro : "";
  const actions    = opts.actions    || [];
  const sessionKey = opts.sessionKey || "agent:main:main";
  const autoConnect = !!opts.autoConnect;

  // Credentials from localStorage (written by mountClawProbe syncCanvas:true).
  // Use the raw URL key so the WS URL is built against the actual launchable,
  // not the CF CORS proxy that _CLAWPROBE_KEY_URL stores.
  function _creds() {
    return {
      rawUrl: localStorage.getItem(_CLAWPROBE_KEY_RAW_URL) ||
              localStorage.getItem(_CLAWPROBE_KEY_URL)     || "",
      token:  localStorage.getItem(_CLAWPROBE_KEY_TOKEN)   || "",
    };
  }

  // Build WS gateway URL directly with no proxy; browser sends CF cookie for CF Access
  function _wsUrl(rawUrl) {
    if (!rawUrl) return null;
    const base = rawUrl.replace(/\/+$/, "").replace(/^https/, "wss").replace(/^http(?!s)/, "ws");
    return base + "/cli/gateway";
  }

  // ── WS state ────────────────────────────────────────────────────────────────
  let _ws      = null;
  let _pending = {};    // id → {resolve, reject, timeout}
  let _chatCb  = null;  // called with each agent/chat event during a chat.send

  function _send(obj) {
    if (_ws && _ws.readyState === WebSocket.OPEN) _ws.send(JSON.stringify(obj));
  }

  function _call(method, params) {
    return new Promise((resolve, reject) => {
      const id = Math.random().toString(36).slice(2) + Date.now().toString(36);
      const tmo = setTimeout(() => {
        delete _pending[id];
        reject(new Error(`${method} timed out`));
      }, 20000);
      _pending[id] = { resolve, reject, tmo };
      _send({ type: "req", id, method, params: params || {} });
    });
  }

  function _connectWs(wsUrl, token) {
    return new Promise((resolve, reject) => {
      if (_ws) { try { _ws.close(); } catch (_) {} }
      _ws = new WebSocket(wsUrl);
      let _connId = null;

      _ws.onopen = () => {};

      _ws.onmessage = ev => {
        let d;
        try { d = JSON.parse(ev.data); } catch (_) { return; }
        const evt = d.event || "";
        const mid = d.id    || "";
        const typ = d.type  || "";

        if (evt === "connect.challenge") {
          _connId = Math.random().toString(36).slice(2) + Date.now().toString(36);
          // Resolve the outer promise on connect response
          _pending[_connId] = {
            resolve: r => {
              clearTimeout(_pending[_connId]?.tmo);
              delete _pending[_connId];
              const scopes  = r?.payload?.auth?.scopes  || [];
              const version = r?.payload?.server?.version || "?";
              resolve({ scopes, version });
              // auto-subscribe to the default session
              _call("sessions.messages.subscribe", { key: sessionKey }).catch(() => {});
            },
            reject: e => {
              clearTimeout(_pending[_connId]?.tmo);
              delete _pending[_connId];
              reject(e);
            },
            tmo: setTimeout(() => reject(new Error("connect timeout")), 15000),
          };
          _ws.send(JSON.stringify({
            type: "req", id: _connId, method: "connect",
            params: {
              minProtocol: 4, maxProtocol: 4,
              client: { id: "openclaw-control-ui", version: "0.1.0", platform: "browser", mode: "webchat" },
              caps: ["tool-events"], role: "operator",
              scopes: ["operator.read", "operator.write", "operator.admin"],
              auth: { token },
            },
          }));
          return;
        }

        // Resolve pending calls
        if (typ === "res" && mid && _pending[mid]) {
          const p = _pending[mid];
          clearTimeout(p.tmo);
          delete _pending[mid];
          if (d.ok) p.resolve(d); else p.reject(new Error(d.error?.message || "gateway error"));
          return;
        }

        // Route agent/chat events to active chat handler
        if (typ === "event" && _chatCb && (evt === "chat" || evt === "agent")) {
          _chatCb(d);
        }
      };

      _ws.onerror = () => reject(new Error("WebSocket error. Check that the URL is correct and the launchable is running."));
      _ws.onclose = () => {
        _setStatus("disconnected");
        _setActions(false);
        Object.values(_pending).forEach(p => { clearTimeout(p.tmo); p.reject(new Error("connection closed")); });
        _pending = {};
      };
    });
  }

  // ── DOM ─────────────────────────────────────────────────────────────────────
  target.innerHTML = `
<div class="claw-probe gw-panel">
  ${intro ? `<div class="gw-intro">${intro}</div>` : ""}
  <div class="claw-label">${label}</div>
  <div class="gw-head">
    <span class="gw-status gw-disc">● disconnected</span>
    <button type="button" class="claw-btn alt gw-connect-btn">Connect</button>
  </div>
  <div class="gw-actions" hidden>
    ${actions.map((a, i) =>
      `<button type="button" class="claw-btn${a.primary ? "" : " alt"} gw-act" data-i="${i}">${a.label}</button>`
    ).join("")}
  </div>
  <div class="gw-out" hidden></div>
</div>`;

  const statusEl  = target.querySelector(".gw-status");
  const connectBtn = target.querySelector(".gw-connect-btn");
  const actionsEl  = target.querySelector(".gw-actions");
  const outEl      = target.querySelector(".gw-out");

  function _setStatus(state, detail) {
    const map = {
      connecting:   ["● connecting…",   "gw-conn"],
      connected:    ["● connected",     "gw-live"],
      disconnected: ["● disconnected",  "gw-disc"],
      error:        ["● error",         "gw-err"],
    };
    const [txt, cls] = map[state] || map.disconnected;
    statusEl.textContent = detail ? `${txt} · ${detail}` : txt;
    statusEl.className   = `gw-status ${cls}`;
  }

  function _setActions(en) {
    actionsEl.hidden = !en;
  }

  function _showOut(html) {
    outEl.hidden  = false;
    outEl.innerHTML = html;
  }

  function _showPre(text) {
    _showOut(`<pre class="gw-pre">${text.replace(/</g,"&lt;")}</pre>`);
  }

  // ── Connect ──────────────────────────────────────────────────────────────────
  connectBtn.addEventListener("click", async () => {
    const { rawUrl, token } = _creds();
    if (!rawUrl || !token) {
      _showOut(`<span class="gw-err-txt">No URL or token yet. Fill in the OpenClaw probe above and click an action first.</span>`);
      return;
    }
    const wsUrl = _wsUrl(rawUrl);
    _setStatus("connecting");
    connectBtn.disabled = true;
    outEl.hidden = true;
    try {
      const { scopes, version } = await _connectWs(wsUrl, token);
      _setStatus("connected", `v${version} · ${scopes.length} scopes`);
      _setActions(true);
      connectBtn.textContent = "Reconnect";
    } catch (e) {
      _setStatus("error", e.message.slice(0, 80));
      _showOut(`<span class="gw-err-txt">${e.message}</span>`);
    }
    connectBtn.disabled = false;
  });

  // ── Action buttons ────────────────────────────────────────────────────────
  actionsEl.querySelectorAll(".gw-act").forEach(btn => {
    const action = actions[parseInt(btn.dataset.i)];
    if (!action) return;

    btn.addEventListener("click", async () => {
      btn.disabled = true;
      outEl.hidden = true;

      try {
        if (action.chat) {
          // Streaming chat
          const ikey = Math.random().toString(36).slice(2) + Date.now().toString(36);
          let fullText = "";
          outEl.hidden  = false;
          outEl.innerHTML = `<div class="gw-chat-out"></div>`;
          const chatDiv = outEl.querySelector(".gw-chat-out");

          await new Promise((resolve, reject) => {
            _chatCb = d => {
              const evt = d.event || "";
              const pl  = d.payload || {};
              if (evt === "chat" && pl.state === "delta") {
                fullText = pl.message?.content?.[0]?.text || (fullText + (pl.deltaText || ""));
                chatDiv.textContent = fullText;
              } else if (evt === "agent" && pl.stream === "lifecycle" && pl.data?.phase === "end") {
                _chatCb = null;
                resolve();
              } else if (evt === "chat" && pl.state === "final") {
                fullText = pl.message?.content?.[0]?.text || fullText;
                chatDiv.textContent = fullText;
              }
            };
            const msg = typeof action.message === "function" ? action.message() : (action.message || "Hello");
            _call("chat.send", { sessionKey, idempotencyKey: ikey, message: msg })
              .catch(e => { _chatCb = null; reject(e); });
            // Safety timeout
            setTimeout(() => { _chatCb = null; resolve(); }, 60000);
          });
        } else {
          // Standard method call
          const params = typeof action.params === "function" ? action.params() : (action.params || {});
          const res = await _call(action.method, params);
          // Pretty-print selected payload shapes
          const pl = res.payload;
          if (action.format === "models" && pl?.models) {
            _showOut(`<table class="gw-table"><thead><tr><th>id</th><th>provider</th><th>ctx</th></tr></thead><tbody>${
              pl.models.map(m => `<tr><td>${m.id}</td><td>${m.provider}</td><td>${m.contextWindow||""}</td></tr>`).join("")
            }</tbody></table>`);
          } else if (action.format === "crons" && pl) {
            const jobs = pl.jobs || [];
            if (!jobs.length) {
              _showOut(`<span class="gw-muted">No cron jobs installed.</span>`);
            } else {
              _showOut(`<table class="gw-table"><thead><tr><th>id</th><th>schedule</th><th>prompt</th></tr></thead><tbody>${
                jobs.map(j => `<tr><td>${j.id}</td><td>${j.schedule}</td><td>${(j.prompt||"").slice(0,60)}</td></tr>`).join("")
              }</tbody></table>`);
            }
          } else {
            _showPre(JSON.stringify(pl, null, 2));
          }
        }
      } catch (e) {
        _showOut(`<span class="gw-err-txt">✗ ${e.message}</span>`);
      }
      btn.disabled = false;
    });
  });

  if (autoConnect) connectBtn.click();

  return { call: _call };
}

// ── ClawProbe widget ─────────────────────────────────────────────────────────
// A paste-your-URL surface for the live OpenClaw/OpenShell exercises. The
// student types a base URL + bearer token, the widget hits the configured
// actions against it, prints back the response. Persists URL+token in
// localStorage (persists in this browser across tabs/reloads, never leaves it).
//
//   mountClawProbe("#probe", {
//     defaultUrl:   "/lab/openclaw",        // lab proxy works without any pasting
//     defaultToken: "dli-openclaw-token",
//     actions: [
//       { label: "Probe /healthz",  path: "/healthz",                method: "GET"  },
//       { label: "List models",     path: "/v1/models",              method: "GET"  },
//       { label: "Chat: hello",     path: "/v1/chat/completions",    method: "POST",
//         body: () => ({ model: "default", max_tokens: 60, messages: [
//           {role:"user", content:"In one sentence: who runs you?"}
//         ]}) },
//     ],
//   });
//
// The widget never assumes a particular service shape: every action is a free
// `fetch` call shaped by the caller. The widget just handles the boilerplate
// (URL+token persistence, request execution, JSON-pretty-print output, timing,
// error reporting) so individual pages can describe their exercises as one
// short array. Pages 3a/3b/3c/4a all mount this with different `actions`.
const _CLAWPROBE_KEY_URL     = "nemoclaw_clawurl";
const _CLAWPROBE_KEY_RAW_URL = "nemoclaw_clawrawurl"; // raw (pre-proxy) URL for WS
const _CLAWPROBE_KEY_TOKEN   = "nemoclaw_clawtoken";
const _CLAWPROBE_KEY_CFJWT   = "nemoclaw_clawcfjwt";

export function mountClawProbe(targetSel, opts = {}) {
  const target = typeof targetSel === "string" ? document.querySelector(targetSel) : targetSel;
  if (!target) return;

  const defaultUrl   = (opts.defaultUrl   || "/lab/openclaw").replace(/\/+$/, "");
  // Respect an explicit empty token. The llm_client probe passes defaultToken:"" because
  // the lab proxy needs no bearer; a bare `|| default` would turn "" into the openclaw
  // token, which llm_client forwards upstream and the model backend rejects (400).
  const defaultToken = (opts.defaultToken !== undefined) ? opts.defaultToken : "dli-openclaw-token";
  // The bearer-field placeholder follows the default: a no-bearer probe (llm_client,
  // defaultToken "") shows "(none needed in the lab)" instead of the misleading openclaw
  // token. Callers can override with opts.tokenPlaceholder.
  const tokenPlaceholder = (opts.tokenPlaceholder !== undefined)
    ? opts.tokenPlaceholder
    : (defaultToken || "(none needed in your launchable)");
  const actions      = opts.actions || [];
  const label        = opts.label || "Live OpenClaw probe";
  const intro        = opts.intro !== undefined ? opts.intro : "Paste the base URL of a running OpenClaw service. Your launchable's proxy is the default; to reach a remote launchable, paste its URL (https://nemoclaw-<id>.brevlab.com) instead.";

  // Scope saved url+token to the service (keyed by base URL) so probes for different
  // services do not share auth. Probes with the same base URL (e.g. the openclaw probes
  // across 3a/3b/3c) still share; the no-auth llm_client probe and sandbox-admin keep
  // their own, so the openclaw token never bleeds into llm_client.
  const _grp     = defaultUrl.replace(/[^a-z0-9]+/gi, "_").replace(/^_+|_+$/g, "") || "default";
  // The openclaw probes keep the legacy key so they also share url+token with the
  // mountCanvasFlow cells on 3a/3b/3c (those cells read the legacy key directly). Other
  // services (llm_client, sandbox-admin) get their own key, so the openclaw token never
  // bleeds into the no-auth llm_client probe.
  const _shared  = (_grp === "lab_openclaw");
  const keyUrl   = _shared ? _CLAWPROBE_KEY_URL   : (_CLAWPROBE_KEY_URL   + ":" + _grp);
  const keyToken = _shared ? _CLAWPROBE_KEY_TOKEN : (_CLAWPROBE_KEY_TOKEN + ":" + _grp);
  // Strip any stale proxy prefix so the input always shows the raw target URL.
  // Guards against earlier code that incorrectly wrote the effective URL into the probe's
  // own storage slot, because on reload those values would get double-proxied.
  const _storedUrl = localStorage.getItem(keyUrl);
  const _stripPb   = (opts.proxyBase || "").replace(/\/+$/, "");
  const _strippedUrl = (_stripPb && (opts.proxyMode || "origin") === "prefix" &&
                        _storedUrl && _storedUrl.startsWith(_stripPb + "/https/"))
    ? "https://" + _storedUrl.slice(_stripPb.length + "/https/".length)
    : _storedUrl;
  if (_strippedUrl !== _storedUrl && _strippedUrl)
    localStorage.setItem(keyUrl, _strippedUrl); // heal stale storage
  const savedUrl   = _strippedUrl || defaultUrl;
  let savedToken = localStorage.getItem(keyToken) || defaultToken;
  // A no-bearer probe must never inherit a stale openclaw token a prior build left in
  // storage (before per-service key scoping); blank it so llm_client sends no bearer.
  if (defaultToken === "" && savedToken === "dli-openclaw-token") savedToken = "";
  const keyCfJwt  = _CLAWPROBE_KEY_CFJWT + ":" + _grp;
  const savedCfJwt = opts.cfAccess ? (localStorage.getItem(keyCfJwt) || "") : "";

  // Label helper: if fieldHelp has content for this key, render a toggle button;
  // otherwise render a plain label. Both match the .claw-lf sizing exactly.
  const _lbl = (key, text) => opts.fieldHelp?.[key]
    ? `<button type="button" class="claw-lf claw-help-trigger" data-field="${key}" aria-expanded="false">${text}</button>`
    : `<label class="claw-lf">${text}</label>`;
  // Help panel rendered immediately after its row (hidden by default).
  const _hlp = (key) => {
    const h = opts.fieldHelp?.[key];
    return h ? `<div class="claw-help-panel" data-field="${key}" hidden role="region">${h}</div>` : "";
  };

  target.innerHTML = `
    <div class="claw-probe">
      <div class="claw-head">
        <div class="claw-label">${escHtml(label)}</div>
        ${intro ? `<div class="claw-intro">${escHtml(intro)}</div>` : ""}
      </div>
      <div class="claw-row">
        ${_lbl("url", "Base URL")}
        <input class="claw-input claw-url" type="text" spellcheck="false" autocapitalize="off"
               placeholder="https://your-tunnel.example.com" value="${_escAttr(savedUrl)}"/>
      </div>
      ${_hlp("url")}
      <div class="claw-row">
        ${_lbl("token", "Bearer token")}
        <input class="claw-input claw-token" type="password" spellcheck="false" autocapitalize="off"
               placeholder="${_escAttr(tokenPlaceholder)}" value="${_escAttr(savedToken)}"/>
        <button type="button" class="claw-btn alt claw-eye" title="Show token" aria-label="Show or hide token">👁</button>
      </div>
      ${_hlp("token")}
      ${opts.cfAccess ? `
      <div class="claw-row">
        ${_lbl("cfJwt", "CF Access JWT")}
        <input class="claw-input claw-cfjwt" type="password" spellcheck="false" autocapitalize="off"
               placeholder="paste CF_Authorization value from DevTools → Application → Cookies"
               value="${_escAttr(savedCfJwt)}"/>
        <button type="button" class="claw-btn alt claw-eye claw-eye-jwt" title="Show JWT" aria-label="Show or hide CF Access JWT">👁</button>
      </div>
      ${_hlp("cfJwt")}` : ""}
      <div class="claw-actions"></div>
      <pre class="claw-out" aria-live="polite"></pre>
    </div>
  `;

  // Inject the widget CSS once (idempotent, keyed off the marker class).
  if (!document.head.querySelector('style[data-claw-probe="1"]')) {
    const s = document.createElement("style");
    s.dataset.clawProbe = "1";
    s.textContent = `
      .claw-probe{border:1px solid var(--bd,#2a2a2a);border-radius:8px;background:var(--e1,#161616);padding:14px 16px;margin:1em 0}
      .claw-head{margin-bottom:.8em}
      .claw-label{font-weight:700;font-size:.95rem;color:var(--gs,#aee23a);margin-bottom:.2em}
      .claw-intro{font-size:.86rem;color:var(--td,#b0b0b0);line-height:1.5}
      .claw-row{display:flex;align-items:center;gap:8px;margin:.4em 0}
      .claw-lf{font-family:var(--mono,monospace);font-size:.75rem;color:var(--tf,#8a8a8a);width:96px;flex:0 0 96px;text-transform:uppercase;letter-spacing:.04em}
      .claw-input{flex:1;background:var(--e2,#1e1e1e);border:1px solid var(--bd,#2a2a2a);border-radius:5px;padding:7px 10px;color:var(--tx,#f2f2f2);font-family:var(--mono,monospace);font-size:.82rem;min-width:0}
      .claw-input:focus{outline:none;border-color:var(--g,#76b900)}
      .claw-actions{display:flex;flex-wrap:wrap;gap:6px;margin:.7em 0 .5em}
      .claw-btn{background:var(--g,#76b900);color:#000;border:0;border-radius:5px;padding:6px 14px;font-size:.82rem;font-weight:700;cursor:pointer;font-family:inherit}
      .claw-btn:hover{background:var(--gs,#aee23a)}
      .claw-btn:disabled{opacity:.5;cursor:wait}
      .claw-btn.alt{background:var(--e2,#1e1e1e);color:var(--gs,#aee23a);border:1px solid var(--bd,#2a2a2a)}
      .claw-btn.alt:hover{border-color:var(--g,#76b900)}
      .claw-eye{flex:0 0 auto;padding:5px 9px;font-size:.88rem;line-height:1}
      .claw-help-trigger{background:none;border:none;padding:0;cursor:pointer;text-align:left;width:96px;flex:0 0 96px;font-family:var(--mono,monospace);font-size:.75rem;color:var(--tf,#8a8a8a);text-transform:uppercase;letter-spacing:.04em;text-decoration:underline dotted;text-underline-offset:2px;line-height:inherit}
      .claw-help-trigger:hover,.claw-help-trigger[aria-expanded="true"]{color:var(--gs,#aee23a);text-decoration-style:solid}
      .claw-help-panel{padding:8px 12px 8px 104px;font-size:.82rem;line-height:1.65;color:var(--td,#b0b0b0);border-left:2px solid var(--bd,#2a2a2a);margin:.1em 0 .5em}
      .claw-help-panel p{margin:.3em 0}.claw-help-panel p:first-child{margin-top:0}.claw-help-panel p:last-child{margin-bottom:0}
      .claw-help-panel code{font-size:.88em;background:#0d0d0d;padding:1px 5px;border-radius:3px;color:var(--gs,#aee23a)}
      .claw-help-panel strong{color:var(--tx,#f2f2f2)}
      .claw-help-panel a{color:var(--gs,#aee23a)}
      .claw-out{background:#0d0d0d;border:1px solid var(--bd,#2a2a2a);border-radius:5px;padding:10px 12px;font-family:var(--mono,monospace);font-size:.78rem;line-height:1.5;color:var(--tx,#f2f2f2);min-height:60px;max-height:340px;overflow:auto;white-space:pre-wrap;word-break:break-word;margin:0}
      .claw-out.ok{border-color:var(--gd,#4a7a00)}
      .claw-out.err{border-color:#a04040;color:#ffb0b0}
      .claw-html-frame{width:100%;height:340px;border:1px solid var(--bd,#2a2a2a);border-radius:5px;margin-top:.5em;background:#fff;display:block}
    `;
    document.head.appendChild(s);
  }

  const urlInp   = target.querySelector(".claw-url");
  const tokenInp = target.querySelector(".claw-token");
  const eyeBtn   = target.querySelector(".claw-eye");
  if (eyeBtn) {
    eyeBtn.addEventListener("click", () => {
      const showing = tokenInp.type !== "password";
      tokenInp.type = showing ? "password" : "text";
      eyeBtn.title  = showing ? "Show token" : "Hide token";
    });
  }
  // Wire help-panel toggles for any field that has a help entry.
  target.querySelectorAll(".claw-help-trigger").forEach(btn => {
    const panel = target.querySelector(`.claw-help-panel[data-field="${btn.dataset.field}"]`);
    if (!panel) return;
    btn.addEventListener("click", () => {
      const opening = panel.hidden;
      panel.hidden  = !opening;
      btn.setAttribute("aria-expanded", String(opening));
    });
  });

  const cfJwtInp  = opts.cfAccess ? target.querySelector(".claw-cfjwt")    : null;
  const eyeJwtBtn = opts.cfAccess ? target.querySelector(".claw-eye-jwt")   : null;
  if (eyeJwtBtn && cfJwtInp) {
    eyeJwtBtn.addEventListener("click", () => {
      const showing = cfJwtInp.type !== "password";
      cfJwtInp.type  = showing ? "password" : "text";
      eyeJwtBtn.title = showing ? "Show JWT" : "Hide JWT";
    });
  }
  if (cfJwtInp) {
    cfJwtInp.addEventListener("input", () => {
      localStorage.setItem(keyCfJwt, cfJwtInp.value.trim());
      _syncCanvasKeys(urlInp.value.trim(), tokenInp.value.trim(), cfJwtInp.value.trim());
    });
  }
  const outEl    = target.querySelector(".claw-out");
  const actBox   = target.querySelector(".claw-actions");

  // _syncCanvasKeys and _effectiveUrl read from opts directly (not the const aliases
  // below) so they are safe to call during mountClawProbe initialisation, before those
  // consts have been reached by the interpreter.
  function _effectiveUrl(raw) {
    const pb = (opts.proxyBase || "").replace(/\/+$/, "");
    const pm = opts.proxyMode  || "origin";
    if (!pb || !raw) return raw;
    // Idempotent guard: already routed through this proxy → return as-is.
    if (raw.startsWith(pb + "/")) return raw;
    if (pm === "prefix") {
      // Encode as <proxyBase>/https/<host>/<path>, which avoids the `://` double-slash that
      // Cloudflare URL normalisation collapses before the worker receives the request.
      // Worker reconstructs https:// from the scheme prefix. Only HTTPS targets supported.
      if (raw.startsWith("https://")) return pb + "/https/" + raw.slice("https://".length);
      return raw;
    }
    // "origin" mode: replace the scheme+host with proxyBase.
    try {
      const u = new URL(raw);
      return pb + u.pathname + u.search;
    } catch (_) { return raw; }
  }

  function _syncCanvasKeys(rawUrl, rawToken, rawCfJwt) {
    if (!opts.syncCanvas) return;
    localStorage.setItem(_CLAWPROBE_KEY_URL,     _effectiveUrl(rawUrl)); // proxy URL for fetch
    localStorage.setItem(_CLAWPROBE_KEY_RAW_URL, rawUrl);                // raw URL for WS
    localStorage.setItem(_CLAWPROBE_KEY_TOKEN,   rawToken);
    if (opts.cfAccess) localStorage.setItem(_CLAWPROBE_KEY_CFJWT, rawCfJwt || "");
    updateClawPill(document.getElementById("claw-status"));
  }

  urlInp.addEventListener("input", () => {
    const raw = urlInp.value.trim();
    localStorage.setItem(keyUrl, raw);
    _syncCanvasKeys(raw, tokenInp.value.trim(), cfJwtInp?.value.trim());
  });
  tokenInp.addEventListener("input", () => {
    const tok = tokenInp.value.trim();
    localStorage.setItem(keyToken, tok);
    _syncCanvasKeys(urlInp.value.trim(), tok, cfJwtInp?.value.trim());
  });
  // Initialise canvas keys on page load with whatever is already stored.
  _syncCanvasKeys(savedUrl, savedToken, savedCfJwt);

  function setOutput(text, kind = "") {
    outEl.textContent = text;
    outEl.classList.remove("ok", "err");
    if (kind) outEl.classList.add(kind);
  }

  // Used by runAction to annotate the output line with "(via proxy)".
  const _proxyBase = (opts.proxyBase || "").replace(/\/+$/, "");

  function _fetchUrl(displayUrl) {
    return _effectiveUrl(displayUrl);
  }

  async function runAction(action) {
    const base = (urlInp.value || "").trim().replace(/\/+$/, "");
    if (!base) { setOutput("Set a base URL above first.", "err"); return; }
    const token = (tokenInp.value || "").trim();
    const displayUrl = base + (action.path || "/");
    const fetchTarget = _fetchUrl(displayUrl);
    const method = action.method || "GET";
    let body = null;
    if (typeof action.body === "function") {
      try { body = action.body(); }
      catch (e) { setOutput("body() threw: " + (e?.message || e), "err"); return; }
    } else if (action.body) {
      body = action.body;
    }
    const cfJwt = cfJwtInp ? cfJwtInp.value.trim() : "";
    const headers = { "Accept": "application/json, text/html, */*" };
    if (token) headers["Authorization"]          = "Bearer " + token;
    if (cfJwt) headers["CF-Access-Jwt-Assertion"] = cfJwt;
    if (body)  headers["Content-Type"]            = "application/json";

    const showUrl = _proxyBase ? displayUrl + "  (via proxy)" : displayUrl;
    setOutput(`→ ${method} ${showUrl}\n   …in flight`);
    // Hide any previous HTML frame while a new request is in flight.
    const _htmlFrame = target.querySelector(".claw-html-frame");
    if (_htmlFrame) _htmlFrame.hidden = true;
    const t0 = performance.now();
    try {
      const r = await fetch(fetchTarget, {
        method,
        headers,
        body: body ? JSON.stringify(body) : null,
      });
      const dt = Math.round(performance.now() - t0);
      const ct = r.headers.get("content-type") || "";
      const head = `← ${r.status} ${r.statusText}   ${dt}ms`;

      if (ct.includes("text/html")) {
        const html = await r.text();
        // A Cloudflare Access "Sign in" page comes back as HTML 200 when the
        // CF_Authorization JWT is missing or expired (it lasts ~24h). Rendering
        // that login form inside the iframe looks like a broken probe; detect it
        // and tell the student to refresh the JWT instead.
        if (/cloudflareaccess\.com|Sign in ・ Cloudflare Access|Cloudflare Access/i.test(html)) {
          setOutput(head + "\n\nCloudflare Access wants a fresh login because your CF Access JWT is missing or expired" +
            " (it lasts about a day).\n\nFix: open your NemoClaw tab → DevTools → Application → Storage → Cookies →" +
            " click the nemoclaw domain → copy the CF_Authorization value → paste it into the CF Access JWT field" +
            " above and probe again.", "err");
          const _fr = target.querySelector(".claw-html-frame");
          if (_fr) _fr.hidden = true;
          return;
        }
        setOutput(head + `   (HTML · ${html.length} bytes)`, r.ok ? "ok" : "err");
        // Render in a sandboxed iframe below the output bar.
        let fr = target.querySelector(".claw-html-frame");
        if (!fr) {
          fr = document.createElement("iframe");
          fr.className = "claw-html-frame";
          fr.setAttribute("sandbox", "allow-same-origin allow-popups");
          target.querySelector(".claw-probe").appendChild(fr);
        }
        fr.srcdoc = html;
        fr.hidden = false;
      } else {
        let j = null, printed;
        if (ct.includes("application/json")) {
          j = await r.json();
          if (action.filterModels && j && Array.isArray(j.data)) {
            const f = action.filterModels;
            const test = typeof f === "function" ? f
              : Array.isArray(f) ? (id) => f.some(s => String(id).includes(s))
              : (id) => String(id).includes(String(f));
            const before = j.data.length;
            j = { ...j, data: j.data.filter(m => test(m.id ?? m)) };
            j._filtered = `showing ${j.data.length} of ${before}`;
          }
          printed = JSON.stringify(j, null, 2);
          // Auto-fill the bearer token from the response when the probe knows
          // how to find it. OpenClaw's /api/agent exposes the gateway token in
          // agent.dashboardUrl ("/#token=…"), so base URL + CF Access JWT is
          // enough to discover it, with no manual paste needed.
          if (opts.autofillToken && r.ok && j) {
            try {
              const found = opts.autofillToken(j);
              if (found && found !== tokenInp.value.trim()) {
                tokenInp.value = found;
                localStorage.setItem(keyToken, found);
                _syncCanvasKeys(urlInp.value.trim(), found, cfJwtInp ? cfJwtInp.value.trim() : "");
                printed += "\n\n↳ bearer token auto-filled from this response (" + found.slice(0, 8) + "…). Ready for the gateway steps below.";
              }
            } catch (_) { /* response shape didn't match; leave the field as-is */ }
          }
        } else {
          printed = await r.text();
        }
        setOutput(head + "\n\n" + printed, r.ok ? "ok" : "err");
      }
    } catch (e) {
      const dt = Math.round(performance.now() - t0);
      const hint = "Possible causes:\n" +
        "• CORS blocked, because a header is not in the Access-Control-Allow-Headers preflight response.\n" +
        "• Wrong URL, so confirm no trailing /v1 on the base URL.\n" +
        "• Service offline. If the launchable just started, wait 30 s and try again.\n" +
        "• 502 on /v1/chat/completions, so the model backend isn't responding; check that\n" +
        "  NVIDIA_API_KEY resolved correctly in the launchable environment.\n\n" +
        "Gateway token: printenv | grep TOKEN  (OPENCLAW_GATEWAY_TOKEN)";
      setOutput(`✗ network error after ${dt}ms\n   ${String(e?.message || e)}\n\n${hint}`, "err");
    }
  }

  actions.forEach(action => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "claw-btn" + (action.kind === "alt" ? " alt" : "");
    b.textContent = action.label;
    b.addEventListener("click", async () => {
      b.disabled = true;
      try { await runAction(action); }
      finally { b.disabled = false; }
    });
    actBox.appendChild(b);
  });

  return {
    getUrl:   () => urlInp.value.trim(),
    getToken: () => tokenInp.value.trim(),
    run:      runAction,
  };
}


// ── Gateway plumbing, shared by 03a/03b/03c/04a ─────────────────────────────
// GW_CONNECT is prepended to a gateway cell's code; it opens the /cli/gateway
// WebSocket, runs the challenge/response handshake, and parks state.call/state._ws.
// mountGwRecover mounts the health-check + recover + logs flow. Both honour the
// canvas Stop button via helpers.signal. Previously copy-pasted into all four pages.
// One streamed chat turn to the live OpenClaw agent over the /cli/gateway
// WebSocket. Keeps one socket open per tab (reconnects if dropped). Reads the
// launchable URL + token the OpenClaw probe stored. The gateway-page artifacts
// use this as their mountChatUI respond, so chatting talks to the real agent.
let _ocSock = null;
export async function openclawChat(message, { session = "main", onToken, onTool, view, signal = null, idleMs = 90000, totalMs = 240000 } = {}) {
  /* @doc <code>helpers.openclawChat(message, {session, onToken, onTool, view})</code> :: Send one chat turn to the live OpenClaw agent over the <code>/cli/gateway</code> WebSocket and stream the reply. Reads the launchable URL + token from the OpenClaw probe (Kickstart page). Pass a <code>view</code> (a <code>mountChatUI</code> <code>ctx.view</code>) and it drives the whole observable trace for you: answer text, a stack-ordered chip per tool/command call (with its args and full result, errors marked), and the gateway-reported context-token budget. (Or pass <code>onToken(delta)</code>/<code>onTool(name,{id,args})</code> to handle events yourself.) The gateway streams no reasoning channel, so none is shown. Reuse the same <code>session</code> for multi-turn. The gateway companion to chat()/createReactAgent. */
  const rawUrl = (localStorage.getItem("nemoclaw_clawrawurl") || localStorage.getItem("nemoclaw_clawurl") || "").replace(/\/+$/, "");
  const token  = localStorage.getItem("nemoclaw_clawtoken") || "";
  if (!rawUrl || !token) throw new Error("Connect first on the Kickstart page (3a): set your launchable URL + token in the probe.");
  const wsUrl = rawUrl.replace(/^https/, "wss").replace(/^http(?!s)/, "ws") + "/cli/gateway";
  async function connect() {
    return await new Promise((resolve, reject) => {
      const pend = {}, ws = new WebSocket(wsUrl);
      let chatCb = null;
      const call = (method, params) => new Promise((res, rej) => {
        const id = Math.random().toString(36).slice(2) + Date.now().toString(36);
        const tmo = setTimeout(() => { delete pend[id]; rej(new Error(method + " timed out")); }, 20000);
        pend[id] = { res, rej, tmo };
        ws.send(JSON.stringify({ type: "req", id, method, params: params || {} }));
      });
      ws.onmessage = ev => { let d; try { d = JSON.parse(ev.data); } catch (_) { return; }
        if (d.type === "res" && d.id && pend[d.id]) { const p = pend[d.id]; clearTimeout(p.tmo); delete pend[d.id]; d.ok ? p.res(d.payload) : p.rej(new Error(d.error?.message || "gateway error")); }
        if (d.type === "event" && chatCb) chatCb(d);
      };
      ws.onerror = () => {};
      ws.onclose = () => { if (_ocSock && _ocSock.ws === ws) _ocSock = null; };
      const sock = { ws, call, setCb: cb => { chatCb = cb; }, subs: {} };
      const base = ws.onmessage;
      ws.onmessage = ev => { let d; try { d = JSON.parse(ev.data); } catch (_) { return; }
        if (d.event !== "connect.challenge") { base(ev); return; }
        ws.onmessage = base;
        call("connect", { minProtocol: 4, maxProtocol: 4, client: { id: "openclaw-control-ui", version: "0.1.0", platform: "browser", mode: "webchat" }, caps: ["tool-events"], role: "operator", scopes: ["operator.read", "operator.write", "operator.admin"], auth: { token } })
          .then(() => resolve(sock)).catch(reject);
      };
      setTimeout(() => reject(new Error("no challenge arrived within 15s. Your Cloudflare Access session likely expired. Reopen your launchable URL to re-authenticate.")), 15000);
    });
  }
  if (!_ocSock || _ocSock.ws.readyState !== 1) _ocSock = await connect();
  const sock = _ocSock;
  if (!sock.subs[session]) { await sock.call("sessions.messages.subscribe", { key: session }); sock.subs[session] = true; }
  // Pull readable text out of a gateway tool result / partial result, in full.
  const resText = (r) => { if (r == null) return ""; if (typeof r === "string") return r;
    if (Array.isArray(r.content)) return r.content.map(c => c && c.text || "").join("\n");
    return JSON.stringify(r); };
  // One-line summary of a tool's args for the chip label (command, path, query…).
  const argSummary = (a) => { if (a == null) return ""; if (typeof a === "string") return a;
    const v = a.command || a.path || a.query || a.file || Object.values(a)[0]; return v == null ? "" : String(v); };
  return await new Promise((resolve, reject) => {
    let text = "", myRun = null, idle, glob, toolStarts = 0, usedTok = 0, winTok = 0, lastModel = "";
    const chips = {};   // toolCallId -> chip element (stack-ordered, never reused)
    const done = (stalled) => { clearTimeout(idle); clearTimeout(glob); sock.setCb(null);
      if (stalled) sock.call("chat.abort", { sessionKey: session }).catch(() => {});
      if (!text.trim() && toolStarts > 0) text = "(the agent ran " + toolStarts + " tool(s) but returned no text. Try the Health check / Recover cells on Kickstart)";
      if (view && usedTok) view.usage({ context: usedTok, window: winTok || undefined, model: lastModel });
      resolve(text); };
    const bump = () => { clearTimeout(idle); idle = setTimeout(() => done(true), idleMs); };
    glob = setTimeout(() => done(true), totalMs);
    // Stop button: abort the agent run (chat.abort) and resolve with what we have.
    if (signal) { if (signal.aborted) return done(true); signal.addEventListener("abort", () => done(true), { once: true }); }
    sock.setCb(d => {
      const pl = d.payload || {};
      if (pl.isHeartbeat || d.event === "health" || d.event === "tick") return;
      if (myRun && pl.runId && pl.runId !== myRun) return;
      bump();
      // The gateway rides its token accounting on the frames: totalTokens = used,
      // contextTokens = the agent's configured window. Trust both (this deployment
      // may size the same model differently than the build endpoint).
      if (pl.totalTokens) usedTok = pl.totalTokens;
      if (pl.contextTokens) winTok = pl.contextTokens;
      if (pl.model) lastModel = pl.model;
      if (d.event === "chat" && pl.state === "final") { text = (pl.message && pl.message.content && pl.message.content[0] && pl.message.content[0].text) || text; return; }
      if (d.event !== "agent") return;
      const sk = pl.sessionKey || ""; if (sk !== session && !sk.endsWith(":" + session)) return;
      const data = pl.data || {}, stream = pl.stream || "";
      const id = data.toolCallId;
      if (stream === "assistant" || ("delta" in data && "text" in data)) {
        const full = data.text || text;
        if (full.length > text.length) { const delta = full.slice(text.length); if (view) view.token(delta); else if (onToken) onToken(delta); }
        text = full;
      }
      else if (stream === "tool" && data.phase === "start") {
        toolStarts++; const name = data.name || "tool"; const sum = argSummary(data.args);
        if (view) chips[id] = view.tool(name + (sum ? " · " + sum : ""), "(running…)");
        else if (onTool) onTool(name, { id, args: data.args });
      }
      else if (stream === "tool" && data.phase === "update" && view && chips[id] && data.partialResult) {
        const b = chips[id].querySelector(".chatui-tool-body"); if (b) b.textContent = resText(data.partialResult);
      }
      else if (stream === "tool" && data.phase === "result" && view && chips[id]) {
        const c = chips[id], b = c.querySelector(".chatui-tool-body"); if (b) b.textContent = resText(data.result);
        if (data.isError) { c.classList.add("err"); const s = c.querySelector("summary"); if (s) s.textContent = s.textContent.replace("🔧", "✗"); }
      }
      else if (data.phase === "end" && !data.itemId) { done(false); }
    });
    bump();
    sock.call("chat.send", { sessionKey: session, idempotencyKey: Math.random().toString(36).slice(2) + Date.now().toString(36), message })
      .then(res => { myRun = (res && res.runId) || null; })
      .catch(e => { clearTimeout(idle); clearTimeout(glob); sock.setCb(null); reject(e); });
  });
}

export const GW_CONNECT = `
const rawUrl = localStorage.getItem("nemoclaw_clawrawurl") ||
               localStorage.getItem("nemoclaw_clawurl") || "";
const token  = localStorage.getItem("nemoclaw_clawtoken") || "";
if (!rawUrl || !token) {
  helpers.log("Fill in the OpenClaw probe above (URL + token) first.");
  return;
}
const wsUrl = rawUrl.replace(/\\/+$/, "").replace(/^https/, "wss").replace(/^http(?!s)/, "ws") + "/cli/gateway";
helpers.log("→ " + wsUrl);

// Close any socket a previous Connect on this flow left open, so re-running a
// node (or running another Connect) does not pile up live WebSockets in the
// background. We keep ONE socket per flow on state._ws.
if (state._ws) { try { state._ws.close(); } catch (_) {} state._chatCb = null; }

const _pend = {};
const _ws = new WebSocket(wsUrl);
state._ws = _ws;
// Stop button: abort the run → close the socket and reject any in-flight call.
if (typeof helpers !== "undefined" && helpers.signal) helpers.signal.addEventListener("abort", () => {
  try { _ws.close(); } catch (_) {}
  for (const _id in _pend) { try { clearTimeout(_pend[_id].tmo); _pend[_id].reject(new Error("stopped")); } catch (_) {} delete _pend[_id]; }
}, { once: true });
_ws.onmessage = ev => {
  let d; try { d = JSON.parse(ev.data); } catch (_) { return; }
  if (d.type === "res" && d.id && _pend[d.id]) {
    const p = _pend[d.id]; clearTimeout(p.tmo); delete _pend[d.id];
    if (d.ok) p.resolve(d.payload); else p.reject(new Error(d.error?.message || "gateway error"));
  }
  if (d.type === "event" && state._chatCb) state._chatCb(d);
};
_ws.onerror = () => {};
state._chatCb = null;
state.call = (method, params) => new Promise((resolve, reject) => {
  const id  = Math.random().toString(36).slice(2) + Date.now().toString(36);
  const tmo = setTimeout(() => { delete _pend[id]; reject(new Error(method + " timed out")); }, 20000);
  _pend[id] = { resolve, reject, tmo };
  _ws.send(JSON.stringify({ type: "req", id, method, params: params || {} }));
});
await new Promise((resolve, reject) => {
  const base = _ws.onmessage;
  _ws.onmessage = ev => {
    let d; try { d = JSON.parse(ev.data); } catch (_) { return; }
    if (d.event !== "connect.challenge") { base(ev); return; }
    _ws.onmessage = base;
    state.call("connect", {
      minProtocol: 4, maxProtocol: 4,
      client: { id: "openclaw-control-ui", version: "0.1.0", platform: "browser", mode: "webchat" },
      caps: ["tool-events"], role: "operator",
      scopes: ["operator.read", "operator.write", "operator.admin"],
      auth: { token },
    }).then(pl => {
      helpers.log("● connected  v" + (pl?.server?.version || "?") + "  scopes: " + (pl?.auth?.scopes || []).join(", "));
      resolve(pl);
    }).catch(reject);
  };
  setTimeout(() => reject(new Error("no challenge arrived within 15s. Your Cloudflare Access session most likely expired. Open your launchable URL (https://nemoclaw-<id>.brevlab.com) in a new tab to re-authenticate, then re-run Connect. (Less often, the launchable is still booting, so wait 30s and retry.)")), 15000);
});
`;

// ── Shared recover flow (health check + toolSearch repair) ───────────────────
// Defined as a function so every gateway page mounts the same detect-and-recover
// cells with one line: mountGwRecover("#gw-recover"). Synced across 03a/03c/04a.
export function mountGwRecover(sel) {
  mountCanvasFlow(sel, {
  label: "Detect & recover · health check, then escalating reset",
  intro: "Health check, recover, and logs for the shared agent runtime. Health check tests whether the agent can run a command and whether toolSearch is on; Recover disables toolSearch and clears sessions (the restart that applies it is opt-in, so Run-all is safe); Runtime logs tails the log when a run stalls. Run these on a fresh launchable, or whenever a chat logs ⚠ DEGRADED.",
  edges: [
    { from: "gw-health", to: "gw-fix" },
  ],
  nodes: [
    {
      id: "gw-health", icon: "🩺", title: "Health check", x: 0, y: 0,
      summary: "Checks env status, toolSearch, stuck approvals, and runs one trivial command. HEALTHY = tools work; DEGRADED = run Recover.",
      code: GW_CONNECT + `
// ── tune these ──────────────────────────────────────────────────────────────
const PROBE_TIMEOUT_S = 60;                // how long to wait for the test command (this model can be slow)
const PROBE_MARKER    = "HEALTHCHECK_OK";  // the agent must echo this for a pass
// ──────────────────────────────────────────────────────────────────────────────
helpers.log("Checking the runtime");

// 1. Is the sandbox/environment even available?
try {
  const envs = await state.call("environments.list", {});
  (envs.environments || []).forEach(e => helpers.log("  env " + e.id + ": " + e.status));
} catch (e) { helpers.log("  environments.list failed: " + e.message); }

// 2. The #1 cause of the tool_search_code loop: tools.toolSearch is ON, so the
//    model uses the code bridge to find tools and gets stuck instead of calling
//    exec. The Recover cell turns it off.
let toolSearch = null;
try {
  const cfg = await state.call("config.get", {});
  toolSearch = !!(cfg.parsed && cfg.parsed.tools && cfg.parsed.tools.toolSearch);
  helpers.log("  tools.toolSearch: " + toolSearch + (toolSearch ? "  ← likely the cause; the Recover cell disables it" : ""));
} catch (e) { helpers.log("  config.get failed: " + e.message); }

// 3. A command stuck waiting on an approval looks exactly like a hang.
let pending = 0;
try {
  const appr = await state.call("exec.approval.list", {});
  pending = Array.isArray(appr) ? appr.length : 0;
  helpers.log("  pending exec approvals: " + pending);
} catch (e) { helpers.log("  exec.approval.list failed: " + e.message); }

// 3. Behavioral probe: ONE trivial command on a fresh key, short budget. We are
//    not after prose, only proof that a shell command runs and returns output.
const PROBE = "quick-health-" + Math.random().toString(36).slice(2, 8);
await state.call("sessions.messages.subscribe", { key: PROBE });
let ok = false, sawTool = false, runId = null;
await new Promise((resolve) => {
  const timer = setTimeout(resolve, PROBE_TIMEOUT_S * 1000);
  if (helpers.signal) helpers.signal.addEventListener("abort", () => resolve(), { once: true });
  state._chatCb = d => {
    const pl = d.payload || {};
    if (pl.isHeartbeat || d.event === "health" || d.event === "tick") return;
    if (runId && pl.runId && pl.runId !== runId) return;
    if (d.event !== "agent") return;
    const data = pl.data || {};
    if ((data.itemId || "").startsWith("tool:") && data.phase === "start") sawTool = true;
    if ((data.itemId || "").startsWith("command:") && data.phase === "end" && data.exitCode === 0 && (data.output || "").includes(PROBE_MARKER)) ok = true;
    if (data.phase === "end" && !data.itemId) { clearTimeout(timer); state._chatCb = null; resolve(); }
  };
  state.call("chat.send", { sessionKey: PROBE, idempotencyKey: "h" + Date.now(), message: "Run exactly this with your exec tool and report nothing else: echo " + PROBE_MARKER })
    .then(r => { runId = r && r.runId; }).catch(() => { clearTimeout(timer); resolve(); });
});
state.call("chat.abort", { sessionKey: PROBE }).catch(() => {});
state.call("sessions.delete", { key: PROBE }).catch(() => {});   // don't leave the probe session behind

if (ok) {
  helpers.log("✓ HEALTHY. The agent ran a command and returned its output. Tool calls will work now.");
} else {
  helpers.log("✗ DEGRADED. No command result came back" + (sawTool ? " (the agent fired tools but exec produced nothing)" : "") + (pending ? "; " + pending + " exec approval(s) stuck" : "") + (toolSearch ? "; tools.toolSearch is ON" : "") + ".");
  helpers.log("  → Run the 🛠 Recover cell next" + (toolSearch ? " (it turns off toolSearch, the usual cause)" : "") + ".");
}
return { healthy: ok, pendingApprovals: pending, toolSearch };
`,
    },
    {
      id: "gw-fix", icon: "🛠", title: "Recover", x: 1, y: 0,
      summary: "Disables tools.toolSearch via config.patch (the cause of the tool_search_code loop) and clears sessions. The restart that applies the change is opt-in (set DO_RESTART = true and re-run this cell), so Run-all never knocks the runtime out mid-flow.",
      code: GW_CONNECT + `
helpers.log("Repairing the runtime");

// 1. THE KEY FIX. tools.toolSearch lets the model run a code "bridge" to find and
//    invoke tools. A weaker model (e.g. nemotron-3-super-120b) loops on that
//    bridge ("tool_search_code · run bridge code") and never calls exec. Turn it
//    off with a config merge-patch so the agent uses the native exec tool.
const cfg = await state.call("config.get", {});
if (cfg.parsed && cfg.parsed.tools && cfg.parsed.tools.toolSearch) {
  await state.call("config.patch", { raw: JSON.stringify({ tools: { toolSearch: false } }), baseHash: cfg.hash });
  helpers.log("  ✓ disabled tools.toolSearch (the tool_search_code loop)");
} else {
  helpers.log("  tools.toolSearch already off");
}

// 2. Clear session state: reset the Main Session, delete throwaway sessions.
await state.call("sessions.reset", { key: "agent:main:main" }).catch(() => {});
let offset = 0, all = [];
for (;;) { const page = await state.call("sessions.list", { limit: 100, offset }); all = all.concat(page.sessions || []); if (!page.hasMore) break; offset = page.nextOffset; }
let removed = 0;
for (const s of all.filter(s => !/:main$/.test(s.key))) { try { await state.call("sessions.delete", { key: s.key }); removed++; } catch (e) {} }
helpers.log("  ✓ reset agent:main:main and deleted " + removed + " throwaway session(s)");

// 3. Applying the toolSearch change needs a runtime restart, which DROPS the
//    connection for ~40s, so it is opt-in, never automatic. Leave DO_RESTART
//    false (config is patched and applies on the next restart); flip it to true
//    and re-run ONLY this cell when you want to restart now. Default-false keeps
//    "Run all" from knocking the runtime out from under the cells after it.
const DO_RESTART = false;
if (DO_RESTART) {
  await state.call("gateway.restart.request", { reason: "course recovery: disable toolSearch" }).catch(e => helpers.log("  restart failed: " + e.message));
  helpers.log("  ⟳ restart requested. Wait ~40s, then re-run Connect and the 🩺 Health check.");
  helpers.log("  Still failing after that? The sandbox is wedged below the gateway, so relaunch the launchable from Brev.");
} else {
  helpers.log("  config patched + sessions cleared. To apply it now: set DO_RESTART = true above and re-run THIS cell (it restarts the runtime, ~40s).");
}
`,
    },
    {
      id: "gw-logs", icon: "📜", title: "Runtime logs", x: 2, y: 0,
      summary: "Tails the gateway/agent log (logs.tail): model calls, tool dispatches, errors, hangs. The deepest view when a run stalls and Health check is green; reasoning itself is not exposed over the gateway.",
      code: GW_CONNECT + `
// ── tune these ──────────────────────────────────────────────────────────────
const LOG_LINES = 40;          // how many recent log lines to show
// ──────────────────────────────────────────────────────────────────────────────
const lg = await state.call("logs.tail", { limit: LOG_LINES + 20 });
const lines = lg.lines || [];
helpers.log("runtime log · last " + lines.length + " line(s)" + (lg.file ? " · " + lg.file : ""));
lines.slice(-LOG_LINES).forEach(raw => {
  // Each line is a JSON STRING: { "0": "{subsystem…}", "1": <message>, …, _meta }.
  // Parse it, read the level + subsystem, and join the numeric arg keys (skip "0",
  // the subsystem tag) into one message.
  let L; try { L = typeof raw === "string" ? JSON.parse(raw) : raw; } catch (_) { return; }
  const lvl = ((L._meta && L._meta.logLevelName) || "?").padEnd(5);
  let sub = ""; try { sub = JSON.parse(L["0"] || "{}").subsystem || ""; } catch (_) {}
  const msg = Object.keys(L).filter(k => /^[0-9]+$/.test(k) && k !== "0")
    .map(k => typeof L[k] === "string" ? L[k] : JSON.stringify(L[k]))
    .join(" ").replace(/\\n/g, " ").slice(0, 180);
  if (msg) helpers.log("  " + lvl + (sub ? " [" + sub + "]" : "") + " " + msg);
});
helpers.log.details("raw logs.tail response", lg);
return { lines: lines.length };
`,
    },
  ],
  });
}

