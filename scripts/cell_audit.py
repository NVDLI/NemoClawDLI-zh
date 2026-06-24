#!/usr/bin/env python3
"""Minimal bars for the runnable cells (every mountCanvasFlow/mountRunCell `code:`).

A good cell is transparent (a model call surfaces its work via the house logger or a
raw-request <details>, not silence), uses helpers.log not console.* (which students
never see), and is correct: awaited model calls, keys from helpers.getKey() not inlined,
no blocking dialog. Flags cells below that bar. Advisory.

Run:  python3 scripts/cell_audit.py
"""
from __future__ import annotations
import re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEB = HERE.parent / "web"

# A cell's code field: `code:` then a backtick literal (may hold escaped \` from nesting).
CODE = re.compile(r"code:\s*`((?:\\.|[^`\\])*)`", re.S)
# Cell-only API (helpers./ctx.view) belongs in a runnable cell, never a static <pre>.
SCRIPT_RE = re.compile(r"<script\b.*?</script>", re.S | re.I)
PRE_RE = re.compile(r"<pre\b.*?</pre>", re.S | re.I)
CELL_API = re.compile(r"\bhelpers\.|\bctx\.view\b")

MODEL_CALL = re.compile(r"(?<![\w.])(chat|chatStream)\s*\(|\.\s*stream\s*\(", re.I)
# Any one of these clears the transparency bar: house logger, view method, maze, artifact, or return.
# A returned value counts because the cell panel renders it.
# An unsuppressed chatStream also streams into the panel.
SURFACE = re.compile(
    r"\blog\s*\(|\blog\.|helpers\.log|ctx\.view|\.view\.|view\.(token|reasoning|usage|tool|warn|html)"
    r"|\binfo\s*\(|\bshow\s*\(|\.html\s*\(|mountChatUI|runMaze|\breturn\s+\S", re.I)
CONSOLE = re.compile(r"\bconsole\s*\.\s*(log|error|warn|info|debug)\b")
DIALOG = re.compile(r"\b(alert|confirm)\s*\(|\bwindow\s*\.\s*prompt\s*\(|document\s*\.\s*write\s*\(")
INLINE_KEY = re.compile(r"nvapi-(?!…|123|FAKE|xxx|redacted|FILL|YOUR)[A-Za-z0-9_-]{8,}")


def strip_noise(c: str) -> str:
    """Blank strings + comments so `chat(` in either isn't read as a call.
    Strings first, so a // inside a string (a URL) can't eat the line."""
    c = re.sub(r'"(?:\\.|[^"\\])*"', '""', c)
    c = re.sub(r"'(?:\\.|[^'\\])*'", "''", c)
    c = re.sub(r"/\*.*?\*/", " ", c, flags=re.S)
    c = re.sub(r"//[^\n]*", " ", c)
    return c


def is_awaited(code: str, call_start: int) -> bool:
    """Is this model call awaited (or returned to a caller that will)? An un-awaited async call in a
    cell resolves to a Promise the student never sees, so the cell silently does nothing on Run.
    Looks back a short window for `await`, or a `return`/`=>` that hands the promise on."""
    pre = code[max(0, call_start - 48):call_start]   # the text just before the call
    return ("await" in pre) or bool(re.search(r"(return|=>)\s*$", pre.strip()))


def audit_page(path: Path):
    """Check every runnable cell on one page against the cell contract. This catches the cells that
    would frustrate or mislead a student: a model call that prints nothing, console.* output they
    never see, an un-awaited call that no-ops, a blocking alert/confirm, a real API key baked into the
    cell, and cell-only API left in a non-editable <pre>. Returns the finding lists run() merges."""
    text = path.read_text(errors="ignore")
    rel = str(path.relative_to(WEB.parent))
    opaque, console, unawaited, dialog, key = [], [], [], [], []
    for m in CODE.finditer(text):                 # each `code:` cell literal on the page
        code = m.group(1)
        clean = strip_noise(code)                 # blank strings/comments so keywords inside them are ignored
        calls = list(MODEL_CALL.finditer(clean))
        if calls and not SURFACE.search(clean):   # makes a model call but never surfaces its output
            snippet = clean[calls[0].start():calls[0].start() + 40].replace("\n", " ")
            opaque.append((rel, snippet.strip()))
        for cm in CONSOLE.finditer(clean):        # console.* output the student cannot see
            console.append((rel, cm.group(0)))
        for cm in calls:
            if not is_awaited(clean, cm.start()):  # async model call left un-awaited (silently no-ops)
                unawaited.append((rel, clean[cm.start():cm.start() + 32].replace("\n", " ").strip()))
        for dm in DIALOG.finditer(clean):         # blocking alert/confirm/prompt/document.write
            dialog.append((rel, dm.group(0)))
        for km in INLINE_KEY.finditer(code):   # keys live in string literals, so scan raw
            key.append((rel, km.group(0)[:14] + "..."))
    # cell-only API shown in a static <pre> (not a runnable cell)
    body = SCRIPT_RE.sub("", text)
    static = [(rel, "static <pre> uses cell-only API (helpers./ctx.view); should be a runnable, editable cell")
              for pm in PRE_RE.finditer(body) if CELL_API.search(pm.group(0))]
    # Editable cells need CodeMirror core, javascript mode, and editor CSS.
    # Otherwise the cell falls back to a plain, unhighlighted textarea.
    unhighlighted = []
    if re.search(r"mountRunCell\s*\(|mountCanvasFlow\s*\(", text):
        miss = [n for n, ok in (
            ("CodeMirror core js", bool(re.search(r"codemirror(?:\.min)?\.js", text, re.I))),
            ("javascript mode",    "mode/javascript" in text.lower()),
            ("editor css",         bool(re.search(r"codemirror(?:\.min)?\.css", text, re.I))),
        ) if not ok]
        if miss:
            unhighlighted.append((rel, "editable cells but the syntax highlighter is not loaded (missing: "
                                  + ", ".join(miss) + "); the editor falls back to a plain, unhighlighted textarea"))
    return opaque, console, unawaited, dialog, key, static, unhighlighted



