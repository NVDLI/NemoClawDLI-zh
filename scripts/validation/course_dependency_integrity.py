#!/usr/bin/env python3
"""Validate exact, same-origin student-browser packages and their public inventory."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

for _p in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
    if (_p / "scripts" / "_bootstrap.py").exists():
        sys.path.insert(0, str(_p / "scripts"))
        break
from _bootstrap import find_repo_root

ROOT = find_repo_root(Path(__file__).resolve())
COURSE = ROOT / "web" / "nemoclaw"
VENDOR = COURSE / "vendor"
MANIFEST = VENDOR / "browser-dependencies.json"
LOCK = ROOT / "scripts" / "browser-vendor" / "package-lock.json"
PACKAGE = ROOT / "scripts" / "browser-vendor" / "package.json"
DASHBOARD = COURSE / "dependencies.html"
PACKAGE_HOSTS = {"cdn.jsdelivr.net", "cdnjs.cloudflare.com", "esm.sh", "unpkg.com"}
SOURCE_SUFFIXES = {".css", ".html", ".js", ".mjs"}
EXCLUDED_PARTS = {"vendor", "standalone", "mats"}
VENDOR_REF_RE = re.compile(r"(?<![A-Za-z0-9_-])(?:\.\.?/)?vendor/([A-Za-z0-9_.-]+)")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runtime_sources() -> list[Path]:
    # Walk source trees directly so a new, not-yet-staged learner page is checked
    # before commit. The generator uses the same working-tree boundary.
    return sorted(
        path
        for base in (ROOT / "web", ROOT / "i18n")
        if base.is_dir()
        for path in base.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SOURCE_SUFFIXES
        and not EXCLUDED_PARTS.intersection(path.parts)
    )


def inventory_size() -> int:
    data = json.loads(MANIFEST.read_text())
    return 1 + sum(len(data.get(key) or []) for key in ("packages", "assets", "legal_notices"))


def source_references(files: list[Path], asset: str,
                      overrides: dict[str, str]) -> list[dict[str, object]]:
    refs = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        text = overrides.get(rel, path.read_text(encoding="utf-8", errors="replace"))
        for line_number, line in enumerate(text.splitlines(), 1):
            if asset in line:
                refs.append({"source": rel, "line": line_number})
    return sorted(refs, key=lambda row: (str(row["source"]), int(row["line"])))


def audit(*, manifest_data: dict | None = None,
          text_overrides: dict[str, str] | None = None) -> list[str]:
    findings: list[str] = []
    overrides = text_overrides or {}
    try:
        manifest = manifest_data if manifest_data is not None else json.loads(MANIFEST.read_text())
        lock = json.loads(LOCK.read_text())
        package = json.loads(PACKAGE.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [f"dependency inventory cannot be read: {exc}"]

    if manifest.get("schema") != "nemoclaw-browser-dependencies/1":
        findings.append("manifest schema is not nemoclaw-browser-dependencies/1")
    if manifest.get("delivery") != "same-origin-vendored":
        findings.append("browser dependency delivery must remain same-origin-vendored")
    if manifest.get("lock_sha256") != sha256(LOCK):
        findings.append("manifest lock_sha256 does not match package-lock.json")

    direct = package.get("dependencies") or {}
    locked = lock.get("packages") or {}
    seen_packages: set[tuple[str, str]] = set()
    for row in manifest.get("packages") or []:
        name, version = row.get("name"), row.get("version")
        key = (str(name), str(version))
        if key in seen_packages:
            findings.append(f"duplicate package row: {name}@{version}")
        seen_packages.add(key)
        if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", str(version)):
            findings.append(f"package version is not exact: {name}@{version}")
        lock_rows = [value for path, value in locked.items()
                     if path.endswith("node_modules/" + str(name)) and value.get("version") == version]
        if not lock_rows:
            findings.append(f"package missing from exact lock: {name}@{version}")
        if row.get("direct") and direct.get(name) != version:
            findings.append(f"direct package differs from package.json: {name}@{version}")
        if row.get("package_url") != f"https://www.npmjs.com/package/{name}":
            findings.append(f"package URL is not the canonical public npm page: {name}@{version}")
        license_path = VENDOR / str(row.get("license_file", ""))
        if not row.get("license") or not license_path.is_file() or not license_path.read_text(errors="replace").strip():
            findings.append(f"package lacks vendored license evidence: {name}@{version}")

    files = runtime_sources()
    asset_names = {row.get("file") for row in manifest.get("assets") or []}
    for row in manifest.get("assets") or []:
        name = row.get("file")
        path = VENDOR / str(name)
        if not path.is_file():
            findings.append(f"vendored browser asset is missing: {name}")
            continue
        if row.get("sha256") != sha256(path) or row.get("bytes") != path.stat().st_size:
            findings.append(f"vendored browser asset hash or size drifted: {name}")
        actual_refs = source_references(files, str(name), overrides)
        if row.get("references") != actual_refs:
            findings.append(f"source-reference inventory drifted: {name}")
        if not actual_refs:
            findings.append(f"vendored browser asset has no runtime reference: {name}")

    for row in manifest.get("legal_notices") or []:
        name = row.get("file")
        path = VENDOR / str(name)
        if not path.is_file() or row.get("sha256") != sha256(path) or row.get("bytes") != path.stat().st_size:
            findings.append(f"bundle legal-notice hash or size drifted: {name}")

    sbom_row = manifest.get("sbom") or {}
    sbom_path = VENDOR / str(sbom_row.get("file", ""))
    if (not sbom_path.is_file() or sbom_row.get("sha256") != sha256(sbom_path)
            or sbom_row.get("bytes") != sbom_path.stat().st_size):
        findings.append("browser CycloneDX SBOM hash or size drifted")
    else:
        try:
            sbom = json.loads(sbom_path.read_text())
            components = {(row.get("name"), row.get("version")) for row in sbom.get("components") or []}
            expected = {(row.get("name"), row.get("version")) for row in manifest.get("packages") or []}
            if sbom.get("bomFormat") != "CycloneDX" or components != expected:
                findings.append("browser CycloneDX SBOM differs from the shipped package inventory")
        except json.JSONDecodeError:
            findings.append("browser CycloneDX SBOM is not valid JSON")

    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        text = overrides.get(rel, path.read_text(encoding="utf-8", errors="replace"))
        for url in re.findall(r"https://[^\s\"'<>`)]+", text):
            if urlsplit(url.rstrip(".,;:]}")).hostname in PACKAGE_HOSTS:
                findings.append(f"runtime still pulls a package CDN: {rel}: {url}")
        for target in VENDOR_REF_RE.findall(text):
            if target not in asset_names and target not in {"browser-dependencies.json", "browser-sbom.cdx.json"}:
                findings.append(f"runtime references unmanifested vendor asset: {rel}: {target}")

    dashboard = overrides.get(
        "web/nemoclaw/dependencies.html",
        DASHBOARD.read_text(encoding="utf-8", errors="replace") if DASHBOARD.is_file() else "",
    )
    for token in (
        "Browser dependency inventory", "vendor/browser-dependencies.json",
        "package-table", "asset-table", "legal-list",
    ):
        if token not in dashboard:
            findings.append(f"dependency dashboard is missing required token: {token}")
    return findings


def self_test() -> tuple[int, int, list[str]]:
    baseline = audit()
    if baseline:
        return 0, 8, ["baseline is not clean: " + item for item in baseline]
    manifest = json.loads(MANIFEST.read_text())
    tests: list[tuple[str, dict, dict[str, str], str]] = []

    changed = copy.deepcopy(manifest)
    changed["assets"][0]["sha256"] = "0" * 64
    tests.append(("asset hash", changed, {}, "hash or size drifted"))
    changed = copy.deepcopy(manifest)
    changed["packages"][0]["version"] = "1"
    tests.append(("inexact version", changed, {}, "version is not exact"))
    changed = copy.deepcopy(manifest)
    changed["delivery"] = "public-cdn"
    tests.append(("delivery boundary", changed, {}, "same-origin-vendored"))
    changed = copy.deepcopy(manifest)
    changed["packages"][0]["package_url"] = "https://example.invalid/package"
    tests.append(("public package URL", changed, {}, "package URL is not the canonical public npm page"))
    sample = "web/nemoclaw/scripts/_chat.js"
    source = (ROOT / sample).read_text(encoding="utf-8")
    tests.append(("runtime CDN", manifest, {sample: source + '\n"https://cdn.jsdelivr.net/npm/demo@1/+esm";'},
                  "runtime still pulls a package CDN"))
    dashboard = DASHBOARD.read_text(encoding="utf-8")
    tests.append(("dashboard wiring", manifest,
                  {"web/nemoclaw/dependencies.html": dashboard.replace("vendor/browser-dependencies.json", "missing.json")},
                  "dashboard is missing required token"))

    failures = []
    for name, fixture, overrides, expected in tests:
        rows = audit(manifest_data=fixture, text_overrides=overrides)
        if not any(expected in row for row in rows):
            failures.append(f"{name}: expected {expected}; got {rows}")
    targets = VENDOR_REF_RE.findall(
        'scripts/browser-vendor/package.json <script src="vendor/runtime.js"></script>'
    )
    if targets != ["runtime.js"]:
        failures.append(f"vendor path boundary: got {targets}, expected ['runtime.js']")
    with tempfile.NamedTemporaryFile(dir=COURSE, prefix=".dependency-audit-", suffix=".js") as probe:
        probe_path = Path(probe.name)
        if probe_path not in runtime_sources():
            failures.append("working-tree discovery: untracked runtime source was not examined")
    total = len(tests) + 2
    return total - len(failures), total, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        passed, total, failures = self_test()
        print(f"course_dependency_integrity self-test: {passed}/{total} passed")
        for row in failures:
            print("  FAIL " + row)
        return 1 if failures else 0
    findings = audit()
    if findings:
        print("course_dependency_integrity: FAIL")
        print("\n".join("  - " + item for item in findings))
        return 1
    manifest = json.loads(MANIFEST.read_text())
    print(
        "course_dependency_integrity: OK "
        f"({len(manifest['packages'])} packages, {len(manifest['assets'])} same-origin assets)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
