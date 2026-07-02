#!/usr/bin/env python3
"""Run the repository validation ladder from one executable definition.

Host-specific submission, commit-range, live-source, and deployment checks remain in
their workflows. This script owns the deterministic repository checks shared by local
contributors, GitLab, GitHub Pages, and the protected release workflow.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable


def py(path: str, *args: str) -> tuple[str, ...]:
    return (PYTHON, path, *args)


FAST_COMMANDS: tuple[tuple[str, ...], ...] = (
    py("scripts/materials/pull_materials.py", "--verify-committed"),
    py("scripts/validation/validate_layout.py", "--quiet"),
    py("scripts/skills/skill_consistency.py"),
    py("scripts/skills/skill_contract.py"),
    py("scripts/build/project_docs_explorer.py", "--self-test"),
    py("scripts/build/project_docs_explorer.py", "--audit"),
    py("scripts/compliance/source_gate.py"),
    py("scripts/validation/validate_bundle.py", "--scope", "ship", "--no-write"),
)


SHIP_COMMANDS: tuple[tuple[str, ...], ...] = (
    py("scripts/materials/pull_materials.py", "--self-test"),
    py("scripts/materials/pull_materials.py", "--verify-committed"),
    py("scripts/validation/validate_layout.py", "--quiet"),
    py("scripts/skills/skill_consistency.py"),
    py("scripts/skills/skill_contract.py"),
    py("scripts/validation/ci_storage_audit.py"),
    py("scripts/validation/branch_preview_manifest_audit.py", "--self-test"),
    py("scripts/validation/learner_flow_audit.py", "--self-test"),
    py("scripts/validation/html_structure_audit.py", "--self-test"),
    py("scripts/validation/slides_audit.py", "--self-test"),
    py("scripts/build/build_repository_overview_html.py", "--check"),
    py("scripts/figures/render_security_architecture.py", "--check"),
    py("scripts/validation/security_architecture_audit.py", "--self-test"),
    py("scripts/validation/security_architecture_audit.py"),
    py("scripts/build/project_docs_explorer.py", "--self-test"),
    py("scripts/build/project_docs_explorer.py", "--audit"),
    py("scripts/validation/release_evidence_audit.py", "--self-test"),
    py("scripts/validation/release_evidence_audit.py"),
    py("scripts/build/assemble_locale_overlay.py", "--self-test"),
    py("scripts/validation/localization_audit.py", "--self-test"),
    py("scripts/validation/contribution_safety_audit.py", "--self-test"),
    py(
        "scripts/validation/contribution_safety_audit.py",
        "--report",
        "docs/validation/contribution-safety.json",
    ),
    py("scripts/compliance/source_gate.py"),
    py("scripts/validation/course_dependency_integrity.py", "--self-test"),
    py("scripts/validation/course_dependency_integrity.py"),
    py("scripts/validation/cell_audit.py", "--self-test"),
    py("scripts/validation/cell_audit.py"),
    py("scripts/security/audit_python_dependencies.py"),
    py("scripts/security/audit_vulnerability_waivers.py"),
    py("scripts/security/audit_dependency_locks.py", "--self-test"),
    py("scripts/security/audit_dependency_locks.py"),
    py("scripts/security/audit_sbom_policy.py", "--self-test"),
    py("scripts/build/package_release.py", "--self-test"),
    ("bash", "scripts/runtime/run_engine.sh", "--self-test"),
    py("scripts/validation/validate_bundle.py", "--scope", "ship"),
)


def locale_commands(*, no_write: bool) -> list[tuple[str, ...]]:
    commands: list[tuple[str, ...]] = []
    for profile in sorted((ROOT / "scripts/translate/locales").glob("*/profile.json")):
        args = ["--locale", profile.parent.name]
        if no_write:
            args.append("--no-write")
        commands.append(py("scripts/validation/localization_audit.py", *args))
    return commands


def commands_for(tier: str, *, no_write: bool) -> list[tuple[str, ...]]:
    commands = list(FAST_COMMANDS if tier == "fast" else SHIP_COMMANDS)
    if tier == "ship":
        insert_at = commands.index(
            py("scripts/validation/contribution_safety_audit.py", "--self-test")
        )
        commands[insert_at:insert_at] = locale_commands(no_write=no_write)
    if no_write:
        commands = [
            py("scripts/validation/contribution_safety_audit.py")
            if command[:2]
            == (PYTHON, "scripts/validation/contribution_safety_audit.py")
            and "--report" in command
            else (
                (*command, "--no-write")
                if command[:2] == (PYTHON, "scripts/validation/validate_bundle.py")
                and "--no-write" not in command
                else command
            )
            for command in commands
        ]
    return commands


def display(command: Iterable[str]) -> str:
    return " ".join(command)


def self_test() -> tuple[int, int, list[str]]:
    failures: list[str] = []
    fast = commands_for("fast", no_write=True)
    ship = commands_for("ship", no_write=False)
    checks = [
        (len(fast) < len(ship), "fast tier is smaller than ship tier"),
        (
            py("scripts/build/project_docs_explorer.py", "--audit") in fast,
            "fast tier includes docs graph audit",
        ),
        (
            py("scripts/materials/pull_materials.py", "--verify-committed") in fast,
            "fast tier verifies committed material provenance without network access",
        ),
        (
            py("scripts/materials/pull_materials.py", "--self-test") in ship,
            "ship tier proves retry classification and tamper detection",
        ),
        (
            py("scripts/figures/render_security_architecture.py", "--check") in ship,
            "ship tier includes generated architecture freshness",
        ),
        (
            any("localization_audit.py" in command[1] and "--locale" in command for command in ship),
            "ship tier discovers locale profiles",
        ),
        (
            ship[-1] == py("scripts/validation/validate_bundle.py", "--scope", "ship"),
            "ship tier ends with report-producing bundle gate",
        ),
        (
            commands_for("ship", no_write=True)[-1]
            == py("scripts/validation/validate_bundle.py", "--scope", "ship", "--no-write"),
            "no-write mode reaches final bundle gate",
        ),
        (
            not any("--report" in command for command in commands_for("ship", no_write=True)),
            "no-write mode suppresses durable contribution report",
        ),
    ]
    failures.extend(label for passed, label in checks if not passed)
    return len(checks) - len(failures), len(checks), failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", choices=("fast", "ship"), default="fast")
    parser.add_argument("--no-write", action="store_true", help="avoid durable validator reports")
    parser.add_argument("--list", action="store_true", help="print commands without running them")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        passed, total, failures = self_test()
        print(f"release gate self-test: {passed}/{total} passed")
        for failure in failures:
            print(f"  FAIL {failure}")
        return 1 if failures else 0

    commands = commands_for(args.tier, no_write=args.no_write)
    if args.list:
        for command in commands:
            print(display(command))
        return 0

    env = os.environ.copy()
    for index, command in enumerate(commands, 1):
        print(f"[release_gate {index}/{len(commands)}] {display(command)}", flush=True)
        completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
        if completed.returncode:
            print(
                f"release gate: FAIL ({completed.returncode}) {display(command)}",
                file=sys.stderr,
            )
            return completed.returncode
    print(f"release gate: PASS tier={args.tier} checks={len(commands)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
