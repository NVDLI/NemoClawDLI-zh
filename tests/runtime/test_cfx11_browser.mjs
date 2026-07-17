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
const retiredBillingHeader = "x-billing-" + "source";

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

async function waitForCourseReady(page, label) {
  console.log(`cfx11_browser_audit: loading ${label}`);
  await page.locator(".xblock, .fatal").first().waitFor({ timeout: Math.min(timeout, 30_000) });
  const fatal = page.locator(".fatal");
  if (await fatal.count()) throw new Error(`${label} failed before its first runnable cell:\n${await fatal.innerText()}`);
}

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

async function openNavigationLesson(page, lessonId) {
  const link = page.locator(`#course-nav a[data-lesson-id="${lessonId}"]`);
  await link.evaluate(element => { element.closest("details").open = true; });
  await link.click();
}

await listen();
let browser;
try {
  browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROME_BIN || undefined,
    args: ["--host-resolver-rules=MAP staging.localhost 127.0.0.1"],
  });
  const stagingPage = await browser.newPage({ viewport: { width: 1280, height: 720 }, colorScheme: "dark" });
  await stagingPage.route("https://d36m44n9vdbmda.cloudfront.net/assets/s-fx-12-v2/*.mp4", route => route.fulfill({ status: 200, contentType: "video/mp4", body: "" }));
  await stagingPage.goto(`http://staging.localhost:${port}/web/cfx11/index.html?lesson=2-Chains%2F22-Runnable-Functions`, { waitUntil: "domcontentloaded", timeout });
  await waitForCourseReady(stagingPage, "unregistered-origin route audit");
  check(await stagingPage.locator("#model-route").inputValue() === "proxy", "an unregistered staging origin did not select the DLI browser relay");
  check((await stagingPage.locator("#route-status").innerText()).includes("staging or embedding origin"), "the staging route choice was not explained to the learner");
  await stagingPage.close();
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, colorScheme: "dark" });
  const errors = [];
  const failures = [];
  let mermaidRequests = 0;
  page.on("pageerror", error => errors.push(error.message));
  page.on("requestfailed", request => failures.push(`${request.url()}: ${request.failure()?.errorText}`));
  await page.route("https://d36m44n9vdbmda.cloudfront.net/assets/s-fx-12-v2/*.mp4", route => route.fulfill({ status: 200, contentType: "video/mp4", body: "" }));
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
  await waitForCourseReady(page, "Runnable Functions");
  const manifest = await page.evaluate(() => fetch("course.json").then(response => response.json()));
  const videoManifest = await page.evaluate(() => fetch("video-supplements.json").then(response => response.json()));
  const videoByLesson = new Map(videoManifest.entries.map(record => [record.lesson_id, record]));
  const renderedVideos = new Set();
  for (const lesson of manifest.lessons) {
    console.log(`cfx11_browser_audit: checking lesson ${lesson.id}`);
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
    const expectedVideo = videoByLesson.get(lesson.id);
    const videos = page.locator(".lesson-video");
    check(await videos.count() === (expectedVideo ? 1 : 0), `${lesson.id} rendered the wrong number of source-bound walkthroughs`);
    if (expectedVideo) {
      renderedVideos.add(expectedVideo.id);
      const player = videos.locator("video");
      const source = player.locator("source");
      check(await player.getAttribute("controls") !== null, `${lesson.id} walkthrough has no learner controls`);
      check(await player.getAttribute("autoplay") === null, `${lesson.id} walkthrough unexpectedly autoplays`);
      check(await player.getAttribute("preload") === "metadata", `${lesson.id} walkthrough does not use bounded metadata preload`);
      check(await source.getAttribute("src") === expectedVideo.media_url, `${lesson.id} walkthrough changed its reviewed media URL`);
      const sourceNotebookHref = await videos.getByRole("link", { name: "View source notebook", exact: true }).getAttribute("href");
      check(sourceNotebookHref?.includes(videoManifest.source.commit), `${lesson.id} walkthrough source link is not commit-bound: ${sourceNotebookHref}`);
    }
  }
  check(renderedVideos.size === videoManifest.entries.length, "full lesson traversal did not render every invoked source walkthrough");
  check(mermaidRequests > 0, "Mermaid source fences were not upgraded to rendered diagrams during full lesson traversal");
  await page.goto(url, { waitUntil: "domcontentloaded", timeout });
  await waitForCourseReady(page, "Runnable Functions interaction audit");
  check(await page.locator("#course-nav details").count() === 7, "course units were not rendered as collapsible sections");
  check(await page.locator("#course-nav details[open]").count() === 1, "navigation did not keep only the current section open by default");
  const currentLessonLink = page.locator('#course-nav a[aria-current="page"]');
  check(await currentLessonLink.count() === 1 && await currentLessonLink.isVisible(), "navigation did not reveal and mark the current lesson");
  check((await currentLessonLink.locator(".nav-lesson-number").innerText()) === "2.3", "current lesson did not receive its section.lesson number");
  check(await page.locator("#previous-lesson").isVisible() && await page.locator("#next-lesson").isVisible(), "header omitted previous or next lesson navigation");
  check((await page.locator("#next-lesson").getAttribute("title"))?.includes("2.4 Combining Chains"), "header next control did not identify its destination");
  await page.locator("#next-lesson").click();
  await page.waitForFunction(() => document.querySelector("#lesson-title")?.textContent === "Combining Chains", null, { timeout });
  check(await page.locator('#course-nav a[aria-current="page"] .nav-lesson-number').innerText() === "2.4", "header navigation did not update the current lesson marker");
  await page.locator("#previous-lesson").click();
  await page.waitForFunction(() => document.querySelector("#lesson-title")?.textContent === "Runnable Functions", null, { timeout });
  check(await page.locator(".xblock").count() === 23, "Runnable Functions must expose all 23 original code cells");
  check(await page.locator(".xblock .wb-cell-workspace").count() === 23, "every Python cell must expose the shared code-and-evidence workspace");
  check(await page.locator(".xblock .wb-cell-artifact[hidden]").count() === 23, "pre-run cells must not reserve space for empty evidence panes");
  check(await page.locator('.xblock[data-output-layout="below"]').count() === 23, "new cells must default to output below the editable code");
  check(await page.locator(".xblock .wb-cell-empty").count() === 0, "pre-run cells must not render placeholder output");
  const proseWidths = await page.locator(".lesson-body > .lesson-lead, .lesson-body > p, .lesson-body > ul > li, .lesson-body > ol > li")
    .evaluateAll(nodes => nodes.map(node => getComputedStyle(node).maxWidth));
  check(proseWidths.every(width => width === "none"), `lesson prose retained a character-width hedge: ${JSON.stringify(proseWidths)}`);
  check(await page.locator("#model-route").inputValue() === "direct", "the local validator origin must retain the direct NVIDIA route");
  check(await page.locator("#model-choice").inputValue() === "auto", "the lesson model must default to a visible automatic compatibility choice");
  check(await page.locator("#runtime-dock").getAttribute("data-workbench-ready") === "true", "runtime workbench did not mount");
  const activityTool = page.getByRole("button", { name: "Activity", exact: false });
  await activityTool.click();
  check(await page.locator("#runtime-panel").isVisible(), "runtime activity view did not open");
  const workspaceGeometry = await page.locator(".xblock .wb-cell-workspace").first().evaluate(workspace => {
    const source = workspace.querySelector(".wb-cell-source").getBoundingClientRect();
    return {
      sourceWidth: source.width,
      sourceRight: source.right,
      viewportWidth: innerWidth,
      documentWidth: document.documentElement.scrollWidth,
    };
  });
  check(workspaceGeometry.sourceWidth > 500,
    `runtime panel crushed the code-only pre-run workspace: ${JSON.stringify(workspaceGeometry)}`);
  check(workspaceGeometry.sourceRight <= workspaceGeometry.documentWidth && workspaceGeometry.documentWidth <= workspaceGeometry.viewportWidth,
    `runtime panel pushed the pre-run cell outside the viewport: ${JSON.stringify(workspaceGeometry)}`);
  await page.keyboard.press("Escape");
  check(await page.locator("#runtime-panel").isHidden(), "Escape did not close the runtime workbench");
  check(await activityTool.evaluate(button => document.activeElement === button), "runtime workbench did not return focus to its opening tool");
  const fixedLogo = page.locator('.lesson-body img[src$="/nvidia.png"], .lesson-body img[src$="/nvidia-logo.png"]').first();
  if (await fixedLogo.count()) {
    check(await fixedLogo.evaluate(image => getComputedStyle(image).backgroundColor === "rgb(255, 255, 255)"), "fixed-color NVIDIA logo did not receive its dark-theme presentation plate");
  }
  check(await page.locator("#api-key").inputValue() === "", "the learner API key must not be prefilled");
  check(await page.locator("#connection-details").getAttribute("open") !== null, "an unset model connection did not expose its key editor");
  check(await page.locator("#api-key").isVisible(), "the learner API key field must be visible in the lesson flow");
  check(await page.locator("#theme-toggle").isVisible(), "the course must expose an explicit theme control");
  await page.locator("#api-key").fill("saved-without-probing");
  await page.getByRole("button", { name: "Save and close", exact: true }).click();
  check(await page.locator("#connection-details").getAttribute("open") === null, "saving a learner key did not collapse the prominent editor");
  check(await page.locator("#connection-summary-status").innerText() === "Key saved in this tab", "the collapsed key editor did not expose its non-secret state");
  await page.locator("#connection-details > summary").click();
  await page.getByRole("button", { name: "Clear", exact: true }).click();
  check(await page.locator("#api-key").inputValue() === "" && await page.locator("#api-key").isVisible(), "clearing a key did not reopen an empty editor");
  await page.getByRole("button", { name: "Test key" }).click();
  check(await page.locator("#api-status").innerText() === "Paste a key before testing the connection.", "the visible API-key action was not usable at a 1280x720 learner viewport");
  const keyboardBlock = page.locator(".xblock").first();
  const originalKeyboardSource = await keyboardBlock.locator(".CodeMirror").evaluate(element => element.CodeMirror.getValue());
  check(await keyboardBlock.locator(".CodeMirror").evaluate(element => element.CodeMirror.getOption("readOnly") === false), "the Python editor is read-only");
  await keyboardBlock.locator(".CodeMirror").click();
  await keyboardBlock.locator(".CodeMirror").evaluate(element => element.CodeMirror.execCommand("selectAll"));
  await page.keyboard.type("student_keyboard_edit = 17\nstudent_keyboard_edit");
  check(await keyboardBlock.locator(".CodeMirror").evaluate(element => element.CodeMirror.getValue()) === "student_keyboard_edit = 17\nstudent_keyboard_edit", "normal keyboard input did not edit the Python cell");
  await keyboardBlock.locator(".CodeMirror").evaluate(element => element.CodeMirror.execCommand("selectAll"));
  await page.keyboard.press("Control+Slash");
  check((await keyboardBlock.locator(".CodeMirror").evaluate(element => element.CodeMirror.getValue())).split("\n").every(line => line.startsWith("# ")), "the notebook comment shortcut did not use Python comments");
  await page.keyboard.press("Control+Slash");
  const settingsToggle = keyboardBlock.locator("summary[aria-label$='settings']");
  await settingsToggle.click();
  await keyboardBlock.getByRole("button", { name: "Restore source", exact: true }).click();
  check(await keyboardBlock.locator(".CodeMirror").evaluate(element => element.CodeMirror.getValue()) === originalKeyboardSource, "Restore source did not recover the imported Python");
  check(await keyboardBlock.getByRole("button", { name: "Copy code", exact: true }).count() === 1, "cell settings omitted the copy action");
  check(await keyboardBlock.getByRole("button", { name: "Clear output", exact: true }).count() === 1, "cell settings omitted the output reset action");
  check(await keyboardBlock.getByLabel("Output position").inputValue() === "below", "the per-cell output control did not default below code");
  await keyboardBlock.locator(".CodeMirror").evaluate(element => element.CodeMirror.setValue("1"));
  await keyboardBlock.getByRole("button", { name: "Run", exact: true }).click();
  await waitForBlock(page, keyboardBlock);
  check(await keyboardBlock.locator(".wb-cell-artifact").isVisible(), "running a cell did not reveal its result pane");
  check(await keyboardBlock.getAttribute("data-output-state") === "complete", "a completed cell did not expose its output lifecycle state");
  const belowGeometry = await keyboardBlock.locator(".wb-cell-workspace").evaluate(workspace => {
    const source = workspace.querySelector(".wb-cell-source").getBoundingClientRect();
    const artifact = workspace.querySelector(".wb-cell-artifact").getBoundingClientRect();
    return { sourceBottom: source.bottom, artifactTop: artifact.top, sourceWidth: source.width, artifactWidth: artifact.width };
  });
  check(belowGeometry.artifactTop >= belowGeometry.sourceBottom - 1 && Math.abs(belowGeometry.sourceWidth - belowGeometry.artifactWidth) < 2,
    `the default below layout did not stack the cell panes: ${JSON.stringify(belowGeometry)}`);
  await keyboardBlock.locator(".cell-output").evaluate(output => output.append(" stale-result-that-must-clear"));
  await keyboardBlock.getByRole("button", { name: "Run", exact: true }).click();
  check(!(await keyboardBlock.locator(".cell-output").innerText()).includes("stale-result-that-must-clear"), "a new execution retained stale output");
  await waitForBlock(page, keyboardBlock);
  await keyboardBlock.locator(".CodeMirror").evaluate(element => element.CodeMirror.setValue("assignment_only = 17"));
  await keyboardBlock.getByRole("button", { name: "Run", exact: true }).click();
  await waitForBlock(page, keyboardBlock);
  check(await keyboardBlock.locator(".wb-cell-result-note").innerText() === "Completed without output.", "a successful assignment-only cell rendered a blank result pane");
  check(await keyboardBlock.locator(".wb-cell-artifact-state").innerText() === "Complete", "the result pane did not expose its settled state");
  await keyboardBlock.getByRole("button", { name: "Clear output", exact: true }).click();
  check(await keyboardBlock.locator(".wb-cell-artifact").isHidden(), "Clear output did not return the cell to its compact pre-run state");
  check(await keyboardBlock.getAttribute("data-output-state") === "hidden", "Clear output did not reset the output lifecycle state");
  await keyboardBlock.getByRole("button", { name: "Restore source", exact: true }).click();
  await keyboardBlock.getByLabel("Output position").selectOption("beside");
  check(await keyboardBlock.getAttribute("data-output-layout") === "beside", "the per-cell output control did not restore the beside layout");
  await keyboardBlock.getByLabel("Wrap long lines").uncheck();
  check(await keyboardBlock.locator(".CodeMirror").evaluate(element => element.CodeMirror.getOption("lineWrapping") === false), "cell settings did not disable line wrapping");
  await keyboardBlock.getByLabel("Wrap long lines").check();
  await keyboardBlock.getByLabel("Show line numbers").uncheck();
  check(await keyboardBlock.locator(".CodeMirror").evaluate(element => element.CodeMirror.getOption("lineNumbers") === false), "cell settings did not hide line numbers");
  await keyboardBlock.getByLabel("Show line numbers").check();
  await keyboardBlock.getByLabel("Editor height").selectOption("tall");
  check(await keyboardBlock.getAttribute("data-editor-height") === "tall", "cell settings did not select a tall editor");
  await keyboardBlock.getByLabel("Editor height").selectOption("match");
  await settingsToggle.click();
  console.log("cfx11_browser_audit: starting persistent Python kernel and queue checks");
  for (const index of [7, 14, 16, 20, 21]) {
    const block = await runCell(page, index);
    const output = await block.locator(".cell-output").innerText();
    check(await block.getAttribute("data-state") === "passed", `source cell ${index} did not execute:\n${output}`);
  }
  check((await page.locator('.xblock[data-cell-id$=":21"] .cell-output').innerText()).includes("12"), "persistent Python state did not return 12");

  const inspectionBlock = await runCell(page, 21, 'base_url = "https://integrate.api.nvidia.com/v1"\n??base_url');
  const inspectionOutput = await inspectionBlock.locator(".cell-output").innerText();
  check(await inspectionBlock.getAttribute("data-state") === "passed" && inspectionOutput.includes("builtins.str") && inspectionOutput.includes("integrate.api.nvidia.com"),
    `notebook ?? inspection did not inspect a live value:\n${inspectionOutput}`);
  const shellBlock = await runCell(page, 21, "!pwd");
  const shellOutput = await shellBlock.locator(".cell-output").innerText();
  check(await shellBlock.getAttribute("data-state") === "passed" && shellOutput.includes("/course/2-Chains"), `browser-shell !pwd did not expose the virtual working directory:\n${shellOutput}`);
  const whoBlock = await runCell(page, 21, "%who");
  check((await whoBlock.locator(".cell-output").innerText()).includes("base_url"), "%who omitted a learner variable from the persistent namespace");
  const magicBlock = await runCell(page, 21, "%magic");
  check((await magicBlock.locator(".cell-output").innerText()).includes("value? / value??"), "%magic did not explain the supported notebook syntax");
  const bashBlock = await runCell(page, 21, "%%bash\necho hello pipes | rev | tr 'a-z' 'A-Z'");
  check((await bashBlock.locator(".cell-output").innerText()).includes("SEPIP OLLEH"), "bounded %%bash pipeline regressed");

  const batchBlock = await runCell(page, 21, "from langchain_core.runnables import RunnableLambda\nRunnableLambda(lambda value: value * 2).batch([2, 4, 6])");
  const batchOutput = await batchBlock.locator(".cell-output").innerText();
  check(await batchBlock.getAttribute("data-state") === "passed", `real LangChain batch failed in the current browser runtime:\n${batchOutput}`);
  check(batchOutput.includes("4") && batchOutput.includes("8") && batchOutput.includes("12"), "real LangChain batch returned the wrong values");
  check(await page.locator("#runtime-status").innerText() === "Python ready · batches run in order in this browser", "the runtime did not disclose Pyodide's batch scheduler");

  const capabilityBlock = await runCell(page, 21, "import sys\n{'pthreads': bool(sys._emscripten_info.pthreads), 'batch_mode': COURSE_BATCH_MODE}");
  const capabilityOutput = await capabilityBlock.locator(".cell-output").innerText();
  check(await capabilityBlock.getAttribute("data-state") === "passed", `Pyodide capability probe failed:\n${capabilityOutput}`);
  check(capabilityOutput.includes("false") && capabilityOutput.includes("ordered-browser-fallback"), `the runtime capability and selected scheduler disagree:\n${capabilityOutput}`);

  const longResultBlock = await runCell(page, 21, `{
    "nested": {"ready": True, "values": list(range(12))},
    "long_text": "x" * 20000,
  }`);
  check(await longResultBlock.locator("pre.formatted-output code.language-json").count() === 1, "a returned dictionary did not use the highlighted JSON renderer");
  const longResultGeometry = await longResultBlock.evaluate(block => {
    const source = block.querySelector(".wb-cell-source").getBoundingClientRect();
    const artifact = block.querySelector(".wb-cell-artifact").getBoundingClientRect();
    const output = block.querySelector(".cell-output");
    return {
      sourceWidth: source.width,
      artifactWidth: artifact.width,
      outputClientHeight: output.clientHeight,
      outputScrollHeight: output.scrollHeight,
      outputScrollWidth: output.scrollWidth,
      outputClientWidth: output.clientWidth,
      documentWidth: document.documentElement.scrollWidth,
      viewportWidth: innerWidth,
    };
  });
  check(longResultGeometry.sourceWidth > 250 && longResultGeometry.artifactWidth > 220,
    `long output resized the code pane: ${JSON.stringify(longResultGeometry)}`);
  check(longResultGeometry.outputClientHeight <= 610 && longResultGeometry.outputScrollHeight > longResultGeometry.outputClientHeight,
    `long output was not contained in a bounded result viewport: ${JSON.stringify(longResultGeometry)}`);
  check(longResultGeometry.outputScrollWidth <= longResultGeometry.outputClientWidth + 1 && longResultGeometry.documentWidth <= longResultGeometry.viewportWidth,
    `long output escaped its cell or page width: ${JSON.stringify(longResultGeometry)}`);

  const inputBlock = page.locator('.xblock[data-cell-id$=":21"]');
  await inputBlock.locator(".CodeMirror").evaluate(element => element.CodeMirror.setValue('student_name = input("Your name: ")\nconnection_config = {"api_key": "nvapi-this-must-not-render"}\n{"student": student_name, "kept": True}'));
  await inputBlock.getByRole("button", { name: "Run", exact: true }).click();
  await inputBlock.locator(".python-input").waitFor({ timeout });
  check(await inputBlock.getAttribute("data-output-state") === "running", "an input-blocked execution did not retain its running result state");
  check(await inputBlock.locator(".wb-cell-artifact-state").innerText() === "Running", "the result heading did not identify active execution");
  check(await inputBlock.locator('.wb-cell-progress[role="status"]').isVisible(), "running a cell revealed a blank result pane instead of visual progress");
  const progressGeometry = await inputBlock.locator(".wb-cell-artifact").evaluate(artifact => {
    const style = getComputedStyle(artifact);
    const progress = artifact.querySelector(".wb-cell-progress").getBoundingClientRect();
    const mark = getComputedStyle(artifact.querySelector(".wb-cell-progress-mark"));
    return { minHeight: style.minHeight, progressHeight: progress.height, animationName: mark.animationName };
  });
  check(progressGeometry.minHeight === "0px" && progressGeometry.progressHeight > 0 && progressGeometry.progressHeight < 80,
    `the running result surface was not compact: ${JSON.stringify(progressGeometry)}`);
  check(progressGeometry.animationName !== "none", `the running result surface had no motion cue: ${JSON.stringify(progressGeometry)}`);
  for (const theme of ["light", "dark"]) {
    await page.evaluate(value => document.documentElement.dataset.theme = value, theme);
    const inputPalette = await inputBlock.locator(".python-input").evaluate(form => {
      const panel = getComputedStyle(form);
      const field = getComputedStyle(form.querySelector("input"));
      return { panel: panel.backgroundColor, field: field.backgroundColor, text: field.color };
    });
    check(inputPalette.panel !== "rgba(0, 0, 0, 0)" && inputPalette.field !== inputPalette.panel && inputPalette.text, `${theme} Python input was not visually separated`);
    const progressPalette = await inputBlock.locator(".wb-cell-progress").evaluate(progress => {
      const copy = getComputedStyle(progress.querySelector(".wb-cell-progress-copy"));
      const mark = getComputedStyle(progress.querySelector(".wb-cell-progress-mark"));
      return { text: copy.color, marker: mark.borderTopColor };
    });
    check(progressPalette.text !== progressPalette.marker && progressPalette.marker !== "rgba(0, 0, 0, 0)", `${theme} running progress did not remain visually distinct`);
    if (process.env.CFX11_SCREENSHOT_DIR) {
      fs.mkdirSync(process.env.CFX11_SCREENSHOT_DIR, { recursive: true });
      await inputBlock.screenshot({ path: path.join(process.env.CFX11_SCREENSHOT_DIR, `cfx11-running-${theme}.png`) });
    }
  }
  const queuedBlock = page.locator('.xblock[data-cell-id$=":20"]');
  await queuedBlock.locator(".CodeMirror").evaluate(element => element.CodeMirror.setValue('queue_marker = "ran second"\nqueue_marker'));
  await queuedBlock.getByRole("button", { name: "Run", exact: true }).click();
  await page.waitForFunction(() => document.querySelector('#queue-status')?.textContent.includes("waiting"), null, { timeout });
  check(await queuedBlock.getAttribute("data-state") === "queued", "a second execution did not wait behind active input");
  check(await queuedBlock.locator('.wb-cell-progress[role="status"]').isVisible(), "a queued cell did not expose visual waiting feedback");
  check(await queuedBlock.locator(".wb-cell-artifact-state").innerText() === "Queued", "a queued result surface mislabeled its state");
  await inputBlock.locator(".python-input input").fill("Ada");
  await inputBlock.locator(".python-input button").click();
  await waitForBlock(page, inputBlock);
  await waitForBlock(page, queuedBlock);
  check(await inputBlock.locator(".wb-cell-progress").count() === 0 && await inputBlock.locator(".wb-cell-artifact-state").innerText() === "Complete", "settled evidence retained its running progress treatment");
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
  await page.locator('[data-workbench-view="variables"]').click();
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
  const matchedEditorGeometry = await errorBlock.evaluate(block => {
    const source = block.querySelector(".wb-cell-source").getBoundingClientRect();
    const editor = block.querySelector(".CodeMirror").getBoundingClientRect();
    return { sourceBottom: source.bottom, editorBottom: editor.bottom, sourceHeight: source.height, editorHeight: editor.height };
  });
  check(Math.abs(matchedEditorGeometry.sourceBottom - matchedEditorGeometry.editorBottom) < 2,
    `the default editor did not fill its source pane beside tall output: ${JSON.stringify(matchedEditorGeometry)}`);
  await errorBlock.locator(".CodeMirror").click();
  for (const theme of ["light", "dark"]) {
    await page.evaluate(value => document.documentElement.dataset.theme = value, theme);
    const caret = await errorBlock.locator(".CodeMirror-cursor").first().evaluate(element => {
      const style = getComputedStyle(element);
      return { width: parseFloat(style.borderLeftWidth), color: style.borderLeftColor };
    });
    check(caret.width >= 2, `${theme} editor caret is too thin: ${JSON.stringify(caret)}`);
    check(theme !== "dark" || caret.color !== "rgb(0, 0, 0)", `dark editor retained a black caret: ${JSON.stringify(caret)}`);
  }

  const widgetSource = `class DummyChat:\n    def chat(self, prompt):\n        return "echo: " + prompt\napp = create_chatbot_interface_from_bot(DummyChat())\napp.launch()`;
  const widgetBlock = await runCell(page, 21, widgetSource);
  const widget = widgetBlock.locator(".course-chat");
  await widget.waitFor();
  await widget.getByLabel("Chat message").fill("hello browser");
  await widget.getByRole("button", { name: "Send" }).click();
  await page.waitForFunction(() => document.querySelector(".chat-message.assistant")?.textContent.includes("echo: hello browser"), null, { timeout });

  const graphSource = `from IPython.display import Image, display\ngraph_chain = RunnableLambda(lambda value: value) | RunnableLambda(lambda value: value)\ndisplay(Image(graph_chain.get_graph().draw_mermaid_png()))`;
  console.log("cfx11_browser_audit: checking widgets, errors, and rendered artifacts");
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
  console.log("cfx11_browser_audit: checking bounded model fallback and streaming transport");
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
  const keyStatus = await page.locator("#api-status").textContent();
  check(keyStatus.startsWith("Connected"), `bounded connection test failed visibly: ${keyStatus}; page errors: ${JSON.stringify(errors)}`);
  check(await page.locator("#connection-details").getAttribute("open") === null, "a verified model connection did not collapse to its compact summary");
  check((await page.locator("#connection-summary-status").innerText()).startsWith("Connected"), "the compact model summary did not report verified state");
  keyTestRequests = await page.evaluate(() => window.__cfx11KeyTestRequests);
  const verifiedFallback = keyTestRequests?.[1]?.body?.model;
  check((await page.locator("#connection-summary-status").innerText()).includes(verifiedFallback), "the visible connection summary did not name the compatible fallback it chose");
  check((await page.locator("#model-choice-status").textContent()).includes(verifiedFallback), "automatic model configuration did not retain the compatible fallback it chose");
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
  check(keyTestRequests[1]?.headers["x-billing-invoke-origin"] === "dli-cfx11-web", "direct key test omitted stable course attribution");
  check(!(retiredBillingHeader in keyTestRequests[1].headers), "direct key test restored the retired billing header");
  check(keyTestRequests.every(request => request.body?.max_tokens === 1 && request.body?.stream === false), "key test fallback was not bounded to one non-streaming output token per candidate");
  const overrideBlock = await runCell(page, 21, 'import os\nos.getenv("NVIDIA_MODEL")');
  check(await overrideBlock.getAttribute("data-state") === "passed" && (await overrideBlock.locator(".cell-output").innerText()).includes(verifiedFallback),
    "the verified compatible model did not reach the Python setup-cell environment");
  const recoveryBlock = await runCell(page, 21, 'raise RuntimeError("NVIDIA chat/completions HTTP 504 Gateway Time-out")');
  check(await recoveryBlock.getAttribute("data-state") === "failed", "the transient model failure probe did not fail");
  check((await recoveryBlock.locator(".model-recovery").innerText()).includes("temporarily unavailable"), "a transient model outage did not provide concise recovery guidance");
  await recoveryBlock.getByRole("button", { name: "Choose another model" }).click();
  check(await page.locator("#connection-details").getAttribute("open") !== null && await page.locator("#model-choice").evaluate(node => document.activeElement === node),
    "the transient model recovery action did not open and focus the model choice");
  await page.locator("#connection-details > summary").click();
  await page.getByRole("button", { name: "Activity", exact: false }).click();
  check((await page.locator("#runtime-operations").innerText()).includes("Test NVIDIA model connection"), "connection fallback was absent from workflow activity");
  check((await page.locator("#operation-summary").innerText()).includes("No work is running"), "completed connection test remained falsely active");
  await page.locator("#close-runtime-panel").click();
  check(modelListingRequest?.headers.authorization === "Bearer browser-test-key", "learner key was not sent on the real package's model discovery request");
  check(modelRequest?.headers.authorization === "Bearer browser-test-key", "learner key was not sent only as the NVIDIA authorization header");
  check(modelRequest?.headers["x-billing-invoke-origin"] === "dli-cfx11-web", "Python direct model request omitted stable course attribution");
  check(!(retiredBillingHeader in modelRequest.headers), "Python model request restored the retired billing header");
  check(modelRequest?.body?.stream === true && modelRequest?.body?.model === "nvidia/test-model", "streaming model request changed its source-cell parameters");
  check(!Object.keys(modelRequest.headers).some(name => name.startsWith("x-stainless-")), "SDK metadata escaped the stable browser CORS header boundary");
  await page.locator('[data-workbench-view="agent"]').click();
  await page.locator("#runtime-agent-input").fill("What remains in this runtime?");
  await page.locator("#runtime-agent-form").getByRole("button", { name: "Ask runtime guide" }).click();
  await page.waitForFunction(() => document.querySelector("#runtime-agent-history")?.textContent.includes("browser stream"), null, { timeout });
  check((await page.locator("#runtime-streams").count()) === 1, "runtime stream surface is missing");
  await page.locator("#close-runtime-panel").click();

  let proxyKeyRequest = null;
  await page.locator("#connection-details > summary").click();
  await page.locator("#model-route").selectOption("proxy");
  await page.route("https://nvidia-api-cors-proxy.experiments.courses.nvidia.com/v1/chat/completions", async route => {
    proxyKeyRequest = { headers: route.request().headers(), body: route.request().postDataJSON() };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ choices: [{ message: { content: "OK" } }] }) });
  });
  await page.getByRole("button", { name: "Test key" }).click();
  await page.waitForFunction(() => !document.querySelector("#test-api-key")?.disabled, null, { timeout: 35_000 });
  check((await page.locator("#api-status").textContent()).startsWith("Connected"), "relay connection test did not settle successfully");
  await page.locator("#connection-details > summary").click();
  check(proxyKeyRequest?.headers["x-billing-invoke-origin"] === "dli-cfx11-web", "relay request omitted stable course attribution");
  check(!(retiredBillingHeader in proxyKeyRequest.headers), "relay request restored the retired billing header");
  await page.locator("#model-route").selectOption("direct");
  await page.unroute("https://nvidia-api-cors-proxy.experiments.courses.nvidia.com/v1/chat/completions");
  await page.locator("#api-key").fill("");
  await page.unroute("https://integrate.api.nvidia.com/v1/models");
  await page.unroute("https://integrate.api.nvidia.com/v1/chat/completions");

  const wikipediaSource = `import wikipediaapi\npage = wikipediaapi.Wikipedia(user_agent="DLI-course-test/1.0").page("Paris")\n{"exists": page.exists(), "mentions_france": "France" in page.summary}`;
  console.log("cfx11_browser_audit: checking live public-data adapters and lesson kernel scopes");
  const wikipediaBlock = await runCell(page, 21, wikipediaSource);
  const wikipediaOutput = await wikipediaBlock.locator(".cell-output").innerText();
  check(wikipediaOutput.includes('"mentions_france": true'), `live Wikipedia compatibility request did not return source data:\n${wikipediaOutput}`);

  const airSource = `import requests\nresponse = requests.get("https://air-quality-api.open-meteo.com/v1/air-quality", params={"latitude": 19.076, "longitude": 72.8777, "hourly": "european_aqi"})\nresponse.raise_for_status()\n{"hourly": "hourly" in response.json(), "status": response.status_code}`;
  const airBlock = await runCell(page, 21, airSource);
  const airOutput = await airBlock.locator(".cell-output").innerText();
  check(airOutput.includes('"hourly": true'), `live Open-Meteo request did not return source data:\n${airOutput}`);

  check(await page.locator("#kernel-scope").inputValue() === "lesson", "course did not default to one kernel per source notebook");
  const stateBlock = await runCell(page, 21, 'isolated_lesson_value = {"answer": 42}\nisolated_lesson_value');
  check(await stateBlock.getAttribute("data-state") === "passed", "per-lesson state setup failed");
  await openNavigationLesson(page, "2-Chains/23-Combining-Chains");
  await page.waitForFunction(() => document.querySelector("#lesson-title")?.textContent.includes("Combining"), null, { timeout });
  const carriedBlock = page.locator(".xblock").first();
  await carriedBlock.locator(".CodeMirror").evaluate(element => element.CodeMirror.setValue("isolated_lesson_value"));
  await carriedBlock.getByRole("button", { name: "Run", exact: true }).click();
  await waitForBlock(page, carriedBlock);
  check(await carriedBlock.getAttribute("data-state") === "failed", "a lesson unexpectedly inherited the previous notebook's namespace");
  check((await carriedBlock.locator(".cell-output").innerText()).includes("NameError"), "isolated lesson state failed without a useful missing-variable error");

  await page.locator('[data-workbench-view="session"]').click();
  await page.locator("#kernel-scope").selectOption("shared");
  check((await page.locator("#kernel-scope-status").innerText()).includes("keeps one kernel"), "shared-kernel mode was not explained after selection");
  await page.locator("#close-runtime-panel").click();
  const sharedStateBlock = await runCell(page, 7, 'shared_lesson_value = {"answer": 84}\nshared_lesson_value');
  check(await sharedStateBlock.getAttribute("data-state") === "passed", "shared-kernel state setup failed");
  await openNavigationLesson(page, "2-Chains/24-Parallel-Chains");
  await page.waitForFunction(() => document.querySelector("#lesson-title")?.textContent.includes("Parallel"), null, { timeout });
  const sharedCarriedBlock = page.locator(".xblock").first();
  await sharedCarriedBlock.locator(".CodeMirror").evaluate(element => element.CodeMirror.setValue("shared_lesson_value"));
  await sharedCarriedBlock.getByRole("button", { name: "Run", exact: true }).click();
  await waitForBlock(page, sharedCarriedBlock);
  check((await sharedCarriedBlock.locator(".cell-output").innerText()).includes('"answer": 84'), "explicit shared-kernel mode did not preserve state across lessons");
  await page.locator('[data-workbench-view="variables"]').click();
  await page.getByRole("button", { name: "All variables", exact: true }).click();
  await page.waitForFunction(() => document.querySelector("#kernel-variables")?.textContent.includes("shared_lesson_value"), null, { timeout });

  const themeBlock = page.locator(".xblock").first();
  await themeBlock.locator(".CodeMirror").evaluate(element => {
    element.CodeMirror.setValue("from typing import Dict\n\ndef sample(value: int = 3):\n    mapping = dict(count=value)\n    # Builtins and atoms must stay readable.\n    return str(mapping) if True else None");
    element.CodeMirror.refresh();
  });
  for (const expectedTheme of ["light", "dark"]) {
    if (await page.locator("html").getAttribute("data-theme") !== expectedTheme) await page.locator("#theme-toggle").click();
    check(await page.locator("html").getAttribute("data-theme") === expectedTheme, `${expectedTheme} theme was not selectable`);
    const palette = await page.evaluate(() => {
      const rgb = value => (value.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
      const luminance = value => rgb(value).map(channel => {
        const normalized = channel / 255;
        return normalized <= .04045 ? normalized / 12.92 : ((normalized + .055) / 1.055) ** 2.4;
      }).reduce((sum, channel, index) => sum + channel * [.2126, .7152, .0722][index], 0);
      const contrast = (foreground, background) => {
        const values = [luminance(foreground), luminance(background)].sort((left, right) => right - left);
        return (values[0] + .05) / (values[1] + .05);
      };
      const key = getComputedStyle(document.querySelector("#api-key"));
      const editorElement = document.querySelector(".CodeMirror");
      const editor = getComputedStyle(editorElement);
      const body = getComputedStyle(document.body);
      const tokenRows = [...editorElement.querySelectorAll('span[class*="cm-"]')].map(token => ({
        classes: token.className,
        text: token.textContent,
        color: getComputedStyle(token).color,
        contrast: contrast(getComputedStyle(token).color, editor.backgroundColor),
      }));
      return {
        keyBackground: key.backgroundColor,
        keyColor: key.color,
        editorBackground: editor.backgroundColor,
        bodyBackground: body.backgroundColor,
        tokens: tokenRows,
      };
    });
    check(palette.keyBackground !== "rgba(0, 0, 0, 0)" && palette.keyColor, `${expectedTheme} API input had no readable palette`);
    check(palette.editorBackground !== palette.bodyBackground, `${expectedTheme} editor lost its visual boundary`);
    check(palette.tokens.some(token => token.classes.includes("cm-builtin") && /str|dict/.test(token.text)), `${expectedTheme} editor did not classify Python builtins`);
    const lowContrastTokens = palette.tokens.filter(token => token.contrast < 4.5);
    check(lowContrastTokens.length === 0, `${expectedTheme} syntax tokens fell below 4.5:1 contrast: ${JSON.stringify(lowContrastTokens)}`);
    if (process.env.CFX11_SCREENSHOT_DIR) {
      fs.mkdirSync(process.env.CFX11_SCREENSHOT_DIR, { recursive: true });
      await page.screenshot({ path: path.join(process.env.CFX11_SCREENSHOT_DIR, `cfx11-${expectedTheme}.png`), fullPage: true });
    }
  }
  await page.setViewportSize({ width: 480, height: 800 });
  const narrowNavigation = await page.evaluate(() => {
    const header = document.querySelector(".course-header").getBoundingClientRect();
    const previous = document.querySelector("#previous-lesson").getBoundingClientRect();
    const next = document.querySelector("#next-lesson").getBoundingClientRect();
    const dock = document.querySelector(".wb-dock");
    const tools = document.querySelector(".wb-tools");
    const box = element => element ? {
      bounds: Object.fromEntries(["left", "right", "width"].map(key => [key, Math.round(element.getBoundingClientRect()[key])])),
      clientWidth: element.clientWidth,
      offsetWidth: element.offsetWidth,
      scrollWidth: element.scrollWidth,
      overflowX: getComputedStyle(element).overflowX,
      minWidth: getComputedStyle(element).minWidth,
      maxWidth: getComputedStyle(element).maxWidth,
    } : null;
    return {
      headerBottom: header.bottom,
      previousWidth: previous.width,
      nextWidth: next.width,
      overflow: document.documentElement.scrollWidth - innerWidth,
      scrollX,
      html: box(document.documentElement),
      body: box(document.body),
      dock: box(dock),
      tools: box(tools),
      widestScrollContainers: [...document.querySelectorAll("body *")]
        .map(element => ({
          tag: element.tagName,
          id: element.id,
          className: String(element.className).slice(0, 100),
          clientWidth: element.clientWidth,
          scrollWidth: element.scrollWidth,
          overflowX: getComputedStyle(element).overflowX,
        }))
        .filter(item => item.scrollWidth > innerWidth + 1)
        .sort((left, right) => right.scrollWidth - left.scrollWidth)
        .slice(0, 12),
      overflowElements: [...document.querySelectorAll("body *")].map(element => {
        const bounds = element.getBoundingClientRect();
        return { element, bounds, documentRight: bounds.right + scrollX };
      }).filter(item => item.documentRight > innerWidth + 1 || item.bounds.width > innerWidth + 1)
        .sort((left, right) => Math.max(right.documentRight, right.bounds.width) - Math.max(left.documentRight, left.bounds.width))
        .slice(0, 12).map(item => ({
        tag: item.element.tagName,
        id: item.element.id,
        className: String(item.element.className).slice(0, 100),
        left: Math.round(item.bounds.left),
        right: Math.round(item.bounds.right),
        documentRight: Math.round(item.documentRight),
        width: Math.round(item.bounds.width),
        clientWidth: item.element.clientWidth,
        scrollWidth: item.element.scrollWidth,
        overflowX: getComputedStyle(item.element).overflowX,
      })),
    };
  });
  check(narrowNavigation.previousWidth > 100 && narrowNavigation.nextWidth > 100, `narrow header lesson controls were not usable: ${JSON.stringify(narrowNavigation)}`);
  check(narrowNavigation.overflow <= 1, `narrow course navigation caused horizontal overflow: ${JSON.stringify(narrowNavigation)}`);
  if (process.env.CFX11_SCREENSHOT_DIR) {
    await page.screenshot({ path: path.join(process.env.CFX11_SCREENSHOT_DIR, "cfx11-dark-narrow.png"), fullPage: true });
  }
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.locator('[data-workbench-view="session"]').click();
  await page.getByRole("button", { name: "Restart Python" }).click();
  check(await page.locator(".xblock .wb-cell-artifact:not([hidden])").count() === 0, "restarting Python left stale cell results visible");
  await page.locator('[data-workbench-view="variables"]').click();
  await page.getByRole("button", { name: "All variables", exact: true }).click();
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await page.waitForFunction(() => document.querySelector("#inspect-runtime")?.disabled === false, null, { timeout });
  check(await page.locator("#kernel-status").innerText() !== "Not started",
    `runtime refresh after restart did not initialize a session: ${await page.locator("#kernel-variables").innerText()}; page errors: ${JSON.stringify(errors)}`);
  check(!(await page.locator("#kernel-variables").innerText()).includes("shared_lesson_value"), "restart did not clear the Python namespace");
  await page.locator("#close-runtime-panel").click();

  await openNavigationLesson(page, "3-Prompting-With-Messages/36-Chatbots");
  await page.waitForFunction(() => document.querySelector("#lesson-title")?.textContent === "Chatbots", null, { timeout });
  const helperLink = page.getByRole("link", { name: "chat_helpers/gradio_interface.py" });
  await helperLink.waitFor();
  check((await helperLink.getAttribute("href")).startsWith("https://gitlab.com/nvidia/dli/content/c-fx-11-v1/"), "unlicensed helper source must remain an upstream link");

  await openNavigationLesson(page, "6-Assessment/61-Assessment");
  await page.waitForFunction(() => document.querySelector("#lesson-title")?.textContent === "Assessment", null, { timeout });
  console.log("cfx11_browser_audit: checking assessment middleware in the retained kernel");
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

  await page.goto(`http://127.0.0.1:${port}/scripts/pyodide/SKILL.html`, { waitUntil: "domcontentloaded", timeout });
  console.log("cfx11_browser_audit: checking canonical Pyodide workbench");
  await page.waitForFunction(() => document.querySelector("#pyodide-playground")?.dataset.runtimeMounted === "true", null, { timeout });
  check(await page.locator(".py-example.wb-cell").count() === 12, "canonical Pyodide workbench did not mount every real progressive cell");
  check(await page.locator(".py-example .wb-cell-workspace").count() === 12, "canonical Pyodide cells did not use the shared code-and-evidence workspace");
  check(await page.locator("[data-reference-workbench]").getAttribute("data-workbench-ready") === "true", "canonical Pyodide runtime tools did not mount");
  const firstReferenceCell = page.locator('[data-example-id="compute"]');
  await firstReferenceCell.getByRole("button", { name: "Run cell" }).click();
  await page.waitForFunction(() => document.querySelector('[data-example-id="compute"]')?.dataset.state === "running", null, { timeout });
  const helperTool = page.locator('[data-reference-workbench] [data-workbench-view="helpers"]');
  check(!(await helperTool.isDisabled()), "canonical runtime tools became unavailable while Python was busy");
  await helperTool.click();
  await page.waitForFunction(() => ["passed", "failed"].includes(document.querySelector('[data-example-id="compute"]')?.dataset.state), null, { timeout });
  check(await firstReferenceCell.getAttribute("data-state") === "passed", `canonical Pyodide compute cell failed:\n${await firstReferenceCell.innerText()}`);
  check((await firstReferenceCell.locator(".py-notebook-output").innerText()).includes('"sum": 16'), "canonical Pyodide compute cell returned the wrong value");
  check(await page.locator("[data-helper-row]").count() > 6, "canonical Pyodide helper inspector did not expose the real helper sources");
  check(await page.locator("[data-workbench-content='helpers']").isVisible(), "canonical helper view did not open");
  if (process.env.CFX11_SCREENSHOT_DIR) {
    for (const theme of ["dark", "light"]) {
      await page.evaluate(value => { document.documentElement.dataset.theme = value; }, theme);
      await page.waitForFunction(value => document.documentElement.dataset.theme === value, theme);
      await page.screenshot({ path: path.join(process.env.CFX11_SCREENSHOT_DIR, `pyodide-workbench-${theme}.png`), fullPage: true });
    }
  }
  check(errors.length === 0, `page errors: ${JSON.stringify(errors)}`);
  check(failures.length === 0, `request failures: ${JSON.stringify(failures)}`);
  console.log(`cfx11_browser_audit: PASS (${manifest.lessons.length} lessons, Pages-style Markdown 404, digest bundle, Mermaid, source-cell order, numbered collapsible navigation, header previous/next controls, shared code-and-evidence workbench, contrast-checked themes, serialized queue, in-cell input, isolated lesson kernels with shared opt-in, focused/all variables, runtime guide, direct and relay billing headers, restart, error line, chat widget, real LangChain graph PNG, live public APIs, upstream helper link, assessment middleware, canonical Pyodide interface)`);
} finally {
  await browser?.close();
  server.close();
}
