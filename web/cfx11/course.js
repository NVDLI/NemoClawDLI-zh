// Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { marked } from "../shared/vendor/marked-14.1.4.esm.js";
import { CoursePythonRunner } from "./runtime/runner.js";

const SOURCE_ASSET_REPLACEMENTS = Object.freeze(new Map([
  [
    "https://dli-lms.s3.amazonaws.com/assets/general/nvidia-logo.png",
    new URL("./assets/nvidia-logo.png", import.meta.url).href,
  ],
]));

const state = {
  manifest: null,
  lesson: null,
  runner: new CoursePythonRunner(new URL("./runtime/worker.js", import.meta.url)),
  blocks: [],
  activeBlock: null,
  activeChat: null,
};

const elements = Object.fromEntries([
  "course-nav", "lesson-title", "lesson-meta", "lesson-body", "runtime-status", "run-all",
  "stop-runtime", "reset-runtime", "settings-dialog", "api-key", "api-status", "open-settings",
  "previous-lesson", "next-lesson", "progress-value", "progress-label",
].map(id => [id, document.getElementById(id)]));

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
    div.append(sanitizeHtml(marked.parse(record.data), location.href));
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
  const row = document.createElement("div");
  row.className = `output-channel ${className}`;
  const heading = document.createElement("strong");
  heading.textContent = label;
  const pre = document.createElement("pre");
  pre.textContent = value;
  row.append(heading, pre);
  output.append(row);
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
  appendChannel(block.output, "stderr", reply.stderr, "stderr");
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
}

async function runBlock(block) {
  state.activeBlock = block;
  block.article.dataset.state = "running";
  block.status.textContent = "Running";
  block.output.replaceChildren();
  const stream = document.createElement("pre");
  stream.className = "model-stream";
  block.output.append(stream);
  try {
    const reply = await state.runner.run(block.editor.getValue(), elements["api-key"].value.trim());
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
    state.activeBlock = null;
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
  const response = await fetch(markdownUrl, { credentials: "omit" });
  if (!response.ok) throw new Error(`Could not load ${lesson.markdown_path} (${response.status}).`);
  const raw = await response.text();
  elements["lesson-title"].textContent = lesson.title;
  elements["lesson-meta"].textContent = `${lesson.unit.replaceAll("-", " ")} · ${lesson.cells.length} source cells · imported verbatim`;
  const html = marked.parse(markerHtml(raw), { gfm: true });
  elements["lesson-body"].replaceChildren(sanitizeHtml(html, markdownUrl));

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
  const configuration = {
    lessonDirectory: lesson.id.includes("/") ? lesson.id.slice(0, lesson.id.lastIndexOf("/")) : "introduction",
    files: filesForLesson(lesson),
  };
  state.runner.reset(configuration);
  elements["runtime-status"].textContent = "Python loads when you run a cell";
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

async function initialize() {
  const response = await fetch(new URL("course.json", location.href), { credentials: "omit" });
  if (!response.ok) throw new Error(`Could not load the course manifest (${response.status}).`);
  state.manifest = await response.json();
  const requested = new URL(location.href).searchParams.get("lesson");
  const lesson = state.manifest.lessons.find(item => item.id === requested) || state.manifest.lessons[0];
  await loadLesson(lesson);
}

state.runner.addEventListener("model-stream", event => {
  if (state.activeChat) {
    state.activeChat.textContent += event.detail.text;
    return;
  }
  const stream = state.activeBlock?.output.querySelector(".model-stream");
  if (stream) stream.textContent += event.detail.text;
});

elements["open-settings"].addEventListener("click", () => elements["settings-dialog"].showModal());
elements["api-key"].value = sessionStorage.getItem("cfx11-nvidia-key") || "";
elements["api-key"].addEventListener("input", () => {
  const value = elements["api-key"].value.trim();
  if (value) sessionStorage.setItem("cfx11-nvidia-key", value); else sessionStorage.removeItem("cfx11-nvidia-key");
  elements["api-status"].textContent = value ? "The key is held in this browser tab only." : "No key is stored in this browser tab.";
});
elements["api-key"].dispatchEvent(new Event("input"));
elements["run-all"].addEventListener("click", async () => {
  if (!confirm(`Run ${state.blocks.length} cells in order? Model cells can consume NVIDIA API quota.`)) return;
  for (const block of state.blocks) if (!(await runBlock(block))) break;
});
elements["stop-runtime"].addEventListener("click", () => state.runner.stop());
elements["reset-runtime"].addEventListener("click", () => {
  state.runner.reset({
    lessonDirectory: state.lesson.id.includes("/") ? state.lesson.id.slice(0, state.lesson.id.lastIndexOf("/")) : "introduction",
    files: filesForLesson(state.lesson),
  });
  for (const block of state.blocks) {
    block.article.dataset.state = "ready";
    block.status.textContent = "Ready";
    block.output.replaceChildren();
  }
});

initialize().catch(error => {
  elements["lesson-body"].innerHTML = `<section class="fatal"><h2>Course could not start</h2><pre>${escapeHtml(error.stack || error.message)}</pre></section>`;
});
