#!/usr/bin/env python3
"""Static legibility / formatting checks the prose suites miss.

Figures are inline SVG with a fixed viewBox and max-width, so on-screen text size is
computable: rendered_px = font_size * render_width / viewBox_width. Flags text under a
legibility floor, text spilling past the figure bounds, and missing a11y affordances
(svg aria-label, img alt, rel=noopener on new-tab links). All advisory.

Checks: tiny-text, text-overflow, no-aria, img-no-alt, blank-link.
Run:  python3 scripts/figure_audit.py
"""
from __future__ import annotations
import re, sys
from pathlib import Path

for _p in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
    if (_p / "scripts" / "_bootstrap.py").exists():
        sys.path.insert(0, str(_p / "scripts")); break
from _bootstrap import add_script_paths, find_repo_root

HERE = Path(__file__).resolve()
TASK1 = find_repo_root(HERE)
WEB = TASK1 / "web"
FLOOR = 9.0                 # px: below this, text is hard to read
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


def audit_file(path: Path):
    """Run the per-figure legibility and a11y checks on one page. This is where a figure with text
    too small to read on screen, text spilling past the figure frame, or an SVG with no screen-reader
    label gets caught before it ships. Returns the five finding lists (tiny, no-aria, overflow,
    img-no-alt, blank-link) that run() aggregates."""
    body = SCRIPT.sub("", path.read_text(errors="ignore"))  # skip lesson/canvas code
    col = column_for(path)
    rel = str(path.relative_to(WEB.parent))
    tiny, noaria, over = [], [], []
    for m in SVG.finditer(body):
        svg = m.group(0)
        # viewBox="minx miny width height" -> width is 3rd token
        vbm = re.search(r'viewBox\s*=\s*"\s*[\d.-]+\s+[\d.-]+\s+([\d.]+)\s+([\d.]+)', svg)
        vbw = float(vbm.group(1)) if vbm else None      # viewBox width: the SVG's own coordinate scale
        mw = re.search(r"max-width\s*:\s*([\d.]+)px", svg)
        render_w = min(float(mw.group(1)), col) if mw else col  # actual on-screen width: capped by max-width or column
        label = (re.search(r'aria-label\s*=\s*"([^"]{0,42})', svg) or [None, "(no aria-label)"])[1]
        if vbw:
            scale = render_w / vbw                      # px-per-viewBox-unit: converts font size to rendered px
            smallest = min((fs for fs, _ in fonts_in(svg)), default=None)
            if smallest is not None and smallest * scale < FLOOR:
                tiny.append((rel, round(smallest * scale, 1), smallest, int(vbw), int(render_w), label))  # below legibility floor
        if "role=\"img\"" not in svg or "aria-label" not in svg:
            if "<text" in svg:                          # decorative markers (no text) need no label
                noaria.append((rel, label))             # a figure with text but no screen-reader label
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
                left = x - (w if anchor == "end" else w / 2 if anchor == "middle" else 0)   # leftmost x given the anchor
                right = x + (0 if anchor == "end" else w / 2 if anchor == "middle" else w)  # rightmost x given the anchor
                if left < -8 or right > vbw + 8:        # spills past the viewBox (clipped / hits the frame)
                    over.append((rel, content[:34], int(left), int(right), int(vbw)))
    # body-only: page <script> is lesson code with functional imgs
    imgs = [rel for m in re.finditer(r"<img\b[^>]*>", body)
            if not re.search(r'\balt\s*=\s*"[^"]+"', m.group(0))]
    blanks = [rel for m in re.finditer(r"<a\b[^>]*target\s*=\s*\"_blank\"[^>]*>", body)
              if "noopener" not in m.group(0)]
    return tiny, noaria, over, imgs, blanks


def run(verbose=True):
    """Driver: audit every nemoclaw page plus the top-level web pages and aggregate the findings. It
    exists so the gate and a reviewer get one accounting of unreadable figure text, overflow, and
    missing a11y across the bundle. Returns the five finding lists; the report and exit code use them."""
    files = sorted((WEB / "nemoclaw").glob("*.html")) + sorted(WEB.glob("*.html"))
    tiny, noaria, over, imgs, blanks = [], [], [], [], []
    for f in files:
        t, n, o, i, b = audit_file(f)             # per-page findings, by category
        tiny += t; noaria += n; over += o; imgs += i; blanks += b
    if verbose:
        if tiny:
            print(f"[tiny text · rendered < {FLOOR}px] {len(tiny)}")
            for rel, rpx, fs, vbw, rw, lab in sorted(tiny, key=lambda x: x[1]):
                print(f"   {rpx:4}px  (font {fs} @ viewBox {vbw}->{rw}px)  {rel}  «{lab}…»")
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
        total = len(tiny) + len(noaria) + len(over) + len(imgs) + len(blanks)
        print(f"\nfigure_audit: {total} finding(s) "
              f"(tiny {len(tiny)}, overflow {len(over)}, no-aria {len(noaria)}, "
              f"img-alt {len(imgs)}, blank-link {len(blanks)})")
    return {"tiny": tiny, "overflow": over, "no_aria": noaria, "img_no_alt": imgs, "blank_link": blanks}


if __name__ == "__main__":
    r = run()
    sys.exit(1 if sum(len(v) for v in r.values()) else 0)
