// ─── Shared runtime for the nemoclaw web course (frontend track) ─────────────

// Remote-service-only. Model calls go to build.nvidia.com via the Cloudflare CORS worker.
// The OpenClaw launchable on Brev is the only other remote; auth is the student's own key.
// No lab proxy, no llm_client:9000, no Python kernel.

const DIRECT_URL = "https://nvidia-api-cors-proxy.vkudlay.workers.dev/v1";
// Billing attribution: the X-BILLING-SOURCE header attributes spend to this DLI course.
// The CORS proxy must allow it in preflight and forward it upstream (attached in _apiHeaders below).
const BILLING_SOURCE = "dli-nemoclaw-web";
// Web-cell model contract: the short course uses the fast reasoning-capable Nemotron nano.
// DEFAULT_MODEL is chat()'s fallback when a cell passes no model. REASONING_MODEL is the
// explicit reasoning-lesson handle; both are injected into every run-cell sandbox.

// Keep DEFAULT_MODEL / REASONING_MODEL in sync with the skill-meta models in SKILL.html.
const DEFAULT_MODEL   = "nvidia/nemotron-3-nano-30b-a3b";
export const REASONING_MODEL = "nvidia/nemotron-3-nano-30b-a3b";

// ── Lab-only step detection ─────────────────────────────────────────────────
// Model calls and web search run from any page; the OpenClaw agent steps do not.
// They reach the NemoClaw launchable on Brev, so they get badged instead of failing.
const LAB_ONLY_RE = /\/lab\/openclaw|open(?:shell|claw):8995|\/lab\/svc\/sandbox-admin|sandbox-admin:8099/;
function _stepSource(node) { return node ? String(node.code || "") : ""; }
export function _stepLabOnly(node) { return LAB_ONLY_RE.test(_stepSource(node)); }
export function _labOnlyService(node) {
  const s = _stepSource(node);
  if (/\/lab\/openclaw|open(?:shell|claw):8995/.test(s))        return "OpenClaw, the sandboxed agent in your NemoClaw launchable";
  if (/sandbox-admin/.test(s))                                  return "the sandbox controller in your NemoClaw launchable";
  return "your NemoClaw launchable";
}

// ── Data-driven diagram grammar → _diagram.js ───────────────────────────────
// The node/edge SVG engine (diagramSVG / mountDiagram) lives in _diagram.js.
// Re-exported here so HELPER_FNS, the helper menu, viz.diagram, and page imports are unchanged.
import { diagramSVG, mountDiagram } from "./_diagram.js";
export { diagramSVG, mountDiagram };

// ── ganttBarsSVG (02c concurrency figure) → _figures.js ──────────────────────
// The 02c concurrency figure generator lives in _figures.js.
// Re-exported here so HELPER_FNS, the menu, viz.ganttBars, and 02c's import are unchanged.
import { ganttBarsSVG } from "./_figures.js";
export { ganttBarsSVG };

const LAB_MODEL     = "nvidia/nemotron-3-nano-30b-a3b"; // proxy-mode default (cfg.model in the lab)
const CONFIG_KEY    = "__nv_slim_cfg_v1";

// The web course runs JavaScript only.
// The in-browser Python / JupyterLab-kernel path was removed; Python lives in the notebooks.

// ── Endpoint discovery ────────────────────────────────────────────────────────
let _cfgPromise = null;

export async function getConfig() {
  /* @doc <code>helpers.getConfig()</code> ::
       Returns the active endpoint config <code>{ mode, url, model, needsKey }</code>. This
       course resolves it to build.nvidia.com through the hosted proxy, so you rarely need
       it directly. */
  if (_cfgPromise) return _cfgPromise;
  _cfgPromise = (async () => {
    // Return cached result for this tab
    try {
      const c = sessionStorage.getItem(CONFIG_KEY);
      if (c) return JSON.parse(c);
    } catch (_) {}

    // Self-contained course: no DLI lab and no proxy to probe.
    // Every model call goes to build.nvidia.com through the hosted Cloudflare worker.
    // Auth is the student's own nvapi- key, kept in localStorage.
    const cfg = { mode: "direct", url: DIRECT_URL, model: DEFAULT_MODEL, needsKey: true };

    try { sessionStorage.setItem(CONFIG_KEY, JSON.stringify(cfg)); } catch (_) {}
    return cfg;
  })();
  return _cfgPromise;
}