def audit_runtime_contract():
    """Guard the shared learner-facing cell UI against regressions that make code dominate again.
    This intentionally checks the runtime contract, not a validator tag: students should see results
    first, reveal code only when they ask or when an error points at a line, and reset one cell or node
    without rebuilding the whole page."""
    src = (WEB / "nemoclaw" / "_canvas.js").read_text(errors="ignore")
    findings = []

    def need(ok: bool, msg: str):
        if not ok:
            findings.append(("web/nemoclaw/_canvas.js", msg))

    rc_out = src.find('class="rc-out"')
    rc_code = src.find('class="rc-code-det"')
    need(rc_out >= 0 and rc_code >= 0 and rc_out < rc_code,
         "run-cell output must render before the code editor so results are visible without scrolling through code")
    need(not re.search(r'<details class="rc-code-det"[^>]*\sopen\b', src),
         "run-cell code must be collapsed by default; open it on demand or on error")
    need(not re.search(r'<details class="rc-schemas-det"[^>]*\sopen\b', src),
         "run-cell schemas must be collapsed by default; schema plumbing should not lead the lesson")
    need('class="rc-reset"' in src and "function resetCell" in src,
         "run-cells need a per-cell Reset that restores original code/schema and clears output")
    need('class="cf-panel-reset"' in src and "function resetNode" in src,
         "canvas-flow nodes need per-node Reset so one step can be restored without resetting the whole flow")
    need('if (codeDet && !codeDet.open) codeDet.open = true;' in src,
         "run-cell errors should open the code panel when a failing line is marked")
    return findings

def run(verbose=True):
    """Driver: audit every numbered lesson page's runnable cells and aggregate the findings. It exists
    so the gate and a reviewer get one accounting of cells that violate the runnable-cell contract.
    Returns the finding lists; the report and exit code are derived from them."""
    pages = sorted((WEB / "nemoclaw").glob("0*.html"))   # the numbered lesson pages carry the runnable cells
    opaque, console, unawaited, dialog, key, static, unhi = [], [], [], [], [], [], []
    ui_contract = audit_runtime_contract()
    for p in pages:
        o, c, u, d, k, st, uh = audit_page(p)  # per-page findings, by category
        opaque += o; console += c; unawaited += u; dialog += d; key += k; static += st; unhi += uh
    if verbose:
        def show(name, items, fmt):
            if items:
                print(f"[{name}] {len(items)}")
                for it in items:
                    print("   " + fmt(it))
        show("opaque cell · model call with no visible output", opaque, lambda it: f"{it[0]}  «…{it[1]}…»")
        show("console.* in cell (use helpers.log)", console, lambda it: f"{it[0]}  {it[1]}")
        show("un-awaited model call", unawaited, lambda it: f"{it[0]}  «{it[1]}…»")
        show("blocking dialog in cell", dialog, lambda it: f"{it[0]}  {it[1]}")
        show("inlined API key in cell", key, lambda it: f"{it[0]}  {it[1]}")
        show("cell-only code shown statically (not editable)", static, lambda it: f"{it[0]}  {it[1]}")
        show("editable cells without the syntax highlighter loaded", unhi, lambda it: f"{it[0]}  {it[1]}")
        show("learner-facing cell UI contract", ui_contract, lambda it: f"{it[0]}  {it[1]}")
        total = (len(opaque) + len(console) + len(unawaited) + len(dialog) + len(key) + len(static)
                 + len(unhi) + len(ui_contract))
        print(f"\ncell_audit: {total} finding(s) (opaque {len(opaque)}, console {len(console)}, "
              f"unawaited {len(unawaited)}, dialog {len(dialog)}, inline-key {len(key)}, static {len(static)}, "
              f"unhighlighted {len(unhi)}, ui-contract {len(ui_contract)})")
    return {"opaque": opaque, "console": console, "unawaited": unawaited,
            "dialog": dialog, "inline_key": key, "static_cell_code": static,
            "unhighlighted": unhi, "ui_contract": ui_contract}


if __name__ == "__main__":
    r = run()
    sys.exit(1 if sum(len(v) for v in r.values()) else 0)
