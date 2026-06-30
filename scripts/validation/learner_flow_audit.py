#!/usr/bin/env python3
"""Required static contract for progressive disclosure and interactive lab state.

The gate stays course-agnostic: it discovers course directories from course SKILL
beacons and checks shared interaction primitives plus each numbered lesson. It does
not infer GPU availability or hard-code one delivery environment.
"""
from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

for _p in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
    if (_p / "scripts" / "_bootstrap.py").exists():
        sys.path.insert(0, str(_p / "scripts"))
        break
from _bootstrap import find_repo_root

ROOT = find_repo_root(Path(__file__).resolve())
WEB = ROOT / "web"
CODE_RE = re.compile(r"code:\s*`((?:\\.|[^`\\])*)`", re.S)
DOM_CODE_RE = re.compile(r'code:\s*document\.getElementById\(["\']([^"\']+)["\']\)\.textContent\.trim\(\)')
MOUNT_RE = re.compile(r"mount(?:RunCell|CanvasFlow)\s*\(")
LAUNCHABLE_HELPER_RE = re.compile(
    r"helpers\.(?:openclawChat|terminal|sandboxExec|policyGet|sandboxNetwork|evalSandboxNetwork|evalSandboxFs)\b"
)
MODEL_HELPER_RE = re.compile(r"(?:helpers\.)?(?:chat|chatStream)\s*\(|helpers\.mountAgentChat\s*\(")
MAX_DEFAULT_OPEN_LINES = 60
LEARNING_VIEW_REQUIRED = {"01a-loop.html", "01b-react.html", "01c-tools.html", "02b-rag.html"}
LEARNING_VIEW_MIN_BLOCKS = {
    "01a-loop.html": 5,
    "01b-react.html": 2,
    "01c-tools.html": 4,
    "02a-routing.html": 2,
    "02b-rag.html": 8,
    "02c-deep.html": 2,
    "03b-openclaw.html": 1,
    "04a-safety.html": 1,
    "04b-modern-clis.html": 2,
    "04c-going-further.html": 2,
}
LEARNING_TIERS = {"applied", "deep"}
LEARNING_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class LearningBlockParser(HTMLParser):
    """Collect explicit optional blocks without pretending regex understands nesting."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, set[str]]] = []
        self.blocks: list[dict] = []
        self.active: list[dict] = []
        self.nested_lines: list[int] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        classes = set(values.get("class", "").split())
        self.stack.append((tag, classes))
        if "data-learning-tier" in values:
            if self.active:
                self.nested_lines.append(self.getpos()[0])
            block = {
                "tag": tag,
                "line": self.getpos()[0],
                "depth": len(self.stack),
                "attrs": values,
                "tags": {tag},
                "ids": {values.get("id", "")} - {""},
                "classes": set(values.get("class", "").split()),
                "text": [],
                "summary_count": 0,
                "scoped_summary_count": 0,
                "question_text": [],
                "scope_text": [],
            }
            self.blocks.append(block)
            self.active.append(block)
        for block in self.active:
            block["tags"].add(tag)
            block["ids"].update({values.get("id", "")} - {""})
            block["classes"].update(values.get("class", "").split())
            if "data-prerequisite" in values:
                block["tags"].add("data-prerequisite")
            if tag == "summary":
                block["summary_count"] += 1
                if values.get("data-localization-scope") == "en":
                    block["scoped_summary_count"] += 1

    def handle_endtag(self, tag: str) -> None:
        if self.active and self.active[-1]["tag"] == tag and self.active[-1]["depth"] == len(self.stack):
            self.active.pop()
        if self.stack:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        for block in self.active:
            block["text"].append(data)
            if any("learning-question" in classes for _, classes in self.stack):
                block["question_text"].append(data)
            if any("learning-scope" in classes for _, classes in self.stack):
                block["scope_text"].append(data)


def audit_learning_runtime(learning: str, shared: str, css: str) -> list[str]:
    findings: list[str] = []
    contract = {
        'LEARNING_DEPTH_KEY = "nemoclaw_learning_depth_v1"': "learning depth needs one versioned localStorage key",
        'return DEPTHS.has(depth) ? depth : "guided"': "first-time learners must start in Guided",
        'querySelectorAll?.("details.learning-block[data-learning-tier]")': "learning runtime must discover native optional disclosures",
        'block.open = DEPTH_RANK[depth] >= required': "saved depth must set each optional disclosure's initial state",
        'CODE_DETAILS_SELECTOR = "details.rc-code-det, details.cf-panel-code-det"': "Guided must cover RunCell and CanvasFlow code disclosures",
        'detail.dataset.learningDefaultOpen = String(detail.open)': "non-Guided views must retain each code cell's authored default",
        'detail.open = depth === "guided" ? false': "Guided must collapse interactive code by default",
        'codeObserver.observe(document.body, { childList: true, subtree: true })': "Guided must initialize code cells mounted after shared chrome",
        'mountCodeObserver();': "Guided must initialize code cells mounted after shared chrome",
        'if (onlyNew && initialized) return;': "lazy editor mutations must not overwrite a learner's local code reveal",
        'select.addEventListener("change"': "learners need a direct global depth override",
        'window.addEventListener("beforeprint"': "printing must temporarily open native optional disclosures",
        'window.addEventListener("afterprint"': "printing must restore the learner's disclosure state",
        'window.addEventListener("hashchange", revealHashTarget)': "deep links must reveal a target inside a collapsed disclosure",
        'target?.closest("details.learning-block[data-learning-tier]")': "deep links must reveal a target inside a collapsed disclosure",
        'mountLearningView()': "learning profile needs a shared mount entry point",
        'if (!supportsLearningView()) return;': "learning controls must stay on course home and numbered lessons",
        'startsWith("en")': "the pilot must remain limited to the English source course",
        'storage()?.setItem(LEARNING_DEPTH_KEY, "guided")': "hidden-selector pilot must reset every page to Guided",
        'applyLearningDepth("guided")': "hidden-selector pilot must render every page in Guided",
    }
    for token, message in contract.items():
        _need(findings, token in learning, message)
    _need(findings, 'import { mountLearningView } from "./_learning.js";' in shared and
          "mountLearningView(); mountThemeToggle()" in shared,
          "_shared.js must mount the learning view on every topbar page")
    _need(findings, "markLiveArtifacts();" in shared,
          "shared page boot must mark every artifact placeholder")
    _need(findings, ".learning-block-body { display: block !important; }" in css,
          "print must restore every optional learning block body")
    _need(findings, '.learning-block[data-learning-tier="deep"]' in css and ".learning-scope" in css,
          "applied and deep sections need text-backed visual scope cues")
    _need(findings, ".course-artifact::before" in css and
          "content: attr(data-artifact-label)" in css and "--artifact:" in css,
          "live artifacts need a restrained text-backed color cue")
    _need(findings, ".course-artifact:empty { display: none; }" in css,
          "unmounted artifact placeholders must not add blank page height")
    _need(findings, ".learning-depth-control { display: none; }" in css,
          "Guided pilot must retain but hide the global depth selector")
    _need(findings, ".course-artifact .chatui-log" in css and "overscroll-behavior: contain" in css,
          "live artifacts need a bounded transcript instead of unbounded page growth")
    _need(findings, "fetch(" not in learning and "XMLHttpRequest" not in learning and "sendBeacon" not in learning,
          "learning profile runtime must remain local and telemetry-free")
    return findings


def audit_page_assistant(assistant: str, shared: str, chat: str, css: str) -> list[str]:
    """Keep the session-aware assistant bounded and grounded in prose plus exact source."""
    findings: list[str] = []
    contract = {
        'import { mountAgentChat } from "./_chat.js";': "page assistant must reuse the tested ReAct artifact",
        'const pt = document.documentElement.lang.toLowerCase().startsWith("pt")': "page assistant must localize itself from the document language",
        'assistant: "ASSISTENTE DO CURSO"': "page assistant needs Brazilian Portuguese chrome",
        'if (!location.pathname.includes("/nemoclaw/")) return;': "page assistant must stay scoped to course pages",
        'pageId: String(item.pageId || "")': "Course Assistant page grounding must persist with its session",
        'initialContext: attachedPage ? async () => ({ label: (pt ? "página + índice de código · " : "page + code index · ") + attachedPage.id': "Course Assistant must seed its attached prose and code index as inspectable context",
        'name: "list_course_pages"': "page assistant must expose the course map to its ReAct loop",
        'name: "search_course_pages"': "page assistant must search the course before guessing which page matters",
        'export async function searchCoursePages': "course search must remain independently testable without a model call",
        'return JSON.stringify(await searchCoursePages(query, readPage, catalog), null, 2);': "assistant search tool must return endpoint-safe text from the tested course-search helper",
        'name: "read_course_page"': "page assistant must let the ReAct loop read supporting course pages",
        'name: "list_course_code"': "Course Assistant must enumerate exact lesson code before reading it",
        'name: "read_course_source"': "Course Assistant must read exact lesson artifact source through one stable URI",
        'name: "list_course_runtime_files"': "Course Assistant must enumerate shared runtime modules",
        'name: "read_course_runtime_source"': "Course Assistant must read allow-listed shared runtime source",
        'uri: `${id}#${item.id}`': "lesson code index must expose one stable source URI",
        'never invent an implementation or claim source is private or inaccessible': "Course Assistant prompt must forbid invented or inaccessible-source claims",
        'Use the code-reading tools for exact source': "attached page context must advertise exact code access",
        '"Show me this page\'s code"': "Course Assistant must make source access discoverable without tool-name knowledge",
        ').filter(result => result.score > 0).sort((a, b) => b.score - a.score).slice(0, 4)': "course search must bound tool output before it enters context",
        'recursionLimit: 24': "page assistant must bound ReAct recursion",
        'data-course-assistant-close': "page assistant needs an explicit close control",
        'event.key === "Escape"': "page assistant needs keyboard dismissal",
        'class="course-assistant-resizer" role="separator"': "page assistant needs an accessible drag handle",
        'resizer.setPointerCapture(event.pointerId)': "page assistant resize must retain pointer capture during drag",
        'Math.floor(window.innerWidth * 0.9)': "page assistant resize must stop at 90 percent of the viewport",
        'event.key === "ArrowLeft"': "page assistant resize must support keyboard adjustment",
        'COURSE ASSISTANT': "shared assistant must use its course-wide name",
        'nemoclaw_course_assistant_sessions_v1': "Course Assistant sessions need a stable local cache key",
        'export function loadCourseAssistantStore': "Course Assistant local sessions must remain independently testable",
        '<button type="button" data-course-assistant-new>': "Course Assistant needs an explicit new-session control",
        'data-course-assistant-delete': "Course Assistant needs an explicit session-delete control",
        'aria-label="${copy.renameLabel}"': "Course Assistant needs an accessible inline session rename control",
        'data-course-assistant-use-page': "Course Assistant needs an explicit page-attachment control",
        'store.sessions = store.sessions.map': "Course Assistant must normalize and cap live plus stored state",
        'MAX_SESSION_HISTORY_CHARS = 100000': "Course Assistant transcripts must fit browser-local storage",
        'MAX_SESSION_ACTIVITY_CHARS = 20000': "Course Assistant visible activity must remain bounded in browser-local storage",
        'return { chars: serialized.length, sessions: store.sessions.length }': "Course Assistant must expose saved-size observability",
        'current && !current.history.length && !current.activity && !current.artifact && current.title === "New session"': "Course Assistant must reuse only a truly empty session",
        'initialHistory: session.history': "Course Assistant must restore the active session transcript",
        'initialActivity: session.activity': "Course Assistant must restore persisted agent activity independently of the page",
        'current.activity = cleanActivity(meta?.activity)': "Course Assistant must save visible agent activity with every turn snapshot",
        'data-course-assistant-view="history"': "Course Assistant needs an explicit persistent History view",
        'class="course-assistant-history"': "Course Assistant History needs a page-independent rendered surface",
        'data-course-history-copy': "Course Assistant must let learners copy persisted activity",
        'onUserMessage: question =>': "Course Assistant must name a session before a failed model turn can strand it",
        'onTurnSnapshot: (history, meta) =>': "Course Assistant must persist in-flight and failed turns",
        'opts.onTurnSnapshot(cleanHistory(items), { state, activity }, ctx)': "shared chat must snapshot a turn before completion",
        'const activitySnapshot = () =>': "shared chat must persist visible ReAct activity, not only model-context messages",
        'ctx.view.updateTool(c.el': "shared chat must capture completed tool results in persisted activity",
        'initialActivity: opts.initialActivity': "shared agent chat must forward restored activity into its UI runtime",
        'window.addEventListener("pagehide", snapshotBeforeNavigation': "shared chat must flush the latest streamed text during navigation",
        'onUserMessage: opts.onUserMessage': "shared chat must forward the preflight session-title hook",
        'onTurnSnapshot: opts.onTurnSnapshot': "shared chat must forward transcript snapshots",
        'onAssistantMessage: opts.onAssistantMessage': "shared chat must forward completed answers for deterministic artifact capture",
        'opts.onUserMessage(q, ctx)': "shared chat must invoke session titling before the model request",
        'onHistoryChange: history =>': "Course Assistant must persist completed turns",
        'compactAtTokens: 12000': "Course Assistant must set an explicit compaction threshold",
        'compactKeepMessages: 6': "Course Assistant compaction must preserve recent verbatim turns",
        'runtime.llm.invoke([': "Course Assistant compaction must summarize old turns with the active model",
        'ctx.history = ctx.replaceHistory([': "Course Assistant compaction must replace old history with durable memory",
        'ctx.thread = ctx.rotateThread()': "Course Assistant compaction must rotate to a fresh bounded agent thread",
        'name: "queue_course_artifact"': "Course Assistant must queue generated browser code into a real artifact view",
        'export function parseInlineCourseSourceIntent': "Course Assistant must detect source arguments emitted as plain JSON",
        'recoverInlineToolIntent: async answer =>': "Course Assistant must recover a model that prints source arguments instead of invoking its tool",
        'ctx.view.discardAnswer()': "shared agent chat must replace recovered tool JSON with the synthesized answer",
        'export function artifactFromMarkdown': "Course Assistant must detect generated HTML/JavaScript without model tool compliance",
        'onAssistantMessage: answer =>': "Course Assistant must auto-fill fenced browser code after completed replies",
        'data-course-assistant-view="artifact"': "Course Assistant needs a discoverable Artifact tab",
        'data-course-artifact-html': "Course Assistant Artifact view needs an editable HTML surface",
        'sandbox="allow-scripts"': "Course Assistant artifact preview must run in an origin-isolated sandbox",
        'default-src \'none\'': "Course Assistant artifact preview must block ambient network and parent access",
        'URL.createObjectURL(new Blob([': "Course Assistant artifact preview must avoid fragile srcdoc injection",
        'window.course=api;window.helpers=new Proxy': "Course Assistant artifact sandbox must expose bounded course and lesson-helper bridges",
        'filter(name => !["embed", "cosineSim"].includes(name))': "Course Assistant must reject lesson helpers absent from the artifact sandbox",
        'input.length > 16': "Course Assistant embedding bridge must bound artifact requests",
        'export function artifactJavaScriptIssue': "Course Assistant must validate generated JavaScript without a model call",
        'Artifact embedding is asynchronous. Assign its result with await course.embed(...) or await helpers.embed(...)': "Course Assistant must reject unawaited embedding requests through either alias",
        'Artifact embed inputType must be': "Course Assistant must reject unsupported embedding input types",
        '(async () => {\\n${javascript}\\n})();': "Course Assistant runner must support top-level await without exposing imports",
        'Artifact rejected: ${issue}': "Course Assistant tool must return invalid artifact code to the agent for correction",
        'class="course-artifact-api"': "Course Assistant editor must show its asynchronous embedding contract",
        'data-course-artifact-clear': "Course Assistant must expose a preview clear control",
        'flushArtifactSave(); clearArtifactPreview(copy.previewCleared);': "Course Assistant preview clear must preserve artifact source",
        'data-course-artifact-delete': "Course Assistant must separate destructive artifact deletion",
        'window.CodeMirror.fromTextArea': "Course Assistant artifact code needs the course editor when available",
        'window.CodeMirror.defineMode("course-html"': "Course Assistant HTML editor needs syntax-aware tokens without another CDN dependency",
        'The course has no generic pasteable code cell': "Course Assistant must reject nonexistent paste-into-cell guidance",
        'The sandbox provides the asynchronous course.embed API': "Course Assistant prompt must teach the artifact bridge instead of inventing imports",
        'always use await course.embed': "Course Assistant prompt must state that embedding calls are asynchronous",
        'No other helpers.* API is available': "Course Assistant prompt must distinguish lesson helpers from artifact APIs",
        'activateView("artifact")': "generated artifacts must open the real Artifact view",
        'mountCourseLicenseNote': "shared chrome must mount the course license note",
        'Course-authored prose, example code, and original diagrams': "license note must state the exact Apache-2.0 scope",
        'Named external material keeps its own terms': "license note must not relicence cited external material",
    }
    for token, message in contract.items():
        _need(findings, token in assistant or token in shared or token in chat, message)
    _need(findings, "mountCourseAssistant({ embed });" in shared,
          "shared chrome must mount the page assistant on every course page")
    _need(findings, "initialContext" in chat and "ctx.view.tool(label" in chat,
          "shared ReAct artifact must expose initial page context as a source chip")
    _need(findings, ".course-assistant-launcher" in css and "width: 32px; height: 32px" in css,
          "page assistant launcher must remain compact")
    _need(findings, ".course-assistant-panel { width: 100vw;" in css,
          "page assistant must fit a narrow viewport")
    _need(findings, "max-width: 90vw" in css and ".course-assistant-resizer" in css and
          "cursor: col-resize" in css and ".course-assistant-resizer { display: none; }" in css,
          "page assistant drag resize needs a 90vw desktop cap and mobile fallback")
    _need(findings, ".course-assistant-sessions" in css and "grid-template-columns" in css,
          "Course Assistant session controls need a bounded responsive layout")
    _need(findings, ".course-assistant-artifact" in css and "min-height: 0" in css and
          ".course-artifact-editors" in css and ".course-assistant-artifact iframe" in css,
          "Course Assistant Artifact view needs a bounded responsive layout")
    _need(findings, ".course-assistant-history" in css and "white-space: pre-wrap" in css,
          "Course Assistant persistent History needs a bounded readable layout")
    _need(findings, ".course-assistant-panel > header button {" in css and
          ".course-assistant-panel header button {" not in css,
          "Course Assistant close-button sizing must not leak into nested History controls")
    _need(findings, assistant.count("artifactJavaScriptIssue(javascript)") >= 2 and
          "artifactJavaScriptIssue(artifact.javascript)" in assistant,
          "Course Assistant must validate manual runs, tool queues, and fenced-code capture")
    _need(findings, ".course-artifact-api" in css,
          "Course Assistant artifact API contract needs visible bounded styling")
    _need(findings, ".course-assistant-body .chatui-log { max-height: none !important; min-height: 0; flex: 1; }" in css,
          "page assistant transcript must stay bounded inside its side view")
    return findings


def audit_course_source_runtime(langchain: str) -> list[str]:
    """Expose exact public lesson/runtime source without creating an arbitrary file reader."""
    findings: list[str] = []
    contract = {
        'const COURSE_RUNTIME_FILES = [': "course runtime source needs an explicit public allow-list",
        'const COURSE_HTML_CACHE = new Map()': "prose and code-index reads must share one page fetch",
        'COURSE_RUNTIME_FILES.find(([name]) => name === safe)': "runtime source reads must remain allow-listed",
        'script[type="text/plain"][id]': "course source index must discover text-backed lesson artifacts",
        'script[type="module"]:not([src])': "course source index must discover inline page modules",
        'export async function courseCodeArtifacts': "lesson code index must remain independently testable",
        '.map(({ source: _source, ...metadata }) => metadata)': "lesson code index must not inline every source body",
        'export async function courseCode(pageId, artifactId)': "exact lesson source must remain readable by artifact id",
        'export function courseRuntimeFiles': "shared runtime source needs an independently testable index",
        'export async function courseRuntimeSource(file)': "allow-listed shared runtime source must remain readable",
        'fetch("scripts/" + safe': "runtime source must resolve from the public course scripts directory",
    }
    for token, message in contract.items():
        _need(findings, token in langchain, message)
    return findings


def audit_deep_research_artifact(text: str) -> list[str]:
    """Keep 02c observable while parallel workers are active, not only after they finish."""
    findings: list[str] = []
    match = re.search(r'<script type="text/plain" id="deep-src">(.*?)</script>', text, re.S)
    source = match.group(1) if match else ""
    contract = {
        'class="research-board" aria-label="Live research operations"': "02c needs a live HTML operation board",
        'class="research-thread-rail"': "02c needs a left-aligned rail for active workers",
        'card.tabIndex = 0': "02c worker panels must be keyboard focusable",
        'role="status" aria-live="polite"': "02c worker progress must be announced while it changes",
        '(token) => streamWorker(worker, token)': "02c must stream each worker into its own panel",
        'Promise.all(branches.map(runBranch))': "02c workers must retain parallel fan-out",
        'worker.stream.scrollTop = worker.stream.scrollHeight': "02c active worker output must follow its own stream",
        's wall time vs " + serial.toFixed(1) + "s serial': "02c must preserve the parallel-versus-serial lesson without a timing SVG",
        '.research-thread-rail { display: flex; justify-content: flex-start;': "02c worker rail must stay left-aligned",
        'overflow-x: auto; overscroll-behavior-inline: contain;': "02c worker rail must remain horizontally inspectable",
        '.research-thread-stream { flex: 1; min-height: 0;': "02c worker output must use bounded internal scrolling",
        'const MATERIAL_TOPICS = [': "02c materials branch needs planner-visible supported topics",
        '\\"source\\":\\"materials\\"|\\"section\\"': "02c planner schema must distinguish curated materials from course sections",
        'Do not claim the materials branch searches the open web.': "02c must describe its curated search boundary honestly",
        'source === "materials"': "02c must route curated-material branches through the local index",
        'gap ? "gap" : "done"': "02c must surface partial coverage instead of presenting it as complete",
        'const gaps = results.filter(r => r.gap).length': "02c summary must report coverage gaps",
    }
    for token, message in contract.items():
        _need(findings, token in text or token in source, message)
    _need(findings, "helpers.diagramSVG(" not in source and "helpers.ganttBarsSVG(" not in source,
          "02c live artifact must not replace active workers with wait-then-render SVGs")
    _need(findings, 'source === "web"' not in source and '\\"source\\":\\"web\\"|\\"section\\"' not in source,
          "02c curated materials search must not be mislabeled as open-web search")
    return findings


def audit_course_assistant_handoff(text: str) -> list[str]:
    findings: list[str] = []
    contract = {
        "Keep the Course Assistant with you": "04c must introduce the persistent Course Assistant",
        'id="open-course-assistant"': "04c needs a direct Course Assistant launch control",
        'document.querySelector(".course-assistant-launcher")?.click()': "04c launch control must open the shared assistant",
        "compacts older turns into durable memory": "04c must explain session compaction",
        "sessions stay in this browser": "04c must explain local session persistence",
    }
    for token, message in contract.items():
        _need(findings, token in text, message)
    _need(findings, "capstone-artifact" not in text and "capstone-cell" not in text and "helpers.mountAgentChat" not in text,
          "04c must not duplicate the always-available Course Assistant artifact")
    return findings


def audit_learning_lesson(path: Path, text: str) -> list[str]:
    findings: list[str] = []
    rel = path.relative_to(ROOT).as_posix()
    parser = LearningBlockParser()
    parser.feed(text)
    if path.name in LEARNING_VIEW_REQUIRED:
        _need(findings, bool(parser.blocks), f"{rel}: Module 1 learning-view pilot needs optional narrative blocks")
    minimum = LEARNING_VIEW_MIN_BLOCKS.get(path.name, 0)
    if minimum:
        _need(findings, len(parser.blocks) >= minimum,
              f"{rel}: Guided reading path needs at least {minimum} intentional disclosures; found {len(parser.blocks)}")
    for line in parser.nested_lines:
        findings.append(f"{rel}:{line}: learning blocks must not nest")
    seen: set[str] = set()
    for block in parser.blocks:
        line = block["line"]
        attrs = block["attrs"]
        tier = attrs.get("data-learning-tier", "")
        block_id = attrs.get("data-learning-id", "")
        question = " ".join(" ".join(block["question_text"]).split())
        scope = " ".join(" ".join(block["scope_text"]).split())
        content = " ".join(" ".join(block["text"]).split())
        _need(findings, block["tag"] == "details" and "learning-block" in block["classes"],
              f"{rel}:{line}: optional narrative must use details.learning-block")
        _need(findings, "open" in attrs,
              f"{rel}:{line}: optional disclosure must default open without JavaScript")
        _need(findings, attrs.get("data-localization-scope") == "en-shell",
              f"{rel}:{line}: English pilot disclosure needs a localization-neutral en-shell")
        _need(findings, block["summary_count"] == 1 and "learning-block-body" in block["classes"],
              f"{rel}:{line}: optional disclosure needs one summary and one learning-block-body")
        _need(findings, block["scoped_summary_count"] == 1,
              f"{rel}:{line}: inline English question must be excluded from locale prose comparison")
        _need(findings, tier in LEARNING_TIERS,
              f"{rel}:{line}: data-learning-tier must be applied or deep")
        _need(findings, bool(block_id) and bool(LEARNING_ID_RE.fullmatch(block_id)),
              f"{rel}:{line}: data-learning-id needs a stable kebab-case value")
        _need(findings, block_id not in seen, f"{rel}:{line}: duplicate data-learning-id {block_id!r}")
        seen.add(block_id)
        question_words = re.findall(r"[A-Za-z0-9'-]+", question)
        _need(findings, 4 <= len(question_words) <= 10 and question.endswith("?"),
              f"{rel}:{line}: inline question needs 4-10 words and a question mark; got {len(question_words)}")
        _need(findings, bool(re.fullmatch(r"(?:Applied|Deep) · [A-Za-z]+", scope)),
              f"{rel}:{line}: scope cue must name its tier and local purpose")
        _need(findings, len(content.split()) >= 20,
              f"{rel}:{line}: optional block is too small to justify a learning tier")
        artifact_mode = attrs.get("data-learning-artifact", "")
        exercise_mode = attrs.get("data-learning-exercise", "")
        cell_ids = {value for value in block["ids"] if value.startswith("cell-") or value.endswith("-artifact")}
        _need(findings, artifact_mode in {"", "optional"},
              f"{rel}:{line}: data-learning-artifact must be optional when present")
        _need(findings, not artifact_mode or (tier in LEARNING_TIERS and bool(cell_ids)),
              f"{rel}:{line}: an optional artifact needs an Applied or Deep block and a cell")
        _need(findings, exercise_mode in {"", "optional"},
              f"{rel}:{line}: data-learning-exercise must be optional when present")
        _need(findings, not exercise_mode or artifact_mode == "optional",
              f"{rel}:{line}: an optional exercise must explicitly declare its artifact optional")
        forbidden_tags = {"h1", "form", "data-prerequisite"} & block["tags"]
        forbidden_classes = {"hero", "warn"} & block["classes"]
        forbidden_ids = {value for value in block["ids"] if value in {"journey-map", "key-panel", "claw-status"}}
        if artifact_mode != "optional":
            forbidden_ids.update(cell_ids)
        _need(findings, not forbidden_tags and not forbidden_classes and not forbidden_ids,
              f"{rel}:{line}: optional block contains core, prerequisite, warning, or exercise UI")
        _need(findings, exercise_mode == "optional" or not re.search(r"\b(?:Before you continue|Try it)\b", content, re.I),
              f"{rel}:{line}: exercises and page checks must remain in the core narrative")
    return findings


def _need(findings: list[str], ok: bool, message: str) -> None:
    if not ok:
        findings.append(message)


def audit_runtime_sources(canvas: str, chat: str) -> list[str]:
    """Check behavior-bearing shared primitives, not page-specific CSS selectors."""
    findings: list[str] = []
    canvas_contract = {
        'class="cf-intro rc-intro"': "RunCell must render its focus-driving intro before implementation details",
        'class="rc-out cell-output-panel" role="status"': "RunCell output must be a programmatic status region",
        '_emptyState("⏹ stopped")': "RunCell Stop must leave an explicit stopped state",
        'if (codeDet && !codeDet.open) codeDet.open = true;': "RunCell errors must reveal code even without CodeMirror",
        '_cellBtnHTML("reset", "↺ Reset", "rc-reset"': "RunCell must expose Reset",
        'btn.textContent = "⏹ Stop"': "RunCell Run must become Stop while work is active",
        '_cellBtnHTML("reset", "↺ Reset code", "cf-btn cf-btn-reset"': "CanvasFlow must expose whole-flow Reset",
        'b.textContent = "⏹ Stop"': "CanvasFlow Run all must become Stop while work is active",
        'resultsDet.open = true': "CanvasFlow must reveal results when a node runs",
        'class="cf-status-bar" role="status"': "CanvasFlow completion state must be a programmatic status region",
        "running = false, runEpoch = 0": "CanvasFlow resets must invalidate stale async completion",
        "const epoch = ++runEpoch;": "RunCell resets must invalidate stale async completion",
    }
    for token, message in canvas_contract.items():
        _need(findings, token in canvas, message)
    error_scope = canvas.find("const _rcCode = cm ? cm.getValue() : ta.value;")
    open_error = canvas.find("if (codeDet && !codeDet.open) codeDet.open = true;", error_scope)
    cm_only = canvas.find("if (_ep !== null && cm)", error_scope)
    _need(findings, error_scope >= 0 and open_error > error_scope and cm_only > open_error,
          "RunCell errors must reveal code before the CodeMirror-only line marker")
    _need(findings, "out.scrollIntoView" not in canvas,
          "RunCell must not move the page viewport after Run")

    chat_contract = {
        'class="chatui-state" role="status"': "chat readiness/run/error state must be programmatically visible",
        "const setDisabled = (blocked": "chat artifacts need a reusable prerequisite gate",
        'sendBtn.textContent = "⏹ Stop"': "chat Send must become Stop while work is active",
        'button class="chatui-reset"': "chat artifacts must expose New chat/Reset",
        'setState("Error. Read the message, then edit or retry."': "chat errors need a stable visible state",
        'class="da-console-state" role="status"': "console readiness/run/error state must be programmatically visible",
        'class="da-chip da-stop"': "console commands must expose Stop",
        'runAC = new AbortController()': "console Stop must own an AbortController",
        'onSubmit(line, con, { signal: runAC.signal })': "console commands must receive the Stop signal",
        'class="da-chip da-clear"': "console commands must expose Clear",
        "resetEpoch = 0": "chat Reset must invalidate stale async completion",
        'el.classList.add("course-artifact")': "live artifacts need the shared artifact cue",
        "markLiveArtifact(el);": "live chat artifacts need the shared artifact cue",
        "markLiveArtifact(root);": "live console artifacts need the shared artifact cue",
        'el.id.endsWith("-artifact")': "artifact cues must not spill onto ordinary teaching cells",
        "export function markLiveArtifacts(root = document)": "artifact placeholders need cues before optional mounts run",
    }
    for token, message in chat_contract.items():
        _need(findings, token in chat, message)
    _need(findings, "input.scrollIntoView" not in chat,
          "console completion must not move the page viewport")
    return findings


def _mount_blocks(text: str) -> list[tuple[int, str, bool]]:
    mounts = list(MOUNT_RE.finditer(text))
    blocks: list[tuple[int, str, bool]] = []
    for index, mount in enumerate(mounts):
        end = mounts[index + 1].start() if index + 1 < len(mounts) else len(text)
        blocks.append((mount.start(), text[mount.start():end], text.startswith("mountRunCell", mount.start())))
    return blocks


def _mask_js_literals(text: str) -> str:
    """Blank strings, templates, and comments while preserving syntax positions."""
    chars = list(text)
    index = 0
    while index < len(chars):
        char = chars[index]
        nxt = chars[index + 1] if index + 1 < len(chars) else ""
        if char in {'"', "'", "`"}:
            quote = char
            chars[index] = " "
            index += 1
            while index < len(chars):
                if chars[index] == "\\":
                    chars[index] = " "
                    if index + 1 < len(chars):
                        chars[index + 1] = " " if chars[index + 1] != "\n" else "\n"
                    index += 2
                    continue
                end = chars[index] == quote
                if chars[index] != "\n":
                    chars[index] = " "
                index += 1
                if end:
                    break
            continue
        if char == "/" and nxt == "/":
            while index < len(chars) and chars[index] != "\n":
                chars[index] = " "
                index += 1
            continue
        if char == "/" and nxt == "*":
            chars[index] = chars[index + 1] = " "
            index += 2
            while index + 1 < len(chars) and not (chars[index] == "*" and chars[index + 1] == "/"):
                if chars[index] != "\n":
                    chars[index] = " "
                index += 1
            if index + 1 < len(chars):
                chars[index] = chars[index + 1] = " "
                index += 2
            continue
        index += 1
    return "".join(chars)


def _canvas_node_count(block: str) -> int | None:
    masked = _mask_js_literals(block)
    match = re.search(r"\bnodes\s*:\s*\[", masked)
    if not match:
        return None
    square_depth = 1
    curly_depth = 0
    count = 0
    for char in masked[match.end():]:
        if char == "[":
            square_depth += 1
        elif char == "]":
            square_depth -= 1
            if square_depth == 0:
                return count
        elif char == "{" and square_depth == 1:
            if curly_depth == 0:
                count += 1
            curly_depth += 1
        elif char == "}" and square_depth == 1 and curly_depth:
            curly_depth -= 1
    return None


def audit_lesson(path: Path, text: str) -> list[str]:
    findings: list[str] = []
    rel = path.relative_to(ROOT).as_posix()
    blocks = _mount_blocks(text)
    model_call = MODEL_HELPER_RE.search(text)
    if model_call:
        model_markers = [text.find('id="key-status"'), text.find('data-prerequisite="model"')]
        _need(findings, any(0 <= marker < model_call.start() for marker in model_markers),
              f"{rel}: model-dependent lesson must expose model readiness before use")

    if LAUNCHABLE_HELPER_RE.search(text):
        first_call = LAUNCHABLE_HELPER_RE.search(text).start()
        launchable_markers = [text.find('id="claw-status"'), text.find('data-prerequisite="launchable"')]
        _need(findings, any(0 <= marker < first_call for marker in launchable_markers),
              f"{rel}: launchable-dependent lesson must expose launchable readiness before use")
        _need(findings, "03a-kickstart.html" in text,
              f"{rel}: launchable-dependent lesson must link its setup path to Module 3a")

    for start, block, is_run_cell in blocks:
        if not is_run_cell:
            line = text[:start].count("\n") + 1
            node_count = _canvas_node_count(block)
            _need(findings, node_count is not None and node_count >= 2,
                  f"{rel}:{line}: CanvasFlow needs at least two visible steps; use RunCell for one operation")
            continue
        line = text[:start].count("\n") + 1
        code_match = CODE_RE.search(block)
        dom_match = DOM_CODE_RE.search(block)
        if code_match:
            code = code_match.group(1)
            options = block[:code_match.start()]
        elif dom_match:
            source_id = re.escape(dom_match.group(1))
            source_match = re.search(
                rf'<script\b[^>]*\bid=["\']{source_id}["\'][^>]*>(.*?)</script>', text, re.S | re.I)
            if not source_match:
                findings.append(f"{rel}:{line}: RunCell DOM code source {dom_match.group(1)!r} does not resolve")
                continue
            code = source_match.group(1)
            options = block[:dom_match.start()]
        else:
            findings.append(f"{rel}:{line}: RunCell has no inspectable code literal or DOM source")
            continue
        _need(findings, bool(re.search(r"\blabel\s*:\s*[\"']", options)),
              f"{rel}:{line}: RunCell needs a learner-facing label")
        if re.search(r"\bopenCode\s*:\s*true\b", options):
            lines = code.count("\n") + 1
            _need(findings, lines <= MAX_DEFAULT_OPEN_LINES,
                  f"{rel}:{line}: default-open implementation has {lines} lines; limit is {MAX_DEFAULT_OPEN_LINES}")
            _need(findings, bool(re.search(r"\bintro\s*:\s*[\"']", options)),
                  f"{rel}:{line}: default-open implementation needs a focus-driving intro")

        mounts_live_artifact = "helpers.mountChatUI" in code or "helpers.mountAgentChat" in code or "helpers.mountConsole" in code
        uses_launchable = bool(LAUNCHABLE_HELPER_RE.search(code))
        if mounts_live_artifact and uses_launchable:
            _need(findings, bool(re.search(r"\bdisabled\s*:", code)),
                  f"{rel}:{line}: launchable artifact must disable input until its prerequisite is ready")
            _need(findings, bool(re.search(r"\bdisabledMsg\s*:", code)),
                  f"{rel}:{line}: disabled launchable artifact must explain how to become ready")
            _need(findings, "signal: ctx.signal" in code,
                  f"{rel}:{line}: launchable artifact must pass its Stop signal into long-running helpers")
    return findings


def course_dirs() -> list[Path]:
    dirs = []
    for skill in WEB.glob("*/SKILL.html"):
        text = skill.read_text(encoding="utf-8", errors="ignore")
        if '"level": "course"' in text and '"surface": "web"' in text:
            dirs.append(skill.parent)
    return sorted(dirs)


def audit_home(text: str) -> list[str]:
    findings: list[str] = []
    _need(findings, "CPU-based" in text and "do not require a learner-managed GPU" in text,
          "web/nemoclaw/index.html: setup must state the CPU baseline and that learner-managed GPU hardware is not required")
    return findings


def audit_workflow_wiring(gitlab: str, github: str, pre_push: str, bundle: str) -> list[str]:
    findings: list[str] = []
    self_test = "python3 scripts/validation/learner_flow_audit.py --self-test"
    _need(findings, self_test in gitlab,
          ".gitlab-ci.yml: required test job must run learner-flow mutation tests")
    _need(findings, self_test in github,
          ".github/workflows/pages.yml: Pages test job must run learner-flow mutation tests")
    _need(findings, "learner_flow_audit.py\" --self-test" in pre_push,
          "scripts/git-hooks/pre-push: local push gate must run learner-flow mutation tests")
    _need(findings, "import learner_flow_audit as lfa" in bundle and
          '("learner_flow", "Learner interaction flow", "required"' in bundle and
          "learner_flow_find = lfa.audit_tree()" in bundle,
          "scripts/validation/validate_bundle.py: learner-flow audit must remain a required release suite")
    return findings


def audit_tree(root: Path = ROOT) -> list[str]:
    findings = audit_runtime_sources(
        (root / "web/nemoclaw/scripts/_canvas.js").read_text(encoding="utf-8"),
        (root / "web/nemoclaw/scripts/_chat.js").read_text(encoding="utf-8"),
    )
    findings.extend(audit_learning_runtime(
        (root / "web/nemoclaw/scripts/_learning.js").read_text(encoding="utf-8"),
        (root / "web/nemoclaw/scripts/_shared.js").read_text(encoding="utf-8"),
        (root / "web/nemoclaw/styles/_style.css").read_text(encoding="utf-8"),
    ))
    findings.extend(audit_page_assistant(
        (root / "web/nemoclaw/scripts/_course_assistant.js").read_text(encoding="utf-8"),
        (root / "web/nemoclaw/scripts/_shared.js").read_text(encoding="utf-8"),
        (root / "web/nemoclaw/scripts/_chat.js").read_text(encoding="utf-8"),
        (root / "web/nemoclaw/styles/_style.css").read_text(encoding="utf-8"),
    ))
    findings.extend(audit_course_source_runtime(
        (root / "web/nemoclaw/scripts/_langchain.js").read_text(encoding="utf-8"),
    ))
    findings.extend(audit_deep_research_artifact(
        (root / "web/nemoclaw/02c-deep.html").read_text(encoding="utf-8"),
    ))
    findings.extend(audit_course_assistant_handoff(
        (root / "web/nemoclaw/04c-going-further.html").read_text(encoding="utf-8"),
    ))
    discovered = course_dirs() if root == ROOT else []
    for course in discovered:
        for page in sorted(course.glob("0*.html")):
            text = page.read_text(encoding="utf-8")
            findings.extend(audit_lesson(page, text))
            findings.extend(audit_learning_lesson(page, text))
    home = (root / "web/nemoclaw/index.html").read_text(encoding="utf-8")
    findings.extend(audit_home(home))
    findings.extend(audit_workflow_wiring(
        (root / ".gitlab-ci.yml").read_text(encoding="utf-8"),
        (root / ".github/workflows/pages.yml").read_text(encoding="utf-8"),
        (root / "scripts/git-hooks/pre-push").read_text(encoding="utf-8"),
        (root / "scripts/validation/validate_bundle.py").read_text(encoding="utf-8"),
    ))
    return findings


def self_test() -> list[str]:
    """Mutation tests prove each high-risk rule detects the regression it names."""
    misses: list[str] = []
    expected_course = ROOT / "web/nemoclaw"
    if expected_course not in course_dirs():
        misses.append("course discovery did not find the current web course beacon")
    canvas = (ROOT / "web/nemoclaw/scripts/_canvas.js").read_text(encoding="utf-8")
    chat = (ROOT / "web/nemoclaw/scripts/_chat.js").read_text(encoding="utf-8")
    runtime_mutations = [
        ("ignored RunCell intro", canvas.replace('class="cf-intro rc-intro"', 'class="rc-intro"', 1), chat, "focus-driving intro"),
        ("blank RunCell stop", canvas.replace('_emptyState("⏹ stopped")', 'out.innerHTML = ""', 1), chat, "explicit stopped state"),
        ("console auto-scroll", canvas, chat.replace('input.focus();', 'input.focus(); input.scrollIntoView();', 1), "must not move"),
        ("missing chat prerequisite gate", canvas, chat.replace("const setDisabled = (blocked", "const ignoreDisabled = (blocked", 1), "prerequisite gate"),
        ("missing chat reset epoch", canvas, chat.replace("resetEpoch = 0", "resetEpochMissing = 0", 1), "stale async completion"),
        ("missing artifact cue", canvas, chat.replace('el.classList.add("course-artifact")', 'el.classList.add("ordinary-cell")', 1), "artifact cue"),
    ]
    for label, mutated_canvas, mutated_chat, expected in runtime_mutations:
        if not any(expected in finding for finding in audit_runtime_sources(mutated_canvas, mutated_chat)):
            misses.append(f"detector missed {label}")

    learning = (ROOT / "web/nemoclaw/scripts/_learning.js").read_text(encoding="utf-8")
    shared = (ROOT / "web/nemoclaw/scripts/_shared.js").read_text(encoding="utf-8")
    css = (ROOT / "web/nemoclaw/styles/_style.css").read_text(encoding="utf-8")
    learning_cases = [
        ("remote learning-depth telemetry", learning + "\nfetch('/profile');", shared, css, "telemetry-free"),
        ("Complete first-visit default", learning.replace('return DEPTHS.has(depth) ? depth : "guided";', 'return DEPTHS.has(depth) ? depth : "complete";', 1), shared, css, "start in Guided"),
        ("Guided leaves code open", learning.replace('detail.open = depth === "guided" ? false', 'detail.open = depth === "guided" ? true', 1), shared, css, "collapse interactive code"),
        ("late code cells ignored", learning.replace("mountCodeObserver();", "", 1), shared, css, "mounted after shared chrome"),
        ("learning controls on support tools", learning.replace("if (!supportsLearningView()) return;", "", 1), shared, css, "course home and numbered lessons"),
        ("learning controls enabled across locales", learning.replace('if (!document.documentElement.lang.toLowerCase().startsWith("en")) return false;', "", 1), shared, css, "English source course"),
        ("hidden selector restores saved depth", learning.replace('applyLearningDepth("guided");', 'applyLearningDepth();', 1), shared, css, "render every page in Guided"),
        ("missing learning-view mount", learning, shared.replace("mountLearningView();", "", 1), css, "every topbar page"),
        ("artifact placeholders wait for mount", learning, shared.replace("markLiveArtifacts();", "", 1), css, "artifact placeholder"),
        ("collapsed deep links stay hidden", learning.replace('window.addEventListener("hashchange", revealHashTarget);', "", 1), shared, css, "deep links must reveal"),
        ("print hides optional blocks", learning, shared,
         css.replace(".learning-block-body { display: block !important; }", "", 1), "print must restore"),
        ("artifact color cue removed", learning, shared,
         css.replace(".course-artifact::before", ".removed-artifact-cue::before", 1), "text-backed color cue"),
        ("empty artifact placeholder visible", learning, shared,
         css.replace(".course-artifact:empty { display: none; }", "", 1), "blank page height"),
        ("depth selector exposed", learning, shared,
         css.replace(".learning-depth-control { display: none; }", ".learning-depth-control { display: flex; }", 1), "hide the global depth selector"),
        ("unbounded artifact transcript", learning, shared,
         css.replace(".course-artifact .chatui-log", ".removed-artifact .chatui-log", 1), "bounded transcript"),
    ]
    for label, mutated_learning, mutated_shared, mutated_css, expected in learning_cases:
        if not any(expected in finding for finding in audit_learning_runtime(mutated_learning, mutated_shared, mutated_css)):
            misses.append(f"detector missed {label}")

    assistant = (ROOT / "web/nemoclaw/scripts/_course_assistant.js").read_text(encoding="utf-8")
    assistant_cases = [
        ("assistant loses session page", assistant.replace('pageId: String(item.pageId || "")', 'legacyPage: String(item.pageId || "")', 1), shared, chat, css, "grounding must persist"),
        ("assistant loses page context", assistant.replace('initialContext: attachedPage ? async () => ({ label: (pt ? "página + índice de código · " : "page + code index · ") + attachedPage.id', 'initialContext: null && async () => ({ label: "missing"', 1), shared, chat, css, "attached prose and code index"),
        ("assistant loses Portuguese chrome", assistant.replace('assistant: "ASSISTENTE DO CURSO"', 'assistant: "COURSE ASSISTANT"', 1), shared, chat, css, "Brazilian Portuguese chrome"),
        ("assistant loses course map", assistant.replace('name: "list_course_pages"', 'name: "missing_course_map"', 1), shared, chat, css, "course map"),
        ("assistant loses course search", assistant.replace('name: "search_course_pages"', 'name: "missing_course_search"', 1), shared, chat, css, "search the course"),
        ("assistant returns structured tool payload", assistant.replace('return JSON.stringify(await searchCoursePages(query, readPage, catalog), null, 2);', 'return searchCoursePages(query, readPage, catalog);', 1), shared, chat, css, "endpoint-safe text"),
        ("assistant loses lesson code index", assistant.replace('name: "list_course_code"', 'name: "missing_course_code"', 1), shared, chat, css, "enumerate exact lesson code"),
        ("assistant loses exact lesson source", assistant.replace('name: "read_course_source"', 'name: "missing_read_course_source"', 1), shared, chat, css, "exact lesson artifact source"),
        ("assistant loses runtime index", assistant.replace('name: "list_course_runtime_files"', 'name: "missing_runtime_files"', 1), shared, chat, css, "enumerate shared runtime"),
        ("assistant loses runtime source", assistant.replace('name: "read_course_runtime_source"', 'name: "missing_runtime_source"', 1), shared, chat, css, "allow-listed shared runtime source"),
        ("assistant can invent inaccessible code", assistant.replace('never invent an implementation or claim source is private or inaccessible', 'guess code when useful', 1), shared, chat, css, "forbid invented or inaccessible-source claims"),
        ("assistant hides source discovery", assistant.replace('"Show me this page\'s code"', '"What should I try next?"', 1), shared, chat, css, "source access discoverable"),
        ("assistant search grows unbounded", assistant.replace('.slice(0, 4)', '', 1), shared, chat, css, "bound tool output"),
        ("assistant leaks into support pages", assistant.replace('if (!location.pathname.includes("/nemoclaw/")) return;', "", 1), shared, chat, css, "scoped to course pages"),
        ("assistant launcher grows", assistant, shared, chat, css.replace("width: 32px; height: 32px", "width: 56px; height: 56px", 1), "remain compact"),
        ("assistant loses resize handle", assistant.replace('class="course-assistant-resizer" role="separator"', 'class="removed-resizer"', 1), shared, chat, css, "drag handle"),
        ("assistant resize loses cap", assistant.replace('Math.floor(window.innerWidth * 0.9)', 'window.innerWidth', 1), shared, chat, css, "90 percent"),
        ("assistant resize loses keyboard", assistant.replace('event.key === "ArrowLeft"', 'event.key === "Never"', 1), shared, chat, css, "keyboard adjustment"),
        ("assistant loses local sessions", assistant.replace('nemoclaw_course_assistant_sessions_v1', 'removed_session_cache', 1), shared, chat, css, "local cache key"),
        ("assistant cap only trims storage", assistant.replace('store.sessions = store.sessions.map', 'const sessions = store.sessions.map', 1), shared, chat, css, "normalize and cap live"),
        ("assistant history exceeds storage", assistant.replace('MAX_SESSION_HISTORY_CHARS = 100000', 'MAX_SESSION_HISTORY_CHARS = Infinity', 1), shared, chat, css, "fit browser-local storage"),
        ("assistant activity exceeds storage", assistant.replace('MAX_SESSION_ACTIVITY_CHARS = 20000', 'MAX_SESSION_ACTIVITY_CHARS = Infinity', 1), shared, chat, css, "activity must remain bounded"),
        ("assistant duplicates empty sessions", assistant.replace('current && !current.history.length && !current.activity && !current.artifact && current.title === "New session"', 'false', 1), shared, chat, css, "truly empty session"),
        ("assistant loses new session", assistant.replace('<button type="button" data-course-assistant-new>', '<button type="button" data-removed-new>', 1), shared, chat, css, "new-session control"),
        ("assistant loses rename", assistant.replace('aria-label="${copy.renameLabel}"', 'aria-label="session"', 1), shared, chat, css, "inline session rename"),
        ("assistant loses page attach", assistant.replace('data-course-assistant-use-page', 'data-removed-use-page'), shared, chat, css, "page-attachment control"),
        ("assistant titles only successful turns", assistant.replace('onUserMessage: question =>', 'onDelayedMessage: question =>', 1), shared, chat, css, "before a failed model turn"),
        ("assistant drops in-flight transcript", assistant.replace('onTurnSnapshot: (history, meta) =>', 'onLostSnapshot: (history, meta) =>', 1), shared, chat, css, "persist in-flight and failed turns"),
        ("assistant drops persisted activity", assistant.replace('current.activity = cleanActivity(meta?.activity)', 'current.activity = ""', 1), shared, chat, css, "save visible agent activity"),
        ("assistant loses History view", assistant.replace('data-course-assistant-view="history"', 'data-missing-view="history"', 1), shared, chat, css, "persistent History view"),
        ("assistant loses History copy", assistant.replace('data-course-history-copy', 'data-missing-history-copy'), shared, chat, css, "copy persisted activity"),
        ("shared chat drops immediate titles", assistant, shared, chat.replace('onUserMessage: opts.onUserMessage', 'onUserMessage: null', 1), css, "preflight session-title hook"),
        ("shared chat delays immediate titles", assistant, shared, chat.replace('opts.onUserMessage(q, ctx)', 'opts.onUserMessageLater(q, ctx)', 1), css, "before the model request"),
        ("shared chat drops transcript snapshots", assistant, shared, chat.replace('onTurnSnapshot: opts.onTurnSnapshot', 'onTurnSnapshot: null', 1), css, "forward transcript snapshots"),
        ("shared chat never writes snapshots", assistant, shared, chat.replace('opts.onTurnSnapshot(cleanHistory(items), { state, activity }, ctx)', 'void items', 1), css, "snapshot a turn before completion"),
        ("shared chat drops activity snapshot", assistant, shared, chat.replace('const activitySnapshot = () =>', 'const removedActivitySnapshot = () =>', 1), css, "visible ReAct activity"),
        ("shared chat drops tool result activity", assistant, shared, chat.replace('ctx.view.updateTool(c.el', 'ctx.view.missingToolUpdate(c.el'), css, "completed tool results"),
        ("shared chat loses navigation tail", assistant, shared, chat.replace('window.addEventListener("pagehide", snapshotBeforeNavigation', 'window.addEventListener("never", snapshotBeforeNavigation', 1), css, "flush the latest streamed text"),
        ("shared chat drops artifact capture", assistant, shared, chat.replace('onAssistantMessage: opts.onAssistantMessage', 'onAssistantMessage: null', 1), css, "deterministic artifact capture"),
        ("assistant loses artifact queue", assistant.replace('name: "queue_course_artifact"', 'name: "missing_artifact_queue"', 1), shared, chat, css, "queue generated browser code"),
        ("assistant loses 120B source recovery", assistant.replace('recoverInlineToolIntent: async answer =>', 'recoverLostIntent: async answer =>', 1), shared, chat, css, "prints source arguments"),
        ("shared chat preserves raw tool JSON", assistant, shared, chat.replace('ctx.view.discardAnswer()', 'void recovered', 1), css, "replace recovered tool JSON"),
        ("assistant loses fenced-code capture", assistant.replace('export function artifactFromMarkdown', 'function removedArtifactFromMarkdown', 1), shared, chat, css, "detect generated HTML/JavaScript"),
        ("assistant loses artifact tab", assistant.replace('data-course-assistant-view="artifact"', 'data-missing-view="artifact"'), shared, chat, css, "discoverable Artifact tab"),
        ("assistant artifact escapes sandbox", assistant.replace('sandbox="allow-scripts"', 'sandbox="allow-scripts allow-same-origin"', 1), shared, chat, css, "origin-isolated sandbox"),
        ("assistant artifact returns to srcdoc", assistant.replace('URL.createObjectURL(new Blob([', 'artifactFrame.srcdoc = ([', 1), shared, chat, css, "fragile srcdoc"),
        ("assistant artifact loses helper bridge", assistant.replace('window.course=api;window.helpers=new Proxy', 'window.course=api;window.missingHelpers=new Proxy', 1), shared, chat, css, "lesson-helper bridges"),
        ("assistant artifact allows unavailable lesson helpers", assistant.replace('filter(name => !["embed", "cosineSim"].includes(name))', 'filter(name => false)', 1), shared, chat, css, "absent from the artifact sandbox"),
        ("assistant artifact bridge unbounded", assistant.replace('input.length > 16', 'false', 1), shared, chat, css, "bound artifact requests"),
        ("assistant artifact loses validator", assistant.replace('export function artifactJavaScriptIssue', 'function removedArtifactJavaScriptIssue', 1), shared, chat, css, "validate generated JavaScript"),
        ("assistant artifact allows unawaited embed", assistant.replace('Artifact embedding is asynchronous. Assign its result with await course.embed(...) or await helpers.embed(...)', 'Embeddings failed', 1), shared, chat, css, "unawaited embedding"),
        ("assistant artifact allows bad input type", assistant.replace('Artifact embed inputType must be', 'Embedding option failed'), shared, chat, css, "unsupported embedding input types"),
        ("assistant artifact validation misses queue and run", assistant.replace('artifactJavaScriptIssue(javascript)', 'removedArtifactCheck(javascript)'), shared, chat, css, "manual runs, tool queues"),
        ("assistant artifact loses async runner", assistant.replace('(async () => {\\n${javascript}\\n})();', '${javascript}', 1), shared, chat, css, "top-level await"),
        ("assistant artifact hides API contract", assistant.replace('class="course-artifact-api"', 'class="removed-artifact-api"', 1), shared, chat, css, "show its asynchronous embedding contract"),
        ("assistant artifact clear becomes destructive", assistant.replace('flushArtifactSave(); clearArtifactPreview(copy.previewCleared);', 'activeSession().artifact = null;', 1), shared, chat, css, "preserve artifact source"),
        ("assistant artifact loses editor", assistant.replace('window.CodeMirror.fromTextArea', 'window.MissingEditor.fromTextArea', 1), shared, chat, css, "course editor"),
        ("assistant artifact loses HTML highlighting", assistant.replace('window.CodeMirror.defineMode("course-html"', 'window.CodeMirror.defineMode("plain-text"', 1), shared, chat, css, "syntax-aware tokens"),
        ("assistant invents pasteable cell", assistant.replace('The course has no generic pasteable code cell', 'Paste code into a course cell', 1), shared, chat, css, "reject nonexistent paste-into-cell"),
        ("assistant invents artifact imports", assistant.replace('The sandbox provides the asynchronous course.embed API', 'Import _rag.js inside the artifact', 1), shared, chat, css, "artifact bridge"),
        ("assistant artifact layout unbounded", assistant, shared, chat, css.replace('.course-assistant-artifact iframe', '.removed-artifact-frame', 1), "bounded responsive layout"),
        ("assistant History layout unbounded", assistant, shared, chat, css.replace('.course-assistant-history', '.removed-assistant-history'), "persistent History needs a bounded"),
        ("assistant close-button style leaks into History", assistant, shared, chat, css.replace('.course-assistant-panel > header button {', '.course-assistant-panel header button {', 1), "must not leak into nested History controls"),
        ("assistant loses compaction threshold", assistant.replace('compactAtTokens: 12000', 'compactAtTokens: 0', 1), shared, chat, css, "compaction threshold"),
        ("assistant compaction keeps no recent turns", assistant.replace('compactKeepMessages: 6', 'compactKeepMessages: 0', 1), shared, chat, css, "recent verbatim"),
        ("assistant compaction skips thread rotation", assistant, shared, chat.replace('ctx.thread = ctx.rotateThread();', '', 1), css, "fresh bounded"),
        ("assistant mobile panel overflows", assistant, shared, chat, css.replace(".course-assistant-panel { width: 100vw;", ".course-assistant-panel { width: 30rem;", 1), "narrow viewport"),
        ("license note relicences sources", assistant.replace("Named external material keeps its own terms", "All named external material is Apache-2.0", 1), shared, chat, css, "must not relicence"),
    ]
    for label, mutated_assistant, mutated_shared, mutated_chat, mutated_css, expected in assistant_cases:
        if not any(expected in finding for finding in audit_page_assistant(mutated_assistant, mutated_shared, mutated_chat, mutated_css)):
            misses.append(f"detector missed {label}")

    langchain = (ROOT / "web/nemoclaw/scripts/_langchain.js").read_text(encoding="utf-8")
    source_cases = [
        ("course source loses shared fetch", langchain.replace('const COURSE_HTML_CACHE = new Map()', 'const COURSE_HTML_CACHE = null', 1), "share one page fetch"),
        ("runtime source loses allow-list", langchain.replace('COURSE_RUNTIME_FILES.find(([name]) => name === safe)', 'COURSE_RUNTIME_FILES[0]', 1), "remain allow-listed"),
        ("lesson source ignores text artifacts", langchain.replace('script[type="text/plain"][id]', 'script[data-missing]', 1), "text-backed lesson artifacts"),
        ("lesson source ignores page modules", langchain.replace('script[type="module"]:not([src])', 'script[data-missing-module]', 1), "inline page modules"),
        ("code index inlines all source", langchain.replace('.map(({ source: _source, ...metadata }) => metadata)', '.map(item => item)', 1), "must not inline every source"),
        ("lesson source reader removed", langchain.replace('export async function courseCode(pageId, artifactId)', 'async function removedCourseCode(pageId, artifactId)', 1), "exact lesson source"),
        ("runtime source reader removed", langchain.replace('export async function courseRuntimeSource(file)', 'async function removedRuntimeSource(file)', 1), "shared runtime source must remain readable"),
    ]
    for label, mutated_langchain, expected in source_cases:
        if not any(expected in finding for finding in audit_course_source_runtime(mutated_langchain)):
            misses.append(f"detector missed {label}")

    fixture_path = ROOT / "web/nemoclaw/01a-loop.html"
    fixture = '''<details class="learning-block" open data-learning-id="wire-detail" data-learning-tier="deep" data-localization-scope="en-shell">
      <summary data-localization-scope="en"><span class="learning-scope">Deep · Build</span><span class="learning-question">Inspect the request transport details?</span></summary>
      <div class="learning-block-body"><h2>Wire detail</h2><p>This optional explanation contains enough concrete implementation detail to justify its own disclosure in the complete course.</p></div>
    </details>'''
    learning_block_cases = [
        ("missing inline question", fixture.replace('<span class="learning-question">Inspect the request transport details?</span>', ""), "inline question"),
        ("missing scope cue", fixture.replace('<span class="learning-scope">Deep · Build</span>', ""), "scope cue"),
        ("localized pilot shell", fixture.replace(' data-localization-scope="en-shell"', "", 1), "localization-neutral"),
        ("unknown learning tier", fixture.replace('data-learning-tier="deep"', 'data-learning-tier="expert"'), "applied or deep"),
        ("duplicate learning id", fixture + fixture, "duplicate data-learning-id"),
        ("hidden learner exercise", fixture.replace("<h2>Wire detail</h2>", '<h2>Try it</h2><div id="cell-hidden"></div>'), "core, prerequisite, warning, or exercise UI"),
        ("optional artifact lacks cell", fixture.replace('data-localization-scope="en-shell"', 'data-learning-artifact="optional" data-localization-scope="en-shell"'), "optional artifact needs"),
        ("optional exercise lacks artifact declaration", fixture.replace('data-localization-scope="en-shell"', 'data-learning-exercise="optional" data-localization-scope="en-shell"'), "must explicitly declare"),
    ]
    for label, mutated, expected in learning_block_cases:
        if not any(expected in finding for finding in audit_learning_lesson(fixture_path, mutated)):
            misses.append(f"detector missed {label}")

    page_path = ROOT / "web/nemoclaw/03b-openclaw.html"
    page = page_path.read_text(encoding="utf-8")
    page_cases = [
        ("missing launchable status", page.replace('id="claw-status"', 'id="removed-claw-status"', 1), "launchable readiness"),
        ("enabled-before-ready chat", re.sub(r"\n\s*disabled:\s*\(\)\s*=>[^\n]+", "", page, count=1), "disable input"),
        ("missing stop signal", page.replace("signal: ctx.signal", "signal: null", 1), "Stop signal"),
    ]
    for label, mutated, expected in page_cases:
        if not any(expected in finding for finding in audit_lesson(page_path, mutated)):
            misses.append(f"detector missed {label}")

    one_step = '''<div id="cell-one"></div><script type="module">
      mountCanvasFlow("#cell-one", { label: "One step", nodes: [
        { id: "only", title: "Only", code: `return { value: 1 };` },
      ]});
    </script>'''
    if not any("CanvasFlow needs at least two" in finding for finding in audit_lesson(page_path, one_step)):
        misses.append("detector missed single-step CanvasFlow")

    dom_page_path = ROOT / "web/nemoclaw/02c-deep.html"
    dom_page = dom_page_path.read_text(encoding="utf-8")
    broken_dom_page = dom_page.replace('id="deep-src"', 'id="missing-deep-src"', 1)
    if not any("DOM code source" in finding for finding in audit_lesson(dom_page_path, broken_dom_page)):
        misses.append("detector missed unresolved RunCell DOM code source")
    deep_cases = [
        ("wait-then-render SVG", dom_page.replace('ctx.view.html(\n      \'<section class="research-board"', 'ctx.view.html(helpers.diagramSVG({}));\n    ctx.view.html(\n      \'<section class="research-board"', 1), "wait-then-render SVGs"),
        ("worker token stream removed", dom_page.replace('(token) => streamWorker(worker, token)', 'null', 1), "stream each worker"),
        ("worker focus removed", dom_page.replace('card.tabIndex = 0;', '', 1), "keyboard focusable"),
        ("worker rail stops scrolling", dom_page.replace('overflow-x: auto; overscroll-behavior-inline: contain;', 'overflow-x: hidden;', 1), "horizontally inspectable"),
        ("materials mislabeled as web", dom_page.replace('source === "materials"', 'source === "web"', 1), "curated materials search"),
        ("materials topics hidden from planner", dom_page.replace('const MATERIAL_TOPICS = [', 'const UNLISTED_TOPICS = [', 1), "planner-visible supported topics"),
        ("coverage gap hidden", dom_page.replace('gap ? "gap" : "done"', '"done"', 1), "partial coverage"),
    ]
    for label, mutated, expected in deep_cases:
        if not any(expected in finding for finding in audit_deep_research_artifact(mutated)):
            misses.append(f"detector missed {label}")

    handoff = (ROOT / "web/nemoclaw/04c-going-further.html").read_text(encoding="utf-8")
    handoff_cases = [
        ("04c duplicates old capstone", handoff.replace('<p><button type="button" class="course-assistant-open"', '<div id="capstone-artifact"></div><p><button type="button" class="course-assistant-open"', 1), "must not duplicate"),
        ("04c loses local-session explanation", handoff.replace("sessions stay in this browser", "sessions disappear", 1), "local session persistence"),
        ("04c loses launch action", handoff.replace('document.querySelector(".course-assistant-launcher")?.click()', 'void 0', 1), "must open the shared"),
    ]
    for label, mutated, expected in handoff_cases:
        if not any(expected in finding for finding in audit_course_assistant_handoff(mutated)):
            misses.append(f"detector missed {label}")

    heavy_path = ROOT / "web/nemoclaw/04b-modern-clis.html"
    heavy = heavy_path.read_text(encoding="utf-8")
    heavy = heavy.replace('mountRunCell("#cell-jsagent", {\n      openCode: false,', 'mountRunCell("#cell-jsagent", {\n      openCode: true,', 1)
    if not any("default-open implementation" in finding for finding in audit_lesson(heavy_path, heavy)):
        misses.append("detector missed oversized default-open implementation")

    home = (ROOT / "web/nemoclaw/index.html").read_text(encoding="utf-8")
    broken = home.replace("CPU-based", "unspecified", 1)
    if not any("CPU baseline" in finding for finding in audit_home(broken)):
        misses.append("detector missed missing CPU baseline")

    gitlab = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
    github = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
    pre_push = (ROOT / "scripts/git-hooks/pre-push").read_text(encoding="utf-8")
    bundle = (ROOT / "scripts/validation/validate_bundle.py").read_text(encoding="utf-8")
    broken_gitlab = gitlab.replace("python3 scripts/validation/learner_flow_audit.py --self-test", "echo skipped", 1)
    if not any(".gitlab-ci.yml" in finding for finding in audit_workflow_wiring(broken_gitlab, github, pre_push, bundle)):
        misses.append("detector missed missing GitLab learner-flow wiring")
    return misses


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    findings = self_test() if args.self_test else audit_tree()
    if findings:
        print("learner_flow_audit: FAIL")
        for finding in findings:
            print(f"  - {finding}")
        return 1
    print("learner_flow_audit: OK" + (" (mutation self-test)" if args.self_test else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
