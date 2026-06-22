#!/usr/bin/env python3
"""Static check that DOM colors are theme-dynamic.

Theming flips a CSS-var palette under :root[data-theme="light"]; anything reaching
the DOM via var(--x) flips for free. Flags what cannot: hard-coded color literals in
inline styles (they outrank the light rules, so never flip) and var(--name) refs whose
name is never defined (the lone fallback never flips). Scope: every course-shipped chrome
script (discovered by glob, so a split of _shared.js into several modules stays covered) plus
each page body and inline SVG; inline <script> in a page is excluded for the CSS scan
(lesson/canvas content with its own palette), but SVG attribute literals are scanned everywhere.
Advisory.  Run:  python3 scripts/color_theme.py
"""
from __future__ import annotations
import re, sys, functools
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
WEB = HERE.parent / "web"
NEMO = WEB / "nemoclaw"

COLOR_PROPS = re.compile(
    r"(?:^|[;{\s])(background|background-color|color|border|border-color|border-top|"
    r"border-bottom|border-left|border-right|border-top-color|border-bottom-color|"
    r"border-left-color|border-right-color|outline|outline-color|box-shadow|fill|stroke|"
    r"caret-color|text-decoration-color|column-rule-color)\s*:", re.I)
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
RGB = re.compile(r"rgba?\([^)]*\)", re.I)
SCRIPT = re.compile(r"<script\b.*?</script>", re.S | re.I)

# By-design literals needing no var: b/w ink on chips/buttons, near-black run-ink, scrims.
NEUTRAL = {"#fff", "#ffffff", "#000", "#000000", "#0a0a0a", "transparent",
           "currentcolor", "inherit", "none", "initial", "unset"}
# Figure frame (bg+border) on an <svg>: flipped by the svg.gfx-dark !important light rule.
SVG_FRAME = {"#0d0d0d", "#2a2a2a", "#262626", "#0a0a0f"}


def neutral(tok: str) -> bool:
    t = tok.strip().lower()
    if t in NEUTRAL:
        return True
    m = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", t)
    if m and m.group(1) == m.group(2) == m.group(3) and m.group(1) in ("0", "255"):
        return True  # 0/255 grey scrim
    # alpha < 1 is a wash that blends over either theme background, so theme-tolerant.
    a = re.match(r"(?:rgba|hsla)\([^)]*,\s*([\d.]+)\s*\)$", t)
    return bool(a and float(a.group(1)) < 1)


def _usable(f) -> bool:
    return not any(p in ("node_modules", ".ipynb_checkpoints") for p in f.parts)


def chrome_js() -> list:
    """Every course-shipped runtime script, found by GLOB rather than a hardcoded name. So when
    _shared.js is split into several modules (or a notebook-binding file is added), each new file is
    scanned the same way with nothing to update here, and the theme audit cannot silently go dark on
    code that just moved. Recurses, so a split into a subdir is covered too. Excludes node_modules,
    the studio tool (its own palette, out of theme scope), and minified vendor bundles."""
    return [f for f in sorted(NEMO.rglob("*.js"))
            if _usable(f) and not f.name.startswith("studio") and not f.name.endswith(".min.js")]


def style_files() -> list:
    """Every stylesheet under the course dir (glob, recursive), so a palette split into a new .css is
    picked up for var-definition discovery without editing a list here."""
    return [f for f in sorted(NEMO.rglob("*.css")) if _usable(f)]


def defined_vars() -> set[str]:
    """Every CSS custom property the bundle DEFINES (a `--name:` declaration), gathered across the
    stylesheets and pages. A var() reference to a name not in this set has no value to flip, so the
    light theme never reaches it; collecting the definitions here is what makes that detectable."""
    names: set[str] = set()
    for f in style_files() + sorted(NEMO.glob("*.html")) + sorted(WEB.glob("*.html")):
        if f.exists():
            names |= set(re.findall(r"(--[A-Za-z0-9-]+)\s*:", f.read_text(errors="ignore")))  # `--name:` definitions
    return names


