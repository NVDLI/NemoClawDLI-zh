// Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { marked } from "../shared/vendor/marked-14.1.4.esm.js";
import { CoursePythonRunner } from "./runtime/runner.js";

const MODEL_BASES = Object.freeze({
  direct: "https://integrate.api.nvidia.com/v1",
  proxy: "https://nvidia-api-cors-proxy.experiments.courses.nvidia.com/v1",
});
const BILLING_SOURCE = "dli-cfx11-web";

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
};

const elements = Object.fromEntries([
  "course-nav", "lesson-title", "lesson-meta", "lesson-body", "runtime-status", "run-all",
  "stop-runtime", "reset-runtime", "settings-dialog", "api-key", "api-status", "open-settings",
  "previous-lesson", "next-lesson", "progress-value", "progress-label", "theme-toggle",
  "clear-api-key", "kernel-status", "queue-status", "kernel-variables", "inspect-runtime",
  "restart-runtime", "test-api-key", "model-route", "route-status", "runtime-panel",
  "runtime-panel-title", "close-runtime-panel", "kernel-started", "start-runtime",
  "dock-stop-runtime", "clear-runtime-streams", "runtime-streams", "runtime-environment",
  "environment-settings", "runtime-agent-form", "runtime-agent-input", "runtime-agent-history",
].map(id => [id, document.getElementById(id)]));

function selectedModelBase() {
  return MODEL_BASES[elements["model-route"]?.value] || MODEL_BASES.direct;
}

function runnerConfiguration(lesson = state.lesson) {
  return {
    lessonDirectory: lesson.id.includes("/") ? lesson.id.slice(0, lesson.id.lastIndexOf("/")) : "introduction",
    files: filesForLesson(lesson),
    modelBaseUrl: selectedModelBase(),
  };
}

function modelHeaders(key, route = elements["model-route"]?.value || "direct") {
  const headers = {
    Accept: "application/json",
    Authorization: `Bearer ${key}`,
    "Content-Type": "application/json",
    "X-BILLING-SOURCE": BILLING_SOURCE,
  };
  if (route === "direct" && location.origin !== "null") headers["X-BILLING-INVOKE-ORIGIN"] = location.origin;
  return headers;
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
      const reply = await state.runner.chat(payload.chat_id, prompt, elements["api-key"].value.trim());
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
  if (reply.kernel) renderKernel(reply.kernel);
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
  state.runner.reset(runnerConfiguration());
  resetKernelView();
  for (const block of state.blocks) {
    block.article.dataset.state = "ready";
    block.status.textContent = "Ready";
    block.output.replaceChildren();
  }
  elements["runtime-status"].textContent = "Python restarted · variables cleared";
}

