#!/usr/bin/env python3
# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Project a Jupyter course into reviewable Markdown without rewriting cells.

The importer adds machine-readable boundary comments around the original cell
source. It never normalizes, formats, or repairs source text. The resulting
manifest binds every imported cell and supporting file to the source archive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path, PurePosixPath


SCHEMA = "dli-markdown-course/1.0"
CELL_MARKER = "dli-course-cell"
SUPPORT_SUFFIXES = {".gif", ".jpeg", ".jpg", ".json", ".png", ".svg", ".webp"}
SOURCE_PATCHES = {
    ("1-Intro-to-Prompting/15-Iterative-Prompting.ipynb", 69): {
        "type": "code",
        "upstream_source_sha256": "5f3a6324a6eb3b2a150244af8388dac9048789a32be55a0a3e3c86132f684ba8",
        "before": 'Portland, OR 97203""""""',
        "after": 'Portland, OR 97203"""',
        "reason": "Remove the accidental second triple-quote opener that makes the original exercise cell invalid Python.",
    },
    ("3-Prompting-With-Messages/36-Chatbots.ipynb", 76): {
        "type": "markdown",
        "upstream_source_sha256": "36fbbf2de0109959505aa56a5bc701e41977d17c33105601ac7efd6fb8a2873e",
        "before": "](chat_helpers/gradio_interface.py)",
        "after": "](https://gitlab.com/nvidia/dli/content/c-fx-11-v1/-/blob/main/task1/dli/3-Prompting-With-Messages/chat_helpers/gradio_interface.py)",
        "reason": "Point the source-code reference to the upstream repository because the unresolved helper file is not copied into this internal candidate.",
    },
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def source_text(cell: dict) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(source)
    if isinstance(source, str):
        return source
    raise ValueError(f"cell source must be a string or list, got {type(source).__name__}")


def project_source(relative: Path, index: int, kind: str, source: str) -> tuple[str, dict | None]:
    patch = SOURCE_PATCHES.get((relative.as_posix(), index))
    if patch is None:
        return source, None
    upstream_sha256 = sha256_text(source)
    if kind != patch["type"] or upstream_sha256 != patch["upstream_source_sha256"]:
        raise ValueError(f"{relative}: reviewed source patch no longer matches cell {index}")
    if source.count(patch["before"]) != 1:
        raise ValueError(f"{relative}: reviewed source patch target is not unique in cell {index}")
    projected = source.replace(patch["before"], patch["after"], 1)
    return projected, {
        "schema": "dli-course-source-patch/1.0",
        "upstream_source_sha256": upstream_sha256,
        "reason": patch["reason"],
    }


def code_fence(source: str) -> str:
    longest = max((len(match.group(0)) for match in re.finditer(r"`+", source)), default=0)
    return "`" * max(3, longest + 1)


def lesson_title(notebook: dict, fallback: str) -> str:
    del notebook
    title = re.sub(r"^\d+[-_ ]*", "", fallback).replace("-", " ").strip().title()
    replacements = {"Nvidia": "NVIDIA", "Lcel": "LCEL", "Nim": "NIM", "Openai": "OpenAI", "Pydantic": "Pydantic"}
    return " ".join(replacements.get(word, word) for word in title.split())


def natural_key(path: Path) -> tuple:
    relative = path.as_posix()
    if relative == "Workshop-Intro.ipynb":
        return (0,)
    parts: list[object] = [1]
    for token in re.split(r"(\d+)", relative.lower()):
        parts.append(int(token) if token.isdigit() else token)
    return tuple(parts)


def validate_relative(path: PurePosixPath) -> None:
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe relative path: {path}")


def render_notebook(source_path: Path, relative: Path) -> tuple[str, dict]:
    raw = source_path.read_bytes()
    notebook = json.loads(raw)
    if notebook.get("nbformat") != 4:
        raise ValueError(f"{relative}: only nbformat 4 is supported")

    markdown: list[str] = []
    cells: list[dict] = []
    for index, cell in enumerate(notebook.get("cells", [])):
        kind = cell.get("cell_type")
        if kind not in {"markdown", "code", "raw"}:
            raise ValueError(f"{relative}: unsupported cell type {kind!r} at {index}")
        source, source_patch = project_source(relative, index, kind, source_text(cell))
        cell_id = f"{relative.with_suffix('').as_posix()}:{index}"
        record = {
            "id": cell_id,
            "index": index,
            "type": kind,
            "source_sha256": sha256_text(source),
            "source_bytes": len(source.encode("utf-8")),
            "source_ends_with_newline": source.endswith("\n"),
        }
        if cell.get("metadata"):
            record["metadata"] = cell["metadata"]
        if source_patch:
            record["source_patch"] = source_patch
        cells.append(record)
        marker = json.dumps({
            "schema": "dli-course-cell/1.0",
            "id": cell_id,
            "index": index,
            "type": kind,
            "source_sha256": record["source_sha256"],
        }, sort_keys=True, separators=(",", ":"))
        markdown.append(f"<!-- {CELL_MARKER} {marker} -->\n")
        if kind == "code":
            fence = code_fence(source)
            suffix = "" if source.endswith("\n") or not source else "\n"
            markdown.append(f"{fence}python\n{source}{suffix}{fence}\n")
        else:
            markdown.append(source)
            if source and not source.endswith("\n"):
                markdown.append("\n")
        markdown.append(f"<!-- /{CELL_MARKER} -->\n\n")

    rendered = "".join(markdown)
    if rendered.endswith("\n\n"):
        rendered = rendered[:-1]
    return rendered, {
        "id": relative.with_suffix("").as_posix(),
        "title": lesson_title(notebook, relative.stem),
        "unit": relative.parts[0] if len(relative.parts) > 1 else "Course introduction",
        "source_path": f"task1/dli/{relative.as_posix()}",
        "source_sha256": sha256_bytes(raw),
        "markdown_path": f"content/{relative.with_suffix('.md').as_posix()}",
        "markdown_sha256": sha256_text(rendered),
        "cells": cells,
    }


def import_course(source: Path, destination: Path, artifact_sha256: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{64}", artifact_sha256):
        raise ValueError("--artifact-sha256 must be a lowercase SHA-256 digest")
    if not source.is_dir():
        raise ValueError(f"source directory does not exist: {source}")

    content = destination / "content"
    if content.exists():
        shutil.rmtree(content)
    content.mkdir(parents=True)

    lessons: list[dict] = []
    for notebook_path in sorted(source.rglob("*.ipynb"), key=lambda path: natural_key(path.relative_to(source))):
        relative = notebook_path.relative_to(source)
        rendered, record = render_notebook(notebook_path, relative)
        target = content / relative.with_suffix(".md")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
        lessons.append(record)

    support: list[dict] = []
    for source_path in sorted(path for path in source.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORT_SUFFIXES):
        relative = source_path.relative_to(source)
        validate_relative(PurePosixPath(relative.as_posix()))
        target = content / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target)
        support.append({
            "path": f"content/{relative.as_posix()}",
            "sha256": sha256_bytes(source_path.read_bytes()),
            "bytes": source_path.stat().st_size,
        })

    manifest = {
        "schema": SCHEMA,
        "course": {
            "id": "c-fx-11-v1",
            "title": "Building LLM Applications With Prompt Engineering",
            "source_artifact_sha256": artifact_sha256,
            "source_scope": "task1/dli",
            "source_repository_modified": False,
        },
        "lessons": lessons,
        "supporting_files": support,
        "totals": {
            "lessons": len(lessons),
            "cells": sum(len(lesson["cells"]) for lesson in lessons),
            "code_cells": sum(cell["type"] == "code" for lesson in lessons for cell in lesson["cells"]),
            "markdown_cells": sum(cell["type"] == "markdown" for lesson in lessons for cell in lesson["cells"]),
            "supporting_files": len(support),
        },
    }
    (destination / "course.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True, help="Path to the source task1/dli directory")
    parser.add_argument("--destination", type=Path, required=True, help="Path to web/<course>")
    parser.add_argument("--artifact-sha256", required=True, help="SHA-256 of the reviewed source archive")
    args = parser.parse_args()
    manifest = import_course(args.source.resolve(), args.destination.resolve(), args.artifact_sha256)
    print(
        "import_course: "
        f"{manifest['totals']['lessons']} lessons, "
        f"{manifest['totals']['cells']} cells, "
        f"{manifest['totals']['supporting_files']} supporting files"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
