#!/usr/bin/env python3
# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""module_check.py verifies ES-module import/export integrity across the web course.

The course pages and the _*.js modules import named bindings from ./_shared.js, and _shared.js
re-exports the names it pulls from the extracted modules (_glossary.js, _openclaw.js, ...). When
an extraction drops a name from that re-export, every page importing it breaks at load with
"does not provide an export named X". That is exactly how glossary.html broke once. render_check catches
that in a real browser; this catches the same class statically in milliseconds with no browser, so
it is cheap enough to run on every commit.

Two checks per directory:
  1. Every `import { a, b } from "./mod.js"` resolves to a real export of mod.js (re-exports
     count, since `export { a }` is itself an export).
  2. Every name a module lists in `export { ... }` is defined in that module or imported into
     it (no re-exporting a name you never brought in).

Usage:
    python3 scripts/runtime/module_check.py                  # web/nemoclaw (default)
    python3 scripts/runtime/module_check.py --dir web        # the bundle root
Exit non-zero on any unresolved import or dangling re-export, so it works as a gate.
"""
import argparse, os, re, sys, glob
from pathlib import Path

_DECL = re.compile(r'\bexport\s+(?:async\s+)?(?:function|const|let|var|class)\s+([A-Za-z_$][\w$]*)')
_EXPORT_BLOCK = re.compile(r'\bexport\s*\{([^}]*)\}')
_IMPORT_BLOCK = re.compile(r'\bimport\s*\{([^}]*)\}\s*from\s*["\']([^"\']+)["\']')
_LOCAL_DECL = re.compile(r'\b(?:function|const|let|var|class)\s+([A-Za-z_$][\w$]*)')


def _names_in_clause(clause, want="exported"):
    """Yield the binding names a `{ ... }` import/export clause introduces.
    For `A as B`: the exported name is B; the imported name needed from the source is A."""
    for part in clause.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.match(r'([A-Za-z_$][\w$]*)\s+as\s+([A-Za-z_$][\w$]*)', part)
        if m:
            yield m.group(2) if want == "exported" else m.group(1)
        else:
            m2 = re.match(r'([A-Za-z_$][\w$]*)', part)
            if m2:
                yield m2.group(1)


def parse_exports(src):
    names = set(_DECL.findall(src))
    for blk in _EXPORT_BLOCK.finditer(src):
        # Count re-export-from names as real exports of this module.
        names.update(_names_in_clause(blk.group(1), "exported"))
    return names


def parse_imports(src):
    """-> list of (source_module, [names_needed_from_it])."""
    out = []
    for m in _IMPORT_BLOCK.finditer(src):
        out.append((m.group(2), list(_names_in_clause(m.group(1), "imported"))))
    return out


def local_bindings(src):
    """Names defined or imported in a module (for the honest-re-export check)."""
    names = set(_LOCAL_DECL.findall(src))
    for m in _IMPORT_BLOCK.finditer(src):
        names.update(_names_in_clause(m.group(1), "exported"))  # local alias is the binding name
    return names


def unused_imports(src):
    """Imported names that never appear again in the file body. A dead import is harmless at
    runtime but it is drift: it implies the code that used it moved or was deleted (this is how
    the stale `chat` import in _openclaw.js was caught). Advisory only, since a name referenced
    solely inside a string would read as unused; triage before removing."""
    imported = []
    for m in _IMPORT_BLOCK.finditer(src):
        for part in m.group(1).split(","):
            part = part.strip()
            if not part:
                continue
            mm = re.match(r'[A-Za-z_$][\w$]*\s+as\s+([A-Za-z_$][\w$]*)', part)
            imported.append(mm.group(1) if mm else re.match(r'([A-Za-z_$][\w$]*)', part).group(1))
    body = _IMPORT_BLOCK.sub("", src)   # drop the import lines, then look for each name
    return [n for n in imported if not re.search(r'\b' + re.escape(n) + r'\b', body)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="web/nemoclaw")
    ap.add_argument("--dead", action="store_true", help="also report dead (never-referenced) imports, advisory only")
    a = ap.parse_args()
    root = Path(a.dir).resolve()
    if not root.is_dir():
        sys.exit("module_check: no such dir: " + str(root))
    module_root = root / "scripts" if (root / "scripts").is_dir() else root

    # Export table for every module in the module dir.
    exports = {}
    for f in sorted(module_root.glob("*.js")):
        exports[f.name] = parse_exports(f.read_text(encoding="utf-8"))

    problems = []

    # Check 1: every relative-import name resolves.
    files = sorted(root.glob("*.html")) + sorted(module_root.glob("*.js"))
    for f in files:
        src = f.read_text(encoding="utf-8")
        for mod, names in parse_imports(src):
            if not mod.startswith("."):
                continue  # external (CDN) import
            target_path = (f.parent / mod).resolve()
            try:
                target = target_path.relative_to(module_root).name if target_path.parent == module_root else target_path.name
            except ValueError:
                target = target_path.name
            if target not in exports:
                problems.append("%s imports from %s, which is not a module in %s" % (f.name, mod, module_root))
                continue
            for n in names:
                if n not in exports[target]:
                    problems.append("%s imports `%s` from %s, but %s does not export it"
                                    % (f.name, n, mod, target))

    # Check 2: re-exported names are actually present in the module.
    for f in sorted(module_root.glob("*.js")):
        name = f.name
        src = f.read_text(encoding="utf-8")
        local = local_bindings(src)
        for blk in _EXPORT_BLOCK.finditer(src):
            # `export { x } from "./y"` brings x straight through; not a dangling re-export.
            tail = src[blk.end():blk.end() + 40]
            if re.match(r'\s*from\s*["\']', tail):
                continue
            for n in _names_in_clause(blk.group(1), "imported"):
                if n not in local:
                    problems.append("%s re-exports `%s` but never defines or imports it" % (name, n))

    if a.dead:
        dead_any = False
        for f in files:
            dead = unused_imports(f.read_text(encoding="utf-8"))
            if dead:
                dead_any = True
                print("  · %s: dead import(s): %s" % (f.name, ", ".join(dead)))
        if not dead_any:
            print("  · no dead imports")

    nmods = len(exports)
    if problems:
        print("module_check: %d integrity problem(s) under %s" % (len(problems), a.dir))
        for p in problems:
            print("  ✗ " + p)
        sys.exit(1)
    print("module_check: %d modules, all imports resolve and all re-exports are honest (%s)" % (nmods, a.dir))


if __name__ == "__main__":
    main()
