#!/usr/bin/env python3
"""Consistency guard: catch "changed a fact in one place, forgot the others".

Enforcement layer behind the SKILL.html change_impact maps. The maps DECLARE which
files move together; this script CHECKS that duplicated facts agree and that every
path a SKILL points at exists.

The proof-surface follows the content across the whole tree, and absence where a fact
is expected is a FAIL, not a pass. A service brain that does not describe itself, a
canonical source whose shape changed out from under the parser, or a config value
present nowhere are all real regressions, surfaced rather than hidden.

Checks
------
INVARIANTS  A fact duplicated across files must agree everywhere; a canonical source
            that exists but no longer parses, or a value expected but absent, FAILs.
DANGLING    Every concrete repo path a SKILL skill-meta points at must exist. FAIL.
HARNESS     A SKILL self-test must be fully wired; a SERVICE SKILL with no tester at
            all is a FAIL (the tests are the agent-facing contract).
PROPAGATION (advisory, --since REF) change_impact when_files moved without then_review.

Usage
-----
  scripts/skill_consistency.py                 # invariants + dangling + harness; exit 1 on FAIL
  scripts/skill_consistency.py --since origin/main   # + propagation reminders
  scripts/skill_consistency.py --json          # machine-readable
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# scripts/ sits directly under the CONTENT ROOT: task1 today (a subdir of the DLI wrapper),
# the repo root in the open-source release. So the content root is scripts/..; the git repo
# (the wrapper that holds .git) is its parent while task1 is still a subdir.
TASK1 = Path(__file__).resolve().parent.parent
REPO = TASK1.parent if (TASK1.parent / ".git").exists() else TASK1
SKIP_PARTS = {"__pycache__", ".ipynb_checkpoints", "node_modules", ".git", ".cache",
              # generated build output (gitignored): public/ is the Pages build, the rest are
              # bundler/export trees. Never source, and a build mid-flight makes subdirs appear
              # and vanish under us, so walking into them crashes the scan. Prune them.
              "public", "export", "standalone", "dist", "build",
              # gitignored lab-runtime cruft: never validate it (and do not rely on
              # filesystem permissions to skip it, e.g. a root-owned .Trash-0).
              ".Trash-0", "artifacts", "grounding_cache", "_paper_cache",
              ".exec_stage", ".solution"}
# config/source suffixes worth scanning for duplicated facts
SCAN_SUFFIX = (".html", ".md", ".py", ".js", ".yaml", ".yml", ".conf", ".json")


def walk_files(root: Path, suffixes=None):
    """os.walk with SKIP_PARTS pruned at the DIRECTORY level. Pruning beats rglob's
    post-filter twice over: we never descend into a generated/cache tree, and we never
    crash when a build dir vanishes mid-scan (the public/ FileNotFoundError this fixes)."""
    import os
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_PARTS]
        for fn in fns:
            p = Path(dp) / fn
            if suffixes is None or p.suffix in suffixes:
                yield p


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, IsADirectoryError):
        return ""


def skill_files() -> list[Path]:
    return sorted(p for p in TASK1.rglob("SKILL.html")
                  if not any(s in p.parts for s in SKIP_PARTS))


def service_skills() -> list[Path]:
    return sorted(p for p in TASK1.rglob("SKILL.html")
                  if "services" in p.parts and p.parent.name != "services"
                  and not any(s in p.parts for s in SKIP_PARTS))


def svc_file(name: str, *rest: str) -> Path | None:
    """Locate a per-service source file post-migration (cpu/services first, then legacy)."""
    for base in (TASK1 / "cpu" / "services", TASK1 / "workspace" / "services"):
        cand = base.joinpath(name, *rest)
        if cand.exists():
            return cand
    return None


def skill_meta(p: Path) -> dict | None:
    m = re.search(r'<script type="application/json" id="skill-meta">(.*?)</script>', read(p), re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


# ── results ───────────────────────────────────────────────────────────────────
FAILS: list[str] = []
WARNS: list[str] = []
OKS: list[str] = []


def ok(msg): OKS.append(msg)
def fail(msg): FAILS.append(msg)
def warn(msg): WARNS.append(msg)


# ── INVARIANTS ──────────────────────────────────────────────────────────────────
def inv_openclaw_token():
    """Every <prefix>-openclaw-token literal in the tree must be dli-openclaw-token."""
    found: dict[str, list[str]] = {}
    for p in walk_files(TASK1, SCAN_SUFFIX):
        for tok in re.findall(r'\b([a-z0-9][a-z0-9_-]*-openclaw-token)\b', read(p)):
            found.setdefault(tok, []).append(str(p.relative_to(REPO)))
    distinct = set(found)
    if not distinct:
        # the token is a load-bearing literal across nginx + service SKILLs; its total
        # absence means the scan surface is wrong again, not that all is well.
        fail("openclaw token: NOT FOUND anywhere. The scan surface is wrong or the refs were dropped.")
    elif distinct == {"dli-openclaw-token"}:
        ok(f"openclaw token: single value across {sum(len(v) for v in found.values())} refs")
    else:
        for t in distinct - {"dli-openclaw-token"}:
            fail(f"openclaw token DIVERGENCE: '{t}' in {found[t][:4]} (expected dli-openclaw-token)")


def inv_service_addresses():
    """Per-service SKILLs are the canonical address source: each MUST declare service +
    address, and the same service name must not get two different addresses anywhere."""
    skills = service_skills()
    if not skills:
        fail("service addresses: NO per-service SKILLs found under cpu/services/*/SKILL.html, so the scope is wrong")
        return
    canon: dict[str, str] = {}
    for p in skills:
        meta = skill_meta(p) or {}
        rel = str(p.relative_to(REPO))
        name, addr = meta.get("service"), meta.get("address")
        if not name:
            fail(f"service address: {rel} declares no 'service' name"); continue
        if not addr:
            fail(f"service address: {rel} (service '{name}') declares no 'address'"); continue
        if name in canon and canon[name] != addr:
            fail(f"service address DIVERGENCE for '{name}': {addr} ({rel}) vs {canon[name]}")
        else:
            canon[name] = addr
            ok(f"service address: '{name}' -> {addr}")


def _py_frozenset(text: str, name: str) -> set[str] | None:
    m = re.search(name + r'\s*=\s*frozenset\(\{(.*?)\}\)', text, re.S)
    return set(re.findall(r'"([^"]+)"', m.group(1))) if m else None


def _generic_allowlist(meta: dict) -> set[str] | None:
    m = re.search(r'"generic"\s*:\s*\[([^\]]*)\]', json.dumps(meta.get("interfaces", {})))
    return set(re.findall(r'"([^"]+)"', m.group(1))) if m else None


def inv_exec_allowlist():
    """sandbox-admin's generic exec allow-list (app.py) must equal what the openclaw +
    sandbox_admin SKILLs declare. A canonical source that exists-but-won't-parse, or a
    service SKILL that omits the declaration, is a FAIL (drift hides exactly here)."""
    app = svc_file("sandbox_admin", "app.py")
    if app is None:
        fail("exec allow-list: sandbox_admin/app.py NOT FOUND (canonical source missing)")
        return
    canon = _py_frozenset(read(app), "_ALLOWED_ARGV0")
    if not canon:
        fail(f"exec allow-list: _ALLOWED_ARGV0 no longer parses from {app.relative_to(REPO)} (shape changed)")
        return
    for svc in ("openclaw", "sandbox_admin"):
        sk = svc_file(svc, "SKILL.html")
        if sk is None:
            fail(f"exec allow-list: {svc} SKILL.html NOT FOUND"); continue
        declared = _generic_allowlist(skill_meta(sk) or {})
        if declared is None:
            fail(f"exec allow-list: {svc} SKILL declares no generic allow-list (must mirror app.py)")
        elif declared == canon:
            ok(f"exec allow-list: {svc} SKILL matches app.py ({len(canon)} verbs)")
        else:
            missing, extra = canon - declared, declared - canon
            fail(f"exec allow-list DIVERGENCE in {svc} SKILL: missing {sorted(missing)} extra {sorted(extra)}")


def inv_control_ui_basepath():
    """openclaw control-UI base path must agree across nginx.conf + openclaw.json, and
    must be declared in at least one of them (it is load-bearing for the WS gateway)."""
    vals: dict[str, str] = {}
    m = re.search(r'__OPENCLAW_CONTROL_UI_BASE_PATH__\s*=\s*"([^"]+)"', read(TASK1 / "nginx.conf"))
    if m:
        vals["nginx.conf"] = m.group(1)
    ocjson = svc_file("openclaw", "openclaw.json")
    if ocjson:
        mm = re.search(r'"basePath"\s*:\s*"([^"]+)"', read(ocjson))
        if mm:
            vals["openclaw.json"] = mm.group(1)
    if not vals:
        fail("control-UI basePath: declared in NEITHER nginx.conf NOR openclaw.json (expected in both)")
    elif len(set(vals.values())) > 1:
        fail(f"control-UI basePath DIVERGENCE: {vals}")
    elif len(vals) == 1:
        fail(f"control-UI basePath: declared only in {list(vals)[0]} ({vals}); must agree across both")
    else:
        ok(f"control-UI basePath: agrees across both ({list(vals.values())[0]})")


def inv_lifecycle_allowlist():
    """docker_router LIFECYCLE_SERVICES (docker_router.py) must equal the docker_router
    SKILL's allowed_services. Unparseable canonical or missing declaration is a FAIL."""
    app = svc_file("docker_router", "docker_router.py")
    if app is None:
        fail("lifecycle allow-list: docker_router.py NOT FOUND (canonical source missing)")
        return
    m = re.search(r'LIFECYCLE_SERVICES\s*=\s*\{([^}]*)\}', read(app))
    if not m:
        fail(f"lifecycle allow-list: LIFECYCLE_SERVICES no longer parses from {app.relative_to(REPO)}")
        return
    canon = set(re.findall(r'"([^"]+)"', m.group(1)))
    sk = svc_file("docker_router", "SKILL.html")
    meta = skill_meta(sk) if sk else None
    am = re.search(r'"allowed_services"\s*:\s*\[([^\]]*)\]', json.dumps((meta or {}).get("interfaces", {})))
    if not am:
        fail("lifecycle allow-list: docker_router SKILL declares no allowed_services (must mirror code)")
        return
    declared = set(re.findall(r'"([^"]+)"', am.group(1)))
    if declared == canon:
        ok(f"lifecycle allow-list: docker_router SKILL matches code ({len(canon)} services)")
    else:
        missing, extra = canon - declared, declared - canon
        fail(f"lifecycle allow-list DIVERGENCE: missing {sorted(missing)} extra {sorted(extra)}")


