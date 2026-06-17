#!/usr/bin/env python3
"""Typed materials vendorer: pull each course material from its live web source into
committed markdown under web/nemoclaw/mats/, with provenance and a drift check.

This generalizes vendor_glossary.py to several host types so the bundle can "rebase" to
the web's ground truth in a controlled, transparent way. Per host:

  glossary   NVIDIA glossary term pages   -> delegated to vendor_glossary.py
             (the CACHED tier: the 79-term index + the 7 deep articles, both shipped)
  devblog    developer.nvidia.com/blog     -> the WordPress .entry-content body -> markdown
  arxiv      arXiv papers                  -> the arXiv API (title + authors + abstract)

Each material is one row of MANIFEST: {name, url, host, tier}. tier="cached" ships in the
glossary index (offline-searchable); tier="on_demand" gets a catalog entry whose full text
is reached through the source URL on demand (the heavy snapshots are committed for review +
grounding, but not shipped in the bundle).

Outputs (all committed, so review, grounding, and the build see exactly what gets pulled):
  web/nemoclaw/mats/<name>.md        the pulled markdown (its H1 links the source URL)
  web/nemoclaw/mats/_materials.json  provenance per material: url, host, tier, title, blurb,
                                     fetched, sha256, bytes, status

Two modes, one transparent vocabulary (ok / DRIFTED / UNREACHABLE):
  PULL  (contributors + the deploy build): fetch, (re)write the markdown, update provenance.
        A per-material failure NEVER aborts the run: it keeps the committed snapshot and
        records status="unreachable" so the failure is loud, never silent.
  CHECK (--check; the gate + pre-push): re-fetch, recompute the fingerprint, compare it to the
        committed provenance, and report each material ok / DRIFTED / UNREACHABLE with the exact
        one-line fix. Writes nothing. Exits 0 only if every material is ok.

The same status + fix text is what the gate folds into docs/validation/latest.{json,md}, which
build_pages.sh projects to the student-facing validator screen (validation.html / gate.json), so
a materials problem reads identically to you, to CI, and to a student who opens the validator.

Usage:
  python3 scripts/pull_materials.py                 # pull the light on-demand materials (deploy-build default)
  python3 scripts/pull_materials.py --all            # also refresh the heavy glossary tier (index + deep articles)
  python3 scripts/pull_materials.py --only papers   # one host: glossary | blogs | papers
  python3 scripts/pull_materials.py --check          # drift check, no writes (CI / pre-push)
  python3 scripts/pull_materials.py --check --json    # machine-readable status (the gate reads this)
  python3 scripts/pull_materials.py --list           # print the manifest and exit

Dependencies: requests, beautifulsoup4, markdownify, lxml (the same set vendor_glossary.py uses).
"""
from __future__ import annotations
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MATS = os.path.join(REPO, "web", "nemoclaw", "mats")
MATERIALS_JSON = os.path.join(MATS, "_materials.json")          # on-demand provenance (this script)
GLOSSARY_INDEX = os.path.join(MATS, "glossary_index.json")       # cached glossary index (vendor_glossary)
# The unified materials catalog the surface searches: the cached glossary terms + the on-demand
# materials, one searchable list with a tier on each entry. Dual-written to mats/ (source of truth,
# committed) and assets/ (shipped; the webSearch/instantAnswer + explorer backend), exactly like
# glossary_index.json. This is what "elevates the glossary into the course's materials surface".
CATALOG_MATS = os.path.join(MATS, "materials_index.json")
CATALOG_ASSET = os.path.join(REPO, "web", "nemoclaw", "assets", "materials_index.json")
UA = {"User-Agent": "Mozilla/5.0 (NVIDIA DLI course materials vendoring)"}

# ── manifest ──────────────────────────────────────────────────────────────────
# name: output stem under web/nemoclaw/mats/   host: which extractor   tier: cached|on_demand
# To add a material: add a row. To change a source: edit its url and re-pull. Nothing else.
MANIFEST = [
    {"name": "developer-nvidia-com-blog-deploy-self-evolving-agents-for-fa", "host": "devblog",
     "tier": "on_demand",
     "url": "https://developer.nvidia.com/blog/deploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw/"},
    {"name": "arxiv-2005.11401-rag", "host": "arxiv", "tier": "on_demand",
     "url": "https://arxiv.org/abs/2005.11401"},
    {"name": "arxiv-2404.16130-graphrag", "host": "arxiv", "tier": "on_demand",
     "url": "https://arxiv.org/abs/2404.16130"},
    {"name": "arxiv-2210.03629-react", "host": "arxiv", "tier": "on_demand",
     "url": "https://arxiv.org/abs/2210.03629"},
    {"name": "arxiv-2305.18323-rewoo", "host": "arxiv", "tier": "on_demand",
     "url": "https://arxiv.org/abs/2305.18323"},
]

