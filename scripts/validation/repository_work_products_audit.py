#!/usr/bin/env python3
"""Validate public repository work products, applicability, and discovery wiring."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

for _path in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
    if (_path / "scripts" / "_bootstrap.py").exists():
        sys.path.insert(0, str(_path / "scripts"))
        break
from _bootstrap import find_repo_root

ROOT = find_repo_root(Path(__file__).resolve())
CONTRACT = ROOT / "docs" / "release-evidence.json"
SECURITY_TEMPLATE_SHA256 = "9b4fc75ece26b86b2bbb93a9f2abce9a853a35f74392dd8207224b274904b7f6"

EXPECTED_LEVELS = {
    "maintainer-plan": "required",
    "readme": "show-stopper",
    "license": "show-stopper",
    "third-party-inventory": "required",
    "contributing": "required",
    "security-policy": "show-stopper",
    "coding-guideline": "contextual",
    "changelog": "required",
    "code-of-conduct": "required",
    "contributor-license-agreement": "contextual-show-stopper",
    "citation": "optional",
    "issue-templates": "required",
    "pull-request-template": "required",
    "release-roadmap": "optional",
    "developer-guide": "optional",
    "user-guide": "optional",
}

REQUIRED_REPOSITORY_FILES = {
    "README.md",
    "LICENSE",
    "THIRD_PARTY_LICENSES.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "DCO.md",
    "CODE_OF_CONDUCT.md",
    "SUPPORT.md",
    "CHANGELOG.md",
    "docs/release_playbook.md",
    ".github/ISSUE_TEMPLATE/bug.yml",
    ".github/ISSUE_TEMPLATE/feature.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
}

CONVENTIONAL_OPTIONAL_PATHS = {
    "contributor-license-agreement": ("CLA.md",),
    "citation": ("CITATION.cff", "CITATION.md"),
    "release-roadmap": ("ROADMAP.md",),
}

WIRING = {
    "scripts/validation/SKILL.html": (
        "repository_work_products_audit.py",
        "Repository work products + detector",
    ),
    "scripts/validation/release_gate.py": (
        'py("scripts/validation/repository_work_products_audit.py", "--self-test")',
    ),
    "scripts/validation/validate_bundle.py": (
        "import repository_work_products_audit as rwpa",
        '"repository_work_products"',
    ),
    "scripts/git-hooks/pre-commit": (
        "repository_work_products_audit.py",
    ),
    "docs/release-test-plan.md": (
        "repository_work_products_audit.py --self-test",
        "repository_work_products_audit.py",
    ),
    "docs/agent_process.md": (
        "repository_work_products_audit.py --self-test",
        "repository_work_products_audit.py",
    ),
}


def finding(code: str, path: str, detail: str, fix: str) -> dict[str, str]:
    return {"code": code, "path": path, "detail": detail, "fix": fix}


def load_contract(path: Path = CONTRACT) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def audit_contract(
    data: dict,
    *,
    root: Path = ROOT,
    text_overrides: dict[str, str] | None = None,
    missing_paths: set[str] | None = None,
    present_paths: set[str] | None = None,
) -> list[dict[str, str]]:
    overrides = text_overrides or {}
    missing = missing_paths or set()
    present = present_paths or set()
    out: list[dict[str, str]] = []

    def exists(rel: str) -> bool:
        return rel not in missing and (rel in present or rel in overrides or (root / rel).exists())

    def text(rel: str) -> str:
        if rel in overrides:
            return overrides[rel]
        try:
            return (root / rel).read_text(encoding="utf-8")
        except OSError:
            return ""

    declared_files = set(data.get("required_repository_files") or [])
    for rel in sorted(REQUIRED_REPOSITORY_FILES - declared_files):
        out.append(finding(
            "required-file-undeclared", "docs/release-evidence.json",
            f"required repository file omitted: {rel}",
            "restore the file to the machine-readable repository baseline",
        ))
    for rel in sorted(declared_files):
        if not exists(rel):
            out.append(finding(
                "required-file-missing", rel, "declared repository work product is absent",
                "restore the file or correct the reviewed applicability record",
            ))

    products = data.get("repository_work_products")
    if not isinstance(products, list):
        return out + [finding(
            "work-product-shape", "docs/release-evidence.json",
            "repository_work_products must be an array",
            "restore one object per reviewed work product",
        )]

    rows = [row for row in products if isinstance(row, dict)]
    if len(rows) != len(products):
        out.append(finding(
            "work-product-shape", "docs/release-evidence.json",
            "every repository work product must be an object",
            "restore id, requirement, status, and paths",
        ))
    ids = [str(row.get("id", "<missing>")) for row in rows]
    if len(ids) != len(set(ids)):
        out.append(finding(
            "work-product-duplicate", "docs/release-evidence.json",
            "repository work-product IDs repeat", "keep one row per work product",
        ))
    for product_id in sorted(set(EXPECTED_LEVELS) - set(ids)):
        out.append(finding(
            "work-product-missing", "docs/release-evidence.json",
            f"repository work product omitted: {product_id}",
            "restore its requirement, disposition, and public paths",
        ))
    for product_id in sorted(set(ids) - set(EXPECTED_LEVELS)):
        out.append(finding(
            "work-product-unrecognized", "docs/release-evidence.json",
            f"unreviewed repository work product: {product_id}",
            "classify the new work product in the validator before relying on it",
        ))

    for row in rows:
        product_id = str(row.get("id", "<missing>"))
        level = row.get("requirement")
        status = row.get("status")
        expected_level = EXPECTED_LEVELS.get(product_id)
        if expected_level and level != expected_level:
            out.append(finding(
                "work-product-level", "docs/release-evidence.json",
                f"{product_id} must remain {expected_level}, not {level}",
                "restore the reviewed requirement level",
            ))

        if level in {"show-stopper", "required"} and status != "satisfied":
            out.append(finding(
                "work-product-status", "docs/release-evidence.json",
                f"{product_id} is {level} and must be satisfied",
                "restore its tracked evidence before release",
            ))
        if product_id == "coding-guideline" and status != "satisfied":
            out.append(finding(
                "work-product-status", "docs/release-evidence.json",
                "coding guidance applies to this contribution-enabled repository",
                "restore the contributor and agent coding guidance",
            ))
        if product_id == "contributor-license-agreement":
            if status != "not-applicable" or "Apache-2.0" not in str(row.get("rationale", "")):
                out.append(finding(
                    "work-product-applicability", "docs/release-evidence.json",
                    "CLA disposition must record the reviewed Apache-2.0 not-applicable rationale",
                    "restore the license-specific applicability decision",
                ))
        elif level == "optional" and status not in {"satisfied", "not-selected"}:
            out.append(finding(
                "work-product-status", "docs/release-evidence.json",
                f"optional {product_id} has invalid status {status}",
                "use satisfied with evidence paths or not-selected without paths",
            ))

        paths = row.get("paths")
        if not isinstance(paths, list):
            out.append(finding(
                "work-product-paths", "docs/release-evidence.json",
                f"{product_id} paths must be an array", "restore the public evidence paths",
            ))
            continue
        if status == "satisfied" and not paths:
            out.append(finding(
                "work-product-paths", "docs/release-evidence.json",
                f"{product_id} claims satisfaction without evidence paths",
                "name at least one tracked work product",
            ))
        if status in {"not-applicable", "not-selected"} and paths:
            out.append(finding(
                "work-product-paths", "docs/release-evidence.json",
                f"{product_id} is {status} but still declares evidence paths",
                "clear the paths or mark the work product satisfied",
            ))
        for rel in paths:
            if not isinstance(rel, str) or not rel or not exists(rel):
                out.append(finding(
                    "work-product-path", "docs/release-evidence.json",
                    f"{product_id} path does not resolve: {rel}",
                    "restore the tracked work product or correct its path",
                ))

        if status in {"not-applicable", "not-selected"}:
            for rel in CONVENTIONAL_OPTIONAL_PATHS.get(product_id, ()):
                if exists(rel):
                    out.append(finding(
                        "work-product-presence-drift", rel,
                        f"{product_id} is {status} but {rel} exists",
                        "update applicability and evidence paths, or remove the unselected file",
                    ))

    security = text("SECURITY.md")
    security_sha = hashlib.sha256(security.encode("utf-8")).hexdigest()
    if security_sha != SECURITY_TEMPLATE_SHA256:
        out.append(finding(
            "security-template", "SECURITY.md",
            f"official repository template changed: sha256={security_sha}",
            "restore the NVIDIA-initialized SECURITY.md verbatim",
        ))
    if "SECURITY.md text eol=lf whitespace=-space-before-tab" not in text(".gitattributes"):
        out.append(finding(
            "security-template-whitespace", ".gitattributes",
            "path-scoped whitespace rule for the verbatim security template is missing",
            "restore the SECURITY.md-only space-before-tab exception",
        ))

    changelog = text("CHANGELOG.md")
    for token in ("# Changelog", "## Unreleased", "docs/release_artifacts.md"):
        if token not in changelog:
            out.append(finding(
                "changelog-contract", "CHANGELOG.md", f"missing changelog token: {token}",
                "restore pending version history and its artifact-contract link",
            ))

    readme = text("README.md")
    for token in ("](CHANGELOG.md)", "](docs/release_playbook.md)", "](SECURITY.md)",
                     "](THIRD_PARTY_LICENSES.md)",
                     "](CONTRIBUTING.md)", "](CODE_OF_CONDUCT.md)"):
        if token not in readme:
            out.append(finding(
                "readme-work-product-link", "README.md", f"missing public work-product link: {token}",
                "restore the canonical policy link from the public entry point",
            ))

    playbook = text("docs/release_playbook.md")
    for token in (
        "## Maintainer operating plan", "Dependency management", "Issue triage", "CI/CD",
        "Testing", "Version history", "## Hotfix workflow",
    ):
        if token not in playbook:
            out.append(finding(
                "maintainer-plan", "docs/release_playbook.md",
                f"maintainer plan omits: {token}",
                "restore dependency, release, issue/hotfix, CI/CD, and testing ownership",
            ))

    contributing = text("CONTRIBUTING.md")
    for token in ("## Conventions", "release_gate.py --tier fast", "source_gate.py"):
        if token not in contributing:
            out.append(finding(
                "coding-guideline", "CONTRIBUTING.md", f"coding guidance omits: {token}",
                "restore style, validation, and source-governance guidance",
            ))

    token_contracts = {
        ".github/ISSUE_TEMPLATE/bug.yml": (
            "name: Bug report", "static `web/nemoclaw/` course", "private route in `SECURITY.md`",
        ),
        ".github/ISSUE_TEMPLATE/feature.yml": (
            "name: Feature request", "Ideas require no patch", "label: Desired outcome",
        ),
        ".gitlab/issue_templates/Bug report.md": (
            "## Reproduction", "private route in `SECURITY.md`",
        ),
        ".gitlab/issue_templates/Feature request.md": (
            "## Problem", "## Desired outcome",
        ),
    }
    for rel, tokens in token_contracts.items():
        raw = text(rel)
        for token in tokens:
            if token not in raw:
                out.append(finding(
                    "issue-template-contract", rel, f"missing issue intake token: {token}",
                    "restore explicit Bug/Feature intake and private security routing",
                ))

    baseline_area = next(
        (row for row in data.get("evidence_areas", [])
         if isinstance(row, dict) and row.get("id") == "repository-baseline"),
        {},
    )
    commands = baseline_area.get("automated_commands") or []
    if "python3 scripts/validation/repository_work_products_audit.py" not in commands:
        out.append(finding(
            "work-product-evidence-wiring", "docs/release-evidence.json",
            "repository baseline does not invoke the work-product audit",
            "add the current-tree validator to repository-baseline evidence",
        ))

    for rel, tokens in WIRING.items():
        raw = text(rel)
        for token in tokens:
            if token not in raw:
                out.append(finding(
                    "work-product-wiring", rel, f"missing validator wiring: {token}",
                    "wire the audit into discovery, early feedback, the shared gate, and durable reports",
                ))
    return out


def self_test() -> tuple[int, int, list[str]]:
    base = load_contract()
    baseline = audit_contract(base)
    if baseline:
        return 0, 0, [f"baseline is not clean: {row['code']} {row['path']} {row['detail']}" for row in baseline]

    tests: list[tuple[str, dict, dict[str, str], set[str], set[str], str]] = []

    def mutated() -> dict:
        return copy.deepcopy(base)

    def product(data: dict, product_id: str) -> dict:
        return next(row for row in data["repository_work_products"] if row["id"] == product_id)

    def add(name: str, data: dict, expected: str, *, overrides: dict[str, str] | None = None,
            missing: set[str] | None = None, present: set[str] | None = None) -> None:
        tests.append((name, data, overrides or {}, missing or set(), present or set(), expected))

    value = mutated(); value["required_repository_files"].remove("CHANGELOG.md")
    add("undeclared required file", value, "required-file-undeclared")
    add("missing required file", mutated(), "required-file-missing", missing={"CHANGELOG.md"})
    value = mutated(); value["repository_work_products"] = [row for row in value["repository_work_products"] if row["id"] != "changelog"]
    add("missing work product", value, "work-product-missing")
    value = mutated(); value["repository_work_products"].append(copy.deepcopy(value["repository_work_products"][0]))
    add("duplicate work product", value, "work-product-duplicate")
    value = mutated(); value["repository_work_products"].append({"id": "unreviewed", "requirement": "optional", "status": "not-selected", "paths": []})
    add("unrecognized work product", value, "work-product-unrecognized")
    value = mutated(); product(value, "maintainer-plan")["requirement"] = "optional"
    add("requirement drift", value, "work-product-level")
    value = mutated(); product(value, "readme")["status"] = "not-selected"
    add("show stopper status", value, "work-product-status")
    value = mutated(); product(value, "coding-guideline")["status"] = "not-selected"
    add("coding applicability", value, "work-product-status")
    value = mutated(); product(value, "contributor-license-agreement").pop("rationale")
    add("CLA rationale", value, "work-product-applicability")
    value = mutated(); product(value, "citation")["status"] = "unknown"
    add("optional status", value, "work-product-status")
    value = mutated(); product(value, "maintainer-plan")["paths"] = []
    add("satisfied without paths", value, "work-product-paths")
    value = mutated(); product(value, "citation")["paths"] = ["CITATION.cff"]
    add("unselected with paths", value, "work-product-paths")
    value = mutated(); product(value, "maintainer-plan")["paths"] = ["docs/missing-plan.md"]
    add("broken evidence path", value, "work-product-path")
    add("CLA presence drift", mutated(), "work-product-presence-drift", present={"CLA.md"})
    add("citation presence drift", mutated(), "work-product-presence-drift", present={"CITATION.cff"})

    def replace(rel: str, old: str, new: str, expected: str, name: str) -> None:
        raw = (ROOT / rel).read_text(encoding="utf-8")
        if old not in raw:
            tests.append((name + " fixture missing", mutated(), {}, set(), set(), "fixture-missing"))
            return
        add(name, mutated(), expected, overrides={rel: raw.replace(old, new, 1)})

    replace("SECURITY.md", "psirt@nvidia.com", "security@example.invalid", "security-template", "security bytes")
    replace(".gitattributes", "SECURITY.md text eol=lf whitespace=-space-before-tab", "SECURITY.md text eol=lf", "security-template-whitespace", "security whitespace")
    replace("CHANGELOG.md", "## Unreleased", "## Pending", "changelog-contract", "changelog heading")
    replace("README.md", "](CHANGELOG.md)", "](history.md)", "readme-work-product-link", "readme link")
    replace("docs/release_playbook.md", "Dependency management", "Package handling", "maintainer-plan", "maintainer dependency")
    replace("docs/release_playbook.md", "## Hotfix workflow", "## Urgent changes", "maintainer-plan", "hotfix process")
    replace("CONTRIBUTING.md", "## Conventions", "## Style notes", "coding-guideline", "coding guidance")
    replace(".github/ISSUE_TEMPLATE/bug.yml", "name: Bug report", "name: Report", "issue-template-contract", "bug form")
    replace(".github/ISSUE_TEMPLATE/bug.yml", "private route in `SECURITY.md`", "public comments", "issue-template-contract", "security route")
    replace(".github/ISSUE_TEMPLATE/feature.yml", "Ideas require no patch", "A patch is required", "issue-template-contract", "feature form")
    replace(".gitlab/issue_templates/Feature request.md", "## Desired outcome", "## Implementation", "issue-template-contract", "GitLab parity")
    value = mutated(); area = next(row for row in value["evidence_areas"] if row["id"] == "repository-baseline"); area["automated_commands"].remove("python3 scripts/validation/repository_work_products_audit.py")
    add("evidence wiring", value, "work-product-evidence-wiring")
    replace("scripts/validation/SKILL.html", "Repository work products + detector", "Repository policy", "work-product-wiring", "SKILL discovery")
    raw = (ROOT / "scripts/validation/release_gate.py").read_text(encoding="utf-8")
    add("release gate", mutated(), "work-product-wiring", overrides={
        "scripts/validation/release_gate.py": raw.replace(
            'py("scripts/validation/repository_work_products_audit.py", "--self-test")',
            'py("scripts/validation/repository_work_products_audit.py", "--help")',
        ),
    })
    raw = (ROOT / "scripts/validation/validate_bundle.py").read_text(encoding="utf-8")
    add("bundle suite", mutated(), "work-product-wiring", overrides={
        "scripts/validation/validate_bundle.py": raw.replace(
            '"repository_work_products"', '"repository_baseline_removed"',
        ),
    })
    replace("scripts/git-hooks/pre-commit", "repository_work_products_audit.py", "repository_policy_removed.py", "work-product-wiring", "pre-commit")
    replace("docs/release-test-plan.md", "repository_work_products_audit.py --self-test", "repository_work_products_audit.py --help", "work-product-wiring", "test plan")
    replace("docs/agent_process.md", "repository_work_products_audit.py --self-test", "repository_work_products_audit.py --help", "work-product-wiring", "agent process")

    passed = 0
    failures: list[str] = []
    for name, data, overrides, missing, present, expected in tests:
        codes = {row["code"] for row in audit_contract(
            data, text_overrides=overrides, missing_paths=missing, present_paths=present,
        )}
        if expected in codes:
            passed += 1
        else:
            failures.append(f"{name}: expected {expected}, got {sorted(codes)}")
    return passed, len(tests), failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        passed, total, failures = self_test()
        print(f"repository work-product self-test: {passed}/{total} mutation detectors passed")
        for failure in failures:
            print("  FAIL " + failure)
        return 1 if failures else 0
    try:
        rows = audit_contract(load_contract())
    except (OSError, json.JSONDecodeError) as exc:
        rows = [finding(
            "contract-read", "docs/release-evidence.json", str(exc),
            "restore valid machine-readable release evidence",
        )]
    if args.json:
        print(json.dumps({"schema": "repository-work-products-audit/1", "findings": rows}, indent=2))
    else:
        print(f"repository work-product audit: {len(rows)} finding(s)")
        for row in rows:
            print(f"  [{row['code']}] {row['path']}: {row['detail']}")
            print(f"    fix: {row['fix']}")
    return 1 if rows else 0


if __name__ == "__main__":
    raise SystemExit(main())