# ── DANGLING refs ────────────────────────────────────────────────────────────────
# dgx/ is kept in the recognizer set on purpose: the release ships no dgx surface, so
# any dgx/<path> a SKILL declares resolves to a missing file and is flagged dangling.
# mats are now course-scoped under web/nemoclaw/mats/, so the "web/" prefix already covers
# them; there is no bare top-level "mats/" path root any more.
_PREFIXES = ("task1/", "cpu/", "web/", "dgx/", "repos/",
             "docs/", "scripts/", "workspace/", "cors-proxy/")


def _resolve(ref: str, base: Path | None = None) -> Path | None:
    """Map a declared path to a filesystem path, or None if it is not a repo path."""
    ref = ref.strip()
    if not ref or ref.startswith(("http://", "https://", "#", "mailto:")):
        return None
    token = ref.split()[0].rstrip(".,;:")
    if "/" not in token and not token.endswith((".md", ".py", ".html", ".yaml", ".yml", ".json")):
        return None
    if token.startswith("task1/"):
        return REPO / token
    if token.startswith(_PREFIXES):
        return TASK1 / token
    if base is not None:                       # relative to the SKILL's own dir
        return base / token
    return None


def check_dangling():
    for p in skill_files():
        meta = skill_meta(p)
        rel = str(p.relative_to(REPO))
        if meta is None:
            fail(f"dangling/JSON: {rel} has no parseable skill-meta")
            continue
        refs: list[str] = []
        if isinstance(meta.get("source_dir"), str):
            refs.append(meta["source_dir"])
        for r in meta.get("related", []) or []:
            if isinstance(r, str):
                refs.append(r)
        for ci in meta.get("change_impact", []) or []:
            for key in ("when_files", "then_review"):
                for r in ci.get(key, []) or []:
                    refs.append(r)
        for ch in meta.get("children", []) or []:        # hub children, now also checked
            if isinstance(ch, dict) and ch.get("path"):
                refs.append(ch["path"])
        bad = [r for r in refs if (fp := _resolve(r, p.parent)) is not None and not fp.exists()]
        if bad:
            fail(f"dangling ref in {rel}: {bad}")
        else:
            ok(f"refs resolve: {rel} ({len(refs)} checked)")


