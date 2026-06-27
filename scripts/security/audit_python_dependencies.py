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
}

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


def fetch_vulns(name: str, version: str) -> list[dict]:
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "NemoClaw-dependency-audit/1"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp).get("vulnerabilities", [])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="emit machine-readable report")
    args = ap.parse_args()

    rows = declarations()
    failures: list[dict] = []
    notes: list[str] = []
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
