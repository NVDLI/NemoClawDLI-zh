#!/usr/bin/env python3
# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Reject unpinned or stale material-tool and SCA dependency locks."""
from __future__ import annotations

import argparse
import re
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAIRS = (
    ("scripts/materials/requirements.lock.in", "scripts/materials/requirements.lock"),
    ("scripts/security/requirements-sca.lock.in", "scripts/security/requirements-sca.lock"),
)
PIN = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?==([^\s;]+)(?:\s*;\s*.+)?$")


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def pins(path: Path) -> tuple[dict[str, str], list[str]]:
    found: dict[str, str] = {}
    errors: list[str] = []
    if not path.is_file():
        return found, [f"{path}: missing dependency file"]
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split(" #", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        match = PIN.fullmatch(line)
        if not match:
            errors.append(f"{path}:{line_no}: dependency must use one exact == version: {line}")
            continue
        name, version = norm(match.group(1)), match.group(2)
        if name in found and found[name] != version:
            errors.append(f"{path}:{line_no}: duplicate {name} versions {found[name]} and {version}")
        found[name] = version
    return found, errors


def audit(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for source_rel, lock_rel in PAIRS:
        source, source_errors = pins(root / source_rel)
        lock, lock_errors = pins(root / lock_rel)
        errors.extend(source_errors)
        errors.extend(lock_errors)
        for name, version in source.items():
            if lock.get(name) != version:
                errors.append(f"{lock_rel}: stale direct pin {name}; expected {version}, found {lock.get(name, 'missing')}")
    return errors


def self_test() -> list[str]:
    failures: list[str] = []
    if audit(ROOT):
        return ["baseline dependency lock contract is not clean"]
    with tempfile.TemporaryDirectory(prefix="dependency-lock-audit-") as td:
        fixture = Path(td)
        for source, lock in PAIRS:
            for rel in (source, lock):
                dst = fixture / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / rel, dst)
        mutations = (
            ("scripts/materials/requirements.lock", "requests==2.33.0", "requests==0.0.1"),
            ("scripts/security/requirements-sca.lock", "pip-audit==2.10.1", "# removed pip-audit"),
        )
        for rel, old, new in mutations:
            path = fixture / rel
            baseline = path.read_text(encoding="utf-8")
            if old not in baseline:
                failures.append(f"fixture token missing: {rel}: {old}")
                continue
            path.write_text(baseline.replace(old, new, 1), encoding="utf-8")
            if not audit(fixture):
                failures.append(f"mutation escaped detector: {rel}")
            path.write_text(baseline, encoding="utf-8")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    errors = self_test() if args.self_test else audit()
    if errors:
        print(f"dependency lock audit: FAIL ({len(errors)})")
        for error in errors:
            print(f"  {error}")
        return 1
    print("dependency lock audit: OK" + (" (mutation self-test)" if args.self_test else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