# ── HARNESS WIRING ───────────────────────────────────────────────────────────────
def check_harness_wiring():
    """A self-test mount must load the harness AND call it. A SERVICE SKILL with no
    tester at all is a FAIL: the self-test is the agent-facing contract for a service."""
    for p in skill_files():
        h = read(p)
        rel = str(p.relative_to(REPO))
        meta = skill_meta(p) or {}
        # A directory-explorer documents files (it may LIST _skill_selftest.js in its index)
        # but does not host the self-test harness, so the half-wired heuristic does not apply.
        if meta.get("node_type") == "directory-explorer":
            continue
        mount = 'id="selftest"' in h
        inc = "_skill_selftest.js" in h
        call = "SkillSelfTest.run(" in h
        if mount and inc and call:
            ok(f"harness wiring: {rel}")
        elif not (mount or inc or call):
            if meta.get("service"):
                fail(f"harness wiring: service SKILL {rel} has NO self-test (services must self-verify)")
        else:
            missing = [n for n, v in (("#selftest mount", mount), ("harness include", inc), ("run() call", call)) if not v]
            fail(f"harness wiring in {rel}: half-wired tester, missing {missing}")


# ── PROPAGATION (advisory) ───────────────────────────────────────────────────────
def changed_files(since: str) -> set[str]:
    try:
        out = subprocess.run(["git", "diff", "--name-only", f"{since}...HEAD"],
                             cwd=REPO, capture_output=True, text=True, check=True).stdout
        staged = subprocess.run(["git", "diff", "--name-only"], cwd=REPO,
                                capture_output=True, text=True).stdout
        return set(filter(None, (out + "\n" + staged).splitlines()))
    except subprocess.CalledProcessError:
        return set()