def bad_in_style_body(body: str, on_svg=False):
    """Find hard-coded color literals on color-bearing properties inside one CSS declaration body.
    These are the literals that outrank the light-theme rules and so stay dark when the theme flips,
    which is the visual bug this whole check exists to catch. Neutral inks, washes, and the SVG frame
    palette are excluded because they are theme-tolerant or flipped by a dedicated !important rule."""
    out = []
    # white-bg inline element = a deliberately-light surface (paper figure); frame is intentional.
    if re.search(r"background(?:-color)?\s*:\s*#(?:fff|ffffff)\b", body, re.I):
        return out
    stripped = re.sub(r"var\(\s*--[A-Za-z0-9-]+\s*(?:,[^)]*)?\)", "var()", body)  # blank var() so its fallback hex is not flagged
    for decl in stripped.split(";"):                  # one CSS declaration per `;`
        if ":" not in decl:
            continue
        prop, _, val = decl.partition(":")
        if not COLOR_PROPS.search(prop + ":"):        # only properties that actually paint color
            continue
        for tok in HEX.findall(val) + RGB.findall(val):
            if neutral(tok) or (on_svg and tok.lower() in SVG_FRAME):
                continue                              # theme-tolerant ink, or the svg frame that flips by rule
            out.append((tok, prop.strip()))           # a literal that will not flip: report it
    return out


STYLE_BLOCK = re.compile(r"<style\b[^>]*>(.*?)</style>", re.S | re.I)
# A stylesheet injected from JS: `styleEl.textContent = `...css...``.
# The OpenClaw probe does exactly this, so its rules were invisible to both scan_inline and the <style> scan.
STYLE_TEXTCONTENT = re.compile(r"\.textContent\s*=\s*`((?:[^`\\]|\\.)*)`", re.S)
# The CodeMirror editor is intentionally dark in both themes, so its rules are out of scope.
_CM_SEL = re.compile(r"CodeMirror|\.cm-", re.I)


def scan_style_blocks(text: str):
    """Hard-coded colors in CSS rulesets, whether in a <style> tag or injected from JS via
    `el.textContent = `...``. scan_inline only sees style= attributes and .style/.cssText, so a
    rule like `.claw-out{background:#0d0d0d}` (the OpenClaw probe's output panel) slipped through
    and stayed dark on the light theme. Crude `selector { decls }` split; code-editor rules are
    excluded as intentionally dark."""
    blocks = list(STYLE_BLOCK.findall(text))
    blocks += [css for css in STYLE_TEXTCONTENT.findall(text)
               if "{" in css and COLOR_PROPS.search(css)]   # CSS rulesets, not prose templates
    bad = []
    for blk in blocks:
        for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", blk):
            if _CM_SEL.search(m.group(1)):
                continue
            bad += bad_in_style_body(m.group(2))
    return bad


def scan_inline(text: str):
    """Collect hard-coded colors set INLINE: the `style=` attribute and the JS paths that write inline
    style (`.cssText`, `setAttribute('style',...)`, `.style.prop=`). Inline style has the highest
    specificity, so a literal set this way always beats the light theme; these are the leaks the
    <style> scan would never see."""
    bad = []
    for m in re.finditer(r"style\s*=\s*(\\?[\"'])((?:(?!\1).)*)\1", text, re.S):   # re.S: multi-line style= attrs
        body = m.group(2).replace('\\"', '"')
        # look back far enough past a long (multi-line) <svg> tag to find this style='s element.
        back = text[max(0, m.start() - 8000):m.start()]
        lt = back.rfind("<")
        on_svg = bool(lt >= 0 and re.match(r"<svg\b", back[lt:]))
        bad += bad_in_style_body(body, on_svg)
    for m in re.finditer(r"\.cssText\s*=\s*([\"'`])((?:(?!\1).)*)\1", text):
        bad += bad_in_style_body(m.group(2))
    for m in re.finditer(r"setAttribute\(\s*[\"']style[\"']\s*,\s*([\"'`])((?:(?!\1).)*)\1", text):
        bad += bad_in_style_body(m.group(2))
    for m in re.finditer(r"\.style\.([A-Za-z]+)\s*=\s*[\"'`]([^\"'`]*)[\"'`]", text):
        prop, val = m.group(1), m.group(2)
        if not re.search(r"color|background|border|outline|shadow|fill|stroke", prop, re.I):
            continue
        for tok in HEX.findall(val) + RGB.findall(val):
            if not neutral(tok):
                bad.append((tok, "style." + prop))
    return bad


