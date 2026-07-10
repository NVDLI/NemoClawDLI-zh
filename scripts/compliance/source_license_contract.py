# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Audit and apply the repository's Apache-2.0 source-license contract."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Iterable


COPYRIGHT = "Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved."
SPDX = "SPDX-License-Identifier: Apache-2.0"
AUTHORED_ROOTS = {"scripts", "web", "tests", "cpu", "workspace"}
COMMENT_PREFIX = {".py": "#", ".js": "//", ".mjs": "//"}
NON_AUTHORED_PREFIXES = ("web/nemoclaw/vendor/",)
NOTICE_LINKS = (
    "THIRD_PARTY_LICENSES.md",
    "web/nemoclaw/vendor/browser-dependencies.json",
    "web/nemoclaw/vendor/licenses/",
    "scripts/compliance/docs/vendor_policy.md",
)
DCO_1_1 = """Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.

Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved."""


def relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def repository_files(root: Path) -> list[Path]:
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    proposed = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    return [root / item for item in dict.fromkeys(tracked + proposed) if (root / item).is_file()]


def authored_sources(root: Path, files: Iterable[Path]) -> list[Path]:
    sources = []
    for path in files:
        rel = relative(path, root)
        if path.suffix.lower() not in COMMENT_PREFIX or not path.stat().st_size:
            continue
        if rel.split("/", 1)[0] not in AUTHORED_ROOTS:
            continue
        if rel.startswith(NON_AUTHORED_PREFIXES):
            continue
        sources.append(path)
    return sorted(sources)


def header_lines(path: Path) -> tuple[str, str]:
    prefix = COMMENT_PREFIX[path.suffix.lower()]
    return f"{prefix} {COPYRIGHT}", f"{prefix} {SPDX}"


def has_header(path: Path) -> bool:
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    start = 1 if lines and lines[0].startswith("#!") else 0
    expected = header_lines(path)
    return tuple(lines[start:start + len(expected)]) == expected


def apply_headers(root: Path, files: Iterable[Path]) -> list[str]:
    changed = []
    for path in authored_sources(root, files):
        if has_header(path):
            continue
        text = path.read_text(encoding="utf-8-sig")
        lines = text.splitlines(keepends=True)
        insertion = 1 if lines and lines[0].startswith("#!") else 0
        newline = "\r\n" if "\r\n" in text else "\n"
        header = [line + newline for line in header_lines(path)]
        if text.strip():
            header.append(newline)
        else:
            lines = []
            insertion = 0
        path.write_text("".join(lines[:insertion] + header + lines[insertion:]), encoding="utf-8")
        changed.append(relative(path, root))
    return changed


def audit(root: Path, files: Iterable[Path]) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    successes: list[str] = []

    license_path = root / "LICENSE"
    license_text = license_path.read_text(encoding="utf-8", errors="replace") if license_path.is_file() else ""
    if license_text.startswith(COPYRIGHT + "\n\n") and "Apache License\n" in license_text and "Version 2.0" in license_text:
        successes.append("root license: NVIDIA copyright precedes Apache-2.0")
    else:
        failures.append("root license: LICENSE must begin with the exact NVIDIA copyright line before Apache-2.0")

    dco_path = root / "DCO.md"
    dco_text = dco_path.read_text(encoding="utf-8", errors="replace") if dco_path.is_file() else ""
    if DCO_1_1 in dco_text:
        successes.append("DCO: complete verbatim Developer Certificate of Origin 1.1 present")
    else:
        failures.append("DCO: DCO.md must contain the complete verbatim Developer Certificate of Origin 1.1 text")

    notice_path = root / "THIRD-PARTY-NOTICES.md"
    notice_text = notice_path.read_text(encoding="utf-8", errors="replace") if notice_path.is_file() else ""
    missing_links = [item for item in NOTICE_LINKS if item not in notice_text]
    if not missing_links and "modified_from_upstream" in notice_text:
        successes.append("third-party notices: top-level index and modification explanation present")
    else:
        detail = ", ".join(missing_links) if missing_links else "modified_from_upstream explanation"
        failures.append(f"third-party notices: missing {detail}")

    sources = authored_sources(root, files)
    missing_headers = [relative(path, root) for path in sources if not has_header(path)]
    if missing_headers:
        failures.extend(f"source header: missing or misplaced Apache-2.0 header: {path}" for path in missing_headers)
    else:
        successes.append(f"source headers: {len(sources)} authored Python/JavaScript file(s) covered")

    manifest_path = root / "web/nemoclaw/vendor/browser-dependencies.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        failures.append(f"browser vendor: unreadable browser-dependencies.json: {error}")
        manifest = {}
    assets = manifest.get("assets") or []
    valid_forms = {"transformed-bundle", "upstream-file-copy"}
    unclassified = []
    for asset in assets:
        distribution_form = asset.get("distribution_form")
        modified = asset.get("modified_from_upstream")
        modification_matches_form = (
            distribution_form == "transformed-bundle" and modified is True
        ) or (
            distribution_form == "upstream-file-copy" and modified is False
        )
        if (
            distribution_form not in valid_forms
            or not isinstance(modified, bool)
            or not modification_matches_form
            or not asset.get("transformation")
            or not asset.get("source_files")
        ):
            unclassified.append(asset.get("file") or "<unnamed>")
    if not assets:
        failures.append("browser vendor: manifest must list delivered assets")
    elif unclassified:
        failures.extend(f"browser vendor: missing modification classification: {item}" for item in unclassified)
    else:
        successes.append(f"browser vendor: {len(assets)} delivered asset(s) classify upstream modification status")

    return failures, successes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix", action="store_true", help="insert missing headers in authored source files")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    files = repository_files(root)
    changed = apply_headers(root, files) if args.fix else []
    failures, successes = audit(root, repository_files(root))
    if args.json:
        print(json.dumps({"changed": changed, "ok": successes, "fail": failures}, indent=2))
    else:
        for item in changed:
            print(f"  fixed {item}")
        for item in successes:
            print(f"  ok    {item}")
        for item in failures:
            print(f"  FAIL  {item}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
