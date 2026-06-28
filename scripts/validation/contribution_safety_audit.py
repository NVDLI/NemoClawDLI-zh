#!/usr/bin/env python3
"""Enforce low-friction idea intake and high-friction code/release boundaries."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

for _p in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
    if (_p / "scripts" / "_bootstrap.py").exists():
        sys.path.insert(0, str(_p / "scripts"))
        break
from _bootstrap import find_repo_root

ROOT = find_repo_root(Path(__file__).resolve())

CONTRACT_FILES = (
    "RELEASE_STATUS.json",
    "RELEASE_STATUS.md",
    "README.md",
    "CONTRIBUTING.md",
    "PHILOSOPHY.md",
    "AGENTS.md",
    "AGENT_QUICKSTART.md",
    "SECURITY.md",
    "docs/release_playbook.md",
    "docs/release_artifacts.md",
    "scripts/compliance/docs/open_source_readiness.md",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".gitlab/merge_request_templates/Default.md",
    ".github/workflows/pages.yml",
    ".github/workflows/release.yml",
    ".gitlab-ci.yml",
    "scripts/build/install-hooks.sh",
    "scripts/build/build_branch_manifest.py",
    "scripts/build/package_release.py",
    "scripts/git-hooks/pre-commit",
    "scripts/git-hooks/pre-push",
    "scripts/skills/gen_skill_hierarchy.py",
    "scripts/validation/SKILL.html",
    "scripts/validation/validate_bundle.py",
    "scripts/validation/gitlab_governance_audit.py",
)


def finding(code: str, path: str, message: str, fix: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message, "fix": fix}


def read(root: Path, rel: str, out: list[dict[str, str]]) -> str:
    path = root / rel
    if not path.is_file():
        out.append(finding("missing-file", rel, "required contribution boundary file is missing", f"restore {rel}"))
        return ""
    return path.read_text(encoding="utf-8")


def require(raw: str, token: str, rel: str, code: str, out: list[dict[str, str]], fix: str) -> None:
    if token not in raw:
        out.append(finding(code, rel, f"missing contract token: {token}", fix))


def top_permissions(workflow: str) -> str:
    match = re.search(r"(?ms)^permissions:\n((?:  [^\n]*\n)+)", workflow)
    return match.group(1) if match else ""


def audit_publication_approval(root: Path = ROOT) -> list[dict[str, str]]:
    try:
        status = json.loads((root / "RELEASE_STATUS.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [finding("publication-approval", "RELEASE_STATUS.json",
                        "publication state cannot be read",
                        "restore the release status before any external write")]
    if status.get("publication_state") not in {"approved-for-publication", "published"}:
        return [finding("publication-approval", "RELEASE_STATUS.json",
                        "external publication is not approved",
                        "complete OSRB approval, then update release status in a reviewed change")]
    return []


def audit_repo(root: Path = ROOT) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    docs = {rel: read(root, rel, out) for rel in CONTRACT_FILES}

    try:
        status = json.loads(docs["RELEASE_STATUS.json"])
    except (TypeError, json.JSONDecodeError):
        status = {}
        out.append(finding("release-status-json", "RELEASE_STATUS.json",
                           "release status is not valid JSON",
                           "restore the machine-readable release status contract"))
    expected_status = {
        "schema": "nemoclaw-release-status/1",
        "publication_state": "pending-osrb-approval",
        "canonical_repository": "internal-gitlab",
        "external_mirror": "not-published",
        "target_license": "Apache-2.0",
    }
    for key, expected in expected_status.items():
        if status.get(key) != expected:
            out.append(finding("release-status", "RELEASE_STATUS.json",
                               f"{key} must be {expected!r} before external approval",
                               "update publication state only in an OSRB-approved release change"))
    notice_required = status.get("notice_required")
    if not isinstance(notice_required, bool):
        out.append(finding("notice-state", "RELEASE_STATUS.json",
                           "notice_required must be a boolean",
                           "record whether required downstream attributions exist"))
    elif notice_required != (root / "NOTICE.md").is_file():
        out.append(finding("notice-state", "NOTICE.md",
                           "NOTICE presence disagrees with RELEASE_STATUS.json",
                           "add NOTICE only for required attributions and update notice_required together"))

    for rel in ("RELEASE_STATUS.md", "README.md", "CONTRIBUTING.md", "AGENT_QUICKSTART.md",
                "docs/release_playbook.md", "scripts/compliance/docs/open_source_readiness.md"):
        require(re.sub(r"\s+", " ", docs[rel]), "pending OSRB approval", rel,
                "release-status-language", out,
                "state that external publication remains pending OSRB approval")
    require(docs["SECURITY.md"], "https://www.nvidia.com/en-us/security/report-vulnerability/",
            "SECURITY.md", "security-report-route", out,
            "make NVIDIA Product Security the stable private reporting route")
    if "github.com/NVIDIA/NemoClawDLIOS/security/advisories/new" in docs["SECURITY.md"]:
        out.append(finding("security-future-route", "SECURITY.md",
                           "policy assumes a repository-specific advisory endpoint exists",
                           "mention private vulnerability reporting only as conditional on enablement"))

    require(docs["README.md"], "Ideas are easy; code is gated", "README.md", "readme-boundary", out,
            "state the intake/code asymmetry in the README")
    require(docs["README.md"], "Discussions", "README.md", "readme-intake", out,
            "link question and broad-idea intake from the README")
    require(docs["CONTRIBUTING.md"], "A local hook is feedback, not authority", "CONTRIBUTING.md",
            "hook-authority", out, "explain that required CI and protected refs remain authoritative")
    require(docs["PHILOSOPHY.md"], "barrier to proposing an idea low", "PHILOSOPHY.md",
            "philosophy-boundary", out, "distinguish idea intake from merging code")
    require(docs["AGENTS.md"], "Treat code contribution as an untrusted proposal", "AGENTS.md",
            "agent-boundary", out, "put the trust boundary in the first agent beacon")
    require(docs["AGENT_QUICKSTART.md"], "Contribution safety first-touch", "AGENT_QUICKSTART.md",
            "quickstart-boundary", out, "add the contribution boundary to session orientation")

    issue_cfg = docs[".github/ISSUE_TEMPLATE/config.yml"]
    require(issue_cfg, "blank_issues_enabled: false", ".github/ISSUE_TEMPLATE/config.yml",
            "issue-structured", out, "keep structured issue intake enabled")
    require(issue_cfg, "/discussions", ".github/ISSUE_TEMPLATE/config.yml", "discussion-route", out,
            "route broad ideas and questions to Discussions")

    required_sections = (
        "## Issue link", "## Surfaces touched", "## Blast radius checked",
        "## Validation evidence", "## Human ownership", "## Risk and rollback", "## Out of scope",
    )
    for rel in (".github/PULL_REQUEST_TEMPLATE.md", ".gitlab/merge_request_templates/Default.md"):
        for section in required_sections:
            require(docs[rel], section, rel, "submission-template", out,
                    f"add the required {section} section")
    gitlab_template = docs[".gitlab/merge_request_templates/Default.md"]
    missing_in_window = [section for section in ("## Summary", *required_sections)
                         if section not in gitlab_template[:2700]]
    if missing_in_window:
        out.append(finding("gitlab-description-window", ".gitlab/merge_request_templates/Default.md",
                           "required headings fall outside GitLab's CI description window: "
                           + ", ".join(missing_in_window),
                           "keep the complete submission gate block within the first 2700 characters"))

    pages = docs[".github/workflows/pages.yml"]
    require(pages, "  pull_request:\n", ".github/workflows/pages.yml", "github-pr-trigger", out,
            "run the required static gate on pull_request")
    if "pull_request_target:" in pages:
        out.append(finding("unsafe-pr-trigger", ".github/workflows/pages.yml",
                           "pull_request_target may execute untrusted fork code with base-repo authority",
                           "use pull_request with a read-only token"))
    perms = top_permissions(pages)
    if "contents: read" not in perms or "pages: write" in perms or "id-token: write" in perms:
        out.append(finding("github-global-permissions", ".github/workflows/pages.yml",
                           "workflow-level permissions are not read-only",
                           "keep contents: read globally and grant Pages writes only to the deploy job"))
    require(pages, "if: github.event_name != 'pull_request'", ".github/workflows/pages.yml",
            "pr-deploy-boundary", out, "prevent pull-request runs from reaching deployment")
    require(pages, "contribution_safety_audit.py --self-test", ".github/workflows/pages.yml",
            "github-safety-selftest", out, "run detector mutations in GitHub CI")
    require(pages, "contribution_safety_audit.py --require-publication-approved",
            ".github/workflows/pages.yml", "publication-deploy-guard", out,
            "refuse external Pages deployment until publication is approved")
    require(pages, "package_release.py --self-test", ".github/workflows/pages.yml",
            "github-package-selftest", out, "test deterministic release packaging in public CI")
    require(pages, "--submission-env CONTRIBUTION_BODY", ".github/workflows/pages.yml",
            "github-submission-contract", out, "validate the live pull-request body")

    release = docs[".github/workflows/release.yml"]
    require(release, "  workflow_dispatch:", ".github/workflows/release.yml", "release-manual", out,
            "make release preparation an explicit operator action")
    require(release, "name: github-release", ".github/workflows/release.yml", "release-environment", out,
            "gate release writes behind the github-release environment")
    require(release, "contents: write", ".github/workflows/release.yml", "release-write", out,
            "grant release write authority only to the draft-release job")
    require(release, "--draft --verify-tag", ".github/workflows/release.yml", "release-draft", out,
            "create a draft from an existing verified tag")
    require(release, "group: github-release", ".github/workflows/release.yml", "release-serial", out,
            "serialize release writes")
    require(release, "GH_REPO: ${{ github.repository }}", ".github/workflows/release.yml", "release-target", out,
            "bind gh release commands to the workflow repository")
    release_perms = top_permissions(release)
    if "contents: read" not in release_perms or "contents: write" in release_perms:
        out.append(finding("release-global-permissions", ".github/workflows/release.yml",
                           "release workflow has write authority outside the approved job",
                           "keep contents: read globally and grant contents: write only to draft-release"))
    require(release, "existing release is already published", ".github/workflows/release.yml",
            "release-immutable", out, "refuse to update a published release")
    require(release, 'git cat-file -t "refs/tags/$RELEASE_TAG"', ".github/workflows/release.yml",
            "release-annotated-tag", out, "refuse lightweight release tags")
    for token in ("package_release.py --self-test", "release-manifest.json", "SHA256SUMS",
                  "python-env.cdx.json", "release-assets/*"):
        require(release, token, ".github/workflows/release.yml", "release-artifact-set", out,
                f"retain required release artifact contract token: {token}")
    require(release, "contribution_safety_audit.py --require-publication-approved",
            ".github/workflows/release.yml", "publication-release-guard", out,
            "refuse external release preparation until publication is approved")
    if "pull_request:" in release or "pull_request_target:" in release:
        out.append(finding("release-pr-trigger", ".github/workflows/release.yml",
                           "release workflow can be started by an untrusted pull request",
                           "keep release workflow_dispatch-only"))

    gitlab = docs[".gitlab-ci.yml"]
    require(gitlab, "contribution_safety_audit.py --self-test", ".gitlab-ci.yml",
            "gitlab-safety-selftest", out, "run detector mutations in GitLab CI")
    require(gitlab, "package_release.py --self-test", ".gitlab-ci.yml",
            "gitlab-package-selftest", out, "test deterministic release packaging in canonical CI")
    require(gitlab, "--report docs/validation/contribution-safety.json", ".gitlab-ci.yml",
            "gitlab-safety-report", out, "retain a machine-readable contribution-boundary report")
    require(gitlab, "CI_MERGE_REQUEST_DESCRIPTION", ".gitlab-ci.yml", "gitlab-submission-contract", out,
            "validate merge-request descriptions when CI has MR context")
    require(gitlab, 'CI_PIPELINE_SOURCE == "merge_request_event"', ".gitlab-ci.yml",
            "gitlab-mr-pipeline", out, "run open merge requests in MR context")
    require(gitlab, "$CI_COMMIT_BRANCH && $CI_OPEN_MERGE_REQUESTS", ".gitlab-ci.yml",
            "gitlab-pipeline-dedup", out, "suppress duplicate branch pipelines after an MR opens")
    require(gitlab, "CI_MERGE_REQUEST_SOURCE_BRANCH_NAME:-$CI_COMMIT_REF_NAME", ".gitlab-ci.yml",
            "gitlab-preview-ref", out, "resolve branch-preview refs in branch and MR pipelines")
    require(gitlab, 'needs: ["test"]', ".gitlab-ci.yml", "gitlab-deploy-gate", out,
            "keep Pages blocked on the required test job")
    require(gitlab, "human_review:", ".gitlab-ci.yml", "gitlab-human-review", out,
            "keep an explicit human acceptance job after preview validation")
    require(gitlab, 'needs: ["test", "pages_smoke"]', ".gitlab-ci.yml", "gitlab-human-review-needs", out,
            "make human acceptance wait for static gates and live preview smoke")
    require(gitlab, "name: human-review", ".gitlab-ci.yml", "gitlab-human-review-environment", out,
            "bind human acceptance to the protected human-review environment")
    human_review = re.search(r"(?ms)^human_review:\n(.*?)(?=^[A-Za-z0-9_.-]+:\n|\Z)", gitlab)
    if not human_review or "when: manual" not in human_review.group(1) or "allow_failure: false" not in human_review.group(1):
        out.append(finding("gitlab-human-review-blocking", ".gitlab-ci.yml",
                           "human_review is not a required manual MR action",
                           "keep human_review manual and blocking for merge-request pipelines"))

    install = docs["scripts/build/install-hooks.sh"]
    require(install, "git rev-parse --git-path hooks", "scripts/build/install-hooks.sh", "worktree-hooks", out,
            "resolve the real hooks directory for normal and linked worktrees")
    precommit = docs["scripts/git-hooks/pre-commit"]
    require(precommit, "REFUSING COMMIT on protected branch", "scripts/git-hooks/pre-commit",
            "protected-local-commit", out, "refuse local commits on main, nemoclaw-only, and release/*")
    require(precommit, "contribution_safety_audit.py", "scripts/git-hooks/pre-commit", "precommit-safety", out,
            "run the fast contribution-boundary audit before staged-file checks")
    prep = docs["scripts/git-hooks/pre-push"]
    if "git pull --rebase" in prep:
        out.append(finding("mutating-prepush", "scripts/git-hooks/pre-push",
                           "pre-push mutates history by rebasing during push",
                           "fail with exact recovery commands and let the operator rebase explicitly"))
    if re.search(r"git fetch[^\n]*(?:\|\||\bor\b)[^\n]*exit 0", prep):
        out.append(finding("fetch-fail-open", "scripts/git-hooks/pre-push",
                           "failed base fetch exits success and skips required gates",
                           "refuse the push when origin/main cannot be verified"))
    if re.search(r'\[ "\$REMOTE" = "origin" \][^\n]*exit 0', prep):
        out.append(finding("remote-fail-open", "scripts/git-hooks/pre-push",
                           "non-origin pushes bypass every repository gate",
                           "skip only base comparison; run deterministic gates for every remote"))
    require(prep, "cannot verify origin/main", "scripts/git-hooks/pre-push", "fetch-refusal", out,
            "fail closed when origin/main cannot be fetched")
    require(prep, "REFUSING PUSH - origin/main is", "scripts/git-hooks/pre-push", "behind-refusal", out,
            "refuse a behind branch instead of silently rewriting it")
    require(prep, "contribution_safety_audit.py", "scripts/git-hooks/pre-push", "prepush-safety", out,
            "run the contribution-boundary audit and its mutations before push")
    require(prep, 'PACKAGE_RELEASE="$T1/scripts/build/package_release.py"',
            "scripts/git-hooks/pre-push", "prepush-package-selftest", out,
            "run the deterministic release-packaging self-test before push")

    playbook = docs["docs/release_playbook.md"]
    for token in ("GitHub release runbook", "github-release", "Rule Insights", "Draft release",
                  "Host settings are not versioned by this repository", "gitlab_governance_audit.py"):
        require(playbook, token, "docs/release_playbook.md", "release-playbook", out,
                f"document {token} in the GitHub release/operator runbook")
    require(playbook, "docs/release_artifacts.md", "docs/release_playbook.md",
            "release-artifact-doc", out, "link the artifact and tag contract from the release runbook")
    package_source = docs["scripts/build/package_release.py"]
    for token in ('mtime=0', 'format=tarfile.PAX_FORMAT', '"release-manifest.json"', '"SHA256SUMS"'):
        require(package_source, token, "scripts/build/package_release.py", "release-package-contract", out,
                f"keep deterministic release-packaging primitive: {token}")
    require(docs["scripts/build/build_branch_manifest.py"], 'os.environ.get("SOURCE_DATE_EPOCH")',
            "scripts/build/build_branch_manifest.py", "release-build-epoch", out,
            "make generated branch metadata reproducible for tagged builds")
    require(release, 'echo "SOURCE_DATE_EPOCH=', ".github/workflows/release.yml",
            "release-build-epoch", out, "bind generated build metadata to the release commit time")
    require(release, '>> "$GITHUB_ENV"', ".github/workflows/release.yml",
            "release-build-epoch", out, "carry the release commit epoch through every build step")
    require(docs["scripts/validation/validate_bundle.py"], 'os.environ.get("SOURCE_DATE_EPOCH")',
            "scripts/validation/validate_bundle.py", "release-build-epoch", out,
            "make generated validation reports reproducible for tagged builds")
    for token in ("annotated", "immutable", "CycloneDX", "SHA256SUMS", "3 days"):
        require(docs["docs/release_artifacts.md"], token, "docs/release_artifacts.md",
                "release-artifact-doc", out, f"document release strategy token: {token}")
    require(docs["scripts/skills/gen_skill_hierarchy.py"], "Ideas stay easy to contribute",
            "scripts/skills/gen_skill_hierarchy.py", "tenet-source", out,
            "project the contribution trust boundary into the root SKILL tenets")
    require(docs["scripts/validation/SKILL.html"], "contribution_safety_audit.py",
            "scripts/validation/SKILL.html", "validation-beacon", out,
            "advertise the contribution boundary from the validation beacon")
    return out


SUBMISSION_SECTIONS = (
    "Summary", "Issue link", "Surfaces touched", "Blast radius checked",
    "Validation evidence", "Human ownership", "Risk and rollback", "Out of scope",
)


def audit_submission(body: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    required_headings = [f"## {section}" for section in SUBMISSION_SECTIONS]
    missing_in_window = [heading for heading in required_headings if heading not in (body or "")[:2700]]
    if missing_in_window:
        out.append(finding("submission-description-window", "submission",
                           "required headings fall outside GitLab's CI description window: "
                           + ", ".join(missing_in_window),
                           "put the compact submission contract before rationale, screenshots, or logs"))
    for section in SUBMISSION_SECTIONS:
        match = re.search(rf"(?ms)^## {re.escape(section)}\s*\n(.*?)(?=^## |\Z)", body or "")
        if not match or not match.group(1).strip():
            out.append(finding("submission-section", "submission", f"missing or empty section: {section}",
                               f"fill ## {section} with concrete evidence"))
    if not re.search(r"(?im)\b(?:Addresses|Closes|Fixes)\s+#[0-9]+\b", body or ""):
        out.append(finding("submission-issue", "submission", "no explicit issue relationship",
                           "add Addresses #N, or Closes #N only when acceptance is fully met"))
    if not re.search(r"(?im)^- \[[xX]\] `?(?:web/|cpu/|deploy/|scripts/|docs/|materials)", body or ""):
        out.append(finding("submission-surface", "submission", "no changed surface is checked",
                           "check every touched surface in ## Surfaces touched"))
    if not re.search(r"(?im)\b(?:PASS|FAIL|BLOCKED)\b", body or ""):
        out.append(finding("submission-evidence", "submission", "validation has no PASS, FAIL, or BLOCKED result",
                           "record command outcomes; do not submit an unqualified checklist"))
    return out


def self_test() -> list[str]:
    failures: list[str] = []
    if audit_repo(ROOT):
        return ["baseline repository contract is not clean"]
    with tempfile.TemporaryDirectory(prefix="contribution-safety-") as td:
        fixture = Path(td)
        for rel in CONTRACT_FILES:
            src, dst = ROOT / rel, fixture / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        cases = (
            ("github-pr-trigger", ".github/workflows/pages.yml", "  pull_request:\n", "  # pull_request removed\n"),
            ("pr-deploy-boundary", ".github/workflows/pages.yml", "if: github.event_name != 'pull_request'", "if: always()"),
            ("release-draft", ".github/workflows/release.yml", "--draft --verify-tag", "--verify-tag"),
            ("release-annotated-tag", ".github/workflows/release.yml", 'git cat-file -t "refs/tags/$RELEASE_TAG"', 'git cat-file -t "$RELEASE_TAG^{commit}"'),
            ("release-artifact-set", ".github/workflows/release.yml", "release-assets/release-manifest.json", "release-assets/manifest.json"),
            ("release-package-contract", "scripts/build/package_release.py", "mtime=0", "mtime=None"),
            ("release-build-epoch", "scripts/build/build_branch_manifest.py", 'os.environ.get("SOURCE_DATE_EPOCH")', 'os.environ.get("BUILD_TIME")'),
            ("publication-release-guard", ".github/workflows/release.yml", "contribution_safety_audit.py --require-publication-approved", "contribution_safety_audit.py"),
            ("publication-deploy-guard", ".github/workflows/pages.yml", "contribution_safety_audit.py --require-publication-approved", "contribution_safety_audit.py"),
            ("discussion-route", ".github/ISSUE_TEMPLATE/config.yml", "/discussions", "/issues"),
            ("submission-template", ".github/PULL_REQUEST_TEMPLATE.md", "## Blast radius checked", "## Scope notes"),
            ("gitlab-description-window", ".gitlab/merge_request_templates/Default.md", "## Validation evidence", "x" * 2700 + "\n## Validation evidence"),
            ("mutating-prepush", "scripts/git-hooks/pre-push", "REFUSING PUSH - origin/main is", "git pull --rebase origin main # REFUSING PUSH - origin/main is"),
            ("fetch-fail-open", "scripts/git-hooks/pre-push", "if ! git fetch origin main --quiet; then", "git fetch origin main --quiet || exit 0\n    if false; then"),
            ("remote-fail-open", "scripts/git-hooks/pre-push", "if [ \"$REMOTE\" = \"origin\" ]; then", "[ \"$REMOTE\" = \"origin\" ] || exit 0\nif false; then"),
            ("prepush-package-selftest", "scripts/git-hooks/pre-push", "PACKAGE_RELEASE=", "PACKAGE_TEST="),
            ("gitlab-safety-selftest", ".gitlab-ci.yml", "contribution_safety_audit.py --self-test", "contribution_safety_audit.py --version"),
            ("gitlab-human-review", ".gitlab-ci.yml", "human_review:", "operator_review:"),
            ("gitlab-human-review-needs", ".gitlab-ci.yml", 'needs: ["test", "pages_smoke"]', 'needs: ["test"]'),
            ("gitlab-human-review-blocking", ".gitlab-ci.yml", '    - if: \'$CI_PIPELINE_SOURCE == "merge_request_event"\'\n      when: manual\n      allow_failure: false\n', '    - if: \'$CI_PIPELINE_SOURCE == "merge_request_event"\'\n      when: on_success\n      allow_failure: true\n'),
            ("readme-boundary", "README.md", "Ideas are easy; code is gated", "Contribution overview"),
            ("release-status", "RELEASE_STATUS.json", '"pending-osrb-approval"', '"published"'),
            ("notice-state", "RELEASE_STATUS.json", '"notice_required": false', '"notice_required": true'),
            ("security-report-route", "SECURITY.md", "https://www.nvidia.com/en-us/security/report-vulnerability/", "https://example.invalid/report"),
            ("release-playbook", "docs/release_playbook.md", "Host settings are not versioned by this repository", "Host settings checklist"),
        )
        originals: dict[str, str] = {}
        for expected, rel, old, new in cases:
            path = fixture / rel
            originals.setdefault(rel, path.read_text(encoding="utf-8"))
            raw = originals[rel]
            if old not in raw:
                failures.append(f"fixture token missing for {expected}: {rel}: {old}")
                continue
            path.write_text(raw.replace(old, new, 1), encoding="utf-8")
            codes = {item["code"] for item in audit_repo(fixture)}
            if expected not in codes:
                failures.append(f"mutation escaped detector: {expected}")
            path.write_text(raw, encoding="utf-8")

        status_path = fixture / "RELEASE_STATUS.json"
        approved = json.loads(status_path.read_text(encoding="utf-8"))
        approved["publication_state"] = "approved-for-publication"
        status_path.write_text(json.dumps(approved, indent=2) + "\n", encoding="utf-8")
        if audit_publication_approval(fixture):
            failures.append("approved release rejected by the external publication guard")

    good = """## Summary\nBound the release path.\n## Issue link\nAddresses #12\n## Surfaces touched\n- [x] `scripts/`\n## Blast radius checked\nHooks and CI.\n## Validation evidence\nPASS: audit.\n## Human ownership\nRelease manager reviews.\n## Risk and rollback\nRevert commit.\n## Out of scope\nHost settings.\n"""
    if audit_submission(good):
        failures.append("valid submission fixture rejected")
    if not audit_publication_approval(ROOT):
        failures.append("pending release unexpectedly passed the external publication guard")
    for needle, expected in (("## Human ownership\nRelease manager reviews.\n", "submission-section"),
                             ("Addresses #12", "submission-issue"), ("PASS: audit.", "submission-evidence")):
        codes = {item["code"] for item in audit_submission(good.replace(needle, "", 1))}
        if expected not in codes:
            failures.append(f"submission mutation escaped detector: {expected}")
    long_body = good.replace("## Out of scope", "x" * 2700 + "\n## Out of scope", 1)
    if "submission-description-window" not in {item["code"] for item in audit_submission(long_body)}:
        failures.append("submission description-window mutation escaped detector")
    return failures


def emit(findings: list[dict[str, str]], label: str, report: str | None = None) -> int:
    result = {"schema": "nemoclaw-contribution-safety/1", "ok": not findings,
              "label": label, "findings": findings}
    if report:
        path = Path(report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if findings:
        print(f"contribution safety: FAIL ({len(findings)})")
        for item in findings:
            print(f"  [{item['code']}] {item['path']}: {item['message']}")
            print(f"    fix: {item['fix']}")
        return 1
    print(f"contribution safety: OK ({label})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--require-publication-approved", action="store_true")
    parser.add_argument("--submission-env", metavar="NAME")
    parser.add_argument("--report")
    args = parser.parse_args()
    if args.require_publication_approved:
        return emit(audit_publication_approval(), "external publication approval", args.report)
    if args.self_test:
        failures = self_test()
        findings = [finding("self-test", "mutation", item, "repair the escaped detector") for item in failures]
        return emit(findings, "mutation self-test", args.report)
    if args.submission_env:
        return emit(audit_submission(os.environ.get(args.submission_env, "")), "submission", args.report)
    return emit(audit_repo(), "repository", args.report)


if __name__ == "__main__":
    raise SystemExit(main())
