// Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import "../../../scripts/pyodide/examples/execution-contract.js";

const PYODIDE_VERSION = "0.27.7";
const PYODIDE_ROOT = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
const NVIDIA_BASE = "https://integrate.api.nvidia.com/v1";
const EXECUTE_CELL = globalThis.PYODIDE_EXECUTION_CONTRACT.source;

let pyodidePromise;
let kernelReady = false;
let executionCount = 0;
let activeRequestId = null;

function safeJson(value) {
  return JSON.stringify(value, (_, item) => typeof item === "bigint" ? String(item) : item);
}

function applyEventBlock(block, state) {
    const payload = block.split(/\r?\n/)
      .filter(line => line.startsWith("data:"))
      .map(line => line.slice(5).trim())
      .join("\n");
    if (!payload || payload === "[DONE]") return;
    let event;
    try { event = JSON.parse(payload); } catch { return; }
    const choice = event.choices?.[0] || {};
    const delta = choice.delta || {};
    if (typeof delta.content === "string" && delta.content) {
      state.chunks.push({ content: delta.content });
      state.message.content += delta.content;
      self.postMessage({ type: "model-stream", requestId: activeRequestId, text: delta.content });
    }
    const reasoning = delta.reasoning_content || delta.reasoning;
    if (typeof reasoning === "string" && reasoning) {
      state.chunks.push({ content: "", reasoning, reasoning_content: reasoning });
      state.message.reasoning_content = (state.message.reasoning_content || "") + reasoning;
    }
    if (Array.isArray(delta.tool_calls)) {
      for (const part of delta.tool_calls) {
        const index = part.index || 0;
        const target = state.message.tool_calls[index] ||= { id: "", type: "function", function: { name: "", arguments: "" } };
        if (part.id) target.id = part.id;
        if (part.function?.name) target.function.name += part.function.name;
        if (part.function?.arguments) target.function.arguments += part.function.arguments;
      }
    }
}

async function parseEventStream(response) {
  const state = { chunks: [], message: { role: "assistant", content: "", tool_calls: [] } };
  if (!response.body) {
    for (const block of (await response.text()).split(/\r?\n\r?\n/)) applyEventBlock(block, state);
    return state;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    let separator = buffer.match(/\r?\n\r?\n/);
    while (separator?.index !== undefined) {
      applyEventBlock(buffer.slice(0, separator.index), state);
      buffer = buffer.slice(separator.index + separator[0].length);
      separator = buffer.match(/\r?\n\r?\n/);
    }
    if (done) break;
  }
  if (buffer.trim()) applyEventBlock(buffer, state);
  return state;
}

