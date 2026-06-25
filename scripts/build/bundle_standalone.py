#!/usr/bin/env python3
"""Bundle web/nemoclaw/*.html into iframe-ready single-file HTMLs.

The lab view (web/*.html behind nginx) is the source of truth. This script
transforms each source page so that it works as a *standalone* file: no
sibling pages, no microservices (other than the Cloudflare LLM proxy), no
topbar, no journey map, no foot-nav. Light theme so it reads inside an edX
iframe.

Every transform happens here. The lab view source files stay untouched.

What gets transformed:

  1. Inline _style.css (so the file is self-contained)
  2. Append _lite_overlay.css (flips theme to light, hides nav chrome)
  3. Inline _shared.js, with the import line removed
  4. Strip the topbar element entirely (auto-mount code bails when missing)
  5. Strip the #journey-map and .foot-nav containers (no cross-page nav)
  6. Inject an inline <div id="key-panel"></div> just inside <main> + lite-
     mode JS that renders an inline NVIDIA API key form (no redirect)
  7. Substitute dark-theme colors inside <svg> bodies so diagrams remain
     legible on a light background

Usage:
  python3 scripts/bundle_standalone.py --src web/nemoclaw
  python3 scripts/bundle_standalone.py --src web/nemoclaw --out /tmp/nemoclaw_iframe --clean
"""
from __future__ import annotations
import argparse
import re
import shutil
import sys
from pathlib import Path

for _p in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
    if (_p / "scripts" / "_bootstrap.py").exists():
        sys.path.insert(0, str(_p / "scripts")); break
from _bootstrap import add_script_paths, find_repo_root

TASK1 = find_repo_root(Path(__file__).resolve())
WEB_DIR = TASK1 / "web"
DEFAULT_OUT = TASK1 / "web_standalone"
# The released course is web/nemoclaw/.
# Pass --src web/nemoclaw to bundle it into --out web/nemoclaw_standalone (the auto-derive convention below).


# ────────────────────────────────────────────────────────────────────────────
# Regex catalogue. Tested against every page in web/.
# ────────────────────────────────────────────────────────────────────────────
CSS_LINK_RE = re.compile(
    r'<link\s+rel="stylesheet"\s+href="_style\.css"\s*/?>',
    re.IGNORECASE,
)
IMPORT_LINE_RE = re.compile(
    r'^\s*import\s+\{[^}]*\}\s+from\s+["\']\./_shared\.js["\'];?\s*$',
    re.MULTILINE,
)
TOPBAR_RE = re.compile(
    # The topbar contains nested divs (.spacer). Anchor the match to
    # whatever follows the topbar, namely the opening of <main> on module
    # pages or a <main> on index/cert pages, so .*? consumes past the inner </div>.
    r'<div class="topbar">.*?</div>\s*(?=<main\b)',
    re.DOTALL,
)
JOURNEY_RE = re.compile(
    r'<div id="journey-map"></div>\s*',
)
FOOTNAV_RE = re.compile(
    r'<div class="foot-nav">.*?</div>\s*',
    re.DOTALL,
)
MAIN_OPEN_RE = re.compile(r'(<main[^>]*>)')
# Some pages call mountJourneyMap("#journey-map", ...) in their inline script.
# The function bails if the target is missing, but kill the call to avoid the
# pointless log noise in the console. Match permits one level of nested parens
# (the calls often pass document.getElementById("…") as an argument).
_NESTED_ARGS = r'(?:[^()]|\([^()]*\))*'
MOUNT_JM_RE = re.compile(rf'^\s*mountJourneyMap\({_NESTED_ARGS}\);\s*$', re.MULTILINE)
UPDATE_PILL_RE = re.compile(rf'^\s*updateKeyPill\({_NESTED_ARGS}\);\s*$', re.MULTILINE)
BUILD_NAV_RE = re.compile(
    rf'^\s*document\.getElementById\("nav"\)\.innerHTML\s*=\s*buildNav\({_NESTED_ARGS}\);\s*$',
    re.MULTILINE,
)


