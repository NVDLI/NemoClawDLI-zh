#!/usr/bin/env python3
# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Reject GitLab CI trust-boundary drift before pipeline execution or merge."""
from __future__ import annotations

import argparse
import json
import re
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROOT_CI = """# This root is intentionally inert and exact. Add repository tests under tests/ and
# register them in the release gate. Core delivery and SCA policy live in owner-gated modules.
include:
  - local: "/.gitlab/ci/core.yml"
  - local: "/.gitlab/ci/sca.yml"
"""
SCA_JOBS = ("security_browser_sca", "security_sca", "security_python_sca")
OWNER_PATHS = (
    "/.gitlab-ci.yml",
    "/.gitlab/ci/",
    "/.gitlab/CODEOWNERS",
    "/scripts/validation/gitlab_ci_policy.py",
    "/scripts/validation/contribution_safety_audit.py",
    "/scripts/validation/gitlab_governance_audit.py",
    "/scripts/validation/release_gate.py",
    "/scripts/git-hooks/",
    "/.github/workflows/",
)


def finding(code: str, path: str, message: str, fix: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message, "fix": fix}


def read(root: Path, rel: str, out: list[dict[str, str]]) -> str:
    path = root / rel
    if not path.is_file():
        out.append(finding("missing-file", rel, "required CI policy file is missing", "restore the reviewed file"))
        return ""
    return path.read_text(encoding="utf-8")


def job_block(source: str, name: str) -> str:
    match = re.search(rf"(?ms)^{re.escape(name)}:\n(.*?)(?=^[A-Za-z0-9_.-]+:\n|\Z)", source)
    return match.group(1) if match else ""


def composed_ci(root: Path = ROOT) -> str:
    """Return the reviewed local modules as the effective repository CI contract."""
    return "\n".join(
        (root / rel).read_text(encoding="utf-8")
        for rel in (".gitlab/ci/core.yml", ".gitlab/ci/sca.yml")
    )


def require(source: str, token: str, code: str, path: str, out: list[dict[str, str]], fix: str) -> None:
    if token not in source:
        out.append(finding(code, path, f"required token is absent: {token}", fix))