globalThis.courseNvidiaChat = async function courseNvidiaChat(requestJson, apiKey) {
  const request = JSON.parse(String(requestJson));
  const base = String(request.base_url || NVIDIA_BASE).replace(/\/+$/, "");
  if (base !== NVIDIA_BASE) {
    throw new Error(`This course permits model calls only to ${NVIDIA_BASE}.`);
  }
  const key = String(apiKey || "").trim();
  if (!key) throw new Error("An NVIDIA API key is required.");
  const body = { ...request };
  delete body.base_url;
  const response = await fetch(`${NVIDIA_BASE}/chat/completions`, {
    method: "POST",
    credentials: "omit",
    headers: {
      "Authorization": `Bearer ${key}`,
      "Content-Type": "application/json",
      "Accept": body.stream ? "text/event-stream" : "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = (await response.text()).slice(0, 800);
    throw new Error(`NVIDIA model request failed (${response.status}): ${detail}`);
  }
  if (body.stream) return safeJson(await parseEventStream(response));
  const payload = await response.json();
  const message = payload.choices?.[0]?.message;
  if (!message) throw new Error("NVIDIA model response did not contain a message.");
  return safeJson({ message, chunks: [] });
};

globalThis.coursePublicJson = async function coursePublicJson(rawUrl) {
  const url = new URL(String(rawUrl));
  const allowed = new Set(["en.wikipedia.org"]);
  if (url.protocol !== "https:" || !allowed.has(url.hostname)) {
    throw new Error(`This lesson does not permit a public-data request to ${url.origin}.`);
  }
  const response = await fetch(url, { credentials: "omit", headers: { "Accept": "application/json" } });
  if (!response.ok) throw new Error(`Public data request failed (${response.status}).`);
  return safeJson(await response.json());
};

async function runtime() {
  if (!pyodidePromise) {
    pyodidePromise = (async () => {
      const module = await import(`${PYODIDE_ROOT}pyodide.mjs`);
      const pyodide = await module.loadPyodide({ indexURL: PYODIDE_ROOT });
      await pyodide.loadPackage(["pydantic", "requests"]);
      return pyodide;
    })();
  }
  return pyodidePromise;
}

async function executeRaw(pyodide, source, inputs = {}, count = 0) {
  pyodide.globals.set("__cell_source", source);
  pyodide.globals.set("__cell_inputs", inputs);
  pyodide.globals.set("__execution_count", count);
  return JSON.parse(String(await pyodide.runPythonAsync(EXECUTE_CELL)));
}

async function prepareKernel(configuration = {}) {
  const pyodide = await runtime();
  if (kernelReady) return pyodide;
  pyodide.runPython('__course_scope = {"__name__": "__main__"}');

  const lessonDirectory = String(configuration.lessonDirectory || "course").replace(/[^A-Za-z0-9._/-]/g, "_");
  const root = `/course/${lessonDirectory}`;
  pyodide.FS.mkdirTree(root);
  for (const file of configuration.files || []) {
    const relative = String(file.path || "");
    if (!relative || relative.startsWith("/") || relative.split("/").includes("..")) {
      throw new Error(`Unsafe lesson file path: ${relative}`);
    }
    const response = await fetch(file.url, { credentials: "omit" });
    if (!response.ok) throw new Error(`Could not load lesson file ${relative} (${response.status}).`);
    const destination = `${root}/${relative}`;
    pyodide.FS.mkdirTree(destination.slice(0, destination.lastIndexOf("/")));
    pyodide.FS.writeFile(destination, new Uint8Array(await response.arrayBuffer()));
  }
  pyodide.runPython(`import os\nos.chdir(${JSON.stringify(root)})`);

  const compatibility = await fetch(new URL("course_compat.py", import.meta.url), { credentials: "omit" });
  if (!compatibility.ok) throw new Error(`Could not load the browser Python compatibility layer (${compatibility.status}).`);
  const bootstrap = await executeRaw(pyodide, await compatibility.text(), {}, 0);
  if (!bootstrap.ok) throw new Error(`Compatibility layer failed to initialize:\n${bootstrap.stderr}`);
  kernelReady = true;
  return pyodide;
}

function normalizeMagic(source) {
  if (source.startsWith("%%time\n")) {
    return {
      source: `import time as __course_time\n__course_started = __course_time.perf_counter()\n${source.slice(7)}\nprint(f"Wall time: {__course_time.perf_counter() - __course_started:.3f} s")`,
      lineOffset: 2,
    };
  }
  if (source.startsWith("%%bash\n")) {
    const command = source.slice(7).trim();
    if (command === "echo hello pipes | rev | tr 'a-z' 'A-Z'") {
      return { source: "print('hello pipes'[::-1].upper())", lineOffset: 0 };
    }
    return { source: `raise RuntimeError(${JSON.stringify("This browser course does not execute arbitrary shell commands.")})`, lineOffset: 0 };
  }
  return { source, lineOffset: 0 };
}

async function runCell(message) {
  const pyodide = await prepareKernel(message.configuration);
  executionCount += 1;
  activeRequestId = message.id;
  const key = String(message.apiKey || "");
  pyodide.globals.set("__course_api_key", key);
  pyodide.runPython(`import os\nos.environ["NVIDIA_BASE_URL"] = ${JSON.stringify(NVIDIA_BASE)}\nos.environ["NVIDIA_API_KEY"] = str(__course_api_key)`);
  const normalized = normalizeMagic(String(message.source || ""));
  try {
    const reply = await executeRaw(pyodide, normalized.source, {}, executionCount);
    if (reply.error_line && normalized.lineOffset) reply.error_line = Math.max(1, reply.error_line - normalized.lineOffset);
    const trace = pyodide.runPython('list(__course_scope.get("COURSE_EXECUTION_TRACE", []))');
    reply.trace = trace.toJs({ dict_converter: Object.fromEntries });
    trace.destroy();
    pyodide.runPython('__course_scope["COURSE_EXECUTION_TRACE"] = []');
    return reply;
  } finally {
    pyodide.runPython('import os\nos.environ.pop("NVIDIA_API_KEY", None)');
    pyodide.globals.delete("__course_api_key");
    activeRequestId = null;
  }
}

async function runChat(message) {
  const pyodide = await prepareKernel(message.configuration);
  activeRequestId = message.id;
  const key = String(message.apiKey || "");
  pyodide.globals.set("__course_api_key", key);
  pyodide.globals.set("__course_chat_id", String(message.chatId || ""));
  pyodide.globals.set("__course_chat_prompt", String(message.prompt || ""));
  pyodide.runPython(`import os\nos.environ["NVIDIA_BASE_URL"] = ${JSON.stringify(NVIDIA_BASE)}\nos.environ["NVIDIA_API_KEY"] = str(__course_api_key)\n__course_scope["__course_chat_id"] = str(__course_chat_id)\n__course_scope["__course_chat_prompt"] = str(__course_chat_prompt)`);
  try {
    const reply = await executeRaw(pyodide, "__course_chatbots[__course_chat_id].chat(__course_chat_prompt)", {}, ++executionCount);
    return reply;
  } finally {
    pyodide.runPython('import os\nos.environ.pop("NVIDIA_API_KEY", None)');
    pyodide.runPython('__course_scope.pop("__course_chat_id", None)\n__course_scope.pop("__course_chat_prompt", None)');
    for (const name of ["__course_api_key", "__course_chat_id", "__course_chat_prompt"]) pyodide.globals.delete(name);
    activeRequestId = null;
  }
}

self.addEventListener("message", async ({ data }) => {
  if (data.type === "stop") return;
  try {
    const result = data.type === "preload"
      ? (await prepareKernel(data.configuration), { ok: true, execution_count: 0 })
      : data.type === "chat" ? await runChat(data) : await runCell(data);
    self.postMessage({ type: "result", id: data.id, ...result });
  } catch (error) {
    self.postMessage({
      type: "result",
      id: data.id,
      ok: false,
      stdout: "",
      stderr: error instanceof Error ? error.message : String(error),
      displays: [],
      has_value: false,
      execution_count: executionCount || null,
      error_line: null,
      trace: [],
    });
  }
});
