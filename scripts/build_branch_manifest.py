#!/usr/bin/env python3
"""Write a build-time branch-preview manifest for the Pages foyer."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
from pathlib import Path


def run_git(args: list[str]) -> list[str]:
    try:
        out = subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def slug_ref(name: str) -> str:
    slug = re.sub(r"[^0-9a-z]+", "-", name.lower()).strip("-")[:63].strip("-")
    return slug or "branch"


def collect_branches() -> list[str]:
    names: set[str] = set()
    for ref in run_git(["for-each-ref", "--format=%(refname:short)", "refs/remotes/origin"]):
        if ref == "origin/HEAD" or not ref.startswith("origin/"):
            continue
        names.add(ref[len("origin/"):])
    for ref in run_git(["for-each-ref", "--format=%(refname:short)", "refs/heads"]):
        names.add(ref)
    return sorted(names, key=lambda n: (n.startswith("translate-"), n.lower()))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--default-branch", default=os.environ.get("CI_DEFAULT_BRANCH", "main"))
    ap.add_argument("--current-ref", default=os.environ.get("CI_COMMIT_REF_NAME") or os.environ.get("CI_COMMIT_BRANCH"))
    ap.add_argument("--current-slug", default=os.environ.get("CI_COMMIT_REF_SLUG"))
    ap.add_argument("--max", type=int, default=80)
    ns = ap.parse_args()

    current = ns.current_ref or (run_git(["branch", "--show-current"]) or [""])[0]
    current_slug = (ns.current_slug or slug_ref(current)) if current else ""
    default_branch = ns.default_branch or "main"

    branches = collect_branches()
    if default_branch and default_branch not in branches:
        branches.insert(0, default_branch)
    if current and current not in branches:
        branches.insert(0, current)

    seen_slugs: set[str] = set()
    items = []
    for name in branches[: ns.max]:
        slug = current_slug if current and name == current and current_slug else slug_ref(name)
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        is_prod = name in {default_branch, "nemoclaw-only"}
        items.append({
            "name": name,
            "slug": slug,
            "kind": "production" if is_prod else "preview",
            "url": "nemoclaw/" if is_prod else f"{slug}/web/nemoclaw/",
            "current": bool(current and name == current),
        })

    data = {
        "schema": "nemoclaw-branches/1",
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "default_branch": default_branch,
        "current": {"name": current, "slug": current_slug} if current else None,
        "production_url": "nemoclaw/",
        "note": "Branch previews exist only after a manual Pages preview deploy has published that branch path.",
        "branches": items,
    }
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"[branches] wrote {out} ({len(items)} branches)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
