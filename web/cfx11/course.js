// Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { marked } from "../shared/vendor/marked-14.1.4.esm.js";
import { mountRuntimeWorkbench } from "../shared/runtime-workbench.js";
import { CoursePythonRunner } from "./runtime/runner.js";
import { ObservableOperations, formatDuration } from "./runtime/operations.js";

const MODEL_BASES = Object.freeze({
  direct: "https://integrate.api.nvidia.com/v1",
  proxy: "https://nvidia-api-cors-proxy.experiments.courses.nvidia.com/v1",
});
const BILLING_INVOKE_ORIGIN = "dli-cfx11-web";
const MODEL_ROUTE_STORAGE_KEY = "cfx11-model-route:v2";
const MODEL_PROBE_CANDIDATES = Object.freeze([
  "nvidia/nemotron-nano-12b-v2-vl",
  "nvidia/nemotron-3-nano-30b-a3b",
  "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
]);

const SOURCE_ASSET_REPLACEMENTS = Object.freeze(new Map([
  [
    "https://dli-lms.s3.amazonaws.com/assets/general/nvidia-logo.png",
    new URL("./assets/nvidia-logo.png", import.meta.url).href,
  ],
]));

const state = {
  manifest: null,
  contentBundle: null,
  lesson: null,
  runner: new CoursePythonRunner(new URL("./runtime/worker.js", import.meta.url)),
  blocks: [],
  activeBlock: null,
  activeChat: null,
  requestBlocks: new Map(),
  latestKernel: null,
  variableView: "focused",
  streams: [],
  agentRequestId: null,
  rawMarkdown: "",
  operations: new ObservableOperations(),
  verifiedModel: sessionStorage.getItem("cfx11-verified-model") || "",
  lastQueueStatus: "",
};

const elements = Object.fromEntries([
  "course-nav", "lesson-title", "lesson-meta", "lesson-body", "runtime-status", "run-all",
  "stop-runtime", "reset-runtime", "settings-dialog", "api-key", "api-status", "open-settings",
  "previous-lesson", "next-lesson", "progress-value", "progress-label", "theme-toggle",
  "clear-api-key", "kernel-status", "queue-status", "kernel-variables", "inspect-runtime",
  "restart-runtime", "test-api-key", "save-api-key", "model-route", "route-status", "runtime-panel",
  "connection-details", "connection-summary-status",
  "runtime-panel-title", "close-runtime-panel", "kernel-started", "start-runtime",
  "dock-stop-runtime", "clear-runtime-streams", "runtime-streams", "runtime-environment",
  "environment-settings", "runtime-agent-form", "runtime-agent-input", "runtime-agent-history",
  "operation-badge", "operation-summary", "runtime-operations", "clear-runtime-operations",
].map(id => [id, document.getElementById(id)]));

function defaultModelRoute(protocol = location.protocol, hostname = location.hostname) {
  const localHost = ["localhost", "127.0.0.1", "::1"].includes(hostname);
  const registeredProductionHost = protocol === "https:" && hostname === "cdn.dli.learn.nvidia.com";
  return localHost || registeredProductionHost ? "direct" : "proxy";
}

function selectedModelBase() {
  return MODEL_BASES[elements["model-route"]?.value] || MODEL_BASES[defaultModelRoute()];
}

function runnerConfiguration(lesson = state.lesson) {
  return {
    lessonDirectory: lesson.id.includes("/") ? lesson.id.slice(0, lesson.id.lastIndexOf("/")) : "introduction",
    files: filesForLesson(lesson),
    modelBaseUrl: selectedModelBase(),
    modelCandidates: state.verifiedModel
      ? [state.verifiedModel, ...MODEL_PROBE_CANDIDATES.filter(model => model !== state.verifiedModel)]
      : [...MODEL_PROBE_CANDIDATES],
  };
}

