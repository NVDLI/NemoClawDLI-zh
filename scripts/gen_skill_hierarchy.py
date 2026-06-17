#!/usr/bin/env python3
"""Generate the nested SKILL.html hub hierarchy:

    task1/SKILL.html  (task hub == bundle index, served at /lab/static/SKILL.html)
      ├─ web/SKILL.html  (surface hub)  ─→ each web/<course>/SKILL.html
      └─ cpu/SKILL.html  (surface hub)  ─→ each cpu/<course>/SKILL.html
            └─ <course>/SKILL.html  (course hub) ─→ its content

The root hub is the ONTOLOGY BEACON for the whole bundle: a semantically- and
statically-verifiable interface over its immediate children (execution surfaces,
reference layers, tooling, agent docs), not a pitch for any one course. Every page is
reachable from the task root through its surface + course hub, so the link graph forms
one tree of clusters budding from SKILL hubs. The pages are BOTH a machine-readable
brain (the `skill-meta` JSON block) AND a styled, human-centric web page that matches
the foyer/course aesthetic (NVIDIA dark theme, hero, card grid). Re-runnable; discovers
structure from disk. Hand-authored course SKILLs are NOT overwritten (only files
carrying the generated marker are refreshed).
"""
from __future__ import annotations
import html, json, sys
from pathlib import Path

HERE = Path(__file__).resolve()
TASK1 = HERE.parents[1]
SURFACES = ("web", "cpu")
MARKER = "gen_skill_hierarchy.py"   # presence in a SKILL.html => safe to regenerate

sys.path.insert(0, str(HERE.parent))
try:
    from link_projection import RELEASED   # single source for the released-course set
except Exception:
    RELEASED = ("nemoclaw",)

# Human-facing one-liner for the web bundle's released course. nemoclaw is what the
# release foyer surfaces.
WEB_COURSE_DESC = {
    "nemoclaw":      "Securing Agents: the browser course.",
}
SURFACE_LEAD = {
    "cpu": "The shared microservice stack (llm_client, openclaw, sandbox-admin, docker_router) that the "
           "browser course runs against. Open the service hub below.",
}

# ── Core tenets: the operating creed, projected INTO the brain ──────────────────────────
# This bundle ships no agent-tool config file (no CLAUDE.md or equivalent). The learnings
# that such a file would hold live here, in the root skill-meta, so any agent or person who
# reads SKILL.html inherits them, and `scripts/tenets.py` reports them + their enforcement.
# Keep these tool-agnostic and load-bearing; the gate scripts enforce the checkable ones.
# The `purpose` group is the platform philosophy (what this repo is for); its long form is
# PHILOSOPHY.md. The other groups are engineering discipline.
TENETS = {
    "purpose": [
        "Content is curated once and projected: pages live under web/ and cpu/, and "
        "bundle_standalone.py, build_pages.sh, and engine.js generate the standalone bundle, the "
        "Pages site, and the link graph from them. Add a delivery format by writing a generator, "
        "so a fix to the source reaches every format. PHILOSOPHY.md is the long form.",
        "Anchor each page in a task that runs: build a working artifact a reader executes against "
        "the lab, and cut a page that only fills an outline. The aim is a change in what a reader "
        "can do.",
        "Order is a default, not a gate: keep pages usable out of sequence, with no enforced "
        "prerequisites or knowledge checks, so a reader can act on partial understanding and "
        "return for the next layer.",
        "Keep the release open: Apache 2.0, no gate or paywall, the foyer surfacing only the "
        "released courses, and mats cited by public URL.",
        "Ship the services a course drives (a model gateway, a sandboxed agent runtime, a policy "
        "control plane) and let them carry the mechanical work, so a reader's attention stays on "
        "the decision the exercise is about.",
        "Keep contribution low-barrier with the quality bar held: the content discipline in "
        "QUALITY_DIRECTIVES.md and these tenets. The path is still forming.",
    ],
    "assumptions": [
        "task1 is the canonical root: the open-source, replicable release. Everything worth "
        "keeping lives here and is versioned; scratch goes to /tmp and is never committed.",
        "Content is organized by execution surface: web/ (browser, remote services only) "
        "holds the released course and its course-scoped reference packets under "
        "web/nemoclaw/mats/; cpu/ holds the shared microservice stack it runs against, "
        "with shared repos/, scripts/, and workspace/.",
        "The brain is each directory's SKILL.html skill-meta JSON, not a SKILL.md. Parse it "
        "first, then walk children: task to surface to course to content.",
        "One link engine (scripts/engine.js) is the single source for resolution, crawl, "
        "reachability, and the release contract; it runs headless and in-browser, with no "
        "second implementation to drift.",
        "The released course is nemoclaw (Securing Agents); the foyer "
        "(web/index.html) surfaces only it.",
    ],
    "practices": [
        "Edit content in place; git history is the auditable record. Keep no parallel mirror.",
        "No em-dashes in authored prose: rewrite the construction so a dash was never needed. "
        "Never swap the glyph for a colon, semicolon, comma, or parentheses.",
        "No buzzy marketing cadence: avoid serial antithesis ('not X but Y', 'N X, one Y') and "
        "rule-of-three flourishes.",
        "Code-first: fixing a real code cell beats improving prose beats adding navigation. A "
        "change that teaches nothing new and prevents no bug is not worth making.",
        "Browser courses stay remote-services-only; never put keys in static files.",
        "The course mats/ (web/nemoclaw/mats/) and repos/ are cited-by-URL reference packets: "
        "cite the external URL, never link the packet file.",
        "Never commit lab-generated runtime output (artifacts/, export/, caches, the public/ build).",
    ],
    "cadences": [
        "Validate before pushing: validate_layout, skill_consistency, run_engine --self-test, "
        "validate_bundle --scope ship. The same gates run at pre-push (install: "
        "bash scripts/install-hooks.sh).",
        "A reported defect is a SAMPLE of a class: grep the whole repo across every course, "
        "surface, and duplicated copy before fixing, then fix every instance or name the deferrals.",
        "Improve one, improve all: a fix in one course propagates to its siblings.",
        "When scope is ambiguous, escalate; never truncate. If literal compliance is worse than "
        "the better thing, do the better thing and say so.",
    ],
    "creeds": [
        "Fix corruption markers on sight: apologetic prose, em-dashes, over-documentation, hedge "
        "phrases, deferred-dead questions, stale cross-references, a same-strength evaluation "
        "judge, commented-out runnable code.",
        "Lead-page parity: a later page must not regress from its course's lead page in heading "
        "voice, exercise density, or depth.",
        "Isolation: a course never links another course directly; only shared infra, SKILL hubs, "
        "and bundle-root files may cross.",
        "Trust the artifact over the summary: when your own text disagrees with the file, diff, "
        "or log, re-read the artifact.",
    ],
}