# ────────────────────────────────────────────────────────────────────────────
# SVG dark→light color substitution table. Applied only inside <svg>…</svg>.
# Keep the substitutions limited and conservative. A diagram should read as "dark
# figure on light card" rather than get wrecked by over-aggressive recolor.
# ────────────────────────────────────────────────────────────────────────────
SVG_SUBS = [
    # Canvas backgrounds (inline style on the <svg> itself)
    ("background:#0d0d0d",          "background:#f6f8fa"),
    ("background: #0d0d0d",         "background:#f6f8fa"),
    ("border:1px solid #2a2a2a",    "border:1px solid #d0d7de"),
    # Fills / strokes that show up across most diagrams
    ('fill="#0d0d0d"',              'fill="#f6f8fa"'),
    ('fill="#1e1e1e"',              'fill="#f6f8fa"'),
    ('fill="#161616"',              'fill="#eef1f4"'),
    ('fill="#262626"',              'fill="#e1e6eb"'),
    ('stroke="#2a2a2a"',            'stroke="#d0d7de"'),
    ('stroke="#3a3a3a"',            'stroke="#b0b8c0"'),
    # Light-on-dark text fills → dark-on-light
    ('fill="#f2f2f2"',              'fill="#1a1a1a"'),
    ('fill="#e8e8e8"',              'fill="#1a1a1a"'),
    ('fill="#b0b0b0"',              'fill="#3b3b3b"'),
    ('fill="#a5a5a5"',              'fill="#57606a"'),
    ('fill="#6a6a6a"',              'fill="#57606a"'),
    ('fill="#6f6f6f"',              'fill="#57606a"'),
    # Highlighted greens (used as fills for "selected" rows)
    ('fill="#0d2a0d"',              'fill="#e6f3d4"'),
    ('fill="#1a3a2a"',              'fill="#daeec1"'),
    ('fill="#1e3a1e"',              'fill="#daeec1"'),
    ('fill="#141f04"',              'fill="#e6f3d4"'),
    ('fill="#111a11"',              'fill="#e6f3d4"'),
    # Generic dark grays used as neutral box backdrops
    ('fill="#131313"',              'fill="#eef1f4"'),
    # Mid-tone supporting text colors that were authored for a dark backdrop
    # but become unreadable on a light one. The pattern is: take whatever
    # mid-saturation hue was used and substitute the darker mate.
    ('fill="#7a5020"',              'fill="#8b6914"'),    # mid amber → dark amber
    ('fill="#2a6090"',              'fill="#0969da"'),    # mid blue → dark blue
    ('fill="#3a5a30"',              'fill="#4a7a00"'),    # mid green → dark green
    ('fill="#2a5020"',              'fill="#4a7a00"'),    # mid green → dark green
    ('fill="#3a4a5a"',              'fill="#0969da"'),    # mid blue-gray → blue
    ('fill="#285070"',              'fill="#0969da"'),    # mid blue → dark blue
    ('fill="#6a40b0"',              'fill="#6f42c1"'),    # mid purple → purple
    ('fill="#4a4a6a"',              'fill="#57606a"'),    # mid blue-gray → neutral gray
    # Bright green text → darker green (more legible on light)
    ('fill="#aee23a"',              'fill="#4a7a00"'),
    ('fill="#76b900"',              'fill="#4a7a00"'),
    ('fill="#8ec444"',               'fill="#4a7a00"'),
    ('fill="#e0eec8"',              'fill="#3b6500"'),
    # Bright blue text → darker blue
    ('fill="#7eb6ff"',              'fill="#0969da"'),
    ('fill="#7eb8ff"',              'fill="#0969da"'),
    ('fill="#c8d8f0"',              'fill="#0969da"'),
    ('fill="#3b82f6"',              'fill="#0969da"'),
    # Amber / warning text
    ('fill="#e8c87a"',              'fill="#8b6914"'),
    ('fill="#f2cc60"',              'fill="#8b6914"'),
    # Red / shutdown
    ('fill="#ff9a9a"',              'fill="#d1242f"'),
    # Purple
    ('fill="#a78bfa"',              'fill="#6f42c1"'),
    ('fill="#d2b9ff"',              'fill="#6f42c1"'),
    # Dark-themed box fills used as backdrops for boxes/labels
    ('fill="#1e1e3a"',              'fill="#dfeaf5"'),
    ('fill="#1a1a2e"',              'fill="#eadfff"'),    # dark navy → light lavender
    ('fill="#3a2e1e"',              'fill="#f7e3c5"'),
    ('fill="#3a1e1e"',              'fill="#fadcdc"'),
    ('fill="#1f1a2e"',              'fill="#eadfff"'),
    ('fill="#0d1828"',              'fill="#dfeaf5"'),
    ('fill="#141f3a"',              'fill="#cad7e8"'),
    ('fill="#1a2850"',              'fill="#b5c6db"'),
    ('fill="#0d2b40"',              'fill="#dfeaf5"'),
    ('fill="#1a2820"',              'fill="#daeec1"'),
    ('fill="#211b12"',              'fill="#f7e3c5"'),
    ('fill="#0f1a22"',              'fill="#dfeaf5"'),
    ('fill="#0b1524"',              'fill="#dfeaf5"'),
    # Dark accent strokes → mid-tone
    ('stroke="#3a6080"',            'stroke="#0969da"'),
    ('stroke="#4a4a6a"',            'stroke="#57606a"'),
    ('stroke="#4a7a30"',            'stroke="#4a7a00"'),
    ('stroke="#cc7a00"',            'stroke="#8b6914"'),
    ('stroke="#8250df"',            'stroke="#6f42c1"'),
    ('stroke="#a78bfa"',            'stroke="#6f42c1"'),
    ('stroke="#58a6ff"',            'stroke="#0969da"'),
    ('stroke="#76b900"',            'stroke="#4a7a00"'),
    ('stroke="#aee23a"',            'stroke="#4a7a00"'),
    ('stroke="#3b82f6"',            'stroke="#0969da"'),
    ('stroke="#d74e4e"',            'stroke="#d1242f"'),
    ('stroke="#d49c2c"',            'stroke="#8b6914"'),
    # White-on-amber labels (lethal trifecta diamond etc.)
    ('fill="#fef9ee"',              'fill="#fff8e1"'),
    # Arrow heads (already-colored polygons)
    ('fill="#88aacc"',              'fill="#0969da"'),
    ('fill="#5a5a5a"',              'fill="#57606a"'),
]

