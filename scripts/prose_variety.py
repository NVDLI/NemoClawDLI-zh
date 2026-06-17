#!/usr/bin/env python3
"""Prose-variety static analysis: does the authored course narrative read like a person wrote it?

LLM prose has structural tells that have nothing to do with word choice: sentences cluster at one
length, ideas get forced into triads, and clauses get welded with colons and semicolons to sound
punchy. This check measures those signals per page over the narrative flow only (<p> paragraphs;
list items are short and parallel by their nature, so they are excluded, along with code, SVG,
headings, and nav chrome), ranks the pages, and surfaces the ones that read machine-uniform so a
human can go vary the rhythm. It is
deterministic and advisory: it points at pages and shows its work, it does not pass verdicts and
never blocks the gate.

Per page it reports:

  cv        coefficient of variation of sentence length (sd / mean), the core variety signal.
            Human prose mixes short and long; a low cv means every sentence is about the same size.
  short%    share of sentences <= 7 words. Real writing breaks long stretches with short jabs.
  triad     runs of 3+ consecutive short sentences (<= 12 words) inside a <= 4-word band: the
            "A does X. B does Y. C does Z." staccato parallel.
  ana       longest run of consecutive sentences opening with the same word.
  r3        three-item "A, B, and C" comma series per 1000 words.
  :;/s      colons + semicolons per sentence (welded-clause punch).
  score     a weighted sum of the above (weights in _score below, and printed in the legend), so
            the table sorts worst-first. A page at or above FLAG_AT is marked for a rhythm pass.

Usage:
  python3 scripts/prose_variety.py                 # rank the course narrative pages (table)
  python3 scripts/prose_variety.py --scope all     # also include the repo's prose .md docs
  python3 scripts/prose_variety.py --page web/nemoclaw/01a-loop.html   # one page + its sentences
  python3 scripts/prose_variety.py --text "..."    # score a snippet (handy while rewriting)
  python3 scripts/prose_variety.py --json          # machine-readable (the gate reads this)
"""
from __future__ import annotations
import argparse
import html
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import link_projection as lp  # noqa: E402

TASK1 = Path(__file__).resolve().parent.parent

FLAG_AT = 3.0   # score at or above this marks a page for a rhythm pass (advisory)

_SENT_SPLIT = re.compile(r'(?<=[.!?])["\'’)\]]*\s+(?=[A-Z(0-9"\'“])')
_WORD = re.compile(r"[A-Za-z0-9']+")
_TAG = re.compile(r"<[^>]+>")
_SVG = re.compile(r"<svg\b.*?</svg>", re.I | re.S)
_PARA = re.compile(r"<p\b[^>]*>(.*?)</p>", re.I | re.S)   # narrative flow only; list items are enumerative by nature
_SERIES3 = re.compile(r"\b[\w][\w'\-]*(?:\s+[\w'\-]+){0,3},\s+[^,.;:]{2,40},\s+(?:and|or)\s+[^,.;:]{2,40}", re.I)
_NEGPAR = re.compile(r"\bnot only\b|\bnot just\b|\bnot merely\b|\bisn't (?:a |an |just )|\bit'?s not\b[^.]*\bit'?s\b|\brather than\b", re.I)


def narrative(f: Path) -> str:
    """The authored narrative of a page: paragraph (<p>) text, with lists/code/SVG/markup removed."""
    raw, suf = lp._read_for_links(f)
    body = lp._strip_noncontent(raw, suf)
    if suf in (".html", ".htm"):
        body = _SVG.sub(" ", body)
        text = "  ".join(_TAG.sub(" ", m.group(1)) for m in _PARA.finditer(body))
    else:
        text = re.sub(r"^\s*#{1,6}\s.*$", " ", body, flags=re.M)   # drop md headings
        text = re.sub(r"^\s*[-*|>].*$", " ", text, flags=re.M)      # drop md lists / tables / quotes
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def _sentences(prose: str):
    out = []
    for p in _SENT_SPLIT.split(prose):
        p = p.strip()
        n = len(_WORD.findall(p))
        if n >= 2:
            out.append((p, n))
    return out


