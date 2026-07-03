#!/usr/bin/env python3
"""SKILL-contract conformance: is every skill-meta a VALID beacon, not just an accurate one?

The link engine proves SKILL paths resolve; skill_audit proves a beacon matches its
directory (drift); skill_consistency proves duplicated facts agree across files. None of
them check the one thing the SKILL contract is actually about: that each
`<script id="skill-meta">` block is a well-formed contract of its kind. This is that leg.

Two readers, one file, so two checks:

  SCHEMA  Every skill-meta classifies into exactly one kind and carries that kind's
          required keys, a known schema/node_type value, a semver version where the kind
          uses one, and only valid notebook status values. An unclassifiable or
          key-missing meta is a beacon an agent cannot trust. (the gap the other tools left)
  DRIFT   The beacon matches its directory: source_dir / human_landing point at the real
          location, the notebook list is complete, hub children exist. Reused wholesale
          from skill_audit (its detector is the source of truth; --fix delegates to it).

  SOURCE  SKILL.html source stays reviewable and durable: static card/command grids are not
          minified into one-line walls, and beacons do not expose numbered issue/MR/PR threads
          or user handles as course-facing provenance.

The KINDS table below is the contract implemented by the shipped tree and documented in
SKILL_CONTRACT.md. A new kind becomes valid only when its first beacon, implementation,
documentation, and mutation coverage arrive together.

Usage:
  python3 scripts/skills/skill_contract.py            # schema + drift; exit 1 on any schema finding
  python3 scripts/skills/skill_contract.py --json     # machine-readable {schema:[...], drift:[...]}
  python3 scripts/skills/skill_contract.py --fix      # mechanical drift fixes (delegated to skill_audit)
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

for _p in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
    if (_p / "scripts" / "_bootstrap.py").exists():
        sys.path.insert(0, str(_p / "scripts")); break
from _bootstrap import add_script_paths, find_repo_root

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import skill_audit as sa  # drift detector + --fix engine + skills()/parse_meta(); single source of truth

TASK1 = sa.TASK1
_SEMVER = re.compile(r"^\d+\.\d+\.\d+([.\-+].*)?$")
_STATUS = {"ready", "setup", "wip", "ref"}
_PROCESS_REF = re.compile(r"(?:GitLab\s+issue\s*#?\d+|\bissue\s*#\d+|\bMR\s*!?\d+|\bPR\s*#?\d+|merge request\s*!?\d+|pull request\s*#?\d+|@(?!media\b|supports\b|keyframes\b|font-face\b|import\b)[A-Za-z0-9_][A-Za-z0-9_.-]*)", re.I)

# Contract matrix: classify by schema/node_type and require stable beacon keys.
KINDS = {
    "service-skill/1.0":   {"req": ["schema", "service", "address", "source_dir", "summary",
                                    "interfaces", "tests", "title", "version"], "label_any": []},
    "service-index/1.0":   {"req": ["schema", "id", "source_dir", "summary", "services",
                                    "tests", "title", "version"], "label_any": []},
    "dir-skill/1.0":       {"req": ["schema", "node_type", "source_dir", "summary", "title",
                                    "explorer"], "label_any": []},
    "node:hub":            {"req": ["node_type", "children"], "label_any": ["title", "course"]},
    "node:leaf":           {"req": ["node_type", "source_dir", "summary", "self_path"],
                            "label_any": ["title", "course"]},
}
SCHEMA_VALUES = set(KINDS) - {"node:hub", "node:leaf"}
NODE_TYPES = {"hub", "leaf", "directory-explorer"}
VERSIONED = {"service-skill/1.0", "service-index/1.0"}


def classify(meta: dict):
    """Which contract kind is this? schema wins, then node_type. None = unclassifiable."""
    if meta.get("schema"):
        return meta["schema"]
    if meta.get("node_type"):
        return "node:" + meta["node_type"]
    return None


def schema_findings():
    """One pass over every SKILL.html: classify, then check required keys, enums, semver, status."""
    out = []
    for sk in sa.skills():
        rel = str(sk.relative_to(TASK1))
        meta, _ = sa.parse_meta(sk.read_text())
        if meta is None:
            out.append((rel, "no skill-meta JSON block")); continue
        if meta == "ERR":
            out.append((rel, "skill-meta JSON does not parse")); continue

        # schema / node_type values must be known before we trust the classification.
        if meta.get("schema") and meta["schema"] not in SCHEMA_VALUES:
            out.append((rel, f"unknown schema value {meta['schema']!r}"))
        if meta.get("node_type") and meta["node_type"] not in NODE_TYPES:
            out.append((rel, f"unknown node_type {meta['node_type']!r}"))

        kind = classify(meta)
        spec = KINDS.get(kind)
        if spec is None:
            out.append((rel, f"unclassifiable skill-meta (no known schema or node_type): keys {sorted(meta)}"))
            continue

        missing = [k for k in spec["req"] if k not in meta]
        if missing:
            out.append((rel, f"[{kind}] missing required key(s): {missing}"))
        if spec["label_any"] and not any(k in meta for k in spec["label_any"]):
            out.append((rel, f"[{kind}] needs a human label: one of {spec['label_any']}"))

        if kind in VERSIONED and "version" in meta and not _SEMVER.match(str(meta["version"])):
            out.append((rel, f"version {meta['version']!r} is not semver (MAJOR.MINOR.PATCH)"))

        for nb in (meta.get("notebooks") or []):
            st = nb.get("status") if isinstance(nb, dict) else None
            if st is not None and st not in _STATUS:
                out.append((rel, f"notebook {nb.get('file')!r} has invalid status {st!r} (want {sorted(_STATUS)})"))
    return out


def source_quality_findings():
    """Source-level quality checks for SKILL.html files.

    These catch failures the JSON schema cannot see: unreadable static HTML walls and
    process/provenance references that should not leak into durable course beacons.
    """
    out = []
    for sk in sa.skills():
        rel = str(sk.relative_to(TASK1))
        text = sk.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            card_count = line.count('class="skill-card"')
            cmd_count = line.count('class="skill-cmd"')
            if len(line) > 320 and card_count + cmd_count >= 3:
                out.append((rel, f"source-quality line {lineno}: static grid/list packs {card_count + cmd_count} cards or commands onto one line"))
            if _PROCESS_REF.search(line):
                out.append((rel, f"source-quality line {lineno}: numbered issue/MR/PR or user-handle provenance does not belong in SKILL.html"))
    return out


def run(verbose: bool = False) -> dict:
    """Gate entrypoint. Returns {"schema": [(page, detail)], "drift": [(page, detail)]}."""
    return {"schema": schema_findings() + source_quality_findings(), "drift": sa.audit(fix=False)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="machine-readable findings")
    ap.add_argument("--fix", action="store_true", help="apply mechanical drift fixes (delegated to skill_audit)")
    a = ap.parse_args()

    if a.fix:
        sa.audit(fix=True)   # drift is the only mechanically-fixable leg; schema needs a human

    res = run()
    if a.json:
        print(json.dumps({k: [{"page": p, "detail": d} for p, d in v] for k, v in res.items()}, indent=2))
        return 1 if res["schema"] else 0

    if not res["schema"] and not res["drift"]:
        print("skill_contract: ✅ every skill-meta is a valid, accurate beacon of its kind")
        return 0
    for label, items, stream in (("schema", res["schema"], sys.stderr), ("drift", res["drift"], sys.stderr)):
        if items:
            print(f"skill_contract: ✗ {len(items)} {label} finding(s):", file=stream)
            for p, d in items:
                print(f"  {p}: {d}", file=stream)
    # Schema findings are the contract leg and gate the standalone exit; drift mirrors skill_audit.
    return 1 if res["schema"] else 0


if __name__ == "__main__":
    sys.exit(main())