# Inline script that runs in the bundled page, after _shared.js, to render
# the lite-mode key form into #key-panel. Hand-written; no template substitution.
LITE_KEY_PANEL_JS = r"""
// ── Lite-mode key panel (iframe export only) ─────────────────────────────
(function _liteKeyPanel() {
  // The exported HTML wraps content in <main>. We inject #key-panel just
  // inside it, before the first <h2>, so the form appears above the
  // first runnable cell.
  function _renderForm(panel, message) {
    panel.innerHTML =
      '<div class="key-form">' +
        '<label for="_lite_key_in">NVIDIA API key (nvapi-…)</label>' +
        '<input id="_lite_key_in" type="password" placeholder="nvapi-…" autocomplete="off"/>' +
        '<button id="_lite_key_btn">Save & verify</button>' +
        '<div class="key-hint">Free key at <a href="https://build.nvidia.com" target="_blank" rel="noopener">build.nvidia.com</a>. Stored in sessionStorage; cleared when this tab closes.</div>' +
        (message ? '<div class="key-err">' + message + '</div>' : '') +
      '</div>';
    var inp = panel.querySelector("#_lite_key_in");
    var btn = panel.querySelector("#_lite_key_btn");
    btn.addEventListener("click", async function() {
      var raw = (inp.value || "").trim();
      if (!raw.startsWith("nvapi-")) {
        _renderForm(panel, "Key must start with 'nvapi-'");
        return;
      }
      sessionStorage.setItem("nvapi", raw);
      _renderOk(panel);
    });
    inp.addEventListener("keydown", function(e) { if (e.key === "Enter") btn.click(); });
  }
  function _renderOk(panel) {
    panel.innerHTML =
      '<div class="key-form">' +
        '<div class="key-ok">✓ Key saved for this tab. Run any cell to call the model.</div>' +
        '<div class="key-note">Wrong key? <a href="#" id="_lite_key_reset">Clear and re-enter</a></div>' +
      '</div>';
    var a = panel.querySelector("#_lite_key_reset");
    a.addEventListener("click", function(e) {
      e.preventDefault();
      sessionStorage.removeItem("nvapi");
      _renderForm(panel, "");
    });
  }
  function _mount() {
    var main = document.querySelector("main");
    if (!main) return;
    // Already mounted? skip.
    if (main.querySelector("#key-panel")) {
      // still wire up its initial state
    } else {
      var panel = document.createElement("div");
      panel.id = "key-panel";
      // Insert before the first <h2> if it is a direct child of <main>; else
      // before the first direct-child ancestor of that h2; else at the top.
      // `insertBefore(node, ref)` requires `ref` to be a direct child of
      // `node`, which the original `main.querySelector("h2")` did not
      // guarantee, because the h2 may be nested inside a wrapper div.
      var ref = null;
      var h2 = main.querySelector("h2");
      if (h2) {
        ref = h2;
        while (ref && ref.parentNode !== main) ref = ref.parentNode;
      }
      if (!ref) ref = main.firstChild;
      if (ref) main.insertBefore(panel, ref);
      else     main.appendChild(panel);
    }
    var panel = main.querySelector("#key-panel");
    if (sessionStorage.getItem("nvapi")) _renderOk(panel);
    else _renderForm(panel, "");
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", _mount);
  } else {
    _mount();
  }
})();
"""


