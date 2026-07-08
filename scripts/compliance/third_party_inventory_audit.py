#!/usr/bin/env python3
"""Keep the static third-party Markdown inventory aligned with repository inputs."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INVENTORY = "THIRD_PARTY_LICENSES.md"
RUNBOOK = "scripts/compliance/docs/sbom_generation.md"
PYTHON_LOCKS = (
    "workspace/requirements.lock",
    "scripts/materials/requirements.lock",
    "scripts/security/requirements-sca.lock",
    "cpu/services/sandbox_admin/requirements.txt",
)
PROVENANCE = (
    ("web/nemoclaw/assets", "web/nemoclaw/assets/SKILL.html", ("figures", "assets")),
    ("web/nemoclaw/mats", "web/nemoclaw/mats/SKILL.html", ("mats", "figures", "assets")),
)
REQUIRED_CONTAINER_FACTS = (
    "nvcr.io/nvidia/cuda | 12.8.1-cudnn-devel-ubuntu22.04 | NOASSERTION",
    "ghcr.io/nvidia/openshell/cluster | 0.0.8 | NOASSERTION",
    "ghcr.io/nvidia/openshell-community/sandboxes/base | latest | NOASSERTION",
    "openclaw | 2026.5.28 | MIT",
    "Open Policy Agent | 1.4.2 | Apache-2.0",
    "Exact transitive operating-system and container-layer packages are build outputs",
)
REQUIRED_LLM_PINS = (
    "fastapi==0.138.2",
    "starlette==1.3.1",
    "uvicorn[standard]==0.49.0",
    "httpx==0.28.1",
    "pydantic==2.13.4",
    "protobuf==5.29.6",
    "opentelemetry-api==1.34.1",
    "opentelemetry-sdk==1.34.1",
    "opentelemetry-exporter-otlp-proto-grpc==1.34.1",
)
REQUIRED_DISTRIBUTION_LINES = (
    'cp "$T1/LICENSE" "$OUT/LICENSE"',
    'cp "$T1/THIRD_PARTY_LICENSES.md" "$OUT/THIRD_PARTY_LICENSES.md"',
)
REQUIRED_EXPLANATIONS = (
    "## Reproducing license-evidence acquisition",
    "scripts/compliance/docs/sbom_generation.md",
    "Generated SBOM bodies are attached to the review record rather than committed here.",
    "`argparse@2.0.1` is a JavaScript npm package used transitively by `js-yaml@5.2.1`.",
    "No package row in this inventory declares GPL.",
    "`LGPL-2.0-or-later` tooling entry",
    "A mixed container image or operating-system layer does not have one honest aggregate SPDX license.",
    "exact package/version static fallback",
)
REQUIRED_RUNBOOK_TEXT = (
    "# SBOM generation and attachment runbook",
    "The static course release does not distribute the local-authoring container images.",
    "npm view <name>@<version> license dist.integrity repository --json",
    "https://pypi.org/pypi/<normalized-name>/<version>/json",
    "anchore/syft:v1.44.0 scan dir:/src",
    "IMAGE=<registry>/<repository>@sha256:<64-hex-digest>",
    "Those extractors acquire content",
    "scripts/compliance/render_sbom_license_inventory.py",
    "browser-runtime.cdx.json",
    "python-env.cdx.json",
    "source-tree.cdx.json",
    "source-tree.spdx.json",
)


def read(path: str, overrides: dict[str, str]) -> str:
    return overrides.get(path, (ROOT / path).read_text(encoding="utf-8"))


def section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    if marker not in text:
        return ""
    body = text.split(marker, 1)[1]
    return body.split("\n## ", 1)[0]


def rows(body: str) -> list[list[str]]:
    parsed = []
    for line in body.splitlines():
        if not line.startswith("|") or set(line.replace("|", "").strip()) <= {"-"}:
            continue
        values = [value.strip() for value in line.strip("|").split("|")]
        if values and values[0] != "Scope" and values[0] != "Repository file":
            parsed.append(values)
    return parsed


def python_pins(text: str) -> set[tuple[str, str]]:
    found = set()
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].strip()
        match = re.match(r"^([A-Za-z0-9_.-]+)(?:\[[^]]+\])?==([^\s;]+)", line)
        if match:
            name = re.sub(r"[-_.]+", "-", match.group(1)).lower()
            found.add((name, match.group(2)))
    return found


def provenance(path: str, overrides: dict[str, str]) -> dict:
    match = re.search(
        r'<script[^>]+id=["\']provenance["\'][^>]*>(.*?)</script>',
        read(path, overrides),
        re.S,
    )
    return json.loads(match.group(1)) if match else {}


def audit(overrides: dict[str, str] | None = None) -> list[str]:
    overrides = overrides or {}
    document = read(INVENTORY, overrides)
    runbook = read(RUNBOOK, overrides)
    findings: list[str] = []

    browser_rows = rows(section(document, "Browser runtime and browser-build packages"))
    browser_index = {(row[1], row[2]): row for row in browser_rows if len(row) >= 4}
    lock = json.loads(read("scripts/browser-vendor/package-lock.json", overrides))
    js_yaml = (lock.get("packages") or {}).get("node_modules/js-yaml") or {}
    if (js_yaml.get("dependencies") or {}).get("argparse") != "^2.0.1":
        findings.append("browser dependency trace changed: js-yaml no longer declares argparse ^2.0.1")
    for path, item in (lock.get("packages") or {}).items():
        if not path:
            continue
        name = path.removeprefix("node_modules/")
        key = (name, str(item.get("version", "")))
        row = browser_index.get(key)
        if not row:
            findings.append(f"missing browser package row: {name}=={key[1]}")
        elif row[3] != (item.get("license") or "NOASSERTION"):
            findings.append(f"browser license drift: {name}=={key[1]}")

    python_rows = rows(section(document, "Python runtime and repository-tool packages"))
    python_index = {(row[1], row[2]): row for row in python_rows if len(row) >= 4}
    expected_python = set()
    for path in PYTHON_LOCKS:
        expected_python |= python_pins(read(path, overrides))
    expected_python |= {
        ("torch", "2.11.0+cu128"),
        ("torchvision", "0.26.0+cu128"),
        ("torchaudio", "2.11.0+cu128"),
    }
    for name, version in sorted(expected_python):
        row = python_index.get((name, version))
        if not row:
            findings.append(f"missing Python package row: {name}=={version}")
        elif row[3] in {"", "BSD", "Apache2.0", "NOASSERTION"}:
            findings.append(f"non-specific Python license identifier: {name}=={version}: {row[3]}")

    material_rows = rows(section(document, "Third-party course-material relationships"))
    material_paths = {row[0] for row in material_rows if row}
    for base, path, arrays in PROVENANCE:
        data = provenance(path, overrides)
        for array in arrays:
            for item in data.get(array, []) or []:
                if item.get("source_url"):
                    local = f"{base}/{item['file']}"
                    if local not in material_paths:
                        findings.append(f"missing external-material row: {local}")

    for fact in REQUIRED_CONTAINER_FACTS:
        if fact not in document:
            findings.append(f"missing container boundary fact: {fact}")
    for explanation in REQUIRED_EXPLANATIONS:
        if explanation not in document:
            findings.append(f"missing license-scope explanation: {explanation}")
    for instruction in REQUIRED_RUNBOOK_TEXT:
        if instruction not in runbook:
            findings.append(f"missing SBOM acquisition instruction: {instruction}")
    dockerfile = read("cpu/services/llm_client/llm_client.Dockerfile", overrides)
    for pin in REQUIRED_LLM_PINS:
        if pin not in dockerfile:
            findings.append(f"llm-client dependency is not exact: {pin}")
    pages_build = read("scripts/build/build_pages.sh", overrides)
    for line in REQUIRED_DISTRIBUTION_LINES:
        if line not in pages_build:
            findings.append(f"Pages artifact does not distribute required license file: {line}")

    return findings


def self_test() -> tuple[int, int, list[str]]:
    baseline = audit()
    if baseline:
        return 0, 0, ["baseline is not clean: " + finding for finding in baseline]
    document = read(INVENTORY, {})
    runbook = read(RUNBOOK, {})
    dockerfile = read("cpu/services/llm_client/llm_client.Dockerfile", {})
    pages_build = read("scripts/build/build_pages.sh", {})
    mutations = (
        ("browser row", {INVENTORY: document.replace("| browser-runtime | codemirror | 5.65.21 |", "| removed | codemirror | 0 |", 1)}, "missing browser package row"),
        ("Python row", {INVENTORY: re.sub(r"(?m)^\| [^\n|]+ \| fastapi \| 0\.138\.2 \|.*$", "| removed | fastapi | 0 |", document, count=1)}, "missing Python package row"),
        ("Python identifier", {INVENTORY: re.sub(r"(?m)^(\| [^\n|]+ \| docker \| 7\.1\.0 \|) Apache-2\.0 (\|.*)$", r"\1 NOASSERTION \2", document, count=1)}, "non-specific Python license identifier"),
        ("material row", {INVENTORY: document.replace("| web/nemoclaw/assets/figures/fig2_react.svg |", "| removed/fig2_react.svg |", 1)}, "missing external-material row"),
        ("service pin", {"cpu/services/llm_client/llm_client.Dockerfile": dockerfile.replace("uvicorn[standard]==0.49.0", "uvicorn[standard]", 1)}, "llm-client dependency is not exact"),
        ("artifact distribution", {"scripts/build/build_pages.sh": pages_build.replace('cp "$T1/THIRD_PARTY_LICENSES.md" "$OUT/THIRD_PARTY_LICENSES.md"', "# removed third-party inventory", 1)}, "Pages artifact does not distribute required license file"),
        ("argparse explanation", {INVENTORY: document.replace("`argparse@2.0.1` is a JavaScript npm package used transitively by `js-yaml@5.2.1`.", "argparse is unexplained.", 1)}, "missing license-scope explanation"),
        ("acquisition procedure", {INVENTORY: document.replace("## Reproducing license-evidence acquisition", "## Undocumented acquisition", 1)}, "missing license-scope explanation"),
        ("SBOM runbook", {RUNBOOK: runbook.replace("# SBOM generation and attachment runbook", "# Missing runbook contract", 1)}, "missing SBOM acquisition instruction"),
    )
    failures = []
    passed = 0
    for label, overrides, expected in mutations:
        observed = audit(overrides)
        if any(expected in finding for finding in observed):
            passed += 1
        else:
            failures.append(f"mutation escaped: {label}")
    return passed, len(mutations), failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        passed, total, failures = self_test()
        print(f"third-party inventory self-test: {passed}/{total} mutation detectors passed")
        for failure in failures:
            print(f"  {failure}")
        return 1 if failures else 0
    findings = audit()
    if findings:
        print(f"third-party inventory audit: FAIL ({len(findings)})")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print("third-party inventory audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
