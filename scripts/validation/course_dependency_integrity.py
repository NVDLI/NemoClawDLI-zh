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
CODEMIRROR_ENTRY = ROOT / "scripts" / "browser-vendor" / "codemirror-entry.js"
CI_CONFIG = ROOT / ".gitlab-ci.yml"
DASHBOARD = COURSE / "dependencies.html"
PACKAGE_HOSTS = {"cdn.jsdelivr.net", "cdnjs.cloudflare.com", "esm.sh", "unpkg.com"}
SOURCE_SUFFIXES = {".css", ".html", ".js", ".mjs"}
EXCLUDED_PARTS = {"vendor", "standalone", "mats"}
VENDOR_REF_RE = re.compile(r"(?<![A-Za-z0-9_-])(?:\.\.?/)?vendor/([A-Za-z0-9_.-]+)")
CODEMIRROR_MODE_RE = re.compile(r'import\s+["\']codemirror/mode/([^/]+)/[^"\']+["\']\s*;')
CODEMIRROR_MARKDOWN_RE = re.compile(r"codemirror(?:/[^/\s\"']+)?/mode/markdown/", re.IGNORECASE)
CODEMIRROR_VERSION_REF_RE = re.compile(
    r"codemirror(?:-monokai)?(?:/|@|-)(\d+\.\d+\.\d+)", re.IGNORECASE
)
EXTERNAL_CODEMIRROR_URL_RE = re.compile(r"https://[^\"';\s]*codemirror[^\"';\s]+", re.IGNORECASE)
CODEMIRROR_CDN_RE = re.compile(
    r"https://cdn\.jsdelivr\.net/npm/codemirror@(\d+\.\d+\.\d+)/([^\"';\s]+)", re.IGNORECASE
)
REVIEWED_CODEMIRROR_MODES = {"css", "htmlmixed", "javascript", "python", "xml"}
EXACT_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.-]+)?")
MINIMUM_BROWSER_PACKAGE_VERSIONS = {"codemirror": (5, 65, 21)}
CODEMIRROR_CDN_SRI = {
    "lib/codemirror.min.css": "sha384-5051nNF3/zZWmqR8xLbnEemOtE5aiJ1EQkEq9vNXYOnGP/3BgYGknkOKuic0TtLg",
    "theme/monokai.min.css": "sha384-quTpEUSU3EctO0q/LujapVfLi1W2HzJSa8AYlphQqdUVu4xv3L0FpJM4qiGlFtSG",
    "lib/codemirror.min.js": "sha384-0g/X0mKSHhn466L6gmwQ9T6fCIeXJnwNSxvvJ0BdQtCDDS0FexoLx+DrxcZEZzEg",
    "mode/javascript/javascript.min.js": "sha384-eFWmno3frUPpxd9HY3/D+mG053G//m0lzptejdowRL0e0ZDemrkiin1+tvD+6y3K",
    "mode/python/python.min.js": "sha384-7b0bBxjCy1nOeHyF0JF7apxjgAqjgO0oIMT+YbJdWCD1XN2yyuH+Bszrto8jH/+8",
    "mode/xml/xml.min.js": "sha384-5YtiW1wbHNoTba5dLtwu12JsaSHlEJUhEIrc2p2mUhj8Qu/IiT1fwoBFF5H6Cnrq",
    "mode/css/css.min.js": "sha384-vp9dw4ad8wEEvNC9LEcNNyB7wbOKO5JDeyB7h2E/VVlVWUB1YluxFkQ9dPaM2gKI",
    "mode/htmlmixed/htmlmixed.min.js": "sha384-oltMhhOH7bsTEI6KaMECnU25oNNADzTcMN3UpgnrG9wAE5OLkvjSZYzQm7LGm7DA",
}


