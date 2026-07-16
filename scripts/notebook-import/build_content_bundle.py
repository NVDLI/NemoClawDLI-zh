#!/usr/bin/env python3
# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Build the browser-readable C-FX-11 lesson bundle from reviewed Markdown.

GitLab Pages retains the imported ``.md`` files in its job artifact but does not
serve those paths.  The browser therefore reads one JSON projection whose rows
remain bound to the Markdown digests in ``course.json``.  Markdown remains the
reviewed source; this file is only its deterministic delivery form.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA = "dli-markdown-delivery/1.0"


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build(course: Path) -> dict:
    manifest = json.loads((course / "course.json").read_text(encoding="utf-8"))
    lessons: dict[str, dict[str, str]] = {}
    for lesson in manifest.get("lessons", []):
        relative = str(lesson.get("markdown_path") or "")
        path = (course / relative).resolve()
        if not relative.startswith("content/") or not path.is_relative_to(course.resolve()):
            raise ValueError(f"unsafe Markdown path in course manifest: {relative!r}")
        markdown = path.read_text(encoding="utf-8")
        actual = digest_text(markdown)
        expected = str(lesson.get("markdown_sha256") or "")
        if actual != expected:
            raise ValueError(f"Markdown digest differs from course manifest: {relative}")
        lessons[relative] = {"sha256": actual, "markdown": markdown}
    if len(lessons) != len(manifest.get("lessons", [])):
        raise ValueError("lesson delivery paths are not unique")
    return {"schema": SCHEMA, "lessons": lessons}


def encoded(bundle: dict) -> str:
    return json.dumps(bundle, ensure_ascii=False, separators=(",", ":")) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--course", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    course = args.course.resolve()
    output = (args.output or course / "content-bundle.json").resolve()
    payload = encoded(build(course))
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != payload:
            print(f"content bundle is stale or missing: {output}")
            return 1
        print(f"content bundle: PASS ({len(json.loads(payload)['lessons'])} lessons)")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload, encoding="utf-8")
    print(f"content bundle: wrote {output} ({len(json.loads(payload)['lessons'])} lessons)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
