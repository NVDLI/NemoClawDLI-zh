// Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import "../../../scripts/pyodide/examples/execution-contract.js";

const PYODIDE_VERSION = "314.0.2";
const PYODIDE_ROOT = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
const NVIDIA_BASE = "https://integrate.api.nvidia.com/v1";
const EXECUTE_CELL = globalThis.PYODIDE_EXECUTION_CONTRACT.source;
const BUILTIN_PACKAGES = Object.freeze([
  "aiohttp", "anyio", "click", "distro", "httpx", "ipython", "jiter",
  "jsonpatch", "msgpack", "orjson", "packaging", "pydantic", "pyyaml",
  "requests", "sniffio", "tqdm", "typing-extensions", "xxhash",
  "zstandard", "micropip",
]);
const LOCAL_WHEELS = Object.freeze([
  "ormsgpack-1.12.2-cp314-cp314-pyemscripten_2026_0_wasm32.whl",
  "pyahocorasick-2.3.1-cp314-cp314-pyemscripten_2026_0_wasm32.whl",
  "pure/anyascii-0.3.3-py3-none-any.whl",
  "pure/textsearch-0.0.24-py2.py3-none-any.whl",
  "pure/contractions-0.1.73-py2.py3-none-any.whl",
  "pure/tenacity-9.1.4-py3-none-any.whl",
  "pure/langchain_protocol-0.0.18-py3-none-any.whl",
  "pure/requests_toolbelt-1.0.0-py2.py3-none-any.whl",
  "pure/websockets-15.0.1-py3-none-any.whl",
  "pure/langsmith-0.10.5-py3-none-any.whl",
  "pure/uuid_utils-0.17.0-cp314-cp314-pyemscripten_2026_0_wasm32.whl",
  "pure/langchain_core-1.4.9-py3-none-any.whl",
  "pure/langgraph_checkpoint-4.1.1-py3-none-any.whl",
  "pure/langgraph_prebuilt-1.1.0-py3-none-any.whl",
  "pure/langgraph_sdk-0.4.2-py3-none-any.whl",
  "pure/langgraph-1.2.9-py3-none-any.whl",
  "pure/langchain-1.3.13-py3-none-any.whl",
  "pure/langchain_nvidia_ai_endpoints-1.4.3-py3-none-any.whl",
  "pure/openai-2.45.0-py3-none-any.whl",
  "pure/wikipedia_api-0.15.0-py3-none-any.whl",
  "pure/grandalf-0.8-py3-none-any.whl",
]);

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

const NETWORK_RULES = Object.freeze(new Map([
  ["integrate.api.nvidia.com", { paths: ["/v1/"], authorization: true }],
  ["en.wikipedia.org", { paths: ["/w/api.php"], authorization: false }],
  ["air-quality-api.open-meteo.com", { paths: ["/v1/air-quality"], authorization: false }],
  ["mermaid.ink", { paths: ["/"], authorization: false }],
]));

function checkedNetworkUrl(rawUrl) {
  const url = new URL(String(rawUrl));
  const rule = NETWORK_RULES.get(url.hostname);
  if (url.protocol !== "https:" || !rule || !rule.paths.some(prefix => url.pathname.startsWith(prefix))) {
    throw new Error(`This lesson does not permit a request to ${url.origin}${url.pathname}.`);
  }
  return { url, rule };
}

function bytesToBase64(bytes) {
  let binary = "";
  const chunkSize = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
  }
  return btoa(binary);
}

