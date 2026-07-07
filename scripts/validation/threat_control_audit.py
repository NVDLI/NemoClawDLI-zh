#!/usr/bin/env python3
"""Audit repository-owned threat controls and keep external limitations explicit."""
from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DISPOSITION = "docs/security-control-disposition.md"
WORKFLOWS = (".github/workflows/pages.yml", ".github/workflows/release.yml")

REQUIRED_TOKENS = {
    DISPOSITION: (
        "## Status vocabulary",
        "## Source and contribution controls",
        "## Build and artifact controls",
        "## Static hosting and browser controls",
        "## Relay, model, launchable, and runtime controls",
        "## Publication blockers and retained risks",
        "Cryptographic artifact signature and signed provenance | Not verified",
        "Browser certificate pinning | Not applicable",
        "Client-side prompt complexity detection | Not applicable",
        "Relay schema, route, frame-size, and rate enforcement | Unknown",
        "Repository evidence does not grant Legal, OSRB, Export, Privacy, Product Security, SCM, host, or",
    ),
    "scripts/validation/pages_artifact_integrity.py": (
        "MAX_FILE_COUNT",
        "MAX_FILE_BYTES",
        "MAX_TOTAL_BYTES",
        "MAX_DIRECTORY_DEPTH",
        "MAX_ARCHIVE_BYTES",
        "MAX_EXPANSION_RATIO",
        "safe_extract_archive",
        "verify_deployment",
        "deployed file digest differs from reviewed artifact",
    ),
    "scripts/validation/repository_sync_audit.py": (
        '"external-ahead"',
        '"internal-ahead"',
        '"diverged"',
        'state != "equivalent-tree"',
        "canonical public GitHub",
    ),
    "scripts/validation/release_gate.py": (
        'py("scripts/validation/threat_control_audit.py", "--self-test")',
        'py("scripts/validation/repository_sync_audit.py", "--self-test")',
    ),
    "scripts/validation/validate_bundle.py": (
        "import threat_control_audit as tca",
        '"threat_controls"',
    ),
    "scripts/git-hooks/pre-commit": (
        "scripts/validation/threat_control_audit.py",
    ),
    ".github/workflows/pages.yml": (
        "outputs:",
        "page_url: ${{ steps.deploy.outputs.page_url }}",
        "--archive reviewed-pages-artifact/artifact.tar --extract-to reviewed-public",
        "verify-deployment:",
        "--base-url \"${{ needs.deploy.outputs.page_url }}\"",
        "--check-manifest reviewed-public/pages-sha256.txt",
    ),
    ".github/workflows/release.yml": (
        "cd release-assets && sha256sum --check SHA256SUMS",
        "timeout-minutes:",
    ),
    ".gitlab-ci.yml": (
        "external_integration_audit:",
        'EXTERNAL_INTEGRATION_AUDIT == "1"',
        "https://github.com/NVDLI/NemoClawDLI.git",
        "repository_sync_audit.py",
        "refs/remotes/external/main",
    ),
    "docs/release_playbook.md": (
        "## Public GitHub write hold",
        "publication_state` as `pending-osrb-approval`",
        "external_mirror` as",
        "must not push branches or",
        "Internal GitLab issues, merge requests, CI, and branch previews may continue",
        "--require-publication-approved",
        "weekly external integration audit",
        "Monday at 09:00 UTC",
        "integration/github-main",
        "never force-push",
        "intended as **OSS Type I**",
    ),
    "RELEASE_STATUS.json": (
        '"publication_state": "pending-osrb-approval"',
        '"external_mirror": "reserved-not-populated"',
        '"canonical_repository": "internal-gitlab"',
        '"intended_oss_type": "Type-I"',
    ),
}


def finding(code: str, path: str, detail: str) -> dict[str, str]:
    return {"code": code, "path": path, "detail": detail}


def read(path: str, overrides: dict[str, str]) -> str:
    return overrides.get(path, (ROOT / path).read_text(encoding="utf-8"))


def workflow_jobs(text: str) -> dict[str, str]:
    jobs_match = re.search(r"(?ms)^jobs:\s*\n(.*)\Z", text)
    if not jobs_match:
        return {}
    body = jobs_match.group(1)
    starts = list(re.finditer(r"(?m)^  ([A-Za-z0-9_-]+):\s*$", body))
    jobs: dict[str, str] = {}
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(body)
        jobs[match.group(1)] = body[match.start():end]
    return jobs


