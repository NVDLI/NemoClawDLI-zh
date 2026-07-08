#!/usr/bin/env python3
"""Run the canonical deterministic repository validation ladder.

Host-specific submission, commit-range, live-source, and deployment checks remain in
their workflows. This script owns the deterministic checks shared by local contributors,
GitLab, GitHub Pages, and the protected release workflow.

Use ``--changed-since`` on proposal branches. Current-tree audits still run, while expensive
mutation suites run only when their validator or protected contract changed. Omit the option
for a full release execution. Successful clean local runs are recorded under the worktree's
Git directory unless ``--no-write`` is active; ``--reuse-success`` may reuse only the identical
commit and gate definition. CI never depends on that local optimization.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable
CACHE_SCHEMA = "release-gate-success/1"
TIMING_SCHEMA = "release-gate-timing/1"


def py(path: str, *args: str) -> tuple[str, ...]:
    return (PYTHON, path, *args)


def unit_test(name: str) -> tuple[str, ...]:
    return py(
        "-m", "unittest", "-v",
        f"tests.validation.test_embedded_validator_suites.ValidatorSelfTests.test_{name}",
    )


def cli_unit_test(name: str) -> tuple[str, ...]:
    return py(
        "-m", "unittest", "-v",
        f"tests.validation.test_embedded_validator_suites.ValidatorCliTests.test_{name}",
    )


HARNESS_CONTRACT = py("-m", "unittest", "-v", "tests.validation.test_test_harness_contract")
NODE_VALIDATOR_TESTS = ("bash", "scripts/runtime/run_node.sh", "tests/runtime/test_embedded_validator_suites.mjs")


FAST_COMMANDS: tuple[tuple[str, ...], ...] = (
    py("scripts/build/bundle_standalone.py", "--self-test"),
    py("scripts/build/build_security_review_package.py", "--self-test"),
    py("scripts/materials/pull_materials.py", "--verify-committed"),
    unit_test("local_path_leak_audit"),
    py("scripts/validation/local_path_leak_audit.py"),
    unit_test("sensitive_content_audit"),
    unit_test("release_change_reminder"),
    unit_test("validation_report_audit"),
    unit_test("pages_artifact_integrity"),
    unit_test("threat_control_audit"),
    unit_test("repository_sync_audit"),
    py("scripts/skills/skill_consistency.py"),
    py("scripts/skills/gen_directory_beacons.py", "--check"),
    py("scripts/skills/normalize_skill_headers.py", "--self-test"),
    py("scripts/skills/normalize_skill_headers.py", "--check"),
    py("scripts/skills/test_skill_contract.py"),
    py("scripts/skills/skill_contract.py"),
    unit_test("project_docs_explorer"),
    HARNESS_CONTRACT,
    py("scripts/build/project_docs_explorer.py", "--audit"),
    py("scripts/build/project_source_tree.py", "--self-test"),
    py("scripts/security/audit_iframe_proxy_opt_in.py"),
    py("scripts/validation/endpoint_registration_audit.py"),
    ("bash", "scripts/runtime/run_node.sh", "scripts/validation/openclaw_connection_audit.mjs"),
    py("scripts/compliance/source_gate.py"),
    py("scripts/compliance/third_party_inventory_audit.py"),
    unit_test("third_party_inventory_audit"),
    unit_test("export_third_party_csv"),
    unit_test("export_legal_scope_csv"),
    unit_test("render_sbom_license_inventory"),
    py("scripts/validation/tenets.py", "--check"),
    py("scripts/runtime/module_check.py", "--dir", "web/nemoclaw"),
    py("scripts/runtime/module_check.py", "--dir", "web"),
    py("scripts/validation/validate_bundle.py", "--scope", "ship", "--no-write"),
)


SHIP_COMMANDS: tuple[tuple[str, ...], ...] = (
    py("scripts/build/bundle_standalone.py", "--self-test"),
    py("scripts/build/build_security_review_package.py", "--self-test"),
    unit_test("materials"),
    py("scripts/materials/pull_materials.py", "--verify-committed"),
    unit_test("local_path_leak_audit"),
    py("scripts/validation/local_path_leak_audit.py"),
    # validate_bundle owns the current-tree sensitive, layout, architecture, release-evidence,
    # repository-work-product, localization, contribution, browser-dependency, and cell audits.
    # Keep only their mutation suites here so one shared gate never scans the same tree twice.
    unit_test("sensitive_content_audit"),
    unit_test("release_change_reminder"),
    unit_test("validation_report_audit"),
    unit_test("pages_artifact_integrity"),
    unit_test("threat_control_audit"),
    unit_test("repository_sync_audit"),
    py("scripts/skills/skill_consistency.py"),
    py("scripts/skills/gen_directory_beacons.py", "--check"),
    py("scripts/skills/normalize_skill_headers.py", "--self-test"),
    py("scripts/skills/normalize_skill_headers.py", "--check"),
    py("scripts/skills/test_skill_contract.py"),
    py("scripts/skills/skill_contract.py"),
    py("scripts/validation/ci_storage_audit.py"),
    py("scripts/validation/branch_preview_manifest_audit.py", "--self-test"),
    py("scripts/validation/learner_flow_audit.py", "--self-test"),
    py("scripts/validation/html_structure_audit.py", "--self-test"),
    py("scripts/validation/code_hygiene.py", "--self-test"),
    unit_test("slides_audit"),
    py("scripts/build/build_repository_overview_html.py", "--check"),
    py("scripts/figures/render_security_architecture.py", "--check"),
    unit_test("security_architecture_audit"),
    unit_test("project_docs_explorer"),
    HARNESS_CONTRACT,
    py("scripts/build/project_docs_explorer.py", "--audit"),
    py("scripts/build/project_source_tree.py", "--self-test"),
    unit_test("release_evidence_audit"),
    unit_test("repository_work_products_audit"),
    NODE_VALIDATOR_TESTS,
    py("scripts/build/assemble_locale_overlay.py", "--self-test"),
    py("scripts/validation/localization_audit.py", "--self-test"),
    py("scripts/validation/contribution_safety_audit.py", "--self-test"),
    py(
        "scripts/validation/contribution_safety_audit.py",
        "--report",
        "docs/validation/contribution-safety.json",
    ),
    py("scripts/security/audit_iframe_proxy_opt_in.py", "--self-test"),
    py("scripts/security/audit_iframe_proxy_opt_in.py"),
    py("scripts/validation/endpoint_registration_audit.py", "--self-test"),
    py("scripts/validation/endpoint_registration_audit.py"),
    ("bash", "scripts/runtime/run_node.sh", "scripts/validation/openclaw_connection_audit.mjs"),
    py("scripts/compliance/source_gate.py"),
    py("scripts/compliance/third_party_inventory_audit.py"),
    unit_test("third_party_inventory_audit"),
    unit_test("export_third_party_csv"),
    unit_test("export_legal_scope_csv"),
    unit_test("render_sbom_license_inventory"),
    unit_test("course_dependency_integrity"),
    cli_unit_test("cell_audit"),
    py("scripts/security/audit_python_dependencies.py"),
    py("scripts/security/audit_vulnerability_waivers.py"),
    py("scripts/security/audit_dependency_locks.py", "--self-test"),
    py("scripts/security/audit_dependency_locks.py"),
    py("scripts/security/audit_sbom_policy.py", "--self-test"),
    py("scripts/build/package_release.py", "--self-test"),
    py("scripts/validation/tenets.py", "--check"),
    py("scripts/runtime/module_check.py", "--dir", "web/nemoclaw"),
    py("scripts/runtime/module_check.py", "--dir", "web"),
    py("scripts/validation/validate_bundle.py", "--scope", "ship"),
)


# Mutation suites prove their detectors. Current-tree behavior remains in validate_bundle.
# Proposal runs may skip a mutation suite only when none of its implementation or contract
# inputs changed. Full release runs omit --changed-since and execute every suite.
MUTATION_IMPACTS: dict[tuple[str, ...], tuple[str, ...]] = {
    py("scripts/skills/normalize_skill_headers.py", "--self-test"): (
        "scripts/skills/normalize_skill_headers.py", "scripts/skills/gen_directory_beacons.py",
        "SKILL_CONTRACT.md", "**/SKILL.html",
    ),
    unit_test("third_party_inventory_audit"): (
        "THIRD_PARTY_LICENSES.md", "scripts/compliance/third_party_inventory_audit.py",
        "scripts/browser-vendor/package-lock.json", "web/nemoclaw/vendor/*",
        "workspace/requirements*", "scripts/materials/requirements*",
        "scripts/security/requirements*", "cpu/services/*", "web/nemoclaw/assets/SKILL.html",
        "web/nemoclaw/mats/SKILL.html", "scripts/build/build_pages.sh",
    ),
    unit_test("render_sbom_license_inventory"): (
        "THIRD_PARTY_LICENSES.md", "scripts/compliance/render_sbom_license_inventory.py",
        "scripts/compliance/third_party_inventory_audit.py",
    ),
    unit_test("export_third_party_csv"): (
        "THIRD_PARTY_LICENSES.md", "scripts/compliance/export_third_party_csv.py",
        "scripts/compliance/third_party_inventory_audit.py", "scripts/compliance/SKILL.html",
        "scripts/compliance/third_party_export_ui.js", "web/nemoclaw/vendor/browser-dependencies.json",
    ),
    unit_test("export_legal_scope_csv"): (
        "THIRD_PARTY_LICENSES.md", "scripts/compliance/export_legal_scope_csv.py",
        "scripts/compliance/export_third_party_csv.py", "scripts/compliance/SKILL.html",
        "scripts/compliance/third_party_export_ui.js", "web/nemoclaw/vendor/browser-dependencies.json",
    ),
    py("scripts/build/build_security_review_package.py", "--self-test"): (
        "scripts/build/build_security_review_package.py", "docs/product-design.md",
        "docs/security-design.md", "docs/security-control-disposition.md", "docs/release-test-plan.md",
        "docs/SKILL.html", "scripts/build/SKILL.html",
    ),
    py("scripts/build/project_source_tree.py", "--self-test"): (
        "scripts/build/project_source_tree.py", "scripts/build/build_pages.sh",
        "scripts/build/SKILL.html", "scripts/skills/skill_audit.py",
    ),
    py("scripts/build/bundle_standalone.py", "--self-test"): (
        "scripts/build/bundle_standalone.py", "scripts/build/build_pages.sh",
        "web/nemoclaw/*.html", "web/nemoclaw/assets/figures/*",
        "i18n/*/web/nemoclaw/*.html",
    ),
    unit_test("materials"): (
        "scripts/materials/pull_materials.py", "scripts/materials/requirements*",
    ),
    unit_test("local_path_leak_audit"): (
        "scripts/validation/local_path_leak_audit.py",
    ),
    unit_test("sensitive_content_audit"): (
        "scripts/validation/sensitive_content_audit.py", "scripts/validation/sensitive-content-policy.json",
    ),
    unit_test("release_change_reminder"): (
        "scripts/validation/release_change_reminder.py",
    ),
    unit_test("validation_report_audit"): (
        "scripts/validation/validation_report_audit.py", "scripts/validation/validate_bundle.py",
        "scripts/build/build_pages.sh", ".gitlab-ci.yml", ".github/workflows/*",
    ),
    unit_test("pages_artifact_integrity"): (
        "scripts/validation/pages_artifact_integrity.py", "scripts/build/build_pages.sh",
        ".github/workflows/pages.yml", "docs/pages_deploy.md", "docs/release-test-plan.md",
    ),
    unit_test("threat_control_audit"): (
        "scripts/validation/threat_control_audit.py", "scripts/validation/pages_artifact_integrity.py",
        "scripts/validation/repository_sync_audit.py", ".github/workflows/pages.yml",
        ".github/workflows/release.yml", ".gitlab-ci.yml", "docs/release_playbook.md",
        "docs/security-control-disposition.md",
    ),
    unit_test("repository_sync_audit"): (
        "scripts/validation/repository_sync_audit.py", ".gitlab-ci.yml",
        "docs/release_playbook.md",
    ),
    py("scripts/validation/branch_preview_manifest_audit.py", "--self-test"): (
        "scripts/validation/branch_preview_manifest_audit.py", "scripts/build/build_branch_manifest.py",
        "web/index.html", ".gitlab-ci.yml",
    ),
    py("scripts/validation/learner_flow_audit.py", "--self-test"): (
        "scripts/validation/learner_flow_audit.py", "web/nemoclaw/scripts/*", "web/nemoclaw/styles/*",
        "web/nemoclaw/0*.html", "i18n/*/web/nemoclaw/0*.html", "scripts/browser-vendor/*",
    ),
    py("scripts/validation/html_structure_audit.py", "--self-test"): (
        "scripts/validation/html_structure_audit.py",
    ),
    py("scripts/validation/code_hygiene.py", "--self-test"): (
        "scripts/validation/code_hygiene.py",
    ),
    unit_test("slides_audit"): (
        "scripts/validation/slides_audit.py", "scripts/validation/prose_variety.py",
        "scripts/build/build_repository_overview*", "docs/repository-overview*",
        "docs/assets/repository-overview/*",
    ),
    unit_test("security_architecture_audit"): (
        "scripts/validation/security_architecture_audit.py", "scripts/figures/render_security_architecture.py",
        "docs/security-architecture*", ".gitlab-ci.yml", ".github/workflows/*",
    ),
    unit_test("project_docs_explorer"): (
        "scripts/build/project_docs_explorer.py", "docs/SKILL.html",
    ),
    unit_test("release_evidence_audit"): (
        "scripts/validation/release_evidence_audit.py", "docs/product-design.md",
        "docs/release-test-plan.md", "docs/release-evidence.json", "RELEASE_STATUS*",
    ),
    unit_test("repository_work_products_audit"): (
        "scripts/validation/repository_work_products_audit.py", "docs/release-evidence.json",
        "README.md", "LICENSE", "SECURITY.md", "CHANGELOG.md", "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md", "docs/release_playbook.md", "docs/release-test-plan.md",
        "docs/agent_process.md", ".gitattributes", ".github/ISSUE_TEMPLATE/*",
        ".github/PULL_REQUEST_TEMPLATE.md", ".gitlab/issue_templates/*",
        "scripts/validation/SKILL.html", "scripts/validation/release_gate.py",
        "scripts/validation/validate_bundle.py", "scripts/git-hooks/pre-commit",
    ),
    NODE_VALIDATOR_TESTS: (
        "scripts/validation/gateway_token_audit.mjs", "scripts/validation/openclaw_fallback_audit.py",
        "scripts/validation/openclaw_connection_audit.mjs", "scripts/runtime/test_page_runtime.js",
        "scripts/runtime/lab_runtime_test.sh", "web/nemoclaw/scripts/_connection.js",
        "web/nemoclaw/scripts/_openclaw.js", "web/nemoclaw/scripts/_openshell.js",
        "web/nemoclaw/scripts/_shared.js", "web/nemoclaw/03a-kickstart.html", "web/nemoclaw/04b-modern-clis.html",
        "i18n/pt/web/nemoclaw/03a-kickstart.html", "i18n/es/web/nemoclaw/03a-kickstart.html",
        "i18n/pt/web/nemoclaw/04b-modern-clis.html", "i18n/es/web/nemoclaw/04b-modern-clis.html",
        "scripts/runtime/engine.js", "scripts/runtime/link_projection.py", "scripts/runtime/run_engine.sh",
        "scripts/runtime/run_node.sh", "deploy/*", "workspace/entrypoint.sh",
    ),
    py("scripts/build/assemble_locale_overlay.py", "--self-test"): (
        "scripts/build/assemble_locale_overlay.py", "scripts/translate/code_localization.py",
        "scripts/translate/locale_projection.py", "i18n/*/locale.json",
    ),
    py("scripts/validation/localization_audit.py", "--self-test"): (
        "scripts/validation/localization_audit.py", "scripts/translate/locales/*",
        "scripts/translate/code_localization.py", "scripts/translate/locale_projection.py",
        "scripts/build/assemble_locale_overlay.py", "i18n/*/locale.json",
        "web/nemoclaw/scripts/_keypanel.js", "web/nemoclaw/scripts/_locale.js",
        "web/nemoclaw/scripts/_shared.js",
    ),
    py("scripts/validation/contribution_safety_audit.py", "--self-test"): (
        ".github/*", ".github/**/*", ".gitlab-ci.yml", ".gitlab/*", ".gitlab/**/*",
        "AGENTS.md", "CONTRIBUTING.md", "DCO.md", "LICENSE", "RELEASE_STATUS.json",
        "CODE_OF_CONDUCT.md", "SUPPORT.md", "RELEASE_STATUS*",
        "docs/agent_process.md", "docs/release*", "docs/pages_deploy.md",
        "scripts/git-hooks/*", "scripts/build/install-hooks.sh", "scripts/build/build_pages.sh",
        "scripts/build/package_release.py", "scripts/validation/release_gate.py",
        "scripts/validation/contribution_safety_audit.py", "scripts/security/*", "workspace/*",
    ),
    py("scripts/security/audit_iframe_proxy_opt_in.py", "--self-test"): (
        "scripts/security/audit_iframe_proxy_opt_in.py", "scripts/cors-proxy/*",
        "web/nemoclaw/index.html", "web/nemoclaw/scripts/_keypanel.js",
        "web/nemoclaw/scripts/_shared.js",
    ),
    py("scripts/validation/endpoint_registration_audit.py", "--self-test"): (
        "scripts/validation/endpoint_registration_audit.py", "web/nemoclaw/scripts/_shared.js",
        "web/nemoclaw/scripts/_keypanel.js", "web/nemoclaw/scripts/_connection.js",
        "web/nemoclaw/scripts/_openclaw.js", "web/nemoclaw/03a-kickstart.html",
        "web/_skill_explorer.js", "scripts/cors-proxy/SKILL.html",
        "scripts/runtime/test_page_runtime.js", "scripts/validation/runtime_integration_browser_audit.py",
        "i18n/pt/web/nemoclaw/03a-kickstart.html", "i18n/es/web/nemoclaw/03a-kickstart.html",
    ),
    unit_test("course_dependency_integrity"): (
        "scripts/validation/course_dependency_integrity.py", "scripts/browser-vendor/*",
        "scripts/build/vendor_browser_dependencies.mjs", "web/nemoclaw/vendor/*",
    ),
    cli_unit_test("cell_audit"): (
        "scripts/validation/cell_audit.py", "web/nemoclaw/scripts/*", "web/nemoclaw/vendor/*",
    ),
    py("scripts/security/audit_dependency_locks.py", "--self-test"): (
        "scripts/security/audit_dependency_locks.py", "workspace/requirements*",
        "scripts/materials/requirements*", "scripts/security/requirements-sca*",
    ),
    py("scripts/security/audit_sbom_policy.py", "--self-test"): (
        "scripts/security/audit_sbom_policy.py",
    ),
    py("scripts/build/package_release.py", "--self-test"): (
        "scripts/build/package_release.py", "docs/release_artifacts.md", ".github/workflows/release.yml",
    ),
    HARNESS_CONTRACT: (
        "tests/validation/test_test_harness_contract.py", "scripts/**/*.py",
        "scripts/**/*.js", "scripts/**/*.mjs", "scripts/**/*.sh",
        "workspace/**/*.py", "cpu/**/*.py", "deploy/**/*.py",
    ),
}


def commands_for(tier: str, *, no_write: bool) -> list[tuple[str, ...]]:
    commands = list(FAST_COMMANDS if tier == "fast" else SHIP_COMMANDS)
    if no_write:
        commands = [
            command
            for command in commands
            if not (
                command[:2] == (PYTHON, "scripts/validation/contribution_safety_audit.py")
                and "--report" in command
            )
        ]
        commands = [
            (*command, "--no-write")
            if command[:2] == (PYTHON, "scripts/validation/validate_bundle.py")
            and "--no-write" not in command
            else command
            for command in commands
        ]
    return commands


def display(command: Iterable[str]) -> str:
    return " ".join(command)


def _git(*args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=ROOT, check=False, text=True, capture_output=True,
    )
    if check and proc.returncode:
        raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout.strip()


def changed_paths(revision: str) -> tuple[str, set[str]]:
    resolved = _git("rev-parse", f"{revision}^{{commit}}")
    paths: set[str] = set()
    for args in (
        ("diff", "--name-only", "-z", f"{resolved}..HEAD"),
        ("diff", "--name-only", "-z"),
        ("diff", "--cached", "--name-only", "-z"),
        ("ls-files", "--others", "--exclude-standard", "-z"),
    ):
        raw = subprocess.run(["git", *args], cwd=ROOT, check=False, capture_output=True)
        if raw.returncode:
            raise RuntimeError(f"git {' '.join(args)} failed; refusing change-aware skips")
        paths.update(os.fsdecode(item) for item in raw.stdout.split(b"\0") if item)
    return resolved, paths


def _matches(path: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(path, pattern)


def mutation_affected(command: tuple[str, ...], paths: set[str]) -> bool:
    patterns = MUTATION_IMPACTS.get(command)
    return True if patterns is None else any(_matches(path, pattern) for path in paths for pattern in patterns)


def _head() -> str | None:
    try:
        return _git("rev-parse", "HEAD")
    except RuntimeError:
        return None


def _clean() -> bool:
    try:
        return not _git("status", "--porcelain", "--untracked-files=all")
    except RuntimeError:
        return False


def _cache_path() -> Path | None:
    try:
        git_dir = Path(_git("rev-parse", "--git-dir"))
    except RuntimeError:
        return None
    if not git_dir.is_absolute():
        git_dir = ROOT / git_dir
    return git_dir / "release-gate-success.json"


def _signature(tier: str, no_write: bool, commands: list[tuple[str, ...]]) -> str:
    payload = json.dumps({"tier": tier, "no_write": no_write, "commands": commands}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def reusable_success(
    *, tier: str, no_write: bool, commands: list[tuple[str, ...]], changed_base: str | None,
) -> dict | None:
    path = _cache_path()
    if path is None or not path.is_file() or not _clean():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("schema") != CACHE_SCHEMA or data.get("head") != _head():
        return None
    if data.get("tier") != tier or data.get("signature") != _signature(tier, no_write, commands):
        return None
    cached_base = data.get("changed_base")
    if cached_base is not None and cached_base != changed_base:
        return None
    return data


def record_success(
    *, tier: str, no_write: bool, commands: list[tuple[str, ...]], changed_base: str | None,
    duration: float, executed: int, skipped: int,
) -> None:
    # --no-write is used by read-only host mounts (including the Apple Container runner). The
    # success cache is durable validator output too; following a worktree .git pointer to write it
    # would violate the mode and can turn an otherwise green gate into a bookkeeping failure.
    if no_write or os.environ.get("CI") or not _clean():
        return
    path = _cache_path()
    head = _head()
    if path is None or head is None:
        return
    data = {
        "schema": CACHE_SCHEMA,
        "head": head,
        "tier": tier,
        "no_write": no_write,
        "signature": _signature(tier, no_write, commands),
        "changed_base": changed_base,
        "duration_seconds": round(duration, 3),
        "executed": executed,
        "skipped": skipped,
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_timing_report(path: str | None, report: dict) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def self_test() -> list[str]:
    failures: list[str] = []
    fast = commands_for("fast", no_write=True)
    ship = commands_for("ship", no_write=False)
    mutation_commands = {
        command for command in ship
        if "--self-test" in command
        or ("-m" in command and "unittest" in command)
        or command == NODE_VALIDATOR_TESTS
    }
    checks = [
        (len(fast) < len(ship), "fast tier is smaller than ship tier"),
        (py("scripts/materials/pull_materials.py", "--verify-committed") in fast,
         "fast tier verifies committed material provenance"),
        (py("scripts/validation/sensitive_content_audit.py") not in ship,
         "ship tier delegates the sensitive tree scan to validate_bundle"),
        (py("scripts/validation/validate_layout.py", "--quiet") not in ship,
         "ship tier delegates layout to validate_bundle"),
        (py("scripts/validation/course_dependency_integrity.py") not in ship,
         "ship tier delegates browser dependency audit to validate_bundle"),
        (py("scripts/validation/localization_audit.py", "--locale", "pt-BR") not in ship,
         "ship tier delegates locale current-tree audits to validate_bundle"),
        (mutation_commands <= set(MUTATION_IMPACTS),
         "every mutation command declares change-impact inputs"),
        (not mutation_affected(unit_test("slides_audit"), {"web/nemoclaw/01a-loop.html"}),
         "unrelated course prose does not trigger slide mutation fixtures"),
        (mutation_affected(unit_test("slides_audit"), {"docs/repository-overview.slides.json"}),
         "slide source triggers slide mutation fixtures"),
        (py("scripts/validation/tenets.py", "--check") in fast and py("scripts/validation/tenets.py", "--check") in ship,
         "shared tiers include the tenets projection"),
        (ship[-1] == py("scripts/validation/validate_bundle.py", "--scope", "ship"),
         "ship tier ends with report-producing bundle gate"),
        (commands_for("ship", no_write=True)[-1]
         == py("scripts/validation/validate_bundle.py", "--scope", "ship", "--no-write"),
         "no-write mode reaches final bundle gate"),
        (not any("--report" in command for command in commands_for("ship", no_write=True)),
         "no-write mode suppresses durable contribution report"),
    ]
    failures.extend(label for passed, label in checks if not passed)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", choices=("fast", "ship"), default="fast")
    parser.add_argument("--no-write", action="store_true", help="avoid durable validator reports")
    parser.add_argument("--changed-since", metavar="REV", help="skip unaffected mutation suites")
    parser.add_argument("--reuse-success", action="store_true", help="reuse an identical clean local success")
    parser.add_argument("--timing-report", metavar="PATH", help="write per-command JSON timing evidence")
    parser.add_argument("--list", action="store_true", help="print commands without running them")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        failures = self_test()
        print("release gate self-test: " + ("FAIL" if failures else "PASS"))
        for failure in failures:
            print(f"  FAIL {failure}")
        return 1 if failures else 0

    commands = commands_for(args.tier, no_write=args.no_write)
    changed_base: str | None = None
    paths: set[str] | None = None
    if args.changed_since:
        try:
            changed_base, paths = changed_paths(args.changed_since)
        except RuntimeError as exc:
            print(f"release gate: FAIL: {exc}", file=sys.stderr)
            return 1

    if args.list:
        for command in commands:
            marker = ""
            if paths is not None and command in MUTATION_IMPACTS and not mutation_affected(command, paths):
                marker = "  # SKIP unaffected mutation suite"
            print(display(command) + marker)
        return 0

    if args.reuse_success:
        cached = reusable_success(
            tier=args.tier, no_write=args.no_write, commands=commands, changed_base=changed_base,
        )
        if cached is not None:
            print(
                "release gate: REUSED clean local success "
                f"tier={args.tier} head={cached['head'][:12]} "
                f"duration={cached.get('duration_seconds', '?')}s"
            )
            return 0

    env = os.environ.copy()
    rows: list[dict[str, object]] = []
    started_gate = time.monotonic()
    executed = 0
    skipped = 0
    for index, command in enumerate(commands, 1):
        if paths is not None and command in MUTATION_IMPACTS and not mutation_affected(command, paths):
            print(f"[release_gate {index}/{len(commands)}] SKIP unaffected mutation: {display(command)}", flush=True)
            rows.append({"index": index, "status": "skipped-unaffected", "seconds": 0.0,
                         "command": display(command)})
            skipped += 1
            continue
        print(f"[release_gate {index}/{len(commands)}] {display(command)}", flush=True)
        started = time.monotonic()
        completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
        elapsed = time.monotonic() - started
        rows.append({"index": index, "status": "passed" if completed.returncode == 0 else "failed",
                     "seconds": round(elapsed, 3), "command": display(command)})
        executed += 1
        print(f"[release_gate {index}/{len(commands)}] {elapsed:.3f}s", flush=True)
        if completed.returncode:
            total = time.monotonic() - started_gate
            report = {"schema": TIMING_SCHEMA, "ok": False, "tier": args.tier,
                      "head": _head(), "changed_since": changed_base,
                      "changed_paths": len(paths or ()), "duration_seconds": round(total, 3),
                      "executed": executed, "skipped": skipped, "commands": rows}
            write_timing_report(args.timing_report, report)
            print(f"release gate: FAIL ({completed.returncode}) {display(command)}", file=sys.stderr)
            return completed.returncode

    total = time.monotonic() - started_gate
    report = {"schema": TIMING_SCHEMA, "ok": True, "tier": args.tier,
              "head": _head(), "changed_since": changed_base,
              "changed_paths": len(paths or ()), "duration_seconds": round(total, 3),
              "executed": executed, "skipped": skipped, "commands": rows}
    write_timing_report(args.timing_report, report)
    record_success(tier=args.tier, no_write=args.no_write, commands=commands,
                   changed_base=changed_base, duration=total, executed=executed, skipped=skipped)
    print(
        f"release gate: PASS tier={args.tier} executed={executed} skipped={skipped} "
        f"duration={total:.3f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
