#!/usr/bin/env python3
"""Prose-variety static analysis: does the authored course narrative read like a person wrote it?

LLM prose has structural tells that have nothing to do with word choice: sentences cluster at one
length, ideas get forced into triads, and clauses get welded with colons and semicolons to sound
punchy. This check measures those signals per page over the narrative flow only and ranks the pages,
surfacing the ones that read machine-uniform so a human can go vary the rhythm. Narrative is the <p>
paragraph text; enumerative-by-structure content is excluded because it is parallel by its nature and
would read as a false tell (list items, catalog cards), along with code, SVG, headings, and nav
chrome. A paragraph break counts as a sentence boundary, so a list-/cell-lead-in colon at a
paragraph's end is not mistaken for a welded mid-sentence clause. It is deterministic and advisory:
it points at pages and shows its work, it does not pass verdicts and never blocks the gate.

Per page it reports:

  cv        coefficient of variation of sentence length (sd / mean), the core variety signal.
            Human prose mixes short and long; a low cv means every sentence is about the same size.
  short%    share of sentences <= 7 words. Real writing breaks long stretches with short jabs.
  triad     runs of 3+ consecutive short sentences (<= 12 words, <= 4-word band) that share one
            opening word: the "It plans. It acts. It reflects." anaphoric staccato. Short sentences
            with varied openers are ordinary terse prose (spec fragments, captions), not a tell.
  ana       longest run of consecutive sentences opening with the same word.
  r3        exactly-three "A, B, and C" comma series per 1000 words (a 4+ item list is a real
            enumeration, not rule-of-three, so it does not count).
  :;/s      welded clauses per sentence: every semicolon, plus colons that sit mid-sentence; a
            trailing colon is a list-/cell-lead-in, not punch, so it does not count.
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

# Do not split after a citation/abbreviation period ("Yao et al. (2022)", "e.g.", "i.e.", "vs."):
# in an academic course those are mid-sentence, and a false split fabricates short fragments that
# skew length variance and triad detection. Each guard is fixed-width (Python lookbehind rule).
_ABBR_GUARD = (r"(?<!\bal\.)(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bvs\.)(?<!\betc\.)(?<!\bcf\.)"
               r"(?<!\bFig\.)(?<!\bEq\.)(?<!\bNo\.)(?<!\bDr\.)(?<!\bMr\.)(?<!\bMs\.)(?<!\bProf\.)")
_SENT_SPLIT = re.compile(r'(?<=[.!?])' + _ABBR_GUARD + r'["\'’)\]]*\s+(?=[A-Z(0-9"\'“])')
_WORD = re.compile(r"[A-Za-z0-9']+")
# function words only: a shared CONTENT word across short sentences signals a parallel triad
# ("A thermostat PUTS... A car PUTS... Every agent PUTS..."), so verbs/nouns must NOT be in here.
_STOP = {"the", "a", "an", "of", "to", "in", "on", "at", "is", "are", "be", "it", "this", "that",
         "and", "or", "with", "for", "as", "by", "from", "its", "you", "your", "we", "our", "they",
         "their", "he", "she", "but", "so", "if", "then", "into", "out", "up", "no", "not"}
_TAG = re.compile(r"<[^>]+>")
_SVG = re.compile(r"<svg\b.*?</svg>", re.I | re.S)
# Reference/navigation tiles carry terse captions, not narrative flow, so they are excluded like
# list items: any link-card (the whole card is an <a> -- url-card, sys-card, path-card, the foyer's
# course cards) and the step-card catalog tile. Content cards that hold teaching prose (pattern-card,
# a <div>) are kept and measured.
_CARDS = (
    re.compile(r'<a\b[^>]*\bclass="[^"]*\bcard\b[^"]*"[^>]*>.*?</a>', re.I | re.S),
    re.compile(r'<div\b[^>]*\bclass="[^"]*\bstep-card\b[^"]*"[^>]*>.*?</div>', re.I | re.S),
)
_PARA = re.compile(r"<p\b[^>]*>(.*?)</p>", re.I | re.S)   # narrative flow only; list items are enumerative by nature
_SERIES3 = re.compile(r"(?<!, )\b[\w][\w'\-]*(?:\s+[\w'\-]+){0,3},\s+[^,.;:]{2,40},\s+(?:and|or)\s+[^,.;:]{2,40}", re.I)  # exactly-three series; a 4+ item enumeration is not rule-of-three
# Negative parallelism / antithesis (HUMANIZE #9): the negate-then-affirm cadence. The strongest
# form is "not X, but Y"; bare "rather than" is usually an ordinary preference contrast, not a tell,
# so it is not counted (it only ever fired on legitimate technical comparisons here).
_NEGPAR = re.compile(
    r"\bnot only\b[^.]{1,60}?\bbut\b"                       # not only X but (also) Y
    r"|\bnot\b[^,.;:]{2,35}?,?\s+but\b"                     # not X(,) but Y
    r"|\bit(?:'?s| is) not\b[^.]{1,60}?\bit(?:'?s| is)\b"   # it's not X, it's Y
    r"|\b(?:not|isn'?t) just\b"                             # not just / isn't just (soft antithesis cue)
    r"|\bnot merely\b",
    re.I)


def narrative(f: Path) -> list:
    """The authored narrative of a page as a list of paragraph chunks (each <p>, or each markdown
    paragraph). Kept as separate chunks so a paragraph break counts as a sentence boundary and a
    list-/cell-lead-in colon at a paragraph's end is not mistaken for a welded mid-sentence clause.
    Lists, code, SVG, and markup are removed."""
    raw, suf = lp._read_for_links(f)
    body = lp._strip_noncontent(raw, suf)
    if suf in (".html", ".htm"):
        body = _SVG.sub(" ", body)
        for _c in _CARDS:             # drop reference/navigation tile captions (not narrative flow)
            body = _c.sub(" ", body)
        raw_chunks = [_TAG.sub(" ", m.group(1)) for m in _PARA.finditer(body)]
    else:
        body = re.sub(r"^\s*#{1,6}\s.*$", " ", body, flags=re.M)   # drop md headings
        body = re.sub(r"^\s*[-*|>].*$", " ", body, flags=re.M)      # drop md lists / tables / quotes
        raw_chunks = re.split(r"\n\s*\n", body)                     # a blank line separates paragraphs
    chunks = []
    for c in raw_chunks:
        c = html.unescape(re.sub(r"\s+", " ", c)).strip()
        if c:
            chunks.append(c)
    return chunks


def _sentences(prose):
    """(sentence, word-count) pairs. Accepts a chunk list (paragraph breaks are sentence
    boundaries) or a single string."""
    chunks = [prose] if isinstance(prose, str) else prose
    out = []
    for ch in chunks:
        for p in _SENT_SPLIT.split(ch):
            p = p.strip()
            n = len(_WORD.findall(p))
            if n >= 2:
                out.append((p, n))
    return out


def metrics(prose):
    sents = _sentences(prose)
    text = " ".join([prose] if isinstance(prose, str) else prose)
    n = len(sents)
    if n < 5:
        return None
    lens = [w for _, w in sents]
    mean = statistics.fmean(lens)
    sd = statistics.pstdev(lens)

    firsts, toks = [], []
    for s, _ in sents:
        w = _WORD.findall(s)
        firsts.append(w[0].lower() if w else "")
        toks.append({t.lower() for t in w if len(t) >= 3 and t.lower() not in _STOP})

    # A staccato triad is 3+ consecutive short sentences (<=12 words, <=4-word band) that are
    # PARALLEL: they share one opening word ("It plans. It acts. It reflects.") OR a content word
    # repeated across all of them ("A thermostat PUTS X. A car PUTS Y. Every agent PUTS Z."). Short
    # sentences sharing neither are ordinary terse prose (spec fragments, captions), not a tell.
    def _parallel(a, b):
        return len(set(firsts[a:b])) == 1 or bool(set.intersection(*toks[a:b]))
    triads, i = 0, 0
    while i < n:
        j = i
        while (j + 1 < n and lens[j + 1] <= 12 and lens[i] <= 12
               and max(lens[i:j + 2]) - min(lens[i:j + 2]) <= 4
               and _parallel(i, j + 2)):
            j += 1
        if j - i + 1 >= 3:
            triads += 1
        i = j + 1 if j > i else i + 1

    best = run = 1
    for k in range(1, n):
        run = run + 1 if firsts[k] and firsts[k] == firsts[k - 1] else 1
        best = max(best, run)

    words = sum(lens)
    series3 = len(_SERIES3.findall(text))

    welded = 0                                                # a semicolon always welds; a colon only
    for s, _ in sents:                                        # when text follows it within the sentence.
        welded += s.count(";")                                # a trailing colon is a list-/cell-lead-in,
        body_s = s.rstrip()                                   # not punch, so it does not count.
        welded += sum(1 for mt in re.finditer(":", body_s) if mt.end() < len(body_s))

    return {
        "sentences": n, "words": words,
        "mean": round(mean, 1), "sd": round(sd, 1), "cv": round(sd / mean if mean else 0.0, 3),
        "short_ratio": round(sum(1 for w in lens if w <= 7) / n, 3),
        "long_ratio": round(sum(1 for w in lens if w >= 30) / n, 3),
        "triads": triads,
        "anaphora_run": best,
        "series3": series3,
        "series3_density": round(series3 / (words / 1000), 1) if words else 0.0,
        "neg_parallel": len(_NEGPAR.findall(text)),
        "colon_semi_per_sent": round(welded / n, 3),
    }


def _score(m: dict) -> float:
    """Weighted buzz score; higher is worse. Each term is a named tell scaled to comparable size."""
    s = 0.0
    s += 1.5 * m["triads"]                                   # staccato parallels (the strongest, most direct tell)
    s += 1.5 * max(0, m["anaphora_run"] - 3)                 # same-opener runs beyond 3 sentences
    s += 20.0 * max(0.0, 0.50 - m["cv"])                     # uniform sentence length below cv 0.50
    s += 5.0 * max(0.0, 0.10 - m["short_ratio"])            # no short sentences to break the rhythm
    s += 0.4 * max(0.0, m["series3_density"] - 7)            # dense three-item series
    s += 6.0 * max(0.0, m["colon_semi_per_sent"] - 0.32)     # welded clauses
    s += 1.0 * max(0, m["neg_parallel"] - 1)                 # negative parallelisms beyond one
    return round(s, 1)


def tells(m: dict) -> list[str]:
    """The named tells that contribute to the score, each shown at the SAME threshold the score
    uses, so a nonzero score is always explained by a visible tell (never a black box)."""
    t = []
    if m["triads"] >= 1:                     t.append(f"staccato triad x{m['triads']}")
    if m["anaphora_run"] >= 4:               t.append(f"anaphora run {m['anaphora_run']}")
    if m["cv"] < 0.50:                        t.append(f"monotone length (cv {m['cv']:.2f})")
    if m["short_ratio"] < 0.10:              t.append(f"no short sentences ({m['short_ratio']:.0%})")
    if m["series3_density"] > 7:             t.append(f"rule-of-three dense ({m['series3_density']}/1k)")
    if m["neg_parallel"] >= 2:               t.append(f"negative parallelism x{m['neg_parallel']}")
    if m["colon_semi_per_sent"] > 0.32:      t.append(f"welded clauses ({m['colon_semi_per_sent']:.2f} :;/sent)")
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
        # vendored mats (now course-scoped under web/nemoclaw/mats/, both .md and .html snapshots)
        # are external reference packets, never authored narrative, so they are excluded by segment.
        if lp.is_mat_path(rel):
            continue
        if suf in (".html", ".htm"):
            if not rel.startswith("web/"):
                continue
        elif suf == ".md":
            if scope != "all" or rel.startswith(("scripts/", "docs/")):
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
    print("  score = 1.5*triads + 1.5*(anaphora-3) + 20*(0.50-cv below) + 5*(0.10-short% below)"
          " + 0.4*(r3/1k over 7) + 6*(:;/sent over 0.32) + 1*(neg-parallel over 1)")
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
        if a.json:
            print(json.dumps(out, indent=2))
        else:
            print(f"score {out['score']}  {m}\n  tells: {out['tells'] or 'none'}")
            if m["sentences"] < 12:
                print(f"  note: only {m['sentences']} sentences; cv and rule-of-three density are noisy "
                      f"on short snippets, so read this as a rough signal, not a verdict")
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
