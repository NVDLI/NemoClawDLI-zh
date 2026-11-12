#!/usr/bin/env python3
# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Write a build-time language manifest for the Pages foyer."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

LABELS = {
    "en": "English",
    "pt": "Portuguese",
    "es": "Spanish",
    "zh": "Simplified Chinese",
}
SKIP_DIRS = {"docs", "scripts", "workspace", "validated-source", "web", "nemoclaw"}
DEFAULT_ROUTE_ID = "default-language-route"


def clean_prefix(prefix: str) -> str:
    return prefix.strip("/")


def language_label(code: str) -> str:
    return LABELS.get(code, code.replace("-", " ").title())


def build_manifest(site: Path, prefix: str = "") -> dict:
    prefix = clean_prefix(prefix)
    english_url = f"{prefix + '/' if prefix else ''}nemoclaw/"
    english_course = site / prefix / "nemoclaw" if prefix else site / "nemoclaw"
    english_pages = sorted(path.name for path in english_course.glob("*.html"))
    languages = [{"code": "en", "locale": "en", "label": language_label("en"),
                  "native_label": "English", "url": english_url,
                  "available_pages": english_pages}]
    defaults: list[str] = []

    for child in sorted(site.iterdir() if site.exists() else [], key=lambda p: p.name):
        if not child.is_dir() or child.name in SKIP_DIRS:
            continue
        code = child.name
        if not re.fullmatch(r"[a-z]{2}(?:-[a-z0-9]+)?", code):
            continue
        course = child / "nemoclaw"
        if (course / "index.html").is_file():
            locale_path = course / "assets" / "locale.json"
            locale = json.loads(locale_path.read_text(encoding="utf-8")) if locale_path.is_file() else {}
            drift_path = course / "assets" / f"localization-{code}.json"
            drift = json.loads(drift_path.read_text(encoding="utf-8")) if drift_path.is_file() else {}
            available = drift.get("available_pages")
            if not isinstance(available, list):
                available = sorted(path.name for path in course.glob("*.html"))
            languages.append({
                "code": code,
                "locale": locale.get("locale", drift.get("locale", code)),
                "label": locale.get("label", drift.get("label", language_label(code))),
                "native_label": locale.get("native_label", drift.get("native_label", language_label(code))),
                "url": f"{code}/nemoclaw/",
                "available_pages": available,
            })
            if locale.get("default") is True:
                defaults.append(code)

    if len(defaults) > 1:
        raise ValueError(f"multiple default course languages: {', '.join(defaults)}")
    return {
        "schema": "nemoclaw-languages/1",
        "default": defaults[0] if defaults else "en",
        "languages": languages,
        "note": "Language entries appear when the build produced that language course under this Pages root.",
    }


def project_default_route(site: Path, data: dict) -> None:
    landing = site / "index.html"
    if not landing.is_file():
        return
    raw = landing.read_text(encoding="utf-8")
    raw = re.sub(rf'\s*<script\s+id="{DEFAULT_ROUTE_ID}">.*?</script>\s*', "\n", raw, flags=re.S)
    default = data.get("default", "en")
    entry = next((item for item in data.get("languages", []) if item.get("code") == default), None)
    if not entry or default == "en":
        landing.write_text(raw, encoding="utf-8")
        return
    target = entry.get("url", "")
    if not target or re.search(r'(^|/)\.\.(?:/|$)|^[a-z]+:', target, re.I):
        raise ValueError(f"unsafe default language route: {target!r}")
    target_literal = json.dumps(target)
    script = (
        f'<script id="{DEFAULT_ROUTE_ID}">\n'
        '(function () {\n'
        f'  var target = new URL({target_literal}, window.location.href);\n'
        '  target.search = window.location.search;\n'
        '  target.hash = window.location.hash;\n'
        '  window.location.replace(target.href);\n'
        '})();\n'
        '</script>\n'
    )
    if not re.search(r"<head(?:\s[^>]*)?>", raw, re.I):
        raise ValueError(f"{landing}: missing head element")
    raw = re.sub(r"(<head(?:\s[^>]*)?>)", lambda match: match.group(1) + "\n" + script,
                 raw, count=1, flags=re.I)
    landing.write_text(raw, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--site-root", required=True)
    ap.add_argument("--course-prefix", default="")
    ap.add_argument("--project-default", action="store_true")
    ns = ap.parse_args()

    site = Path(ns.site_root)
    data = build_manifest(site, ns.course_prefix)
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    if ns.project_default:
        project_default_route(site, data)
    print(f"[languages] wrote {out} ({len(data['languages'])} languages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