def metrics(prose: str):
    sents = _sentences(prose)
    n = len(sents)
    if n < 5:
        return None
    lens = [w for _, w in sents]
    mean = statistics.fmean(lens)
    sd = statistics.pstdev(lens)

    triads, i = 0, 0
    while i < n:
        j = i
        while (j + 1 < n and lens[j + 1] <= 12 and lens[i] <= 12
               and max(lens[i:j + 2]) - min(lens[i:j + 2]) <= 4):
            j += 1
        if j - i + 1 >= 3:
            triads += 1
        i = j + 1 if j > i else i + 1

    firsts = []
    for s, _ in sents:
        m = _WORD.findall(s)
        firsts.append(m[0].lower() if m else "")
    best = run = 1
    for k in range(1, n):
        run = run + 1 if firsts[k] and firsts[k] == firsts[k - 1] else 1
        best = max(best, run)

    words = sum(lens)
    series3 = len(_SERIES3.findall(prose))
    return {
        "sentences": n, "words": words,
        "mean": round(mean, 1), "sd": round(sd, 1), "cv": round(sd / mean if mean else 0.0, 3),
        "short_ratio": round(sum(1 for w in lens if w <= 7) / n, 3),
        "long_ratio": round(sum(1 for w in lens if w >= 30) / n, 3),
        "triads": triads,
        "anaphora_run": best,
        "series3": series3,
        "series3_density": round(series3 / (words / 1000), 1) if words else 0.0,
        "neg_parallel": len(_NEGPAR.findall(prose)),
        "colon_semi_per_sent": round((prose.count(":") + prose.count(";")) / n, 3),
    }


def _score(m: dict) -> float:
    """Weighted buzz score; higher is worse. Each term is a named tell scaled to comparable size."""
    s = 0.0
    s += 1.5 * m["triads"]                                   # staccato parallels (the strongest, most direct tell)
    s += 1.5 * max(0, m["anaphora_run"] - 3)                 # same-opener runs beyond 3 sentences
    s += 20.0 * max(0.0, 0.50 - m["cv"])                     # uniform sentence length below cv 0.50
    s += 0.4 * max(0.0, m["series3_density"] - 7)            # dense three-item series
    s += 6.0 * max(0.0, m["colon_semi_per_sent"] - 0.32)     # welded clauses
    s += 1.0 * max(0, m["neg_parallel"] - 1)                 # negative parallelisms beyond one
    return round(s, 1)


def tells(m: dict) -> list[str]:
    """The named tells that are notably present, shown so the score is never a black box."""
    t = []
    if m["triads"] >= 2:                     t.append(f"staccato triad x{m['triads']}")
    elif m["triads"] == 1:                   t.append("staccato triad x1")
    if m["anaphora_run"] >= 4:               t.append(f"anaphora run {m['anaphora_run']}")
    if m["cv"] < 0.50:                        t.append(f"monotone length (cv {m['cv']:.2f})")
    if m["short_ratio"] < 0.10:              t.append(f"no short sentences ({m['short_ratio']:.0%})")
    if m["series3_density"] > 9:             t.append(f"rule-of-three dense ({m['series3_density']}/1k)")
    if m["neg_parallel"] >= 3:               t.append(f"negative parallelism x{m['neg_parallel']}")
    if m["colon_semi_per_sent"] > 0.38:      t.append(f"welded clauses ({m['colon_semi_per_sent']:.2f} :;/sent)")
    return t


def _pages(scope: str):
    """Authored narrative pages: the student-facing course HTML under web/. With --scope all, the
    repo's prose .md docs are added too. Generated hubs, tooling, vendored mats, and the license
    (a different genre where terseness and lists are expected) are skipped."""
    for f in sorted(lp._iter_pages(TASK1)):
        rel = f.relative_to(TASK1).as_posix()
        suf = f.suffix.lower()
        if f.name in ("SKILL.html", "studio.html", "courses.html", "cert.html", "LICENSE.md"):
            continue
        if suf in (".html", ".htm"):
            if not rel.startswith("web/"):
                continue
        elif suf == ".md":
            if scope != "all" or rel.startswith(("scripts/", "docs/", "mats/")):
                continue
        else:
            continue
        yield f, rel


