#!/usr/bin/env python3
# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Fail closed before reusing a same-commit bundle validation report."""
from __future__ import annotations

import argparse
import copy
import json
import subprocess
from pathlib import Path


SCHEMA = "bundle-validation/1"
ROOT = Path(__file__).resolve().parents[2]


def current_short_sha() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
        check=False, text=True, capture_output=True,
    )
    if proc.returncode:
        raise RuntimeError("cannot resolve current Git commit for report reuse")
    return proc.stdout.strip()


def require_clean_tree() -> None:
    """Prevent a HEAD-labelled report from authorizing different local source bytes."""
    proc = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT,
        check=False, text=True, capture_output=True,
    )
    if proc.returncode:
        raise RuntimeError("cannot verify source-tree cleanliness for report reuse")
    if proc.stdout.strip():
        raise RuntimeError("source tree is dirty; regenerate validation instead of reusing a HEAD report")


def findings(data: dict, expected_sha: str) -> list[str]:
    out: list[str] = []
    if data.get("schema") != SCHEMA:
        out.append("unsupported or missing report schema")
    if data.get("git_sha") != expected_sha:
        out.append(f"report commit {data.get('git_sha')!r} does not match {expected_sha!r}")
    if data.get("scope") != "ship" or data.get("lang") != "en":
        out.append("report is not the English ship-scope result")
    if data.get("ok") is not True or data.get("validate_layout_ok") is not True:
        out.append("report did not pass required bundle or layout checks")
    gradient = data.get("gradient") or {}
    if gradient.get("required") != 0:
        out.append("report contains required findings")
    if data.get("degraded"):
        out.append("report contains degraded or skipped required suites")
    stats = data.get("link_stats") or {}
    for field in ("blocking_failures", "blocking_asset_leaks", "blocking_cross_course"):
        if stats.get(field) != 0:
            out.append(f"report contains {field}")
    suites = data.get("suites")
    if not isinstance(suites, list) or not suites:
        out.append("report has no suite evidence")
    elif any(item.get("tag") == "required" and item.get("status") != "clean" for item in suites):
        out.append("a required suite is not recorded as pass")
    return out


def read_report(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read validation report {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"validation report {path} is not a JSON object")
    return data


def self_test() -> list[str]:
    valid = {
        "schema": SCHEMA,
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
    mutations = (
        ("schema", lambda row: row.update(schema="older/0")),
        ("commit", lambda row: row.update(git_sha="different")),
        ("scope", lambda row: row.update(scope="all")),
        ("bundle result", lambda row: row.update(ok=False)),
        ("required findings", lambda row: row["gradient"].update(required=1)),
        ("degraded suite", lambda row: row.update(degraded=["links"])),
        ("blocking links", lambda row: row["link_stats"].update(blocking_failures=1)),
        ("required suite", lambda row: row["suites"][0].update(status="degraded")),
    )
    failures: list[str] = []
    if findings(valid, "abc1234"):
        failures.append("valid fixture was rejected")
    for label, mutate in mutations:
        row = copy.deepcopy(valid)
        mutate(row)
        if not findings(row, "abc1234"):
            failures.append(f"missed {label} mutation")
    from validate_bundle import _span
    multiline = [
        "def audit_contract(",
        "    data: dict,",
        "    *,",
        "    root=None,",
        ") -> list:",
        "    value = data.get('value')",
        "    return [value]",
        "",
        "def later():",
        "    return None",
    ]
    if _span(multiline, "audit_contract", "py") != [1, 7]:
        failures.append("multiline Python implementation span excludes the function body")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", default="docs/validation/latest.json")
    parser.add_argument("--expect-head", action="store_true")
    parser.add_argument("--expect-sha")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        failures = self_test()
        print("validation report self-test: " + ("FAIL" if failures else "PASS"))
        for item in failures:
            print("  FAIL " + item)
        return 1 if failures else 0
    try:
        if args.expect_head:
            require_clean_tree()
        expected = current_short_sha() if args.expect_head else args.expect_sha
        if not expected:
            raise RuntimeError("provide --expect-head or --expect-sha")
        rows = findings(read_report(Path(args.report)), expected)
    except RuntimeError as exc:
        print(f"validation report audit: FAIL: {exc}")
        return 1
    if rows:
        print("validation report audit: FAIL")
        for item in rows:
            print("  " + item)
        return 1
    print(f"validation report audit: PASS ({args.report} @ {expected})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
