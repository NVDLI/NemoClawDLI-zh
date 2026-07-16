// Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const repositoryPlaywright = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../scripts/runtime/node_modules/playwright-core",
);
let chromium;
try { ({ chromium } = require(repositoryPlaywright)); }
catch (_) { ({ chromium } = require("/opt/nemoclaw-runtime/node_modules/playwright-core")); }

const root = path.resolve(process.env.SITE_ROOT || ".");
const port = Number(process.env.SITE_PORT || 4211);
const timeout = Number(process.env.AUDIT_TIMEOUT_MS || 180000);
const mime = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8", ".md": "text/markdown; charset=utf-8",
  ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".ico": "image/x-icon",
};

const server = http.createServer((request, response) => {
  const relative = decodeURIComponent(new URL(request.url, "http://localhost").pathname).replace(/^\/+/, "");
  let file = path.resolve(root, relative || "web/cfx11/index.html");
  if (file !== root && !file.startsWith(root + path.sep)) return response.writeHead(403).end("forbidden");
  // GitLab Pages keeps raw Markdown in the artifact but does not reliably serve it.
  // The course must work against that deployed constraint, not only a source server.
  if (path.extname(file) === ".md") return response.writeHead(404).end("raw Markdown is not served");
  if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, "index.html");
  fs.readFile(file, (error, body) => {
    if (error) return response.writeHead(404).end("not found");
    response.writeHead(200, { "content-type": mime[path.extname(file)] || "application/octet-stream" });
    response.end(body);
  });
});

function check(value, message) { if (!value) throw new Error(message); }
function listen() { return new Promise(resolve => server.listen(port, "127.0.0.1", resolve)); }

async function runCell(page, index, replacement = null) {
  const block = page.locator(`.xblock[data-cell-id$=":${index}"]`);
  await block.waitFor();
  if (replacement !== null) {
    await block.locator(".CodeMirror").evaluate((element, source) => element.CodeMirror.setValue(source), replacement);
  }
  await block.getByRole("button", { name: "Run", exact: true }).click();
  await page.waitForFunction(cellIndex => {
    const element = document.querySelector(`.xblock[data-cell-id$=":${cellIndex}"]`);
    return ["passed", "failed"].includes(element?.dataset.state);
  }, index, { timeout });
  return block;
}

async function waitForBlock(page, block) {
  await page.waitForFunction(cellId => {
    const element = document.querySelector(`.xblock[data-cell-id="${CSS.escape(cellId)}"]`);
    return ["passed", "failed"].includes(element?.dataset.state);
  }, await block.getAttribute("data-cell-id"), { timeout });
  return block;
}

