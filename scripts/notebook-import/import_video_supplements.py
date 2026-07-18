#!/usr/bin/env python3
# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Bind invoked S-FX walkthrough widgets to the C-FX browser projection."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re


SCHEMA = "dli-course-video-supplements/1.0"
SOURCE_REPOSITORY = "https://gitlab.com/nvidia/dli/content/s-fx-12-v2"
MEDIA_PREFIX = "https://d36m44n9vdbmda.cloudfront.net/assets/s-fx-12-v2/"
TARGET_RENAMES = {
    "3-Prompting-With-Messages/35-Chatbots": "3-Prompting-With-Messages/36-Chatbots",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def helper_functions(path: Path) -> dict[str, str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    found: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("walkthrough_"):
            continue
        body = ast.get_source_segment(source, node) or ""
        urls = re.findall(r'https://[^"\']+\.mp4', body)
        if len(urls) != 1:
            raise ValueError(f"{path}: {node.name} must declare exactly one HTTPS MP4 URL")
        found[node.name] = urls[0]
    return found


def invoked_walkthrough(notebook: dict, relative: str) -> tuple[str, int]:
    imported: list[str] = []
    called: list[int] = []
    for index, cell in enumerate(notebook.get("cells", [])):
        source = "".join(cell.get("source", []))
        imported.extend(re.findall(r"from videos\.walkthroughs import (walkthrough_\d+) as walkthrough", source))
        if re.search(r"(?m)^walkthrough\(\)\s*$", source):
            called.append(index)
    if len(imported) != 1 or len(called) != 1:
        raise ValueError(f"{relative}: expected one walkthrough import and one widget call")
    return imported[0], called[0]


def build(source: Path, target: Path, commit: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("source commit must be a full 40-character Git commit")
    course = json.loads((target / "course.json").read_text(encoding="utf-8"))
    titles = {lesson["id"]: lesson["title"] for lesson in course["lessons"]}
    entries: list[dict] = []
    declared: set[tuple[str, str]] = set()
    invoked: set[tuple[str, str]] = set()

    for helper in sorted(source.rglob("videos/walkthroughs.py")):
        functions = helper_functions(helper)
        helper_relative = helper.relative_to(source).as_posix()
        declared.update((helper_relative, name) for name in functions)
    for notebook_path in sorted(source.rglob("*.ipynb")):
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        if not any("videos.walkthroughs" in "".join(cell.get("source", [])) for cell in notebook.get("cells", [])):
            continue
        source_notebook = notebook_path.relative_to(source).as_posix()
        function, call_cell = invoked_walkthrough(notebook, source_notebook)
        helper = notebook_path.parent / "videos/walkthroughs.py"
        functions = helper_functions(helper)
        if function not in functions:
            raise ValueError(f"{source_notebook}: {function} is absent from {helper}")
        helper_relative = helper.relative_to(source).as_posix()
        invoked.add((helper_relative, function))
        target_id = TARGET_RENAMES.get(source_notebook.removesuffix(".ipynb"), source_notebook.removesuffix(".ipynb"))
        if target_id not in titles:
            raise ValueError(f"{source_notebook}: no target lesson {target_id}")
        media_url = functions[function]
        if not media_url.startswith(MEDIA_PREFIX):
            raise ValueError(f"{source_notebook}: media URL leaves the reviewed S-FX asset prefix")
        entries.append({
            "id": function,
            "lesson_id": target_id,
            "lesson_title": titles[target_id],
            "insert_after_cell": 1,
            "source_notebook": source_notebook,
            "source_notebook_sha256": digest(notebook_path),
            "source_widget_cell": call_cell,
            "source_helper": helper_relative,
            "source_helper_sha256": digest(helper),
            "source_function": function,
            "media_url": media_url,
            "media_type": "video/mp4",
            "distribution": "referenced-not-copied",
        })

    unused = [f"{helper}#{name}" for helper, name in sorted(declared - invoked)]
    return {
        "schema": SCHEMA,
        "source": {
            "repository": SOURCE_REPOSITORY,
            "commit": commit,
            "scope": "task1/dli",
            "relationship": "supplemental walkthroughs referenced from the adjacent instructor-led course",
            "terms": "NVIDIA-owned course assets; reuse terms are not asserted by this repository",
        },
        "entries": entries,
        "source_audit": {
            "invoked_widget_count": len(entries),
            "unused_helper_functions": unused,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="S-FX task1/dli directory")
    parser.add_argument("target", type=Path, help="C-FX web course directory")
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or args.target / "video-supplements.json"
    payload = build(args.source.resolve(), args.target.resolve(), args.source_commit)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload['entries'])} invoked walkthroughs to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
