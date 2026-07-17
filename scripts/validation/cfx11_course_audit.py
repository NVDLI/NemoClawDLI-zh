#!/usr/bin/env python3
# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Fail-closed integrity and runtime-boundary audit for Markdown notebook courses."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.pyodide.verify_cfx11_wheels import audit as audit_wheels


COURSE = ROOT / "web/cfx11"
SCHEMA = "dli-markdown-course/1.0"
DELIVERY_SCHEMA = "dli-markdown-delivery/1.0"
MARKER = re.compile(
    r"<!-- dli-course-cell (?P<meta>\{[^\n]+\}) -->\n(?P<body>.*?)<!-- /dli-course-cell -->",
    re.DOTALL,
)


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_text(value: str) -> str:
    return digest_bytes(value.encode("utf-8"))


def source_from_block(body: str, record: dict) -> str:
    if record["type"] == "code":
        match = re.match(r"(?P<fence>`{3,})python\n", body)
        if not match:
            raise ValueError("code cell is not enclosed by its generated Python fence")
        fence = match.group("fence")
        closing = body.rfind(fence)
        if closing < match.end() or body[closing + len(fence):] not in {"", "\n"}:
            raise ValueError("code cell closing fence is missing or malformed")
        candidate = body[match.end():closing]
    else:
        candidate = body
    raw = candidate.encode("utf-8")
    size = record["source_bytes"]
    if len(raw) < size:
        raise ValueError(f"cell body is shorter than its recorded {size} bytes")
    source_raw, generated = raw[:size], raw[size:]
    if generated not in {b"", b"\n"}:
        raise ValueError("cell wrapper contains unrecognized bytes after source")
    return source_raw.decode("utf-8")


def audit_discovery(root: Path = ROOT) -> list[str]:
    """Require every learner preview to be reachable from both human and agent hubs."""

    findings: list[str] = []
    required = {
        "web/index.html": "/lab/static/cfx11/index.html",
        "SKILL.html": "web/cfx11/index.html",
        "web/cfx11/SKILL.html": 'href="index.html">Open the course preview',
    }
    for relative, marker in required.items():
        try:
            source = (root / relative).read_text(encoding="utf-8")
        except OSError:
            findings.append(f"course discovery surface is missing: {relative}")
            continue
        if marker not in source:
            findings.append(f"course preview is disconnected at {relative}")
    return findings


