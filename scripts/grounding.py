#!/usr/bin/env python3
"""Grounded self-validation for the bundle: deterministic material references, cached.

For each content page it builds a compact, reproducible "material reference" (title,
headings, the external citation URLs it shares with a mat, source-file citations, prose
em-dash count) and caches it by content hash, so a re-run only touches CHANGED pages.

Grounding = a page cites an external URL that a mat (the curated reference layer) also
cites; the link graph then associates page<->mat THROUGH that shared URL. mats are never
linked as files; you cite the source they vouch for.

No LLM, no network: every signal is deterministic and reproducible. An earlier 30b
"is-this-on-topic / toney" verdict layer was removed: it needed page-type carve-outs to
manage its noise, defaulted toward pass, and added vibes rather than honest signal.

Usage:
  python3 scripts/grounding.py --scope ship       # all ship-target pages
  python3 scripts/grounding.py --course nemoclaw  # one course
  python3 scripts/grounding.py --report PATH      # aggregate findings + mat-association JSON
"""
from __future__ import annotations
import argparse, hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve()
SCRIPTS = HERE.parent
TASK1 = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
import link_projection as lp  # noqa: E402

CACHE = SCRIPTS / "grounding_cache"
# bump when the reference schema/logic changes (mat-association, vendored, cites, em-dash);
# a logic change then auto-invalidates the cache instead of serving stale records.
REF_VERSION = "r4"

_TAG = re.compile(r"<[^>]+>")
_SVG = re.compile(r"<svg\b.*?</svg>", re.I | re.S)   # diagram text is not prose
_WS = re.compile(r"[ \t]*\n[ \t]*")
_EMDASH = re.compile(r"\S\s*—\s*\S")
_HEADING_MD = re.compile(r"^#{1,4}\s+(.+)$", re.M)
_HEADING_HTML = re.compile(r"<h[1-4][^>]*>(.*?)</h[1-4]>", re.I | re.S)
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>|<h1[^>]*>(.*?)</h1>", re.I | re.S)

# ── mat-grounding by SHARED EXTERNAL URL ─────────────────────────────────────
# Mats are the curated reference layer: they cite external URLs (arxiv, build.nvidia.com,
# developer.nvidia.com, ...). A page is GROUNDED when it cites a URL a mat also cites; the
# link graph then associates page<->mat through that shared URL.
_URL_RE = re.compile(r'https?://[^\s)"\'<>\]\[(]+')
# asset CDNs + infra hosts are not CITATIONS (they are <script>/<link> loads).
_NOISE_HOST = {"localhost", "127.0.0.1", "0.0.0.0", "example.com", "bring-up.sh", "skill.md",
               "cdnjs.cloudflare.com", "cdn.jsdelivr.net", "unpkg.com",
               "fonts.googleapis.com", "fonts.gstatic.com", "dli-lms.s3.amazonaws.com"}


def _norm_url(u: str) -> str:
    u = u.strip().rstrip('.,;:!').split('#')[0]
    m = re.match(r'(https?://)([^/]+)(.*)', u)
    return m.group(1).lower() + m.group(2).lower() + m.group(3).rstrip('/') if m else u.lower()


def _is_citation(u: str) -> bool:
    m = re.match(r'https?://([^/:]+)', u)
    if not m:
        return False
    host = m.group(1).lower()
    if host in _NOISE_HOST or 'w3.org' in host or re.match(r'^\d+\.\d+\.\d+\.\d+$', host):
        return False
    return "." in host


_MAT_INDEX = None


def mat_url_index() -> dict:
    """{normalized_url: {mat_basename, ...}} built from the curated source set in mats/."""
    global _MAT_INDEX
    if _MAT_INDEX is not None:
        return _MAT_INDEX
    idx: dict[str, set] = {}
    md = TASK1 / "mats"
    if md.is_dir():
        for f in md.rglob("*"):
            if f.suffix.lower() not in (".md", ".html", ".htm"):
                continue
            for raw in _URL_RE.findall(f.read_text(errors="ignore")):
                u = _norm_url(raw)
                if _is_citation(u):
                    idx.setdefault(u, set()).add(f.name)
    _MAT_INDEX = idx
    return idx


