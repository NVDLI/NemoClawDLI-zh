#!/usr/bin/env python3
"""Verify that the Pages branch selector advertises only published artifact paths."""
from __future__ import annotations

import argparse
import json
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def parse_ref(spec: str) -> tuple[str, str]:
    name, sep, slug = spec.partition("=")
    slug = slug if sep else name
    if not name or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", slug):
        raise ValueError(f"invalid preview ref: {spec!r}")
    return name, slug


def audit(artifact_root: Path, manifest: Path, expected: list[str] | None = None) -> list[str]:
    findings: list[str] = []
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read branch manifest {manifest}: {exc}"]
    if data.get("schema") != "nemoclaw-branches/2":
        findings.append("branch manifest must use availability-aware schema nemoclaw-branches/2")
    items = data.get("branches")
    if not isinstance(items, list) or not items:
        return findings + ["branch manifest must contain at least the production entry"]

    names: set[str] = set()
    slugs: set[str] = set()
    previews: dict[str, str] = {}
    current = []
    production = 0
    for item in items:
        if not isinstance(item, dict):
            findings.append("branch manifest entries must be objects")
            continue
        name = item.get("name")
        slug = item.get("slug")
        kind = item.get("kind")
        if not isinstance(name, str) or not name:
            findings.append("branch manifest entry is missing its name")
            continue
        if name in names:
            findings.append(f"duplicate branch name: {name}")
        names.add(name)
        if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", slug):
            findings.append(f"invalid branch slug for {name}: {slug!r}")
            continue
        if slug in slugs:
            findings.append(f"duplicate branch slug: {slug}")
        slugs.add(slug)
        if item.get("preview_ready") is not True:
            findings.append(f"{name} is listed without preview_ready=true")
        if item.get("current") is True:
            current.append(name)
        if kind == "production":
            production += 1
            target = artifact_root / "nemoclaw" / "index.html"
            expected_url = "nemoclaw/"
        elif kind == "preview":
            previews[name] = slug
            target = artifact_root / slug / "web" / "nemoclaw" / "index.html"
            expected_url = f"{slug}/web/nemoclaw/"
        else:
            findings.append(f"invalid branch kind for {name}: {kind!r}")
            continue
        if item.get("url") != expected_url:
            findings.append(f"{name} URL must be {expected_url!r}, got {item.get('url')!r}")
        if not target.is_file():
            findings.append(f"{name} advertises missing preview target: {target}")

    if production != 1:
        findings.append(f"branch manifest must contain exactly one production entry, found {production}")
    declared_current = data.get("current") or {}
    if len(current) != 1 or current[0] != declared_current.get("name"):
        findings.append("branch manifest current entry must uniquely match data.current.name")

    discovered = {
        path.relative_to(artifact_root).parts[0]
        for path in artifact_root.glob("*/web/nemoclaw/index.html")
        if path.relative_to(artifact_root).parts[0] != "validated-source"
    }
    listed = set(previews.values())
    for slug in sorted(discovered - listed):
        findings.append(f"published preview path is missing from manifest: {slug}")
    for slug in sorted(listed - discovered):
        findings.append(f"manifest preview has no published artifact path: {slug}")
    for spec in expected or []:
        name, slug = parse_ref(spec)
        if previews.get(name) != slug:
            findings.append(f"expected published preview missing: {name}={slug}")
    return findings


def self_test() -> list[str]:
    misses: list[str] = []
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        (root / "nemoclaw").mkdir()
        (root / "nemoclaw" / "index.html").write_text("production", encoding="utf-8")
        (root / "ready" / "web" / "nemoclaw").mkdir(parents=True)
        (root / "ready" / "web" / "nemoclaw" / "index.html").write_text("preview", encoding="utf-8")
        base = {
            "schema": "nemoclaw-branches/2",
            "current": {"name": "main", "slug": "main"},
            "branches": [
                {"name": "main", "slug": "main", "kind": "production", "url": "nemoclaw/", "preview_ready": True, "current": True},
                {"name": "ready", "slug": "ready", "kind": "preview", "url": "ready/web/nemoclaw/", "preview_ready": True, "current": False},
            ],
        }
        manifest = root / "branches.json"
        manifest.write_text(json.dumps(base), encoding="utf-8")
        if audit(root, manifest, ["ready=ready"]):
            misses.append("valid artifact rejected")
        cases = []
        ghost = json.loads(json.dumps(base))
        ghost["branches"].append({"name": "ghost", "slug": "ghost", "kind": "preview", "url": "ghost/web/nemoclaw/", "preview_ready": True, "current": False})
        cases.append(("ghost target", ghost, "missing preview target"))
        unready = json.loads(json.dumps(base))
        unready["branches"][1]["preview_ready"] = False
        cases.append(("readiness flag", unready, "preview_ready=true"))
        old = json.loads(json.dumps(base))
        old["schema"] = "nemoclaw-branches/1"
        cases.append(("old schema", old, "availability-aware schema"))
        for label, mutated, expected in cases:
            manifest.write_text(json.dumps(mutated), encoding="utf-8")
            if not any(expected in finding for finding in audit(root, manifest)):
                misses.append(f"detector missed {label}")
        manifest.write_text(json.dumps(base), encoding="utf-8")
        (root / "unlisted" / "web" / "nemoclaw").mkdir(parents=True)
        (root / "unlisted" / "web" / "nemoclaw" / "index.html").write_text("preview", encoding="utf-8")
        if not any("missing from manifest" in finding for finding in audit(root, manifest)):
            misses.append("detector missed unlisted published path")
    return misses