def audit(root: Path = ROOT) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    root_ci = read(root, ".gitlab-ci.yml", out)
    core = read(root, ".gitlab/ci/core.yml", out)
    sca = read(root, ".gitlab/ci/sca.yml", out)
    owners = read(root, ".gitlab/CODEOWNERS", out)
    release_gate = read(root, "scripts/validation/release_gate.py", out)
    pages_builder = read(root, "scripts/build/build_pages.sh", out)

    if root_ci != ROOT_CI:
        out.append(finding(
            "root-ci-not-inert", ".gitlab-ci.yml",
            "root CI differs from the exact two-module manifest",
            "put jobs and policy in the owner-gated modules; register repository tests in the release gate",
        ))

    if re.search(r"(?m)^include:\s*$", core) or re.search(r"(?m)^include:\s*$", sca):
        out.append(finding("nested-ci-include", ".gitlab/ci/", "a CI module adds another include boundary",
                           "keep the complete include set visible in the inert root manifest"))
    for name in SCA_JOBS:
        if re.search(rf"(?m)^{re.escape(name)}:\s*$", core):
            out.append(finding("sca-job-in-core", ".gitlab/ci/core.yml", f"{name} is defined outside the SCA module",
                               "keep scanner jobs self-contained in .gitlab/ci/sca.yml"))

    for token in ("extends:", "!reference", "trigger:", "needs:\n    - project:"):
        if token in sca:
            out.append(finding("sca-cross-config-reference", ".gitlab/ci/sca.yml",
                               f"SCA module uses cross-configuration behavior: {token}",
                               "keep scanner setup and execution self-contained"))
    for token in (
        "inherit:\n    default: false\n    variables: false",
        "node:20-bookworm-slim@sha256:25070a03f077f5860e4f2db8d147380678ed40ead415a21eaffd5a6208f61948",
        "retry_cmd apt-get install -y -qq --no-install-recommends python3 python3-pip python3-venv ca-certificates curl git",
    ):
        require(sca, token, "sca-self-contained", ".gitlab/ci/sca.yml", out,
                "restore the isolated image, inheritance boundary, and explicit scanner prerequisites")

    optional_mr = """- if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
      when: manual
      allow_failure: true"""
    schedule = """- if: '$CI_PIPELINE_SOURCE == "schedule"'
      when: on_success
      allow_failure: false"""
    for name in SCA_JOBS:
        body = job_block(sca, name)
        if not body:
            out.append(finding("missing-sca-job", ".gitlab/ci/sca.yml", f"{name} is missing",
                               "restore the reviewed scanner job"))
            continue
        require(body, "<<: *sca_base", "sca-base-bypass", ".gitlab/ci/sca.yml", out,
                f"make {name} inherit the isolated SCA base")
        require(body, schedule, "sca-schedule", ".gitlab/ci/sca.yml", out,
                f"keep {name} automatic and blocking on scheduled advisory refreshes")
        require(body, optional_mr, "sca-manual-opt-in", ".gitlab/ci/sca.yml", out,
                f"keep {name} available but non-blocking on unrelated merge requests")

    for name, changed_input in (
        ("security_browser_sca", "scripts/browser-vendor/package-lock.json"),
        ("security_python_sca", "scripts/materials/requirements.lock"),
    ):
        body = job_block(sca, name)
        require(body, changed_input, "sca-change-trigger", ".gitlab/ci/sca.yml", out,
                f"run {name} automatically when its dependency graph changes")
        require(body, ".gitlab/ci/sca.yml", "sca-policy-trigger", ".gitlab/ci/sca.yml", out,
                f"run {name} automatically when scanner policy changes")
        for broad_path in ("- .gitlab-ci.yml", "- .gitlab/ci/core.yml"):
            if broad_path in body:
                out.append(finding("sca-broad-trigger", ".gitlab/ci/sca.yml",
                                   f"{name} is coupled to unrelated CI changes through {broad_path[2:]}",
                                   "trigger from the self-contained SCA module and dependency inputs"))

    for token in (
        "npm audit --prefix scripts/browser-vendor --package-lock-only",
        "pnpm audit --audit-level=moderate",
        "scripts/runtime/pnpm-lock.yaml",
        ".sca-tools-venv/bin/python -m pip install --require-hashes --no-deps --only-binary=:all: -q -r scripts/security/requirements-sca.lock",
        ".sca-tools-venv/bin/pip-audit -r scripts/materials/requirements.lock",
        "audit_sbom_policy.py --sbom",
        "scripts/compliance/resolve_sbom_licenses.py --input scripts/security/reports/python-materials/python-env.raw.cdx.json",
        "--sbom scripts/security/reports/python-materials/python-env.cdx.json",
    ):
        require(sca, token, "sca-required-command", ".gitlab/ci/sca.yml", out,
                "restore the locked dependency scan and SBOM policy command")

    if "security_image_sca:" in sca or "security_deep_sca:" in sca:
        out.append(finding("retired-sca-job", ".gitlab/ci/sca.yml", "obsolete image or workspace scan returned",
                           "scan only the distributed browser graph and pinned material tools"))

    for path in OWNER_PATHS:
        if not re.search(rf"(?m)^{re.escape(path)}\s+@\S+", owners):
            out.append(finding("missing-code-owner", ".gitlab/CODEOWNERS",
                               f"security-sensitive path lacks a named owner: {path}",
                               "assign a real GitLab user or group and require Code Owner approval on main"))
    require(release_gate, 'unit_test("gitlab_ci_policy")', "ci-policy-not-gated",
            "scripts/validation/release_gate.py", out,
            "run the mutation-tested CI policy in both fast and ship gates")
    require(release_gate, 'unit_test("artifact_link_audit")', "artifact-policy-not-gated",
            "scripts/validation/release_gate.py", out,
            "run the exhaustive artifact-link mutation suite in both fast and ship gates")
    require(pages_builder, 'artifact_link_audit.py" "$OUT"', "artifact-boundary-not-gated",
            "scripts/build/build_pages.sh", out,
            "reject every broken, missing, absolute, or deployment-root-escaping local URL before Pages upload")
    return out


