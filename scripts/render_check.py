#!/usr/bin/env python3
"""render_check.py loads course pages in a real headless Chromium and reports what mounted.

The lab image ships playwright + chromium (workspace/Dockerfile installs them, pinned in
workspace/requirements.txt), so this runs in the lab with no setup:

    python3 scripts/render_check.py                       # the course pages, web/nemoclaw
    python3 scripts/render_check.py --all                 # course pages + the aux pages (glossary, index, ...)
    python3 scripts/render_check.py --all --run           # + click Run on a cell per page (catches execution-time errors)
    python3 scripts/render_check.py --screenshot 01a-loop # + full-page PNG next to the page
    python3 scripts/render_check.py --dir web/nemoclaw 02b-rag 04b-modern-clis

For each page it serves the directory over a local HTTP server (ES-module imports need a real
origin, not file://), loads it in Chromium, and reports: canvas panels mounted, run-cell count,
the per-node run-button labels, any leftover python code-views, and any real script errors.
Offline-service fetch failures are filtered out (the lab backend is not wired to this static
server), so what remains is genuine page breakage. Zero panels on a canvas page or any real
error makes that page fail; the process exits non-zero, so this is usable as a gate.

Mount alone is not enough. A cell can mount fine and still throw the moment it RUNS: the node
executor injects helpers (webSearch, chat, ...) into cell scope as bare identifiers, so a helper
that is in HELPER_FNS but missing from _canvas.js's imports surfaces only as a ReferenceError on
Run. --run clicks Run on the first canvas node and run-cell of each page and flags execution-time
CODE errors (ReferenceError / not-a-function / SyntaxError), ignoring the expected offline fetch
failures. This is the gap that let a dropped `webSearch` import ship past a mount-only check.

This is the in-lab counterpart to scripts/test_page_runtime.js (which drives the OpenClaw
gateway nodes from the openclaw container); this one verifies that pages mount and render.
"""
import argparse, http.server, os, socketserver, sys, threading
from playwright.sync_api import sync_playwright

DEFAULT_PAGES = ["01a-loop", "01b-react", "01c-tools", "02a-routing", "02b-rag", "02c-deep",
                 "03a-kickstart", "03b-openclaw", "03c-always-on", "04a-safety",
                 "04b-modern-clis", "04c-going-further"]

# Non-numbered pages that share _shared.js and the module graph. They mount fewer (or no)
# canvas cells, so the gate that matters for them is "loads without a JS error or a failed
# module import" rather than panel count. They are checked under --all. glossary.html broke
# once because the _glossary.js extraction dropped a re-export and no gate covered it; this
# list closes that gap.
AUX_PAGES = ["index", "courses", "cert", "glossary", "studio", "SKILL"]

# Execution-time errors that mean broken CODE (a helper out of scope, a typo), as opposed to the
# offline fetch failures that are expected here (no backend wired to the static server).
_CODE_ERR = ("is not defined", "is not a function", "is not iterable", "SyntaxError",
             "Cannot read properties", "Cannot access",
             # A fetched asset that 404s returns the HTML index; .json() on it throws this. The message
             # carries none of the names above, so without these a crashed cell read as ok (the 04b miss).
             "Unexpected token", "is not valid JSON")
_NET_NOISE = ("fetch", "NetworkError", "Failed to load", "ERR_", "/api/", "/lab/", "Load failed",
              "AbortError", "timed out", "timeout", "ECONN", "ERR_NETWORK")


def _run_cells(page, console_errs):
    """Click the first canvas node + run-cell, wait, and return execution-time CODE errors shown
    in the panels or thrown to the console. The node executor catches errors and renders them in
    the panel (not the console), so the panel text is scanned too. Network/offline failures are
    not code errors and are filtered out, so a clean result means the cell's helpers resolved."""
    clicked = False
    for sel in (".cf-panel-runone", ".rc-run"):
        b = page.query_selector(sel)
        if b:
            try:
                b.click()
                clicked = True
            except Exception:
                pass
    if not clicked:
        return []
    page.wait_for_timeout(3500)   # the ReferenceError fires synchronously; the fetch error (later) is filtered
    panel = page.eval_on_selector_all(
        ".cf-panel-log, .cf-panel-output, .cf-panel-stream, .cf-debug, .rc-output, .rc-log",
        "els => els.map(e => e.textContent).join('\\n')") or ""
    out = []
    for line in (panel + "\n" + "\n".join(console_errs)).split("\n"):
        if any(c in line for c in _CODE_ERR) and not any(nw in line for nw in _NET_NOISE):
            out.append("RUN: " + line.strip()[:140])
    return list(dict.fromkeys(out))[:5]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="web/nemoclaw", help="directory of pages to serve (default web/nemoclaw)")
    ap.add_argument("--port", type=int, default=8123)
    ap.add_argument("--screenshot", default=None, help="page name to capture a full-page PNG of")
    ap.add_argument("--all", action="store_true", help="also render the aux pages (glossary, index, courses, cert, studio, SKILL)")
    ap.add_argument("--run", action="store_true", help="also click Run on the first canvas node + run-cell per page and flag execution-time code errors (ReferenceError / not-a-function) that mount-only checks miss")
    ap.add_argument("pages", nargs="*", help="page names without .html; default: the course pages present")
    a = ap.parse_args()

    root = os.path.abspath(a.dir)
    if not os.path.isdir(root):
        sys.exit("render_check: no such dir: " + root)
    if a.pages:
        pages = a.pages
    else:
        candidates = DEFAULT_PAGES + AUX_PAGES if a.all else DEFAULT_PAGES
        pages = [p for p in candidates if os.path.exists(os.path.join(root, p + ".html"))]
    if not pages:
        sys.exit("render_check: no pages to render under " + root)

    os.chdir(root)
    httpd = socketserver.TCPServer(("127.0.0.1", a.port), http.server.SimpleHTTPRequestHandler)
    httpd.RequestHandlerClass.log_message = lambda *x, **k: None   # quiet the access log
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    bad = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name in pages:
            page = browser.new_page(viewport={"width": 1280, "height": 2200})
            errs = []
            page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errs.append("PAGEERROR: " + str(e)))
            try:
                page.goto("http://127.0.0.1:%d/%s.html" % (a.port, name), wait_until="load", timeout=20000)
                page.wait_for_timeout(2800)
                panels = page.eval_on_selector_all(".cf-panel", "e=>e.length")
                btns = page.eval_on_selector_all(".cf-panel-runone", "e=>[...new Set(e.map(x=>x.textContent.trim()))]")
                pyv = page.eval_on_selector_all('.cf-code-view[data-lang="python"]', "e=>e.length")
                cells = page.eval_on_selector_all(".rc-run", "e=>e.length")
                real = [e for e in errs if "ERR_" not in e and "Failed to load resource" not in e
                        and "/api/" not in e and "/lab/" not in e]
                if a.run:
                    real += _run_cells(page, errs)
                ok = not real
                print("[%s] %s: panels=%s runCells=%s runBtns=%s pythonViews=%s%s"
                      % ("ok" if ok else "ERR", name, panels, cells, btns, pyv,
                         (" errors=%s" % real[:5]) if real else ""))
                if not ok:
                    bad += 1
                if a.screenshot == name:
                    out = os.path.join(root, name + ".render.png")
                    page.screenshot(path=out, full_page=True)
                    print("       screenshot -> " + out)
            except Exception as e:
                print("[FAIL] %s: %s" % (name, e))
                bad += 1
            page.close()
        browser.close()

    print("render_check: %d/%d pages clean" % (len(pages) - bad, len(pages)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