// ── Key management (used in direct mode only) ─────────────────────────────────
export function getKey() {
  /* @doc <code>helpers.getKey()</code> ::
       Returns the <code>nvapi-</code> key saved in this browser (<code>localStorage</code>),
       or <code>null</code>. Model calls use it automatically; read it only if you call an
       endpoint by hand. */
  return localStorage.getItem("nvapi");
}
export function setKey(k) { localStorage.setItem("nvapi", k.trim()); }
export function hasKey() { return !!getKey(); }

// The OpenAI JS SDK (what ChatOpenAI uses) attaches x-stainless-* headers.
// The build CORS proxy rejects them in preflight, so the browser blocks the call.
// This wrapper strips them; pass it as configuration.fetch when constructing ChatOpenAI.
export function browserChatFetch() {
  /* @doc <code>helpers.browserChatFetch()</code> ::
       Returns a <code>fetch</code> that strips the OpenAI SDK's <code>x-stainless-*</code>
       headers (the build CORS proxy rejects them in preflight) and attaches the
       <code>X-BILLING-SOURCE</code> tag. Pass it as <code>configuration.fetch</code> when
       constructing a browser <code>ChatOpenAI</code>. */
  return (url, init = {}) => {
    const h = init.headers instanceof Headers ? init.headers : new Headers(init.headers || {});
    for (const k of [...h.keys()]) { if (k.startsWith("x-stainless")) h.delete(k); }
    h.set("X-BILLING-SOURCE", BILLING_SOURCE);
    return fetch(url, { ...init, headers: h });
  };
}

export function requireKey(returnUrl) {
  // In proxy mode a key is never required, so skip the check
  getConfig().then(cfg => {
    if (!cfg.needsKey) return;
    if (!hasKey()) location.href = `index.html?next=${encodeURIComponent(returnUrl || location.pathname)}`;
  });
}

