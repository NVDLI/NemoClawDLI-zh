#!/usr/bin/env python3
"""Audit Python dependency declarations against PyPI vulnerability metadata.

This is a fast source-level guard for dependency manifests. It checks the version a
manifest declares as its floor or exact pin, then fails if PyPI/OSV reports any known
vulnerability for that release. It is intentionally narrower than a full transitive
SCA pass; use pip-audit or OSV-Scanner inside the built test/lab environment for the
installed dependency graph.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

MANIFESTS = (
    Path("workspace/requirements.txt"),
    Path("cpu/services/sandbox_admin/requirements.txt"),
    Path("cpu/services/docker_router/Dockerfile"),
    Path("cpu/services/llm_client/llm_client.Dockerfile"),
)

# Packages from the current advisory class plus their required minimum remediation floors.
# Names use normalized PEP 503 form.
REQUIRED_FLOORS = {
    "fastapi": "0.138.1",
    "starlette": "1.3.1",
    "protobuf": "5.29.6",
    "mcp": "1.23.0",
    "cryptography": "48.0.1",
    "aiohttp": "3.14.1",
}

# These packages are intentionally absent from the supported course/lab runtime.
# Adding one back requires a demonstrated runtime use plus a fresh OSRB distribution
# decision; a bare dependency declaration is not sufficient evidence.
FORBIDDEN_DIRECT_REQUIREMENTS = {
    "langserve": "retired unused dependency; reintroduction requires runtime evidence and an OSRB distribution decision",
    "langgraph-cli": "retired unused in-memory runtime; it conflicts with the supported protobuf, cryptography, OpenTelemetry, and Starlette compatibility line",
    "jupyter-archive": "unused optional Jupyter extension removed from the supported runtime and SBOM; reintroduction requires learner evidence and source/license disposition",
    "jupyter-collaboration": "unused optional Jupyter extension removed from the supported runtime and SBOM; reintroduction requires learner evidence and source/license disposition",
    "jupyter-resource-usage": "unused optional Jupyter extension removed from the supported runtime and SBOM; reintroduction requires learner evidence and source/license disposition",
    "jupyterlab-language-pack-ja-jp": "unused language pack removed from the supported runtime and SBOM; reintroduction requires learner evidence and source/license disposition",
    "jupyterlab-language-pack-zh-cn": "unused language pack removed from the supported runtime and SBOM; reintroduction requires learner evidence and source/license disposition",
    "jupyterlab-language-pack-zh-tw": "unused language pack removed from the supported runtime and SBOM; reintroduction requires learner evidence and source/license disposition",
    "pymupdf": "unused document processor removed from the supported runtime and SBOM; reintroduction requires runtime evidence and source/license disposition",
}

# BDSA-2025-123809 / upstream #26432: no released wheel through 7.35.1 contains
# the complete Struct/Value/ListValue recursion fix. The runtime currently uses
# protobuf for generated/binary messages, not the vulnerable JSON conversion API.
# Keep that claim executable while the time-boxed waiver is active.
PROTOBUF_JSON_PARSE_RE = re.compile(
    r"\b(?:json_format|protobuf_json_format)\.(?:Parse|ParseDict)\s*\("
    r"|from\s+google\.protobuf\.json_format\s+import\s+[^\n]*(?:Parse|ParseDict)\b"
)
PROTOBUF_WAIVER_ID = "BDSA-2025-123809"
WAIVER_REGISTRY = ROOT / "scripts" / "security" / "vulnerability-waivers.json"

REQ_RE = re.compile(
    r'^(?P<name>[A-Za-z0-9_.-]+)(?:\[[^\]]+\])?\s*'
    r'(?:(?P<op>==|>=|~=|>|<=|<)\s*(?P<ver>[A-Za-z0-9_.!*+\-]+))?'
)
PIP_INSTALL_RE = re.compile(r"\bpip(?:3)?\s+install\b")


def norm_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def version_tuple(ver: str) -> tuple:
    parts = []
    for piece in re.split(r"[.+_-]", ver):
        if piece.isdigit():
            parts.append(int(piece))
        else:
            parts.append(piece)
    return tuple(parts)


def split_requirement_line(line: str) -> str | None:
    line = line.split("#", 1)[0].strip()
    if not line or line.startswith(("-", "--")):
        return None
    return line


def pip_install_blocks(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks: list[str] = []
    current: list[str] = []
    collecting = False
    for line in lines:
        stripped = line.strip()
        if not collecting and PIP_INSTALL_RE.search(stripped):
            collecting = True
        if collecting:
            current.append(stripped.rstrip("\\").strip())
            if not stripped.endswith("\\"):
                blocks.append(" ".join(current))
                current = []
                collecting = False
    if current:
        blocks.append(" ".join(current))
    return blocks


def docker_tokens(block: str) -> list[str]:
    # Enough shell splitting for quoted requirement specs; ignore flags and shell operators.
    try:
        import shlex
        return [tok for tok in shlex.split(block) if tok and not tok.startswith("-")]
    except ValueError:
        return block.replace("\\", " ").split()


def declarations() -> list[dict]:
    rows: list[dict] = []
    for rel in MANIFESTS:
        path = ROOT / rel
        if not path.is_file():
            rows.append({"file": str(rel), "error": "missing manifest"})
            continue
        if rel.name == "Dockerfile" or rel.suffix == ".Dockerfile":
            for block in pip_install_blocks(path):
                for token in docker_tokens(block):
                    spec = token.strip('"\'')
                    m = REQ_RE.match(spec)
                    if not m:
                        continue
                    name = norm_name(m.group("name"))
                    op, ver = m.group("op"), m.group("ver")
                    if name in REQUIRED_FLOORS:
                        rows.append({"file": str(rel), "spec": spec, "name": name, "op": op, "version": ver})
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            spec = split_requirement_line(line)
            if not spec:
                continue
            m = REQ_RE.match(spec)
            if not m:
                continue
            name = norm_name(m.group("name"))
            if name in REQUIRED_FLOORS:
                rows.append({"file": str(rel), "line": n, "spec": spec, "name": name, "op": m.group("op"), "version": m.group("ver")})
    return rows


def forbidden_direct_requirements(path: Path = ROOT / "workspace" / "requirements.txt") -> list[dict]:
    """Reject direct dependencies intentionally removed from the supported runtime."""
    findings: list[dict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        spec = split_requirement_line(line)
        if not spec:
            continue
        match = REQ_RE.match(spec)
        if not match:
            continue
        name = norm_name(match.group("name"))
        if name in FORBIDDEN_DIRECT_REQUIREMENTS:
            findings.append({
                "file": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                "line": line_number,
                "package": name,
                "reason": FORBIDDEN_DIRECT_REQUIREMENTS[name],
            })
    return findings


def unlocked_direct_requirements(path: Path = ROOT / "workspace" / "requirements.txt") -> list[dict]:
    """Require exact versions for each direct workspace dependency used by SBOM scans."""
    findings: list[dict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        spec = split_requirement_line(line)
        if not spec:
            continue
        match = REQ_RE.match(spec)
        if not match:
            continue
        if match.group("op") != "==" or not match.group("ver"):
            findings.append({
                "file": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                "line": line_number,
                "package": norm_name(match.group("name")),
                "reason": "direct workspace dependencies must use an exact == version for source/SBOM identity",
            })
    return findings


def protobuf_json_parse_callers() -> list[dict]:
    """Find runtime code that would make the waived recursion bug reachable."""
    findings: list[dict] = []
    for root_name in ("cpu", "workspace"):
        for path in (ROOT / root_name).rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for match in PROTOBUF_JSON_PARSE_RE.finditer(text):
                findings.append({
                    "file": str(path.relative_to(ROOT)),
                    "line": text.count("\n", 0, match.start()) + 1,
                    "package": "protobuf",
                    "reason": "BDSA-2025-123809 exposure: protobuf JSON Parse/ParseDict is forbidden while the recursion advisory has no patched release",
                })
    return findings


def active_waiver(advisory_id: str, package: str) -> bool:
    try:
        data = json.loads(WAIVER_REGISTRY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    today = dt.date.today()
    for waiver in data.get("waivers", []):
        if waiver.get("id") != advisory_id or norm_name(str(waiver.get("package", ""))) != norm_name(package):
            continue
        try:
            return dt.date.fromisoformat(str(waiver.get("expires"))) >= today
        except ValueError:
            return False
    return False


def fetch_vulns(name: str, version: str) -> list[dict]:
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "NemoClaw-dependency-audit/1"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp).get("vulnerabilities", [])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="emit machine-readable report")
    ap.add_argument("--self-test", action="store_true", help="exercise the retired-dependency guard without network access")
    args = ap.parse_args()

    if args.self_test:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "requirements.txt"
            retired = ["langserve>=0.3"] + [f"{name}==0" for name in FORBIDDEN_DIRECT_REQUIREMENTS if name != "langserve"]
            manifest.write_text("requests==2.33.1\n" + "\n".join(retired) + "\n", encoding="utf-8")
            forbidden = forbidden_direct_requirements(manifest)
            unlocked = unlocked_direct_requirements(manifest)
        if {item.get("package") for item in forbidden} != set(FORBIDDEN_DIRECT_REQUIREMENTS):
            print("python dependency audit self-test: FAIL", file=sys.stderr)
            return 1
        if len(unlocked) != 1 or unlocked[0].get("package") != "langserve":
            print("python dependency audit self-test: FAIL", file=sys.stderr)
            return 1
        print("python dependency audit self-test: PASS (retired and unlocked dependencies rejected)")
        return 0

    rows = declarations()
    failures: list[dict] = (
        protobuf_json_parse_callers()
        + forbidden_direct_requirements()
        + unlocked_direct_requirements()
    )
    notes: list[str] = []
    protobuf_waived = active_waiver(PROTOBUF_WAIVER_ID, "protobuf")
    if not protobuf_waived:
        failures.append({
            "file": str(WAIVER_REGISTRY.relative_to(ROOT)),
            "package": "protobuf",
            "reason": f"{PROTOBUF_WAIVER_ID} has no active waiver while no patched protobuf release is available",
        })
    seen = {(r.get("file"), r.get("name")) for r in rows if r.get("name")}

    for file_rel in ("workspace/requirements.txt",):
        for name in REQUIRED_FLOORS:
            if (file_rel, name) not in seen:
                failures.append({"file": file_rel, "package": name, "reason": "missing required dependency floor"})

    cache: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        if row.get("error"):
            failures.append(row)
            continue
        name = row["name"]
        op = row.get("op")
        ver = row.get("version")
        floor = REQUIRED_FLOORS[name]
        if op not in {"==", ">="} or not ver:
            failures.append({**row, "reason": f"{name} must declare == or >= {floor}"})
            continue
        if version_tuple(ver) < version_tuple(floor):
            failures.append({**row, "reason": f"{name} floor {ver} is below required {floor}"})
            continue
        key = (name, ver)
        if key not in cache:
            try:
                cache[key] = fetch_vulns(name, ver)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                failures.append({**row, "reason": f"could not query PyPI vulnerability metadata: {exc}"})
                continue
        vulns = cache[key]
        if vulns:
            failures.append({**row, "reason": "known vulnerabilities reported by PyPI/OSV", "vulnerabilities": vulns})
        elif name == "protobuf" and protobuf_waived:
            notes.append(f"WAIVED {row['file']}: {row['spec']} ({PROTOBUF_WAIVER_ID}; Parse/ParseDict reachability guard clean)")
        else:
            notes.append(f"PASS {row['file']}: {row['spec']} ({name} {ver})")

    report = {"ok": not failures, "checked": rows, "failures": failures, "notes": notes}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for note in notes:
            print(note)
        if failures:
            print("python dependency audit: FAIL", file=sys.stderr)
            for f in failures:
                loc = f.get("file", "?")
                if f.get("line"):
                    loc += f":{f['line']}"
                print(f"  - {loc}: {f.get('package') or f.get('name') or f.get('spec')} - {f.get('reason')}", file=sys.stderr)
        else:
            print("python dependency audit: OK")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