def fetch(url: str, method: str = "GET") -> bytes:
    request = urllib.request.Request(url, method=method, headers={"User-Agent": "nemoclaw-pages-audit/1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status < 200 or response.status >= 400:
            raise RuntimeError(f"HTTP {response.status}: {url}")
        return response.read()


def audit_live_once(base_url: str, expected: list[str]) -> list[str]:
    base = base_url.rstrip("/") + "/"
    findings: list[str] = []
    expected_map = dict(parse_ref(spec) for spec in expected)
    try:
        root_html = fetch(urllib.parse.urljoin(base, "index.html")).decode("utf-8", "replace")
        root_data = json.loads(fetch(urllib.parse.urljoin(base, "branches.json")))
    except (urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
        return [f"live Pages root unavailable: {exc}"]
    if not expected_map and ("b.preview_ready === true" not in root_html or 'method: "HEAD"' not in root_html):
        findings.append("live foyer lacks readiness filtering and same-origin HEAD probes")
    if root_data.get("schema") != "nemoclaw-branches/2":
        findings.append("live root manifest is not nemoclaw-branches/2")
    items = root_data.get("branches") if isinstance(root_data.get("branches"), list) else []
    actual = {
        item.get("name"): item.get("slug")
        for item in items
        if isinstance(item, dict) and item.get("kind") == "preview"
    }
    if actual != expected_map:
        findings.append(f"live root preview set mismatch: expected {expected_map}, got {actual}")
    for item in items:
        if not isinstance(item, dict):
            findings.append("live root manifest contains a non-object entry")
            continue
        if item.get("preview_ready") is not True:
            findings.append(f"live branch lacks preview_ready=true: {item.get('name')}")
        target = urllib.parse.urljoin(base, str(item.get("url") or "") + "index.html")
        try:
            fetch(target, "HEAD")
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            findings.append(f"advertised branch target unavailable: {target}: {exc}")
    for name, slug in expected_map.items():
        branch_base = urllib.parse.urljoin(base, f"{slug}/")
        try:
            branch_html = fetch(urllib.parse.urljoin(branch_base, "index.html")).decode("utf-8", "replace")
            branch_data = json.loads(fetch(urllib.parse.urljoin(branch_base, "branches.json")))
        except (urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
            findings.append(f"branch foyer unavailable for {name}: {exc}")
            continue
        if "b.preview_ready === true" not in branch_html or 'method: "HEAD"' not in branch_html:
            findings.append(f"branch foyer lacks readiness filtering and HEAD probes: {name}")
        if branch_data.get("schema") != "nemoclaw-branches/2":
            findings.append(f"branch foyer manifest is not nemoclaw-branches/2: {name}")
        branch_previews = {
            item.get("name"): item.get("slug")
            for item in branch_data.get("branches", [])
            if isinstance(item, dict) and item.get("kind") == "preview"
        }
        if branch_previews != expected_map:
            findings.append(f"branch foyer preview set mismatch for {name}: {branch_previews}")
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact-root", type=Path)
    ap.add_argument("--manifest", type=Path)
    ap.add_argument("--expect-preview", action="append", default=[])
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--base-url", help="live Pages project root")
    ap.add_argument("--attempts", type=int, default=12)
    ap.add_argument("--delay", type=float, default=5.0)
    ns = ap.parse_args()
    findings = self_test() if ns.self_test else []
    if ns.base_url:
        for attempt in range(1, max(1, ns.attempts) + 1):
            findings = audit_live_once(ns.base_url, ns.expect_preview)
            if not findings:
                break
            if attempt < ns.attempts:
                print(f"branch_preview_manifest_audit: live attempt {attempt}/{ns.attempts} not ready")
                time.sleep(max(0, ns.delay))
    elif not ns.self_test:
        if not ns.artifact_root or not ns.manifest:
            ap.error("--artifact-root and --manifest are required unless --self-test or --base-url is used")
        findings.extend(audit(ns.artifact_root.resolve(), ns.manifest.resolve(), ns.expect_preview))
    if findings:
        print("branch_preview_manifest_audit: FAIL")
        for finding in findings:
            print(f"  - {finding}")
        return 1
    print("branch_preview_manifest_audit: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
