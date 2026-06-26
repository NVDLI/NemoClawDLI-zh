#!/usr/bin/env python3
"""Deterministic layout/glue validator for the task1 course stack.

Runs a FIXED battery of static checks and exits nonzero naming the exact failing
item. No agent has to "look for" the problem: a check either passes or prints the
precise path that is wrong.

The link check is a LIVE CRAWL of the running lab, which is the only accurate source.
The old static link_graph analyzer was retired because it mis-resolved links and
silently hid whole directories. If the lab is not reachable it is SKIPPED with a
note, never a false pass/fail. The canonical link tool is the self-contained
viewer scripts/runtime/link_graph.html (⟳ Rescan), which crawls the same way in-browser.

Checks
  links     LIVE: every page-link (.md/.ipynb/.html) the lab serves resolves to a
            real served file (jupytext .md<->.ipynb pairing honoured). Best-effort.
  static    every load-bearing /sandbox/dli/... path the lab is configured to serve
            or mount (entrypoint extra_static_paths + root_dir; compose *_SRC=) maps
            to an existing host path. Catches a moved dir that config still points at.
  skills    every SKILL.html beacon matches its directory (delegates to skill_audit).

Usage:
  python3 validate_layout.py            # all checks, human output, exit 1 on failure
  python3 validate_layout.py --quiet    # only print failures
"""
from __future__ import annotations
import argparse, json, re, sys, urllib.request, urllib.parse
from collections import deque
from pathlib import Path

for _p in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
    if (_p / "scripts" / "_bootstrap.py").exists():
        sys.path.insert(0, str(_p / "scripts")); break
from _bootstrap import add_script_paths, find_repo_root

HERE = Path(__file__).resolve()


def _find_task1(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "deploy" / "docker-compose.yml").is_file() or (p / "AGENT_QUICKSTART.md").is_file():
            return p
    return start.parents[1]


TASK1 = _find_task1(HERE)
DLI = "/sandbox/dli"
STATIC_ALLOW_MISSING = ("/sandbox/dli_seed", "/sandbox/dli/workspace/export", "/sandbox/dli/export")
# lab base URLs to try for the live crawl (host -> container)
LAB_URLS = ("http://localhost:8888", "http://127.0.0.1:8888", "http://lab:8888")
PAGE_EXT = (".md", ".ipynb", ".html", ".htm")
SKIP_DIR = {"__pycache__", ".ipynb_checkpoints", "node_modules", "export", "standalone",
            "_paper_cache", "repos_index", "docstore_index", "artifacts", ".pytest_cache",
            "skills-seed", "generated_images", "sample_videos", "_offloaded_tracks", ".git", ".cache",
            "i18n"}   # staged translation content (a copy of web/), validated on its own branch, not here
# static-search roots the lab serves under /lab/static/ (entrypoint extra_static_paths)
STATIC_SUBROOTS = ("web/nemoclaw", "web")


class Result:
    def __init__(self): self.failures = []; self.notes = []
    def fail(self, check, msg): self.failures.append((check, msg))
    def note(self, msg): self.notes.append(msg)
    @property
    def ok(self): return not self.failures


def _container_to_host(p: str):
    if p == DLI:
        return TASK1
    if p.startswith(DLI + "/"):
        return TASK1 / p[len(DLI) + 1:]
    return None


# ── check: links (LIVE crawl of the running lab) ─────────────────────────────
def _lab_base():
    for base in LAB_URLS:
        try:
            urllib.request.urlopen(base + "/lab/api/contents?content=1", timeout=5).read(1)
            return base
        except Exception:
            continue
    return None


def _api(base, path):
    u = base + "/lab/api/contents/" + urllib.parse.quote(path) + "?content=1" if path \
        else base + "/lab/api/contents?content=1"
    try:
        with urllib.request.urlopen(u, timeout=30) as r:
            return json.load(r)
    except Exception:
        return None


def _text(base, path):
    j = _api(base, path)
    if not j:
        return ""
    if j.get("type") == "notebook":
        out = []
        for c in j.get("content", {}).get("cells", []):
            s = c.get("source", "")
            out.append("".join(s) if isinstance(s, list) else (s or ""))
        return "\n\n".join(out)
    c = j.get("content")
    return c if isinstance(c, str) else ""


_HREF = re.compile(r'(?:href|src)\s*=\s*["\']([^"\'#?]+)', re.I)
_MDL = re.compile(r'!?\[[^\]]*\]\(\s*<?([^)\s>]+)')


def _pair(p):
    out = {p}
    if p.endswith(".ipynb"): out.add(p[:-6] + ".md")
    if p.endswith(".md"): out.add(p[:-3] + ".ipynb")
    return out


def _clamp(base_dir, tgt):
    parts = [x for x in base_dir.split("/") if x]
    for seg in tgt.split("/"):
        if seg in ("", "."): continue
        if seg == "..":
            if parts: parts.pop()
        else: parts.append(seg)
    return "/".join(parts)