def _text_of(f: Path):
    raw, suf = lp._read_for_links(f)
    body = lp._strip_noncontent(raw, suf)
    if suf in (".html", ".htm"):
        body = _SVG.sub(" ", body)                    # exclude diagram text from the prose signal
        heads = [re.sub(_TAG, "", h).strip() for h in _HEADING_HTML.findall(body)]
        tm = _TITLE.search(body)
        title = re.sub(_TAG, "", (tm.group(1) or tm.group(2)) if tm else "").strip()
        prose = re.sub(_TAG, " ", body)
    else:
        heads = [h.strip() for h in _HEADING_MD.findall(body)]
        title = heads[0] if heads else ""
        prose = re.sub(r"^#{1,4}\s+", "", body, flags=re.M)
    prose = re.sub(r"[ \t]{2,}", " ", _WS.sub("\n", prose)).strip()
    return title, heads, prose


_SRC_EXT = (".py", ".yaml", ".yml", ".json", ".toml", ".cfg", ".sh", ".js", ".ts",
            ".dockerfile", ".conf")


def build_reference(f: Path, rel: str) -> dict:
    title, heads, prose = _text_of(f)
    course = lp.course_of(rel)
    raw, suf = lp._read_for_links(f)
    txt = lp._strip_noncontent(raw, suf)
    base_dir = "/".join(rel.split("/")[:-1])
    cites = 0                                          # resolvable source-file citations
    for m in set(lp._HREF.findall(txt)) | set(lp._MDL.findall(txt)):
        if lp._is_template_link(m) or m.startswith(("http", "//", "#", "mailto:", "data:", "tel:")):
            continue
        clean = m.split("#")[0].split("?")[0]
        resolved = clean[len("/lab/static/"):] if clean.startswith("/lab/static/") else lp._clamp(base_dir, clean)
        if resolved.lower().endswith(_SRC_EXT) and (TASK1 / resolved).is_file():
            cites += 1
    page_urls = {u for u in (_norm_url(x) for x in _URL_RE.findall(txt)) if _is_citation(u)}
    midx = mat_url_index()
    mat_assoc: dict[str, list] = {}
    for u in page_urls:
        for mat in midx.get(u, ()):
            mat_assoc.setdefault(mat, []).append(u)
    uncovered = sorted(u for u in page_urls if u not in midx)
    # vendored = an external snapshot under mats/ (scraped build.nvidia.com / blog / brev / the
    # developer-site learning path, or a vendored NVIDIA glossary page under glossary_raw/).
    # We cite these but do not rewrite their prose, so any em-dashes in them belong to the
    # original author. The sweep still surfaces and labels them so they are visible in the report.
    vendored = rel.startswith("mats/") and (
        rel.startswith("mats/glossary_raw/") or
        bool(re.search(r'(-(com|org|io)-|learning_path|^(build|developer|brev|module|nemoclaw)-)',
                       rel.rsplit("/", 1)[-1])))
    return {"title": title, "course": course, "vendored": vendored, "headings": heads[:24],
            "em_dash_in_prose": len(_EMDASH.findall(prose)), "prose_chars": len(prose),
            "cites": cites, "ext_urls": len(page_urls), "mat_grounded": bool(mat_assoc),
            "mat_assoc": {m: sorted(us) for m, us in mat_assoc.items()},
            "uncovered_urls": uncovered[:20]}


def _hash(f: Path) -> str:
    return hashlib.sha256(f.read_bytes()).hexdigest()[:16]


def _cache_file(course: str, rel: str) -> Path:
    return CACHE / course / (rel.replace("/", "__") + ".json")