function modelHeaders(key) {
  return {
    Accept: "application/json",
    Authorization: `Bearer ${key}`,
    "Content-Type": "application/json",
    "X-BILLING-INVOKE-ORIGIN": BILLING_INVOKE_ORIGIN,
  };
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function safeUrl(raw, base) {
  try {
    const url = new URL(raw, base);
    if (!["http:", "https:"].includes(url.protocol)) return "";
    const localAsset = SOURCE_ASSET_REPLACEMENTS.get(url.href);
    if (localAsset) return localAsset;
    if (url.hostname === "build.nvidia.com" && !url.searchParams.has("ncid")) {
      url.searchParams.set("ncid", "ref-dli-146986");
    }
    return url.href;
  } catch {
    return "";
  }
}

function sanitizeHtml(html, baseUrl) {
  const template = document.createElement("template");
  template.innerHTML = html;
  template.content.querySelectorAll("script,style,iframe,object,embed,link,meta,base,form,input,button,textarea,select").forEach(node => node.remove());
  template.content.querySelectorAll("*").forEach(node => {
    for (const attribute of [...node.attributes]) {
      const name = attribute.name.toLowerCase();
      const value = attribute.value.trim();
      if (name.startsWith("on") || ["srcdoc", "srcset", "style", "color", "bgcolor"].includes(name)) {
        node.removeAttribute(attribute.name);
      }
      if (["href", "src"].includes(name) || name.endsWith(":href")) {
        const safe = safeUrl(value, baseUrl);
        if (safe) node.setAttribute(name, safe); else node.removeAttribute(name);
      }
    }
    if (node.tagName === "A") {
      node.target = "_blank";
      node.rel = "noopener noreferrer";
    }
  });
  return template.content;
}

async function sha256(value) {
  const bytes = new TextEncoder().encode(value);
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return [...digest].map(byte => byte.toString(16).padStart(2, "0")).join("");
}

function mermaidImageUrl(source, theme = currentTheme()) {
  const bytes = new TextEncoder().encode(source);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  const encoded = btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
  const background = theme === "dark" ? "181b20" : "ffffff";
  return `https://mermaid.ink/img/${encoded}?type=png&bgColor=${background}`;
}

function decorateMarkdown(root) {
  const firstParagraph = root.querySelector(":scope > p");
  if (firstParagraph) firstParagraph.classList.add("lesson-lead");
  const used = new Set();
  root.querySelectorAll("h1,h2,h3,h4").forEach((heading, index) => {
    const base = heading.textContent.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || `section-${index + 1}`;
    let id = base;
    for (let suffix = 2; used.has(id); suffix += 1) id = `${base}-${suffix}`;
    used.add(id);
    heading.id = id;
    const anchor = document.createElement("a");
    anchor.className = "heading-anchor";
    anchor.href = `#${id}`;
    anchor.textContent = "#";
    anchor.setAttribute("aria-label", `Link to ${heading.textContent}`);
    heading.append(anchor);
  });
  root.querySelectorAll("pre > code.language-mermaid").forEach(code => {
    const source = code.textContent.trim();
    const figure = document.createElement("figure");
    figure.className = "mermaid-diagram";
    figure.dataset.mermaidSource = source;
    const image = document.createElement("img");
    image.alt = "Diagram described by this lesson";
    image.src = mermaidImageUrl(source);
    image.addEventListener("error", () => figure.classList.add("render-failed"), { once: true });
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = "Diagram source";
    const pre = document.createElement("pre");
    pre.textContent = source;
    details.append(summary, pre);
    figure.append(image, details);
    code.parentElement.replaceWith(figure);
  });
  root.querySelectorAll("table").forEach(table => {
    if (table.parentElement?.classList.contains("table-scroll")) return;
    const wrapper = document.createElement("div");
    wrapper.className = "table-scroll";
    table.replaceWith(wrapper);
    wrapper.append(table);
  });
}

function markdownFragment(raw, baseUrl) {
  const wrapper = document.createElement("div");
  wrapper.append(sanitizeHtml(marked.parse(raw, { gfm: true }), baseUrl));
  decorateMarkdown(wrapper);
  const fragment = document.createDocumentFragment();
  fragment.append(...wrapper.childNodes);
  return fragment;
}

function lessonHref(lesson) {
  const url = new URL(location.href);
  url.searchParams.set("lesson", lesson.id);
  url.hash = "";
  return url.href;
}

function progress() {
  try { return JSON.parse(sessionStorage.getItem("cfx11-progress") || "{}"); } catch { return {}; }
}

function updateProgress(lessonId, cellId) {
  const record = progress();
  record[lessonId] ||= [];
  if (!record[lessonId].includes(cellId)) record[lessonId].push(cellId);
  sessionStorage.setItem("cfx11-progress", JSON.stringify(record));
  renderProgress();
}

function renderProgress() {
  if (!state.manifest || !state.lesson) return;
  const record = progress();
  const total = state.manifest.totals.code_cells;
  const complete = Object.values(record).reduce((count, cells) => count + cells.length, 0);
  const lessonTotal = state.lesson.cells.filter(cell => cell.type === "code").length;
  const lessonComplete = (record[state.lesson.id] || []).length;
  elements["progress-value"].max = Math.max(total, 1);
  elements["progress-value"].value = complete;
  elements["progress-label"].textContent = `${complete} of ${total} code cells run. This lesson: ${lessonComplete} of ${lessonTotal}.`;
}

function renderNavigation() {
  const current = state.lesson?.id;
  const groups = new Map();
  for (const lesson of state.manifest.lessons) {
    if (!groups.has(lesson.unit)) groups.set(lesson.unit, []);
    groups.get(lesson.unit).push(lesson);
  }
  elements["course-nav"].replaceChildren();
  for (const [unit, lessons] of groups) {
    const section = document.createElement("section");
    const heading = document.createElement("h2");
    heading.textContent = unit.replace(/^\d+-/, "").replaceAll("-", " ");
    section.append(heading);
    for (const lesson of lessons) {
      const link = document.createElement("a");
      link.href = lessonHref(lesson);
      link.textContent = lesson.title;
      link.dataset.lessonId = lesson.id;
      if (lesson.id === current) link.setAttribute("aria-current", "page");
      section.append(link);
    }
    elements["course-nav"].append(section);
  }
}

function markerHtml(raw) {
  return raw.replace(/<!-- dli-course-cell (\{[^\n]+\}) -->/g, (_, json) => {
    const record = JSON.parse(json);
    return record.type === "code"
      ? `\n<div class="xblock-marker" data-cell-id="${escapeHtml(record.id)}" data-cell-index="${record.index}"></div>\n\n`
      : "\n";
  }).replace(/<!-- \/dli-course-cell -->/g, "\n");
}

function renderDisplay(record) {
  const type = record.type || "text/plain";
  if (type === "application/x-course-chat+json") return renderChatWidget(record.data);
  if (type === "image/svg+xml") {
    const figure = document.createElement("figure");
    figure.className = "graph-output";
    figure.append(sanitizeHtml(record.data, location.href));
    return figure;
  }
  if (type === "image/png" || type === "image/jpeg") {
    const figure = document.createElement("figure");
    figure.className = "graph-output raster-output";
    const image = document.createElement("img");
    image.alt = "Generated computational graph";
    image.src = `data:${type};base64,${record.data}`;
    figure.append(image);
    return figure;
  }
  if (type === "application/json" || type === "text/x-code") {
    const pre = document.createElement("pre");
    pre.className = "formatted-output";
    const code = document.createElement("code");
    code.className = `language-${record.language || (type === "application/json" ? "json" : "python")}`;
    code.textContent = record.data;
    pre.append(code);
    globalThis.hljs?.highlightElement(code);
    return pre;
  }
  if (type === "text/markdown") {
    const div = document.createElement("div");
    div.className = "rich-output";
    div.append(markdownFragment(record.data, location.href));
    return div;
  }
  if (type === "text/html") {
    const div = document.createElement("div");
    div.className = "rich-output";
    div.append(sanitizeHtml(record.data, location.href));
    return div;
  }
  const pre = document.createElement("pre");
  pre.textContent = record.data;
  return pre;
}

function renderChatWidget(raw) {
  const payload = JSON.parse(raw);
  if (!/^chat-[1-9][0-9]*$/.test(payload.chat_id || "")) throw new Error("Chat widget identifier is invalid.");
  const section = document.createElement("section");
  section.className = "course-chat";
  const heading = document.createElement("h3");
  heading.textContent = "Live browser chat";
  const history = document.createElement("div");
  history.className = "chat-history";
  history.setAttribute("aria-live", "polite");
  const form = document.createElement("form");
  const input = document.createElement("textarea");
  input.rows = 2;
  input.required = true;
  input.placeholder = "Write a message";
  input.setAttribute("aria-label", "Chat message");
  const send = document.createElement("button");
  send.type = "submit";
  send.textContent = "Send";
  form.append(input, send);

  function addMessage(role, value, pending = false) {
    const article = document.createElement("article");
    article.className = `chat-message ${role}`;
    if (pending) article.dataset.pending = "true";
    const label = document.createElement("strong");
    label.textContent = role === "user" ? "You" : "Assistant";
    const body = document.createElement("div");
    body.textContent = value;
    article.append(label, body);
    history.append(article);
    article.scrollIntoView({ block: "nearest" });
    return body;
  }

  form.addEventListener("submit", async event => {
    event.preventDefault();
    const prompt = input.value.trim();
    if (!prompt) return;
    addMessage("user", prompt);
    input.value = "";
    const response = addMessage("assistant", "", true);
    send.disabled = true;
    state.activeChat = response;
    try {
      const reply = await state.runner.chat(payload.chat_id, prompt, elements["api-key"].value.trim(), { label: "Course chat response" });
      response.parentElement.dataset.pending = "false";
      response.textContent = reply.ok ? String(reply.value ?? reply.display ?? "") : reply.stderr;
    } catch (error) {
      response.parentElement.dataset.pending = "false";
      response.textContent = error.message;
    } finally {
      state.activeChat = null;
      send.disabled = false;
      input.focus();
    }
  });
  section.append(heading, history, form);
  return section;
}

function appendChannel(output, label, value, className = "") {
  if (!value) return;
  recordRuntimeEvent(className || label.toLowerCase(), value);
  const row = document.createElement("div");
  row.className = `output-channel ${className}`;
  const heading = document.createElement("strong");
  heading.textContent = label;
  const pre = document.createElement("pre");
  pre.textContent = value;
  row.append(heading, pre);
  output.append(row);
}

function recordRuntimeEvent(channel, value) {
  const text = String(value || "").trim()
    .replace(/nvapi-[A-Za-z0-9_-]{6,}/g, "nvapi-[hidden]")
    .replace(/(bearer\s+)[A-Za-z0-9._-]{8,}/gi, "$1[hidden]");
  if (!text) return;
  const now = Date.now();
  const previous = state.streams.at(-1);
  if (channel === "model" && previous?.channel === channel && now - previous.timestamp < 2000) {
    previous.text = (previous.text + text).slice(-2400);
    previous.timestamp = now;
    previous.at = new Date(now).toLocaleTimeString();
  } else {
    state.streams.push({ channel, text: text.slice(0, 2400), timestamp: now, at: new Date(now).toLocaleTimeString() });
  }
  if (state.streams.length > 160) state.streams.splice(0, state.streams.length - 160);
  renderRuntimeStreams();
}

function renderRuntimeStreams() {
  if (!elements["runtime-streams"]) return;
  if (!state.streams.length) {
    const empty = document.createElement("li");
    empty.textContent = "No runtime events yet.";
    elements["runtime-streams"].replaceChildren(empty);
    return;
  }
  elements["runtime-streams"].replaceChildren(...state.streams.slice(-60).reverse().map(event => {
    const item = document.createElement("li");
    item.dataset.channel = event.channel;
    const meta = document.createElement("span");
    meta.textContent = `${event.at} · ${event.channel}`;
    const pre = document.createElement("pre");
    pre.textContent = event.text;
    item.append(meta, pre);
    return item;
  }));
}

function appendError(output, stderr) {
  if (!stderr) return;
  const actionable = String(stderr).split("\n").find(line => line.includes("The browser could not reach"));
  if (!actionable) {
    appendChannel(output, "stderr", stderr, "stderr");
    return;
  }
  appendChannel(output, "Connection", actionable.replace(/^.*?(The browser could not reach)/, "$1"), "stderr");
  const details = document.createElement("details");
  const summary = document.createElement("summary");
  summary.textContent = "Full Python traceback";
  const pre = document.createElement("pre");
  pre.textContent = stderr;
  details.append(summary, pre);
  output.append(details);
}

function renderReply(block, reply) {
  if (reply.batch_mode === "gil-locked-threads") {
    elements["runtime-status"].textContent = "Python ready · batches use GIL-locked threads";
  } else if (reply.batch_mode === "ordered-browser-fallback") {
    elements["runtime-status"].textContent = "Python ready · batches run in order in this browser";
  }
  block.output.replaceChildren();
  block.editor.clearGutter?.("course-errors");
  block.editor.eachLine?.(line => block.editor.removeLineClass(line, "background", "course-error-line"));
  appendChannel(block.output, "stdout", reply.stdout, "stdout");
  for (const display of reply.displays || []) {
    const row = document.createElement("div");
    row.className = "output-channel display";
    row.append(renderDisplay(display));
    block.output.append(row);
  }
  if (reply.has_value) {
    const row = document.createElement("div");
    row.className = "output-channel result";
    const label = document.createElement("strong");
    label.textContent = `Out [${reply.execution_count}]`;
    row.append(label, renderDisplay({ type: reply.display_type, data: reply.display, language: reply.display_language }));
    block.output.append(row);
  }
  appendError(block.output, reply.stderr);
  if (reply.error_line) {
    const line = Math.max(0, reply.error_line - 1);
    block.editor.addLineClass?.(line, "background", "course-error-line");
    block.editor.setGutterMarker?.(line, "course-errors", Object.assign(document.createElement("span"), { textContent: "●" }));
    block.editor.scrollIntoView?.({ line, ch: 0 }, 80);
  }
  if (reply.trace?.length) {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = `Execution trace (${reply.trace.length})`;
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(reply.trace, null, 2);
    details.append(summary, pre);
    block.output.append(details);
  }
  if (reply.ok && !block.output.childElementCount) {
    const note = document.createElement("p");
    note.className = "wb-cell-result-note";
    note.textContent = "Completed without output.";
    block.output.append(note);
  }
  if (reply.kernel) renderKernel(reply.kernel);
}

function setArtifactState(block, stateName) {
  const labels = {
    ready: "Ready",
    queued: "Queued",
    running: "Running",
    complete: "Complete",
    failed: "Needs attention",
  };
  block.artifactState.dataset.state = stateName;
  block.artifactState.textContent = labels[stateName] || stateName;
  const progressCopy = block.output.querySelector(".wb-cell-progress-copy");
  if (progressCopy) progressCopy.textContent = stateName === "queued" ? "Waiting for Python…" : "Running this cell…";
}

function showArtifactProgress(block) {
  const progress = document.createElement("div");
  progress.className = "wb-cell-progress";
  progress.setAttribute("role", "status");
  progress.setAttribute("aria-live", "polite");
  progress.setAttribute("aria-atomic", "true");
  const mark = document.createElement("span");
  mark.className = "wb-cell-progress-mark";
  mark.setAttribute("aria-hidden", "true");
  const copy = document.createElement("span");
  copy.className = "wb-cell-progress-copy";
  const track = document.createElement("span");
  track.className = "wb-cell-progress-track";
  track.setAttribute("aria-hidden", "true");
  progress.append(mark, copy, track);
  const stream = document.createElement("pre");
  stream.className = "model-stream";
  block.output.replaceChildren(progress, stream);
}

function renderKernel(kernel) {
  state.latestKernel = kernel;
  const shortId = String(kernel.session_id || "").split("-")[0] || "starting";
  elements["kernel-status"].textContent = `#${shortId} · ${kernel.execution_count || 0} executions`;
  elements["kernel-started"].textContent = kernel.started_at ? new Date(kernel.started_at).toLocaleTimeString() : "Not started";
  renderEnvironment(kernel.environment || {});
  const allRows = Array.isArray(kernel.variables) ? kernel.variables : [];
  const rows = state.variableView === "focused" ? allRows.filter(row => row.focused) : allRows;
  if (!rows.length) {
    elements["kernel-variables"].innerHTML = state.variableView === "focused"
      ? "<p>No named variable was read or changed by the last cell. Choose <strong>All variables</strong> to inspect the complete namespace.</p>"
      : "<p>No public variables are in memory yet.</p>";
    return;
  }
  const table = document.createElement("table");
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const label of ["Name", "Why shown", "Type", "Current value"]) {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = label;
    headRow.append(cell);
  }
  head.append(headRow);
  const body = document.createElement("tbody");
  for (const row of rows) {
    const tr = document.createElement("tr");
    for (const value of [row.name, row.focus_reason || "namespace", row.type, row.preview]) {
      const td = document.createElement("td");
      const code = document.createElement("code");
      code.textContent = String(value ?? "");
      td.append(code);
      tr.append(td);
    }
    body.append(tr);
  }
  table.append(head, body);
  elements["kernel-variables"].replaceChildren(table);
}