def check_links(res: Result):
    """Verify every page-link the lab serves resolves to a real served file. This is the check that
    catches a dead link a student would click and hit a 404, after a file was moved or renamed. It
    prefers a LIVE crawl of the running lab (the only fully accurate source); if the lab is down (CI)
    it falls back to the offline projection gate so links are never left unvalidated."""
    base = _lab_base()
    if not base:
        # When the lab is down, fall back to the offline compilation-projection gate so
        # links are ALWAYS validated, including in CI where there is no live lab. The live
        # crawl below is complementary.
        try:
            add_script_paths(TASK1 / "scripts")
            import link_projection as lp
            rep = lp.check(lp.Projection())
            s = rep["stats"]
            res.note(f"links: lab is down, so the OFFLINE projection gate ran over {s['pages']} pages and {s['links']} links")
            blocking = s["blocking_failures"] + s["blocking_asset_leaks"] + s["blocking_cross_course"]
            if blocking:
                res.fail("links", f"{blocking} ship-blocking link issue(s) via offline projection; "
                                  f"run: python3 scripts/runtime/link_projection.py --check")
        except Exception as e:
            res.fail("links", f"lab down AND offline projection fallback failed: {e}")
        return
    files, q, seen = set(), deque([""]), set()
    while q:                                       # BFS over the lab contents API to enumerate every served file
        d = q.popleft()
        if d in seen: continue
        seen.add(d)
        j = _api(base, d)
        if not j or j.get("type") != "directory": continue
        for it in j.get("content", []):
            if it["type"] == "directory":
                if it["name"] not in SKIP_DIR: q.append(it["path"])   # descend, skipping build/cache dirs
            else:
                files.add(it["path"])
    pages = {f for f in files if f.lower().endswith(PAGE_EXT)}   # the pages whose links we will follow

    def in_files(p): return any(v in files for v in _pair(p))   # served? (honour .md<->.ipynb pairing)

    dead = []
    for p in sorted(pages):
        txt = _text(base, p)
        if not txt: continue
        d = "/".join(p.split("/")[:-1])            # the page's own directory, for resolving relative links
        for raw in set(_HREF.findall(txt)) | set(_MDL.findall(txt)):   # every href/src + markdown link
            t = raw.split("#")[0].split("?")[0].strip()
            if not t or t.startswith(("http://", "https://", "mailto:", "//", "data:", "tel:")):
                continue                           # external / non-file targets are out of scope
            if t.startswith("/"):
                m = re.match(r"/lab/(?:lab/)?tree/(.+)", t)
                ms = re.match(r"/lab/static/(.+)", t)
                if m:
                    resv = m.group(1)
                elif ms:
                    cand = [f"{s}/{ms.group(1)}" for s in STATIC_SUBROOTS]
                    resv = next((c for c in cand if in_files(c)), cand[0])
                else:
                    continue  # runtime /lab/svc, /lab/api, etc.
            else:
                resv = _clamp(d, t)                # relative link: resolve against the page's directory
            if resv.lower().endswith(PAGE_EXT) and not in_files(resv):
                dead.append((p, raw))              # a page-link that resolves to nothing the lab serves
    res.note(f"links: live crawl of {base} reached {len(files)} files across {len(pages)} pages")
    if dead:
        res.fail("links", f"{len(dead)} dead page-link(s); first: {dead[:5]}")


# ── check: static/mount paths resolve ────────────────────────────────────────
def _config_paths():
    out = []
    ep = TASK1 / "workspace" / "entrypoint.sh"
    if ep.is_file():
        txt = ep.read_text()
        m = re.search(r"extra_static_paths\s*=\s*'(\[[^']*\])'", txt)
        if m:
            for p in json.loads(m.group(1)):
                out.append((ep.name, p))
        for m in re.finditer(r'root_dir\s*=\s*"([^"]+)"', txt):
            out.append((ep.name, m.group(1)))
    for comp in sorted((TASK1 / "deploy").glob("docker-compose*.yml")):
        for m in re.finditer(r"\b[A-Z_]+_SRC=(/sandbox/dli/[^\s,\"']+)", comp.read_text()):
            out.append((str(comp.relative_to(TASK1)), m.group(1)))
    return out


def check_static(res: Result):
    """Verify every load-bearing static/mount path the lab is configured to serve maps to a real host
    path. This is the check that catches a directory moved or renamed without updating the entrypoint
    or compose config, which would otherwise leave the lab serving (or mounting) nothing at that path."""
    for src, cpath in _config_paths():            # each (config file, /sandbox/dli/... path) it declares
        if any(cpath == a or cpath.startswith(a) for a in STATIC_ALLOW_MISSING):
            continue                              # paths allowed to be absent (seed/export dirs)
        host = _container_to_host(cpath)          # translate the container path to its host location
        if host is None:
            res.fail("static", f"{src}: path '{cpath}' is not under {DLI}")
        elif not host.exists():
            res.fail("static", f"{src}: '{cpath}' -> '{host}' does not exist (moved dir? stale config)")



