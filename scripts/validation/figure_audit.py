#!/usr/bin/env python3
"""Static legibility / formatting checks the prose suites miss.

Figures are inline or fetched SVG with a fixed viewBox and max-width, so on-screen text size is
computable: rendered_px = font_size * render_width / viewBox_width. Flags text under a
legibility floor, full-width course figures capped too small, text spilling past the figure
bounds, dark-mode-hostile external SVGs, excess viewBox canvas, crowded figure stacks, and
missing a11y affordances (svg aria-label, img alt, rel=noopener on new-tab links).
All advisory.

Checks: tiny-text, small-render, flex-parent, text-overflow, no-aria, img-no-alt, blank-link,
dark-mode, canvas, crowded.
Run:  python3 scripts/validation/figure_audit.py
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

for _p in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
    if (_p / "scripts" / "_bootstrap.py").exists():
        sys.path.insert(0, str(_p / "scripts")); break
from _bootstrap import add_script_paths, find_repo_root

HERE = Path(__file__).resolve()
TASK1 = find_repo_root(HERE)
WEB = TASK1 / "web"
FLOOR = 9.0                 # px: below this, text is hard to read
MIN_RENDER_W = 900           # px: full-width text figures below this read like thumbnails
# Content column (px) a figure renders into. main: 71.25rem ~ 1140px - padding; index: 62.5rem.
COLUMN = {"index.html": 936, "_default": 1076}
SCRIPT = re.compile(r"<script\b.*?</script>", re.S | re.I)
SVG = re.compile(r"<svg\b.*?</svg>", re.S | re.I)


def column_for(path: Path) -> int:
    """The on-screen content-column width (px) this page renders a figure into. Needed because text
    legibility and overflow are judged in RENDERED pixels, and that depends on how wide the column
    actually is; the index page is narrower than the lesson pages."""
    return COLUMN.get(path.name, COLUMN["_default"])


def fonts_in(svg: str):
    """Font sizes (px) on <text>/<tspan>, attr or inline-style form."""
    out = []
    for m in re.finditer(r'font-size\s*=\s*"([\d.]+)"', svg):
        out.append((float(m.group(1)), m.start()))
    for m in re.finditer(r"font-size\s*:\s*([\d.]+)px", svg):
        out.append((float(m.group(1)), m.start()))
    return out


def _resolve_asset(page: Path, src: str) -> Path | None:
    """Resolve a data-svg-src/img src the way the browser does for lesson pages."""
    if not src or src.startswith(("http://", "https://", "data:")):
        return None
    cand = (page.parent / src).resolve()
    try:
        cand.relative_to(TASK1.resolve())
    except ValueError:
        return None
    return cand if cand.exists() else None


def _attrs(tag: str) -> dict[str, str]:
    """Small attribute reader for tags the audit already isolated."""
    return {m.group(1).lower(): m.group(2) for m in re.finditer(r'([\w:-]+)\s*=\s*"([^"]*)"', tag)}


def _fixed_white_assets() -> set[str]:
    """Paper conversions are intentionally fixed-white; course-authored/provided diagrams are not."""
    page = WEB / "nemoclaw" / "assets" / "SKILL.html"
    try:
        raw = page.read_text(errors="ignore")
    except OSError:
        return set()
    m = re.search(r'<script type="application/json" id="provenance">(.*?)</script>', raw, re.S)
    if not m:
        return set()
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return set()
    return {row.get("file", "") for row in data.get("figures", []) if row.get("connection") == "conversion"}


FIXED_WHITE_ASSETS = _fixed_white_assets()


def _asset_key(src: str) -> str:
    return src.split("assets/", 1)[1] if "assets/" in src else src


def _viewbox(svg: str) -> tuple[float, float, float, float] | None:
    m = re.search(r'viewBox\s*=\s*"\s*([\d.-]+)\s+([\d.-]+)\s+([\d.]+)\s+([\d.]+)', svg)
    return tuple(map(float, m.groups())) if m else None


def _max_width(style: str) -> float | None:
    m = re.search(r"max-width\s*:\s*([\d.]+)px", style, re.I)
    return float(m.group(1)) if m else None


def _largest_rect(svg: str) -> tuple[float, float, float, float] | None:
    """Approximate authored canvas bounds from the largest rectangular path in the SVG."""
    best = None
    best_area = 0.0
    for pm in re.finditer(r"<path\b[^>]*>", svg):
        attrs = _attrs(pm.group(0))
        dm = re.match(r"M\s*([\d.-]+)\s+([\d.-]+)H\s*([\d.-]+)V\s*([\d.-]+)H\s*([\d.-]+)Z", attrs.get("d", ""))
        if not dm:
            continue
        x1, y1, x2, y2, x3 = map(float, dm.groups())
        sx = sy = 1.0
        tx = ty = 0.0
        tm = re.search(r"matrix\(([\d.-]+),0,0,([\d.-]+),([\d.-]+),([\d.-]+)\)", attrs.get("transform", ""))
        if tm:
            sx, sy, tx, ty = map(float, tm.groups())
        xs = [x * sx + tx for x in (x1, x2, x3)]
        ys = [y * sy + ty for y in (y1, y2)]
        left, right, top, bottom = min(xs), max(xs), min(ys), max(ys)
        area = max(0.0, right - left) * max(0.0, bottom - top)
        if area > best_area:
            best_area = area
            best = (left, top, right, bottom)
    return best


def _crowded_figures(rel: str, body: str):
    out = []
    pattern = re.compile(r"(?P<prev><figure\b.*?</figure>)\s*(?P<gap>.*?)\s*(?P<next><figure\b)", re.S | re.I)
    for m in pattern.finditer(body):
        joined = m.group("prev") + m.group("next")
        has_nonfixed_external_svg = False
        for im in re.finditer(r"<img\b[^>]*>", joined, re.I):
            src = _attrs(im.group(0)).get("src", "")
            if src.endswith(".svg") and _asset_key(src) not in FIXED_WHITE_ASSETS:
                has_nonfixed_external_svg = True
                break
        if not has_nonfixed_external_svg:
            continue
        words = re.findall(r"[A-Za-z][A-Za-z0-9'-]+", re.sub(r"<[^>]+>", " ", m.group("gap")))
        if len(words) < 35:
            out.append((rel, len(words)))
    return out


def _dark_mode_problems(svg: str, where: str, meta: dict[str, object]):
    if meta.get("fixed_white"):
        return []
    out = []
    if meta.get("kind") == "img":
        out.append((where, "non-conversion course SVG is rendered as plain <img>; use fig-embed/data-svg-src so theme variables and zoom lightbox work"))
    for pm in re.finditer(r"<path\b[^>]*\bfill=\"#(?:fff|ffffff)\"[^>]*>", svg, re.I):
        tag = pm.group(0)
        if re.search(r'\bclass="[^"]*\bos-(?:surface|panel)\b', tag):
            continue
        out.append((where, "non-conversion SVG has unthemed white path fill; darken the canvas/panels or mark it as a fixed-white conversion in provenance"))
        break
    if re.search(r"background\s*:\s*#(?:fff|ffffff)\b", str(meta.get("style", "")), re.I):
        out.append((where, "non-conversion SVG image is framed on a white page background"))
    for im in re.finditer(r"<image\b[^>]*xlink:href=\"data:image/(?:jpeg|png);base64,", svg, re.I):
        tag = im.group(0)
        if not (re.search(r"filter\s*:\s*invert\(", tag, re.I) or re.search(r'\bclass="[^"]*\bos-raster\b', tag)):
            out.append((where, "embedded raster icon may carry a white tile; filter it for dark mode, hook it to a theme class, or replace it with vector art"))
    return out


def _canvas_problems(svg: str, where: str, render_w: float):
    out = []
    vb = _viewbox(svg)
    if not vb:
        return out
    vbx, vby, vbw, vbh = vb
    render_h = render_w * (vbh / vbw) if vbw else 0
    if render_h > 650:
        out.append((where, int(render_h), "rendered height > 650px; crop whitespace or lower the display cap"))
    rect = _largest_rect(svg)
    if rect:
        left, top, right, bottom = rect
        h_margin = max(0.0, (left - vbx) + ((vbx + vbw) - right)) / vbw if vbw else 0
        v_margin = max(0.0, (top - vby) + ((vby + vbh) - bottom)) / vbh if vbh else 0
        if h_margin > 0.10 or v_margin > 0.14:
            out.append((where, int(v_margin * 100), "viewBox has excessive empty canvas around the authored figure"))
    return out


def _embedded_caption_problems(svg: str, where: str):
    """Long sentence-like prose at the top/bottom of an SVG is a caption, not diagram content."""
    out = []
    vb = _viewbox(svg)
    if not vb:
        return out
    _x, vby, _w, vbh = vb
    top = vby + 40
    bottom = vby + vbh - 40
    for tm in re.finditer(r"<text\b([^>]*)>([^<]+)</text>", svg):
        attrs = tm.group(1)
        text = re.sub(r"\s+", " ", re.sub(r"&[a-z]+;|&#\d+;", "x", tm.group(2))).strip()
        ym = re.search(r'\by\s*=\s*"([\d.-]+)"', attrs)
        if not ym or len(text) < 72:
            continue
        y = float(ym.group(1))
        if y <= top or y >= bottom:
            out.append((where, text[:96]))
    return out


def _svg_cases(path: Path, body: str):
    """Yield (svg, label, fetched, meta) for inline SVGs and local external SVG figures."""
    rel = str(path.relative_to(WEB.parent))
    for m in SVG.finditer(body):
        yield m.group(0), rel, False, {}
    for m in re.finditer(r'<[^>]+data-svg-src\s*=\s*"([^"]+)"[^>]*>', body):
        src = m.group(1)
        asset = _resolve_asset(path, src)
        if not asset or asset.suffix.lower() != ".svg":
            continue
        try:
            svg = asset.read_text(errors="ignore")
        except OSError:
            continue
        yield svg, f"{rel} -> {src}", True, {"src": src, "style": "", "fixed_white": _asset_key(src) in FIXED_WHITE_ASSETS, "kind": "data"}
    for m in re.finditer(r"<img\b[^>]*>", body, re.I):
        tag = m.group(0)
        attrs = _attrs(tag)
        src = attrs.get("src", "")
        asset = _resolve_asset(path, src)
        if not asset or asset.suffix.lower() != ".svg":
            continue
        try:
            svg = asset.read_text(errors="ignore")
        except OSError:
            continue
        yield svg, f"{rel} -> {src}", True, {"src": src, "style": attrs.get("style", ""), "fixed_white": _asset_key(src) in FIXED_WHITE_ASSETS, "kind": "img"}


def audit_file(path: Path):
    """Run render-size, legibility, and a11y checks on one page. This catches both inline
    SVG and fetched <div data-svg-src=...> course figures before they ship."""
    body = SCRIPT.sub("", path.read_text(errors="ignore"))  # skip lesson/canvas code
    col = column_for(path)
    rel = str(path.relative_to(WEB.parent))
    tiny, small, noaria, over, dark, canvas, embedded_caption = [], [], [], [], [], [], []
    for svg, where, fetched, meta in _svg_cases(path, body):
        # viewBox="minx miny width height" -> width is 3rd token
        vb = _viewbox(svg)
        vbw = vb[2] if vb else None      # viewBox width: the SVG's own coordinate scale
        mw = _max_width(str(meta.get("style", ""))) or (_max_width(svg) if not meta.get("src") else None)
        render_w = min(float(mw), col) if mw else col  # actual on-screen width: capped by max-width or column
        label = (re.search(r'aria-label\s*=\s*"([^"]{0,42})', svg) or [None, "(no aria-label)"])[1]
        has_text = "<text" in svg
        dark += _dark_mode_problems(svg, where, meta)
        if fetched and has_text and not meta.get("fixed_white"):
            embedded_caption += _embedded_caption_problems(svg, where)
        if fetched and has_text and not meta.get("fixed_white") and meta.get("kind") == "img":
            canvas += _canvas_problems(svg, where, render_w)
        if vbw:
            scale = render_w / vbw                      # px-per-viewBox-unit: converts font size to rendered px
            smallest = min((fs for fs, _ in fonts_in(svg)), default=None)
            if smallest is not None and smallest * scale < FLOOR:
                tiny.append((where, round(smallest * scale, 1), smallest, int(vbw), int(render_w), label))  # below legibility floor
            if fetched and has_text and render_w < MIN_RENDER_W:
                small.append((where, int(render_w), MIN_RENDER_W, label))
        if meta.get("kind") != "img" and ("role=\"img\"" not in svg or "aria-label" not in svg):
            if has_text:                                # decorative markers (no text) need no label
                noaria.append((where, label))           # a figure with text but no screen-reader label
        # text past the figure's horizontal bounds (clipped / hits the frame); width est. from chars
        if vbw:
            for tm in re.finditer(r"<text\b([^>]*)>([^<]+)</text>", svg):
                attrs, content = tm.group(1), re.sub(r"&[a-z]+;|&#\d+;", "x", tm.group(2)).strip()
                if not content or "${" in content:
                    continue
                fm = re.search(r'font-size\s*=\s*"([\d.]+)"', attrs) or re.search(r"font-size\s*:\s*([\d.]+)px", attrs)
                xm = re.search(r'\bx\s*=\s*"([\d.-]+)"', attrs)
                if not fm or not xm:
                    continue
                fs2, x = float(fm.group(1)), float(xm.group(1))
                w = len(content) * fs2 * 0.58           # estimate label width from char count and font size
                anchor = "middle" if 'text-anchor="middle"' in attrs or "text-anchor:middle" in attrs else \
                         ("end" if 'text-anchor="end"' in attrs or "text-anchor:end" in attrs else "start")
                left = x - (w if anchor == "end" else w / 2 if anchor == "middle" else 0)
                right = x + (0 if anchor == "end" else w / 2 if anchor == "middle" else w)
                if left < -8 or right > vbw + 8:
                    over.append((where, content[:34], int(left), int(right), int(vbw)))
    # body-only: page <script> is lesson code with functional imgs
    imgs = [rel for m in re.finditer(r"<img\b[^>]*>", body)
            if not re.search(r'\balt\s*=\s*"[^"]+"', m.group(0))]
    flex_parent = []
    for m in re.finditer(r'<(?P<tag>\w+)\b(?P<attrs>[^>]*)>\s*<[^>]+data-svg-src\s*=\s*"([^"]+)"', body, re.S):
        attrs = m.group('attrs')
        sm = re.search(r'style\s*=\s*"([^"]*)"', attrs, re.I)
        style = sm.group(1) if sm else ''
        if re.search(r'display\s*:\s*flex', style, re.I) and not re.search(r'\bwidth\s*:', style, re.I):
            flex_parent.append((rel, m.group(3), style[:90]))
    blanks = [rel for m in re.finditer(r"<a\b[^>]*target\s*=\s*\"_blank\"[^>]*>", body)
              if "noopener" not in m.group(0)]
    crowded = _crowded_figures(rel, body)
    return tiny, small, flex_parent, noaria, over, imgs, blanks, dark, canvas, crowded, embedded_caption


def run(verbose=True):
    """Driver: audit every nemoclaw page plus the top-level web pages and aggregate the findings. It
    exists so the gate and a reviewer get one accounting of unreadable figure text, overflow, and
    missing a11y across the bundle. Returns the five finding lists; the report and exit code use them."""
    files = sorted((WEB / "nemoclaw").glob("*.html")) + sorted(WEB.glob("*.html"))
    tiny, small, flex_parent, noaria, over, imgs, blanks, dark, canvas, crowded, embedded_caption = [], [], [], [], [], [], [], [], [], [], []
    for f in files:
        t, s, fp, n, o, i, b, d, c, cr, ec = audit_file(f)      # per-page findings, by category
        tiny += t; small += s; flex_parent += fp; noaria += n; over += o; imgs += i; blanks += b
        dark += d; canvas += c; crowded += cr; embedded_caption += ec
    if verbose:
        if tiny:
            print(f"[tiny text · rendered < {FLOOR}px] {len(tiny)}")
            for rel, rpx, fs, vbw, rw, lab in sorted(tiny, key=lambda x: x[1]):
                print(f"   {rpx:4}px  (font {fs} @ viewBox {vbw}->{rw}px)  {rel}  «{lab}…»")
        if small:
            print(f"[small rendered figure · rendered < {MIN_RENDER_W}px] {len(small)}")
            for rel, rw, floor, lab in sorted(small, key=lambda x: x[1]):
                print(f"   {rw:4}px  (< {floor}px)  {rel}  «{lab}…»")
        if flex_parent:
            print(f"[shrink-prone flex figure parent] {len(flex_parent)}")
            for rel, src, style in flex_parent:
                print(f'        {rel} -> {src}  parent style="{style}"')
        if over:
            print(f"[text overflows figure bounds] {len(over)}")
            for rel, txt, lf, rt, vbw in over:
                print(f"        {rel}  x-extent [{lf},{rt}] vs viewBox 0..{vbw}  «{txt}…»")
        if noaria:
            print(f"[svg missing role/aria-label] {len(noaria)}")
            for rel, lab in noaria:
                print(f"        {rel}  «{lab}…»")
        if imgs:
            print(f"[img missing alt] {len(imgs)}: {sorted(set(imgs))}")
        if blanks:
            print(f"[target=_blank missing rel=noopener] {len(blanks)}: {sorted(set(blanks))}")
        if dark:
            print(f"[dark-mode-unfriendly SVG image] {len(dark)}")
            for rel, msg in dark:
                print(f"        {rel}  {msg}")
        if canvas:
            print(f"[oversized / uncropped SVG image] {len(canvas)}")
            for item in canvas:
                print(f"        {item[0]}  {item[2]}")
        if crowded:
            print(f"[crowded consecutive figures] {len(crowded)}")
            for rel, words in crowded:
                print(f"        {rel}  only {words} word(s) between consecutive figures")
        if embedded_caption:
            print(f"[embedded SVG caption prose] {len(embedded_caption)}")
            for rel, text in embedded_caption:
                print(f"        {rel}  «{text}…»")
        total = (len(tiny) + len(small) + len(flex_parent) + len(noaria) + len(over) + len(imgs)
                 + len(blanks) + len(dark) + len(canvas) + len(crowded) + len(embedded_caption))
        print(f"\nfigure_audit: {total} finding(s) "
              f"(tiny {len(tiny)}, small {len(small)}, flex-parent {len(flex_parent)}, "
              f"overflow {len(over)}, no-aria {len(noaria)}, img-alt {len(imgs)}, blank-link {len(blanks)}, "
              f"dark-mode {len(dark)}, canvas {len(canvas)}, crowded {len(crowded)}, "
              f"embedded-caption {len(embedded_caption)})")
    return {"tiny": tiny, "small_render": small, "flex_parent": flex_parent, "overflow": over,
            "no_aria": noaria, "img_no_alt": imgs, "blank_link": blanks, "dark_mode": dark,
            "canvas": canvas, "crowded": crowded, "embedded_caption": embedded_caption}


if __name__ == "__main__":
    r = run()
    sys.exit(1 if sum(len(v) for v in r.values()) else 0)