def courses_in(surface: str):
    """(name, skill_href|index_href) for each course dir under a surface."""
    root = TASK1 / surface
    if not root.is_dir():
        return []
    out = []
    for d in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        if (d / "SKILL.html").is_file():
            out.append((d.name, f"{d.name}/SKILL.html"))
        else:
            for cand in ("index.html", "web/index.html"):
                if (d / cand).is_file():
                    out.append((d.name, f"{d.name}/{cand}")); break
    return out


# ONE content bound, and everything flows to it. The <main> container is the single content
# width (a sane rem max that never exceeds the viewport via min(...,100%)); the hero lead, the
# section help, the note, and the card grid ALL fill it, so prose and cards line up at the same
# left+right edge instead of prose sitting in a narrow half-column under a full-width grid. No
# per-element width locks (the previous 800px lead and 68ch measure were exactly that mistake).
# Type scales fluidly (clamp). The only literal px are idioms: 1px borders, the 999px pill, and
# the clamp font floor.
_CSS = """:root{--g:#76b900;--gs:#aee23a;--bg:#0d0d0d;--e1:#161616;--e2:#1e1e1e;--e3:#2a2a2a;
--tx:#f2f2f2;--td:#b0b0b0;--tf:#8a8a8a;--mono:ui-monospace,"SF Mono",Consolas,monospace;
--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
--pad:clamp(1rem,4vw,2rem);--r:.6rem}
*{box-sizing:border-box;margin:0;padding:0}
html{font-size:clamp(15px,0.94rem + 0.25vw,17.5px)}
body{background:var(--bg);color:var(--tx);font-family:var(--sans);line-height:1.6}
a{color:var(--g);text-decoration:none}a:hover{text-decoration:underline}
code{font-family:var(--mono);font-size:.9em;background:var(--e2);padding:.05em .4em;border-radius:.25rem;color:var(--gs)}
.topbar{display:flex;align-items:center;gap:1rem;flex-wrap:wrap;padding:.8rem var(--pad);
background:linear-gradient(180deg,#000,var(--bg));border-bottom:1px solid var(--e3);position:sticky;top:0;z-index:10}
.topbar .logo{font-weight:700;color:var(--g);letter-spacing:.04em}
.topbar .crumb{color:var(--td);font-size:.88rem}.topbar .crumb a{color:var(--td)}
.topbar .spacer{flex:1}
.topbar .badge{font-size:.7rem;font-family:var(--mono);padding:.2rem .6rem;border-radius:999px;
background:var(--e2);border:1px solid var(--e3);color:var(--td)}
main{max-width:min(60rem,100%);margin:0 auto;padding:clamp(1.5rem,4vw,2.5rem) var(--pad) 5rem}
.hero{margin:.4em 0 1.6em}
.hero .eyebrow{font-family:var(--mono);font-size:.72rem;color:var(--gs);text-transform:uppercase;
letter-spacing:.12em;margin-bottom:.6em}
.hero h1{font-size:clamp(1.7rem,1.3rem + 2vw,2.45rem);font-weight:700;line-height:1.12;margin:0 0 .35em;letter-spacing:-.01em}
.hero h1 .accent{color:var(--g)}
.hero p.lead{font-size:1.04rem;color:var(--td)}
.actions{display:flex;gap:.7rem;flex-wrap:wrap;margin:1.3em 0 .2em}
.actions a{display:inline-flex;align-items:center;gap:.45rem;padding:.65rem 1.25rem;border-radius:.55rem;font-weight:600;
font-size:.92rem;border:1px solid var(--e3);background:var(--e2);color:var(--td);transition:.13s}
.actions a:hover{border-color:var(--g);color:var(--gs);text-decoration:none}
.actions a.primary{background:var(--g);color:#000;border-color:var(--g)}.actions a.primary:hover{background:var(--gs)}
.section{margin:2.3em 0 1em}
.section h2{font-size:1.1rem;color:var(--tx);border-bottom:1px solid var(--e3);padding-bottom:.35em;margin-bottom:.3em}
.section .help{font-size:.92rem;color:var(--td);margin:.55em 0 .2em}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(16rem,100%),1fr));gap:clamp(.6rem,1.5vw,1rem);margin-top:.9em}
.card{display:block;background:var(--e1);border:1px solid var(--e3);border-radius:var(--r);padding:.9rem 1rem;transition:.13s}
.card:hover{border-color:var(--g);background:rgba(118,185,0,.05);text-decoration:none;transform:translateY(-1px)}
.card .nm{font-family:var(--mono);font-size:.95rem;color:var(--gs);display:block;margin-bottom:.25em;word-break:break-word}
.card .ds{font-size:.85rem;color:var(--td);line-height:1.5}
.card .st-flag{font-size:.74em;color:#f85149;font-family:var(--mono);margin-left:.4rem}
.note{font-size:.85rem;color:var(--tf);margin-top:2.4em;border-left:3px solid var(--e3);padding:.45em 0 .45em .9rem}
details.fold{margin-top:1.5em;border:1px solid var(--e3);border-radius:var(--r);background:var(--e1);overflow:hidden}
details.fold>summary{cursor:pointer;padding:.7rem 1rem;font-weight:600;color:var(--gs);font-size:.92rem;
list-style:none;display:flex;align-items:center;gap:.6rem}
details.fold>summary::-webkit-details-marker{display:none}
details.fold>summary::before{content:"▸";color:var(--tf);font-size:.8em}
details.fold[open]>summary::before{content:"▾"}
.foldbody{padding:.15rem 1.15rem 1rem;font-size:.9rem;color:var(--td)}
.foldbody h4{color:var(--tx);font-size:.92rem;margin:1.1em 0 .35em}
.foldbody h4:first-child{margin-top:.3em}
.foldbody ul{margin:.4em 0 .7em 1.1em;padding:0}.foldbody li{margin:.35em 0;list-style:disc}
.foldbody li.tight{margin:.22em 0}
.metamap{font-family:var(--mono);font-size:.8rem;color:var(--tf);background:var(--bg);border:1px solid var(--e3);
border-radius:.5rem;padding:.65rem .8rem;margin-top:.7em;overflow:auto;white-space:pre-wrap;line-height:1.5}
.metamap b{color:var(--gs)}
.st-badge{font-family:var(--mono);font-size:.7rem;border-radius:999px;padding:.05rem .6rem;margin-left:auto;
background:var(--e2);border:1px solid var(--e3);color:var(--td)}
.st-badge.ok{color:#3fb950;border-color:#234} .st-badge.warn{color:#d29922} .st-badge.fail{color:#f85149;border-color:#522}
.st-actions{margin:.2em 0 .8em}
.st-actions button{font:inherit;font-size:.82rem;cursor:pointer;background:var(--e2);border:1px solid var(--e3);
color:var(--td);border-radius:.45rem;padding:.3rem .75rem}.st-actions button:hover{border-color:var(--g);color:var(--gs)}
.st-row{display:flex;gap:.5rem;padding:.1rem 0}.st-mark{width:1.1em;flex:0 0 auto}
.st-row.ok{color:var(--td)}.st-row.warn{color:#d2a64a}.st-row.fail{color:#f08a82}
.st-hint{color:var(--tf)}"""


