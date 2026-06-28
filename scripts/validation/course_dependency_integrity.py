#!/usr/bin/env python3
"""Keep fixed third-party UI assets pinned to their expected CDN bytes."""
from __future__ import annotations

import re
import sys
from pathlib import Path

for _p in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
    if (_p / "scripts" / "_bootstrap.py").exists():
        sys.path.insert(0, str(_p / "scripts"))
        break
from _bootstrap import find_repo_root

ROOT = find_repo_root(Path(__file__).resolve())
COURSE = ROOT / "web" / "nemoclaw"
HASHES = {
    "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.10.0/highlight.min.js": "sha384-GdEWAbCjn+ghjX0gLx7/N1hyTVmPAjdC2OvoAA0RyNcAOhqwtT8qnbCxWle2+uJX",
    "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css": "sha384-zaeBlB/vwYsDRSlFajnDd7OydJ0cWk+c2OWybl3eSUf6hW2EbhlCsQPqKr3gkznT",
    "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/theme/monokai.min.css": "sha384-05WuhgjXiqmZzcQ3vQRQ39HN356Yqb+SnhvELzFtpwS5b2IlqE8QsOO5LCSJ2znj",
    "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js": "sha384-ZYmwuq4n2gOcNxMSiJ6jyTj+BbIrilr7p6dlq6q5nmSWKmsH9UU4K1qqjycMkfmR",
    "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/javascript/javascript.min.js": "sha384-g0o+WW9mdIxA7LaaCKTkRm0M5TVT+Bb4s9eocxPsI2G0Xm0POG9iD6G6qP1IIsfS",
}


def audit() -> list[str]:
    findings = []
    pages = [*COURSE.glob("*.html"), COURSE / "scripts" / "SKILL.html"]
    for page in pages:
        text = page.read_text(encoding="utf-8", errors="replace")
        for url, digest in HASHES.items():
            if url not in text:
                continue
            tag = re.search(r"<(?:script|link)\b[^>]*" + re.escape(url) + r"[^>]*>", text, re.I)
            rel = page.relative_to(ROOT)
            if not tag or f'integrity="{digest}"' not in tag.group(0) or 'crossorigin="anonymous"' not in tag.group(0):
                findings.append(f"{rel}: fixed CDN asset lacks expected SRI/crossorigin: {url}")
    return findings


if __name__ == "__main__":
    findings = audit()
    if findings:
        print("course_dependency_integrity: FAIL")
        print("\n".join("  - " + item for item in findings))
        raise SystemExit(1)
    print("course_dependency_integrity: OK")