def _strip_dead_chrome(html: str) -> str:
    """Remove topbar, journey-map, foot-nav and any leftover script calls
    that referenced them. The auto-mount logic in _shared.js bails out
    when its target elements aren't found, so stripping is enough."""
    html = TOPBAR_RE.sub("", html, count=1)
    html = JOURNEY_RE.sub("", html)
    # foot-nav (prev/next at the bottom of each module page) is intentionally
    # kept: the lite link-bridge in LITE_AUTOSIZE_JS catches clicks and
    # routes them through the edX navigator's setActive(). The lab view
    # uses its own journey map; the bundled view leans on foot-nav as
    # the natural "continue to next module" surface.
    html = MOUNT_JM_RE.sub("", html)
    html = UPDATE_PILL_RE.sub("", html)
    html = BUILD_NAV_RE.sub("", html)
    return html


# When the bundle is iframed inside the edX navigator, we don't want the
# inner page to grow its own scrollbar (the dreaded "window-in-window"
# look). Each bundled HTML posts its full scrollHeight to its parent via
# postMessage; the navigator listens and grows the iframe to fit. Safe
# no-op when the page isn't iframed (window.parent === window) or when
# nobody is listening.
LITE_AUTOSIZE_JS = r"""
// ── Lite-mode bridge (iframe export only) ───────────────────────────────
// When iframed, the parent (edX navigator) listens for two message types:
//
//   { type: "fx43-iframe-size",  height: <px> }     ← from autosize loop
//   { type: "fx43-navigate",     file: "<x>.html" } ← from link interceptor
//
// The autosize keeps iframe.height == content height (no scrollbar). The
// link interceptor catches clicks on sibling .html anchors (foot-nav
// prev/next, in-prose cross-references, etc.) so the navigator routes
// them through its own setActive() and the journey bar stays in sync.
// Both IIFEs no-op when the page is loaded standalone (window.parent
// === window).
(function _liteAutosize() {
  if (window.parent === window) return;            // standalone tab, no parent

  // BREAK THE FEEDBACK LOOP: the lab CSS sets `body { min-height: 100vh }`.
  // Inside an iframe, 100vh == the iframe's own viewport. When the parent
  // grows the iframe (even by 1px), the body's min-height grows with it,
  // body.scrollHeight reports the new larger value, parent grows again …
  // we'd loop forever. Pin html/body to natural height inside the iframe.
  function pinSize() {
    if (document.documentElement) {
      document.documentElement.style.setProperty("min-height", "0", "important");
      document.documentElement.style.setProperty("height", "auto", "important");
    }
    if (document.body) {
      document.body.style.setProperty("min-height", "0", "important");
      document.body.style.setProperty("height", "auto", "important");
    }
  }
  pinSize();

  // Track only INCREASES that come from genuine content additions (a
  // CodeMirror mount, a helpers row open, a late image load). We never
  // shrink. Once we've reported a height, the parent owns it; subsequent
  // smaller measurements are ignored, which keeps us out of the loop
  // even if pinSize() races with a stylesheet that resets min-height.
  var reported = 0;
  function measureContent() {
    // Use the rendered content's bottom edge, not body.scrollHeight (which
    // is biased by min-height). We probe the actual children of <main> /
    // <body> and take the maximum bottom-y.
    var body = document.body;
    if (!body) return 0;
    var max = 0;
    var nodes = body.children;
    for (var i = 0; i < nodes.length; i++) {
      var r = nodes[i].getBoundingClientRect();
      var bottom = r.bottom + window.scrollY;
      if (bottom > max) max = bottom;
    }
    return Math.ceil(max);
  }
  function emit() {
    pinSize();                        // re-apply, defensive
    var h = measureContent();
    if (h > reported + 4) {           // grow-only, ignore tiny jitter
      reported = h;
      try {
        window.parent.postMessage({ type: "fx43-iframe-size", height: h, url: location.href }, "*");
      } catch (_) {}
    }
  }

  function start() {
    emit();
    window.addEventListener("load", emit);
    // ResizeObserver / MutationObserver catch real layout additions such as
    // CodeMirror mounts, <details> open, and helpers source-row reveal.
    // Throttled via requestAnimationFrame to coalesce bursts.
    var rafScheduled = false;
    function schedule() {
      if (rafScheduled) return;
      rafScheduled = true;
      requestAnimationFrame(function () { rafScheduled = false; emit(); });
    }
    try { new ResizeObserver(schedule).observe(document.body); } catch (_) {}
    try {
      new MutationObserver(schedule).observe(document.body, {
        childList: true, subtree: true, attributes: true,
        attributeFilter: ["open", "hidden", "class"]
      });
    } catch (_) {}
    // A short post-load burst for content that lands a beat after load
    // (highlight.js, CodeMirror, viz drawing). After that, observers
    // carry the rest. A long-running interval is avoided, since that is what
    // caused the indefinite-growth perception.
    var burst = 0;
    var bid = setInterval(function () {
      emit();
      if (++burst >= 15) clearInterval(bid);    // ~2.2s of 150ms ticks
    }, 150);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();

// ── Lite-mode link interceptor (iframe export only) ─────────────────────
// Catch clicks on sibling .html anchors and hand them up to the parent
// navigator. Source of truth for the link target is the actual <a href>
// in the page, so no separate map needs to be maintained. Capture-phase
// listener so we beat any page-level click handlers.
(function _liteLinkBridge() {
  if (window.parent === window) return;

  function fileFromHref(a) {
    if (!a || !a.href || a.target === "_blank") return null;
    var url;
    try { url = new URL(a.href, location.href); } catch (_) { return null; }
    if (url.origin !== location.origin) return null;     // external
    var dir = location.pathname.replace(/[^/]*$/, "");
    if (!url.pathname.startsWith(dir)) return null;      // out of bundle dir
    var rest = url.pathname.slice(dir.length);
    if (!rest || rest.indexOf("/") >= 0) return null;    // subdir, not a sibling
    if (!/\.html(\?.*)?$/i.test(rest)) return null;
    return { file: rest.replace(/\?.*$/, ""), hash: url.hash || "" };
  }

  document.addEventListener("click", function (ev) {
    if (ev.defaultPrevented) return;
    if (ev.button !== 0) return;                 // only left-click
    if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
    var a = ev.target;
    while (a && a !== document.body && a.tagName !== "A") a = a.parentElement;
    if (!a || a.tagName !== "A") return;
    var t = fileFromHref(a);
    if (!t) return;
    // Self-link? Let it fall through to natural anchor scroll.
    if (t.file === location.pathname.split("/").pop()) return;
    ev.preventDefault();
    try {
      window.parent.postMessage({
        type: "fx43-navigate",
        file: t.file,
        hash: t.hash,
      }, "*");
    } catch (_) {}
  }, true);
})();
"""