# -- check: course runtime asset layout ---------------------------------------
def check_course_assets(res: Result):
    """The NemoClaw course runtime has an intentional interface: pages import browser modules
    from web/nemoclaw/scripts/ and styles from web/nemoclaw/styles/. Keep this in the
    layout gate so a future script or asset migration cannot leave a source page pointing at
    the old root-level _shared.js / _style.css paths while the files live elsewhere."""
    course = TASK1 / "web" / "nemoclaw"
    if not course.is_dir():
        return
    required = [
        course / "scripts" / "_shared.js",
        course / "scripts" / "_canvas.js",
        course / "scripts" / "SKILL.html",
        course / "styles" / "_style.css",
        course / "styles" / "_lite_overlay.css",
        course / "styles" / "SKILL.html",
    ]
    for path in required:
        if not path.is_file():
            res.fail("course-assets", f"missing course runtime asset: {path.relative_to(TASK1)}")

    stale = []
    patterns = (
        'href="_style.css"',
        'from "./_shared.js"',
        "from './_shared.js'",
        'src="studio_main.js"',
    )
    for html in sorted(course.glob("*.html")):
        text = html.read_text(errors="ignore")
        for pat in patterns:
            if pat in text:
                stale.append(f"{html.relative_to(TASK1)} still contains {pat}")
    for old in sorted(course.glob("_*.js")) + sorted(course.glob("_*.css")) + [course / "studio_main.js"]:
        if old.exists():
            stale.append(f"old root-level course asset still exists: {old.relative_to(TASK1)}")
    if stale:
        res.fail("course-assets", "; ".join(stale[:8]))



def check_deploy_layout(res: Result):
    """Compose and nginx config belong under deploy/. Keep this in the layout gate so
    future deployment edits do not leak orchestration files back into the release root."""
    required = [
        TASK1 / "deploy" / "SKILL.html",
        TASK1 / "deploy" / "docker-compose.yml",
        TASK1 / "deploy" / "docker-compose.override.yml",
        TASK1 / "deploy" / "docker-compose.deployment.yml",
        TASK1 / "deploy" / "nginx.conf",
    ]
    for path in required:
        if not path.is_file():
            res.fail("deploy-layout", f"missing deployment file: {path.relative_to(TASK1)}")
    stale = [p.name for p in TASK1.glob("docker-compose*.yml")]
    if (TASK1 / "nginx.conf").exists():
        stale.append("nginx.conf")
    if stale:
        res.fail("deploy-layout", "deployment config must live in deploy/: " + ", ".join(sorted(stale)))

def check_skill_asset_coverage(res: Result):
    """Verify assets/SKILL.html and mats/SKILL.html directly link every local file they govern.
    This keeps provenance pages usable as file indexes in the deployed course and catches the
    exact regression where a SKILL page names a class of files without providing direct tabs."""
    import subprocess
    r = subprocess.run([sys.executable, str(TASK1 / "scripts" / "validation" / "skill_asset_coverage.py"), "--quiet"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        lines = [ln.strip() for ln in (r.stdout + "\n" + r.stderr).splitlines() if ln.strip()]
        for line in lines or ["skill_asset_coverage.py failed without output"]:
            res.fail("skill-asset-coverage", line)

def check_skills(res: Result):
    """Verify every SKILL.html beacon still matches its directory, by delegating to scripts/skills/skill_audit.py. A
    drifted beacon (a file listed that no longer exists, or one present but undocumented) means the
    machine-readable directory map an agent ingests first is lying; this surfaces each such mismatch."""
    import subprocess
    r = subprocess.run([sys.executable, str(TASK1 / "scripts" / "skills" / "skill_audit.py")],
                       capture_output=True, text=True)
    if r.returncode != 0:                         # skill_audit exits nonzero and prints each mismatch
        for line in r.stderr.splitlines():
            line = line.strip()
            if line and not line.startswith("skill_audit:"):   # skip its summary line, keep the per-item failures
                res.fail("skills", line)


def main():
    """Run the full fixed battery (links, static paths, skill beacons) and exit nonzero naming each
    failing item. This is the deterministic layout gate: it exists so a broken link, a moved served
    directory, or a drifted SKILL beacon is reported with the exact bad path, not left for someone to
    hunt down. Notes (skips, crawl counts) print on success; failures print to stderr and return 1."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    res = Result()
    check_links(res)                              # dead page-links (live crawl, else offline projection)
    check_static(res)                             # configured static/mount paths that no longer exist
    check_course_assets(res)                      # course runtime scripts/styles interface
    check_deploy_layout(res)                       # compose/nginx isolated under deploy/
    check_skill_asset_coverage(res)               # asset/mat SKILL pages directly link governed files
    check_skills(res)                             # SKILL.html beacons that drifted from their directory

    if not a.quiet:
        for nt in res.notes:
            print(f"  · {nt}")
    if res.ok:
        if not a.quiet:
            print("validate_layout: ✅ all checks pass")
        return 0
    print("validate_layout: ✗ FAILURES", file=sys.stderr)
    for check, msg in res.failures:
        print(f"  [{check}] {msg}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
