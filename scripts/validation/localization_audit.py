#!/usr/bin/env python3
"""Validate sparse same-branch localizations and emit the Studio drift manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

for _p in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
    if (_p / "scripts" / "_bootstrap.py").exists():
        sys.path.insert(0, str(_p / "scripts"))
        break
from _bootstrap import find_repo_root

ROOT = find_repo_root(Path(__file__).resolve())
SKIP_TEXT = {"script", "style", "pre", "code", "svg", "noscript"}
INTERFACE_CONTRACT = {
    "web/nemoclaw/localization.html": ("id=\"loc-filters\"", "id=\"loc-source\"", "id=\"loc-target\"", "scripts/localization_main.js"),
    "web/nemoclaw/scripts/localization_main.js": ("assets/localization-pt.json", '"current", "stale", "blocked", "needs-review", "missing"', "reviewed_source_sha256"),
    "web/nemoclaw/scripts/_locale.js": ("mountLanguageMenu", "available_pages", 'aria-haspopup', "languageFallback", "language-fallback-badge"),
    "web/nemoclaw/scripts/_shared.js": ("mountLanguageMenu()",),
    "web/nemoclaw/studio.html": ('href="localization.html"',),
    "scripts/build/build_language_manifest.py": ("native_label", "available_pages", "localization-"),
    "scripts/build/build_pages.sh": ("assemble_locale_overlay.py",),
    "scripts/build/assemble_locale_overlay.py": ("source_sha256", "self-test", "stale translation did not fall back"),
    "scripts/validation/localization_runtime_audit.py": ("pageerror", "language-menu entries are clipped", "Localization Studio"),
    ".gitlab-ci.yml": ("assemble_locale_overlay.py --self-test", "localization_audit.py --self-test", "localization_audit.py --locale pt-BR"),
    "scripts/translate/SKILL.html": ("locales/pt-BR/SKILL.html", "same-branch localization"),
}


class ReaderText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in SKIP_TEXT:
            self.depth += 1
        if not self.depth:
            for key, value in attrs:
                if key.lower() in {"alt", "aria-label", "placeholder", "title"} and value:
                    self.parts.append(value.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in SKIP_TEXT and self.depth:
            self.depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.depth and data.strip():
            self.parts.append(data.strip())


class TagSkeleton(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(f"<{tag.lower()}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(f"<{tag.lower()}/>")

    def handle_endtag(self, tag: str) -> None:
        self.tags.append(f"</{tag.lower()}>")


def sha(raw: str) -> str:
    return hashlib.sha256(raw.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def reader_text(raw: str) -> str:
    parser = ReaderText()
    parser.feed(raw)
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def tag_skeleton(raw: str) -> list[str]:
    parser = TagSkeleton()
    parser.feed(raw)
    return parser.tags


def js_shape(raw: str) -> str:
    """Remove comments, whitespace, and string text while retaining executable tokens."""
    out: list[str] = []
    i = 0
    while i < len(raw):
        char = raw[i]
        following = raw[i + 1] if i + 1 < len(raw) else ""
        if char == "/" and following == "/":
            i += 2
            while i < len(raw) and raw[i] not in "\r\n":
                i += 1
            continue
        if char == "/" and following == "*":
            end = raw.find("*/", i + 2)
            i = len(raw) if end < 0 else end + 2
            continue
        if char in {'"', "'", "`"}:
            quote = char
            i += 1
            while i < len(raw):
                if raw[i] == "\\":
                    i += 2
                    continue
                if raw[i] == quote:
                    i += 1
                    break
                i += 1
            out.append("S")
            continue
        if not char.isspace():
            out.append(char)
        i += 1
    return "".join(out)


def script_shapes(raw: str) -> list[str]:
    inline = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", raw, re.S | re.I)
    cells = re.findall(r"\bcode\s*:\s*`((?:\\.|[^`])*)`", raw, re.S)
    return [js_shape(item) for item in inline + cells]


def scripted_ui_text(raw: str) -> str:
    """Extract common learner-facing object fields without treating model prompts as UI prose."""
    values = []
    pattern = r'\b(?:label|intro|title|summary|greeting)\s*:\s*(["\'])(.*?)(?<!\\)\1'
    for match in re.finditer(pattern, raw, re.S):
        values.append(match.group(2).replace("\\n", " "))
    call_pattern = r'\b(?:helpers\.log|log(?:\.h|\.details|\.html)?|info|show)\s*\(\s*(["\'])(.*?)(?<!\\)\1'
    for match in re.finditer(call_pattern, raw, re.S):
        values.append(match.group(2).replace("\\n", " "))
    return re.sub(r"\s+", " ", " ".join(values)).strip()


def html_lang(raw: str) -> str:
    match = re.search(r"<html\b[^>]*\blang=[\"']([^\"']+)", raw, re.I)
    return match.group(1) if match else ""


def html_ids(raw: str) -> set[str]:
    return set(re.findall(r"\bid=[\"']([^\"']+)", raw, re.I))


def local_deps(raw: str) -> set[str]:
    refs = re.findall(r"<(?:script|link)\b[^>]*(?:src|href)=[\"']([^\"']+)", raw, re.I)
    return {ref for ref in refs if not re.match(r"(?:https?:|data:|#)", ref)}


def skill_meta(raw: str) -> object | None:
    match = re.search(r'<script[^>]*id=["\']skill-meta["\'][^>]*>(.*?)</script>', raw, re.S | re.I)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def canonical_pages(root: Path) -> list[Path]:
    pages = [root / "web" / "index.html", root / "web" / "courses.html"]
    pages.extend(sorted((root / "web" / "nemoclaw").glob("*.html")))
    return [page for page in pages if page.is_file() and page.name not in {"localization.html"}]


def locale_paths(root: Path, locale: str) -> tuple[Path, Path, Path, dict, dict]:
    profile_path = root / "scripts" / "translate" / "locales" / locale / "profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    locale_root = root / "i18n" / profile["url_code"]
    state_path = locale_root / "localization_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    return profile_path, locale_root, state_path, profile, state


def interface_findings(root: Path) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for rel, tokens in INTERFACE_CONTRACT.items():
        path = root / rel
        if not path.is_file():
            out.append({"code": "interface-file", "path": rel, "detail": "required localization interface file is missing"})
            continue
        raw = path.read_text(encoding="utf-8")
        for token in tokens:
            if token not in raw:
                out.append({"code": "interface-contract", "path": rel, "detail": f"missing contract token: {token}"})
    return out


def page_quality(source_raw: str, target_raw: str, profile: dict, *, skill: bool = False) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    expected_lang = profile["html_lang"]
    if html_lang(target_raw) != expected_lang:
        out.append({"code": "html-lang", "detail": f"expected <html lang=\"{expected_lang}\">"})
    ui_text = scripted_ui_text(target_raw)
    visible = reader_text(target_raw) + " " + ui_text
    for marker in profile.get("english_sentence_markers", []):
        if marker in visible:
            out.append({"code": "untranslated-english", "detail": f"reader text still contains {marker!r}"})
    for marker in profile.get("english_ui_markers", []):
        if marker.lower() in ui_text.lower():
            out.append({"code": "untranslated-ui", "detail": f"scripted learner UI still contains {marker!r}"})
    for phrase, fix in profile.get("unfit_phrases", {}).items():
        if re.search(rf"(?i)\b{re.escape(phrase)}\b", visible):
            out.append({"code": "unfit-pt-br", "detail": f"{phrase!r}: {fix}"})
    missing_ids = sorted(html_ids(source_raw) - html_ids(target_raw))
    if missing_ids:
        out.append({"code": "structure-ids", "detail": "missing source ids: " + ", ".join(missing_ids[:12])})
    missing_deps = sorted(local_deps(source_raw) - local_deps(target_raw))
    if missing_deps:
        out.append({"code": "structure-deps", "detail": "missing source dependencies: " + ", ".join(missing_deps)})
    if tag_skeleton(source_raw) != tag_skeleton(target_raw):
        out.append({"code": "structure-tags", "detail": "HTML tag order differs from the canonical source"})
    if script_shapes(source_raw) != script_shapes(target_raw):
        out.append({"code": "script-structure", "detail": "executable JavaScript structure differs from the canonical source"})
    if skill and skill_meta(source_raw) != skill_meta(target_raw):
        out.append({"code": "skill-meta-drift", "detail": "localized skill-meta differs from canonical JSON"})
    return out


def scan(root: Path, locale: str) -> tuple[list[dict[str, str]], dict]:
    _, locale_root, _, profile, state = locale_paths(root, locale)
    overlay_root = locale_root / "web"
    declared = {Path(item).as_posix() for item in state.get("overlay_files", [])}
    actual = {path.relative_to(locale_root).as_posix() for path in overlay_root.rglob("*") if path.is_file()}
    findings: list[dict[str, str]] = interface_findings(root) if (root / "web/nemoclaw/localization.html").exists() else []
    for path in sorted(actual - declared):
        findings.append({"code": "overlay-extra", "path": path,
                         "detail": "not declared as localized prose; code/assets and fallback pages belong to canonical web/"})
    for path in sorted(declared - actual):
        findings.append({"code": "overlay-missing", "path": path, "detail": "declared overlay file is missing"})
    for path in sorted(declared):
        if not path.startswith("web/") or not path.endswith(".html") or not (root / path).is_file():
            findings.append({"code": "overlay-boundary", "path": path,
                             "detail": "locale overlays may contain only HTML files with a canonical web/ source"})

    reviews = state.get("reviews", {})
    for path in sorted(set(reviews) - declared):
        findings.append({"code": "review-orphan", "path": path,
                         "detail": "review entry is not present in overlay_files"})
    rows: list[dict[str, object]] = []
    for source in canonical_pages(root):
        rel = source.relative_to(root).as_posix()
        target = locale_root / rel
        source_raw = source.read_text(encoding="utf-8")
        source_digest = sha(source_raw)
        target_raw = target.read_text(encoding="utf-8") if target.is_file() else ""
        review = reviews.get(rel) or {}
        reviewed_digest = review.get("source_sha256")
        quality = page_quality(source_raw, target_raw, profile, skill=source.name == "SKILL.html") if target_raw else []
        if not target_raw:
            status = "missing"
        elif not reviewed_digest:
            status = "needs-review"
        elif reviewed_digest != source_digest:
            status = "stale"
        elif quality:
            status = "blocked"
        else:
            status = "current"
        if reviewed_digest and reviewed_digest != source_digest:
            findings.append({"code": "stale-source", "path": rel,
                             "detail": f"reviewed {reviewed_digest[:12]}, source is {source_digest[:12]}"})
        if reviewed_digest:
            findings.extend({"code": item["code"], "path": rel, "detail": item["detail"]} for item in quality)
        rows.append({
            "path": rel,
            "file": source.name,
            "source_sha256": source_digest,
            "reviewed_source_sha256": reviewed_digest,
            "target_sha256": sha(target_raw) if target_raw else None,
            "status": status,
            "quality": quality,
        })

    for rel in sorted(path for path in declared if path.endswith("SKILL.html")):
        source = root / rel
        target = locale_root / rel
        if source.is_file() and target.is_file() and skill_meta(source.read_text(encoding="utf-8")) != skill_meta(target.read_text(encoding="utf-8")):
            findings.append({"code": "skill-meta-drift", "path": rel,
                             "detail": "localized skill-meta differs from canonical JSON"})

    available = sorted(row["file"] for row in rows
                       if row["path"].startswith("web/nemoclaw/") and row["status"] == "current")
    manifest = {
        "schema": "nemoclaw-localization-drift/1",
        "locale": profile["locale"],
        "url_code": profile["url_code"],
        "label": profile["label"],
        "native_label": profile["native_label"],
        "available_pages": available,
        "counts": {name: sum(1 for row in rows if row["status"] == name)
                   for name in ("current", "stale", "blocked", "needs-review", "missing")},
        "pages": rows,
        "terminology_sources": profile.get("terminology_sources", []),
    }
    return findings, manifest


def write_manifest(root: Path, profile: dict, manifest: dict) -> Path:
    path = root / "web" / "nemoclaw" / "assets" / f"localization-{profile['url_code']}.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def accept(root: Path, locale: str, paths: list[str]) -> list[str]:
    _, locale_root, state_path, profile, state = locale_paths(root, locale)
    errors: list[str] = []
    reviews = state.setdefault("reviews", {})
    for rel in paths:
        source, target = root / rel, locale_root / rel
        if not source.is_file() or not target.is_file():
            errors.append(f"{rel}: source or localized target missing")
            continue
        quality = page_quality(source.read_text(encoding="utf-8"), target.read_text(encoding="utf-8"), profile,
                               skill=source.name == "SKILL.html")
        if quality:
            errors.append(f"{rel}: " + "; ".join(item["detail"] for item in quality))
            continue
        reviews[rel] = {"source_sha256": sha(source.read_text(encoding="utf-8")),
                        "reviewed_on": date.today().isoformat()}
    if not errors:
        state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return errors


def self_test() -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="localization-audit-") as td:
        root = Path(td)
        profile_dir = root / "scripts/translate/locales/pt-BR"
        target_dir = root / "i18n/pt/web/nemoclaw"
        source_dir = root / "web/nemoclaw"
        profile_dir.mkdir(parents=True)
        target_dir.mkdir(parents=True)
        source_dir.mkdir(parents=True)
        profile = {"locale": "pt-BR", "url_code": "pt", "label": "Portuguese", "native_label": "Português",
                   "html_lang": "pt-BR", "english_sentence_markers": ["Course home"],
                   "english_ui_markers": ["Run the node"],
                   "unfit_phrases": {"soquete de raciocínio": "use etapa de decisão"}}
        (profile_dir / "profile.json").write_text(json.dumps(profile))
        source_raw = '<!doctype html><html lang="en"><body><main id="lesson">Course home</main><script>const x=1; helpers.log("Run the node");</script></body></html>'
        target_raw = '<!doctype html><html lang="pt-BR"><body><main id="lesson">Início do curso</main><script>const x=1; helpers.log("Execute o nó");</script></body></html>'
        (source_dir / "index.html").write_text(source_raw)
        (target_dir / "index.html").write_text(target_raw)
        (root / "i18n/pt/locale.json").write_text('{}')
        state = {"overlay_files": ["web/nemoclaw/index.html"],
                 "reviews": {"web/nemoclaw/index.html": {"source_sha256": sha(source_raw)}}}
        (root / "i18n/pt/localization_state.json").write_text(json.dumps(state))
        base, _ = scan(root, "pt-BR")
        if base:
            failures.append(f"clean fixture rejected: {base}")
        cases = (
            ("html-lang", lambda: (target_dir / "index.html").write_text(target_raw.replace('lang="pt-BR"', 'lang="en"'))),
            ("untranslated-english", lambda: (target_dir / "index.html").write_text(target_raw.replace("Início do curso", "Course home"))),
            ("untranslated-ui", lambda: (target_dir / "index.html").write_text(target_raw.replace("Execute o nó", "Run the node"))),
            ("structure-tags", lambda: (target_dir / "index.html").write_text(target_raw.replace("</main>", "</section>"))),
            ("script-structure", lambda: (target_dir / "index.html").write_text(target_raw.replace("const x=1", "const x=2"))),
            ("stale-source", lambda: (source_dir / "index.html").write_text(source_raw.replace("Course home", "Course home changed"))),
            ("overlay-extra", lambda: (target_dir / "extra.js").write_text("x")),
        )
        for expected, mutate in cases:
            shutil.rmtree(target_dir)
            target_dir.mkdir(parents=True)
            (target_dir / "index.html").write_text(target_raw)
            (source_dir / "index.html").write_text(source_raw)
            mutate()
            codes = {item["code"] for item in scan(root, "pt-BR")[0]}
            if expected not in codes:
                failures.append(f"mutation escaped detector: {expected}")
    with tempfile.TemporaryDirectory(prefix="localization-interface-") as td:
        fixture = Path(td)
        for rel in INTERFACE_CONTRACT:
            src, dst = ROOT / rel, fixture / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        if interface_findings(fixture):
            failures.append("clean localization interface fixture rejected")
        for rel, token in (("web/nemoclaw/scripts/_locale.js", "available_pages"),
                           ("web/nemoclaw/localization.html", 'id="loc-target"'),
                           ("scripts/build/build_pages.sh", "assemble_locale_overlay.py")):
            path = fixture / rel
            raw = path.read_text(encoding="utf-8")
            path.write_text(raw.replace(token, "removed-contract-token"), encoding="utf-8")
            if "interface-contract" not in {item["code"] for item in interface_findings(fixture)}:
                failures.append(f"interface mutation escaped detector: {rel}: {token}")
            path.write_text(raw, encoding="utf-8")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--locale", default="pt-BR")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--accept", action="append", default=[], metavar="REPO_PATH")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--report")
    args = parser.parse_args()
    if args.self_test:
        failures = self_test()
        if failures:
            print("localization audit self-test: FAIL")
            for item in failures:
                print(f"  - {item}")
            return 1
        print("localization audit self-test: OK")
        return 0
    if args.accept:
        errors = accept(ROOT, args.locale, args.accept)
        if errors:
            print("localization accept: REFUSED")
            for item in errors:
                print(f"  - {item}")
            return 1
    _, _, _, profile, _ = locale_paths(ROOT, args.locale)
    findings, manifest = scan(ROOT, args.locale)
    if not args.no_write:
        path = write_manifest(ROOT, profile, manifest)
        print(f"localization manifest: {path.relative_to(ROOT)}")
    result = {"ok": not findings, "findings": findings, "manifest": manifest}
    if args.report:
        Path(args.report).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if findings:
        print(f"localization audit: FAIL ({len(findings)})")
        for item in findings:
            print(f"  [{item['code']}] {item['path']}: {item['detail']}")
        return 1
    print(f"localization audit: OK ({manifest['counts']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