# Self-test harness. Runs in the browser on load (and on the "re-run" button): checks every
# card link on the hub resolves, flags stray SKILL.md links and inconsistencies, and pins a
# ⚠ hint onto any broken card. Raw string so the JS regex backslashes survive verbatim.
_SELFTEST_JS = r'''<script>
(function(){
  var STALE=/SKILL\.md(?:$|["'\s<])/;
  var SKIP=/^(https?:|mailto:|tel:|data:|#)|(AGENT_QUICKSTART|QUALITY_DIRECTIVES|SKILL_CONTRACT)\.md$|(^|\/)docs\//;
  function runSelfTest(){
    var out=document.getElementById("selftest-out"), badge=document.getElementById("st-badge");
    if(!out) return;
    [].forEach.call(document.querySelectorAll(".st-flag"),function(e){e.parentNode&&e.parentNode.removeChild(e);});
    var meta={}; try{ meta=JSON.parse(document.getElementById("skill-meta").textContent); }catch(e){}
    var cards=[].slice.call(document.querySelectorAll("a.card"));
    var kids=(meta.children||[]).map(function(c){return c.path;});
    var rows=[];
    function add(s,l,h){ rows.push({s:s,l:l,h:h||""}); }
    add(meta.node_type?"ok":"warn","skill-meta present"+(meta.level?(" · "+meta.level):""), meta.node_type?"":"missing node_type");
    add(kids.length?"ok":"warn", kids.length+" children declared", kids.length?"":"hub declares no children");
    var seen={},dups=[]; kids.forEach(function(p){ if(seen[p])dups.push(p); seen[p]=1; });
    add(dups.length?"fail":"ok","no duplicate children", dups.length?dups.join(", "):"");
    // normalise a path (collapse ./ and ../) for comparing card hrefs to declared child paths
    function norm(p){ var a=[]; (p||"").split("/").forEach(function(s){ if(s===""||s===".")return; if(s===".."){a.pop();} else a.push(s); }); return a.join("/"); }
    var selfp=meta.self_path||"", dir=selfp.indexOf("/")<0?"":selfp.slice(0,selfp.lastIndexOf("/"));
    // SCOPE: every declared child must live under this hub's own directory (isolation:
    // a hub must not claim a child outside its scope, e.g. a course hub reaching a sibling).
    var outside=kids.filter(function(p){ return dir && norm(p).indexOf(dir+"/")!==0; });
    add(outside.length?"fail":"ok","children scoped under "+(dir||"task root")+"/", outside.length?("out of scope: "+outside.join(", ")):"");
    // CONSISTENCY: every declared child is actually rendered as a card here (skill-meta ↔ DOM).
    var targets={}; cards.forEach(function(a){ var h=a.getAttribute("href")||"";
      if(/^(https?:|mailto:|tel:|#|\/)/.test(h))return; targets[norm((dir?dir+"/":"")+h)]=1; });
    var missing=kids.filter(function(p){ return !targets[norm(p)]; });
    add(missing.length?"fail":"ok","every declared child has a card", missing.length?("no card for: "+missing.join(", ")):"");
    var hrefs=cards.map(function(a){return a.getAttribute("href");}).concat(kids);
    var stale=hrefs.filter(function(h){return h&&STALE.test(h);}); stale=stale.filter(function(h,i){return stale.indexOf(h)===i;});
    add(stale.length?"warn":"ok","no deprecated / stale path patterns", stale.length?stale.join(", "):"");
    var check=cards.filter(function(a){ var h=a.getAttribute("href"); return h && !SKIP.test(h); });
    function paint(){
      var fail=rows.filter(function(r){return r.s==="fail";}).length, warn=rows.filter(function(r){return r.s==="warn";}).length;
      var cls=fail?"fail":(warn?"warn":"ok"), head=fail?("✗ "+fail+" issue"+(fail>1?"s":"")):(warn?("⚠ "+warn+" hint"+(warn>1?"s":"")):"✓ all checks pass");
      if(badge){ badge.className="st-badge "+cls; badge.textContent=head; }
      out.innerHTML=rows.map(function(r){return '<div class="st-row '+r.s+'"><span class="st-mark">'+
        (r.s==="ok"?"✓":(r.s==="warn"?"⚠":"✗"))+'</span><span>'+r.l+(r.h?' <span class="st-hint">· '+r.h+'</span>':'')+'</span></div>';}).join("");
    }
    if(!check.length){ paint(); return; }
    var pending=check.length, broken=0, neterr=0;
    check.forEach(function(a){
      var h=a.getAttribute("href");
      fetch(h,{method:"HEAD",credentials:"same-origin",cache:"no-store"}).then(function(r){
        if(!r.ok){ broken++; flag(a,r.status); }
      })["catch"](function(){ neterr++; }).then(function(){
        if(!--pending){
          if(neterr===check.length) add("warn","link resolution","not checked; open this hub inside the lab to verify");
          else add(broken?"fail":"ok",(check.length-neterr)+" links checked", broken?(broken+" broken; see the ⚠ hints pinned above"):"all resolve");
          paint();
        }
      });
    });
    function flag(a,c){ var s=document.createElement("span"); s.className="st-flag"; s.textContent="⚠ "+c;
      s.title="This link does not resolve ("+c+"). Likely a moved or deprecated page; fix the href in the source."; a.appendChild(s); }
  }
  if(document.readyState!=="loading") runSelfTest(); else window.addEventListener("DOMContentLoaded",runSelfTest);
  document.addEventListener("click",function(e){ if(e.target && e.target.id==="st-run") runSelfTest(); });
})();
</script>'''