def audit(course: Path = COURSE) -> list[str]:
    findings: list[str] = []
    required = [
        "index.html", "course.css", "course.js", "course.json", "content-bundle.json", "SOURCE_PROVENANCE.md",
        "runtime/runner.js", "runtime/worker.js", "runtime/operations.js", "runtime/course_compat.py",
    ]
    for relative in required:
        if not (course / relative).is_file():
            findings.append(f"missing required course file: {relative}")
    if findings:
        return findings

    try:
        manifest = json.loads((course / "course.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"cannot load course.json: {error}"]
    if manifest.get("schema") != SCHEMA:
        findings.append(f"course.json schema must be {SCHEMA}")
    course_record = manifest.get("course", {})
    if course_record.get("id") != "c-fx-11-v1":
        findings.append("course id must remain c-fx-11-v1")
    if course_record.get("source_repository_modified") is not False:
        findings.append("manifest must state that the source repository was not modified")
    if not re.fullmatch(r"[0-9a-f]{64}", str(course_record.get("source_artifact_sha256", ""))):
        findings.append("source archive SHA-256 is missing or malformed")

    lessons = manifest.get("lessons", [])
    try:
        delivery = json.loads((course / "content-bundle.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        delivery = {}
        findings.append(f"cannot load content-bundle.json: {error}")
    if delivery.get("schema") != DELIVERY_SCHEMA:
        findings.append(f"content-bundle.json schema must be {DELIVERY_SCHEMA}")
    delivered = delivery.get("lessons", {})
    if not lessons:
        findings.append("course manifest has no lessons")
    lesson_ids: set[str] = set()
    cell_ids: set[str] = set()
    counted = {"cells": 0, "code_cells": 0, "markdown_cells": 0}
    for lesson in lessons:
        lesson_id = lesson.get("id")
        if not lesson_id or lesson_id in lesson_ids:
            findings.append(f"missing or duplicate lesson id: {lesson_id!r}")
            continue
        lesson_ids.add(lesson_id)
        relative = lesson.get("markdown_path", "")
        path = course / relative
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as error:
            findings.append(f"{relative}: cannot read Markdown: {error}")
            continue
        if digest_text(raw) != lesson.get("markdown_sha256"):
            findings.append(f"{relative}: Markdown digest differs from course.json")
        bundled = delivered.get(relative)
        if not isinstance(bundled, dict):
            findings.append(f"{relative}: missing from the Pages-safe content bundle")
        elif bundled.get("markdown") != raw or bundled.get("sha256") != lesson.get("markdown_sha256"):
            findings.append(f"{relative}: content bundle differs from the reviewed Markdown and manifest digest")
        blocks = list(MARKER.finditer(raw))
        cells = lesson.get("cells", [])
        if len(blocks) != len(cells):
            findings.append(f"{relative}: marker count {len(blocks)} differs from manifest cell count {len(cells)}")
            continue
        for expected, block in zip(cells, blocks):
            try:
                actual = json.loads(block.group("meta"))
            except json.JSONDecodeError as error:
                findings.append(f"{relative}: malformed cell marker: {error}")
                continue
            for field in ("id", "index", "type", "source_sha256"):
                if actual.get(field) != expected.get(field):
                    findings.append(f"{relative}: cell {expected.get('index')} marker {field} differs from manifest")
            cell_id = expected.get("id")
            if cell_id in cell_ids:
                findings.append(f"duplicate cell id: {cell_id}")
            cell_ids.add(cell_id)
            try:
                source = source_from_block(block.group("body"), expected)
            except (UnicodeDecodeError, ValueError) as error:
                findings.append(f"{relative}: cell {expected.get('index')} cannot reconstruct source: {error}")
                continue
            if digest_text(source) != expected.get("source_sha256"):
                findings.append(f"{relative}: cell {expected.get('index')} source differs from imported notebook")
            if source.endswith("\n") != expected.get("source_ends_with_newline"):
                findings.append(f"{relative}: cell {expected.get('index')} newline state differs from manifest")
            patch = expected.get("source_patch")
            if patch is not None:
                if expected.get("type") not in {"code", "markdown"}:
                    findings.append(f"{relative}: cell {expected.get('index')} applies a source patch to an unsupported cell type")
                if not isinstance(patch, dict) or set(patch) != {"schema", "upstream_source_sha256", "reason"}:
                    findings.append(f"{relative}: cell {expected.get('index')} source patch is malformed")
                else:
                    if patch.get("schema") != "dli-course-source-patch/1.0":
                        findings.append(f"{relative}: cell {expected.get('index')} source patch schema is unsupported")
                    upstream = str(patch.get("upstream_source_sha256") or "")
                    if not re.fullmatch(r"[0-9a-f]{64}", upstream) or upstream == expected.get("source_sha256"):
                        findings.append(f"{relative}: cell {expected.get('index')} source patch does not bind a distinct upstream digest")
                    if len(str(patch.get("reason") or "").strip()) < 24:
                        findings.append(f"{relative}: cell {expected.get('index')} source patch lacks a concrete reason")
            counted["cells"] += 1
            if expected.get("type") == "code":
                counted["code_cells"] += 1
            if expected.get("type") == "markdown":
                counted["markdown_cells"] += 1

    support = manifest.get("supporting_files", [])
    for record in support:
        relative = record.get("path", "")
        path = course / relative
        if not path.is_file():
            findings.append(f"missing supporting file: {relative}")
            continue
        raw = path.read_bytes()
        if len(raw) != record.get("bytes") or digest_bytes(raw) != record.get("sha256"):
            findings.append(f"supporting file differs from source archive: {relative}")
    counted["supporting_files"] = len(support)
    if any(str(record.get("path", "")).endswith(".py") for record in support):
        findings.append("source-course helper Python with unresolved terms must remain an upstream link")
    for field, actual in counted.items():
        if manifest.get("totals", {}).get(field) != actual:
            findings.append(f"manifest total {field} is {manifest.get('totals', {}).get(field)!r}; reconstructed {actual}")
    expected_delivery = {lesson.get("markdown_path") for lesson in lessons}
    if set(delivered) != expected_delivery:
        findings.append("content bundle lesson paths do not exactly match course.json")

    runtime = (course / "runtime/worker.js").read_text(encoding="utf-8")
    runner = (course / "runtime/runner.js").read_text(encoding="utf-8")
    operations = (course / "runtime/operations.js").read_text(encoding="utf-8")
    client = (course / "course.js").read_text(encoding="utf-8")
    compatibility = (course / "runtime/course_compat.py").read_text(encoding="utf-8")
    learner_shell = (course / "index.html").read_text(encoding="utf-8")
    styles = (course / "course.css").read_text(encoding="utf-8")
    shared_workbench = (ROOT / "web/shared/runtime-workbench.js").read_text(encoding="utf-8")
    shared_workbench_styles = (ROOT / "web/shared/runtime-workbench.css").read_text(encoding="utf-8")
    notebook_syntax = (ROOT / "scripts/pyodide/examples/notebook-syntax.js").read_text(encoding="utf-8")
    boundary = runtime + runner + operations + client + compatibility + learner_shell
    if boundary.count("https://integrate.api.nvidia.com/v1") < 2:
        findings.append("direct NVIDIA API boundary is not explicit in both runtime and learner settings")
    forbidden = ["openclaw-cors-proxy", "CF_Authorization", "_pomerium"]
    for token in forbidden:
        if token in boundary:
            findings.append(f"course runtime must not depend on unrelated proxy or launchable credential: {token}")
    if re.search(r"(?:nvapi-[A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9_-]{20,})", boundary):
        findings.append("course runtime contains a credential-shaped literal")
    for contract in ("primary product category", "counterfactual product category", "input sensitivity"):
        if contract not in compatibility:
            findings.append(f"assessment middleware omits required behavior check: {contract}")
    for contract in (
        "from openai import OpenAI", "BrowserHTTPXTransport", "_browser_openai_init",
        "from langchain_nvidia_ai_endpoints import ChatNVIDIA",
    ):
        source = compatibility if contract != "from langchain_nvidia_ai_endpoints import ChatNVIDIA" else "".join(
            path.read_text(encoding="utf-8") for path in (course / "content").rglob("*.md")
        )
        if contract not in source:
            findings.append(f"real upstream model transport contract is missing: {contract}")
    if "new CoursePythonRunner" not in client or "buildXBlocks" not in client:
        findings.append("Markdown code cells are not upgraded through the shared executable XBlock path")
    if "fetch(markdownUrl" in client or "content-bundle.json" not in client or "crypto.subtle.digest" not in client:
        findings.append("lesson delivery must use the digest-checked Pages-safe content bundle rather than runtime Markdown fetches")
    if course == COURSE:
        findings.extend(audit_discovery())
    probe_start = client.find("async function probeModelConnection")
    probe_end = client.find('elements["test-api-key"].addEventListener', probe_start)
    probe_source = client[probe_start:probe_end] if probe_start >= 0 and probe_end > probe_start else ""
    runtime_contracts = {
        "visible learner key entry": (learner_shell, 'id="api-key"'),
        "visible model connection test": (learner_shell + client, 'id="test-api-key"'),
        "compact saved model connection": (learner_shell + client, 'id="connection-details"'),
        "non-secret connection summary": (learner_shell + client, 'id="connection-summary-status"'),
        "auth-sensitive model connection test": (client, '`${baseUrl}/chat/completions`'),
        "one-token model connection test": (client, "max_tokens: 1"),
        "bounded model fallback": (client + runtime, "MODEL_PROBE_CANDIDATES"),
        "abortable model probe": (probe_source, 'credentials: "omit",\n          signal,'),
        "explicit theme control": (learner_shell, 'id="theme-toggle"'),
        "focus-aware kernel variable panel": (learner_shell + client + compatibility, 'data-variable-view="focused"'),
        "complete kernel namespace option": (learner_shell, 'data-variable-view="all"'),
        "shared runtime workbench": (learner_shell + client + shared_workbench, "mountRuntimeWorkbench"),
        "accessible runtime disclosure": (learner_shell + shared_workbench, "data-workbench-view"),
        "runtime disclosure title target": (learner_shell, "data-workbench-title"),
        "runtime disclosure close control": (learner_shell, "data-workbench-close"),
        "runtime focus return": (shared_workbench, "returnFocus"),
        "code and evidence workspace": (client + shared_workbench_styles, "wb-cell-workspace"),
        "explicit keyboard-editable cells": (client, "readOnly: false"),
        "coherent per-cell settings": (client + shared_workbench_styles, "wb-cell-settings-panel"),
        "per-cell output layout": (client + shared_workbench_styles, "cellSettings.output"),
        "below-code output default": (client, 'legacyLayout === "beside" ? "beside" : "below"'),
        "hidden pre-run output": (client + styles, "artifactPane.hidden = true"),
        "stale output cleared before execution": (client, "block.output.replaceChildren(progress, stream)"),
        "compact visual execution progress": (client + styles, "wb-cell-progress-track"),
        "accessible execution progress": (client, 'progress.setAttribute("role", "status")'),
        "compact result pane": (styles, ".wb-cell-artifact { min-height: 0; }"),
        "explicit no-output completion": (client, "Completed without output."),
        "reduced-motion execution progress": (styles, "prefers-reduced-motion: reduce"),
        "origin-aware model route": (client, "function defaultModelRoute"),
        "versioned model route preference": (client, 'const MODEL_ROUTE_STORAGE_KEY = "cfx11-model-route:v2"'),
        "per-cell editor height": (client + styles, "cellSettings.height"),
        "per-cell wrapping and line numbers": (client, 'editor.setOption("lineWrapping"'),
        "Python comment and indentation shortcuts": (client, '"Ctrl-/": togglePythonComments'),
        "theme-aware visible editor caret": (styles, "border-left: 2px solid var(--code-caret)"),
        "shared notebook inspection and magic syntax": (runtime + notebook_syntax, "PYODIDE_NOTEBOOK_SYNTAX"),
        "bounded output geometry": (styles + shared_workbench_styles, "max-height: 38rem"),
        "highlighted structured results": (client, 'pre.className = "formatted-output"'),
        "in-cell runtime inspection": (client, "Inspect the runtime behind this cell"),
        "bounded runtime stream view": (client, "state.streams.length > 160"),
        "NVIDIA-backed runtime guide": (client + runtime, "state.runner.assistant"),
        "serialized execution queue": (client, 'addEventListener("queue-change"'),
        "visible workflow activity": (learner_shell + client, 'data-runtime-panel="activity"'),
        "workflow lifecycle ledger": (client + operations, "ObservableOperations"),
        "queue-wait deadline": (runner, "this.armTimeout(job, this.queueTimeoutMs"),
        "execution deadline": (runner, "this.armTimeout(job, this.runTimeoutMs"),
        "complete job lifecycle": (runner, 'new CustomEvent("job-state"'),
        "observable variable refresh failure": (client, 'message.textContent = `Refresh failed:'),
        "in-cell Python input": (client + runtime + compatibility, 'addEventListener("input-request"'),
        "kernel inspection": (client + runtime, 'state.runner.inspect('),
        "cross-lesson kernel configuration": (client, "state.runner.configure(runnerConfiguration"),
        "stable NVIDIA request headers": (runtime, '["accept", "authorization", "content-type"]'),
        "origin-specific transport error": (runtime, "choose the DLI browser relay"),
        "concise transport error presentation": (client, 'summary.textContent = "Full Python traceback"'),
        "wide lesson reading surface": (styles, ".lesson-body { max-width: 90rem;"),
        "theme-specific input palette": (styles, "--input-bg: #f2f8e9;"),
        "theme-specific code palette": (styles, "--code-bg: #f6f8fa;"),
        "fixed-color logo presentation": (styles, 'img[src$="/nvidia.png"]'),
        "Mermaid presentation": (client, "function mermaidImageUrl"),
        "opinionated Markdown anchors": (client + styles, "heading-anchor"),
        "client billing attribution": (client, '"X-BILLING-INVOKE-ORIGIN": BILLING_INVOKE_ORIGIN'),
        "runtime billing attribution": (runtime, 'headers.set("X-BILLING-INVOKE-ORIGIN", BILLING_INVOKE_ORIGIN)'),
        "bounded NVIDIA relay": (runtime, '"nvidia-api-cors-proxy.experiments.courses.nvidia.com"'),
    }
    for label, (source, marker) in runtime_contracts.items():
        if marker not in source:
            findings.append(f"browser course omits {label}")
    for selector in (r"\.lesson-body\s*>\s*\.lesson-lead", r"\.lesson-body\s+(?:p|li)"):
        if re.search(selector + r"\s*\{[^}]*max-width\s*:", styles):
            findings.append("browser course must not constrain lesson prose with character-width hedges")
    candidate_match = re.search(r"const MODEL_PROBE_CANDIDATES = Object\.freeze\(\[(.*?)\]\);", client, re.DOTALL)
    candidate_models = re.findall(r'"(nvidia/[^"\s]+)"', candidate_match.group(1) if candidate_match else "")
    if len(set(candidate_models)) < 2:
        findings.append("browser course model probe must retain multiple distinct bounded candidates")
    lifecycle_states = set(re.findall(r'"(queued|running|succeeded|failed|timed-out|cancelled)"', runner + operations))
    if lifecycle_states != {"queued", "running", "succeeded", "failed", "timed-out", "cancelled"}:
        findings.append("browser workflow lifecycle must surface queued, running, succeeded, failed, timed-out, and cancelled states")
    for contract in (
        "application/x-course-chat+json", "courseHttpRequest", "_browser_wikipedia_init",
        "_assert_upstream_packages", "await micropip.install(__course_local_wheels.to_py(), deps=False",
    ):
        if contract not in boundary:
            findings.append(f"browser compatibility layer omits required source-course behavior: {contract}")
    if "cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/" not in runtime or 'PYODIDE_VERSION = "314.0.2"' not in runtime:
        findings.append("Pyodide runtime URL must remain version-pinned")
    public_shims = set(re.findall(r'_owned_module\("([^"]+)"', compatibility)) - {
        "assessment_helper", "chat_helpers.gradio_interface",
    }
    if public_shims:
        findings.append(f"course compatibility layer replaces public packages: {sorted(public_shims)}")
    for forbidden_shim in ("langchain", "langchain_core", "langgraph", "openai", "wikipediaapi", "contractions"):
        if re.search(rf'(?:ModuleType|_owned_module)\(["\']{re.escape(forbidden_shim)}["\']', compatibility):
            findings.append(f"course compatibility layer mimics upstream package: {forbidden_shim}")
    findings.extend(f"browser wheel evidence: {finding}" for finding in audit_wheels(course / "runtime"))
    if "source license is unresolved" not in (course / "SOURCE_PROVENANCE.md").read_text(encoding="utf-8").lower():
        findings.append("source provenance must fail closed on the unresolved source-course license")

    candidate_path = ROOT / "scripts/pyodide/candidate-components.json"
    try:
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        findings.append(f"cannot load browser-Python component evidence: {error}")
        candidate = {}
    adopted = candidate.get("course_candidate", {})
    direct_packages = {
        "contractions", "langchain", "langchain-core", "langchain-nvidia-ai-endpoints",
        "langgraph", "openai", "pydantic", "requests", "Wikipedia-API",
    }
    if (
        adopted.get("entrypoint") != "web/cfx11/runtime/worker.js"
        or (adopted.get("runtime") or {}).get("pyodide") != "314.0.2"
        or adopted.get("wheel_lock") != "web/cfx11/runtime/wheels.lock.json"
        or set(adopted.get("direct_packages") or []) != direct_packages
    ):
        findings.append("browser-Python evidence does not match the course worker's direct package set")

    shared_path = ROOT / "web/shared/vendor/browser-dependencies.json"
    try:
        shared = json.loads(shared_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        findings.append(f"cannot load shared browser vendor evidence: {error}")
        shared = {}
    referenced_vendor = set(re.findall(r'\.\./shared/vendor/([^"\']+)', (course / "index.html").read_text(encoding="utf-8") + client))
    recorded_vendor = {str(item.get("file") or "") for item in shared.get("assets") or []}
    if not referenced_vendor or not referenced_vendor <= recorded_vendor:
        findings.append("course references a shared browser asset outside the reviewed vendor manifest")

    return findings


def main() -> int:
    findings = audit()
    if findings:
        print(f"cfx11_course_audit: FAIL ({len(findings)})")
        for finding in findings:
            print(f"  - {finding}")
        return 1
    manifest = json.loads((COURSE / "course.json").read_text(encoding="utf-8"))
    print(
        "cfx11_course_audit: PASS "
        f"lessons={manifest['totals']['lessons']} cells={manifest['totals']['cells']} "
        f"code={manifest['totals']['code_cells']} support={manifest['totals']['supporting_files']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
