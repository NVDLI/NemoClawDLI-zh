#!/usr/bin/env python3
"""Build and verify immutable links between SBOMs, license appendices, and inventory scope."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import tempfile
from pathlib import Path

import render_sbom_license_inventory as license_inventory


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "scripts/compliance/docs/sbom_evidence.json"
INVENTORY = ROOT / "THIRD_PARTY_LICENSES.md"
COMMIT = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
ALLOWED_STATES = {"available", "ci-generated", "conditional"}
ALLOWED_DISTRIBUTION = {"distributed", "not-distributed", "conditional-release"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def license_summary(components: list[dict]) -> dict[str, int]:
    summary = {"spdx": 0, "named": 0, "missing": 0}
    for component in components:
        licenses = component.get("licenses") or []
        if not licenses:
            summary["missing"] += 1
        elif any((item.get("license") or {}).get("id") or item.get("expression") for item in licenses):
            summary["spdx"] += 1
        else:
            summary["named"] += 1
    return summary


def load_sbom(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("bomFormat") != "CycloneDX" or not isinstance(document.get("components"), list):
        raise ValueError("SBOM must be CycloneDX JSON with a components array")
    return document


def inventory_noassertion() -> set[tuple[str, str]]:
    text = INVENTORY.read_text(encoding="utf-8")
    marker = "## Direct container, runtime, and operating-system declarations"
    if marker not in text:
        return set()
    body = text.split(marker, 1)[1].split("\n## ", 1)[0]
    rows: set[tuple[str, str]] = set()
    for line in body.splitlines():
        if not line.startswith("|") or "NOASSERTION" not in line:
            continue
        columns = [value.strip() for value in line.strip("|").split("|")]
        if len(columns) >= 4 and columns[0] != "Scope" and columns[3] == "NOASSERTION":
            rows.add((columns[1], columns[2]))
    return rows


def resolve_catalog_path(href: str) -> Path:
    path = (CATALOG.parent / href).resolve()
    if ROOT.resolve() not in path.parents:
        raise ValueError(f"SBOM href escapes the repository: {href}")
    return path


def audit_catalog(document: dict | None = None) -> list[str]:
    """Check the committed catalog against its linked files and inventory boundary."""
    findings: list[str] = []
    data = document if document is not None else json.loads(CATALOG.read_text(encoding="utf-8"))
    if data.get("schema") != "nemoclaw-sbom-evidence/1":
        findings.append("unexpected SBOM evidence schema")
    records = data.get("records")
    if not isinstance(records, list) or not records:
        return findings + ["SBOM evidence records must be a non-empty list"]
    ids = [record.get("id") for record in records if isinstance(record, dict)]
    if len(ids) != len(set(ids)) or any(not value for value in ids):
        findings.append("SBOM evidence record IDs must be present and unique")

    for record in records:
        if not isinstance(record, dict):
            findings.append("SBOM evidence record is not an object")
            continue
        label = record.get("id", "<missing>")
        if record.get("state") not in ALLOWED_STATES:
            findings.append(f"{label}: unsupported evidence state")
        if record.get("distribution") not in ALLOWED_DISTRIBUTION:
            findings.append(f"{label}: unsupported distribution state")
        if not record.get("selectors"):
            findings.append(f"{label}: no inventory selectors")

        if record.get("state") == "available":
            sbom = record.get("sbom") or {}
            href = sbom.get("href")
            try:
                path = resolve_catalog_path(href) if href else None
            except ValueError as error:
                findings.append(f"{label}: {error}")
                path = None

            if not path or not path.is_file():
                findings.append(f"{label}: linked SBOM is missing")
                continue
            try:
                source = load_sbom(path)
            except (ValueError, json.JSONDecodeError) as error:
                findings.append(f"{label}: invalid linked SBOM: {error}")
                continue

            expected = {
                "sha256": digest(path),
                "bytes": path.stat().st_size,
                "component_count": len(source["components"]),
                "license_metadata": license_summary(source["components"]),
            }
            for key, value in expected.items():
                if sbom.get(key) != value:
                    findings.append(f"{label}: linked SBOM {key} is stale")
        elif record.get("state") == "ci-generated":
            ci = record.get("ci") or {}
            for key in ("job", "sbom_artifact_path", "manifest_artifact_path", "appendix_artifact_path", "retention_days"):
                if not ci.get(key):
                    findings.append(f"{label}: CI evidence location lacks {key}")
        elif record.get("state") == "conditional":
            if record.get("distribution") != "not-distributed":
                findings.append(f"{label}: conditional inventory is currently distributed")
            if record.get("required_before_distribution") != "digest-bound-component-sbom":
                findings.append(f"{label}: distribution does not require a digest-bound component SBOM")

    conditional = next((record for record in records if record.get("id") == "local-authoring-image-boundary"), {})
    declared = {
        (str(item.get("component")), str(item.get("version")))
        for item in conditional.get("subjects", [])
        if isinstance(item, dict)
    }
    if declared != inventory_noassertion():
        findings.append("local-authoring NOASSERTION subjects do not match the checked inventory")
    return findings


def emit(args: argparse.Namespace) -> tuple[dict, int]:
    """Write one digest-bound evidence manifest and its license appendix."""
    if not COMMIT.fullmatch(args.source_commit):
        raise ValueError("source commit must be a full 40- or 64-character lowercase hexadecimal ID")
    document = load_sbom(args.sbom)
    sbom_sha = digest(args.sbom)
    artifact_id = args.artifact_id or f"{args.artifact_name}@sha256:{sbom_sha}"
    rendered, unresolved = license_inventory.render(args.sbom, artifact_id, args.inventory)
    args.appendix_out.parent.mkdir(parents=True, exist_ok=True)
    args.appendix_out.write_text(rendered, encoding="utf-8")
    record = {
        "id": args.record_id,
        "state": "available",
        "distribution": args.distribution,
        "description": args.description,
        "selectors": [{"category": category} for category in args.category],
        "artifact_id": artifact_id,
        "source_commit": args.source_commit,
        "sbom": {
            "href": args.sbom_href or args.sbom.name,
            "sha256": sbom_sha,
            "bytes": args.sbom.stat().st_size,
            "format": "CycloneDX",
            "spec_version": document.get("specVersion"),
            "component_count": len(document["components"]),
            "license_metadata": license_summary(document["components"]),
        },
        "license_appendix": {
            "href": args.appendix_href or args.appendix_out.name,
            "sha256": digest(args.appendix_out),
            "unresolved_count": unresolved,
        },
        "ci": {
            "job": args.ci_job,
            "pipeline_url": args.pipeline_url,
            "job_url": args.job_url,
            "retention_days": args.retention_days,
        },
    }
    output = {"schema": "nemoclaw-sbom-evidence/1", "records": [record]}
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output, unresolved


def compose_release_catalog(base_path: Path, generated_path: Path, browser_href: str) -> dict:
    """Replace transient declarations with the records shipped beside release SBOMs."""
    base = json.loads(base_path.read_text(encoding="utf-8"))
    generated = json.loads(generated_path.read_text(encoding="utf-8"))
    if base.get("schema") != "nemoclaw-sbom-evidence/1" or generated.get("schema") != base.get("schema"):
        raise ValueError("release catalog inputs must use nemoclaw-sbom-evidence/1")
    generated_records = generated.get("records") or []
    if len(generated_records) != 1 or generated_records[0].get("id") != "python-validation-environment":
        raise ValueError("generated release evidence must contain the Python validation record")
    output = copy.deepcopy(base)
    records = output.get("records") or []
    browser = next((record for record in records if record.get("id") == "browser-runtime"), None)
    if not browser or not browser.get("sbom"):
        raise ValueError("base catalog lacks browser runtime evidence")
    browser["sbom"]["href"] = browser_href
    python_index = next((index for index, record in enumerate(records)
                         if record.get("id") == "python-validation-environment"), None)
    if python_index is None:
        raise ValueError("base catalog lacks the Python evidence declaration")
    records[python_index] = generated_records[0]
    output["release_source_commit"] = generated_records[0].get("source_commit")
    return output


def self_test() -> list[str]:
    """Exercise linked-file drift, inventory coverage, emission, and release composition."""
    failures: list[str] = []
    clean = json.loads(CATALOG.read_text(encoding="utf-8"))
    if audit_catalog(clean):
        failures.append("clean evidence catalog rejected")
    mutations = []
    stale = copy.deepcopy(clean)
    stale["records"][0]["sbom"]["sha256"] = "0" * 64
    mutations.append(("linked SBOM digest", stale, "sha256 is stale"))
    incomplete = copy.deepcopy(clean)
    incomplete["records"][-1]["subjects"] = incomplete["records"][-1]["subjects"][:-1]
    mutations.append(("NOASSERTION coverage", incomplete, "subjects do not match"))
    for label, mutation, expected in mutations:
        if not any(expected in finding for finding in audit_catalog(mutation)):
            failures.append(f"mutation escaped: {label}")
    with tempfile.TemporaryDirectory(prefix="sbom-evidence-") as directory:
        root = Path(directory)
        sbom = root / "fixture.cdx.json"
        sbom.write_text(json.dumps({
            "bomFormat": "CycloneDX", "specVersion": "1.6",
            "components": [{"name": "fixture", "version": "1", "licenses": [{"license": {"id": "MIT"}}]}],
        }), encoding="utf-8")
        appendix = root / "licenses.md"
        manifest = root / "evidence.json"
        args = argparse.Namespace(
            source_commit="a" * 40, sbom=sbom, artifact_id=None, artifact_name="fixture",
            inventory=INVENTORY, appendix_out=appendix, manifest_out=manifest,
            record_id="python-validation-environment", distribution="not-distributed", description="fixture",
            category=["validation"], sbom_href=None, appendix_href=None, ci_job="fixture",
            pipeline_url="", job_url="",
            retention_days=30,
        )
        emitted, unresolved = emit(args)
        if unresolved or emitted["records"][0]["sbom"]["sha256"] != digest(sbom):
            failures.append("emitted evidence does not bind the fixture SBOM")
        release = compose_release_catalog(CATALOG, manifest, "nemoclaw-v1.0.0.browser.cdx.json")
        release_records = {record["id"]: record for record in release["records"]}
        if release_records["browser-runtime"]["sbom"]["href"] != "nemoclaw-v1.0.0.browser.cdx.json":
            failures.append("release catalog does not link the versioned browser SBOM")
        if release_records["python-validation-environment"]["state"] != "available":
            failures.append("release catalog does not replace the transient Python declaration")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--compose-release-catalog", action="store_true")
    parser.add_argument("--base-catalog", type=Path, default=CATALOG)
    parser.add_argument("--generated-manifest", type=Path)
    parser.add_argument("--browser-href")
    parser.add_argument("--release-catalog-out", type=Path)
    parser.add_argument("--sbom", type=Path)
    parser.add_argument("--artifact-name")
    parser.add_argument("--artifact-id")
    parser.add_argument("--record-id")
    parser.add_argument("--description", default="CI-generated SBOM evidence")
    parser.add_argument("--distribution", choices=sorted(ALLOWED_DISTRIBUTION))
    parser.add_argument("--category", action="append", choices=("vendored", "build-input", "validation", "local-authoring"))
    parser.add_argument("--source-commit")
    parser.add_argument("--ci-job")
    parser.add_argument("--pipeline-url", default="")
    parser.add_argument("--job-url", default="")
    parser.add_argument("--retention-days", type=int, default=30)
    parser.add_argument("--sbom-href")
    parser.add_argument("--appendix-href")
    parser.add_argument("--appendix-out", type=Path)
    parser.add_argument("--manifest-out", type=Path)
    parser.add_argument("--inventory", type=Path, default=INVENTORY)
    parser.add_argument("--allow-unresolved", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        failures = self_test()
        print("SBOM evidence self-test: " + ("FAIL" if failures else "PASS"))
        for failure in failures:
            print(f"  {failure}")
        return 1 if failures else 0

    if args.check:
        findings = audit_catalog()
        print("SBOM evidence catalog: " + (f"FAIL ({len(findings)})" if findings else "PASS"))
        for finding in findings:
            print(f"  {finding}")
        return 1 if findings else 0

    if args.compose_release_catalog:
        if not args.generated_manifest or not args.browser_href or not args.release_catalog_out:
            parser.error("release catalog composition requires --generated-manifest, --browser-href, and --release-catalog-out")
        try:
            output = compose_release_catalog(args.base_catalog, args.generated_manifest, args.browser_href)
        except (ValueError, json.JSONDecodeError) as error:
            parser.error(str(error))
        args.release_catalog_out.parent.mkdir(parents=True, exist_ok=True)
        args.release_catalog_out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote release SBOM evidence catalog: {args.release_catalog_out}")
        return 0

    required = {
        "--sbom": args.sbom, "--artifact-name": args.artifact_name, "--record-id": args.record_id,
        "--distribution": args.distribution, "--category": args.category, "--source-commit": args.source_commit,
        "--ci-job": args.ci_job, "--appendix-out": args.appendix_out, "--manifest-out": args.manifest_out,
    }
    missing = [flag for flag, value in required.items() if not value]
    if missing:
        parser.error("evidence emission requires " + ", ".join(missing))
    try:
        _output, unresolved = emit(args)
    except (ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(f"wrote {args.manifest_out} and {args.appendix_out}: unresolved={unresolved}")
    return 0 if args.allow_unresolved or unresolved == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