async function runBlock(block) {
  block.article.dataset.state = "queued";
  block.status.textContent = "Queued";
  block.output.replaceChildren();
  const stream = document.createElement("pre");
  stream.className = "model-stream";
  block.output.append(stream);
  try {
    const execution = state.runner.run(block.editor.getValue(), elements["api-key"].value.trim());
    state.requestBlocks.set(execution.requestId, block);
    const reply = await execution;
    renderReply(block, reply);
    block.article.dataset.state = reply.ok ? "passed" : "failed";
    block.status.textContent = reply.ok ? `Ran as In [${reply.execution_count}]` : "Failed";
    if (reply.ok) updateProgress(state.lesson.id, block.id);
    return reply.ok;
  } catch (error) {
    renderReply(block, { stderr: error.message, displays: [] });
    block.article.dataset.state = "failed";
    block.status.textContent = "Failed";
    return false;
  } finally {
    for (const [requestId, candidate] of state.requestBlocks) {
      if (candidate === block) state.requestBlocks.delete(requestId);
    }
  }
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
    article.className = "xblock";
    article.dataset.cellId = marker.dataset.cellId;
    article.dataset.state = "ready";
    const header = document.createElement("header");
    const prompt = document.createElement("strong");
    prompt.textContent = `In [ ] · cell ${Number(marker.dataset.cellIndex) + 1}`;
    const status = document.createElement("span");
    status.textContent = "Ready";
    const run = document.createElement("button");
    run.type = "button";
    run.textContent = "Run";
    const restore = document.createElement("button");
    restore.type = "button";
    restore.textContent = "Restore source";
    header.append(prompt, status, restore, run);
    const textarea = document.createElement("textarea");
    textarea.value = source;
    textarea.setAttribute("aria-label", `Python source for cell ${Number(marker.dataset.cellIndex) + 1}`);
    const output = document.createElement("div");
    output.className = "cell-output";
    article.append(header, textarea, output);
    markerContainer.replaceWith(article);
    sourceNode.remove();
    const editor = globalThis.CodeMirror.fromTextArea(textarea, {
      mode: "python", lineNumbers: true, indentUnit: 4, tabSize: 4,
      lineWrapping: false, gutters: ["CodeMirror-linenumbers", "course-errors"],
      extraKeys: { "Shift-Enter": () => run.click(), "Ctrl-Enter": () => run.click(), "Cmd-Enter": () => run.click() },
    });
    const block = { id: marker.dataset.cellId, article, status, output, editor, originalSource: source };
    run.addEventListener("click", () => runBlock(block));
    restore.addEventListener("click", () => editor.setValue(source));
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

async function initialize() {
  const [manifestResponse, contentResponse] = await Promise.all([
    fetch(new URL("course.json", location.href), { credentials: "omit" }),
    fetch(new URL("content-bundle.json", location.href), { credentials: "omit" }),
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
  block.status.textContent = "Running";
});

state.runner.addEventListener("queue-change", event => {
  const { active, queued } = event.detail;
  elements["queue-status"].textContent = active
    ? `${queued} waiting · 1 running`
    : queued ? `${queued} waiting` : "Queue empty";
  if (active || queued) recordRuntimeEvent("queue", active ? `${queued} waiting; one job running` : `${queued} waiting`);
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

function openRuntimePanel(name) {
  const titles = { session: "Session", variables: "Variables", streams: "Streams", environment: "Environment", agent: "Runtime guide" };
  elements["runtime-panel"].hidden = false;
  elements["runtime-panel-title"].textContent = titles[name] || "Runtime";
  document.querySelectorAll("[data-panel-view]").forEach(view => { view.hidden = view.dataset.panelView !== name; });
  document.querySelectorAll("[data-runtime-panel]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.runtimePanel === name)));
  if (name === "environment") renderEnvironment();
  if (name === "variables" && state.latestKernel) renderKernel(state.latestKernel);
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
elements["model-route"].value = sessionStorage.getItem("cfx11-model-route") === "proxy" ? "proxy" : "direct";
elements["model-route"].addEventListener("change", () => {
  sessionStorage.setItem("cfx11-model-route", elements["model-route"].value);
  elements["route-status"].textContent = elements["model-route"].value === "direct"
    ? "Direct mode sends requests to NVIDIA from this page and includes this page origin for billing attribution."
    : "Relay mode is for embedding hosts that cannot use the direct CORS route. The relay derives the page origin server-side.";
  if (state.lesson) state.runner.configure(runnerConfiguration());
  renderEnvironment();
});
elements["model-route"].dispatchEvent(new Event("change"));
elements["api-key"].value = sessionStorage.getItem("cfx11-nvidia-key") || "";
elements["api-key"].addEventListener("input", () => {
  const value = elements["api-key"].value.trim();
  if (value) sessionStorage.setItem("cfx11-nvidia-key", value); else sessionStorage.removeItem("cfx11-nvidia-key");
  elements["api-status"].textContent = value ? "The key is held in this browser tab only." : "No key is stored in this browser tab.";
});
elements["api-key"].dispatchEvent(new Event("input"));
elements["clear-api-key"].addEventListener("click", () => {
  elements["api-key"].value = "";
  elements["api-key"].dispatchEvent(new Event("input"));
  elements["api-key"].focus();
});
elements["test-api-key"].addEventListener("click", async () => {
  const key = elements["api-key"].value.trim();
  if (!key) {
    elements["api-status"].textContent = "Paste a key before testing the connection.";
    elements["api-key"].focus();
    return;
  }
  elements["test-api-key"].disabled = true;
  elements["api-status"].textContent = "Checking NVIDIA API access…";
  try {
    const response = await fetch(`${selectedModelBase()}/chat/completions`, {
      method: "POST",
      credentials: "omit",
      headers: modelHeaders(key),
      body: JSON.stringify({
        model: "nvidia/nemotron-nano-12b-v2-vl",
        messages: [{ role: "user", content: "Reply OK." }],
        max_tokens: 1,
        stream: false,
        temperature: 0,
      }),
    });
    elements["api-status"].textContent = response.ok
      ? "Connected. Model cells can use this key."
      : [401, 403].includes(response.status)
        ? `NVIDIA rejected this key (${response.status}). Check or replace it.`
        : `NVIDIA rejected the test request (${response.status}). Check the course model or try again.`;
  } catch (error) {
    const origin = location.origin === "null" ? "a local file" : location.origin;
    elements["api-status"].textContent = `This origin (${origin}) cannot reach NVIDIA's API. Open the published HTTPS course.`;
  } finally {
    elements["test-api-key"].disabled = false;
  }
});
elements["run-all"].addEventListener("click", async () => {
  if (!confirm(`Run ${state.blocks.length} cells in order? Model cells can consume NVIDIA API quota.`)) return;
  for (const block of state.blocks) if (!(await runBlock(block))) break;
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
    const reply = await state.runner.preload();
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
  try {
    const reply = await state.runner.inspect();
    if (reply.kernel) renderKernel(reply.kernel);
  } finally {
    elements["inspect-runtime"].disabled = false;
  }
});
document.querySelectorAll("[data-runtime-panel]").forEach(button => button.addEventListener("click", () => openRuntimePanel(button.dataset.runtimePanel)));
elements["close-runtime-panel"].addEventListener("click", () => {
  elements["runtime-panel"].hidden = true;
  document.querySelectorAll("[data-runtime-panel]").forEach(button => button.setAttribute("aria-pressed", "false"));
});
document.querySelectorAll("[data-variable-view]").forEach(button => button.addEventListener("click", () => {
  state.variableView = button.dataset.variableView;
  document.querySelectorAll("[data-variable-view]").forEach(candidate => candidate.setAttribute("aria-pressed", String(candidate === button)));
  if (state.latestKernel) renderKernel(state.latestKernel);
}));
elements["clear-runtime-streams"].addEventListener("click", () => { state.streams = []; renderRuntimeStreams(); });
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
    const execution = state.runner.assistant(prompt, runtimeGuideContext(), key);
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
  if (lesson) loadLesson(lesson);
});

initialize().catch(error => {
  elements["lesson-body"].innerHTML = `<section class="fatal"><h2>Course could not start</h2><pre>${escapeHtml(error.stack || error.message)}</pre></section>`;
});