// Retry a fetch on transient failure (network error, 502 / 503 / 504 / 524), backing off 250ms, 500ms, 1000ms; streaming calls retry only the headers phase.
// `timeoutMs` aborts the fetch when no headers arrive, so a Cloudflare 524 cannot hang the cell for 100+ seconds.
async function fetchRetry(url, opts = {}, { retries = 2, backoffMs = 250, timeoutMs = 60000 } = {}) {
  /* @doc <code>helpers.fetchRetry(url, opts)</code> ::
       Like <code>helpers.fetch</code>, but retries up to 2 times on 5xx or network errors
       with exponential backoff (250 / 500 / 1000 ms). Use it when calling an endpoint by
       hand (e.g. the Responses API) and you want resilience without writing the loop. */
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
      // 5xx (including Cloudflare's 524 origin-timeout) is transient upstream.
      // 4xx is the caller's fault, don't retry.
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

// Headers shared by every model request: JSON content type, the BILLING_SOURCE tag, and the student's key in direct mode.
// Built in one place so chat / chatStream / embed stay consistent and the billing tag is never dropped on a new call.
export function _apiHeaders(cfg) {
  const h = { "Content-Type": "application/json", "X-BILLING-SOURCE": BILLING_SOURCE };
  if (cfg.needsKey) h["Authorization"] = `Bearer ${getKey()}`;
  return h;
}

// ── Core API call ─────────────────────────────────────────────────────────────
// The default model reasons on a private channel before writing content.
// A small max_tokens leaves content empty (finish_reason "length"), so the default keeps headroom.
export async function chat({ messages, tools = null, model = null, temperature = 0.1, max_tokens = 8196, response_format = null, tool_choice = null, signal = null }) {
  /* @doc <code>helpers.chat(opts)</code> ::
       One-shot, non-streaming chat completion. Returns the raw OpenAI-shape response. Use
       when you just want the final message. */
  const cfg = await getConfig();
  const useModel = model || cfg.model;
  const body = { model: useModel, messages, temperature, max_tokens };
  if (tools?.length)   body.tools           = tools;
  if (response_format) body.response_format = response_format;
  if (tool_choice)     body.tool_choice     = tool_choice;

  const headers = _apiHeaders(cfg);

  const resp = await fetchRetry(`${cfg.url}/chat/completions`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    credentials: "same-origin",
    signal,
  });
  if (!resp.ok) {
    const txt = await resp.text();
    // 524 is Cloudflare's origin-timeout.
    // The generic "524: <html>..." body does not help a student debug their cell, so surface it explicitly with next steps.
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

// Streaming wrapper. `onChunk(text)` receives each user-facing content delta.
// An optional third arg, chatStream(opts, onContent, { onReasoning, onMeta }), adds more.

// `onReasoning(text)` fires per reasoning_content delta.
// `onMeta(obj)` fires once at the end with { usage, finish_reason, model, raw }.
// The same fields are also returned as a summary, so callers can read totals callback-free.
export async function chatStream(opts, onChunk, extra = {}) {
  /* @doc <code>helpers.chatStream(opts)</code> ::
       Streaming chat completion; tokens flow into this panel's results view as they arrive.
       Returns a summary with <code>.content</code>, <code>.reasoning</code>,
       <code>.tool_calls</code>, <code>.finish_reason</code>, <code>.usage</code>. */
  const { messages, model = null, temperature = 0.1, max_tokens = 8196, tools = null, response_format = null, tool_choice = null, signal = null } = opts;
  const onReasoning = extra.onReasoning || null;
  const onMeta = extra.onMeta || null;
  const cfg = await getConfig();
  const useModel = model || cfg.model;

  const headers = _apiHeaders(cfg);

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
  // tool_calls arrive fragmented across frames: the streaming API splits function.arguments JSON into deltas, each tagged with an `index` for the call it belongs to.
  // Accumulate by index here so the caller ends with a flat [{id, function: {name, arguments}}] array.
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

  // Boundary-safe SSE frame parser: consume only complete "data: ...\n\n" frames.
  // Partial frames stay buffered for the next read.
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


// ── Canvas + cell runtime → _canvas.js ───────────────────────────────────────

// mountCanvasFlow, mountRunCell, the helper-menu builders, and error/log helpers live there.
// _canvas.js is a leaf that uses the registries and primitives only at call time, so re-exporting the two mount* entry points adds no load-time cycle.
import { mountCanvasFlow, mountRunCell } from "./_canvas.js";
export { mountCanvasFlow, mountRunCell };

// ── glossary → _glossary.js ─────────────────────────────────────────
// Re-exported here so the helper registry/menu and existing page imports are unchanged.
import {
  webSearch, instantAnswer, glossaryScore, loadGlossaryIndex, loadMaterialsCatalog,
} from "./_glossary.js";
export {
  webSearch, instantAnswer, glossaryScore, loadGlossaryIndex, loadMaterialsCatalog,
};

// ── rag → _rag.js ─────────────────────────────────────────
// Re-exported here so the helper registry/menu and existing page imports are unchanged.
import {
  embed, cosineSim,
} from "./_rag.js";
export {
  embed, cosineSim,
};

// ── OpenShell policy engine + launchable terminal → _openshell.js ────────────
// Used by 04a/04b only.
// Re-exported here so the helper registry/menu resolve these names and pages keep importing them from _shared.js.
import {
  terminal, evalSandboxNetwork, evalSandboxFs, OPENSHELL_POLICY_HARDENED,
  sandboxExec, policyGet, policyToYaml, annotatePolicyYaml, mountPolicyMap,
} from "./_openshell.js";
export {
  terminal, evalSandboxNetwork, evalSandboxFs, OPENSHELL_POLICY_HARDENED,
  sandboxExec, policyGet, policyToYaml, annotatePolicyYaml, mountPolicyMap,
};

// ── langchain → _langchain.js ─────────────────────────────────────────
// Re-exported here so the helper registry/menu and existing page imports are unchanged.
import {
  COURSE_PAGES, coursePage, CONTEXT_WINDOWS, contextWindow, estimateTokens, coursePages,
} from "./_langchain.js";
export {
  COURSE_PAGES, coursePage, CONTEXT_WINDOWS, contextWindow, estimateTokens, coursePages,
};

// ── A live chat artifact → _chat.js ──────────────────────────────────────────

// The chat-artifact widgets (ensureChatStyles / mountChatUI / mountAgentChat) live in _chat.js.
// The _chat.js -> _shared.js import cycle is load-safe because the refs sit inside function bodies, which run only after both modules finish loading.
import { ensureChatStyles, mountChatUI, mountAgentChat } from "./_chat.js";
export { ensureChatStyles, mountChatUI, mountAgentChat };

// Render search results into one text blob (numbered snippets with title + body + url) that the LLM can read as a tool result.
export function formatSearchResults(searchOut) {
  /* @doc <code>helpers.formatSearchResults(out)</code> ::
       Turn a <code>webSearch</code> or <code>instantAnswer</code> result into a numbered
       text block the LLM can read as a tool message. */
  if (searchOut.unreachable) {
    const api = searchOut.source === "glossary-term" ? "NVIDIA glossary term lookup" : "NVIDIA glossary index";
    return `(search unavailable: ${searchOut.error || "HTTP " + searchOut.status}. ` +
           `The ${api} ships with the course as a static file; this is usually a transient load error, so try again.)`;
  }
  if (!searchOut.results.length) {
    return `(no results for "${searchOut.query}". Tell the user you could not find current information on this; do not answer from memory.)`;
  }
  return searchOut.results.map((r, i) => {
    const tier = r.tier === "on_demand" ? "  (on-demand: open the link for the full source)"
               : r.tier === "cached" ? "  (cached)" : "";
    return `[${i + 1}] ${r.title}${tier}\n    ${r.body}\n    ${r.href}`;
  }).join("\n\n");
}

// ── viz.* builders → _viz.js ─────────────────────────────────────────────────

// The canvas visualization builders (makeViz) live in _viz.js, imported here because both mountCanvasFlow and the VIZ_BUILDERS registry below use it.
// The _viz.js -> _shared.js cycle is load-safe: a builder calls diagramSVG/ganttBarsSVG only when a cell invokes a viz helper, never at load.
import { makeViz } from "./_viz.js";
export const VIZ_BUILDERS = makeViz(() => {});

// ── Helper registry (single source of truth for the canvas helper menu) ───────

// The menu enumerates these and reads each one's source via Function.toString(), so the source cannot drift from the definition.
// `viz.*` source comes from the live viz object once a node has run; `state`, `fetch`, `trace`, and `log` are described by SPECIALS, since they are values and closures, not module functions.
export const HELPER_FNS = {
  chat, chatStream, webSearch, instantAnswer, formatSearchResults,
  embed, cosineSim, fetchRetry, getConfig, getKey, terminal,
  coursePage, coursePages, contextWindow, estimateTokens, browserChatFetch, diagramSVG, ganttBarsSVG, mountChatUI, mountAgentChat, mountKeyPanel, openclawChat,
  evalSandboxNetwork, evalSandboxFs, sandboxExec, policyGet, mountPolicyMap,
};
// SPECIALS: the menu entries that are not plain module functions, namely a value (state),
// the platform primitive (fetch), and per-node closures (trace, log). Each carries the
// row's sig + desc and the source shown in the editor. The menu reads sig/desc from a
// function's @doc, and from here otherwise, so each row has exactly one source.
export const SPECIALS = {
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
  signal: {
    sig: "<code>helpers.signal</code>",
    desc: `The <code>AbortSignal</code> for this run, wired to the Stop button. Pass it to <code>helpers.chat</code>/<code>chatStream</code> (they accept it automatically), to <code>helpers.fetch</code>, or to your own <code>WebSocket</code> cleanup so a long run actually cancels when the student hits Stop.`,
    src: `// helpers.signal aborts when the student clicks Stop.\nconst r = await helpers.fetch(url, { signal: helpers.signal });\n// ...or react to it directly:\nhelpers.signal.addEventListener("abort", () => ws.close(), { once: true });`,
  },
};

// A helper's self-doc is a leading `/* @doc <sig> :: <desc> */` comment in its body, read
// via Function.toString() so it stays tied to the code in both the lab and the standalone
// build. The menu prefers it over any curated fallback, so the docs cannot drift.

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

export function escHtml(s) { return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

// ── Page nav ──────────────────────────────────────────────────────────────────

// In-course navigation lives in the journey-map widget below the topbar: current section, prev/next links, and a "Course map" toggle for the full staircase.
// The topbar carries the brand and the key-pill only.
export function buildNav(currentFile) {
  /* @doc <code>helpers.buildNav(currentFile)</code> ::
       The persistent course menu for the sticky topbar: one compact pill per page (its id),
       the current page marked, every pill a real link so the jump bar stays visible and the
       link graph sees the edges. The in-body journey map is the rich view; this is the
       always-there way back and forward. */
  return (_JM_STEPS || []).filter(function (s) { return s.href; }).map(function (s) {
    var cur = s.href === currentFile ? " cur" : "";
    var t = (s.title || "").replace(/"/g, "&quot;");
    return '<a class="navpill' + cur + '" href="' + s.href + '" title="' + t + '">' + s.id + '</a>';
  }).join("");
}

// ── Journey map ─────────────────────────────────────────────────────────────

// Per-page progression: one box per sub-page, three per row, each row offset right by STAIR pixels so the figure cascades down a staircase. Call mountJourneyMap(sel, id) with the current step id to highlight its box.
// Done boxes get a dim "✓ Done"; the current box a green "★ You are here"; pending boxes stay neutral. A missing target element makes the call a no-op.
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

// Friendly label for the banner on the left of the bar.
// Sections 1-4 get a "Section N" label; Going Further is the end of the course.
// The short course has no separate assessment, so the cert belongs to the long course.
function _jmSectionLabel(stepId) {
  if (stepId === "next") return "Going Further";
  const m = String(stepId).match(/^(\d)/);
  return m ? `Section ${m[1]}` : "";
}

export function _escAttr(s) {
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
    const fill   = isCurrent ? "rgba(118,185,0,0.16)" : (isDone ? "rgba(118,185,0,0.07)" : "var(--e1,#161616)");
    const stroke = isCurrent ? "var(--g,#76b900)" : (isDone ? "var(--gd,#4a7a00)" : "var(--bd,#2a2a2a)");
    const sw     = isCurrent ? 2.2 : 1.1;
    const titleColor = isCurrent ? "var(--gs,#aee23a)" : (isDone ? "var(--td,#b0b0b0)" : "var(--tx,#f2f2f2)");
    const subColor   = isCurrent ? "var(--g,#76b900)" : (isDone ? "var(--tf,#6a6a6a)" : "var(--td,#a5a5a5)");
    const titlePrefix = isCurrent ? "★ " : (isDone ? "✓ " : "");
    return `
      <a href="${step.href}" style="text-decoration:none;">
        <g>
          <rect x="${x}" y="${y}" width="${W}" height="${H}" rx="8"
                style="fill:${fill};stroke:${stroke};stroke-width:${sw};"/>
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
    arrows.push(`<path d="M ${x1} ${cy} L ${x2} ${cy}" style="stroke:var(--tf,#6f6f6f);stroke-width:1.4;fill:none" marker-end="url(#jm-arr)"/>`);
  }
  const fullSvg = `
    <svg viewBox="0 0 ${viewW} ${viewH}" preserveAspectRatio="xMidYMid meet"
         xmlns="http://www.w3.org/2000/svg"
         role="img" aria-label="Course progression; current step highlighted."
         class="cf-jm-svg" style="display:block;width:100%;height:auto;">
      <defs>
        <marker id="jm-arr" viewBox="0 0 10 10" refX="9" refY="5"
                markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0,0 L10,5 L0,10 Z" style="fill:var(--tf,#6f6f6f)"/>
        </marker>
      </defs>
      ${arrows.join("")}
      ${boxes}
    </svg>`;

  // ── Slim bar: [Section banner] [current page info] [prev] [next] ──
  // Pages with no known current id (e.g. index.html passes null) collapse to one "Course map" banner with no prev/next stubs.
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

// ── Mode indicator. Call on page load to update key-pill ────────────────────

// Verify the saved nvapi key is actually accepted (GET /models, the cheapest authenticated call), not merely present. Cached per tab session so navigation does not re-hit the API.
// Only a hard 401/403 marks the key bad, so a network blip never downgrades a working key.
async function keyAccepted() {
  const cached = sessionStorage.getItem("nvapi_ok");
  if (cached) return cached === "1";
  const cfg = await getConfig();
  try {
    const r = await fetchRetry(`${cfg.url}/models`, { headers: _apiHeaders(cfg) }, { retries: 0, timeoutMs: 7000 });
    if (r.status === 401 || r.status === 403) { sessionStorage.setItem("nvapi_ok", "0"); return false; }
    if (r.ok) sessionStorage.setItem("nvapi_ok", "1");
    return r.ok;
  } catch (_) { return true; }   // network blip: do not cry wolf on a key that may be fine
}

export async function updateKeyPill(pill) {
  if (!pill) return;
  const cfg = await getConfig();
  if (cfg.needsKey && !hasKey()) {
    pill.textContent = "No API key"; pill.classList.remove("set"); return;
  }
  pill.textContent = "Key …"; pill.classList.add("set");
  const ok = await keyAccepted();
  if (ok) { pill.textContent = "Key set ✓"; pill.classList.add("set"); pill.title = "nvapi key verified this session"; }
  else { pill.textContent = "Key rejected ✗"; pill.classList.remove("set"); pill.title = "the saved nvapi key was refused (401/403). Re-enter it on Module 1a."; }
}

// Is the launchable's gateway reachable right now?
// The connect.challenge frame arrives only when the browser's Cloudflare Access session is still valid, so this detects an expired session that mere url+token presence cannot.
// Best-effort, ~6s cap.
function clawSessionOk(timeoutMs = 6000) {
  const rawUrl = localStorage.getItem("nemoclaw_clawrawurl") || localStorage.getItem("nemoclaw_clawurl") || "";
  if (!rawUrl) return Promise.resolve(false);
  const wsUrl = rawUrl.replace(/\/+$/, "").replace(/^https/, "wss").replace(/^http(?!s)/, "ws") + "/cli/gateway";
  return new Promise(res => {
    let done = false, ws;
    const finish = ok => { if (done) return; done = true; try { ws.close(); } catch (_) {} res(ok); };
    try { ws = new WebSocket(wsUrl); } catch (_) { return res(false); }
    const t = setTimeout(() => finish(false), timeoutMs);
    ws.onmessage = ev => { try { if (JSON.parse(ev.data).event === "connect.challenge") { clearTimeout(t); finish(true); } } catch (_) {} };
    ws.onerror = () => { clearTimeout(t); finish(false); };
    ws.onclose = () => { clearTimeout(t); finish(false); };
  });
}

// ── OpenClaw indicator. Re-validates the live session on every page load, because a
// stored url+token says nothing about whether the Cloudflare Access session still works.
export async function updateClawPill(pill) {
  if (!pill) return;
  const url   = localStorage.getItem("nemoclaw_clawurl")   || "";
  const token = localStorage.getItem("nemoclaw_clawtoken") || "";
  if (!(url && token)) { pill.textContent = "No OpenClaw"; pill.classList.remove("set"); pill.title = ""; return; }
  const host = url.replace(/^https?:\/\//, "").replace(/\/.*$/, "");
  pill.textContent = "OpenClaw …"; pill.classList.add("set"); pill.title = host + " · checking session";
  const ok = await clawSessionOk();
  if (ok) {
    pill.textContent = "OpenClaw ✓"; pill.classList.add("set"); pill.title = host + " · session live";
    try { localStorage.setItem("nemoclaw_claw_verified_at", String(Date.now())); } catch (_) {}
  } else {
    pill.textContent = "OpenClaw ⚠"; pill.classList.remove("set");
    pill.title = host + " · session expired or unreachable. Open the launchable and reconnect on Kickstart.";
  }
}

// ── Inline API-key setup panel → _keypanel.js ───────────────────────────────
// mountKeyPanel lives in _keypanel.js.
// Re-exported here so HELPER_FNS, the menu, and 01a's import are unchanged.
import { mountKeyPanel } from "./_keypanel.js";
export { mountKeyPanel };

// ── openclaw → _openclaw.js ─────────────────────────────────────────
// Re-exported here so the helper registry/menu and existing page imports are unchanged.
import {
  mountClawGateway, mountClawProbe, openclawChat, GW_CONNECT, mountGwRecover,
} from "./_openclaw.js";
export {
  mountClawGateway, mountClawProbe, openclawChat, GW_CONNECT, mountGwRecover,
};


// ── Theme toggle ─────────────────────────────────────────────────────────────

// A dark/light switch in the topbar. The active theme is data-theme on <html>, remembered in localStorage.
// The standalone sets data-theme before paint (a <head> script injected by bundle_standalone.py) so the page opens in the right palette with no flash; _style.css carries the matching light palette.
// No-ops in the topbar-less iframe.
export function mountThemeToggle() {
  /* @doc <code>helpers.mountThemeToggle()</code> ::
       Adds a dark/light toggle to the <code>.topbar</code>, saving the choice in
       <code>localStorage</code> under <code>theme</code>. No-ops with no topbar (the iframe
       export) or if one is already mounted. */
  const bar = document.querySelector(".topbar");
  if (!bar || bar.querySelector(".theme-toggle")) return;
  const root = document.documentElement;
  // The rendered theme is whatever data-theme says (set pre-paint in the standalone), or the dark :root default.
  // The OS-preference default lives only in that pre-paint init.
  const current = () => root.getAttribute("data-theme") || "dark";
  const btn = document.createElement("button");
  btn.className = "theme-toggle";
  btn.type = "button";
  btn.setAttribute("aria-label", "Toggle dark or light theme");
  btn.style.cssText = "flex:0 0 auto;margin-left:10px;width:30px;height:30px;display:inline-flex;" +
    "align-items:center;justify-content:center;font-size:15px;line-height:1;cursor:pointer;" +
    "background:transparent;color:var(--td);border:1px solid var(--bd);border-radius:7px;";
  function paint() {
    const t = current();
    // Show the icon for the theme the click switches TO.
    btn.textContent = t === "light" ? "☾" : "☀"; // moon -> go dark, sun -> go light
    btn.title = t === "light" ? "Switch to dark theme" : "Switch to light theme";
  }
  btn.addEventListener("click", () => {
    const next = current() === "light" ? "dark" : "light";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("theme", next); } catch (_) {}
    paint();
  });
  paint();
  const pill = bar.querySelector(".key-pill");
  if (pill) bar.insertBefore(btn, pill);
  else bar.appendChild(btn);
}

// Auto-mount on any page that ships a topbar (the lab and the full standalone).
if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountThemeToggle);
  } else {
    mountThemeToggle();
  }
}