def audit(*, text_overrides: dict[str, str] | None = None) -> list[dict[str, str]]:
    overrides = text_overrides or {}
    findings: list[dict[str, str]] = []
    for path, tokens in REQUIRED_TOKENS.items():
        if not (ROOT / path).is_file() and path not in overrides:
            findings.append(finding("missing-control-file", path, "required control evidence file is absent"))
            continue
        text = read(path, overrides)
        for token in tokens:
            if token not in text:
                findings.append(finding("missing-control-token", path, f"missing control evidence: {token}"))

    for path in WORKFLOWS:
        if not (ROOT / path).is_file() and path not in overrides:
            continue
        text = read(path, overrides)
        for line_number, line in enumerate(text.splitlines(), 1):
            match = re.match(r"\s*-\s+uses:\s+([^\s#]+)", line)
            if match and not re.fullmatch(r"[^@]+@[0-9a-f]{40}", match.group(1)):
                findings.append(finding(
                    "mutable-action", path,
                    f"line {line_number} does not pin a GitHub Action to a full commit SHA",
                ))
        for job, block in workflow_jobs(text).items():
            if "timeout-minutes:" not in block:
                findings.append(finding("missing-job-timeout", path, f"job {job} has no timeout-minutes"))

    disposition = read(DISPOSITION, overrides) if (ROOT / DISPOSITION).is_file() or DISPOSITION in overrides else ""
    if "MITIGATED" in disposition or "Status: mitigated" in disposition:
        findings.append(finding(
            "false-mitigation", DISPOSITION,
            "the repository disposition must use evidence states, not a blanket mitigated claim",
        ))
    return findings


def self_test() -> list[str]:
    baseline = audit()
    if baseline:
        return [f"baseline is not clean: {item['code']} {item['path']} {item['detail']}" for item in baseline]
    tests: list[tuple[str, dict[str, str], str]] = []
    pages = read(".github/workflows/pages.yml", {})
    release = read(".github/workflows/release.yml", {})
    disposition = read(DISPOSITION, {})
    playbook = read("docs/release_playbook.md", {})
    tests.append((
        "post-deploy verification",
        {".github/workflows/pages.yml": pages.replace("verify-deployment:", "verification-removed:", 1)},
        "missing-control-token",
    ))
    tests.append((
        "mutable action",
        {".github/workflows/pages.yml": re.sub(r"@[0-9a-f]{40}", "@v4", pages, count=1)},
        "mutable-action",
    ))
    tests.append((
        "release timeout",
        {".github/workflows/release.yml": release.replace("    timeout-minutes:", "    timeout-removed:", 1)},
        "missing-job-timeout",
    ))
    tests.append((
        "false signing claim",
        {DISPOSITION: disposition.replace(
            "Cryptographic artifact signature and signed provenance | Not verified",
            "Cryptographic artifact signature and signed provenance | Verified",
            1,
        )},
        "missing-control-token",
    ))
    tests.append((
        "sync cadence",
        {"docs/release_playbook.md": playbook.replace("Monday at 09:00 UTC", "unscheduled", 1)},
        "missing-control-token",
    ))
    tests.append((
        "public GitHub hold",
        {"docs/release_playbook.md": playbook.replace("## Public GitHub write hold", "## External publishing", 1)},
        "missing-control-token",
    ))
    tests.append((
        "full OSS classification",
        {"docs/release_playbook.md": playbook.replace("OSS Type I", "OSS Type II", 1)},
        "missing-control-token",
    ))
    failures: list[str] = []
    for label, overrides, expected in tests:
        codes = {item["code"] for item in audit(text_overrides=overrides)}
        if expected not in codes:
            failures.append(f"mutation escaped: {label}; got {sorted(codes)}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        failures = self_test()
        total = 7
        print(f"threat control self-test: {total - len(failures)}/{total} passed")
        for failure in failures:
            print("  " + failure)
        return 1 if failures else 0
    findings = audit()
    if findings:
        print(f"threat control audit: FAIL ({len(findings)})")
        for item in findings:
            print(f"  [{item['code']}] {item['path']}: {item['detail']}")
        return 1
    print(f"threat control audit: PASS ({sum(len(value) for value in REQUIRED_TOKENS.values())} controls)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