# The code/helpers panels are <details> elements built by _shared.js at
# runtime, so a static regex over the HTML doesn't catch them. Instead the
# lite bootstrap below watches the DOM for new panels and adds the `open`
# attribute. The lab view stays collapsed-by-default; only the export opens.
LITE_OPEN_PANELS_JS = r"""
// ── Lite-mode: open code/helpers panels by default ───────────────────────
// In the iframe export there is no obvious affordance for the disclosure
// triangle, and the whole point of the export is *reading the code*. So we
// auto-open .cf-panel-code-det as panels get mounted. Helpers stay closed
// by default (students open them on demand) and results panels stay
// collapsed (they're empty until a run).
(function _liteOpenPanels() {
  const SEL = ".cf-panel-code-det";
  function openAll(root) {
    (root || document).querySelectorAll(SEL).forEach(el => {
      if (!el.hasAttribute("open")) el.setAttribute("open", "");
    });
  }
  function start() {
    openAll(document);
    new MutationObserver(muts => {
      for (const m of muts) for (const n of m.addedNodes) {
        if (n.nodeType === 1) {
          if (n.matches && n.matches(SEL)) {
            if (!n.hasAttribute("open")) n.setAttribute("open", "");
          }
          if (n.querySelectorAll) openAll(n);
        }
      }
    }).observe(document.body, { childList: true, subtree: true });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
"""