# A color-bearing style fed by a `${var}` interpolation hides a hard-coded default from every literal
# scan above: `function f(t, color = "#e6edf3")` then `cssText = `...;color:${color};...``. The cssText
# carries only `${color}`, so scan_inline reads no literal and the frozen default ships. The log-row
# renderer did exactly this: its panel background is var(--bg) (white in light) while the row text
# stayed a hard-coded light grey, so output went near-invisible on the light theme.
_STYLE_INTERP = re.compile(
    r"(?:background(?:-color)?|(?<![-\w])color|border(?:-[a-z]+)?|outline|box-shadow|fill|stroke|"
    r"caret-color|text-decoration-color)\s*:\s*\$\{\s*([A-Za-z_$][\w$]*)\s*\}", re.I)


def _extreme_ink(tok: str) -> bool:
    """A near-white or near-black hex: it relies on the opposite-tone background to be legible, so it
    goes unreadable when the theme flips (light grey on the now-white panel, the _appendText bug). A
    mid-tone (brand green, semantic amber, a blue) keeps usable contrast on both backgrounds, so it is
    theme-tolerant and not flagged. Only relative luminance decides it; non-hex tokens are not extreme."""
    h = tok.lower().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) < 6 or not re.fullmatch(r"[0-9a-f]{6}", h):
        return False
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    return lum > 0.78 or lum < 0.16


def scan_interpolated_color_defaults(text: str):
    """Hard-coded colors that reach a style only through a `${var}` interpolation, so the literal lives
    in the variable's default or binding rather than in the style string the other scanners read. Pairs
    each `prop:${ident}` color interpolation with a color literal bound to that ident (a default
    parameter or an assignment) in the same file, and flags it when the literal is an EXTREME ink
    (near-white/near-black): the style cannot flip with the theme, so the value frozen at the binding
    goes unreadable on the opposite background. var(--x) binds no literal; neutral inks, the intentional
    SVG frame palette, and theme-tolerant mid-tones are exempt. This is the gap that let the _appendText
    log row stay light-grey on the light theme while its panel background flipped to white."""
    bad = []
    for ident in set(_STYLE_INTERP.findall(text)):
        bind = re.compile(r"\b" + re.escape(ident) + r"""\s*=\s*(["'])(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))\1""")
        for m in bind.finditer(text):
            tok = m.group(2)
            if neutral(tok) or tok.lower() in SVG_FRAME or not _extreme_ink(tok):
                continue
            bad.append((tok, ident + "= (extreme ink interpolated into a color style)"))
    return bad


@functools.lru_cache(maxsize=1)
def svg_sub_sources():
    """The two theme-substitution lists that flip SVG colors to the light palette: the bundler's
    SVG_SUBS (static page SVG, rewritten at build) and _shared.js's _LITE_VIZ_SUBS (runtime charts,
    rewritten by log.svg in the lite export). JS-generated and inline SVG paint with PRESENTATION
    ATTRIBUTES (fill=, stroke=) that no CSS rule and no light stylesheet can reach, so one of these
    lists is the only thing that flips them. A literal handled by EITHER is theme-handled; one in
    NEITHER stays frozen dark, which is the bug. Reading both lists from source keeps the check in
    lockstep with them. Returns (attr_keys, bare_hexes), lowercased: an `attr="#hex"` key, or a bare
    `#hex` that a plain-string substitution flips inside any attribute."""
    attr_keys: set[str] = set()
    bare: set[str] = set()

    def harvest(txt: str, anchor: str):
        i = txt.find(anchor)
        if i < 0:
            return
        blk = txt[i:i + 8000]                           # the list body
        for m in re.finditer(r"[\(\[]\s*('([^']*)'|\"([^\"]*)\")\s*,", blk):   # first elem of each (old,new) pair
            k = (m.group(2) if m.group(2) is not None else m.group(3)).lower()
            if re.match(r"(?:fill|stroke|stop-color|flood-color|lighting-color)=", k):
                attr_keys.add(k)
            elif re.fullmatch(r"#[0-9a-fA-F]{3,8}", k):
                bare.add(k)

    bp = HERE / "bundle_standalone.py"
    if bp.exists():
        harvest(bp.read_text(errors="ignore"), "SVG_SUBS")
    for js in chrome_js():                              # the runtime subs list may live in any chrome module
        harvest(js.read_text(errors="ignore"), "_LITE_VIZ_SUBS")
    return frozenset(attr_keys), frozenset(bare)