function renderEnvironment(environment = state.latestKernel?.environment || {}) {
  const facts = [
    ["Python", environment.python || "Starts on demand"],
    ["Pyodide", environment.pyodide || "Starts on demand"],
    ["Scheduler", environment.batch_mode || "Ordered execution queue"],
    ["Working directory", environment.cwd || "Created with the session"],
    ["Lesson", state.lesson?.title || "Loading"],
    ["Page origin", location.origin === "null" ? "Local file (model calls unavailable)" : location.origin],
    ["Model route", selectedModelBase()],
  ];
  elements["runtime-environment"].replaceChildren(...facts.map(([label, value]) => {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    const detail = document.createElement("dd");
    term.textContent = label;
    detail.textContent = value;
    row.append(term, detail);
    return row;
  }));
}

function resetKernelView() {
  state.latestKernel = null;
  elements["kernel-status"].textContent = "Not started";
  elements["kernel-started"].textContent = "Not started";
  elements["kernel-variables"].innerHTML = "<p>Run a cell to see the variables it actually reads or changes.</p>";
  renderEnvironment();
}

function restartRuntime() {
  const operationId = state.operations.begin("Restart Python", { kind: "runtime", detail: "Cancelling queued and running work" });
  state.runner.reset(runnerConfiguration());
  resetKernelView();
  for (const block of state.blocks) {
    block.article.dataset.state = "ready";
    block.article.dataset.outputState = "hidden";
    block.status.textContent = "Ready";
    block.output.replaceChildren();
    block.artifact.hidden = true;
    setArtifactState(block, "ready");
  }
  elements["runtime-status"].textContent = "Python restarted · variables cleared";
  state.operations.settle(operationId, "succeeded", "Namespace cleared and worker replaced");
}