# --only takes a friendly name; map it to the host key.
ONLY_MAP = {"glossary": "glossary", "blogs": "devblog", "papers": "arxiv"}
# The one-line fix shown for a failing material, keyed by host (the --only name to re-run).
FIX_ONLY = {"devblog": "blogs", "arxiv": "papers", "glossary": "glossary"}


def _need_deps():
    try:
        import requests  # noqa: F401
        import bs4  # noqa: F401
        import markdownify  # noqa: F401
        return True
    except ImportError as exc:
        sys.stderr.write(
            "pull_materials needs: requests beautifulsoup4 markdownify lxml\n"
            "  pip install requests beautifulsoup4 markdownify lxml\n"
            f"  (missing: {exc.name})\n")
        return False


def _fetch(url):
    import requests
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    return r.text


# ── extractors: url -> (title, blurb, markdown_body) ──────────────────────────
def extract_devblog(url):
    from bs4 import BeautifulSoup
    from markdownify import markdownify as to_md
    soup = BeautifulSoup(_fetch(url), "lxml")
    title = ""
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        title = og["content"].strip()
    elif soup.find("h1"):
        title = soup.find("h1").get_text(strip=True)
    blurb = ""
    md = (soup.find("meta", attrs={"name": "description"})
          or soup.find("meta", attrs={"property": "og:description"}))
    if md and md.get("content"):
        blurb = " ".join(md["content"].split())
    # The WordPress article body. Try the tightest container first, fall back outward.
    node = (soup.select_one("div.entry-content") or soup.select_one("article .entry-content")
            or soup.select_one("main article") or soup.find("article") or soup.find("main")
            or soup.body)
    if node is None:
        raise ValueError("no article body found")
    for sel in ["script", "style", "nav", "header", "footer", "aside", "form",
                ".related", ".related-posts", ".subscribe", ".newsletter", ".share",
                ".social", ".post-meta", ".breadcrumb", "#comments", ".comments"]:
        for el in node.select(sel):
            el.decompose()
    body = re.sub(r"\n{3,}", "\n\n", to_md(str(node), heading_style="ATX", bullets="-")).strip()
    if len(body) < 200:
        raise ValueError(f"extracted body suspiciously short ({len(body)} chars) -- check the selector")
    return title, blurb, body


def extract_arxiv(url):
    m = re.search(r"(\d{4}\.\d{4,5})", url)
    if not m:
        raise ValueError("no arXiv id in " + url)
    aid = m.group(1)
    xml = _fetch("https://export.arxiv.org/api/query?id_list=" + aid)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entry = ET.fromstring(xml).find("a:entry", ns)
    if entry is None or entry.findtext("a:title", "", ns).strip().lower() == "error":
        raise ValueError("arXiv API returned no entry for " + aid)
    title = " ".join(entry.findtext("a:title", "", ns).split())
    authors = [a.findtext("a:name", "", ns).strip() for a in entry.findall("a:author", ns)]
    summary = " ".join(entry.findtext("a:summary", "", ns).split())
    if not summary:
        raise ValueError("arXiv API returned an empty abstract for " + aid)
    blurb = (summary[:197] + "...") if len(summary) > 200 else summary
    body = ("**Authors:** " + ", ".join(authors) + "\n\n"
            "**Abstract.** " + summary + "\n\n"
            "*Canonical abstract pulled from the arXiv API; the figures in this course are "
            "hand-authored redraws, not extracted from the paper PDF.*")
    return title, blurb, body


EXTRACTORS = {"devblog": extract_devblog, "arxiv": extract_arxiv}


# ── render / fingerprint (PULL and CHECK build the same string, so the hash compares) ──
def _render(mat, title, body):
    return f"# [{title}]({mat['url']})\n\n{body}\n"


def _sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def _md_path(mat):
    return os.path.join(MATS, mat["name"] + ".md")


def _load_provenance():
    if os.path.exists(MATERIALS_JSON):
        with open(MATERIALS_JSON, encoding="utf-8") as fh:
            return {r["name"]: r for r in json.load(fh).get("materials", [])}
    return {}


def _selected(only):
    if not only:
        return list(MANIFEST)
    host = ONLY_MAP.get(only, only)
    return [m for m in MANIFEST if m["host"] == host]


