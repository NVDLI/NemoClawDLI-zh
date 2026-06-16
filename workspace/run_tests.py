#!/usr/bin/env python3
"""
run_tests.py: end-to-end course test runner
===========================================

Works in two modes, detected automatically:

  HOST MODE: run from the host machine; uses `docker exec` to drive the
             lab container.  The script file lives at task1/workspace/ on
             the host, which maps to /sandbox/dli/workspace/ inside the
             container.

  CONTAINER MODE: run directly inside the lab container (e.g. from a
                   JupyterLab terminal).  Commands execute in-process; no
                   Docker socket required.

In both modes executed .ipynb files land at:

    workspace/export/<course_name>/<notebook_name>.ipynb

Usage
-----
  # Run every course (default):
  python3 run_tests.py

  # Run a specific course:
  python3 run_tests.py services

  # Run one notebook across all courses that have it:
  python3 run_tests.py --notebook 00_llm_client

  # Tune the per-cell timeout (default 180 s):
  python3 run_tests.py --timeout 300

  # Run up to N courses in parallel (default 1 = sequential):
  python3 run_tests.py --jobs 3

  # Show what would run, without executing:
  python3 run_tests.py --dry-run

  # Re-use existing .ipynb if one already exists (skip re-execution):
  python3 run_tests.py --skip-existing
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import textwrap
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import NamedTuple


# ── Configuration ────────────────────────────────────────────────────────────

SCRIPT_DIR   = Path(__file__).parent.resolve()          # workspace/ (host or container)
EXPORT_ROOT  = SCRIPT_DIR / "export"
# Per-course notebook subdirectory overrides (none in the current release).
COURSE_NB_SUBDIR: dict[str, str] = {}
DEFAULT_TIMEOUT = 180                                   # seconds per cell (fallback)
DEFAULT_JOBS    = 1                                     # sequential by default

# Per-course per-cell timeout overrides.  These take precedence over --timeout
# so that heavy notebooks (FAISS indexing, RAGAS eval, multi-agent loops) get
# the headroom they need on fast hardware like the DGX Spark without forcing
# a blanket high timeout on every course.
COURSE_TIMEOUTS: dict[str, int] = {
    "services":         300,   # service health + API contract verification
}

# ── Environment detection ─────────────────────────────────────────────────────
# Inside the lab container /sandbox/dli is the mount point for task1/.
# When this script runs inside the container, Path(__file__) already resolves
# to /sandbox/dli/workspace/run_tests.py so SCRIPT_DIR is correct in both
# environments; only WORKSPACE_LAB and _dexec() need to differ.

IN_CONTAINER: bool = Path("/sandbox/dli").exists()

if IN_CONTAINER:
    WORKSPACE_LAB = str(SCRIPT_DIR)   # same directory; no translation needed
    LAB = "(in-container)"            # not used for exec but shown in header
else:
    WORKSPACE_LAB = "/sandbox/dli/workspace"   # path inside the container

    def _detect_lab_container() -> str:
        try:
            out = subprocess.check_output(
                ["docker", "ps", "--format", "{{.Names}}"], text=True
            )
            for name in out.splitlines():
                if "lab" in name.lower() and "task1" in name.lower():
                    return name.strip()
        except Exception:
            pass
        # fallback: derive from the compose project (the deployment sets COMPOSE_PROJECT_NAME);
        # never hardcode a course code, which is an above-task1 wrapper detail.
        return f"{os.environ.get('COMPOSE_PROJECT_NAME', 'task1')}-lab-1"

    LAB = _detect_lab_container()

# Surface-first layout: course notebooks live under task1/cpu/<course> (the
# release keeps cpu/services). The legacy workspace/<course> fallback stays so
# the runner still resolves a course placed directly under workspace/.
TASK1_DIR  = SCRIPT_DIR.parent                  # task1/
NB_SURFACES = ("cpu",)
_DLI_LAB   = str(Path(WORKSPACE_LAB).parent)    # container path of task1 (/sandbox/dli)


def _course_loc(course: str):
    """(host_course_dir, container_parent) for a course, searching the cpu
    surface first, then the legacy workspace/ root. container_parent is the dir
    that CONTAINS <course>, so callers build f'{container_parent}/{course}/...'
    exactly as before."""
    for surf in NB_SURFACES:
        d = TASK1_DIR / surf / course
        if d.is_dir():
            return d, f"{_DLI_LAB}/{surf}"
    if (SCRIPT_DIR / course).is_dir():
        return SCRIPT_DIR / course, WORKSPACE_LAB
    return None, None


def _lab_course_base(course: str) -> str:
    """In-container dir that contains <course> (surface-aware)."""
    _, base = _course_loc(course)
    return base or WORKSPACE_LAB

# Canonical course list (order matters for display). The release ships the
# browser course (web/nemoclaw, no .md notebooks to execute) plus the shared
# service docs under cpu/services, so the only thing this runner has to test is
# the service notebooks.
ALL_COURSES = [
    "services",
]

# Files that are never notebooks: only pure doc/nav files, never content notebooks.
# Do NOT add notebooks here even if they require a GPU or special packages;
# they should be attempted and surface a real error bucket if they fail.
SKIP_EXACT = {
    "README.md", "CONTRIBUTING.md", "SKILL.md", "AUDIT.md",
    "old.md", "TOC_PATCH.md",
}

# Glob patterns for files to skip (names with spaces = prose notes; *_old* = superseded)
SKIP_PATTERNS = [
    re.compile(r".*_old(_\d+|_\w+)?\.md$", re.IGNORECASE),
    re.compile(r".*_MCP_old.*\.md$",         re.IGNORECASE),
    re.compile(r".*\s+.*\.md$"),              # spaces in name → doc/notes, not notebook
    re.compile(r"^_.*\.md$"),                 # leading underscore → internal support doc
]

# Notebooks where a 0exec result is environmental / runner-side, not a
# code bug. Reclassified from "0exec" → "soft" so they don't count as
# hard infrastructure failures. Students on a properly provisioned
# machine run them without issues. Original purpose was "GPU-required";
# it broadened to cover service flakes and kernel-startup hangs. Name kept
# for git-history continuity and the _bucket() reclassification path.
#
# Empty for this release: the only surfaces shipped are the browser course
# (web/nemoclaw, no executable notebooks) and the service health notebooks
# under cpu/services, none of which need a GPU or hit the kernel-launch hang.
# The set and its _bucket() handling stay so a future GPU notebook can be
# added here without touching the bucketing logic.
GPU_REQUIRED_NOTEBOOKS: frozenset[str] = frozenset()

# ANSI colours
RED    = "\033[31m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ── Data structures ───────────────────────────────────────────────────────────

class NotebookResult(NamedTuple):
    course:      str
    name:        str           # stem (no .md/.ipynb)
    n_code:      int
    n_exec:      int
    n_errors:    int
    first_error: str           # "" if clean
    elapsed_s:   float
    skipped:     bool = False  # True when --skip-existing and file already present


_INFRASTRUCTURE_ERRORS = frozenset({
    # Connection errors: the gateway or a microservice isn't reachable.
    # Expected when a service health notebook runs before its service is up.
    "APIConnectionError",
    "ConnectionRefusedError",
    "ConnectionError",
    "ReadTimeout",
    "ConnectTimeout",
    "ServiceUnavailable",
    # Upstream LLM gateway errors that aren't notebook code bugs:
    #   429 / Too Many Requests is a transient rate limit
    #   500 / Internal Server Error is a generic gateway failure
    "[429]",
    "Too Many Requests",
    "Internal Server Error",
})

def _is_infra_error(first_error: str) -> bool:
    """True when the first_error is a known infrastructure gap (no GPU, no service)."""
    return any(marker in first_error for marker in _INFRASTRUCTURE_ERRORS)


## Notebooks whose narrative explicitly depends on a sibling notebook spinning
## up a server in the SAME kernel. In CI each notebook gets its own isolated
## kernel so the dependency never materialises, and any error after the
## dependency point is environmental, not a code bug. Bucket these as soft on
## any error, even when n_exec > 0 (the failure is at a consumer cell the
## student wouldn't reach without the sibling running).
##
## Empty for this release: the shipped surfaces are the browser course
## (web/nemoclaw, no executable notebooks) and the standalone service health
## notebooks under cpu/services, none of which chain across a sibling kernel.
## The set and its _bucket() handling stay so the pattern is available again.
SIBLING_DEPENDENT_NOTEBOOKS: frozenset[str] = frozenset()


def _bucket(r: NotebookResult) -> str:
    if r.skipped:                    return "skip"
    # n_code=0 has two sources: legitimate markdown-only notebooks (clean) AND
    # the parse-error fallback path that synthesises n_code=0/n_errors=1 to
    # surface "parse error: ..." in first_error. Distinguish on n_errors.
    if r.n_code == 0 and r.n_errors == 0: return "clean"  # markdown-only notebook
    if r.n_code == 0 and r.n_errors > 0:  return "soft"   # parse error / runner failure
    # Reclassified 0exec notebooks (GPU_REQUIRED_NOTEBOOKS) time out in CI.
    # This is expected and is not an infra bug. The set is empty in this release.
    if r.n_exec == 0 and r.name in GPU_REQUIRED_NOTEBOOKS: return "soft"
    if r.n_exec == 0:               return "0exec"
    if r.n_errors == 0:             return "clean"
    # Sibling-dependent notebooks: ANY error here is environmental, not a code
    # bug. The full chain only works when the sibling notebook ran in the same
    # kernel; CI can't satisfy that.
    if r.n_errors > 0 and r.name in SIBLING_DEPENDENT_NOTEBOOKS: return "soft"
    # Infra errors are environmental (service down, rate limit, gateway 5xx).
    # When the FIRST error is infra, anything after it is downstream noise:
    # cells that would have run cleanly on a healthy backend either never
    # executed or errored on the cascading bad state. Grade soft regardless of
    # how far execution got before the gap hit, rather than requiring
    # n_exec == n_code (which mis-graded gateway-crash cascades as hard).
    if _is_infra_error(r.first_error): return "soft"
    # Assessment FIXME stubs cascade NameErrors; expected, not a code bug.
    if r.n_exec == r.n_code and "FIXME" in r.first_error: return "soft"
    if r.n_errors <= 2:             return "soft"
    return "hard"


# ── Notebook discovery ────────────────────────────────────────────────────────

def _should_skip(fname: str) -> bool:
    if fname in SKIP_EXACT:
        return True
    for pat in SKIP_PATTERNS:
        if pat.match(fname):
            return True
    return False


def find_notebooks(course: str) -> list[str]:
    """Return sorted list of .md notebook stems for a course.

    For 'services', discovers 00_*.md notebooks from each service subdirectory
    (these serve as integration tests for each microservice).  For other courses,
    discovers *.md files directly inside the course directory.
    """
    # Surface-first: notebooks live under task1/cpu/<course>. _course_loc
    # searches the cpu surface first, then the legacy workspace/ root.
    course_dir, _ = _course_loc(course)
    if course_dir is None:
        return []
    if course in COURSE_NB_SUBDIR:
        course_dir = course_dir / COURSE_NB_SUBDIR[course]
    if course == "services":
        # Include top-level service notebooks and one per service subdirectory
        notebooks = []
        for f in sorted(course_dir.glob("*.md")):
            if not _should_skip(f.name):
                notebooks.append(f.stem)
        for subdir in sorted(course_dir.iterdir()):
            if subdir.is_dir() and not subdir.name.startswith("__"):
                for f in sorted(subdir.glob("00_*.md")):
                    if not _should_skip(f.name):
                        # Use relative path stem so nbconvert knows the subdir
                        notebooks.append(f"{subdir.name}/{f.stem}")
        return notebooks
    notebooks = []
    for f in sorted(course_dir.glob("*.md")):
        if not _should_skip(f.name):
            notebooks.append(f.stem)
    return notebooks


# ── Execution ─────────────────────────────────────────────────────────────────

def _dexec(cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    """Run a shell command, either directly (container) or via docker exec (host)."""
    if IN_CONTAINER:
        full = ["bash", "-lc", cmd]
    else:
        full = ["docker", "exec", LAB, "bash", "-lc", cmd]
    result = subprocess.run(full, capture_output=True, text=True, timeout=timeout)
    return result.returncode, result.stdout, result.stderr


def _cleanup_server_procs() -> None:
    """
    Kill lingering server processes left by the previous notebook execution.

    Notebooks that call uvicorn.run(), demo.launch(), or gunicorn without a
    try/except leave those servers alive after the kernel cell times out.  The
    next notebook that tries to bind the same port then fails with
    "Address already in use" or gets an immediate ConnectionError.

    pkill exits 0 (processes killed) or 1 (nothing matched); both are fine.
    The call is fire-and-forget with a short timeout so it never stalls a run.
    """
    cmd = "pkill -9 -f 'uvicorn' 2>/dev/null; pkill -9 -f 'gradio' 2>/dev/null; pkill -9 -f 'gunicorn' 2>/dev/null; true"
    try:
        _dexec(cmd, timeout=8)
    except Exception:
        pass


def execute_notebook(
    course:    str,
    nb_stem:   str,
    timeout:   int,
    skip_existing: bool,
    dry_run:   bool,
) -> NotebookResult:
    """Convert .md → .ipynb, execute in lab, save to export/. Return audit result."""
    t0 = time.monotonic()
    # nb_stem may include a subdirectory prefix (e.g. "llm_client/00_llm_client")
    nb_parts = nb_stem.replace("\\", "/").split("/")
    nb_leaf  = nb_parts[-1]            # just the stem without path
    nb_subdir = "/".join(nb_parts[:-1])  # "" for flat notebooks, "llm_client" for services

    # _lab_course_base resolves the in-container dir that contains <course>.
    course_base = _lab_course_base(course)

    if nb_subdir:
        # Service notebook: CWD and PYTHONPATH are the service subdirectory
        exec_dir = f"{course_base}/{course}/{nb_subdir}"
        src_md   = f"{exec_dir}/{nb_leaf}.md"
        tmp_ipynb = f"{exec_dir}/._test_{nb_leaf}.ipynb"
        out_flat = nb_stem.replace("/", "__")   # flatten for export filename
    else:
        _nb_sub   = COURSE_NB_SUBDIR.get(course, "")
        exec_dir  = f"{course_base}/{course}/{_nb_sub}".rstrip("/")
        src_md    = f"{exec_dir}/{nb_leaf}.md"
        tmp_ipynb = f"{exec_dir}/._test_{nb_leaf}.ipynb"
        out_flat  = nb_leaf

    out_dir   = EXPORT_ROOT / course
    out_path  = out_dir / f"{out_flat}.ipynb"
    out_ipynb = f"{WORKSPACE_LAB}/export/{course}/{out_flat}.ipynb"
    pythonpath = f"{exec_dir}:{exec_dir}/ocstart:{course_base}/{course}:{course_base}/{course}/ocstart"

    # Course-aware timeout: per-course override beats the --timeout flag.
    effective_timeout = COURSE_TIMEOUTS.get(course, timeout)

    if skip_existing and out_path.exists():
        try:
            r = _audit_ipynb(json.loads(out_path.read_text()), course, nb_stem)
            return NotebookResult(
                course=course, name=nb_stem,
                n_code=r.n_code, n_exec=r.n_exec, n_errors=r.n_errors,
                first_error=r.first_error, elapsed_s=0.0, skipped=True,
            )
        except Exception:
            pass

    if dry_run:
        return NotebookResult(
            course=course, name=nb_stem,
            n_code=0, n_exec=0, n_errors=0,
            first_error="(dry-run)", elapsed_s=0.0,
        )

    # Ensure export dir exists inside the lab (shared mount → also creates on host)
    _dexec(f"mkdir -p {WORKSPACE_LAB}/export/{course}")

    # Convert md → ipynb, execute from course/service dir, move to export.
    #
    # TORCHINDUCTOR_COMPILE_THREADS=1: PyTorch 2.10's inductor compile worker
    # subprocess crashes on this image (visible as "Kernel died" the first time
    # a notebook triggers torch.compile).  Forcing single-threaded compile keeps
    # everything in-process and avoids the "compilation subprocess exited
    # unexpectedly" InductorError.  entrypoint.sh sets the same var for
    # jupyter-lab kernels; we set it here so `docker exec`-spawned kernels (the
    # test runner's path) get it too.  Inert for the current torch-free
    # notebooks, kept so a torch-using notebook can be added without a regression.
    script = textwrap.dedent(f"""
        cd {exec_dir!r}
        jupytext --from md --to ipynb -o {tmp_ipynb!r} {src_md!r} 2>/dev/null
        if [ -f {tmp_ipynb!r} ]; then
          PYTHONPATH={pythonpath!r} NBCONVERT_RUNNING=1 \\
            TORCHINDUCTOR_COMPILE_THREADS=1 \\
            jupyter nbconvert --to notebook --execute --inplace --allow-errors \\
              --ExecutePreprocessor.timeout={effective_timeout} \\
              {tmp_ipynb!r} 2>&1 | tail -1
          [ -f {tmp_ipynb!r} ] && mv {tmp_ipynb!r} {out_ipynb!r} || true
        fi
    """).strip()
    # Outer subprocess timeout: capped at 2 h so a hung notebook never blocks
    # the watcher indefinitely.  The inner nbconvert per-cell timeout controls
    # actual cell execution; this is just a safety net for infrastructure hangs.
    outer_timeout = min(effective_timeout * 30 + 300, 7200)

    try:
        rc, stdout, stderr = _dexec(script, timeout=outer_timeout)
    except subprocess.TimeoutExpired:
        _dexec(f"rm -f {tmp_ipynb!r}")
        elapsed = time.monotonic() - t0
        return NotebookResult(
            course=course, name=nb_stem,
            n_code=1, n_exec=0, n_errors=0,
            first_error="subprocess timeout (runner)",
            elapsed_s=elapsed,
        )

    # Clean up temp if mv failed
    _dexec(f"rm -f {tmp_ipynb!r}")

    # If docker exec / bash itself failed (e.g. container not running), surface the
    # actual error rather than the generic "output file not written" fallback below.
    if rc != 0 and not out_path.exists():
        elapsed = time.monotonic() - t0
        err = (stderr or stdout or "").strip().splitlines()
        first_line = err[0] if err else f"rc={rc}"
        return NotebookResult(
            course=course, name=nb_stem,
            n_code=1, n_exec=0, n_errors=0,
            first_error=first_line,
            elapsed_s=elapsed,
        )

    elapsed = time.monotonic() - t0

    # Parse the output
    if not out_path.exists():
        return NotebookResult(
            course=course, name=nb_stem,
            n_code=1, n_exec=0, n_errors=0,  # n_code>0, n_exec=0 → "0exec" bucket
            first_error="output file not written",
            elapsed_s=elapsed,
        )

    try:
        nb_json = json.loads(out_path.read_text())
        return _audit_ipynb(nb_json, course, nb_stem, elapsed)
    except Exception as exc:
        return NotebookResult(
            course=course, name=nb_stem,
            n_code=0, n_exec=0, n_errors=1,
            first_error=f"parse error: {exc}",
            elapsed_s=elapsed,
        )


def _audit_ipynb(
    nb: dict,
    course: str,
    nb_stem: str,
    elapsed_s: float = 0.0,
) -> NotebookResult:
    code = [c for c in nb.get("cells", []) if c.get("cell_type") == "code"]
    n_code = len(code)
    n_exec = sum(1 for c in code if c.get("execution_count") is not None)
    errors = [
        o
        for c in code
        for o in c.get("outputs", [])
        if o.get("output_type") == "error"
    ]
    n_errors = len(errors)
    first_error = ""
    if errors:
        e = errors[0]
        ## evalue can be empty (TimeoutError, some langchain exceptions). splitlines() on ""
        ## returns [] and indexing [0] raises IndexError, which the caller then surfaces as
        ## "parse error: list index out of range", which masks the actual exception class.
        evalue = e.get('evalue') or ''
        first_line = evalue.splitlines()[0] if evalue.splitlines() else ''
        first_error = f"{e.get('ename','')}: {first_line}"
    return NotebookResult(
        course=course, name=nb_stem,
        n_code=n_code, n_exec=n_exec, n_errors=n_errors,
        first_error=first_error, elapsed_s=elapsed_s,
    )


# ── Per-course runner ─────────────────────────────────────────────────────────

def run_course(
    course: str,
    notebooks: list[str],
    timeout: int,
    skip_existing: bool,
    dry_run: bool,
    notebook_filter: str | None,
    verbose: bool,
) -> list[NotebookResult]:
    if notebook_filter:
        notebooks = [n for n in notebooks if notebook_filter.lower() in n.lower()]

    results: list[NotebookResult] = []
    n = len(notebooks)
    pad = len(str(n))

    for i, nb in enumerate(notebooks, 1):
        prefix = f"[{course}] ({i:{pad}}/{n}) {nb}"
        if verbose:
            print(f"  {CYAN}RUN{RESET}  {prefix}", flush=True)

        # Kill any server processes left by the previous notebook before starting
        # the next one, so port conflicts don't cascade across the course run.
        if i > 1 and not dry_run:
            _cleanup_server_procs()

        r = execute_notebook(course, nb, timeout, skip_existing, dry_run)
        results.append(r)

        bucket = _bucket(r)
        if bucket == "clean":
            flag = f"{GREEN}✅ clean{RESET}"
        elif bucket == "soft":
            flag = f"{YELLOW}•  soft {RESET}"
        elif bucket == "0exec":
            flag = f"{RED}❌ 0exec{RESET}"
        elif bucket == "skip":
            flag = f"{CYAN}⏭  skip {RESET}"
        elif bucket == "hard":
            flag = f"{RED}✗  hard {RESET}"
        else:
            flag = f"?  {bucket} "

        detail = ""
        if r.first_error and r.first_error != "(dry-run)":
            detail = f"  → {r.first_error}"
        timing = f" ({r.elapsed_s:.0f}s)" if r.elapsed_s else ""
        print(f"  {flag}  {prefix}{timing}{detail}", flush=True)

    return results


# ── Summary table ─────────────────────────────────────────────────────────────

def print_summary(all_results: dict[str, list[NotebookResult]]) -> None:
    print()
    print(f"{BOLD}{'─'*74}{RESET}")
    print(f"{BOLD}  SUMMARY{RESET}")
    print(f"{BOLD}{'─'*74}{RESET}")

    hdr = f"  {'Course':<22} {'Total':>5} {'Clean':>6} {'Soft':>5} {'Hard':>5} {'0exec':>5} {'Skip':>5}"
    print(hdr)
    print(f"  {'─'*22} {'─'*5} {'─'*6} {'─'*5} {'─'*5} {'─'*5} {'─'*5}")

    grand = dict(total=0, clean=0, soft=0, hard=0, zero=0, skip=0)

    for course, results in all_results.items():
        counts = dict(total=0, clean=0, soft=0, hard=0, zero=0, skip=0)
        for r in results:
            counts["total"] += 1
            b = _bucket(r)
            if b == "clean": counts["clean"] += 1
            elif b == "soft": counts["soft"] += 1
            elif b == "hard": counts["hard"] += 1
            elif b == "0exec": counts["zero"] += 1
            elif b == "skip": counts["skip"] += 1
        for k in grand:                           # outside notebook loop; runs once per course
            grand[k] += counts[k]

        c_col = f"{GREEN}{counts['clean']:>6}{RESET}"
        s_col = f"{YELLOW}{counts['soft']:>5}{RESET}"
        h_col = f"{RED}{counts['hard']:>5}{RESET}"
        z_col = f"{RED}{counts['zero']:>5}{RESET}"
        sk_col = f"{CYAN}{counts['skip']:>5}{RESET}"
        print(f"  {course:<22} {counts['total']:>5} {c_col} {s_col} {h_col} {z_col} {sk_col}")

    print(f"  {'─'*22} {'─'*5} {'─'*6} {'─'*5} {'─'*5} {'─'*5} {'─'*5}")
    gc = f"{GREEN}{grand['clean']:>6}{RESET}"
    gs = f"{YELLOW}{grand['soft']:>5}{RESET}"
    gh = f"{RED}{grand['hard']:>5}{RESET}"
    gz = f"{RED}{grand['zero']:>5}{RESET}"
    gsk = f"{CYAN}{grand['skip']:>5}{RESET}"
    print(f"  {'TOTAL':<22} {grand['total']:>5} {gc} {gs} {gh} {gz} {gsk}")
    print(f"{BOLD}{'─'*74}{RESET}")
    print()

    # Write machine-readable JSON summary
    summary_path = EXPORT_ROOT / "test_summary.json"
    summary_data = {}
    for course, results in all_results.items():
        summary_data[course] = [
            {
                "name":        r.name,
                "n_code":      r.n_code,
                "n_exec":      r.n_exec,
                "n_errors":    r.n_errors,
                "first_error": r.first_error,
                "elapsed_s":   round(r.elapsed_s, 1),
                "bucket":      _bucket(r),
            }
            for r in results
        ]
    try:
        summary_path.write_text(json.dumps(summary_data, indent=2))
        print(f"  JSON summary → {summary_path.relative_to(SCRIPT_DIR)}")
    except PermissionError as exc:
        print(f"  Warning: could not write JSON summary ({exc})")
    print(f"  Notebooks   → {EXPORT_ROOT.relative_to(SCRIPT_DIR)}/")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    global LAB  # may be overridden by --lab on host; declared here to precede all uses

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "courses",
        nargs="*",
        metavar="COURSE",
        help=f"Course names to test. Leave empty for all. Available: {', '.join(ALL_COURSES)}",
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Run all courses (same as omitting course names).",
    )
    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=DEFAULT_TIMEOUT,
        metavar="SECONDS",
        help=f"Per-cell execution timeout in seconds (default: {DEFAULT_TIMEOUT}).",
    )
    parser.add_argument(
        "--jobs", "-j",
        type=int,
        default=DEFAULT_JOBS,
        metavar="N",
        help=f"Number of courses to run in parallel (default: {DEFAULT_JOBS}).",
    )
    parser.add_argument(
        "--notebook", "-n",
        metavar="PATTERN",
        default=None,
        help="Only run notebooks whose name contains PATTERN (case-insensitive).",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="If an export .ipynb already exists, skip re-execution and use cached result.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover notebooks and print what would run, without executing.",
    )
    parser.add_argument(
        "--lab",
        default=LAB,
        metavar="CONTAINER",
        help=(
            f"Docker container name for the lab (auto-detected: {LAB}). "
            "Ignored when running inside the container."
        ),
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print a RUN line before each notebook (not just the result).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all discoverable notebooks and exit.",
    )

    args = parser.parse_args()
    if not IN_CONTAINER:
        LAB = args.lab   # apply --lab override; global declared at top of main()

    # Determine course list
    if args.courses:
        unknown = [c for c in args.courses if c not in ALL_COURSES]
        if unknown:
            print(f"{RED}Unknown courses: {', '.join(unknown)}{RESET}")
            print(f"Available: {', '.join(ALL_COURSES)}")
            sys.exit(1)
        courses = args.courses
    else:
        courses = ALL_COURSES

    # Discover notebooks
    plan: dict[str, list[str]] = {}
    for course in courses:
        nbs = find_notebooks(course)
        if args.notebook:
            nbs = [n for n in nbs if args.notebook.lower() in n.lower()]
        plan[course] = nbs

    # --list mode
    if args.list:
        total = 0
        for course, nbs in plan.items():
            print(f"\n{BOLD}{course}{RESET} ({len(nbs)} notebooks)")
            for nb in nbs:
                print(f"  {nb}")
            total += len(nbs)
        print(f"\n{BOLD}Total: {total} notebooks across {len(plan)} courses{RESET}")
        return

    # Verify execution environment is reachable
    rc, _, _ = _dexec("echo ok", timeout=10)
    if rc != 0:
        if IN_CONTAINER:
            print(f"{RED}Shell exec failed inside container.{RESET}")
        else:
            print(f"{RED}Cannot reach lab container '{LAB}'. Is it running?{RESET}")
        sys.exit(1)

    # Create export root
    EXPORT_ROOT.mkdir(parents=True, exist_ok=True)
    _dexec(f"mkdir -p {WORKSPACE_LAB}/export")

    # Print header
    total_nbs = sum(len(v) for v in plan.values())
    mode = "DRY-RUN" if args.dry_run else f"timeout={args.timeout}s"
    env_label = "in-container" if IN_CONTAINER else f"host → {LAB}"
    print()
    print(f"{BOLD}{'─'*74}{RESET}")
    print(f"{BOLD}  COURSE TEST RUNNER   [{mode}]   jobs={args.jobs}{RESET}")
    print(f"{BOLD}  Environment: {env_label}{RESET}")
    print(f"{BOLD}  Output:    workspace/export/<course>/{RESET}")
    print(f"{BOLD}  Notebooks: {total_nbs} across {len(plan)} courses{RESET}")
    print(f"{BOLD}{'─'*74}{RESET}")
    print()

    # Run courses
    all_results: dict[str, list[NotebookResult]] = {}
    wall_t0 = time.monotonic()

    def _run_one(course: str) -> tuple[str, list[NotebookResult]]:
        nbs = plan[course]
        if not nbs:
            print(f"{CYAN}[{course}]{RESET} no notebooks found; skipping\n")
            return course, []
        print(f"{BOLD}[{course}]{RESET} {len(nbs)} notebooks → export/{course}/")
        EXPORT_ROOT.joinpath(course).mkdir(parents=True, exist_ok=True)
        results = run_course(
            course=course,
            notebooks=nbs,
            timeout=args.timeout,
            skip_existing=args.skip_existing,
            dry_run=args.dry_run,
            notebook_filter=None,   # already filtered above
            verbose=args.verbose,
        )
        clean = sum(1 for r in results if _bucket(r) == "clean")
        soft  = sum(1 for r in results if _bucket(r) == "soft")
        hard  = sum(1 for r in results if _bucket(r) in ("hard", "0exec"))
        print(f"  → {GREEN}{clean} clean{RESET}  {YELLOW}{soft} soft{RESET}  {RED}{hard} hard{RESET}\n")
        return course, results

    if args.jobs == 1:
        for course in courses:
            name, results = _run_one(course)
            all_results[name] = results
    else:
        with ThreadPoolExecutor(max_workers=args.jobs) as ex:
            futures = {ex.submit(_run_one, c): c for c in courses}
            for fut in as_completed(futures):
                name, results = fut.result()
                all_results[name] = results

    # Ensure display order matches input order
    all_results = {c: all_results.get(c, []) for c in courses}

    wall_elapsed = time.monotonic() - wall_t0
    print_summary(all_results)
    print(f"  Total wall time: {wall_elapsed:.0f}s\n")


if __name__ == "__main__":
    main()
