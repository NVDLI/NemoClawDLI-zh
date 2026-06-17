#!/usr/bin/env python3
"""Auto-runnable validation cadence for the task1 bundle. This is the single CI entrypoint.

Composes the deterministic validators into one gate and writes a DURABLE static log
(the "failures-to-get" record) so an agent / CI / the DGX-spark watcher can read the
current health without a live lab:

  1. link_projection --check (ship scope)  → virtual-link failures-to-get + asset leaks
  2. validate_layout.py                     → static mount paths, notebooks, SKILL beacons
  3. grounding.py                           → em-dash / ungrounded / mat-association sweep
  4. prose_variety.py                       → sentence-variety + buzz signals over the narrative
  5. reachability, foyer-release, page-audit (via link_projection)

Each suite also runs standalone for detail, e.g. `python3 scripts/prose_variety.py`.

Exit 0 iff there are no SHIP-blocking link failures AND validate_layout passes. Breakage
outside the shipped surface (anything that is not the released nemoclaw course or its shared
infra) is LOGGED as advisory and never blocks the gate.

Outputs (overwritten each run, committable as "current known state"):
  docs/validation/latest.json   full machine report (blocking + advisory)
  docs/validation/latest.md     human summary

Usage:
  python3 scripts/validate_bundle.py            # gate + write log
  python3 scripts/validate_bundle.py --scope all  # gate on the whole tree, not just shipped (strict)
  python3 scripts/validate_bundle.py --no-write   # gate only, no log file
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve()
SCRIPTS = HERE.parent
TASK1 = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
import link_projection as lp  # noqa: E402
import grounding as gr  # noqa: E402
import prose_variety as pv  # noqa: E402


def _git_sha() -> str:
    try:
        return subprocess.run(["git", "-C", str(TASK1), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip() or "?"
    except Exception:
        return "?"


def run(scope: str = "ship", write: bool = True, stamp: str | None = None) -> int:
    proj = lp.Projection(TASK1)
    rep = lp.check(proj)
    s = rep["stats"]

    # validate_layout (static mount paths + notebooks + SKILL beacons; live-links skip if lab down)
    vl = subprocess.run([sys.executable, str(SCRIPTS / "validate_layout.py"), "--quiet"],
                        capture_output=True, text=True)
    vl_ok = vl.returncode == 0
    vl_fail = [ln for ln in vl.stdout.splitlines() + vl.stderr.splitlines()
               if ln.strip().startswith("[")]

    try:
        reach = lp.reachability(proj)
    except Exception as e:
        reach = {"pages": 0, "reachable": 0, "strays": [], "real_strays": -1, "expected_strays": -1}
        vl_fail.append(f"reachability error: {e}")

    # release-foyer contract: the foyer surfaces only RELEASED courses. This is ship-blocking
    # because the foyer IS the release surface, so leaking an unreleased course onto it is a real defect.
    try:
        foyer = lp.foyer_release_check(proj)
    except Exception as e:
        foyer = {"ok": False, "released": list(lp.RELEASED), "surfaced_courses": [],
                 "violations": [{"kind": "error", "detail": str(e)}]}
        vl_fail.append(f"foyer release check error: {e}")
    foyer_ok = foyer.get("ok", False)

    # per-.html drift audit (every page auto-verifies through the engine: stale tokens, missing
    # assets, skill-meta / foyer-release contract drift). Advisory: surfaced, never ship-blocking.
    try:
        audit = lp.page_audit(proj)
    except Exception as e:
        audit = {"pages": 0, "pages_with_findings": -1, "findings": []}
        vl_fail.append(f"page audit error: {e}")

    block = s["blocking_failures"] + s["blocking_asset_leaks"] + s["blocking_cross_course"]
    total = s["failures"] + s["asset_leaks"] + s["cross_course"]
    gate_block = block if scope == "ship" else total
    ok = gate_block == 0 and vl_ok and foyer_ok

    # grounding reference sweep (fast, no-llm). Folds the em-dash / ungrounded / cross
    # signals into the durable log so the cadence reflects content health, not just links.
    try:
        grecs = gr.sweep(None, scope, limit=None, force=False)
        gfind = gr._findings(grecs)
        ungrounded = sum(1 for fo in gfind if any("ungrounded" in i for i in fo["issues"]))
        emdash = sum(1 for fo in gfind if any("em-dash" in i for i in fo["issues"]))
        mat_assoc = {r["path"]: r["reference"]["mat_assoc"]
                     for r in grecs if r.get("reference", {}).get("mat_assoc")}
    except Exception as e:                       # grounding must never silently pass the gate
        grecs, gfind, ungrounded, emdash, mat_assoc = [], [], -1, -1, {}
        vl_fail.append(f"grounding sweep error: {e}")

    # prose variety (deterministic, advisory): rank the authored narrative by machine-uniformity
    # (sentence-length spread, staccato triads, enumeration, welded clauses) so monotone pages surface.
    try:
        pv_rows = pv.sweep(scope)
        pv_flagged = [r for r in pv_rows if r["flagged"]]
    except Exception as e:
        pv_rows, pv_flagged = [], []
        vl_fail.append(f"prose variety error: {e}")

    advisory = (total - gate_block) + len(gfind) + max(0, reach.get("real_strays", 0)) \
        + max(0, audit.get("pages_with_findings", 0)) + len(pv_flagged)

    summary = {
        "generated": stamp or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": _git_sha(), "scope": scope, "ok": ok,
        "link_stats": s, "validate_layout_ok": vl_ok, "validate_layout_failures": vl_fail,
        "grounding": {"pages": len(grecs), "findings": len(gfind),
                      "ungrounded": ungrounded, "em_dash_pages": emdash,
                      "mat_associated": len(mat_assoc)},
        "reachability": reach,
        "foyer_release": foyer,
        "page_audit": audit,
        "prose_variety": {"pages": len(pv_rows), "flagged": len(pv_flagged), "flag_at": pv.FLAG_AT,
                          "flagged_pages": [{"path": r["path"], "score": r["score"], "tells": r["tells"]}
                                            for r in pv_flagged]},
        "advisory_total": advisory,
        "report": rep,
    }

    print(f"validate_bundle [{summary['git_sha']}] scope={scope}")
    print(f"  links: {s['pages']} pages / {s['links']} links")
    print(f"  failures-to-get : {s['failures']} (blocking {s['blocking_failures']})")
    print(f"  asset leaks     : {s['asset_leaks']} (blocking {s['blocking_asset_leaks']})")
    print(f"  cross-course    : {s['cross_course']} (blocking {s['blocking_cross_course']})")
    print(f"  validate_layout : {'OK' if vl_ok else 'FAIL ' + '; '.join(vl_fail[:3])}")
    print(f"  grounding       : {len(gfind)} pages w/ issues "
          f"(ungrounded {ungrounded}, em-dash {emdash}) over {len(grecs)} pages")
    print(f"  reachability    : {reach['reachable']}/{reach['pages']} pages reach a SKILL hub; "
          f"strays {len(reach['strays'])} ({reach['real_strays']} real, {reach['expected_strays']} expected-detached)")
    print(f"  foyer release   : {'OK' if foyer_ok else 'FAIL'} (surfaces {foyer.get('surfaced_courses', [])}; "
          f"released {foyer.get('released', [])})")
    for v in foyer.get("violations", []):
        print(f"    ✗ foyer {v.get('kind')}: {v.get('detail')}")
    print(f"  page audit      : {audit.get('pages_with_findings', '?')}/{audit.get('pages', '?')} .html show drift "
          f"(stale tokens / missing assets / contract)")
    if pv_rows:
        print(f"  prose variety   : {len(pv_flagged)}/{len(pv_rows)} narrative pages flagged for a rhythm pass"
              + (f" (worst: {pv_rows[0]['path'].split('/')[-1]} @ score {pv_rows[0]['score']})" if pv_flagged else ""))
    if not ok:
        for x in (rep["failures"] + rep["asset_leaks"] + rep["cross_course"]):
            if scope == "all" or x.get("ship"):
                print(f"    ✗ {x['page']} -> {x.get('link')}  ({x.get('reason','leak/cross')})")

    if write:
        out = TASK1 / "docs" / "validation"
        out.mkdir(parents=True, exist_ok=True)
        (out / "latest.json").write_text(json.dumps(summary, indent=2))
        (out / "latest.md").write_text(_render_md(summary))
        # mat-association obs artifact: page -> {mat: [shared citation URLs]}. The link
        # graph reads this to draw page<->mat grounding edges (request: associate via URL).
        (out / "mat_association.json").write_text(json.dumps(
            {"generated": summary["generated"], "pages_associated": len(mat_assoc),
             "association": mat_assoc}, indent=2))
        # single source for the viewer: refresh the embedded DATA snapshot in link_graph.html
        # so its offline default reflects current reality (the in-lab Rescan still overrides).
        lp.embed_snapshot(proj)
        print(f"  wrote docs/validation/latest.{{json,md}} plus mat_association.json "
              f"and the link_graph.html snapshot (via engine.js)")

    # honest verdict: "clean" ONLY when nothing is outstanding. A passing ship gate with
    # advisory items left over is reported as PASS-BUT-NOT-CLEAN, never "all good".
    if not ok:
        verdict = "✗ FAIL. Ship-blocking issues are listed above."
    elif advisory > 0:
        verdict = f"ship gate PASS · ⚠ NOT CLEAN. {advisory} advisory issue(s) logged; see docs/validation/latest.md."
    else:
        verdict = "✅ clean. No blocking and no advisory issues."
    print(f"validate_bundle: {verdict}")
    print("  detail: docs/validation/latest.md   ·   single suite, e.g.: python3 scripts/prose_variety.py")
    return 0 if ok else 1


def _render_md(summary: dict) -> str:
    s = summary["link_stats"]
    rep = summary["report"]
    g = summary.get("grounding", {})
    rc = summary.get("reachability", {})
    fy = summary.get("foyer_release", {})
    pa = summary.get("page_audit", {})
    adv = summary.get("advisory_total", 0)
    if not summary["ok"]:
        gate = "✗ FAIL (ship-blocking)"
    elif adv > 0:
        gate = f"PASS but NOT CLEAN: {adv} advisory issue(s)"
    else:
        gate = "✅ clean"
    L = [f"# Bundle validation · {summary['generated']}  ·  `{summary['git_sha']}`",
         "", f"**Gate ({summary['scope']} scope): {gate}**", "",
         "| metric | total | blocking |", "|---|---|---|",
         f"| failures-to-get | {s['failures']} | {s['blocking_failures']} |",
         f"| asset leaks | {s['asset_leaks']} | {s['blocking_asset_leaks']} |",
         f"| cross-course | {s['cross_course']} | {s['blocking_cross_course']} |",
         f"| grounding issues | {g.get('findings','?')} | advisory |",
         f"| · ungrounded pages | {g.get('ungrounded','?')} | advisory |",
         f"| · em-dash pages | {g.get('em_dash_pages','?')} | advisory |",
         f"| prose variety (narrative pages flagged) | {summary.get('prose_variety',{}).get('flagged','?')} / {summary.get('prose_variety',{}).get('pages','?')} | advisory |",
         f"| strays (unreachable from a SKILL hub) | {len(rc.get('strays',[]))} | {rc.get('real_strays','?')} real |",
         f"| release foyer (surfaces only RELEASED) | {'OK' if fy.get('ok') else 'FAIL'} | {len(fy.get('violations',[]))} blocking |",
         f"| page audit (.html drift) | {pa.get('pages_with_findings','?')} / {pa.get('pages','?')} | advisory |",
         f"| validate_layout | {'OK' if summary['validate_layout_ok'] else 'FAIL'} | |", ""]

    # per-.html drift audit: each page auto-verified against the engine (stale tokens, missing
    # assets, skill-meta / foyer-release contract). Advisory, but it is how drift gets caught.
    L.append(f"## Page audit (.html drift): {pa.get('pages_with_findings', 0)} of {pa.get('pages', 0)} pages")
    if pa.get("findings"):
        for pf in pa["findings"][:60]:
            for fnd in pf.get("findings", []):
                L.append(f"- `{pf['page']}` **{fnd.get('kind')}**: {fnd.get('detail') or fnd.get('asset') or fnd.get('token','')}")
    else:
        L.append("\nNo drift: every audited page passes stale-token, asset, and contract checks.")
    L.append("")

    # release-foyer contract: the foyer is the student-facing release surface; it must
    # discover ONLY the released courses. A violation is ship-blocking, not advisory.
    L.append(f"## Release foyer (surfaces {fy.get('surfaced_courses', [])}; released {fy.get('released', [])})")
    if fy.get("violations"):
        L.append("\n_contract broken (ship-blocking)_:")
        for v in fy["violations"]:
            L.append(f"- **{v.get('kind')}**: {v.get('detail')}")
    else:
        L.append("\nContract honored: the foyer discovers exactly the released courses.")
    L.append("")

    def section(title, items, fmt):
        block = [x for x in items if x.get("ship")]
        adv = [x for x in items if not x.get("ship")]
        L.append(f"## {title}: {len(block)} blocking, {len(adv)} advisory")
        for label, group in (("blocking", block), ("advisory", adv)):
            if not group:
                continue
            L.append(f"\n_{label}_:")
            for x in group[:40]:
                L.append(f"- {fmt(x)}")
            if len(group) > 40:
                L.append(f"- … {len(group) - 40} more")
        L.append("")

    section("Failures-to-get", rep["failures"],
            lambda x: f"`{x['page']}` → `{x.get('link')}`  _{x.get('reason','')}_")
    section("Asset leaks (cross-contamination)", rep["asset_leaks"],
            lambda x: f"`{x['page']}` ({x['src_course']}) → `{x['link']}` ({x['tgt_course']}); isolate: {x.get('isolate','')}")
    section("Cross-course links", rep["cross_course"],
            lambda x: f"`{x['page']}` ({x['src_course']}) → `{x['link']}` ({x['tgt_course']})")

    # strays: pages no SKILL hub leads to. REAL = a content page that should be in the
    # hierarchy (a navigation gap). EXPECTED = mats / corpus data / demo internals / skill
    # configs / generated reports, which are detached by design and surfaced for honesty not action.
    sset = rc.get("strays", [])
    real = [x for x in sset if not x.get("expected")]
    exp = [x for x in sset if x.get("expected")]
    L.append(f"## Strays (unreachable from a SKILL hub): {len(real)} real, {len(exp)} expected-detached")
    if real:
        L.append("\n_real (a navigation gap; no hub path leads here)_:")
        for x in real[:40]:
            L.append(f"- `{x['page']}` ({x['course']}): {x['reason']}")
    if exp:
        L.append(f"\n_expected-detached (mats / data / demo internals / skill configs / generated)_:")
        for x in exp[:15]:
            L.append(f"- `{x['page']}`")
        if len(exp) > 15:
            L.append(f"- … {len(exp) - 15} more")
    L.append("")

    # prose variety: narrative pages that read machine-uniform (monotone length, staccato triads,
    # enumeration, welded clauses). Advisory; it points at pages to give a rhythm pass, not verdicts.
    pvd = summary.get("prose_variety", {})
    L.append(f"## Prose variety (machine-uniformity; advisory): {pvd.get('flagged', 0)} of {pvd.get('pages', 0)} narrative pages flagged")
    if pvd.get("flagged_pages"):
        L.append(f"\n_at or above score {pvd.get('flag_at')}; `python3 scripts/prose_variety.py` for the full ranked table_:")
        for r in pvd["flagged_pages"][:20]:
            L.append(f"- `{r['path']}` score {r['score']}: {'; '.join(r['tells'])}")
    else:
        L.append("\nNo page is over the rhythm threshold. Full ranked metrics: `python3 scripts/prose_variety.py`.")
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scope", choices=["ship", "all"], default="ship")
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--stamp", help="ISO timestamp to embed (for reproducible CI logs)")
    a = ap.parse_args()
    return run(scope=a.scope, write=not a.no_write, stamp=a.stamp)


if __name__ == "__main__":
    sys.exit(main())