_SELFTEST_HTML = """  <details class="fold" open>
    <summary>Self-test <span class="st-badge" id="st-badge">running…</span></summary>
    <div class="foldbody">
      <p style="color:var(--tf);font-size:.84rem;margin:.2em 0 .2em">Runs in your browser on load: every card link
      on this page is fetched, deprecated path patterns + inconsistencies are flagged, and a ⚠ hint is pinned onto
      any broken card above. Fix the source, hit re-run (or reload), and watch the hints clear.</p>
      <div class="st-actions"><button id="st-run" type="button">↻ re-run tests</button></div>
      <div id="selftest-out"></div>
    </div>
  </details>
"""


def _tenets_html(tenets):
    """Render the core-tenets projection (assumptions/practices/cadences/creeds) as prose.
    The same data lives in skill-meta, so scripts/tenets.py can report it and map the
    checkable tenets to the gate that enforces each. No agent-tool config file ships."""
    if not tenets:
        return ""
    label = {"assumptions": "Assumptions (what is true here)",
             "practices": "Practices (how to work)",
             "cadences": "Cadences (the rhythm and the gates)",
             "creeds": "Creeds (the quality bar)"}
    out = ['\n      <h4>Core tenets, projected into this brain</h4>',
           '      <p style="color:var(--tf);font-size:.84rem;margin:.1em 0 .4em">This bundle ships '
           'no agent-tool config file. The operating creed lives here and in <code>skill-meta.tenets</code>; '
           '<code>python3 scripts/tenets.py</code> reports it and names the gate that enforces each.</p>']
    for key in ("assumptions", "practices", "cadences", "creeds"):
        items = tenets.get(key) or []
        if not items:
            continue
        lis = "\n".join(f'        <li class="tight">{html.escape(t)}</li>' for t in items)
        out.append(f'      <p style="margin:.7em 0 .1em;color:var(--gs);font-size:.86rem">{label[key]}</p>'
                   f'\n      <ul>\n{lis}\n      </ul>')
    return "\n".join(out)


