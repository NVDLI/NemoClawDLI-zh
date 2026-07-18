#!/usr/bin/env python3
# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Verify every repository-copied c-fx-11 browser wheel against its lock."""

from __future__ import annotations

import email
import hashlib
import json
import re
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "web" / "cfx11" / "runtime"
LOCK = RUNTIME / "wheels.lock.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(runtime: Path = RUNTIME) -> list[str]:
    lock = runtime / "wheels.lock.json"
    try:
        data = json.loads(lock.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"wheel lock cannot be read: {error}"]
    findings: list[str] = []
    recorded: set[Path] = set()
    names: set[str] = set()
    for package in data.get("packages", []):
        name = str(package.get("name") or "")
        version = str(package.get("version") or "")
        relative = Path(str(package.get("path") or ""))
        path = runtime / relative
        recorded.add(path.resolve())
        if not name or name.lower() in names:
            findings.append(f"missing or duplicate package name: {name!r}")
        names.add(name.lower())
        if package.get("relationship") not in {"direct", "transitive"}:
            findings.append(f"invalid relationship: {name}")
        if not str(package.get("license_expression") or "").strip():
            findings.append(f"missing license expression: {name}")
        if not str(package.get("source_url") or "").startswith("https://files.pythonhosted.org/"):
            findings.append(f"source URL is not an exact PyPI artifact: {name}")
        if str(package.get("source_url") or "").endswith((".tar.gz", ".zip")) and not re.fullmatch(
            r"[0-9a-f]{64}", str(package.get("source_sha256") or "")
        ):
            findings.append(f"source archive hash missing or malformed: {name}")
        patch_relative = str(package.get("patch") or "")
        patch_sha256 = str(package.get("patch_sha256") or "")
        if patch_relative:
            patch_path = (ROOT / patch_relative).resolve()
            try:
                patch_path.relative_to(ROOT)
            except ValueError:
                findings.append(f"patch escapes the repository: {name}")
            else:
                if not patch_path.is_file():
                    findings.append(f"missing build patch: {patch_relative}")
                elif digest(patch_path) != patch_sha256:
                    findings.append(f"build patch hash differs: {patch_relative}")
        elif patch_sha256:
            findings.append(f"patch hash has no patch path: {name}")
        if not path.is_file():
            findings.append(f"missing wheel: {relative}")
            continue
        if digest(path) != package.get("sha256"):
            findings.append(f"wheel hash differs: {relative}")
        try:
            with zipfile.ZipFile(path) as archive:
                metadata_name = next(item for item in archive.namelist() if item.endswith(".dist-info/METADATA"))
                metadata = email.message_from_bytes(archive.read(metadata_name))
        except (OSError, zipfile.BadZipFile, StopIteration) as error:
            findings.append(f"wheel metadata cannot be read: {relative}: {error}")
            continue
        if metadata.get("Name", "").lower().replace("_", "-") != name.lower().replace("_", "-"):
            findings.append(f"wheel name differs: {relative}")
        if metadata.get("Version") != version:
            findings.append(f"wheel version differs: {relative}")

    actual = {path.resolve() for path in (runtime / "wheels").rglob("*.whl")}
    for path in sorted(actual - recorded):
        findings.append(f"unrecorded wheel: {path.relative_to(ROOT)}")
    for path in sorted(recorded - actual):
        findings.append(f"recorded wheel is absent: {path.relative_to(ROOT)}")

    return findings


def main() -> int:
    findings = audit()
    if findings:
        print(f"cfx11 wheel verification: FAIL ({len(findings)})")
        for finding in findings:
            print(f"  - {finding}")
        return 1
    data = json.loads(LOCK.read_text(encoding="utf-8"))
    print(f"cfx11 wheel verification: PASS ({len(data['packages'])} wheels)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
