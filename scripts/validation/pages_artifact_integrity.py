#!/usr/bin/env python3
"""Fail closed on an unexpected or substituted GitHub Pages artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


MANIFEST_NAME = "pages-sha256.txt"
MANIFEST_SCHEMA = "nemoclaw-pages-sha256/1"
REQUIRED = (
    "index.html",
    "branches.json",
    "languages.json",
    "gate.json",
    "nemoclaw/index.html",
    "nemoclaw/scripts/_shared.js",
    "nemoclaw/vendor/browser-dependencies.json",
    "nemoclaw/vendor/browser-sbom.cdx.json",
)
SHA = re.compile(r"[0-9a-f]{7,40}")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def remote(value: str) -> bool:
    parsed = urlsplit(value.strip())
    return value.strip().startswith("//") or parsed.scheme.lower() in {"http", "https"}


class ExecutableReferenceParser(HTMLParser):
    """Find remote executable references; learner links and media remain allowed."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.findings: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.lower(): value or "" for name, value in attrs}
        tag = tag.lower()
        if tag == "script" and remote(values.get("src", "")):
            self.findings.append(f"remote script source {values['src']}")
        if tag == "link" and "stylesheet" in values.get("rel", "").lower().split() and remote(values.get("href", "")):
            self.findings.append(f"remote stylesheet source {values['href']}")
        if tag == "base" and remote(values.get("href", "")):
            self.findings.append(f"remote base URL {values['href']}")


def manifest_text(root: Path, expected_sha: str) -> str:
    rows = [f"# {MANIFEST_SCHEMA} commit={expected_sha}"]
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix()
        if rel == MANIFEST_NAME or not path.is_file() or path.is_symlink():
            continue
        rows.append(f"{digest(path)}  {rel}")
    return "\n".join(rows) + "\n"


def audit(root: Path, expected_sha: str, manifest: Path | None = None) -> list[str]:
    findings: list[str] = []
    if not SHA.fullmatch(expected_sha):
        return ["expected commit must be a 7-40 character lowercase hexadecimal SHA"]
    if not root.is_dir():
        return [f"artifact root is not a directory: {root}"]

    for rel in REQUIRED:
        if not (root / rel).is_file():
            findings.append(f"missing required artifact file: {rel}")

    files = 0
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            findings.append(f"artifact contains symlink: {rel}")
            continue
        if path.is_dir():
            continue
        if not path.is_file():
            findings.append(f"artifact contains unsupported file type: {rel}")
            continue
        files += 1
        if path.suffix.lower() == ".html":
            parser = ExecutableReferenceParser()
            try:
                parser.feed(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError) as exc:
                findings.append(f"cannot parse HTML {rel}: {exc}")
            findings.extend(f"{rel}: {item}" for item in parser.findings)
    if files < len(REQUIRED):
        findings.append(f"artifact file count is implausibly small: {files}")

    gate = root / "gate.json"
    if gate.is_file():
        try:
            data = json.loads(gate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            findings.append(f"gate.json is unreadable: {exc}")
        else:
            from validation_report_audit import findings as report_findings

            findings.extend(f"gate.json: {item}" for item in report_findings(data, expected_sha))

    if manifest is not None:
        try:
            actual = manifest.read_text(encoding="utf-8")
        except OSError as exc:
            findings.append(f"cannot read integrity manifest: {exc}")
        else:
            expected = manifest_text(root, expected_sha)
            if actual != expected:
                findings.append("integrity manifest does not match the extracted Pages tree")
    return findings


def self_test() -> list[str]:
    failures: list[str] = []
    valid_report = {
        "schema": "bundle-validation/1",
        "git_sha": "abc1234",
        "scope": "ship",
        "lang": "en",
        "ok": True,
        "validate_layout_ok": True,
        "gradient": {"required": 0},
        "degraded": [],
        "link_stats": {"blocking_failures": 0, "blocking_asset_leaks": 0, "blocking_cross_course": 0},
        "suites": [{"id": "bundle", "tag": "required", "status": "clean"}],
    }
    with tempfile.TemporaryDirectory(prefix="pages-artifact-integrity-") as tmp:
        root = Path(tmp) / "baseline"
        for rel in REQUIRED:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("<html></html>\n" if path.suffix == ".html" else "{}\n", encoding="utf-8")
        (root / "gate.json").write_text(json.dumps(valid_report), encoding="utf-8")
        manifest = root / MANIFEST_NAME
        manifest.write_text(manifest_text(root, "abc1234"), encoding="utf-8")
        if audit(root, "abc1234", manifest):
            failures.append("clean fixture was rejected")

        mutations = (
            ("missing file", lambda fixture: (fixture / "nemoclaw/index.html").unlink()),
            ("remote script", lambda fixture: (fixture / "index.html").write_text('<script src="https://evil.invalid/x.js"></script>', encoding="utf-8")),
            ("wrong gate SHA", lambda fixture: (fixture / "gate.json").write_text(json.dumps({**valid_report, "git_sha": "def5678"}), encoding="utf-8")),
            ("changed after manifest", lambda fixture: (fixture / "languages.json").write_text('{"changed":true}\n', encoding="utf-8")),
            ("symlink", lambda fixture: (fixture / "injected-link").symlink_to(fixture / "index.html")),
        )
        for label, mutate in mutations:
            fixture = Path(tmp) / f"case-{label.replace(' ', '-')}"
            shutil.copytree(root, fixture)
            mutate(fixture)
            if not audit(fixture, "abc1234", fixture / MANIFEST_NAME):
                failures.append(f"mutation escaped: {label}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--expect-sha")
    parser.add_argument("--write-manifest", type=Path)
    parser.add_argument("--check-manifest", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        failures = self_test()
        total = 6
        print(f"Pages artifact integrity self-test: {total - len(failures)}/{total} passed")
        for finding in failures:
            print("  " + finding)
        return 1 if failures else 0
    if not args.root or not args.expect_sha:
        parser.error("--root and --expect-sha are required")
    root = args.root.resolve()
    findings = audit(root, args.expect_sha, args.check_manifest)
    if findings:
        print(f"Pages artifact integrity: FAIL ({len(findings)})")
        for finding in findings:
            print("  " + finding)
        return 1
    if args.write_manifest:
        target = args.write_manifest.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(manifest_text(root, args.expect_sha), encoding="utf-8")
    print(f"Pages artifact integrity: PASS ({sum(1 for path in root.rglob('*') if path.is_file())} files @ {args.expect_sha})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