def _agent_block(meta, root_prefix):
    r = root_prefix
    is_root = meta.get("level") == "task"
    tenets_html = _tenets_html(meta.get("tenets")) if is_root else ""
    scalars = "  ".join(f"<b>{k}</b>: {html.escape(str(meta[k]))}"
                        for k in ("node_type", "level", "surface", "course", "role", "served_at") if meta.get(k))
    kids = meta.get("children", [])
    kid_lines = "\n".join(f"  • {html.escape(c.get('name', ''))} → {html.escape(c.get('path', ''))}" for c in kids)
    metamap = scalars + (f"\nchildren ({len(kids)}):\n{kid_lines}" if kids else "")

    # The ROOT beacon is the highest-leverage agent page (the first thing read), so it gets a
    # full operating manual; sub-hubs get the scoped contract. This block is the agent directive
    # rendered IN the page; the canonical docs (AGENT_QUICKSTART / SKILL_CONTRACT / QUALITY) are
    # linked at the end.
    root_extra = f"""
      <h4>The ontology in one read</h4>
      <p>An open-source, replicable course release: narrative, assets, the deployment that runs
      them, and the verification that keeps them honest. Organised by <strong>execution
      surface</strong> so each piece declares what it needs to run, <code>web/</code> (browser +
      remote services) holds the released course and its course-scoped reference layer
      (<code>web/nemoclaw/mats/</code>), <code>cpu/</code> the shared microservice stack
      it runs against. <code>scripts/</code> is the tooling,
      <code>workspace/</code> the lab runtime, <code>docker-compose.yml</code> + <code>nginx.conf</code>
      the deployment. This directory is the true root; nothing outside it is referenced from within.</p>
      <h4>Two surfaces: one for students, one for you</h4>
      <ul>
        <li class="tight"><strong>The foyer</strong> (<a href="{r}web/index.html">web/index.html</a>) is the student RELEASE surface: it discovers only the released courses, nothing else.</li>
        <li class="tight"><strong>This beacon</strong> is the agent ONTOLOGY surface: it maps the WHOLE bundle. Parse <code>skill-meta</code>, walk <code>children</code> into the surface hubs, then course hubs, then content.</li>
      </ul>
      <h4>Verify before you trust: one engine, two runtimes</h4>
      <ul>
        <li class="tight">The link graph is ONE engine, <a href="{r}scripts/engine.js">scripts/engine.js</a> (resolution, crawl, reachability, the release contract), run in the browser viewer AND headless via node. No second implementation to drift.</li>
        <li class="tight">Headless: <code>bash scripts/run_engine.sh --check</code> (links + reachability + foyer contract) and <code>--self-test</code> (pinned projection facts). In-browser: <a href="{r}scripts/link_graph.html">link_graph.html</a> (⟳ Rescan).</li>
        <li class="tight">Full cadence + content grounding: <code>python3 scripts/validate_bundle.py --scope ship</code>. The same gates run at pre-push.</li>
      </ul>"""
    contract = f"""
      <h4>Contracts you must keep</h4>
      <ul>
        <li class="tight"><strong>Hierarchy.</strong> task &#8594; surface &#8594; course &#8594; content. Every page buds from a SKILL hub; nothing floats unreached, and the engine flags any real stray.</li>
        <li class="tight"><strong>Isolation.</strong> A course never links another course directly. Only <code>_shared</code> infra, SKILL hubs, and bundle-root files may cross. The course mats (<code>web/nemoclaw/mats/</code>) + <code>repos/</code> are cited-by-URL reference packets: cite the underlying external URL, never link the packet file.</li>
        <li class="tight"><strong>Generated, not hand-edited.</strong> These hubs come from <code>scripts/gen_skill_hierarchy.py</code>. Edit the generator and regenerate, then refresh the viewer snapshot with <code>run_engine.sh --embed</code>. A hand edit here is overwritten.</li>
        <li class="tight"><strong>Source of truth is here.</strong> This directory holds everything worth keeping; scratch goes to <code>/tmp</code>, never committed.</li>
      </ul>
      <h4>Canonical directives</h4>
      <p><a href="{r}README.md">README.md</a> &middot; <a href="{r}AGENT_QUICKSTART.md">AGENT_QUICKSTART.md</a> &middot; <a href="{r}SKILL_CONTRACT.md">SKILL_CONTRACT.md</a> &middot; <a href="{r}QUALITY_DIRECTIVES.md">QUALITY_DIRECTIVES.md</a>.</p>"""
    return f"""  <details class="fold"{' open' if is_root else ''}>
    <summary>For agents &middot; {'operating manual' if is_root else 'directives'} &amp; machine map</summary>
    <div class="foldbody">
      <p>This page is the <strong>brain</strong> for its scope: human prose above, a
      machine-readable <code>skill-meta</code> JSON in the page head (mirrored at the bottom),
      and an auto-running self-test. Agents parse <code>skill-meta</code> first, then read the prose.</p>{root_extra if is_root else ""}{tenets_html}{contract}
      <div class="metamap">{metamap}</div>
    </div>
  </details>
"""


