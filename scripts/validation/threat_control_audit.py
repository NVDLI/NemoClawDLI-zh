#!/usr/bin/env python3
"""Audit repository-owned threat controls and keep external limitations explicit."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DISPOSITION = "docs/security-control-disposition.md"
CONTROL_REGISTER = "docs/security-control-themes.json"
WORKFLOWS = (".github/workflows/pages.yml", ".github/workflows/release.yml")
REQUIRED_THEME_IDS = {
    "source-ci-trust",
    "build-supply-chain",
    "artifact-integrity",
    "static-host-browser",
    "browser-credentials",
    "relay-boundary",
    "model-service-boundary",
    "launchable-runtime-boundary",
    "availability-resource-controls",
    "assessment-fidelity",
}
REQUIRED_THEME_FIELDS = {
    "id", "title", "state", "owner", "current_control", "evidence",
    "future_candidate", "trigger", "verification",
}
ALLOWED_THEME_STATES = {
    "partially-verified",
    "external-evidence-required",
    "architecture-decision-required",
    "shared-verification-required",
    "human-review-required",
}
EXPECTED_OWNED = {
    "DLI course source and repository CI definitions",
    "validated static course artifact",
    "course JavaScript, HTML, CSS, images, and locale overlays executed by the learner browser",
}
EXPECTED_EXTERNAL = {
    "source host and CI execution service",
    "static hosting service",
    "co-located launchable",
    "learner browser and device",
    "model service",
    "NemoClaw runtime",
    "cross-origin relays",
}
EXPECTED_STATUS_RULES = {
    "Current status and current-control evidence take precedence over recommendations or future work.",
    "A future candidate is not implemented and cannot support a Mitigated status.",
    "An external control without current operator evidence remains Not Mitigated.",
    "A contradiction between a claimed mitigation and the Target of Evaluation resolves to the conservative status.",
    "A human reviewer or release owner is an actor, not a system component or automated control.",
}
REQUIRED_EXPLICIT_FACTS = {
    "Course source and released static artifacts are public; their confidentiality is not a security objective.",
    "Proposed-change build and validation jobs hold no signing key, model API credential, runtime credential, production-service secret, or deployment key.",
    "Artifact signing and provenance attestation are not implemented.",
    "CI does not write Git refs or repository content; logs and test results are job artifacts or external records.",
    "A protected-environment reviewer is a human actor, not a system component.",
    "The static host serves bytes; repository workflows, not the host, enforce build and deployment gates.",
    "Branch and merge-request validation is normal; protected annotated tags identify release candidates only.",
    "Model, relay, launchable, runtime, and live-host controls remain unknown without current operator evidence.",
}

REQUIRED_TOKENS = {
    DISPOSITION: (
        "## Status vocabulary",
        "## Review synthesis",
        "## Source and contribution controls",
        "## Build and artifact controls",
        "## Static hosting and browser controls",
        "## Relay, model, launchable, and runtime controls",
        "## Publication blockers and retained risks",
        "security-control-themes.json",
        "Do not version private review rows one-to-one",
        "cryptographic signature and provenance attestation are not verified",
        "The intended OSS Type I classification applies only to the NemoClaw DLI course repository",
        "It does not classify or release the NemoClaw product, launchable",
        "The course repository can test route selection and client behavior",
        "Unknown, partial, architecture-decision, shared-verification, and human-review states remain open",
        "A future candidate is not",
        "external control without current operator",
    ),
    "docs/product-design.md": (
        "The Type I subject is only the DLI course repository",
        "product, launchable, runtime, relays",
        "outside this classification",
        "external integration dependencies",
    ),
    "docs/security-design.md": (
        "## Threat-analysis invariants",
        "canonical Target of Evaluation summary",
        "published course artifact are public",
        "bearer credentials are JavaScript-readable",
        "values retained in `localStorage`",
        "hold no signing key, model API credential, runtime credential",
        "CI does not write Git refs or repository content",
        "reviewer is a human actor, not a component",
        "static host serves bytes",
        "protected annotated tags only",
        "only solid green nodes are Target of Evaluation components",
        "External-to-external internals are excluded",
        "Cryptographic signing or provenance attestation is Not verified",
        "does not assume mTLS, DPoP, zero-retention model processing",
        "live relay enforcement is Unknown",
        "deployed state is Unknown",
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
        "This classification is limited to `NVDLI/NemoClawDLI`",
        "classify or release the NemoClaw product",
    ),
    "docs/release-test-plan.md": (
        "| M10a | Generated threat-analysis reconciliation |",
        "The Target of Evaluation matches the canonical invariants",
        "public repository contains no private row-by-row assessment",
        "Complete M10a, then obtain M11",
    ),
    "scripts/build/build_security_review_package.py": (
        "Aggregate control and mitigation register",
        "self-contained supporting design",
        "evidence labels, not required reading",
        "Generated risk labels and mitigation statuses are advisory",
        "A future candidate is not implemented and cannot support a Mitigated status",
        "An external control without current operator evidence remains Not Mitigated",
        "Future candidate",
        "solid green nodes are Target of Evaluation components",
        "external-to-external internals are excluded",
        "section_body",
        '"Threat-analysis invariants"',
        "security-control-themes.json",
        "len(document.splitlines()) < 260",
    ),
    "RELEASE_STATUS.json": (
        '"publication_state": "pending-osrb-approval"',
        '"external_mirror": "reserved-not-populated"',
        '"canonical_repository": "internal-gitlab"',
        '"intended_oss_type": "Type-I"',
        '"oss_scope": "nemoclaw-dli-course-repository"',
        '"NemoClaw product"',
        '"NemoClaw launchable"',
        '"NemoClaw runtime"',
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

    try:
        register = json.loads(read(CONTROL_REGISTER, overrides))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(finding("control-register", CONTROL_REGISTER, f"cannot read control register: {exc}"))
        register = {}
    if register.get("schema") != "nemoclaw-security-control-themes/1":
        findings.append(finding("control-register-schema", CONTROL_REGISTER, "unexpected or missing schema"))
    target = register.get("target_of_evaluation") or {}
    if set(target.get("owned") or []) != EXPECTED_OWNED:
        findings.append(finding(
            "toe-owned-scope", CONTROL_REGISTER,
            "repository-owned Target of Evaluation components changed",
        ))
    if set(target.get("external_dependencies") or []) != EXPECTED_EXTERNAL:
        findings.append(finding(
            "toe-external-scope", CONTROL_REGISTER,
            "external dependency boundary changed",
        ))
    if "not a repository-owned component" not in str(target.get("ownership_rule", "")):
        findings.append(finding(
            "toe-ownership-rule", CONTROL_REGISTER,
            "data-flow participation is not separated from repository ownership",
        ))
    if "applies only to the NemoClaw DLI course repository" not in str(
        target.get("classification_rule", "")
    ):
        findings.append(finding(
            "toe-classification", CONTROL_REGISTER,
            "course OSS classification is not explicitly bounded",
        ))
    if set(target.get("explicit_facts") or []) != REQUIRED_EXPLICIT_FACTS:
        findings.append(finding(
            "toe-explicit-facts", CONTROL_REGISTER,
            "current-state facts changed or are incomplete",
        ))
    if set(register.get("assessment_status_rules") or []) != EXPECTED_STATUS_RULES:
        findings.append(finding(
            "assessment-status-rules", CONTROL_REGISTER,
            "status precedence does not fail closed",
        ))

    themes = register.get("themes") or []
    theme_ids = [row.get("id") for row in themes if isinstance(row, dict)]
    if len(theme_ids) != len(set(theme_ids)):
        findings.append(finding("theme-duplicate", CONTROL_REGISTER, "control theme IDs repeat"))
    for theme_id in sorted(REQUIRED_THEME_IDS - set(theme_ids)):
        findings.append(finding("theme-missing", CONTROL_REGISTER, f"missing control theme: {theme_id}"))
    for index, row in enumerate(themes):
        if not isinstance(row, dict):
            findings.append(finding("theme-shape", CONTROL_REGISTER, f"theme {index} is not an object"))
            continue
        theme_id = str(row.get("id", f"index-{index}"))
        for field in sorted(REQUIRED_THEME_FIELDS - set(row)):
            findings.append(finding(
                "theme-field", CONTROL_REGISTER, f"{theme_id} is missing {field}",
            ))
        if row.get("state") not in ALLOWED_THEME_STATES:
            findings.append(finding(
                "theme-state", CONTROL_REGISTER,
                f"{theme_id} has unsupported state {row.get('state')}",
            ))
        for field in ("title", "owner", "current_control", "future_candidate", "trigger", "verification"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                findings.append(finding(
                    "theme-value", CONTROL_REGISTER, f"{theme_id} has an empty {field}",
                ))
        future = str(row.get("future_candidate", ""))
        if not future.startswith(("NOT IMPLEMENTED. ", "NO LIVE EVIDENCE. ")):
            findings.append(finding(
                "future-status-prefix", CONTROL_REGISTER,
                f"{theme_id} future candidate is not explicitly non-current",
            ))
        if row.get("state") == "external-evidence-required" and not future.startswith(
            "NO LIVE EVIDENCE. "
        ):
            findings.append(finding(
                "external-future-evidence", CONTROL_REGISTER,
                f"{theme_id} lacks the external-evidence warning",
            ))
        current = str(row.get("current_control", ""))
        if row.get("state") == "external-evidence-required" and re.search(
            r"\b(?:operator|service|runtime|relay) (?:enforces?|verifies?|guarantees?|ensures?)\b",
            current,
            re.IGNORECASE,
        ):
            findings.append(finding(
                "unsupported-external-control", CONTROL_REGISTER,
                f"{theme_id} claims an unevidenced live external control",
            ))
        if theme_id == "artifact-integrity" and re.search(
            r"\b(?:signed|signature|attestation|provenance)\b",
            current,
            re.IGNORECASE,
        ):
            findings.append(finding(
                "unsupported-signing-claim", CONTROL_REGISTER,
                "artifact signing or provenance appears as a current control",
            ))
        evidence = row.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            findings.append(finding(
                "theme-evidence", CONTROL_REGISTER, f"{theme_id} has no repository evidence",
            ))
        else:
            for path in evidence:
                if not isinstance(path, str) or not (ROOT / path).exists():
                    findings.append(finding(
                        "theme-evidence-path", CONTROL_REGISTER,
                        f"{theme_id} evidence path does not resolve: {path}",
                    ))

    for path in ("docs/security-design.md", DISPOSITION):
        text = read(path, overrides)
        for phrase in (
            "secure course delivery architecture",
            "hardened CI/CD pipeline",
            "hardened pipeline",
            "immutable, verified build artifact",
        ):
            if phrase.casefold() in text.casefold():
                findings.append(finding(
                    "unqualified-security-claim", path,
                    f"remove or qualify generated-style overclaim: {phrase}",
                ))

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


def self_test() -> tuple[int, int, list[str]]:
    baseline = audit()
    if baseline:
        failures = [
            f"baseline is not clean: {item['code']} {item['path']} {item['detail']}"
            for item in baseline
        ]
        return 0, 0, failures
    tests: list[tuple[str, dict[str, str], str]] = []
    pages = read(".github/workflows/pages.yml", {})
    release = read(".github/workflows/release.yml", {})
    disposition = read(DISPOSITION, {})
    playbook = read("docs/release_playbook.md", {})
    product_design = read("docs/product-design.md", {})
    security_design = read("docs/security-design.md", {})
    register = json.loads(read(CONTROL_REGISTER, {}))

    def mutated_register() -> dict:
        return json.loads(json.dumps(register))

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
    tests.append((
        "course versus product scope",
        {"docs/product-design.md": product_design.replace(
            "The Type I subject is only the DLI course repository",
            "The Type I subject is the complete NemoClaw product",
            1,
        )},
        "missing-control-token",
    ))
    tests.append((
        "aggregate generated-review reconciliation",
        {DISPOSITION: disposition.replace(
            "Do not version private review rows one-to-one",
            "Private review rows are copied into the public repository",
            1,
        )},
        "missing-control-token",
    ))
    tests.append((
        "submission browser fact",
        {"docs/security-design.md": security_design.replace(
            "bearer credentials are JavaScript-readable",
            "browser storage is not used for credentials",
            1,
        )},
        "missing-control-token",
    ))
    value = mutated_register()
    value["themes"] = [row for row in value["themes"] if row["id"] != "relay-boundary"]
    tests.append(("missing aggregate theme", {CONTROL_REGISTER: json.dumps(value)}, "theme-missing"))
    value = mutated_register()
    value["themes"][0]["state"] = "mitigated"
    tests.append(("blanket mitigated state", {CONTROL_REGISTER: json.dumps(value)}, "theme-state"))
    value = mutated_register()
    del value["themes"][0]["verification"]
    tests.append(("missing verification field", {CONTROL_REGISTER: json.dumps(value)}, "theme-field"))
    value = mutated_register()
    value["target_of_evaluation"]["owned"].append("NemoClaw runtime")
    tests.append(("external component claimed as owned", {CONTROL_REGISTER: json.dumps(value)}, "toe-owned-scope"))
    value = mutated_register()
    value["target_of_evaluation"]["external_dependencies"].remove("model service")
    tests.append(("external boundary narrowed", {CONTROL_REGISTER: json.dumps(value)}, "toe-external-scope"))
    value = mutated_register()
    value["themes"][0]["evidence"] = ["docs/does-not-exist.md"]
    tests.append(("unresolvable theme evidence", {CONTROL_REGISTER: json.dumps(value)}, "theme-evidence-path"))
    value = mutated_register()
    value["target_of_evaluation"]["ownership_rule"] = "Every data-flow participant is owned."
    tests.append(("ownership conflation", {CONTROL_REGISTER: json.dumps(value)}, "toe-ownership-rule"))
    value = mutated_register()
    value["assessment_status_rules"] = value["assessment_status_rules"][1:]
    tests.append((
        "missing conservative status precedence",
        {CONTROL_REGISTER: json.dumps(value)},
        "assessment-status-rules",
    ))
    value = mutated_register()
    value["target_of_evaluation"]["explicit_facts"][0] = (
        "Course source is proprietary and the build runner holds pre-release secrets."
    )
    tests.append((
        "invented source confidentiality objective",
        {CONTROL_REGISTER: json.dumps(value)},
        "toe-explicit-facts",
    ))
    value = mutated_register()
    value["themes"][0]["future_candidate"] = "Verify every live source-host control."
    tests.append((
        "future work presented as current",
        {CONTROL_REGISTER: json.dumps(value)},
        "future-status-prefix",
    ))
    value = mutated_register()
    relay = next(row for row in value["themes"] if row["id"] == "relay-boundary")
    relay["future_candidate"] = "NOT IMPLEMENTED. Add relay limits later."
    tests.append((
        "external control without live-evidence warning",
        {CONTROL_REGISTER: json.dumps(value)},
        "external-future-evidence",
    ))
    value = mutated_register()
    relay = next(row for row in value["themes"] if row["id"] == "relay-boundary")
    relay["current_control"] = "The relay enforces destination allowlists and request quotas."
    tests.append((
        "unevidenced relay control",
        {CONTROL_REGISTER: json.dumps(value)},
        "unsupported-external-control",
    ))
    value = mutated_register()
    artifact = next(row for row in value["themes"] if row["id"] == "artifact-integrity")
    artifact["current_control"] = "Signed provenance attestation verifies every artifact."
    tests.append((
        "unevidenced signing claim",
        {CONTROL_REGISTER: json.dumps(value)},
        "unsupported-signing-claim",
    ))
    tests.append((
        "unqualified secure architecture",
        {"docs/security-design.md": security_design + "\nThis is a secure course delivery architecture.\n"},
        "unqualified-security-claim",
    ))
    tests.append((
        "blanket mitigation claim",
        {DISPOSITION: disposition + "\nStatus: mitigated\n"},
        "false-mitigation",
    ))
    passed = 0
    failures: list[str] = []
    for label, overrides, expected in tests:
        codes = {item["code"] for item in audit(text_overrides=overrides)}
        if expected in codes:
            passed += 1
        else:
            failures.append(f"mutation escaped: {label}; got {sorted(codes)}")
    return passed, len(tests), failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        passed, total, failures = self_test()
        print(f"threat control self-test: {passed}/{total} mutation detectors passed")
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