def self_test() -> list[str]:
    files = {
        rel: (ROOT / rel).read_text(encoding="utf-8")
        for rel in (
            ".gitlab-ci.yml", ".gitlab/ci/core.yml", ".gitlab/ci/sca.yml",
            ".gitlab/CODEOWNERS", "scripts/validation/release_gate.py", "scripts/build/build_pages.sh",
        )
    }
    root_owner_line = next(line for line in files[".gitlab/CODEOWNERS"].splitlines()
                           if line.startswith("/.gitlab-ci.yml "))
    cases = (
        ("root-ci-not-inert", ".gitlab-ci.yml", ROOT_CI, ROOT_CI + "variables: {EVIL: 1}\n"),
        ("nested-ci-include", ".gitlab/ci/core.yml", "stages: [test, deploy, verify, review]",
         "include:\n  - remote: https://example.invalid/ci.yml\nstages: [test, deploy, verify, review]"),
        ("sca-self-contained", ".gitlab/ci/sca.yml", "variables: false", "variables: true"),
        ("sca-base-bypass", ".gitlab/ci/sca.yml", "security_browser_sca:\n  <<: *sca_base",
         "security_browser_sca:\n  # isolated base removed"),
        ("sca-broad-trigger", ".gitlab/ci/sca.yml", "        - .gitlab/ci/sca.yml",
         "        - .gitlab-ci.yml"),
        ("sca-required-command", ".gitlab/ci/sca.yml", "audit_sbom_policy.py --sbom",
         "audit_sbom_policy.py --help"),
        ("retired-sca-job", ".gitlab/ci/sca.yml", "security_python_sca:",
         "security_deep_sca:"),
        ("missing-code-owner", ".gitlab/CODEOWNERS", root_owner_line,
         "/.gitlab-ci.yml"),
        ("ci-policy-not-gated", "scripts/validation/release_gate.py", 'unit_test("gitlab_ci_policy")',
         'unit_test("repository_sync_audit")'),
        ("artifact-policy-not-gated", "scripts/validation/release_gate.py", 'unit_test("artifact_link_audit")',
         'unit_test("repository_sync_audit")'),
        ("artifact-boundary-not-gated", "scripts/build/build_pages.sh", 'artifact_link_audit.py" "$OUT"',
         'artifact_link_audit.py" "$OPTIONAL_OUT"'),
    )
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as directory:
        fixture = Path(directory)
        for rel, content in files.items():
            path = fixture / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        if audit(fixture):
            failures.append("clean CI policy fixture rejected")
        for expected, rel, old, new in cases:
            path = fixture / rel
            original = files[rel]
            if old not in original:
                failures.append(f"fixture token missing for {expected}")
                continue
            path.write_text(original.replace(old, new), encoding="utf-8")
            codes = {item["code"] for item in audit(fixture)}
            if expected not in codes:
                failures.append(f"mutation escaped detector: {expected}")
            path.write_text(original, encoding="utf-8")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    findings = ([finding("self-test", "fixtures", failure, "repair the detector")
                 for failure in self_test()] if args.self_test else audit())
    if args.json:
        print(json.dumps({"ok": not findings, "findings": findings}, indent=2))
    elif findings:
        print(f"gitlab CI policy: FAIL ({len(findings)})")
        for item in findings:
            print(f"  [{item['code']}] {item['path']}: {item['message']}")
            print(f"    fix: {item['fix']}")
    else:
        print(f"gitlab CI policy: OK ({'mutation self-test' if args.self_test else 'repository'})")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