async function runBlock(block) {
  block.article.dataset.state = "queued";
  block.article.setAttribute("aria-busy", "true");
  block.status.textContent = "Queued";
  block.artifact.hidden = false;
  block.article.dataset.outputState = "queued";
  showArtifactProgress(block);
  setArtifactState(block, "queued");
  try {
    const execution = state.runner.run(block.editor.getValue(), elements["api-key"].value.trim(), {
      label: `${state.lesson?.title || "Lesson"} · cell ${block.article.dataset.cellId.split(":").at(-1)}`,
    });
    state.requestBlocks.set(execution.requestId, block);
    const reply = await execution;
    renderReply(block, reply);
    block.article.dataset.state = reply.ok ? "passed" : "failed";
    block.article.dataset.outputState = reply.ok ? "complete" : "failed";
    setArtifactState(block, reply.ok ? "complete" : "failed");
    block.status.textContent = reply.ok ? `Ran as In [${reply.execution_count}]` : "Failed";
    if (reply.ok) updateProgress(state.lesson.id, block.id);
    return reply.ok;
  } catch (error) {
    renderReply(block, { stderr: error.message, displays: [] });
    block.article.dataset.state = "failed";
    block.article.dataset.outputState = "failed";
    setArtifactState(block, "failed");
    block.status.textContent = "Failed";
    return false;
  } finally {
    block.article.setAttribute("aria-busy", "false");
    for (const [requestId, candidate] of state.requestBlocks) {
      if (candidate === block) state.requestBlocks.delete(requestId);
    }
  }
}