# /lab/lab/... is the JupyterLab tree URL only resolvable inside the lab container. /lab/static/ ditto.
# In an external iframe these 404.
# Convert any anchor with such an href into plain text so the prose still reads.
LAB_ANCHOR_RE = re.compile(
    r'<a([^>]*?)href="/lab/(?:lab|static)/[^"]*"([^>]*)>(.*?)</a>',
    re.DOTALL,
)


def _strip_lab_anchors(html: str) -> str:
    """Demote dead /lab/* anchor tags to plain text (keeps inner content)."""
    return LAB_ANCHOR_RE.sub(lambda m: m.group(3), html)


def _apply_svg_subs(html: str) -> str:
    """Replace dark-theme inline colors inside SVG element bodies. The match
    is scoped to real SVG element spans so prose, code, and inline color
    references outside diagrams are untouched.

    The opening-tag character class is `[^<>]` (not the looser `[^>]`) so
    the regex cannot start at a literal `<svg>` inside a CSS comment or
    code-string context. A real SVG opening tag never contains an unescaped
    `<` in its attributes; the broken `[^>]` form would happily consume
    across `</style>` and onward, accidentally rewriting unrelated CSS
    (notably `background: #0d0d0d` inside a CodeMirror theme block).

    The opening tag must also carry a `viewBox` attribute. Every real figure
    this course emits (mountDiagram output, the inline file-trees, log.draw
    frames) declares one; a bare `<svg>` token sitting in prose or a CSS
    comment does not. Without this guard such a token matches as an empty
    opening tag and `.*?</svg>` swallows everything up to the next real
    closing tag, dragging the head `<style>` (and its CodeMirror dark theme)
    into the recolor pass and flipping the code background to light."""
    out = []
    cursor = 0
    for m in re.finditer(r'<svg\b[^<>]*\bviewBox[^<>]*>.*?</svg>', html, re.DOTALL | re.IGNORECASE):
        out.append(html[cursor:m.start()])
        svg = m.group(0)
        for old, new in SVG_SUBS:
            svg = svg.replace(old, new)
        svg = svg.replace(' class="gfx-dark"', "")  # GFX graphics use light defaults in the light standalone
        out.append(svg)
        cursor = m.end()
    out.append(html[cursor:])
    return "".join(out)


# Injected into <head>. The favicon ships under assets/ (relative, both builds). The theme init
# runs before first paint in the full build: it sets data-theme on <html> from a saved choice or
# the OS preference, so the page opens in the right palette with no flash. _style.css carries the
# matching :root[data-theme="light"] palette; the toggle button is mounted by _shared.js.
FAVICON_LINK = '<link rel="icon" type="image/x-icon" href="./assets/favicon.ico"/>'
THEME_INIT_JS = (
    '<script>(function(){try{var t=localStorage.getItem("theme")'
    '||(matchMedia("(prefers-color-scheme: light)").matches?"light":"dark");'
    'document.documentElement.setAttribute("data-theme",t);}catch(e){}})();</script>'
)