async function readResponseBytes(response, emitModelStream) {
  if (!response.body) return new Uint8Array(await response.arrayBuffer());
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const chunks = [];
  let total = 0;
  let pending = "";
  while (true) {
    const { value, done } = await reader.read();
    if (value?.length) {
      chunks.push(value);
      total += value.length;
    }
    if (emitModelStream && value?.length) {
      const text = decoder.decode(value, { stream: !done });
      pending += text;
      let separator = pending.match(/\r?\n\r?\n/);
      while (separator?.index !== undefined) {
        const state = { chunks: [], message: { role: "assistant", content: "", tool_calls: [] } };
        applyEventBlock(pending.slice(0, separator.index), state);
        pending = pending.slice(separator.index + separator[0].length);
        separator = pending.match(/\r?\n\r?\n/);
      }
    }
    if (done) break;
  }
  if (emitModelStream) {
    pending += decoder.decode();
    if (pending.trim()) {
      const state = { chunks: [], message: { role: "assistant", content: "", tool_calls: [] } };
      applyEventBlock(pending, state);
    }
  }
  const body = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.length;
  }
  return body;
}

globalThis.courseHttpRequest = async function courseHttpRequest(requestJson) {
  const request = JSON.parse(String(requestJson));
  const { url, rule } = checkedNetworkUrl(request.url);
  // MediaWiki requires an explicit CORS origin parameter for browser API clients.
  // The upstream Python package still owns the request; this only opts its
  // allowlisted transport into MediaWiki's documented cross-origin response.
  if (url.hostname === "en.wikipedia.org") url.searchParams.set("origin", "*");
  const headers = new Headers();
  for (const [name, value] of Object.entries(request.headers || {})) {
    const normalized = name.toLowerCase();
    if (["connection", "content-length", "host", "user-agent"].includes(normalized)) continue;
    if (normalized === "authorization" && !rule.authorization) {
      throw new Error(`Authorization is not permitted for ${url.hostname}.`);
    }
    headers.set(name, String(value));
  }
  const method = String(request.method || "GET").toUpperCase();
  const requestBody = ["GET", "HEAD"].includes(method) || request.body == null || request.body === ""
    ? undefined
    : String(request.body);
  const response = await fetch(url, {
    method,
    credentials: "omit",
    headers,
    body: requestBody,
  });
  const stream = headers.get("accept")?.includes("text/event-stream") || false;
  const responseBytes = await readResponseBytes(response, stream && url.hostname === "integrate.api.nvidia.com");
  return safeJson({
    status: response.status,
    reason: response.statusText,
    url: response.url || url.href,
    headers: Object.fromEntries(response.headers.entries()),
    body_base64: bytesToBase64(responseBytes),
  });
};

async function runtime() {
  if (!pyodidePromise) {
    pyodidePromise = (async () => {
      const module = await import(`${PYODIDE_ROOT}pyodide.mjs`);
      const pyodide = await module.loadPyodide({ indexURL: PYODIDE_ROOT });
      await pyodide.loadPackage(BUILTIN_PACKAGES);
      const wheelUrls = LOCAL_WHEELS.map(name => new URL(`wheels/${name}`, import.meta.url).href);
      pyodide.globals.set("__course_local_wheels", wheelUrls);
      try {
        await pyodide.runPythonAsync(`
import micropip
await micropip.install(__course_local_wheels.to_py(), deps=False, reinstall=True)
`);
      } finally {
        pyodide.globals.delete("__course_local_wheels");
      }
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

function batchMode(pyodide) {
  return String(pyodide.runPython('__course_scope.get("COURSE_BATCH_MODE", "unknown")'));
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
    reply.batch_mode = batchMode(pyodide);
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
    reply.batch_mode = batchMode(pyodide);
    return reply;
  } finally {
    pyodide.runPython('import os\nos.environ.pop("NVIDIA_API_KEY", None)');
    pyodide.runPython('__course_scope.pop("__course_chat_id", None)\n__course_scope.pop("__course_chat_prompt", None)');
    for (const name of ["__course_api_key", "__course_chat_id", "__course_chat_prompt"]) pyodide.globals.delete(name);
    activeRequestId = null;
  }
}

async function preload(message) {
  const pyodide = await prepareKernel(message.configuration);
  return { ok: true, execution_count: 0, batch_mode: batchMode(pyodide) };
}

self.addEventListener("message", async ({ data }) => {
  if (data.type === "stop") return;
  try {
    const result = data.type === "preload"
      ? await preload(data)
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