def _actions(actions):
    if not actions:
        return ""
    out = '    <div class="actions">\n'
    for label, href, primary in actions:
        cls = ' class="primary"' if primary else ""
        out += f'      <a{cls} href="{href}">{html.escape(label)}</a>\n'
    return out + "    </div>\n"


def _sections(sections):
    out = ""
    for title, help_html, items in sections:
        out += f'    <div class="section">\n      <h2>{html.escape(title)}</h2>\n'
        if help_html:
            out += f'      <p class="help">{help_html}</p>\n'   # help is trusted HTML (may hold links)
        out += '      <div class="grid">\n'
        for name, href, desc in items:
            ds = f'<span class="ds">{html.escape(desc)}</span>' if desc else ""
            out += f'        <a class="card" href="{href}"><span class="nm">{html.escape(name)}</span>{ds}</a>\n'
        out += "      </div>\n    </div>\n"
    return out


def page(title, eyebrow, lead_html, crumb_html, sections, meta, actions=None, note=None, root_prefix=""):
    note = note or (f"Generated by <code>scripts/{MARKER}</code>. The machine-readable map is the "
                    "<code>skill-meta</code> JSON in this page's head. Hierarchy: task → surface → course → content.")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<script type="application/json" id="skill-meta">
{json.dumps(meta, indent=2)}
</script>
<style>{_CSS}</style></head>
<body>
  <div class="topbar"><span class="logo">NVIDIA DLI</span>
    <span class="crumb">{crumb_html}</span><span class="spacer"></span>
    <span class="badge">skill-meta · {html.escape(meta.get("level", "hub"))}</span></div>
  <main>
    <div class="hero">
      <div class="eyebrow">{html.escape(eyebrow)}</div>
      <h1>{html.escape(title)}</h1>
      <p class="lead">{lead_html}</p>
    </div>
{_actions(actions)}{_sections(sections)}{_agent_block(meta, root_prefix)}{_SELFTEST_HTML}    <p class="note">{note}</p>
  </main>
{_SELFTEST_JS}
</body></html>
"""


def write(path: Path, content: str):
    path.write_text(content); print("wrote", path.relative_to(TASK1))


def gen_task():
    """task1/SKILL.html is the ROOT hub, served at /lab/static/SKILL.html. It is the
    ONTOLOGY BEACON for the whole bundle: an honest, statically-verifiable interface over
    its immediate children (the execution surfaces, the reference layers, the tooling, the
    agent docs), not a pitch for any one course. It descends into the per-surface hubs and
    points humans at the curated release foyer."""
    surfaces = [(s, f"{s}/SKILL.html") for s in SURFACES if (TASK1 / s).is_dir()]
    sdesc = {"web": "Browser frontends: the course as styled web pages, remote services only "
                    "(no local microservices). Assumes only a browser and the lab proxy.",
             "cpu": "The shared microservice stack (llm_client, openclaw, sandbox-admin, docker_router) the browser "
                    "course runs against. Assumes a CPU lab box."}
    items = [(f"{s}/", h, sdesc.get(s, "")) for s, h in surfaces]

    # Reference + infrastructure layers: immediate children of task1/ that are NOT courses.
    # repos/ is a cited-by-URL reference packet set (joined to pages via shared external
    # citations, never linked as files), so it is DESCRIBED, not carded. The mats reference
    # layer is now COURSE-SCOPED under web/nemoclaw/mats/, so it is documented as part of the
    # course rather than as a top-level peer. scripts/ is the tooling; the one card is the
    # static verifier itself, on-theme for a verifiable ontology.
    ref_layers = []
    if (TASK1 / "web" / "nemoclaw" / "mats").is_dir():
        ref_layers.append({"name": "web/nemoclaw/mats", "role": "course-scoped curated reference "
                           "packets; joined to pages by the external URLs they cite and associated "
                           "through the link graph, never linked as files"})
    if (TASK1 / "repos").is_dir():
        ref_layers.append({"name": "repos", "role": "vendored external repositories kept for "
                           "context-sharing and retrieval; not student content"})
    if (TASK1 / "scripts").is_dir():
        ref_layers.append({"name": "scripts", "role": "bundle tooling: the projection engine, the "
                           "link-graph viewer, the validation cadence, this SKILL generator"})
    # describe only the layers that actually exist on disk (ref_layers is dir-gated)
    layers_html = ", ".join(f"<code>{r['name']}/</code>" for r in ref_layers) or "none present"
    ref_help = ("Immediate children of the bundle root that are not courses. "
                + " ".join(f"<code>{r['name']}/</code> {r['role']}." for r in ref_layers))
    ref_items = []
    if (TASK1 / "scripts" / "link_graph.html").is_file():
        ref_items.append(("scripts/link_graph.html", "scripts/link_graph.html",
                          "Link + topology viewer: an honest projection of how every page resolves "
                          "and what reaches a SKILL hub."))

    docs = [("README.md", "README.md", "What the release is and how to run it (start here)."),
            ("AGENT_QUICKSTART.md", "AGENT_QUICKSTART.md", "Agent orientation: layout, services, rules."),
            ("CONTRIBUTING.md", "CONTRIBUTING.md", "How to contribute: hooks, the validation gate, conventions."),
            ("QUALITY_DIRECTIVES.md", "QUALITY_DIRECTIVES.md", "Pedagogical quality bar."),
            ("SKILL_CONTRACT.md", "SKILL_CONTRACT.md", "The SKILL.html beacon spec.")]
    docs = [(n, h, d) for n, h, d in docs if (TASK1 / h).is_file()]
    for p in (sorted((TASK1 / "docs").glob("*.md")) if (TASK1 / "docs").is_dir() else []):
        docs.append((f"docs/{p.name}", f"docs/{p.name}", ""))

    # The release foyer is the CURATED student entry: it surfaces only the released courses
    # (RELEASED). This beacon documents the whole ontology; the foyer ships a subset.
    rel_courses = [c for c in RELEASED if (TASK1 / "web" / c).is_dir()]
    actions = [("Open the release foyer →", "web/index.html", True)]
    if (TASK1 / "web" / "nemoclaw" / "01a-loop.html").is_file():
        actions.append(("Securing Agents", "web/nemoclaw/01a-loop.html", False))

    meta = {"node_type": "hub", "level": "task", "title": "Building Agents · NVIDIA DLI bundle",
            "role": "bundle_index", "served_at": "/lab/static/SKILL.html", "self_path": "SKILL.html",
            "thesis": ("NVIDIA DLI's open-source, replicable release of course material: the narrative, "
                       "the assets, the agent-friendly deployment that runs it, and the automatic "
                       "verification that keeps it honest, packaged so a person or an agent can stand it "
                       "up, navigate it, and check it end to end. Content is organized by EXECUTION SURFACE "
                       "(web / cpu) so each piece declares what it needs to run; every page buds from "
                       "a SKILL hub, so the whole bundle is statically and semantically verifiable."),
            "surfaces": [{"name": s, "path": f"{s}/SKILL.html", "assumes": sdesc.get(s, "")} for s, _ in surfaces],
            "reference_layers": ref_layers,
            "release": {"surface": "web/index.html", "courses": rel_courses,
                        "note": "the foyer surfaces only these released courses; this beacon maps the whole bundle"},
            "tenets": TENETS,
            "children": [{"name": s, "path": f"{s}/SKILL.html"} for s, _ in surfaces]}

    write(TASK1 / "SKILL.html",
          page("Building Agents · NVIDIA DLI bundle", "BUNDLE INDEX · /lab/static/SKILL.html",
               "NVIDIA DLI's open-source, replicable release of course material: the narrative, the "
               "assets, the agent-friendly deployment that runs it, and the automatic verification that "
               "keeps it honest. The root is organised by execution surface, so each piece declares what "
               "it needs to run. "
               "The browser course lives under <code>web/</code> (remote services only), and the shared "
               "microservice stack it runs against lives under <code>cpu/</code>. "
               f"Alongside the surfaces sit the reference and tooling layers ({layers_html}). "
               "Every page buds from a SKILL hub, so the whole tree is "
               'statically and semantically verifiable. Students enter through the curated '
               '<a href="web/index.html">release foyer</a>; this page is the full map for an agent.',
               "task1 (root)",
               [("Execution surfaces", "Each surface declares its environment assumptions; open a "
                 "surface hub to reach its courses.", items),
                ("Reference & infrastructure layers", ref_help, ref_items),
                ("Agent docs", "Operating docs for agents working in this repo "
                 "(shipped in git, not seeded into the student lab image).", docs)],
               meta, actions=actions))


def gen_surface(surface: str):
    cs = courses_in(surface)
    items = [(n, h, WEB_COURSE_DESC.get(n, "")) for n, h in cs] if surface == "web" \
        else [(f"{n}/", h, "") for n, h in cs]
    sections = [("Courses", None, items)]
    if surface == "web":   # the web surface also hosts the bundle's landing pages + LMS navigators
        landing = [(n, n, d) for n, d in
                   [("index.html", "Human entry: the release course picker."),
                    ("courses.html", "Catalog redirect stub.")]
                   if (TASK1 / "web" / n).is_file()]
        if landing:
            sections.append(("Landing pages", None, landing))
        nav = [(n, f"../scripts/{n}", d) for n, d in
               [("edx_navigator_quick.html", "Course LMS navigator."),
                ("edx_getting_started.html", "LMS getting-started page.")]
               if (TASK1 / "scripts" / n).is_file()]
        if nav:
            sections.append(("LMS navigators", None, nav))
    lead = ("The browser frontends: each course rendered as styled web pages, remote services only."
            if surface == "web" else SURFACE_LEAD.get(surface, f"Courses on the {surface} surface."))
    meta = {"node_type": "hub", "level": "surface", "surface": surface, "title": f"{surface} surface",
            "self_path": f"{surface}/SKILL.html",
            "children": [{"name": n, "path": f"{surface}/{h}"} for n, h in cs]}
    write(TASK1 / surface / "SKILL.html",
          page(f"{surface}/ · surface hub", f"SURFACE HUB · {len(cs)} COURSES",
               lead, '<a href="../SKILL.html">task1</a> / ' + surface,
               sections, meta, root_prefix="../"))


def gen_web_course_hubs():
    """Web courses (frontends) often lack a SKILL.html. Give each a styled course hub so the
    web surface follows the task→surface→course→content shape. Refreshes only its own generated
    hubs (marker check); never clobbers a hand-authored course SKILL."""
    web = TASK1 / "web"
    if not web.is_dir():
        return
    for d in sorted(p for p in web.iterdir() if p.is_dir() and not p.name.startswith(".")):
        sk = d / "SKILL.html"
        if sk.is_file() and MARKER not in sk.read_text():
            continue
        # NON-NAV files (authoring tools) and BUILD-OUTPUT dirs are served on disk but are NOT
        # part of the navigable SKILL graph (engine.js graphNavigable + SKIP_DIR drop them). The
        # hub must not card them, or it emits links the live crawl reports as dead.
        NON_NAV = {"studio.html", "link_graph.html"}
        flat = [p for p in d.glob("*.html") if not p.name.startswith("_") and p.name not in NON_NAV]
        nested = [p for p in (d / "web").glob("*.html")] if (d / "web").is_dir() else []
        edx = sorted((d / "edx").glob("*.html")) if (d / "edx").is_dir() else []
        shared_docs = sorted((d / "_shared").glob("*.md")) if (d / "_shared").is_dir() else []
        # Sub-collection launchers (e.g. slides/index.html): a subdir's index.html is the hub
        # FOR that collection and links every page inside it, so linking the launcher from the
        # course hub pulls the whole collection into the SKILL tree in one edge. Without this a
        # collection (decks + their speaker scripts) is a detached cluster with no SKILL path.
        # SKIP_SUB excludes delivery/asset/build dirs (standalone is regenerated bundle output).
        SKIP_SUB = {"edx", "web", "_shared", "assets", "scripts", "_tools",
                    "standalone", "node_modules", "__pycache__", ".ipynb_checkpoints"}
        subindex = sorted(p for p in d.glob("*/index.html")
                          if p.parent.name not in SKIP_SUB and not p.parent.name.startswith((".", "_")))
        primary = sorted(flat or nested)
        pages = primary + subindex + edx + shared_docs
        if not pages:
            continue

        def _label(p):
            return p.parent.name if p.name == "index.html" else p.stem

        sections = [("Pages", None, [(p.stem, p.relative_to(d).as_posix(), "") for p in primary])]
        if subindex:
            sections.append(("Collections", "Sub-collections with their own launcher; open one to "
                             "reach every page inside it.",
                             [(_label(p), p.relative_to(d).as_posix(), "") for p in subindex]))
        if edx:
            sections.append(("edX delivery", None, [(p.stem, p.relative_to(d).as_posix(), "") for p in edx]))
        if shared_docs:
            sections.append(("Shared", None, [(p.stem, p.relative_to(d).as_posix(), "") for p in shared_docs]))
        meta = {"node_type": "hub", "level": "course", "surface": "web", "course": d.name,
                "self_path": f"web/{d.name}/SKILL.html",
                "children": [{"name": _label(p), "path": p.relative_to(TASK1).as_posix()} for p in pages]}
        lead = WEB_COURSE_DESC.get(d.name, f"The {d.name} browser course, {len(primary)} pages.")
        write(sk, page(f"web/{d.name} · course hub", f"COURSE HUB · {len(primary)} PAGES",
                       lead, '<a href="../SKILL.html">web</a> / ' + d.name, sections, meta, root_prefix="../../"))


if __name__ == "__main__":
    gen_web_course_hubs()          # web course hubs first, so the bundle index can link them
    gen_task()
    for s in SURFACES:
        if (TASK1 / s).is_dir():
            gen_surface(s)