def bundle_one(html_path: Path, css_text: str, lite_css: str, shared_js: str,
               full: bool = False) -> str:
    """Bundle one page into a self-contained file.

    The default (lite) build is the light, chrome-free iframe export for the edX navigator.
    With full=True it is the dark, fully navigable standalone for a self-hosted Pages site:
    the same content the lab serves, made self-contained, with the off-lab key panel added.
    """
    html = html_path.read_text(encoding="utf-8")

    # 0) A generated SKILL hub loads ../_skill_explorer.js (the renderer lives one dir up so it serves
    #    every surface). The bundle is flat, so point it at the sibling copy shipped alongside the pages.
    html = html.replace('src="../_skill_explorer.js"', 'src="_skill_explorer.js"')

    # 1) Inline _style.css. The lite export appends _lite_overlay.css to flip the page to a
    #    light background and hide the nav chrome; the full build keeps the lab's dark theme,
    #    so it inlines _style.css on its own.
    if full:
        style_block = "<style>\n" + css_text + "\n</style>"
    else:
        style_block = (
            "<style>\n" + css_text + "\n\n/* ── lite overlay ── */\n" + lite_css + "\n</style>"
        )
    new_html, n_css = CSS_LINK_RE.subn(style_block, html, count=1)
    if n_css == 0:
        # Page has no <link rel="stylesheet" href="_style.css"/> (e.g. courses.html).
        # Insert the style block right before </head>.
        new_html = html.replace("</head>", style_block + "\n</head>", 1)

    # 1b) Favicon on every bundled page. In the full build also inject the pre-paint theme init so
    #     the page opens in the saved/OS palette without a flash; the lite iframe export stays baked.
    head_inject = FAVICON_LINK + ("\n" + THEME_INIT_JS if full else "")
    new_html = new_html.replace("</head>", head_inject + "\n</head>", 1)

    # 2) The lite export strips the lab-only chrome (topbar / journey map / the JS that mounts
    #    them) because the edX navigator supplies its own; the full build keeps the chrome so
    #    the course navigates itself. Both demote dead /lab/* anchors, which never resolve
    #    off-lab.
    if not full:
        new_html = _strip_dead_chrome(new_html)
    new_html = _strip_lab_anchors(new_html)

    # 3) Keep the `import {...} from "./_shared.js"` line and ship _shared.js as a real file
    #    alongside the pages (copied in main). The imports then resolve, and ES module caching
    #    loads the module once even across multiple module blocks, exactly as the lab serves
    #    it, so each page stays small. The lite export injects its own sessionStorage key form
    #    and auto-opens the code panels for reading. The full build injects NOTHING here: each
    #    page already has a native key panel (mountKeyPanel on module pages, the static form on
    #    the landing) that works off-lab and is styled by _style.css, so injecting the lite form
    #    would only collide with it on #key-panel and render unstyled.
    if not full:
        new_html, n_js = IMPORT_LINE_RE.subn(
            lambda m: m.group(0) + "\n" + LITE_KEY_PANEL_JS + LITE_OPEN_PANELS_JS,
            new_html,
            count=1,
        )
    # Pages without _shared.js (e.g. courses.html) get no key panel either.

    # 4) The lite export re-themes the SVG figures to read on a light background; the full
    #    build keeps them dark, their .gfx-dark class resolving against the dark palette in
    #    _style.css, so it skips the recolor.
    if not full:
        new_html = _apply_svg_subs(new_html)

    # 5) The lite export posts its height to the edX navigator and bridges sibling-page clicks
    #    back through it. The full build navigates with ordinary relative anchors, so it skips
    #    the autosize beacon, whose link bridge would otherwise swallow that navigation.
    if not full:
        autosize_tag = f"<script>{LITE_AUTOSIZE_JS}</script>\n</body>"
        new_html = new_html.replace("</body>", autosize_tag, 1)

    return new_html


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--src",
        type=Path,
        default=WEB_DIR,
        help="Source directory of *.html + _shared.js + _style.css. "
             "Default is web/. Pass a relative name (e.g. 'web/nemoclaw') "
             "or an absolute path. The default --out is auto-derived from --src "
             "by appending _standalone, so --src web/nemoclaw → --out web/nemoclaw_standalone.",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory. Default derives from --src by appending _standalone.",
    )
    ap.add_argument(
        "--clean",
        action="store_true",
        help="Wipe the output directory before bundling.",
    )
    ap.add_argument(
        "--full",
        action="store_true",
        help="Build the full standalone for a self-hosted Pages site: the lab's dark theme, "
             "full nav chrome, and interactive panels, made self-contained. The default is the "
             "light, chrome-free iframe export for the edX navigator.",
    )
    args = ap.parse_args()

    # Resolve --src: accept either an absolute path or a name relative to the task1/ root.
    web = args.src
    if not web.is_absolute():
        web = TASK1 / web
    if args.out is not None:
        out = args.out
    else:
        # Auto-derive: web → web_standalone, web/nemoclaw → web/nemoclaw_standalone.
        out = web.parent / (web.name + "_standalone")
    if not web.is_dir():
        print(f"web/ not found at {web}", file=sys.stderr)
        return 1

    if args.clean and out.exists():
        # Walk and unlink only the files we own. JupyterLab may have created
        # an .ipynb_checkpoints subdirectory owned by a different uid; skip
        # anything we can't remove rather than failing the whole bundle.
        for p in sorted(out.rglob("*"), key=lambda x: len(x.parts), reverse=True):
            try:
                if p.is_file() or p.is_symlink():
                    p.unlink()
                elif p.is_dir():
                    p.rmdir()
            except (PermissionError, OSError):
                pass
    out.mkdir(parents=True, exist_ok=True)

    css_text = (web / "_style.css").read_text(encoding="utf-8")
    lite_css = (web / "_lite_overlay.css").read_text(encoding="utf-8")
    shared_js = (web / "_shared.js").read_text(encoding="utf-8")

    pages = sorted(p for p in web.glob("*.html") if not p.name.startswith("."))
    if not pages:
        print(f"no *.html under {web}", file=sys.stderr)
        return 1

    mode = "full standalone (dark theme, full nav)" if args.full else "lite iframe export (light)"
    print(f"  mode: {mode}")
    for src in pages:
        bundled = bundle_one(src, css_text, lite_css, shared_js, full=args.full)
        dst = out / src.name
        dst.write_text(bundled, encoding="utf-8")
        kb = len(bundled.encode("utf-8")) / 1024
        print(f"  bundled {src.name:<28} → {dst.name}  ({kb:5.1f} KB)")

    # Ship the shared ES modules as real files so the pages' kept `./_shared.js` import and the
    # per-section modules _shared.js imports in turn (e.g. _openshell.js) all resolve as siblings,
    # loaded once via ES-module caching exactly as the lab serves them. Globbing _*.js carries any
    # module the split adds without a per-module edit here.
    for mod in sorted(web.glob("_*.js")):
        shutil.copy2(mod, out / mod.name)
        print(f"  shipped {mod.name}  ({(out / mod.name).stat().st_size // 1024} KB)")

    # The SKILL hubs render via web/_skill_explorer.js, which lives one level ABOVE --src (one renderer
    # serves every surface), and the copied subdir SKILLs link ../_style.css. Neither is caught by the
    # globs above, so ship both flat: the hubs then render and the provenance pages style in the bundle.
    for extra in (web.parent / "_skill_explorer.js", web / "_style.css"):
        if extra.is_file() and not (out / extra.name).exists():
            shutil.copy2(extra, out / extra.name)
            print(f"  shipped {extra.name}")

    # Ship any LOCAL js a bundled page loads by relative <script src> (tool modules such as
    # studio.html's studio_main.js) so the page resolves its scripts and works standalone. Found by
    # scanning the pages rather than by naming the files, so a new tool module needs no edit here.
    # CDN srcs (http...) do not match the local pattern; _shared.js is already shipped above.
    js_refs = set()
    for src in pages:
        for m in re.finditer(r'<script[^>]+src=["\']\.?/?([\w./-]+\.m?js)["\']', src.read_text(encoding="utf-8")):
            js_refs.add(m.group(1))
    for ref in sorted(js_refs):
        cand = web / ref
        if cand.is_file() and not (out / ref).exists():
            (out / ref).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cand, out / ref)
            print(f"  shipped {ref}  ({cand.stat().st_size // 1024} KB)")

    # Carry non-inlined assets (images, SVGs) the pages reference by relative path, so the
    # bundle in --out is complete on its own and callers need no separate asset copy.
    assets = web / "assets"
    if assets.is_dir():
        shutil.copytree(assets, out / "assets", dirs_exist_ok=True)
        n_assets = sum(1 for p in (out / "assets").rglob("*") if p.is_file())
        print(f"  copied assets/      ({n_assets} files)")

    # Carry the "deep" glossary articles the course fetches by relative path
    # (mats/glossary_raw/<slug>.md, the full term bodies behind glossary_search's full=true mode).
    # Only the .md bodies are read, as text by the agent, so skip the images and other mats/
    # subtrees to keep the bundle lean. Without this the live full-article retrieval 404s.
    raw = web / "mats" / "glossary_raw"
    if raw.is_dir():
        dst = out / "mats" / "glossary_raw"
        dst.mkdir(parents=True, exist_ok=True)
        n_raw = 0
        for md in sorted(raw.glob("*.md")):
            shutil.copy2(md, dst / md.name)
            n_raw += 1
        print(f"  copied mats/glossary_raw/  ({n_raw} full glossary articles)")

    # Ship the mats provenance hub AND the top-level companion .md it previews, so the hub is reachable
    # and its lazy "preview" excerpts resolve in the bundle (each fetches the local .md by relative path).
    # The index JSON and the two unreferenced figure duplicates stay out to keep the bundle lean; their
    # previews fall back to a link, and the canonical figures already ship via copytree(assets) above.
    matsdir = web / "mats"
    msk = matsdir / "SKILL.html"
    if msk.is_file():
        (out / "mats").mkdir(parents=True, exist_ok=True)
        shutil.copy2(msk, out / "mats" / "SKILL.html")
        n_mats = 0
        for md in sorted(matsdir.glob("*.md")):
            shutil.copy2(md, out / "mats" / md.name)
            n_mats += 1
        print(f"  copied mats/SKILL.html + {n_mats} companion .md")

    print(f"\n{len(pages)} pages → {out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