def check_propagation(since: str):
    changed = changed_files(since)
    if not changed:
        return
    for p in skill_files():
        meta = skill_meta(p) or {}
        for ci in meta.get("change_impact", []) or []:
            when = [w for w in ci.get("when_files", []) if w in changed]
            if not when:
                continue
            then = ci.get("then_review", [])
            missing = [t for t in then if t not in changed and (_resolve(t) is None or _resolve(t).exists())]
            if missing:
                warn(f"propagation: {when} changed but change_impact says also review {missing} "
                     f"(declared in {p.relative_to(REPO)})")


def main():
    ap = argparse.ArgumentParser(description="SKILL.html consistency guard")
    ap.add_argument("--since", help="git ref; add propagation reminders vs this base")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    inv_openclaw_token()
    inv_service_addresses()
    inv_exec_allowlist()
    inv_control_ui_basepath()
    inv_lifecycle_allowlist()
    check_dangling()
    check_harness_wiring()
    if args.since:
        check_propagation(args.since)

    if args.json:
        print(json.dumps({"fail": FAILS, "warn": WARNS, "ok": OKS}, indent=2))
    else:
        for m in OKS:
            print(f"  \033[32mok\033[0m   {m}")
        for m in WARNS:
            print(f"  \033[33mwarn\033[0m {m}")
        for m in FAILS:
            print(f"  \033[31mFAIL\033[0m {m}")
        print(f"\n{len(OKS)} ok · {len(WARNS)} warn · {len(FAILS)} FAIL")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
