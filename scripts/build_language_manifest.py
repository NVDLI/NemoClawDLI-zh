#!/usr/bin/env python3
"""Write a build-time language manifest for the Pages foyer."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

LABELS = {
    "en": "English",
    "pt": "Portuguese",
}
SKIP_DIRS = {"cors-proxy", "docs", "scripts", "workspace", "validated-source", "web", "nemoclaw"}


def clean_prefix(prefix: str) -> str:
    return prefix.strip("/")


def language_label(code: str) -> str:
    return LABELS.get(code, code.replace("-", " ").title())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--site-root", required=True)
    ap.add_argument("--course-prefix", default="")
    ns = ap.parse_args()

    site = Path(ns.site_root)
    prefix = clean_prefix(ns.course_prefix)
    english_url = f"{prefix + '/' if prefix else ''}nemoclaw/"
    languages = [{"code": "en", "label": language_label("en"), "url": english_url, "current": True}]

    for child in sorted(site.iterdir() if site.exists() else [], key=lambda p: p.name):
        if not child.is_dir() or child.name in SKIP_DIRS:
            continue
        code = child.name
        if not re.fullmatch(r"[a-z]{2}(?:-[a-z0-9]+)?", code):
            continue
        if (child / "nemoclaw" / "index.html").is_file():
            languages.append({"code": code, "label": language_label(code), "url": f"{code}/nemoclaw/", "current": False})

    data = {
        "schema": "nemoclaw-languages/1",
        "default": "en",
        "languages": languages,
        "note": "Language entries appear when the build produced that language course under this Pages root.",
    }
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"[languages] wrote {out} ({len(languages)} languages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
