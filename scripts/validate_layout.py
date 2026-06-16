#!/usr/bin/env python3
"""Deterministic layout/glue validator for the task1 course stack.

Runs a FIXED battery of static checks and exits nonzero naming the exact failing
item. No agent has to "look for" the problem: a check either passes or prints the
precise path that is wrong.

The link check is a LIVE CRAWL of the running lab, which is the only accurate source.
The old static link_graph analyzer was retired because it mis-resolved links and
silently hid whole directories. If the lab is not reachable it is SKIPPED with a
note, never a false pass/fail. The canonical link tool is the self-contained
viewer scripts/link_graph.html (⟳ Rescan), which crawls the same way in-browser.

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

HERE = Path(__file__).resolve()


def _find_task1(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "docker-compose.yml").is_file() or (p / "AGENT_QUICKSTART.md").is_file():
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
            "skills-seed", "generated_images", "sample_videos", "_offloaded_tracks", ".git", ".cache"}
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
    base = _lab_base()
    if not base:
        # When the lab is down, fall back to the offline compilation-projection gate so
        # links are ALWAYS validated, including in CI where there is no live lab. The live
        # crawl below is complementary.
        try:
            sys.path.insert(0, str(HERE.parent))
            import link_projection as lp
            rep = lp.check(lp.Projection())
            s = rep["stats"]
            res.note(f"links: lab is down, so the OFFLINE projection gate ran over {s['pages']} pages and {s['links']} links")
            blocking = s["blocking_failures"] + s["blocking_asset_leaks"] + s["blocking_cross_course"]
            if blocking:
                res.fail("links", f"{blocking} ship-blocking link issue(s) via offline projection; "
                                  f"run: python3 scripts/link_projection.py --check")
        except Exception as e:
            res.fail("links", f"lab down AND offline projection fallback failed: {e}")
        return
    files, q, seen = set(), deque([""]), set()
    while q:
        d = q.popleft()
        if d in seen: continue
        seen.add(d)
        j = _api(base, d)
        if not j or j.get("type") != "directory": continue
        for it in j.get("content", []):
            if it["type"] == "directory":
                if it["name"] not in SKIP_DIR: q.append(it["path"])
            else:
                files.add(it["path"])
    pages = {f for f in files if f.lower().endswith(PAGE_EXT)}

    def in_files(p): return any(v in files for v in _pair(p))

    dead = []
    for p in sorted(pages):
        txt = _text(base, p)
        if not txt: continue
        d = "/".join(p.split("/")[:-1])
        for raw in set(_HREF.findall(txt)) | set(_MDL.findall(txt)):
            t = raw.split("#")[0].split("?")[0].strip()
            if not t or t.startswith(("http://", "https://", "mailto:", "//", "data:", "tel:")):
                continue
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
                resv = _clamp(d, t)
            if resv.lower().endswith(PAGE_EXT) and not in_files(resv):
                dead.append((p, raw))
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
    for comp in sorted(TASK1.glob("docker-compose*.yml")):
        for m in re.finditer(r"\b[A-Z_]+_SRC=(/sandbox/dli/[^\s,\"']+)", comp.read_text()):
            out.append((comp.name, m.group(1)))
    return out


def check_static(res: Result):
    for src, cpath in _config_paths():
        if any(cpath == a or cpath.startswith(a) for a in STATIC_ALLOW_MISSING):
            continue
        host = _container_to_host(cpath)
        if host is None:
            res.fail("static", f"{src}: path '{cpath}' is not under {DLI}")
        elif not host.exists():
            res.fail("static", f"{src}: '{cpath}' -> '{host}' does not exist (moved dir? stale config)")


def check_skills(res: Result):
    import subprocess
    r = subprocess.run([sys.executable, str(HERE.parent / "skill_audit.py")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        for line in r.stderr.splitlines():
            line = line.strip()
            if line and not line.startswith("skill_audit:"):
                res.fail("skills", line)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    res = Result()
    check_links(res)
    check_static(res)
    check_skills(res)

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
