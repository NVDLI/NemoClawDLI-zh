#!/usr/bin/env python3
"""Validate sparse same-branch localizations and emit the Studio drift manifest."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import html
import json
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

for _p in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
    if (_p / "scripts" / "_bootstrap.py").exists():
        sys.path.insert(0, str(_p / "scripts"))
        break
from _bootstrap import find_repo_root
from translate.locale_projection import project_locale_html
from translate.localization_scope import translation_canonical, translation_sha
from translate.translate_html_segments import extract_segments, protected_tokens
from translate.translate_svg_text import extract_svg_segments

ROOT = find_repo_root(Path(__file__).resolve())
SKIP_TEXT = {"script", "style", "pre", "code", "svg", "noscript"}
INTERFACE_CONTRACT = {
    "web/nemoclaw/localization.html": ("id=\"loc-kinds\"", "data-kind=\"assets\"", "id=\"loc-filters\"", "id=\"loc-source\"", "id=\"loc-target\"", "scripts/localization_main.js"),
    "web/nemoclaw/scripts/localization_main.js": ("localization-", '"current", "stale", "blocked", "needs-review", "missing"', "reviewed_source_sha256", "asset_counts", 'activeKind === "assets"', "loc-locale"),
    "web/nemoclaw/scripts/_locale.js": ("mountLanguageMenu", "available_pages", 'aria-haspopup', "languageFallback", "language-fallback-badge"),
    "web/nemoclaw/scripts/_shared.js": ("mountLanguageMenu()",),
    "web/nemoclaw/studio.html": ('href="localization.html"',),
    "scripts/build/build_language_manifest.py": ("native_label", "available_pages", "localization-"),
    "scripts/build/build_pages.sh": ("assemble_locale_overlay.py",),
    "scripts/build/assemble_locale_overlay.py": ("source_sha256", "translation_sha256", "self-test", "stale translation did not fall back"),
    "scripts/translate/translate_svg_text.py": ("extract_svg_segments", "data-locale", "--no-api", "svg_translations.json"),
    "scripts/translate/locales/pt-BR/svg_translations.json": ("Ambiente", "ETAPA DE DECISÃO", "Agentes com aprendizado"),
    "scripts/translate/locales/es-ES/profile.json": ("es-ES", "agentes de IA", "generación aumentada por recuperación"),
    "scripts/translate/localization_scope.py": ("en-shell", "data-localization-scope", "translation_sha"),
    "scripts/translate/locale_projection.py": ("project_locale_html", "missing localized shell segment"),
    "scripts/validation/localization_runtime_audit.py": ("pageerror", "language-menu entries are clipped", "Localization Studio"),
    ".gitlab-ci.yml": ("assemble_locale_overlay.py --self-test", "localization_audit.py --self-test", "for locale in scripts/translate/locales/*"),
    "scripts/translate/SKILL.html": ("locales/pt-BR/SKILL.html", "locales/es-ES/SKILL.html", "same-branch localization", "translate_svg_text.py"),
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


def code_templates(raw: str) -> list[str]:
    """Return runnable cell bodies; localization may change chrome, never executable examples."""
    return re.findall(r'\bcode\s*:\s*(?:(?:[A-Za-z_$][\w$]*(?:\.[\w$]+)*)\s*\+\s*)*`((?:\\.|[^`])*)`', raw, re.S)


def scripted_ui_text(raw: str) -> str:
    """Extract common learner-facing object fields without treating model prompts as UI prose."""
    raw = re.sub(r'(\bcode\s*:\s*(?:(?:[A-Za-z_$][\w$]*(?:\.[\w$]+)*)\s*\+\s*)*`)((?:\\.|[^`])*)(`)', r'\1\3', raw, flags=re.S)
    values = []
    pattern = r'\b(?:label|intro|title|summary|greeting|disabledMsg|kicker|socket)\s*:\s*(["\'])(.*?)(?<!\\)\1'
    for match in re.finditer(pattern, raw, re.S):
        values.append(match.group(2).replace("\\n", " "))
    call_pattern = r'\b(?:helpers\.log|log(?:\.h|\.details|\.html)?|info|show)\s*\((.*?)\)\s*;'
    for call in re.finditer(call_pattern, raw, re.S):
        values.extend(match.group(2).replace("\\n", " ") for match in re.finditer(r'(["\'])(.*?)(?<!\\)\1', call.group(1), re.S))
    for array in re.finditer(r'\blines\s*:\s*\[(.*?)\]', raw, re.S):
        values.extend(match.group(2) for match in re.finditer(r'(["\'])(.*?)(?<!\\)\1', array.group(1), re.S))
    values.extend(match.group(1) for match in re.finditer(r'\b(?:url|token|cfJwt)\s*:\s*`(.*?)`', raw, re.S))
    for field in re.finditer(r'\b(?:greeting|disabledMsg)\s*:\s*([^\n]+)', raw):
        if "?" in field.group(1):
            values.extend(match.group(2) for match in re.finditer(r'(["\'])(.*?)(?<!\\)\1', field.group(1)))
    return re.sub(r"\s+", " ", " ".join(values)).strip()


def citation_titles(raw: str) -> list[tuple[str, str]]:
    """Return cited titles that remain canonical across language overlays."""
    out = []
    anchor = re.compile(r'<a\b[^>]*\bhref=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
    for href, body in anchor.findall(raw):
        title = re.search(r"<em>(.*?)</em>", body, re.I | re.S)
        if title:
            out.append((href, re.sub(r"\s+", " ", title.group(1)).strip()))
    return out


def reference_citation_titles(raw: str) -> list[tuple[str, str]]:
    """Return academic titles from the module-organized references hub.

    Localized prose may translate descriptions and link labels, but published paper and
    book titles remain canonical. Academic entries in this hub begin with an author and year.
    """
    start = raw.find('id="refs"')
    if start < 0:
        return []
    end = raw.find('id="learning-path"', start)
    body = raw[start:end if end >= 0 else len(raw)]
    out: list[tuple[str, str]] = []
    anchor = re.compile(r'<a\b[^>]*\bhref=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
    for item in re.findall(r"<li\b[^>]*>(.*?)</li>", body, re.I | re.S):
        first = anchor.search(item)
        if not first:
            continue
        prefix = item[:first.start()]
        if not re.search(r"\(\d{4}\)\.", prefix) or "<em" in prefix.lower():
            continue
        title = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", first.group(2))).strip())
        if title:
            out.append((first.group(1), title))
    return out


def html_lang(raw: str) -> str:
    match = re.search(r"<html\b[^>]*\blang=[\"']([^\"']+)", raw, re.I)
    return match.group(1) if match else ""


def segment_contract_tokens(raw: str) -> list[str]:
    """Return tokens that must stay in the same learner-facing segment."""
    protected = [token for token in protected_tokens(raw)
                 if token.lower().startswith(("<code", "<kbd", "http", "${", "{{", "nvapi-"))]
    urls = re.findall(r"https?://[^\s<\"']+", raw, re.I)
    visible = re.sub(r"<[^>]+>", " ", raw)
    routes = re.findall(r"(?<!\w)/(?:[A-Za-z0-9_.{}:<>-]+/?)+", visible)
    return sorted(Counter(protected + urls + routes).elements())


def rhythm_quality(text: str, profile: dict) -> list[dict[str, str]]:
    rules = profile.get("rhythm_rules", {})
    if not rules:
        return []
    sentences = [re.sub(r"\s+", " ", item).strip(" \n\t•")
                 for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()]
    out: list[dict[str, str]] = []
    limit = int(rules.get("max_sentence_words", 0))
    for sentence in sentences:
        words = re.findall(r"\b[\wÁÉÍÓÚÜÑáéíóúüñ]+\b", sentence)
        if limit and len(words) > limit:
            out.append({"code": "locale-long-sentence", "detail": f"sentence has {len(words)} words; limit is {limit}"})
            break
    opening_limit = int(rules.get("repeated_opening_run", 0))
    openings = [" ".join(re.findall(r"\b[\wÁÉÍÓÚÜÑáéíóúüñ]+\b", item.lower())[:2]) for item in sentences]
    for index in range(max(0, len(openings) - opening_limit + 1)):
        run = openings[index:index + opening_limit]
        if opening_limit and len(run) == opening_limit and len(set(run)) == 1 and run[0]:
            out.append({"code": "locale-repeated-opening", "detail": f"{opening_limit} consecutive sentences start with {run[0]!r}"})
            break
    short_run = int(rules.get("short_sentence_run", 0))
    short_words = int(rules.get("short_sentence_words", 0))
    lengths = [len(re.findall(r"\b[\wÁÉÍÓÚÜÑáéíóúüñ]+\b", item)) for item in sentences]
    for index in range(max(0, len(lengths) - short_run + 1)):
        run = lengths[index:index + short_run]
        if short_run and len(run) == short_run and all(length <= short_words for length in run):
            out.append({"code": "locale-choppy-run", "detail": f"{short_run} consecutive sentences have at most {short_words} words"})
            break
    return out


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


def svg_geometry(raw: str) -> list[tuple[str, tuple[tuple[str, str], ...]]]:
    """Represent non-language SVG structure; text coordinates may change to repair wrapping."""
    root = ET.fromstring(raw)
    out = []
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag in {"text", "tspan", "title", "desc"}:
            out.append((tag, ()))
            continue
        attrs = tuple(sorted((key.rsplit("}", 1)[-1], value) for key, value in element.attrib.items()
                             if key not in {"aria-label", "data-locale"}))
        out.append((tag, attrs))
    return out


def svg_visible_text(raw: str) -> str:
    root = ET.fromstring(raw)
    values = [root.attrib.get("aria-label", "")]
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] in {"text", "tspan", "title", "desc"} and element.text:
            values.append(element.text)
    return re.sub(r"\s+", " ", " ".join(values)).strip()


def svg_prose_text(raw: str) -> str:
    """Return descriptive SVG prose; terse diagram labels are not sentences."""
    root = ET.fromstring(raw)
    values = [root.attrib.get("aria-label", "")]
    values.extend(element.text for element in root.iter()
                  if element.tag.rsplit("}", 1)[-1] in {"title", "desc"} and element.text)
    return re.sub(r"\s+", " ", " ".join(values)).strip()


def svg_quality(source_raw: str, target_raw: str, profile: dict) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    try:
        source_geometry = svg_geometry(source_raw)
        target_geometry = svg_geometry(target_raw)
        source_root = ET.fromstring(source_raw)
        target_root = ET.fromstring(target_raw)
    except ET.ParseError as exc:
        return [{"code": "svg-xml", "detail": f"invalid localized SVG: {exc}"}]
    expected_locale = profile["locale"]
    if f'data-locale="{expected_locale}"' not in target_raw:
        out.append({"code": "svg-locale", "detail": f"localized SVG needs data-locale={expected_locale}"})
    if source_geometry != target_geometry:
        out.append({"code": "svg-geometry", "detail": "localized SVG changed non-text geometry or element order"})
    for source_el, target_el in zip(source_root.iter(), target_root.iter()):
        if source_el.tag.rsplit("}", 1)[-1] != "tspan":
            continue
        source_text = "".join(source_el.itertext()).strip()
        target_text = "".join(target_el.itertext()).strip()
        if source_text != target_text and len(target_el.attrib.get("x", "").split()) > 1:
            out.append({"code": "svg-glyph-positions",
                        "detail": f"translated tspan {target_text!r} retains source per-glyph x positions"})
            break
    if re.search(r"<script\b|\bon\w+\s*=", target_raw, re.I):
        out.append({"code": "svg-script", "detail": "localized SVG may not add executable content"})
    visible = svg_visible_text(target_raw)
    source_segments = [item.text for item in extract_svg_segments(source_raw)]
    target_segments = [item.text for item in extract_svg_segments(target_raw)]
    translations = profile.get("_svg_translations", {})
    if len(source_segments) != len(target_segments):
        out.append({"code": "svg-text-shape", "detail": "localized SVG changed the number of translatable text nodes"})
    else:
        for source_text, target_text in zip(source_segments, target_segments):
            if source_text not in translations:
                out.append({"code": "svg-translation-map", "detail": f"missing reviewed SVG mapping for {source_text!r}"})
                break
            if translations[source_text] != target_text:
                out.append({"code": "svg-translation-drift", "detail": f"localized SVG text differs from reviewed mapping for {source_text!r}"})
                break
    for phrase, fix in profile.get("unfit_phrases", {}).items():
        if re.search(rf"(?i)\b{re.escape(phrase)}\b", visible):
            out.append({"code": "unfit-locale", "detail": f"{phrase!r}: {fix}"})
    out.extend(rhythm_quality(svg_prose_text(target_raw), profile))
    return out


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
    if 'data-localization-scope="en-shell"' in source_raw:
        try:
            target_raw = project_locale_html(source_raw, target_raw, profile.get("_shell_translations", {}))
        except ValueError as exc:
            return [{"code": "locale-projection", "detail": str(exc)}]
    expected_lang = profile["html_lang"]
    if html_lang(target_raw) != expected_lang:
        out.append({"code": "html-lang", "detail": f"expected <html lang=\"{expected_lang}\">"})
    source_segments = extract_segments(source_raw)
    target_segments = extract_segments(target_raw)
    if (len(source_segments) != len(target_segments)
            or [item.kind for item in source_segments] != [item.kind for item in target_segments]):
        out.append({"code": "content-segments",
                    "detail": f"learner-facing segment parity differs: source {len(source_segments)}, target {len(target_segments)}"})
    else:
        for index, (source_segment, target_segment) in enumerate(zip(source_segments, target_segments)):
            if segment_contract_tokens(source_segment.text) != segment_contract_tokens(target_segment.text):
                out.append({"code": "segment-token-drift",
                            "detail": f"segment {index} moved or changed a protected URL, path, placeholder, or code token"})
                break
            source_words = len(re.findall(r"\b\w+\b", re.sub(r"<[^>]+>", " ", source_segment.text)))
            target_words = len(re.findall(r"\b\w+\b", re.sub(r"<[^>]+>", " ", target_segment.text)))
            if source_segment.kind == "block" and source_words >= 12 and target_words / source_words < 0.35:
                out.append({"code": "content-shortfall",
                            "detail": f"segment {index} retained only {target_words}/{source_words} words"})
                break
    ui_text = scripted_ui_text(target_raw)
    visible = reader_text(target_raw) + " " + ui_text
    for _, title in citation_titles(target_raw):
        visible = visible.replace(html.unescape(re.sub(r"<[^>]+>", "", title)), "")
    source_reference_titles = set(reference_citation_titles(source_raw))
    target_reference_titles = set(reference_citation_titles(target_raw))
    for _, title in source_reference_titles & target_reference_titles:
        visible = visible.replace(title, "")
    for title in profile.get("canonical_english_titles", []):
        visible = visible.replace(title, "")
    for marker in profile.get("english_sentence_markers", []):
        if marker in visible:
            out.append({"code": "untranslated-english", "detail": f"reader text still contains {marker!r}"})
    for marker in profile.get("english_ui_markers", []):
        if marker.lower() in ui_text.lower():
            out.append({"code": "untranslated-ui", "detail": f"scripted learner UI still contains {marker!r}"})
    for phrase, fix in profile.get("unfit_phrases", {}).items():
        if re.search(rf"(?i)\b{re.escape(phrase)}\b", visible):
            out.append({"code": "unfit-locale", "detail": f"{phrase!r}: {fix}"})
    if (citation_titles(source_raw) != citation_titles(target_raw)
            or reference_citation_titles(source_raw) != reference_citation_titles(target_raw)):
        out.append({"code": "citation-title", "detail": "cited paper/book titles must remain canonical"})
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
    if profile.get("canonical_code_templates") and code_templates(source_raw) != code_templates(target_raw):
        out.append({"code": "code-cell-drift", "detail": "localized runnable code differs from the canonical source"})
    if skill and skill_meta(source_raw) != skill_meta(target_raw):
        out.append({"code": "skill-meta-drift", "detail": "localized skill-meta differs from canonical JSON"})
    return out


def scan(root: Path, locale: str) -> tuple[list[dict[str, str]], dict]:
    _, locale_root, _, profile, state = locale_paths(root, locale)
    svg_map = root / "scripts" / "translate" / "locales" / locale / "svg_translations.json"
    profile["_svg_translations"] = json.loads(svg_map.read_text(encoding="utf-8")) if svg_map.is_file() else {}
    shell_map = root / "scripts" / "translate" / "locales" / locale / "shell_translations.json"
    profile["_shell_translations"] = json.loads(shell_map.read_text(encoding="utf-8")) if shell_map.is_file() else {}
    overlay_root = locale_root / "web"
    declared = {Path(item).as_posix() for item in state.get("overlay_files", [])}
    declared_assets = {Path(item).as_posix() for item in state.get("asset_files", [])}
    declared_all = declared | declared_assets
    actual = {path.relative_to(locale_root).as_posix() for path in overlay_root.rglob("*") if path.is_file()}
    findings: list[dict[str, str]] = interface_findings(root) if (root / "web/nemoclaw/localization.html").exists() else []
    for path in sorted(actual - declared_all):
        findings.append({"code": "overlay-extra", "path": path,
                         "detail": "not declared as localized prose; code/assets and fallback pages belong to canonical web/"})
    for path in sorted(declared_all - actual):
        findings.append({"code": "overlay-missing", "path": path, "detail": "declared overlay file is missing"})
    for path in sorted(declared):
        if not path.startswith("web/") or not path.endswith(".html") or not (root / path).is_file():
            findings.append({"code": "overlay-boundary", "path": path,
                             "detail": "locale overlays may contain only HTML files with a canonical web/ source"})
    for path in sorted(declared_assets):
        if not path.startswith("web/nemoclaw/assets/figures/") or not path.endswith(".svg") or not (root / path).is_file():
            findings.append({"code": "overlay-asset-boundary", "path": path,
                             "detail": "localized assets may contain only reviewed course figure SVGs"})

    reviews = state.get("reviews", {})
    asset_reviews = state.get("asset_reviews", {})
    for path in sorted(set(reviews) - declared):
        findings.append({"code": "review-orphan", "path": path,
                         "detail": "review entry is not present in overlay_files"})
    for path in sorted(set(asset_reviews) - declared_assets):
        findings.append({"code": "asset-review-orphan", "path": path,
                         "detail": "asset review entry is not present in asset_files"})
    rows: list[dict[str, object]] = []
    for source in canonical_pages(root):
        rel = source.relative_to(root).as_posix()
        target = locale_root / rel
        source_raw = source.read_text(encoding="utf-8")
        scoped = 'data-localization-scope="en-shell"' in source_raw
        source_digest = translation_sha(source_raw) if scoped else sha(source_raw)
        target_raw = target.read_text(encoding="utf-8") if target.is_file() else ""
        review = reviews.get(rel) or {}
        reviewed_digest = review.get("translation_sha256") if scoped else review.get("source_sha256")
        target_digest = sha(target_raw) if target_raw else None
        reviewed_target = review.get("target_sha256")
        require_target_review = bool(profile.get("reviewed_target_hashes"))
        quality = page_quality(source_raw, target_raw, profile, skill=source.name == "SKILL.html") if target_raw else []
        if not target_raw:
            status = "missing"
        elif not reviewed_digest or (require_target_review and not reviewed_target):
            status = "needs-review"
        elif reviewed_digest != source_digest:
            status = "stale"
        elif require_target_review and reviewed_target != target_digest:
            status = "needs-review"
        elif quality:
            status = "blocked"
        else:
            status = "current"
        if reviewed_digest and reviewed_digest != source_digest:
            findings.append({"code": "stale-source", "path": rel,
                             "detail": f"reviewed {reviewed_digest[:12]}, source is {source_digest[:12]}"})
        if require_target_review and reviewed_target and reviewed_target != target_digest:
            findings.append({"code": "target-drift", "path": rel,
                             "detail": f"reviewed target {reviewed_target[:12]}, target is {(target_digest or 'missing')[:12]}"})
        elif require_target_review and target_raw and not reviewed_target:
            findings.append({"code": "target-unreviewed", "path": rel,
                             "detail": "locale requires an accepted target hash"})
        if reviewed_digest:
            findings.extend({"code": item["code"], "path": rel, "detail": item["detail"]} for item in quality)
        rows.append({
            "path": rel,
            "file": source.name,
            "source_sha256": source_digest,
            "reviewed_source_sha256": reviewed_digest,
            "target_sha256": target_digest,
            "reviewed_target_sha256": reviewed_target,
            "status": status,
            "quality": quality,
        })

    for rel in sorted(path for path in declared if path.endswith("SKILL.html")):
        source = root / rel
        target = locale_root / rel
        if source.is_file() and target.is_file() and skill_meta(source.read_text(encoding="utf-8")) != skill_meta(target.read_text(encoding="utf-8")):
            findings.append({"code": "skill-meta-drift", "path": rel,
                             "detail": "localized skill-meta differs from canonical JSON"})

    asset_rows = []
    for rel in sorted(declared_assets):
        source, target = root / rel, locale_root / rel
        source_raw = source.read_text(encoding="utf-8") if source.is_file() else ""
        target_raw = target.read_text(encoding="utf-8") if target.is_file() else ""
        review = asset_reviews.get(rel) or {}
        source_digest = sha(source_raw) if source_raw else None
        target_digest = sha(target_raw) if target_raw else None
        reviewed_target = review.get("target_sha256")
        require_target_review = bool(profile.get("reviewed_target_hashes"))
        quality = svg_quality(source_raw, target_raw, profile) if source_raw and target_raw else []
        if not target_raw:
            status = "missing"
        elif not review.get("source_sha256") or (require_target_review and not reviewed_target):
            status = "needs-review"
        elif review.get("source_sha256") != source_digest:
            status = "stale"
        elif require_target_review and reviewed_target != target_digest:
            status = "needs-review"
        elif quality:
            status = "blocked"
        else:
            status = "current"
        if review.get("source_sha256") and review.get("source_sha256") != source_digest:
            findings.append({"code": "stale-asset-source", "path": rel,
                             "detail": f"reviewed {review['source_sha256'][:12]}, source is {source_digest[:12]}"})
        if require_target_review and reviewed_target and reviewed_target != target_digest:
            findings.append({"code": "target-asset-drift", "path": rel,
                             "detail": f"reviewed target {reviewed_target[:12]}, target is {(target_digest or 'missing')[:12]}"})
        elif require_target_review and target_raw and not reviewed_target:
            findings.append({"code": "target-asset-unreviewed", "path": rel,
                             "detail": "locale requires an accepted target hash"})
        if review.get("source_sha256"):
            findings.extend({"code": item["code"], "path": rel, "detail": item["detail"]} for item in quality)
        asset_rows.append({"path": rel, "file": Path(rel).name, "source_sha256": source_digest,
                           "reviewed_source_sha256": review.get("source_sha256"),
                           "target_sha256": target_digest,
                           "reviewed_target_sha256": reviewed_target,
                           "status": status, "quality": quality})

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
        "assets": asset_rows,
        "asset_counts": {name: sum(1 for row in asset_rows if row["status"] == name)
                         for name in ("current", "stale", "blocked", "needs-review", "missing")},
        "terminology_sources": profile.get("terminology_sources", []),
    }
    return findings, manifest


def write_manifest(root: Path, profile: dict, manifest: dict) -> Path:
    path = root / "web" / "nemoclaw" / "assets" / f"localization-{profile['url_code']}.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def accept(root: Path, locale: str, paths: list[str]) -> list[str]:
    _, locale_root, state_path, profile, state = locale_paths(root, locale)
    svg_map = root / "scripts" / "translate" / "locales" / locale / "svg_translations.json"
    profile["_svg_translations"] = json.loads(svg_map.read_text(encoding="utf-8")) if svg_map.is_file() else {}
    shell_map = root / "scripts" / "translate" / "locales" / locale / "shell_translations.json"
    profile["_shell_translations"] = json.loads(shell_map.read_text(encoding="utf-8")) if shell_map.is_file() else {}
    errors: list[str] = []
    reviews = state.setdefault("reviews", {})
    asset_reviews = state.setdefault("asset_reviews", {})
    for rel in paths:
        source, target = root / rel, locale_root / rel
        if not source.is_file() or not target.is_file():
            errors.append(f"{rel}: source or localized target missing")
            continue
        source_raw = source.read_text(encoding="utf-8")
        target_raw = target.read_text(encoding="utf-8")
        quality = (svg_quality(source_raw, target_raw, profile) if source.suffix == ".svg" else
                   page_quality(source_raw, target_raw, profile, skill=source.name == "SKILL.html"))
        if quality:
            errors.append(f"{rel}: " + "; ".join(item["detail"] for item in quality))
            continue
        raw = source_raw
        if source.suffix == ".svg":
            asset_reviews[rel] = {"source_sha256": sha(raw), "target_sha256": sha(target_raw),
                                  "reviewed_on": date.today().isoformat()}
            continue
        if 'data-localization-scope="en-shell"' in raw:
            reviews[rel] = {"source_sha256": sha(raw), "translation_sha256": translation_sha(raw),
                            "target_sha256": sha(target_raw),
                            "reviewed_on": date.today().isoformat()}
        else:
            reviews[rel] = {"source_sha256": sha(raw), "target_sha256": sha(target_raw),
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
        profile["_svg_translations"] = {"Agent loop": "Ciclo do agente"}
        (profile_dir / "profile.json").write_text(json.dumps(profile))
        (profile_dir / "svg_translations.json").write_text(json.dumps(profile["_svg_translations"]))
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
        profile["reviewed_target_hashes"] = True
        (profile_dir / "profile.json").write_text(json.dumps(profile))
        state["reviews"]["web/nemoclaw/index.html"]["target_sha256"] = sha(target_raw)
        (root / "i18n/pt/localization_state.json").write_text(json.dumps(state))
        (target_dir / "index.html").write_text(target_raw.replace("Início do curso", "Curso inicial"))
        target_changed, _ = scan(root, "pt-BR")
        if not any(item["code"] == "target-drift" for item in target_changed):
            failures.append("post-review localized prose mutation escaped target hash")
        (target_dir / "index.html").write_text(target_raw)
        cited_source = '<html lang="en"><a href="paper"><em>Canonical Paper Title</em></a></html>'
        cited_target = '<html lang="pt-BR"><a href="paper"><em>Título traduzido</em></a></html>'
        if "citation-title" not in {item["code"] for item in page_quality(cited_source, cited_target, profile)}:
            failures.append("translated citation title escaped detector")
        reference_source = ('<html lang="en"><div class="section" id="refs"><ul><li>Doe et al. (2025). '
                            '<a href="paper">The Canonical Paper Title.</a></li></ul></div>'
                            '<div id="learning-path">What comes next</div></html>')
        reference_target = ('<html lang="pt-BR"><div class="section" id="refs"><ul><li>Doe et al. (2025). '
                            '<a href="paper">The Canonical Paper Title.</a></li></ul></div>'
                            '<div id="learning-path">Próximos pasos</div></html>')
        reference_profile = {**profile, "english_sentence_markers": ["The ", "What "]}
        if page_quality(reference_source, reference_target, reference_profile):
            failures.append("canonical English reference title was rejected as untranslated prose")
        translated_reference = reference_target.replace("The Canonical Paper Title.", "Título traducido.")
        if "citation-title" not in {item["code"] for item in page_quality(reference_source, translated_reference, reference_profile)}:
            failures.append("translated reference-hub paper title escaped detector")
        line_source = '<html lang="en"><script>const x={lines:["Run the node"]}</script></html>'
        line_target = '<html lang="pt-BR"><script>const x={lines:["Run the node"]}</script></html>'
        if "untranslated-ui" not in {item["code"] for item in page_quality(line_source, line_target, profile)}:
            failures.append("English diagram line escaped detector")
        code_profile = {**profile, "canonical_code_templates": True}
        code_source = '<html lang="en"><script>const x={code:`return 1;`}</script></html>'
        code_target = '<html lang="pt-BR"><script>const x={code:`return 2;`}</script></html>'
        if "code-cell-drift" not in {item["code"] for item in page_quality(code_source, code_target, code_profile)}:
            failures.append("localized runnable-code mutation escaped detector")
        concat_source = '<html lang="en"><script>const x={code: PREFIX + `return 1;`}</script></html>'
        concat_target = '<html lang="pt-BR"><script>const x={code: PREFIX + `return 2;`}</script></html>'
        if "code-cell-drift" not in {item["code"] for item in page_quality(concat_source, concat_target, code_profile)}:
            failures.append("concatenated runnable-code mutation escaped detector")
        missing_source = '<html lang="en"><p>Course home contains a complete explanatory paragraph for students.</p></html>'
        missing_target = '<html lang="pt-BR"><p></p></html>'
        if "content-segments" not in {item["code"] for item in page_quality(missing_source, missing_target, profile)}:
            failures.append("missing localized prose segment escaped detector")
        shifted_ui_source = ('<html lang="en"><script>const cells=['
                             '{label:"GET /healthz"},{label:"Describe workspace"}];</script></html>')
        shifted_ui_target = ('<html lang="pt-BR"><script>const cells=['
                             '{label:"Comprobar estado"},{label:"GET /healthz"}];</script></html>')
        if "segment-token-drift" not in {item["code"] for item in page_quality(shifted_ui_source, shifted_ui_target, profile)}:
            failures.append("learner UI path shifted between adjacent segments without detection")
        svg_rel = "web/nemoclaw/assets/figures/lesson.svg"
        svg_source = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 30" aria-label="Agent loop"><rect width="100" height="30"/><text x="5" y="20">Agent loop</text></svg>'
        svg_target = '<svg data-locale="pt-BR" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 30" aria-label="Ciclo do agente"><rect width="100" height="30"/><text x="5" y="20">Ciclo do agente</text></svg>'
        positioned_source = '<svg xmlns="http://www.w3.org/2000/svg"><text><tspan x="1 2 3">Run</tspan></text></svg>'
        positioned_target = '<svg data-locale="pt-BR" xmlns="http://www.w3.org/2000/svg"><text><tspan x="1 2 3">Executar</tspan></text></svg>'
        positioned_profile = {**profile, "_svg_translations": {"Run": "Executar"}}
        if "svg-glyph-positions" not in {item["code"] for item in svg_quality(positioned_source, positioned_target, positioned_profile)}:
            failures.append("translated text retaining source glyph positions escaped detector")
        terse_profile = {**positioned_profile, "rhythm_rules": {"short_sentence_run": 3, "short_sentence_words": 2}}
        terse_source = '<svg xmlns="http://www.w3.org/2000/svg" aria-label="Agent loop"><text>One.</text><text>Two.</text><text>Three.</text></svg>'
        terse_target = '<svg data-locale="pt-BR" xmlns="http://www.w3.org/2000/svg" aria-label="Ciclo do agente"><text>Um.</text><text>Dois.</text><text>Três.</text></svg>'
        terse_profile["_svg_translations"] = {"Agent loop": "Ciclo do agente", "One.": "Um.", "Two.": "Dois.", "Three.": "Três."}
        if "locale-choppy-run" in {item["code"] for item in svg_quality(terse_source, terse_target, terse_profile)}:
            failures.append("terse SVG labels were incorrectly treated as prose sentences")
        (root / svg_rel).parent.mkdir(parents=True)
        (root / svg_rel).write_text(svg_source)
        (root / "i18n/pt" / svg_rel).parent.mkdir(parents=True)
        (root / "i18n/pt" / svg_rel).write_text(svg_target)
        state["asset_files"] = [svg_rel]
        state["asset_reviews"] = {svg_rel: {"source_sha256": sha(svg_source), "target_sha256": sha(svg_target)}}
        (root / "i18n/pt/localization_state.json").write_text(json.dumps(state))
        svg_base, _ = scan(root, "pt-BR")
        if svg_base:
            failures.append(f"clean SVG fixture rejected: {svg_base}")
        (root / "i18n/pt" / svg_rel).write_text(svg_target.replace('<rect width="100"', '<rect width="90"'))
        svg_changed, _ = scan(root, "pt-BR")
        if not any(item["code"] == "svg-geometry" for item in svg_changed):
            failures.append("localized SVG geometry mutation was not rejected")
        (root / "i18n/pt" / svg_rel).write_text(svg_target.replace('data-locale="pt-BR" ', ""))
        svg_unmarked, _ = scan(root, "pt-BR")
        if not any(item["code"] == "svg-locale" for item in svg_unmarked):
            failures.append("unmarked localized SVG was not rejected")
        (root / "i18n/pt" / svg_rel).write_text(svg_target)
        scoped_raw = source_raw.replace(
            "Course home",
            '<details class="learning-block" data-localization-scope="en-shell"><summary data-localization-scope="en">Need detail?</summary><div class="learning-block-body">Course home</div></details>',
        )
        profile["_shell_translations"] = {"Need detail?": "Precisa de detalhes?"}
        if page_quality(scoped_raw, target_raw, profile):
            failures.append("English-only presentation shell changed locale structure checks")
        profile["_shell_translations"] = {}
        if "locale-projection" not in {item["code"] for item in page_quality(scoped_raw, target_raw, profile)}:
            failures.append("missing localized presentation shell escaped detector")
        profile["_shell_translations"] = {"Need detail?": "Precisa de detalhes?"}
        if (translation_sha(scoped_raw) != translation_sha(scoped_raw.replace("Need detail?", "Open detail?")) or
                translation_sha(scoped_raw) == translation_sha(scoped_raw.replace("Course home", "Changed lesson", 1))):
            failures.append("translation digest did not isolate controls from translatable body changes")
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