def pull_one(mat):
    """Fetch + (re)write the markdown. Never raises: returns a provenance record whose
    status is 'ok' or 'unreachable' (keeping the committed snapshot on failure)."""
    rec = {"name": mat["name"], "url": mat["url"], "host": mat["host"], "tier": mat["tier"]}
    try:
        title, blurb, body = EXTRACTORS[mat["host"]](mat["url"])
        out = _render(mat, title, body)
        with open(_md_path(mat), "w", encoding="utf-8") as fh:
            fh.write(out)
        rec.update(title=title, blurb=blurb,
                   fetched=datetime.date.today().isoformat(),
                   sha256=_sha(out), bytes=len(out), status="ok")
        print(f"  ok           {mat['name']}  ({len(out)} bytes)")
    except Exception as exc:  # noqa: BLE001 - one source must never abort the rest
        rec.update(status="unreachable", error=str(exc)[:200],
                   fetched=datetime.date.today().isoformat())
        print(f"  UNREACHABLE  {mat['name']}  ({exc})")
        print(f"               kept the committed snapshot; fix with: "
              f"python3 scripts/pull_materials.py --only {FIX_ONLY[mat['host']]}")
    return rec


def check_one(mat, prov):
    """Re-fetch and compare the freshly-rendered fingerprint to the committed provenance.
    Returns (status, detail) with status in ok / drifted / unreachable. Writes nothing."""
    have = prov.get(mat["name"])
    try:
        title, blurb, body = EXTRACTORS[mat["host"]](mat["url"])
        fresh = _sha(_render(mat, title, body))
    except Exception as exc:  # noqa: BLE001
        return "unreachable", str(exc)[:160]
    if not have or "sha256" not in have:
        return "drifted", "no committed fingerprint yet (never pulled)"
    if fresh != have["sha256"]:
        return "drifted", f"source changed since {have.get('fetched', '?')} ({have['sha256']} -> {fresh})"
    return "ok", ""


def cmd_glossary(check):
    """Delegate the glossary host to the proven vendor_glossary.py (cached tier)."""
    vg = os.path.join(HERE, "vendor_glossary.py")
    if check:
        # The glossary index is committed + shipped; a deep drift check would re-fetch 79
        # pages. Keep CHECK fast + deterministic here: verify the committed index parses and
        # is non-empty. A full glossary re-pull is the explicit refresh below.
        idx = os.path.join(MATS, "glossary_index.json")
        try:
            with open(idx, encoding="utf-8") as fh:
                n = len(json.load(fh).get("terms", []))
            print(f"  ok           glossary index ({n} terms committed)")
            return "ok"
        except Exception as exc:  # noqa: BLE001
            print(f"  UNREACHABLE  glossary index ({exc})  "
                  f"-> rebuild: python3 scripts/vendor_glossary.py --index")
            return "unreachable"
    print("  glossary: delegating to vendor_glossary.py (deep articles + --index)")
    subprocess.run([sys.executable, vg], check=False)
    subprocess.run([sys.executable, vg, "--index"], check=False)
    return "ok"


def build_catalog():
    """Merge the cached glossary index + the on-demand materials provenance into one searchable
    catalog -- the unified surface that webSearch/instantAnswer and the explorer read. Each entry
    carries its tier so a cached glossary term (full text shipped) and an on-demand source (reached
    via its URL) are visibly different. Dual-write to mats/ + assets/. Returns (cached, on_demand)."""
    entries = []
    if os.path.exists(GLOSSARY_INDEX):
        for t in json.load(open(GLOSSARY_INDEX, encoding="utf-8")).get("terms", []):
            entries.append({"kind": "glossary", "tier": "cached", "term": t.get("term"),
                            "blurb": t.get("blurb", ""), "url": t.get("url"),
                            "tags": t.get("tags", []), "deep": bool(t.get("deep"))})
    if os.path.exists(MATERIALS_JSON):
        for m in json.load(open(MATERIALS_JSON, encoding="utf-8")).get("materials", []):
            entries.append({"kind": m.get("host"), "tier": m.get("tier", "on_demand"),
                            "term": m.get("title") or m.get("name"), "blurb": m.get("blurb", ""),
                            "url": m.get("url"), "tags": [], "status": m.get("status", "ok")})
    entries.sort(key=lambda e: (e["tier"] != "cached", (e.get("term") or "").lower()))
    cached = sum(1 for e in entries if e["tier"] == "cached")
    payload = {"generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               "count": len(entries), "cached": cached, "on_demand": len(entries) - cached,
               "entries": entries}
    for p in (CATALOG_MATS, CATALOG_ASSET):
        if os.path.isdir(os.path.dirname(p)):
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
    print(f"  -> materials_index.json  ({cached} cached + {len(entries) - cached} on-demand = {len(entries)})")
    return cached, len(entries) - cached