SVG_ATTR = re.compile(
    r'\b(fill|stroke|stop-color|flood-color|lighting-color)\s*=\s*"(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))"', re.I)


def scan_svg_attrs(text: str):
    """Hard-coded colors on SVG presentation attributes (fill=, stroke=, stop-color=) in JS-generated
    or inline SVG. scan_inline / scan_style_blocks only see CSS, so a chart drawn as `<rect fill="#161616">`
    or an axis label `<text fill="#b0b0b0">` was never checked, and it stays dark when a student flips
    to light because the only thing that flips an attribute literal is the bundler's SVG_SUBS list.
    Flags every literal NOT in that list (and not a neutral ink); var(--x) attrs are theme-dynamic and
    are skipped by the regex. This is what makes a JS-rendered figure obey the theme like the rest of
    the page."""
    attr_keys, bare_hexes = svg_sub_sources()
    bad = []
    for m in SVG_ATTR.finditer(text):
        attr, tok = m.group(1).lower(), m.group(2)
        if neutral(tok):
            continue
        if f'{attr}="{tok.lower()}"' in attr_keys or tok.lower() in bare_hexes:   # flipped by a substitution list
            continue
        # Skip the entries of a substitution MAP rather than rendered output: a `'fill="#x"'` that is
        # a complete single-quoted JS string is one side of a SVG_SUBS-style pair (log.svg mirrors the
        # bundler's list), so it IS the theming mechanism, not a frozen literal. Rendered SVG always
        # has the attribute inside a wider template, never wrapped tight in its own quotes.
        before = text[m.start() - 1] if m.start() else ""
        after = text[m.end()] if m.end() < len(text) else ""
        if before == "'" and after == "'":
            continue
        bad.append((tok, attr + "= (svg)"))             # an attribute literal the theme cannot reach
    return bad


# A render helper that RESOLVES a CSS color at render time (getComputedStyle / getPropertyValue) and
# bakes it into the markup it builds paints a fixed color into the DOM. That output then ignores the
# theme toggle, so a diagram or cell render stays frozen on whatever theme was active when it ran (the
# "play output in the wrong theme" bug). The fix is always to emit var(--x) and let CSS flip it. This
# flags any chrome module that does BOTH in one file: reads a computed style AND interpolates a value
# into a color-bearing attribute / style. It is a regression guard: with diagramSVG emitting var(),
# nothing trips it; reintroducing a render-time bake lights it back up.
_GCS = re.compile(r"\bgetComputedStyle\b|\.getPropertyValue\s*\(")
_MARKUP_COLOR = re.compile(
    r"""(?:fill|stroke|stop-color|flood-color|color|background(?:-color)?)\s*[:=]\s*["']?\$\{""",
    re.I)


