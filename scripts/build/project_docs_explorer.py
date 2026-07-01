#!/usr/bin/env python3
"""Project docs explorer files and rendered Markdown targets into a Pages artifact."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit


CONFIG_RE = re.compile(
    r'<script[^>]*id="explorer-config"[^>]*>(.*?)</script>', re.DOTALL
)
FENCE_RE = re.compile(r"(?:^|\n)(?:```|~~~).*?(?=\n(?:```|~~~)(?:\n|$))", re.DOTALL)
INLINE_LINK_RE = re.compile(r"!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|[^)\s]+)")
REFERENCE_LINK_RE = re.compile(r"^\s{0,3}\[[^\]\n]+\]:\s*(<[^>\n]+>|\S+)", re.MULTILINE)


class ProjectionError(ValueError):
    """Raised when a declared or linked artifact cannot be projected safely."""


def explorer_config(skill: Path) -> dict:
    match = CONFIG_RE.search(skill.read_text(encoding="utf-8"))
    if not match:
        raise ProjectionError("docs explorer projection: missing explorer-config")
    try:
        config = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ProjectionError(f"docs explorer projection: invalid explorer-config: {exc}") from exc
    if not isinstance(config.get("files"), list):
        raise ProjectionError("docs explorer projection: explorer-config.files must be an array")
    return config


def local_markdown_targets(path: Path) -> list[str]:
    """Return local inline/image/reference targets from one rendered Markdown file."""
    text = FENCE_RE.sub("\n", path.read_text(encoding="utf-8"))
    raw_targets = [match.group(1) for match in INLINE_LINK_RE.finditer(text)]
    raw_targets.extend(match.group(1) for match in REFERENCE_LINK_RE.finditer(text))
    targets: list[str] = []
    for raw in raw_targets:
        target = raw.strip().strip("<>")
        if not target or target.startswith("#"):
            continue
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc:
            continue
        decoded = unquote(parsed.path)
        if decoded:
            targets.append(decoded)
    return targets


def safe_source(root: Path, base: Path, relative: str, *, context: str) -> Path:
    if "\\" in relative or "\x00" in relative:
        raise ProjectionError(f"docs explorer projection: unsafe {context}: {relative}")
    target = (base / relative).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise ProjectionError(
            f"docs explorer projection: missing or unsafe {context}: {relative}"
        )
    return target


def copy_into_artifact(source: Path, source_root: Path, artifact_root: Path) -> Path:
    destination = (artifact_root / source.relative_to(source_root)).resolve()
    if not destination.is_relative_to(artifact_root):
        raise ProjectionError(f"docs explorer projection: unsafe artifact target: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def project(source_skill: Path, source_root: Path, artifact_root: Path) -> tuple[int, int]:
    source_root = source_root.resolve()
    artifact_root = artifact_root.resolve()
    source_skill = source_skill.resolve()
    if not source_skill.is_relative_to(source_root) or not source_skill.is_file():
        raise ProjectionError("docs explorer projection: source SKILL.html is outside the repository")

    config = explorer_config(source_skill)
    declared: list[Path] = []
    for entry in config["files"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ProjectionError("docs explorer projection: every file entry needs a string path")
        source = safe_source(
            source_root, source_skill.parent, entry["path"], context="declared file"
        )
        copy_into_artifact(source, source_root, artifact_root)
        declared.append(source)

    linked: set[Path] = set()
    for markdown in (path for path in declared if path.suffix.lower() == ".md"):
        for relative in local_markdown_targets(markdown):
            source = safe_source(
                source_root,
                markdown.parent,
                relative,
                context=f"local Markdown target from {markdown.relative_to(source_root)}",
            )
            copy_into_artifact(source, source_root, artifact_root)
            linked.add(source)

    for source in set(declared) | linked:
        destination = artifact_root / source.relative_to(source_root)
        if not destination.is_file():
            raise ProjectionError(
                "docs explorer projection: projected file missing from artifact: "
                f"{source.relative_to(source_root)}"
            )
    return len(declared), len(linked)


def self_test() -> tuple[int, int, list[str]]:
    failures: list[str] = []
    total = 4
    with tempfile.TemporaryDirectory(prefix="docs-projection-") as tmp:
        base = Path(tmp)
        root = base / "repo"
        docs = root / "docs"
        docs.mkdir(parents=True)
        (root / "RELEASE_STATUS.json").write_text('{"state":"draft"}\n', encoding="utf-8")
        (docs / "design.md").write_text(
            "[state](../RELEASE_STATUS.json) [outside](https://example.com)\n",
            encoding="utf-8",
        )
        skill = docs / "SKILL.html"
        skill.write_text(
            '<script type="application/json" id="explorer-config">'
            '{"files":[{"path":"design.md"}]}</script>\n',
            encoding="utf-8",
        )

        artifact = base / "artifact"
        declared, linked = project(skill, root, artifact)
        checks = [
            (declared == 1 and linked == 1, "declared and linked counts"),
            ((artifact / "docs/design.md").is_file(), "declared file projection"),
            ((artifact / "RELEASE_STATUS.json").is_file(), "Markdown target projection"),
        ]
        failures.extend(label for passed, label in checks if not passed)

        (docs / "design.md").write_text("[missing](../missing.json)\n", encoding="utf-8")
        try:
            project(skill, root, base / "broken-artifact")
        except ProjectionError as exc:
            if "local Markdown target" not in str(exc):
                failures.append("missing target error classification")
        else:
            failures.append("missing target was accepted")

    return total - len(failures), total, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-skill", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        passed, total, failures = self_test()
        print(f"docs explorer projection self-test: {passed}/{total} passed")
        for failure in failures:
            print(f"  FAIL {failure}")
        return 1 if failures else 0
    if not (args.source_skill and args.source_root and args.artifact_root):
        parser.error("--source-skill, --source-root, and --artifact-root are required")
    try:
        declared, linked = project(args.source_skill, args.source_root, args.artifact_root)
    except (OSError, ProjectionError) as exc:
        print(exc)
        return 1
    print(
        f"[build_pages] docs explorer projection: {declared} declared files and "
        f"{linked} local Markdown targets resolve"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