def is_transient_generated_source(path: Path) -> bool:
    """Exclude the short-lived ESM shim created by concurrent figure checks."""
    return path.name == ".figcheck_shared.mjs" or (
        path.name.startswith(".figcheck_shared-") and path.suffix == ".mjs"
    )


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
        and not is_transient_generated_source(path)
        and not EXCLUDED_PARTS.intersection(path.parts)
    )


def browser_projection_sources() -> list[Path]:
    """Return browser sources, including tracked standalone projections."""
    return sorted(
        path
        for base in (ROOT / "web", ROOT / "i18n")
        if base.is_dir()
        for path in base.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SOURCE_SUFFIXES
        and not is_transient_generated_source(path)
        and not {"vendor", "mats"}.intersection(path.parts)
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
    entry_rel = CODEMIRROR_ENTRY.relative_to(ROOT).as_posix()
    entry = overrides.get(
        entry_rel,
        CODEMIRROR_ENTRY.read_text(encoding="utf-8", errors="replace")
        if CODEMIRROR_ENTRY.is_file() else "",
    )
    modes = set(CODEMIRROR_MODE_RE.findall(entry))
    unexpected_modes = sorted(modes - REVIEWED_CODEMIRROR_MODES)
    missing_modes = sorted(REVIEWED_CODEMIRROR_MODES - modes)
    if unexpected_modes:
        findings.append("unreviewed CodeMirror modes: " + ", ".join(unexpected_modes))
    if missing_modes:
        findings.append("reviewed CodeMirror modes missing from bundle entry: " + ", ".join(missing_modes))
    ci_text = overrides.get(".gitlab-ci.yml", CI_CONFIG.read_text(encoding="utf-8"))
    ci_job = re.search(r"(?ms)^security_browser_sca:\s*\n(.*?)(?=^\S[^\n]*:\s*(?:$|&)|\Z)", ci_text)
    ci_tokens = (
        "npm audit --prefix scripts/browser-vendor",
        "--package-lock-only",
        "--audit-level=moderate",
        "browser-npm-audit.json",
        'CI_PIPELINE_SOURCE == "merge_request_event"',
        "scripts/browser-vendor/package-lock.json",
        "scripts/validation/course_dependency_integrity.py",
    )
    if not ci_job:
        findings.append("GitLab CI is missing the security_browser_sca job")
    else:
        missing_ci = [token for token in ci_tokens if token not in ci_job.group(1)]
        if missing_ci:
            findings.append("security_browser_sca is incomplete: " + ", ".join(missing_ci))
    for path in browser_projection_sources():
        rel = path.relative_to(ROOT).as_posix()
        text = overrides.get(rel, path.read_text(encoding="utf-8", errors="replace"))
        if CODEMIRROR_MARKDOWN_RE.search(text):
            findings.append(f"CodeMirror Markdown mode is outside the reviewed browser surface: {rel}")
        minimum = MINIMUM_BROWSER_PACKAGE_VERSIONS["codemirror"]
        for version in sorted(set(CODEMIRROR_VERSION_REF_RE.findall(text))):
            if tuple(int(part) for part in version.split(".")) < minimum:
                floor = ".".join(str(part) for part in minimum)
                findings.append(f"browser projection uses CodeMirror below supported floor: {rel}: {version} < {floor}")
        for url in EXTERNAL_CODEMIRROR_URL_RE.findall(text):
            if not CODEMIRROR_CDN_RE.fullmatch(url):
                findings.append(f"standalone projection uses an unreviewed CodeMirror CDN URL: {rel}: {url}")
        for match in CODEMIRROR_CDN_RE.finditer(text):
            asset = match.group(2)
            expected_sri = CODEMIRROR_CDN_SRI.get(asset)
            evidence = text[match.end():match.end() + 300]
            if not expected_sri:
                findings.append(f"standalone projection uses an unreviewed CodeMirror CDN asset: {rel}: {asset}")
            elif expected_sri not in evidence or not re.search(r"crossorigin|crossOrigin", evidence):
                findings.append(f"standalone CodeMirror asset lacks pinned integrity: {rel}: {asset}")
    seen_packages: set[tuple[str, str]] = set()
    for row in manifest.get("packages") or []:
        name, version = row.get("name"), row.get("version")
        key = (str(name), str(version))
        if key in seen_packages:
            findings.append(f"duplicate package row: {name}@{version}")
        seen_packages.add(key)
        version_match = EXACT_VERSION_RE.fullmatch(str(version))
        if not version_match:
            findings.append(f"package version is not exact: {name}@{version}")
        elif name in MINIMUM_BROWSER_PACKAGE_VERSIONS:
            current = tuple(int(part) for part in version_match.groups())
            minimum = MINIMUM_BROWSER_PACKAGE_VERSIONS[name]
            if current < minimum:
                floor = ".".join(str(part) for part in minimum)
                findings.append(f"package is below supported security floor: {name}@{version}; require >= {floor}")
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
        return 0, 15, ["baseline is not clean: " + item for item in baseline]
    manifest = json.loads(MANIFEST.read_text())
    tests: list[tuple[str, dict, dict[str, str], str]] = []

    changed = copy.deepcopy(manifest)
    changed["assets"][0]["sha256"] = "0" * 64
    tests.append(("asset hash", changed, {}, "hash or size drifted"))
    changed = copy.deepcopy(manifest)
    changed["packages"][0]["version"] = "1"
    tests.append(("inexact version", changed, {}, "version is not exact"))
    changed = copy.deepcopy(manifest)
    codemirror_row = next(row for row in changed["packages"] if row["name"] == "codemirror")
    codemirror_row["version"] = "5.65.16"
    tests.append(("browser security floor", changed, {}, "below supported security floor"))
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
    entry_rel = CODEMIRROR_ENTRY.relative_to(ROOT).as_posix()
    entry = CODEMIRROR_ENTRY.read_text(encoding="utf-8")
    tests.append(("editor mode allowlist", manifest,
                  {entry_rel: entry.replace("mode/xml/xml.js", "mode/markdown/markdown.js")},
                  "unreviewed CodeMirror modes"))
    sample = "web/nemoclaw/scripts/_chat.js"
    source = (ROOT / sample).read_text(encoding="utf-8")
    tests.append(("standalone editor boundary", manifest,
                  {sample: source + '\nimport "codemirror/mode/markdown/markdown.js";'},
                  "Markdown mode is outside the reviewed browser surface"))
    sample = "web/nemoclaw/01a-loop.html"
    source = (ROOT / sample).read_text(encoding="utf-8")
    tests.append(("browser projection security floor", manifest,
                  {sample: source.replace("5.65.21", "5.65.16")},
                  "browser projection uses CodeMirror below supported floor"))
    sample = "web/nemoclaw/standalone/studio.html"
    source = (ROOT / sample).read_text(encoding="utf-8")
    tests.append(("standalone CodeMirror integrity", manifest,
                  {sample: source.replace(CODEMIRROR_CDN_SRI["lib/codemirror.min.js"], "sha384-invalid")},
                  "standalone CodeMirror asset lacks pinned integrity"))
    tests.append(("standalone CodeMirror host", manifest,
                  {sample: source.replace("cdn.jsdelivr.net/npm/codemirror", "cdn.example.test/codemirror")},
                  "standalone projection uses an unreviewed CodeMirror CDN URL"))
    ci_source = CI_CONFIG.read_text(encoding="utf-8")
    tests.append(("browser SCA CI wiring", manifest,
                  {".gitlab-ci.yml": ci_source.replace("security_browser_sca:", "security_browser_scan:", 1)},
                  "GitLab CI is missing the security_browser_sca job"))

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
    with tempfile.NamedTemporaryFile(
        dir=COURSE / "scripts", prefix=".figcheck_shared-", suffix=".mjs"
    ) as probe:
        probe_path = Path(probe.name)
        if probe_path in browser_projection_sources():
            failures.append("working-tree discovery: transient figure shim was examined")
    total = len(tests) + 3
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
