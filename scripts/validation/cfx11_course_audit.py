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
COURSE = ROOT / "web/cfx11"
SCHEMA = "dli-markdown-course/1.0"
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


def audit(course: Path = COURSE) -> list[str]:
    findings: list[str] = []
    required = [
        "index.html", "course.css", "course.js", "course.json", "SOURCE_PROVENANCE.md",
        "runtime/runner.js", "runtime/worker.js", "runtime/course_compat.py",
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

    runtime = (course / "runtime/worker.js").read_text(encoding="utf-8")
    client = (course / "course.js").read_text(encoding="utf-8")
    compatibility = (course / "runtime/course_compat.py").read_text(encoding="utf-8")
    boundary = runtime + client + compatibility
    if boundary.count("https://integrate.api.nvidia.com/v1") < 2:
        findings.append("direct NVIDIA API boundary is not explicit in both runtime and learner settings")
    forbidden = ["openclaw-cors-proxy", "nvidia-api-cors-proxy", "CF_Authorization", "_pomerium"]
    for token in forbidden:
        if token in boundary:
            findings.append(f"course runtime must not depend on unrelated proxy or launchable credential: {token}")
    if re.search(r"(?:nvapi-|Bearer\s+[A-Za-z0-9_-]{20,})", boundary):
        findings.append("course runtime contains a credential-shaped literal")
    for contract in ("primary product category", "counterfactual product category", "input sensitivity"):
        if contract not in compatibility:
            findings.append(f"assessment middleware omits required behavior check: {contract}")
    if "courseNvidiaChat" not in compatibility or "fetch(`${NVIDIA_BASE}/chat/completions`" not in runtime:
        findings.append("model cells are not connected to the real direct NVIDIA transport")
    if "new CoursePythonRunner" not in client or "buildXBlocks" not in client:
        findings.append("Markdown code cells are not upgraded through the shared executable XBlock path")
    for contract in (
        "application/x-course-chat+json", "coursePublicJson", "draw_mermaid_png",
        "additional_kwargs", '_install_module("wikipediaapi"',
    ):
        if contract not in boundary:
            findings.append(f"browser compatibility layer omits required source-course behavior: {contract}")
    if "cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/" not in runtime or 'PYODIDE_VERSION = "0.27.7"' not in runtime:
        findings.append("Pyodide runtime URL must remain version-pinned")
    if "source license is unresolved" not in (course / "SOURCE_PROVENANCE.md").read_text(encoding="utf-8").lower():
        findings.append("source provenance must fail closed on the unresolved source-course license")

    candidate_path = ROOT / "scripts/pyodide/candidate-components.json"
    try:
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        findings.append(f"cannot load browser-Python component evidence: {error}")
        candidate = {}
    adopted = candidate.get("course_candidate", {})
    if adopted.get("entrypoint") != "web/cfx11/runtime/worker.js" or adopted.get("direct_packages") != ["pydantic", "requests"]:
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