def _strip_js_comments(text: str) -> str:
    """Drop /* */ and // comments so the bake heuristic reads executable code only (a comment that
    merely names getComputedStyle is not a bake). // is left alone after a colon so https:// survives."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"(?<!:)//[^\n]*", " ", text)
    return text


def scan_js_theme_bake(text: str):
    """(snippet, reason) for a render-time color bake: a file that reads computed styles and feeds a
    value straight into color markup, freezing that output against the theme toggle."""
    code = _strip_js_comments(text)
    g = _GCS.search(code)
    if not g or not _MARKUP_COLOR.search(code):
        return []
    snippet = code[g.start():g.start() + 48].splitlines()[0].strip()
    return [(snippet, "getComputedStyle color baked into markup (emit var(--x) so it follows the theme)")]


def run(verbose=True):
    """Driver: gather every non-theme-dynamic color use across the chrome and the pages. It exists so
    a reviewer (and the gate) gets one list of exactly which color literals and undefined var() refs
    will stay stuck on the dark palette when a student flips to light theme, with the file and
    property named. Returns {inline, undefined_var}; the report and exit code are derived from it."""
    defined = defined_vars()                          # the var names that actually have a definition to flip
    inline, undef, bake = [], [], []
    for js in chrome_js():                            # every chrome module (whatever _shared.js was split into)
        t = js.read_text(errors="ignore")
        rel = str(js.relative_to(WEB.parent))
        # inline styles + injected/<style> rulesets + SVG presentation attributes (fill=/stroke=) +
        # hard-coded color defaults that reach a style through a ${var} interpolation
        for tok, prop in (scan_inline(t) + scan_style_blocks(t) + scan_svg_attrs(t)
                          + scan_interpolated_color_defaults(t)):
            inline.append((rel, tok, prop))
        for snippet, reason in scan_js_theme_bake(t):  # render-time color bakes (output frozen vs the toggle)
            bake.append((rel, snippet, reason))
    # Not theme-flipped student pages: the LMS studio export, the agent beacon, the course
    # picker, and the cert page carry their own palettes and are out of the light/dark scope.
    OUT_OF_SCOPE = {"studio.html", "SKILL.html", "courses.html", "cert.html"}
    for f in sorted(NEMO.glob("*.html")) + sorted(WEB.glob("*.html")):
        if f.name in OUT_OF_SCOPE:
            continue
        raw = f.read_text(errors="ignore")
        body = SCRIPT.sub("", raw)                    # body only; <script> is lesson code
        rel = str(f.relative_to(WEB.parent))
        # inline-SVG presentation attributes are scanned on the FULL page (raw), since the page's
        # static <svg> figures live outside <script> but its mountDiagram/viz SVG is built in-script;
        # both paint by attribute and both rely on SVG_SUBS to flip, so both are in scope here.
        for tok, prop in scan_inline(body) + scan_style_blocks(body) + scan_svg_attrs(raw):
            inline.append((rel, tok, prop))
    # Second pass: every var() REFERENCE whose name is never defined anywhere (its lone fallback
    # never flips), scanned across the stylesheets, the chrome, and the pages.
    for f in style_files() + chrome_js() + sorted(NEMO.glob("*.html")) + sorted(WEB.glob("*.html")):
        if not f.exists():
            continue
        rel = str(f.relative_to(WEB.parent))
        for name in set(re.findall(r"var\(\s*(--[A-Za-z0-9-]+)", f.read_text(errors="ignore"))):
            if name.endswith("-"):                    # a glob placeholder in prose (var(--dg-*)), not a real ref
                continue
            if name not in defined:                   # referenced but never declared: theme cannot reach it
                undef.append((rel, name))
    total = len(inline) + len(undef)
    if verbose:
        if inline:
            print(f"[inline hard-coded color] {len(inline)}")
            for (key, n) in Counter((f, tok, prop) for f, tok, prop in inline).most_common(50):
                print(f"   {n:3}  {key[0]:32} {key[1]:9} {key[2]}")
        if undef:
            print(f"[undefined var reference] {len(undef)}")
            for (key, n) in Counter(undef).most_common(30):
                print(f"   {n:3}  {key[0]:32} {key[1]}")
        if bake:
            print(f"[render-time color bake] {len(bake)}")
            for rel, snippet, reason in bake:
                print(f"        {rel}  «{snippet}»  {reason}")
        print(f"\ncolor_theme: {total} non-theme-dynamic color use(s) "
              f"(inline {len(inline)}, undefined-var {len(undef)}, render-bake {len(bake)})")
    return {"inline": inline, "undefined_var": undef, "bake": bake}


if __name__ == "__main__":
    r = run()
    sys.exit(1 if (len(r["inline"]) + len(r["undefined_var"]) + len(r["bake"])) else 0)
