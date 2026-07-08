#!/usr/bin/env python3
"""Project the exact Git source tree into Pages so every SKILL explorer remains usable."""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


def source_files(root: Path) -> list[Path]:
    raw = subprocess.check_output(
        ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
    )
    return sorted(Path(item.decode()) for item in raw.split(b"\0") if item)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project(root: Path, output: Path) -> tuple[int, list[str]]:
    findings = []
    files = source_files(root)
    for relative in files:
        source = root / relative
        target = output / relative
        if not source.is_file():
            findings.append(f"source is not a regular file: {relative}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for relative in files:
        source = root / relative
        target = output / relative
        if not target.is_file():
            findings.append(f"projected source is missing: {relative}")
        elif source.stat().st_size != target.stat().st_size or digest(source) != digest(target):
            findings.append(f"projected source differs: {relative}")
    return len(files), findings


class ProjectionTests(unittest.TestCase):
    def test_tracked_and_proposed_files_project_but_ignored_output_does_not(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"
            output = Path(temp) / "artifact"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text("ignored/\n", encoding="utf-8")
            (root / "SKILL.html").write_text("root", encoding="utf-8")
            (root / "nested").mkdir()
            (root / "nested" / "tracked.txt").write_text("tracked", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", ".gitignore", "SKILL.html", "nested/tracked.txt"], check=True)
            (root / "nested" / "proposed.txt").write_text("proposed", encoding="utf-8")
            (root / "ignored").mkdir()
            (root / "ignored" / "build.txt").write_text("ignored", encoding="utf-8")
            count, findings = project(root, output)
            self.assertEqual(findings, [])
            self.assertEqual(count, 4)
            self.assertTrue((output / "nested" / "tracked.txt").is_file())
            self.assertTrue((output / "nested" / "proposed.txt").is_file())
            self.assertFalse((output / "ignored" / "build.txt").exists())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ProjectionTests)
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    if not args.source_root or not args.artifact_root:
        parser.error("--source-root and --artifact-root are required unless --self-test is used")
    count, findings = project(args.source_root.resolve(), args.artifact_root.resolve())
    if findings:
        print(f"source explorer projection: FAIL ({len(findings)})")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print(f"source explorer projection: PASS ({count} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