await listen();
let browser;
try {
  browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_BIN || undefined });
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, colorScheme: "dark" });
  const errors = [];
  const failures = [];
  let mermaidRequests = 0;
  page.on("pageerror", error => errors.push(error.message));
  page.on("requestfailed", request => failures.push(`${request.url()}: ${request.failure()?.errorText}`));
  await page.route("https://mermaid.ink/img/**", async route => {
    mermaidRequests += 1;
    await route.fulfill({
      status: 200,
      contentType: "image/png",
      body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAUAAAAC0CAIAAABqhmJGAAABjUlEQVR42u3TQQkAAAACMfv39W8OYYtwcClwKxKAgQEDAwYGAwMGBgwMGBgMDBgYMDAYGDAwYGDAwGBgwMCAgQEDg4EBAwMGBgMDBgYMDBgYDAwYGDAwYGAwMGBgwMBgYMDAgIEBA4OBAQMDBgYDAwYGDAwYGAwMGBgwMGBgMDBgYMDAYGDAwICBAQODgQEDAwYGDAwGBgwMGBgMDBgYMDBgYDAwYGDAwICBwcCAgQEDg4EBAwMGBgwMBgYMDBgYDAwYGDAwYGAwMGBgwMCAgcHAgIEBA4OBAQMDBgYMDAYGDAwYGDAwGBgwMGBgMDBgYMDAgIHBwICBAQMDBgYDAwYGDAwGBgwMGBgwMBgYMDBgYDAwYGDAwICBwcCAgQEDAwYGAwMGBgwMBgYMDBgYMDAYGDAwYGDAwGBgwMCAgcHAgIEBAwMGBgMDBgYMDAYGDAwYGDAwGBgwMGBgwMBgYMDAgIHBwICBAQMDBgYDAwYGDAwYGAwMGBgwMBgYMDBgYMDAYGDAwICBAQPDtwHZISTbeVhHAAAAAABJRU5ErkJggg==", "base64"),
    });
  });
  const url = `http://127.0.0.1:${port}/web/cfx11/index.html?lesson=2-Chains%2F22-Runnable-Functions`;
  await page.goto(url, { waitUntil: "domcontentloaded", timeout });
  await page.locator(".xblock").first().waitFor({ timeout });
  const manifest = await page.evaluate(() => fetch("course.json").then(response => response.json()));
  for (const lesson of manifest.lessons) {
    const lessonUrl = `http://127.0.0.1:${port}/web/cfx11/index.html?lesson=${encodeURIComponent(lesson.id)}`;
    await page.goto(lessonUrl, { waitUntil: "domcontentloaded", timeout });
    await page.waitForFunction(expected => document.querySelector("#lesson-title")?.textContent === expected, lesson.title, { timeout });
    const expectedCells = lesson.cells.filter(cell => cell.type === "code");
    check(await page.locator(".xblock").count() === expectedCells.length, `${lesson.id} did not expose every source code cell`);
    const actualIds = await page.locator(".xblock").evaluateAll(nodes => nodes.map(node => node.dataset.cellId));
    check(JSON.stringify(actualIds) === JSON.stringify(expectedCells.map(cell => cell.id)), `${lesson.id} changed source-cell order`);
    const sourceThemeOverrides = await page.locator("#lesson-body style, #lesson-body [style], #lesson-body [color], #lesson-body [bgcolor]")
      .evaluateAll(nodes => nodes.filter(node => !node.closest(".xblock")).length);
    check(sourceThemeOverrides === 0, `${lesson.id} retained a source-controlled theme override`);
  }
  check(mermaidRequests > 0, "Mermaid source fences were not upgraded to rendered diagrams during full lesson traversal");
  await page.goto(url, { waitUntil: "domcontentloaded", timeout });
  await page.locator(".xblock").first().waitFor({ timeout });
  check(await page.locator(".xblock").count() === 23, "Runnable Functions must expose all 23 original code cells");
  const fixedLogo = page.locator('.lesson-body img[src$="/nvidia.png"], .lesson-body img[src$="/nvidia-logo.png"]').first();
  if (await fixedLogo.count()) {
    check(await fixedLogo.evaluate(image => getComputedStyle(image).backgroundColor === "rgb(255, 255, 255)"), "fixed-color NVIDIA logo did not receive its dark-theme presentation plate");
  }
  check(await page.locator("#api-key").inputValue() === "", "the learner API key must not be prefilled");
  check(await page.locator("#api-key").isVisible(), "the learner API key field must be visible in the lesson flow");
  check(await page.locator("#theme-toggle").isVisible(), "the course must expose an explicit theme control");
  await page.getByRole("button", { name: "Test key" }).click();
  check(await page.locator("#api-status").innerText() === "Paste a key before testing the connection.", "the visible API-key action was not usable at a 1280x720 learner viewport");
  for (const index of [7, 14, 16, 20, 21]) {
    const block = await runCell(page, index);
    const output = await block.locator(".cell-output").innerText();
    check(await block.getAttribute("data-state") === "passed", `source cell ${index} did not execute:\n${output}`);
  }
  check((await page.locator('.xblock[data-cell-id$=":21"] .cell-output').innerText()).includes("12"), "persistent Python state did not return 12");

  const batchBlock = await runCell(page, 21, "from langchain_core.runnables import RunnableLambda\nRunnableLambda(lambda value: value * 2).batch([2, 4, 6])");
  const batchOutput = await batchBlock.locator(".cell-output").innerText();
  check(await batchBlock.getAttribute("data-state") === "passed", `real LangChain batch failed in the current browser runtime:\n${batchOutput}`);
  check(batchOutput.includes("4") && batchOutput.includes("8") && batchOutput.includes("12"), "real LangChain batch returned the wrong values");
  check(await page.locator("#runtime-status").innerText() === "Python ready · batches run in order in this browser", "the runtime did not disclose Pyodide's batch scheduler");

  const capabilityBlock = await runCell(page, 21, "import sys\n{'pthreads': bool(sys._emscripten_info.pthreads), 'batch_mode': COURSE_BATCH_MODE}");
  const capabilityOutput = await capabilityBlock.locator(".cell-output").innerText();
  check(await capabilityBlock.getAttribute("data-state") === "passed", `Pyodide capability probe failed:\n${capabilityOutput}`);
  check(capabilityOutput.includes("false") && capabilityOutput.includes("ordered-browser-fallback"), `the runtime capability and selected scheduler disagree:\n${capabilityOutput}`);

  const inputBlock = page.locator('.xblock[data-cell-id$=":21"]');
  await inputBlock.locator(".CodeMirror").evaluate(element => element.CodeMirror.setValue('student_name = input("Your name: ")\nconnection_config = {"api_key": "nvapi-this-must-not-render"}\n{"student": student_name, "kept": True}'));
  await inputBlock.getByRole("button", { name: "Run", exact: true }).click();
  await inputBlock.locator(".python-input").waitFor({ timeout });
  for (const theme of ["light", "dark"]) {
    await page.evaluate(value => document.documentElement.dataset.theme = value, theme);
    const inputPalette = await inputBlock.locator(".python-input").evaluate(form => {
      const panel = getComputedStyle(form);
      const field = getComputedStyle(form.querySelector("input"));
      return { panel: panel.backgroundColor, field: field.backgroundColor, text: field.color };
    });
    check(inputPalette.panel !== "rgba(0, 0, 0, 0)" && inputPalette.field !== inputPalette.panel && inputPalette.text, `${theme} Python input was not visually separated`);
  }
  const queuedBlock = page.locator('.xblock[data-cell-id$=":20"]');
  await queuedBlock.locator(".CodeMirror").evaluate(element => element.CodeMirror.setValue('queue_marker = "ran second"\nqueue_marker'));
  await queuedBlock.getByRole("button", { name: "Run", exact: true }).click();
  await page.waitForFunction(() => document.querySelector('#queue-status')?.textContent.includes("waiting"), null, { timeout });
  check(await queuedBlock.getAttribute("data-state") === "queued", "a second execution did not wait behind active input");
  await inputBlock.locator(".python-input input").fill("Ada");
  await inputBlock.locator(".python-input button").click();
  await waitForBlock(page, inputBlock);
  await waitForBlock(page, queuedBlock);
  const inputOutput = await inputBlock.locator(".cell-output").innerText();
  check(inputOutput.includes("Your name: Ada") && inputOutput.includes('"student": "Ada"'), `Python input did not return through the requesting cell:\n${inputOutput}`);
  check((await queuedBlock.locator(".cell-output").innerText()).includes("ran second"), "queued execution did not run after input completed");
  for (const theme of ["light", "dark"]) {
    await page.evaluate(value => document.documentElement.dataset.theme = value, theme);
    const stdoutPalette = await inputBlock.locator(".output-channel.stdout").evaluate(channel => {
      const style = getComputedStyle(channel);
      return { background: style.backgroundColor, color: style.color };
    });
    check(stdoutPalette.background !== "rgba(0, 0, 0, 0)" && stdoutPalette.color, `${theme} stdout had no readable presentation`);
  }
  check(await page.locator("#queue-status").innerText() === "Queue empty", "execution queue did not return to idle");

  await runCell(page, 21, "focused_value = 41\nif False:\n    never_created = focused_value\nfocused_value + 1");
  await page.getByRole("button", { name: "Variables", exact: true }).click();
  await page.waitForFunction(() => document.querySelector("#kernel-variables")?.textContent.includes("focused_value"), null, { timeout });
  check(!(await page.locator("#kernel-variables").innerText()).includes("student_name"), "focused variable view dumped unrelated persistent state");
  await page.getByRole("button", { name: "All variables", exact: true }).click();
  await page.waitForFunction(() => document.querySelector("#kernel-variables")?.textContent.includes("student_name"), null, { timeout });
  check((await page.locator("#kernel-variables").innerText()).includes("queue_marker"), "complete namespace omitted persisted queue output");
  check(!(await page.locator("#kernel-variables").innerText()).includes("this-must-not-render"), "variable inspector exposed a credential-shaped nested value");
  check(!(await page.locator("#kernel-status").innerText()).includes("Not started"), "kernel session identity was not displayed");
  await page.locator("#close-runtime-panel").click();

  const errorBlock = await runCell(page, 21, "values = [1]\nvalues[9]");
  check(await errorBlock.getAttribute("data-state") === "failed", "runtime error did not fail the cell");
  check(await errorBlock.locator(".CodeMirror").evaluate(element => element.CodeMirror.lineInfo(1)?.bgClass?.includes("course-error-line")), "runtime error did not highlight line 2");

  const widgetSource = `class DummyChat:\n    def chat(self, prompt):\n        return "echo: " + prompt\napp = create_chatbot_interface_from_bot(DummyChat())\napp.launch()`;
  const widgetBlock = await runCell(page, 21, widgetSource);
  const widget = widgetBlock.locator(".course-chat");
  await widget.waitFor();
  await widget.getByLabel("Chat message").fill("hello browser");
  await widget.getByRole("button", { name: "Send" }).click();
  await page.waitForFunction(() => document.querySelector(".chat-message.assistant")?.textContent.includes("echo: hello browser"), null, { timeout });

  const graphSource = `from IPython.display import Image, display\ngraph_chain = RunnableLambda(lambda value: value) | RunnableLambda(lambda value: value)\ndisplay(Image(graph_chain.get_graph().draw_mermaid_png()))`;
  const graphBlock = await runCell(page, 21, graphSource);
  const graphImage = graphBlock.locator(".graph-output img");
  check(await graphImage.count() === 1, "the real LangChain graph did not render as a PNG");
  check((await graphImage.getAttribute("src")).startsWith("data:image/png;base64,"), "graph output was not a safe PNG data URL");
  const graphPayload = await graphImage.evaluate(image => {
    const encoded = image.src.split(",", 2)[1] || "";
    const decoded = atob(encoded);
    return { encodedLength: encoded.length, signature: Array.from(decoded.slice(0, 8), character => character.charCodeAt(0)) };
  });
  check(JSON.stringify(graphPayload.signature) === JSON.stringify([137, 80, 78, 71, 13, 10, 26, 10]), `graph output did not contain PNG bytes: ${JSON.stringify(graphPayload)}`);
  await graphImage.evaluate(image => image.decode());
  for (const colorScheme of ["dark", "light"]) {
    await page.emulateMedia({ colorScheme });
    const graphLayout = await graphImage.evaluate(image => {
      const style = getComputedStyle(image);
      return {
        complete: image.complete,
        naturalWidth: image.naturalWidth,
        naturalHeight: image.naturalHeight,
        renderedWidth: image.getBoundingClientRect().width,
        maxWidth: style.maxWidth,
      };
    });
    check(graphLayout.complete && graphLayout.naturalWidth > 100 && graphLayout.naturalHeight > 50, `${colorScheme} graph PNG did not decode`);
    check(graphLayout.renderedWidth > 100 && graphLayout.renderedWidth <= 1200, `${colorScheme} graph PNG escaped its responsive output bounds`);
  }

  let modelRequest = null;
  let keyTestRequests = null;
  let modelListingRequest = null;
  await page.route("https://integrate.api.nvidia.com/v1/models", async route => {
    modelListingRequest = { headers: route.request().headers() };
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ object: "list", data: [{ id: "nvidia/test-model", object: "model", created: 0, owned_by: "nvidia" }] }),
    });
  });
  await page.evaluate(() => {
    window.__cfx11OriginalFetch = window.fetch.bind(window);
    window.__cfx11KeyTestRequests = [];
    window.fetch = async (input, init = {}) => {
      if (String(input) === "https://integrate.api.nvidia.com/v1/chat/completions") {
        window.__cfx11KeyTestRequests.push({
          headers: Object.fromEntries(new Headers(init.headers || {}).entries()),
          body: JSON.parse(String(init.body || "{}")),
        });
        if (window.__cfx11KeyTestRequests.length === 1) {
          return new Response(JSON.stringify({ error: "candidate unavailable" }), { status: 503, headers: { "Content-Type": "application/json" } });
        }
        return new Response(JSON.stringify({ choices: [{ message: { role: "assistant", content: "OK" }, finish_reason: "stop" }] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return window.__cfx11OriginalFetch(input, init);
    };
  });
  await page.locator("#api-key").fill("browser-test-key");
  await page.getByRole("button", { name: "Test key" }).click();
  await page.waitForFunction(() => !document.querySelector("#test-api-key")?.disabled, null, { timeout: 35_000 });
  const keyStatus = await page.locator("#api-status").innerText();
  check(keyStatus.startsWith("Connected"), `bounded connection test failed visibly: ${keyStatus}; page errors: ${JSON.stringify(errors)}`);
  keyTestRequests = await page.evaluate(() => window.__cfx11KeyTestRequests);
  await page.evaluate(() => {
    window.fetch = window.__cfx11OriginalFetch;
    delete window.__cfx11OriginalFetch;
    delete window.__cfx11KeyTestRequests;
  });
  await page.route("https://integrate.api.nvidia.com/v1/chat/completions", async route => {
    const request = route.request();
    modelRequest = { headers: request.headers(), body: request.postDataJSON() };
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: [
        'data: {"choices":[{"delta":{"content":"browser "}}]}',
        'data: {"choices":[{"delta":{"content":"stream"}}]}',
        "data: [DONE]",
        "",
      ].join("\n\n"),
    });
  });
  const modelSource = `from langchain_nvidia_ai_endpoints import ChatNVIDIA\n"".join(chunk.content for chunk in ChatNVIDIA(model="nvidia/test-model").stream("hello"))`;
  const modelBlock = await runCell(page, 21, modelSource);
  const modelOutput = await modelBlock.locator(".cell-output").innerText();
  check(await modelBlock.getAttribute("data-state") === "passed", `direct NVIDIA streaming compatibility call failed:\n${modelOutput}`);
  check((await modelBlock.locator(".cell-output").innerText()).includes("browser stream"), "streaming model result was not returned to Python");
  check(keyTestRequests?.length === 2, `connection test did not fall back once after a model outage: ${JSON.stringify(keyTestRequests)}`);
  check(keyTestRequests[0].body.model !== keyTestRequests[1].body.model, "connection-test fallback retried the same model");
  check(keyTestRequests[1]?.headers.authorization === "Bearer browser-test-key", "learner key was not sent on the auth-sensitive model test");
  check(keyTestRequests[1]?.headers["x-billing-source"] === "dli-cfx11-web", "key test omitted the stable billing source");
  check(keyTestRequests[1]?.headers["x-billing-invoke-origin"] === `http://127.0.0.1:${port}`, "direct key test omitted trusted page-origin attribution");
  check(keyTestRequests.every(request => request.body?.max_tokens === 1 && request.body?.stream === false), "key test fallback was not bounded to one non-streaming output token per candidate");
  await page.getByRole("button", { name: "Activity", exact: false }).click();
  check((await page.locator("#runtime-operations").innerText()).includes("Test NVIDIA model connection"), "connection fallback was absent from workflow activity");
  check((await page.locator("#operation-summary").innerText()).includes("No work is running"), "completed connection test remained falsely active");
  await page.locator("#close-runtime-panel").click();
  check(modelListingRequest?.headers.authorization === "Bearer browser-test-key", "learner key was not sent on the real package's model discovery request");
  check(modelRequest?.headers.authorization === "Bearer browser-test-key", "learner key was not sent only as the NVIDIA authorization header");
  check(modelRequest?.headers["x-billing-source"] === "dli-cfx11-web", "Python model request omitted billing source");
  check(modelRequest?.headers["x-billing-invoke-origin"] === `http://127.0.0.1:${port}`, "Python direct model request omitted page-origin attribution");
  check(modelRequest?.body?.stream === true && modelRequest?.body?.model === "nvidia/test-model", "streaming model request changed its source-cell parameters");
  check(!Object.keys(modelRequest.headers).some(name => name.startsWith("x-stainless-")), "SDK metadata escaped the stable browser CORS header boundary");
  await page.getByRole("button", { name: "Agent", exact: true }).click();
  await page.locator("#runtime-agent-input").fill("What remains in this runtime?");
  await page.locator("#runtime-agent-form").getByRole("button", { name: "Ask runtime guide" }).click();
  await page.waitForFunction(() => document.querySelector("#runtime-agent-history")?.textContent.includes("browser stream"), null, { timeout });
  check((await page.locator("#runtime-streams").count()) === 1, "runtime stream surface is missing");
  await page.locator("#close-runtime-panel").click();

  let proxyKeyRequest = null;
  await page.locator("#model-route").selectOption("proxy");
  await page.route("https://nvidia-api-cors-proxy.experiments.courses.nvidia.com/v1/chat/completions", async route => {
    proxyKeyRequest = { headers: route.request().headers(), body: route.request().postDataJSON() };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ choices: [{ message: { content: "OK" } }] }) });
  });
  await page.getByRole("button", { name: "Test key" }).click();
  await page.waitForFunction(() => !document.querySelector("#test-api-key")?.disabled, null, { timeout: 35_000 });
  check((await page.locator("#api-status").innerText()).startsWith("Connected"), "relay connection test did not settle successfully");
  check(proxyKeyRequest?.headers["x-billing-source"] === "dli-cfx11-web", "relay request omitted billing source");
  check(!("x-billing-invoke-origin" in proxyKeyRequest.headers), "relay accepted caller-controlled billing-origin attribution");
  await page.locator("#model-route").selectOption("direct");
  await page.unroute("https://nvidia-api-cors-proxy.experiments.courses.nvidia.com/v1/chat/completions");
  await page.locator("#api-key").fill("");
  await page.unroute("https://integrate.api.nvidia.com/v1/models");
  await page.unroute("https://integrate.api.nvidia.com/v1/chat/completions");

  const wikipediaSource = `import wikipediaapi\npage = wikipediaapi.Wikipedia(user_agent="DLI-course-test/1.0").page("Paris")\n{"exists": page.exists(), "mentions_france": "France" in page.summary}`;
  const wikipediaBlock = await runCell(page, 21, wikipediaSource);
  const wikipediaOutput = await wikipediaBlock.locator(".cell-output").innerText();
  check(wikipediaOutput.includes('"mentions_france": true'), `live Wikipedia compatibility request did not return source data:\n${wikipediaOutput}`);

  const airSource = `import requests\nresponse = requests.get("https://air-quality-api.open-meteo.com/v1/air-quality", params={"latitude": 19.076, "longitude": 72.8777, "hourly": "european_aqi"})\nresponse.raise_for_status()\n{"hourly": "hourly" in response.json(), "status": response.status_code}`;
  const airBlock = await runCell(page, 21, airSource);
  const airOutput = await airBlock.locator(".cell-output").innerText();
  check(airOutput.includes('"hourly": true'), `live Open-Meteo request did not return source data:\n${airOutput}`);

  const stateBlock = await runCell(page, 21, 'cross_lesson_value = {"answer": 42}\ncross_lesson_value');
  check(await stateBlock.getAttribute("data-state") === "passed", "cross-lesson state setup failed");
  await page.locator('#course-nav a[data-lesson-id="2-Chains/23-Combining-Chains"]').click();
  await page.waitForFunction(() => document.querySelector("#lesson-title")?.textContent.includes("Combining"), null, { timeout });
  const carriedBlock = page.locator(".xblock").first();
  await carriedBlock.locator(".CodeMirror").evaluate(element => element.CodeMirror.setValue("cross_lesson_value"));
  await carriedBlock.getByRole("button", { name: "Run", exact: true }).click();
  await waitForBlock(page, carriedBlock);
  check((await carriedBlock.locator(".cell-output").innerText()).includes('"answer": 42'), "Python variables did not persist across in-tab lesson navigation");
  await page.getByRole("button", { name: "Variables", exact: true }).click();
  await page.getByRole("button", { name: "All variables", exact: true }).click();
  await page.waitForFunction(() => document.querySelector("#kernel-variables")?.textContent.includes("cross_lesson_value"), null, { timeout });

  for (const expectedTheme of ["light", "dark"]) {
    if (await page.locator("html").getAttribute("data-theme") !== expectedTheme) await page.locator("#theme-toggle").click();
    check(await page.locator("html").getAttribute("data-theme") === expectedTheme, `${expectedTheme} theme was not selectable`);
    const palette = await page.evaluate(() => {
      const key = getComputedStyle(document.querySelector("#api-key"));
      const editor = getComputedStyle(document.querySelector(".CodeMirror"));
      const body = getComputedStyle(document.body);
      return { keyBackground: key.backgroundColor, keyColor: key.color, editorBackground: editor.backgroundColor, bodyBackground: body.backgroundColor };
    });
    check(palette.keyBackground !== "rgba(0, 0, 0, 0)" && palette.keyColor, `${expectedTheme} API input had no readable palette`);
    check(palette.editorBackground !== palette.bodyBackground, `${expectedTheme} editor lost its visual boundary`);
    if (process.env.CFX11_SCREENSHOT_DIR) {
      fs.mkdirSync(process.env.CFX11_SCREENSHOT_DIR, { recursive: true });
      await page.screenshot({ path: path.join(process.env.CFX11_SCREENSHOT_DIR, `cfx11-${expectedTheme}.png`), fullPage: true });
    }
  }
  await page.getByRole("button", { name: "Session", exact: true }).click();
  await page.getByRole("button", { name: "Restart Python" }).click();
  await page.getByRole("button", { name: "Variables", exact: true }).click();
  await page.getByRole("button", { name: "All variables", exact: true }).click();
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await page.waitForFunction(() => document.querySelector("#kernel-status")?.textContent !== "Not started", null, { timeout });
  check(!(await page.locator("#kernel-variables").innerText()).includes("cross_lesson_value"), "restart did not clear the Python namespace");

  await page.goto(`http://127.0.0.1:${port}/web/cfx11/index.html?lesson=3-Prompting-With-Messages%2F36-Chatbots`, { waitUntil: "domcontentloaded", timeout });
  const helperLink = page.getByRole("link", { name: "chat_helpers/gradio_interface.py" });
  await helperLink.waitFor();
  check((await helperLink.getAttribute("href")).startsWith("https://gitlab.com/nvidia/dli/content/c-fx-11-v1/"), "unlicensed helper source must remain an upstream link");

  await page.goto(`http://127.0.0.1:${port}/web/cfx11/index.html?lesson=6-Assessment%2F61-Assessment`, { waitUntil: "domcontentloaded", timeout });
  const assessmentSource = `from assessment_helper import run_assessment

class InputSensitiveChain:
    def invoke(self, messages):
        joined = " ".join(messages).lower()
        if "shirt tore" in joined:
            return "clothing, Dallas"
        return "furniture, New York"

run_assessment(InputSensitiveChain())`;
  const assessmentBlock = await runCell(page, 32, assessmentSource);
  check(await assessmentBlock.getAttribute("data-state") === "passed", "assessment middleware did not accept an input-sensitive chain");
  const assessmentOutput = await assessmentBlock.locator(".cell-output").innerText();
  check(assessmentOutput.includes('"input sensitivity": true'), "assessment output omitted the counterfactual sensitivity check");
  check(assessmentOutput.includes("Assessment passed"), "assessment did not return its learner-facing pass evidence");
  check(errors.length === 0, `page errors: ${JSON.stringify(errors)}`);
  check(failures.length === 0, `request failures: ${JSON.stringify(failures)}`);
  console.log(`cfx11_browser_audit: PASS (${manifest.lessons.length} lessons, Pages-style Markdown 404, digest bundle, Mermaid, source-cell order, explicit themes, serialized queue, in-cell input, cross-lesson kernel state, focused/all variables, runtime guide, direct and relay billing headers, restart, error line, chat widget, real LangChain graph PNG, live public APIs, upstream helper link, assessment middleware)`);
} finally {
  await browser?.close();
  server.close();
}
