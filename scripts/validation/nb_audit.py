#!/usr/bin/env python3
"""Course-notebook structural audit.

Catches the IDE-buffer-merge corruption patterns we've actually seen:

  REAL signals (fail audit):
    A. Multiple H1 banners in one file (more than the one expected at the top).
    B. Duplicate `## **Part N:**` headers within a file.
    C. Doubled identifiers like `chatchat`, `thinkthink`, or model-name
       interleaves like `nvidia/nemotron-nano-nvidia/nemotron-nano-...`.

  Soft signals (warn unless --strict):
    D. Verbatim long-paragraph repeats. False positives common (the course
       banner appears top+bottom by design and some code blocks are
       intentionally identical between cells), so we only warn.

Usage:
    python3 scripts/validation/nb_audit.py            # exit 1 on REAL issue, 0 otherwise
    python3 scripts/validation/nb_audit.py --strict   # also fail on soft signals
    python3 scripts/validation/nb_audit.py PATH ...   # audit specific files

Run after every edit.
"""
from __future__ import annotations
import argparse, re, sys
from pathlib import Path

H1_RX   = re.compile(r"^<h1 style=", re.M)
# Capture the full part identifier including optional sub-part (e.g. "1.2" in "Part 1.2:")
# so that Part 1.1 / Part 1.2 / Part 1.3 are NOT treated as duplicates of Part 1.
PART_RX = re.compile(r"^## \*\*Part\s+([\d]+(?:\.\d+)?)[:.\*]", re.M)

DOUBLED_IDENT_RX = re.compile(r"\b([A-Za-z][A-Za-z0-9_./-]{2,}[A-Za-z0-9])\1\b")
# Model-name interleave: require the two `nvidia/nemotron` occurrences to be
# adjacent, meaning only letters/digits/hyphens sit between them. This excludes
# legitimate Markdown links like `[**nvidia/nemotron-...**](https://build.nvidia.com/nvidia/nemotron-...)`.
NEMOTRON_INTERLEAVE_RX = re.compile(r"nvidia/nemotron-[a-z0-9-]{0,50}nvidia/nemotron-")

# Known false-positive doubled tokens (legitimate in our corpus).
DOUBLED_FALSE_POSITIVES = {"rw-rw-"}

# Identifiers we've actually seen the IDE corrupt by doubling.
# Any of these appearing as `tokentoken` is a hard-fail regardless of length filter.
CORRUPTION_PRONE_IDS = {
    "chat", "think", "prompt", "reply", "invoke", "stream",
    "content", "client", "model", "llm", "user", "agent",
    "session", "context", "tool",
}


def audit(path: Path):
    text = path.read_text(errors="replace")
    real: list[str] = []
    soft: list[str] = []

    h1_n = len(H1_RX.findall(text))
    if h1_n > 1:
        real.append(f"H1 banner appears {h1_n}x (expected 1)")

    parts = [m.group(1) for m in PART_RX.finditer(text)]  # keep as string ("1.1", "2", etc.)
    seen, dups = set(), []
    for p in parts:
        if p in seen:
            dups.append(p)
        seen.add(p)
    if dups:
        real.append(f"Part headers duplicated: {dups}")

    for m in DOUBLED_IDENT_RX.finditer(text):
        tok = m.group(1)
        if tok.lower() in DOUBLED_FALSE_POSITIVES:
            continue
        # Hard fail on known IDE-corruption-prone identifiers regardless of length.
        if tok.lower() in CORRUPTION_PRONE_IDS:
            real.append(f"doubled identifier: {tok!r}{tok!r} at offset {m.start()}")
            break
        # Otherwise require either a special char (path/snake/kebab) or length>=5.
        if (len(tok) >= 4 and any(c in tok for c in "_./-")) or len(tok) >= 5:
            real.append(f"doubled identifier: {tok!r}{tok!r} at offset {m.start()}")
            break

    for m in NEMOTRON_INTERLEAVE_RX.finditer(text):
        snippet = m.group(0)
        if " " not in snippet and "\n" not in snippet:
            real.append(f"interleaved model name: {snippet[:80]!r}")
            break

    for c in (s.strip() for s in text.split("\n\n")):
        if len(c) < 400 or c.startswith("<a href=") or c.startswith("<br>"):
            continue
        if text.count(c) > 1:
            soft.append(f"paragraph repeated verbatim ({len(c)}c): {c[:80]!r}...")
            break

    return real, soft


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="also fail on soft signals (verbatim paragraph repeats)")
    ap.add_argument("paths", nargs="*",
                    help="paths to audit; default: all course notebooks")
    args = ap.parse_args()

    if args.paths:
        files = [Path(p) for p in args.paths if Path(p).exists()]
    else:
        # Auto-discover: every directory under cpu/ that contains .md files (the
        # release is browser-only, so cpu/ holds the shared service docs; any
        # notebook track a future change adds under cpu/ is picked up too).
        # Ignore auto-generated checkpoint copies.
        files = []
        for top in ("cpu",):
            root = Path(top)
            if not root.exists():
                continue
            for sub in sorted(root.iterdir()):
                if not sub.is_dir():
                    continue
                for md in sorted(sub.glob("*.md")):
                    files.append(md)
                # Also pick up one level deeper but skip checkpoint dirs.
                for md in sorted(sub.rglob("*.md")):
                    if any(part.startswith(".") for part in md.parts):
                        continue   # .ipynb_checkpoints, .git, etc.
                    if md not in files:
                        files.append(md)

    n_real, n_soft = 0, 0
    for f in files:
        real, soft = audit(f)
        if real:
            n_real += len(real)
            print(f"!! {f}")
            for i in real:
                print(f"   - {i}")
        if soft and args.strict:
            n_soft += len(soft)
            print(f"~~ {f}  (soft)")
            for i in soft:
                print(f"   - {i}")

    summary = f"{n_real} REAL issues"
    if args.strict:
        summary += f", {n_soft} soft issues"
    print(f"\n=== {summary} across {len(files)} files ===")
    sys.exit(1 if n_real or (args.strict and n_soft) else 0)


if __name__ == "__main__":
    main()