def sweep(scope: str = "ship"):
    rows = []
    for f, rel in _pages(scope):
        try:
            m = metrics(narrative(f))
        except Exception:
            m = None
        if m:
            sc = _score(m)
            rows.append({"path": rel, "score": sc, "flagged": sc >= FLAG_AT,
                         "metrics": m, "tells": tells(m)})
    rows.sort(key=lambda r: -r["score"])
    return rows


def _print_table(rows):
    print("prose-variety . authored narrative (advisory; higher score = more machine-uniform)")
    print(f"  {'page':<34} {'score':>5} {'sent':>4} {'mean±sd':>8} {'cv':>5} {'shrt':>5} {'tri':>3} {'ana':>3} {'r3':>4} {':;/s':>5}  tells")
    flagged = 0
    for r in rows:
        m = r["metrics"]
        mark = "* " if r["flagged"] else "  "
        flagged += 1 if r["flagged"] else 0
        print(f"{mark}{r['path']:<34} {r['score']:>5.1f} {m['sentences']:>4} "
              f"{str(m['mean'])+'±'+str(m['sd']):>8} {m['cv']:>5.2f} {m['short_ratio']*100:>4.0f}% "
              f"{m['triads']:>3} {m['anaphora_run']:>3} {m['series3_density']:>4.1f} "
              f"{m['colon_semi_per_sent']:>5.2f}  {'; '.join(r['tells'])}")
    print(f"\n  {len(rows)} pages ranked . {flagged} at/above score {FLAG_AT} (marked *), worth a rhythm pass")
    print("  score = 1.5*triads + 1.5*(anaphora-3) + 20*(0.50-cv when below) + 0.4*(r3/1k over 7)"
          " + 6*(:;/sent over 0.32) + 1*(neg-parallel over 1)")
    print("  legend: cv=length variation (higher is more varied); shrt=% sentences <=7 words; "
          "tri=staccato triads; ana=longest same-opener run; r3=three-item series per 1k words")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Measure human-like prose variety (sentence-length spread, enumeration, clause welding).",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--scope", choices=["ship", "all"], default="ship",
                    help="ship = course narrative under web/ (default); all = also the repo's prose .md docs")
    ap.add_argument("--page", help="analyze one page (relative path) and print its sentences with word counts")
    ap.add_argument("--text", help="score a snippet of prose directly (handy while rewriting)")
    ap.add_argument("--json", action="store_true", help="machine-readable output (the gate reads this)")
    a = ap.parse_args()

    if a.text is not None:
        m = metrics(a.text)
        if not m:
            print("(need at least 5 sentences to measure variety)"); return 0
        out = {"score": _score(m), "flagged": _score(m) >= FLAG_AT, "metrics": m, "tells": tells(m)}
        print(json.dumps(out, indent=2) if a.json else f"score {out['score']}  {m}\n  tells: {out['tells'] or 'none'}")
        return 0

    if a.page:
        f = TASK1 / a.page
        if not f.is_file():
            print(f"no such page: {a.page}", file=sys.stderr); return 2
        prose = narrative(f)
        m = metrics(prose)
        if a.json:
            print(json.dumps({"path": a.page, "score": _score(m) if m else None,
                              "metrics": m, "tells": tells(m) if m else []}, indent=2)); return 0
        if not m:
            print(f"{a.page}: too little narrative to measure (need 5+ sentences)"); return 0
        print(f"{a.page}  score {_score(m)}\n  {m}\n  tells: {tells(m) or 'none'}\n")
        for s, w in _sentences(prose):
            print(f"  [{w:>2}] {s}")
        return 0

    rows = sweep(a.scope)
    if a.json:
        print(json.dumps({"scope": a.scope, "pages": len(rows),
                          "flagged": sum(1 for r in rows if r["flagged"]),
                          "flag_at": FLAG_AT, "rows": rows}, indent=2))
    else:
        _print_table(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