function togglePythonComments(editor) {
  editor.operation(() => {
    for (const range of editor.listSelections()) {
      const first = Math.min(range.anchor.line, range.head.line);
      const last = Math.max(range.anchor.line, range.head.line);
      const lines = Array.from({ length: last - first + 1 }, (_, offset) => editor.getLine(first + offset));
      const uncomment = lines.filter(line => line.trim()).every(line => /^\s*#(?:\s|$)/.test(line));
      lines.forEach((line, offset) => {
        if (!line.trim()) return;
        const lineNumber = first + offset;
        const indent = line.match(/^\s*/)[0];
        if (uncomment) {
          const prefix = line.match(/^\s*# ?/)[0];
          editor.replaceRange(indent, { line: lineNumber, ch: 0 }, { line: lineNumber, ch: prefix.length });
        } else {
          editor.replaceRange(`${indent}# `, { line: lineNumber, ch: 0 }, { line: lineNumber, ch: indent.length });
        }
      });
    }
  });
}

async function copyText(value) {
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(value);
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.append(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

function buildXBlocks() {
  state.blocks = [];
  for (const marker of elements["lesson-body"].querySelectorAll(".xblock-marker")) {
    const markerContainer = marker.parentElement?.tagName === "P" && marker.parentElement.children.length === 1
      ? marker.parentElement
      : marker;
    let sourceNode = markerContainer.nextElementSibling;
    if (!sourceNode?.matches("pre")) {
      sourceNode = [...elements["lesson-body"].querySelectorAll("pre")].find(node =>
        Boolean(marker.compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING));
    }
    if (!sourceNode?.matches("pre")) throw new Error(`Code cell ${marker.dataset.cellId} did not render a source block.`);
    const source = sourceNode.textContent.replace(/\n$/, "");
    const article = document.createElement("article");
    article.className = "xblock wb-cell";
    article.dataset.cellId = marker.dataset.cellId;
    article.dataset.state = "ready";
    article.dataset.outputState = "hidden";
    article.setAttribute("aria-busy", "false");
    const header = document.createElement("header");
    const heading = document.createElement("div");
    heading.className = "wb-cell-heading";
    const prompt = document.createElement("strong");
    prompt.textContent = `In [ ] · cell ${Number(marker.dataset.cellIndex) + 1}`;
    const priorHeading = [...elements["lesson-body"].querySelectorAll("h2, h3")]
      .filter(candidate => Boolean(candidate.compareDocumentPosition(markerContainer) & Node.DOCUMENT_POSITION_FOLLOWING))
      .at(-1);
    const context = document.createElement("span");
    context.textContent = priorHeading?.textContent.replace(/#$/, "").trim() || state.lesson?.title || "Python exercise";
    heading.append(prompt, context);
    const status = document.createElement("span");
    status.className = "wb-cell-state";
    status.textContent = "Ready";
    const run = document.createElement("button");
    run.type = "button";
    run.textContent = "Run";
    const settings = document.createElement("details");
    settings.className = "wb-cell-settings";
    const settingsSummary = document.createElement("summary");
    settingsSummary.textContent = "Cell settings";
    settingsSummary.setAttribute("aria-label", `Cell ${Number(marker.dataset.cellIndex) + 1} settings`);
    const settingsPanel = document.createElement("div");
    settingsPanel.className = "wb-cell-settings-panel";
    const makeSelect = (labelText, name, choices) => {
      const label = document.createElement("label");
      label.textContent = labelText;
      const select = document.createElement("select");
      select.name = name;
      select.setAttribute("aria-label", labelText);
      for (const [value, text] of choices) select.add(new Option(text, value));
      label.append(select);
      settingsPanel.append(label);
      return select;
    };
    const layout = makeSelect("Output position", "output-position", [["beside", "Beside code"], ["below", "Below code"]]);
    const editorHeight = makeSelect("Editor height", "editor-height", [["match", "Match result"], ["content", "Fit code"], ["tall", "Tall editor"]]);
    const makeCheck = (labelText, name) => {
      const label = document.createElement("label");
      label.className = "wb-cell-setting-check";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.name = name;
      input.setAttribute("aria-label", labelText);
      label.append(input, document.createTextNode(labelText));
      settingsPanel.append(label);
      return input;
    };
    const wrap = makeCheck("Wrap long lines", "wrap-lines");
    const lineNumbers = makeCheck("Show line numbers", "line-numbers");
    const settingsActions = document.createElement("div");
    settingsActions.className = "wb-cell-settings-actions";
    const copy = document.createElement("button");
    copy.type = "button";
    copy.textContent = "Copy code";
    const restore = document.createElement("button");
    restore.type = "button";
    restore.textContent = "Restore source";
    const clear = document.createElement("button");
    clear.type = "button";
    clear.textContent = "Clear output";
    settingsActions.append(copy, restore, clear);
    const syntaxHelp = document.createElement("p");
    syntaxHelp.className = "wb-cell-settings-help";
    syntaxHelp.innerHTML = "<strong>Notebook controls</strong><br>Shift/Ctrl/⌘+Enter runs · Ctrl/⌘+/ comments · Tab/Shift+Tab indents<br><code>value?</code> / <code>value??</code> inspect · <code>!command</code> uses the browser shell · <code>%magic</code> lists commands";
    settingsPanel.append(settingsActions, syntaxHelp);
    settings.append(settingsSummary, settingsPanel);
    header.append(heading, status, settings, run);

    const workspace = document.createElement("div");
    workspace.className = "wb-cell-workspace";
    const sourcePane = document.createElement("section");
    sourcePane.className = "wb-cell-source";
    sourcePane.setAttribute("aria-label", "Editable Python source");
    const sourceLabel = document.createElement("div");
    sourceLabel.className = "wb-cell-pane-label";
    const sourceCopy = document.createElement("span");
    sourceCopy.textContent = "Editable Python · click to type · Shift+Enter runs";
    const sourcePosition = document.createElement("span");
    sourcePosition.className = "wb-cell-editor-position";
    sourcePosition.textContent = "Ln 1, Col 1";
    sourceLabel.append(sourceCopy, sourcePosition);
    const textarea = document.createElement("textarea");
    textarea.value = source;
    textarea.setAttribute("aria-label", `Python source for cell ${Number(marker.dataset.cellIndex) + 1}`);
    sourcePane.append(sourceLabel, textarea);

    const artifactPane = document.createElement("section");
    artifactPane.className = "wb-cell-artifact";
    artifactPane.setAttribute("aria-label", "Cell result");
    artifactPane.hidden = true;
    const artifactLabel = document.createElement("div");
    artifactLabel.className = "wb-cell-pane-label";
    const artifactTitle = document.createElement("span");
    artifactTitle.textContent = "Result and evidence";
    const artifactState = document.createElement("span");
    artifactState.className = "wb-cell-artifact-state";
    artifactState.dataset.state = "ready";
    artifactState.textContent = "Ready";
    artifactLabel.append(artifactTitle, artifactState);
    const output = document.createElement("div");
    output.className = "cell-output";
    artifactPane.append(artifactLabel, output);
    workspace.append(sourcePane, artifactPane);

    const tools = document.createElement("details");
    tools.className = "wb-cell-tools";
    const toolsSummary = document.createElement("summary");
    toolsSummary.textContent = "Inspect the runtime behind this cell";
    const toolsBody = document.createElement("div");
    toolsBody.className = "wb-cell-tools-body";
    for (const [label, panelName] of [
      ["Cell activity", "activity"],
      ["Variables", "variables"],
      ["Output streams", "streams"],
      ["Environment", "environment"],
    ]) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.addEventListener("click", () => openRuntimePanel(panelName));
      toolsBody.append(button);
    }
    tools.append(toolsSummary, toolsBody);
    article.append(header, workspace, tools);
    markerContainer.replaceWith(article);
    sourceNode.remove();
    const editor = globalThis.CodeMirror.fromTextArea(textarea, {
      mode: "python", lineNumbers: true, indentUnit: 4, tabSize: 4,
      lineWrapping: true, readOnly: false, viewportMargin: Infinity,
      gutters: ["CodeMirror-linenumbers", "course-errors"],
      extraKeys: {
        "Shift-Enter": () => run.click(), "Ctrl-Enter": () => run.click(), "Cmd-Enter": () => run.click(),
        "Ctrl-/": togglePythonComments, "Cmd-/": togglePythonComments,
        "Tab": candidate => candidate.somethingSelected() ? candidate.execCommand("indentMore") : candidate.replaceSelection("    ", "end"),
        "Shift-Tab": candidate => candidate.execCommand("indentLess"),
      },
    });
    editor.setSize("100%", "auto");
    const block = { id: marker.dataset.cellId, article, status, artifact: artifactPane, artifactState, output, editor, originalSource: source };
    const settingsKey = `cfx11-cell-settings:${marker.dataset.cellId}`;
    const legacyLayout = sessionStorage.getItem(`cfx11-output-layout:${marker.dataset.cellId}`);
    let saved = {};
    try { saved = JSON.parse(sessionStorage.getItem(settingsKey) || "{}"); } catch { saved = {}; }
    const cellSettings = {
      output: ["beside", "below"].includes(saved.output) ? saved.output : legacyLayout === "beside" ? "beside" : "below",
      height: ["match", "content", "tall"].includes(saved.height) ? saved.height : "match",
      wrap: saved.wrap !== false,
      lineNumbers: saved.lineNumbers !== false,
    };
    const applySettings = (persist = true) => {
      article.dataset.outputLayout = cellSettings.output;
      article.dataset.editorHeight = cellSettings.height;
      layout.value = cellSettings.output;
      editorHeight.value = cellSettings.height;
      wrap.checked = cellSettings.wrap;
      lineNumbers.checked = cellSettings.lineNumbers;
      editor.setOption("lineWrapping", cellSettings.wrap);
      editor.setOption("lineNumbers", cellSettings.lineNumbers);
      editor.setSize("100%", cellSettings.height === "tall" ? "24rem" : "auto");
      editor.refresh();
      if (persist) sessionStorage.setItem(settingsKey, JSON.stringify(cellSettings));
    };
    applySettings(false);
    run.addEventListener("click", () => runBlock(block));
    restore.addEventListener("click", () => { editor.setValue(source); editor.focus(); });
    copy.addEventListener("click", async () => {
      await copyText(editor.getValue());
      copy.textContent = "Copied";
      setTimeout(() => { copy.textContent = "Copy code"; }, 1200);
    });
    clear.addEventListener("click", () => {
      output.replaceChildren();
      artifactPane.hidden = true;
      article.dataset.state = "ready";
      article.dataset.outputState = "hidden";
      status.textContent = "Ready";
      setArtifactState(block, "ready");
    });
    layout.addEventListener("change", () => { cellSettings.output = layout.value; applySettings(); });
    editorHeight.addEventListener("change", () => { cellSettings.height = editorHeight.value; applySettings(); });
    wrap.addEventListener("change", () => { cellSettings.wrap = wrap.checked; applySettings(); });
    lineNumbers.addEventListener("change", () => { cellSettings.lineNumbers = lineNumbers.checked; applySettings(); });
    editor.on("cursorActivity", candidate => {
      const cursor = candidate.getCursor();
      sourcePosition.textContent = `Ln ${cursor.line + 1}, Col ${cursor.ch + 1}`;
    });
    editor.on("change", candidate => {
      sourcePane.dataset.edited = String(candidate.getValue() !== source);
    });
    state.blocks.push(block);
  }
  elements["lesson-body"].querySelectorAll("pre code").forEach(code => globalThis.hljs?.highlightElement(code));
}

function filesForLesson(lesson) {
  const directory = lesson.id.includes("/") ? lesson.id.slice(0, lesson.id.lastIndexOf("/")) : "";
  const prefix = directory ? `content/${directory}/` : "content/";
  return state.manifest.supporting_files
    .filter(file => file.path.startsWith(prefix))
    .map(file => ({ path: file.path.slice(prefix.length), url: new URL(file.path, location.href).href }));
}

async function loadLesson(lesson) {
  state.lesson = lesson;
  renderNavigation();
  const markdownUrl = new URL(lesson.markdown_path, location.href);
  const bundled = state.contentBundle?.lessons?.[lesson.markdown_path];
  if (!bundled) throw new Error(`The reviewed content bundle does not contain ${lesson.markdown_path}.`);
  const raw = bundled.markdown;
  const digest = await sha256(raw);
  if (digest !== bundled.sha256 || digest !== lesson.markdown_sha256) {
    throw new Error(`The reviewed Markdown digest does not match for ${lesson.markdown_path}.`);
  }
  state.rawMarkdown = raw;
  elements["lesson-title"].textContent = lesson.title;
  elements["lesson-meta"].textContent = `${lesson.unit.replaceAll("-", " ")} · ${lesson.cells.length} source cells · imported verbatim`;
  elements["lesson-body"].replaceChildren(markdownFragment(markerHtml(raw), markdownUrl));

  const bySource = new Map(state.manifest.lessons.map(item => [item.source_path.replace(/^task1\/dli\//, ""), item]));
  elements["lesson-body"].querySelectorAll("a[href]").forEach(link => {
    const decoded = decodeURIComponent(new URL(link.href).pathname);
    const sourceLink = [...bySource.keys()].find(path => decoded.endsWith(path));
    if (sourceLink) {
      link.href = lessonHref(bySource.get(sourceLink));
      link.target = "_self";
      link.removeAttribute("rel");
    } else if (decoded.endsWith(".py")) {
      const relative = new URL(link.href).pathname.split("/content/").pop();
      link.href = `https://gitlab.com/nvidia/dli/content/c-fx-11-v1/-/blob/main/task1/dli/${relative}`;
    }
  });
  buildXBlocks();
  state.runner.configure(runnerConfiguration(lesson));
  renderEnvironment();
  elements["runtime-status"].textContent = state.latestKernel ? "Python session kept across lessons" : "Python loads when you run a cell";
  const index = state.manifest.lessons.indexOf(lesson);
  const previous = state.manifest.lessons[index - 1];
  const next = state.manifest.lessons[index + 1];
  elements["previous-lesson"].hidden = !previous;
  elements["next-lesson"].hidden = !next;
  if (previous) { elements["previous-lesson"].href = lessonHref(previous); elements["previous-lesson"].textContent = `Previous · ${previous.title}`; }
  if (next) { elements["next-lesson"].href = lessonHref(next); elements["next-lesson"].textContent = `Next · ${next.title}`; }
  renderProgress();
  window.scrollTo({ top: 0 });
}

function openLesson(lesson, { replace = false } = {}) {
  const url = lessonHref(lesson);
  if (replace) history.replaceState({ lesson: lesson.id }, "", url);
  else history.pushState({ lesson: lesson.id }, "", url);
  return loadLesson(lesson);
}

async function initialize(signal) {
  const [manifestResponse, contentResponse] = await Promise.all([
    fetch(new URL("course.json", location.href), { credentials: "omit", signal }),
    fetch(new URL("content-bundle.json", location.href), { credentials: "omit", signal }),
  ]);
  if (!manifestResponse.ok) throw new Error(`Could not load the course manifest (${manifestResponse.status}).`);
  if (!contentResponse.ok) throw new Error(`Could not load the reviewed lesson bundle (${contentResponse.status}).`);
  state.manifest = await manifestResponse.json();
  state.contentBundle = await contentResponse.json();
  if (state.contentBundle.schema !== "dli-markdown-delivery/1.0") throw new Error("The lesson bundle schema is not supported.");
  const expected = new Set(state.manifest.lessons.map(lesson => lesson.markdown_path));
  const bundled = new Set(Object.keys(state.contentBundle.lessons || {}));
  if (expected.size !== bundled.size || [...expected].some(path => !bundled.has(path))) {
    throw new Error("The lesson bundle does not exactly match the course manifest.");
  }
  const requested = new URL(location.href).searchParams.get("lesson");
  const lesson = state.manifest.lessons.find(item => item.id === requested) || state.manifest.lessons[0];
  await loadLesson(lesson);
}

state.runner.addEventListener("model-stream", event => {
  recordRuntimeEvent("model", event.detail.text);
  if (state.agentRequestId === event.detail.requestId) {
    const pending = elements["runtime-agent-history"].querySelector('[data-agent-pending="true"] .agent-message-body');
    if (pending) pending.textContent += event.detail.text;
    return;
  }
  if (state.activeChat) {
    state.activeChat.textContent += event.detail.text;
    return;
  }
  const stream = state.requestBlocks.get(event.detail.requestId)?.output.querySelector(".model-stream");
  if (stream) stream.textContent += event.detail.text;
});

state.runner.addEventListener("job-start", event => {
  const block = state.requestBlocks.get(event.detail.id);
  if (!block) return;
  block.article.dataset.state = "running";
  block.article.setAttribute("aria-busy", "true");
  block.article.dataset.outputState = "running";
  block.status.textContent = "Running";
  setArtifactState(block, "running");
});

state.runner.addEventListener("queue-change", event => {
  const { active, activeLabel, queued } = event.detail;
  elements["queue-status"].textContent = active
    ? `${queued} waiting · running: ${activeLabel || "Python job"}`
    : queued ? `${queued} waiting` : "Queue empty";
  const summary = active ? `${queued} waiting; running ${activeLabel || "Python job"}` : queued ? `${queued} waiting` : "Queue empty";
  if (summary !== state.lastQueueStatus) {
    state.lastQueueStatus = summary;
    recordRuntimeEvent("queue", summary);
  }
});

state.runner.addEventListener("job-state", event => state.operations.ingest(event.detail));
state.runner.addEventListener("operation-note", event => {
  state.operations.update(`python-${event.detail.requestId}`, event.detail.text);
  recordRuntimeEvent("connection", event.detail.text);
});

state.runner.addEventListener("input-request", event => {
  recordRuntimeEvent("input", event.detail.prompt || "Python requested input");
  const block = state.requestBlocks.get(event.detail.requestId);
  if (!block) {
    event.detail.respond("");
    return;
  }
  const form = document.createElement("form");
  form.className = "python-input";
  const label = document.createElement("label");
  label.textContent = event.detail.prompt || "Python input";
  const input = document.createElement("input");
  input.type = "text";
  input.required = true;
  input.autocomplete = "off";
  const submit = document.createElement("button");
  submit.type = "submit";
  submit.textContent = "Continue";
  form.append(label, input, submit);
  form.addEventListener("submit", submitEvent => {
    submitEvent.preventDefault();
    input.disabled = true;
    submit.disabled = true;
    event.detail.respond(input.value);
  }, { once: true });
  block.output.append(form);
  input.focus();
});

function renderOperations(records = state.operations.snapshot()) {
  if (!elements["runtime-operations"]) return;
  const active = records.filter(record => ["queued", "running"].includes(record.state));
  const latestFailure = records.find(record => ["failed", "timed-out"].includes(record.state));
  const badge = active.length ? `${active.length} active` : latestFailure ? "Needs attention" : "Idle";
  elements["operation-badge"].textContent = badge;
  elements["operation-badge"].dataset.state = active.length ? "running" : latestFailure ? "failed" : "idle";
  elements["operation-summary"].textContent = active.length
    ? `${active.length} operation${active.length === 1 ? " is" : "s are"} visible and still active.`
    : latestFailure ? `No work is running. Latest issue: ${latestFailure.label}.` : "No work is running.";
  if (!records.length) {
    const empty = document.createElement("li");
    empty.textContent = "No operations yet.";
    elements["runtime-operations"].replaceChildren(empty);
    return;
  }
  elements["runtime-operations"].replaceChildren(...records.map(record => {
    const item = document.createElement("li");
    item.dataset.state = record.state;
    const heading = document.createElement("div");
    const label = document.createElement("strong");
    label.textContent = record.label;
    const status = document.createElement("span");
    status.textContent = record.state.replace("-", " ");
    heading.append(label, status);
    const detail = document.createElement("p");
    const elapsedTo = record.finishedAt || Date.now();
    detail.textContent = `${record.detail || "No additional detail"} · ${formatDuration(elapsedTo - (record.queuedAt || elapsedTo))}`;
    item.append(heading, detail);
    return item;
  }));
}

state.operations.addEventListener("change", event => renderOperations(event.detail));
renderOperations();

function currentTheme() {
  return document.documentElement.dataset.theme
    || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  elements["theme-toggle"].textContent = theme === "dark" ? "Light mode" : "Dark mode";
  elements["theme-toggle"].setAttribute("aria-pressed", String(theme === "dark"));
  try { localStorage.setItem("cfx11-theme", theme); } catch (_) {}
  document.querySelectorAll(".mermaid-diagram").forEach(figure => {
    const image = figure.querySelector("img");
    if (image) image.src = mermaidImageUrl(figure.dataset.mermaidSource, theme);
  });
}

const runtimeWorkbench = mountRuntimeWorkbench(document.querySelector("[data-runtime-workbench]"), {
  labels: {
    session: "Session",
    activity: "Activity",
    variables: "Variables",
    streams: "Streams",
    environment: "Environment",
    agent: "Runtime guide",
  },
  onOpen(name) {
    if (name === "environment") renderEnvironment();
    if (name === "variables" && state.latestKernel) renderKernel(state.latestKernel);
  },
});

function openRuntimePanel(name) {
  runtimeWorkbench.open(name);
}

function addAgentMessage(role, text, pending = false) {
  if (elements["runtime-agent-history"].children.length === 1 && elements["runtime-agent-history"].firstElementChild?.tagName === "P") {
    elements["runtime-agent-history"].replaceChildren();
  }
  const article = document.createElement("article");
  article.className = `agent-message ${role}`;
  if (pending) article.dataset.agentPending = "true";
  const label = document.createElement("strong");
  label.textContent = role === "user" ? "You" : "Runtime guide";
  const body = document.createElement("div");
  body.className = "agent-message-body";
  body.textContent = text;
  article.append(label, body);
  elements["runtime-agent-history"].append(article);
  article.scrollIntoView({ block: "nearest" });
  return article;
}

function runtimeGuideContext() {
  const focused = (state.latestKernel?.variables || []).filter(row => row.focused)
    .map(row => `${row.name} (${row.type}; ${row.focus_reason})`).join(", ") || "none";
  const recentErrors = state.streams.filter(item => item.channel === "stderr").slice(-3).map(item => item.text).join("\n---\n") || "none";
  const lessonText = state.rawMarkdown.replace(/<!--[^]*?-->/g, "").slice(0, 6500);
  return `Lesson: ${state.lesson?.title}\nFocused variable names: ${focused}\nRecent errors:\n${recentErrors}\n\nReviewed lesson excerpt:\n${lessonText}`;
}

elements["open-settings"].addEventListener("click", () => elements["settings-dialog"].showModal());
applyTheme(currentTheme());
elements["theme-toggle"].addEventListener("click", () => applyTheme(currentTheme() === "dark" ? "light" : "dark"));
const savedModelRoute = sessionStorage.getItem(MODEL_ROUTE_STORAGE_KEY);
elements["model-route"].value = ["direct", "proxy"].includes(savedModelRoute) ? savedModelRoute : defaultModelRoute();
function applyModelRoute({ persist = false } = {}) {
  if (persist) sessionStorage.setItem(MODEL_ROUTE_STORAGE_KEY, elements["model-route"].value);
  elements["route-status"].textContent = elements["model-route"].value === "direct"
    ? "Direct NVIDIA API · selected for the registered production course origin."
    : "DLI browser relay · selected for this staging or embedding origin.";
  if (state.lesson) state.runner.configure(runnerConfiguration());
  renderEnvironment();
}
elements["model-route"].addEventListener("change", () => applyModelRoute({ persist: true }));
applyModelRoute();
elements["api-key"].value = sessionStorage.getItem("cfx11-nvidia-key") || "";
function updateConnectionSummary(status = "") {
  const hasKey = Boolean(elements["api-key"].value.trim());
  elements["connection-summary-status"].textContent = status || (hasKey ? "Key saved in this tab" : "No key saved");
  if (!hasKey) elements["connection-details"].open = true;
}
elements["api-key"].addEventListener("input", () => {
  const value = elements["api-key"].value.trim();
  if (value) sessionStorage.setItem("cfx11-nvidia-key", value); else sessionStorage.removeItem("cfx11-nvidia-key");
  elements["api-status"].textContent = value ? "The key is held in this browser tab only." : "No key is stored in this browser tab.";
  updateConnectionSummary();
});
elements["api-key"].dispatchEvent(new Event("input"));
if (elements["api-key"].value.trim()) elements["connection-details"].open = false;
elements["save-api-key"].addEventListener("click", () => {
  if (!elements["api-key"].value.trim()) {
    elements["api-status"].textContent = "Paste a key before saving the connection.";
    elements["api-key"].focus();
    return;
  }
  updateConnectionSummary();
  elements["connection-details"].open = false;
});
elements["clear-api-key"].addEventListener("click", () => {
  elements["api-key"].value = "";
  elements["api-key"].dispatchEvent(new Event("input"));
  elements["connection-details"].open = true;
  elements["api-key"].focus();
});

async function probeModelConnection(key) {
  const route = elements["model-route"]?.value || "direct";
  const baseUrl = MODEL_BASES[route] || MODEL_BASES.direct;
  return state.operations.run("Test NVIDIA model connection", async ({ signal, update }) => {
    const attempts = [];
    for (const [index, model] of MODEL_PROBE_CANDIDATES.entries()) {
      update(`Trying ${index + 1} of ${MODEL_PROBE_CANDIDATES.length}: ${model}`);
      elements["api-status"].textContent = `Checking model ${index + 1} of ${MODEL_PROBE_CANDIDATES.length}: ${model}…`;
      let response;
      try {
        response = await fetch(`${baseUrl}/chat/completions`, {
          method: "POST",
          credentials: "omit",
          signal,
          headers: modelHeaders(key, route),
          body: JSON.stringify({
            model,
            messages: [{ role: "user", content: "Reply OK." }],
            max_tokens: 1,
            stream: false,
            temperature: 0,
          }),
        });
      } catch (error) {
        if (signal.aborted) throw error;
        attempts.push(`${model}: network error`);
        recordRuntimeEvent("connection", `${model} could not be reached; trying the next bounded candidate.`);
        continue;
      }
      if (response.ok) {
        state.verifiedModel = model;
        sessionStorage.setItem("cfx11-verified-model", model);
        state.runner.configure(runnerConfiguration());
        recordRuntimeEvent("connection", `NVIDIA connection verified with ${model}.`);
        return model;
      }
      if ([401, 403].includes(response.status)) {
        throw new Error(`NVIDIA rejected this key (${response.status}). Check or replace it.`);
      }
      attempts.push(`${model}: HTTP ${response.status}`);
      recordRuntimeEvent("connection", `${model} returned HTTP ${response.status}; trying the next bounded candidate.`);
    }
    throw new Error(`No connection-test model responded. ${attempts.join("; ")}.`);
  }, { timeoutMs: 30_000, kind: "model-probe" });
}

elements["test-api-key"].addEventListener("click", async () => {
  const key = elements["api-key"].value.trim();
  if (!key) {
    elements["api-status"].textContent = "Paste a key before testing the connection.";
    elements["api-key"].focus();
    return;
  }
  elements["test-api-key"].disabled = true;
  elements["api-status"].textContent = "Checking NVIDIA API access with bounded fallback…";
  try {
    const model = await probeModelConnection(key);
    elements["api-status"].textContent = `Connected with ${model}. Lesson cells keep their explicit model choices.`;
    updateConnectionSummary(`Connected · ${model}`);
    elements["connection-details"].open = false;
  } catch (error) {
    elements["api-status"].textContent = error.message;
    updateConnectionSummary("Connection needs attention");
    elements["connection-details"].open = true;
  } finally {
    elements["test-api-key"].disabled = false;
  }
});
elements["run-all"].addEventListener("click", async () => {
  if (!confirm(`Run ${state.blocks.length} cells in order? Model cells can consume NVIDIA API quota.`)) return;
  elements["run-all"].disabled = true;
  const operationId = state.operations.begin("Run lesson", { kind: "lesson", detail: `${state.blocks.length} cells in order` });
  let completed = 0;
  try {
    for (const block of state.blocks) {
      if (!(await runBlock(block))) throw new Error(`Stopped after ${completed} completed cells because a cell failed.`);
      completed += 1;
      state.operations.update(operationId, `${completed} of ${state.blocks.length} cells completed`);
    }
    state.operations.settle(operationId, "succeeded", `${completed} cells completed`);
  } catch (error) {
    state.operations.settle(operationId, "failed", error.message);
  } finally {
    elements["run-all"].disabled = false;
  }
});
elements["stop-runtime"].addEventListener("click", () => {
  state.runner.stop();
  resetKernelView();
  elements["runtime-status"].textContent = "Python stopped · variables cleared";
});
elements["dock-stop-runtime"].addEventListener("click", () => elements["stop-runtime"].click());
elements["reset-runtime"].addEventListener("click", restartRuntime);
elements["restart-runtime"].addEventListener("click", restartRuntime);
elements["start-runtime"].addEventListener("click", async () => {
  elements["start-runtime"].disabled = true;
  elements["runtime-status"].textContent = "Starting Python…";
  try {
    const reply = await state.runner.preload({ label: "Start Python runtime" });
    if (!reply.ok) throw new Error(reply.stderr || "Python could not start.");
    renderKernel(reply.kernel);
    elements["runtime-status"].textContent = "Python ready";
    recordRuntimeEvent("session", "Python runtime started");
  } catch (error) {
    recordRuntimeEvent("stderr", error.message);
    elements["runtime-status"].textContent = "Python failed to start";
  } finally {
    elements["start-runtime"].disabled = false;
  }
});
elements["inspect-runtime"].addEventListener("click", async () => {
  elements["inspect-runtime"].disabled = true;
  elements["inspect-runtime"].textContent = "Refreshing…";
  elements["kernel-variables"].setAttribute("aria-busy", "true");
  try {
    const reply = await state.runner.inspect({ label: "Refresh runtime variables" });
    if (!reply.ok) throw new Error(reply.stderr || "Variable refresh failed.");
    if (reply.kernel) renderKernel(reply.kernel);
    recordRuntimeEvent("session", "Runtime variables refreshed");
  } catch (error) {
    recordRuntimeEvent("stderr", error.message);
    const message = document.createElement("p");
    message.className = "inline-error";
    message.textContent = `Refresh failed: ${error.message}`;
    elements["kernel-variables"].replaceChildren(message);
  } finally {
    elements["inspect-runtime"].disabled = false;
    elements["inspect-runtime"].textContent = "Refresh";
    elements["kernel-variables"].removeAttribute("aria-busy");
  }
});
document.querySelectorAll("[data-variable-view]").forEach(button => button.addEventListener("click", () => {
  state.variableView = button.dataset.variableView;
  document.querySelectorAll("[data-variable-view]").forEach(candidate => candidate.setAttribute("aria-pressed", String(candidate === button)));
  if (state.latestKernel) renderKernel(state.latestKernel);
}));
elements["clear-runtime-streams"].addEventListener("click", () => { state.streams = []; renderRuntimeStreams(); });
elements["clear-runtime-operations"].addEventListener("click", () => state.operations.clearSettled());
elements["environment-settings"].addEventListener("click", () => elements["settings-dialog"].showModal());
elements["runtime-agent-form"].addEventListener("submit", async event => {
  event.preventDefault();
  const prompt = elements["runtime-agent-input"].value.trim();
  const key = elements["api-key"].value.trim();
  if (!prompt) return;
  if (!key) {
    elements["api-status"].textContent = "Paste an NVIDIA API key before asking the runtime guide.";
    elements["api-key"].focus();
    return;
  }
  addAgentMessage("user", prompt);
  const pending = addAgentMessage("assistant", "", true);
  elements["runtime-agent-input"].value = "";
  const submit = elements["runtime-agent-form"].querySelector('button[type="submit"]');
  submit.disabled = true;
  try {
    const execution = state.runner.assistant(prompt, runtimeGuideContext(), key, { label: "Runtime guide response" });
    state.agentRequestId = execution.requestId;
    const reply = await execution;
    pending.dataset.agentPending = "false";
    const body = pending.querySelector(".agent-message-body");
    if (!reply.ok) throw new Error(reply.stderr || "The runtime guide failed.");
    if (!body.textContent) body.textContent = reply.value || "No response returned.";
  } catch (error) {
    pending.dataset.agentPending = "false";
    pending.querySelector(".agent-message-body").textContent ||= error.message;
    recordRuntimeEvent("stderr", error.message);
  } finally {
    state.agentRequestId = null;
    submit.disabled = false;
  }
});
document.addEventListener("click", event => {
  const link = event.target.closest("a[data-lesson-id], #previous-lesson, #next-lesson");
  if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  const lessonId = link.dataset.lessonId || new URL(link.href).searchParams.get("lesson");
  const lesson = state.manifest?.lessons.find(item => item.id === lessonId);
  if (!lesson) return;
  event.preventDefault();
  openLesson(lesson).catch(error => {
    elements["lesson-body"].innerHTML = `<section class="fatal"><h2>Lesson could not open</h2><pre>${escapeHtml(error.stack || error.message)}</pre></section>`;
  });
});
window.addEventListener("popstate", () => {
  const requested = new URL(location.href).searchParams.get("lesson");
  const lesson = state.manifest?.lessons.find(item => item.id === requested) || state.manifest?.lessons[0];
  if (lesson) loadLesson(lesson).catch(error => {
    recordRuntimeEvent("stderr", error.message);
    elements["lesson-body"].innerHTML = `<section class="fatal"><h2>Lesson could not open</h2><pre>${escapeHtml(error.stack || error.message)}</pre></section>`;
  });
});

state.operations.run("Open course", ({ signal, update }) => {
  update("Loading the reviewed manifest and lesson bundle");
  return initialize(signal);
}, { timeoutMs: 30_000, kind: "course-load" }).catch(error => {
  elements["lesson-body"].innerHTML = `<section class="fatal"><h2>Course could not start</h2><pre>${escapeHtml(error.stack || error.message)}</pre></section>`;
});