def main():
    ap = argparse.ArgumentParser(
        description="Pull course materials from their web sources into committed markdown.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--only", choices=list(ONLY_MAP), help="restrict to one host type")
    ap.add_argument("--check", action="store_true", help="drift check (re-fetch + compare); writes nothing")
    ap.add_argument("--all", action="store_true",
                    help="also refresh the heavy glossary tier (index + 7 deep articles + images); "
                         "the default pulls only the light on-demand materials, which is what the deploy build runs")
    ap.add_argument("--list", action="store_true", help="print the manifest and exit")
    ap.add_argument("--catalog", action="store_true",
                    help="rebuild only materials_index.json (glossary + on-demand) from existing data, no fetch")
    ap.add_argument("--json", action="store_true", help="machine-readable status (for the gate)")
    a = ap.parse_args()

    if a.catalog:
        build_catalog()
        return 0

    if a.list:
        for m in MANIFEST:
            print(f"  {m['tier']:10} {m['host']:8} {m['name']}\n             {m['url']}")
        print(f"  glossary   cached   (delegated to vendor_glossary.py: 79-term index + deep articles)")
        return 0

    if not _need_deps():
        return 2

    sel = _selected(a.only)
    # The glossary is the heavy cached tier (86 nvidia.com fetches); refresh it only on explicit
    # --all or --only glossary, never on the default pull the deploy build runs (kept fast + reliable).
    do_glossary = a.all or a.only == "glossary"

    # ── CHECK mode (the gate + pre-push) ──────────────────────────────────────
    if a.check:
        prov = _load_provenance()
        rows, drifted, unreachable = [], [], []
        for mat in sel:
            status, detail = check_one(mat, prov)
            rows.append({"name": mat["name"], "url": mat["url"], "host": mat["host"],
                         "tier": mat["tier"], "status": status, "detail": detail})
            if status == "drifted":
                drifted.append(mat)
            elif status == "unreachable":
                unreachable.append(mat)
        gstat = cmd_glossary(check=True) if do_glossary else None
        if gstat and gstat != "ok":
            unreachable.append({"name": "glossary", "host": "glossary"})
        ok = len(rows) - len(drifted) - len(unreachable)
        if not a.json:
            print("\nmaterials drift check  (re-fetch + fingerprint vs committed provenance)")
            for r in rows:
                tag = {"ok": "ok         ", "drifted": "DRIFTED    ", "unreachable": "UNREACHABLE"}[r["status"]]
                print(f"  {tag} {r['name']}")
                if r["status"] != "ok":
                    fix = FIX_ONLY[r["host"]]
                    print(f"               {r['detail']}")
                    print(f"               fix: python3 scripts/pull_materials.py --only {fix}   (then commit)")
            print(f"\n  {ok}/{len(rows)} ok"
                  + (f" · {len(drifted)} drifted" if drifted else "")
                  + (f" · {len(unreachable)} unreachable" if unreachable else ""))
        else:
            print(json.dumps({"checked": len(rows), "ok": ok,
                              "drifted": [r["name"] for r in rows if r["status"] == "drifted"],
                              "unreachable": [r["name"] for r in rows if r["status"] == "unreachable"],
                              "clean": not drifted and not unreachable,
                              "rows": rows}, indent=2))
        return 0 if (not drifted and not unreachable) else 1

    # ── PULL mode (contributors + the deploy build) ───────────────────────────
    os.makedirs(MATS, exist_ok=True)
    prov = _load_provenance()
    print(f"pulling {len(sel)} material(s)" + (f" (--only {a.only})" if a.only else "") + ":")
    for mat in sel:
        prov[mat["name"]] = pull_one(mat)
    if do_glossary:
        cmd_glossary(check=False)
    payload = {"generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               "materials": [prov[m["name"]] for m in MANIFEST if m["name"] in prov]}
    with open(MATERIALS_JSON, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    bad = [r for r in payload["materials"] if r.get("status") != "ok"]
    print(f"  -> {MATERIALS_JSON}"
          + (f"   ({len(bad)} unreachable -- see above)" if bad else "   (all ok)"))
    build_catalog()   # refresh the unified surface (glossary + on-demand) after every pull
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