def ground_page(rel: str, force: bool = False) -> dict:
    f = TASK1 / rel
    course = lp.course_of(rel)
    h = _hash(f)
    cf = _cache_file(course, rel)
    if cf.exists() and not force:
        try:
            old = json.loads(cf.read_text())
            if old.get("hash") == h and old.get("ref_version") == REF_VERSION:
                old["cached"] = True
                return old
        except Exception:
            pass
    rec = {"path": rel, "course": course, "hash": h, "ref_version": REF_VERSION,
           "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "reference": build_reference(f, rel), "cached": False}
    cf.parent.mkdir(parents=True, exist_ok=True)
    cf.write_text(json.dumps(rec, indent=2, ensure_ascii=False))
    return rec


def _ship_pages():
    proj = lp.Projection(TASK1)
    for f in lp._iter_pages(TASK1):
        try:
            yield str(f.relative_to(proj.host_root))
        except ValueError:
            yield str(f.relative_to(TASK1))


def sweep(course, scope, limit=None, force=False):
    recs = []
    for rel in _ship_pages():
        c = lp.course_of(rel)
        if course and c != course:
            continue
        if not course and scope == "ship" and not lp.ship_relevant(rel):
            continue
        if not rel.lower().endswith((".html", ".htm", ".md", ".ipynb")):
            continue
        recs.append(ground_page(rel, force=force))
        if limit and len(recs) >= limit:
            break
    return recs


def _groundable(rel: str) -> bool:
    """Should this page TRACE to a mat via a shared citation URL? Only the claim-bearing
    teaching explainers: the numbered nemoclaw web-course pages. Everything else is correctly
    ungrounded by TYPE (corpus data, skill configs, agent docs, persona, hubs, scripts, demo
    notes). Classifying makes 'ungrounded' a meaningful metric instead of a flood of
    non-explainer pages."""
    if "/data/" in rel:
        return False
    return bool(re.match(r'web/nemoclaw/\d', rel))


def _findings(recs):
    out = []
    for r in recs:
        ref = r.get("reference", {})
        issues = []
        if _groundable(r["path"]) and ref.get("prose_chars", 0) > 800 and not ref.get("cites") and not ref.get("mat_grounded"):
            issues.append("ungrounded (no source citation and no mat URL-association)")
        elif _groundable(r["path"]) and ref.get("uncovered_urls") and not ref.get("mat_grounded"):
            issues.append(f"unvetted sources: cites {len(ref['uncovered_urls'])} external URL(s) no mat covers")
        if ref.get("em_dash_in_prose"):
            # the em-dash is a STRUCTURE smell: each one marks an AI-cadenced sentence.
            # Swapping the dash for ./;/() games the metric and reads worse. Rewrite the
            # sentence. Vendored mats are external snapshots, surfaced but not ours to rewrite.
            if ref.get("vendored"):
                issues.append(f"em-dash x{ref['em_dash_in_prose']} (vendored external reference; not ours to rewrite)")
            else:
                issues.append(f"em-dash x{ref['em_dash_in_prose']} "
                              f"(STRUCTURE smell: rewrite each sentence, never substitute punctuation)")
        if issues:
            out.append({"path": r["path"], "course": r["course"], "issues": issues})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--course", help="ground a single course (nemoclaw)")
    ap.add_argument("--scope", choices=["ship", "all"], default="ship")
    ap.add_argument("--force", action="store_true", help="ignore cache, re-ground every page")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--report", help="write an aggregate findings + mat-association JSON to PATH")
    a = ap.parse_args()

    recs = sweep(a.course, a.scope, limit=a.limit, force=a.force)
    findings = _findings(recs)
    cached = sum(1 for r in recs if r.get("cached"))
    grounded = sum(1 for r in recs if r.get("reference", {}).get("mat_grounded"))
    ungrounded = sum(1 for fo in findings if any("ungrounded" in i for i in fo["issues"]))

    print(f"grounding: {len(recs)} pages  (cached {cached})")
    print(f"  mat-associated: {grounded}/{len(recs)} pages share an external citation URL with a mat")
    print(f"  ungrounded: {ungrounded} content page(s) grounded in nothing")
    print(f"  findings: {len(findings)} page(s) with issues")
    for fo in findings[:40]:
        print(f"  {fo['path']}")
        for iss in fo["issues"]:
            print(f"      - {iss}")
    if a.report:
        assoc = {r["path"]: r["reference"]["mat_assoc"] for r in recs if r["reference"].get("mat_assoc")}
        Path(a.report).parent.mkdir(parents=True, exist_ok=True)
        Path(a.report).write_text(json.dumps(
            {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "pages": len(recs), "mat_associated": len(assoc),
             "findings": findings, "mat_association": assoc}, indent=2, ensure_ascii=False))
        print(f"  report -> {a.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
