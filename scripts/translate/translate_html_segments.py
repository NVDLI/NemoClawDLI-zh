#!/usr/bin/env python3
"""Translate learner-facing HTML segments without rewriting document/code structure.

The source page remains canonical. This tool translates text nodes, accessibility attributes,
and known learner-facing JavaScript string fields/calls, then writes a sparse locale overlay.
Model prompts, code bodies, identifiers, tags, and executable tokens remain untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from threading import Lock
from typing import Iterable

import requests

for _p in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
    if (_p / "scripts" / "_bootstrap.py").exists():
        sys.path.insert(0, str(_p / "scripts"))
        break
from _bootstrap import find_repo_root

ROOT = find_repo_root(Path(__file__).resolve())
TRANSLATION_REVISION = "pt-br-editorial-v3"
SKIP_TEXT = {"script", "style", "pre", "code", "svg", "noscript"}
ATTRS = {"alt", "aria-label", "placeholder", "title"}
BLOCK_TAGS = {"p", "li", "h1", "h2", "h3", "h4", "figcaption", "button", "option", "label", "summary", "td", "th", "a"}
BLOCK_DIV_CLASSES = {"callout", "step", "sys-desc", "num", "eyebrow"}
UI_FIELD_RE = re.compile(r'\b(?:label|intro|title|summary|greeting)\s*:\s*(["\'])(.*?)(?<!\\)\1', re.S)
UI_CALL_RE = re.compile(r'\b(?:helpers\.log|log(?:\.h|\.details|\.html)?|info|show)\s*\(\s*(["\'])(.*?)(?<!\\)\1', re.S)
SCRIPT_RE = re.compile(r'<script\b([^>]*)>(.*?)</script>', re.S | re.I)
PLACEHOLDER_RE = re.compile(r'(?:<code\b[^>]*>.*?</code>|<kbd\b[^>]*>.*?</kbd>|\\?\$\{[^}]+\}|\{\{[^}]+\}\}|https?://[^\s<"\']+|nvapi-|&[A-Za-z0-9#]+;|<[^>]+>)', re.S | re.I)


@dataclass(frozen=True)
class Segment:
    start: int
    end: int
    text: str
    kind: str


@dataclass
class UsageLedger:
    """Thread-safe, secret-free request and provider-usage accounting."""

    model: str
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    attempts: int = 0
    completed: int = 0
    failed: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    request_seconds: float = 0.0
    pages: dict[str, dict[str, int]] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def record(self, page: str, seconds: float, usage: dict | None, *, failed: bool) -> None:
        usage = usage or {}
        with self._lock:
            self.attempts += 1
            self.request_seconds += seconds
            self.failed += int(failed)
            self.completed += int(not failed)
            row = self.pages.setdefault(page, {"attempts": 0, "completed": 0, "failed": 0,
                                               "prompt_tokens": 0, "completion_tokens": 0,
                                               "total_tokens": 0})
            row["attempts"] += 1
            row["failed"] += int(failed)
            row["completed"] += int(not failed)
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                value = int(usage.get(key) or 0)
                setattr(self, key, getattr(self, key) + value)
                row[key] += value

    def report(self) -> dict:
        return {
            "schema": "nemoclaw-translation-usage/1",
            "model": self.model,
            "endpoint": "https://integrate.api.nvidia.com/v1/chat/completions",
            "started_at": self.started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "attempts": self.attempts,
            "completed": self.completed,
            "failed": self.failed,
            "provider_reported_usage": {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
            },
            "request_seconds": round(self.request_seconds, 3),
            "pages": self.pages,
        }


class SegmentParser(HTMLParser):
    def __init__(self, raw: str) -> None:
        super().__init__(convert_charrefs=False)
        self.raw = raw
        self.line_starts = [0]
        self.line_starts.extend(match.end() for match in re.finditer("\n", raw))
        self.skip_depth = 0
        self.segments: list[Segment] = []
        self.blocks: list[Segment] = []
        self.block_stack: list[tuple[str, int]] = []

    def absolute_offset(self) -> int:
        line, column = self.getpos()
        return self.line_starts[line - 1] + column

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        start = self.absolute_offset()
        token = self.get_starttag_text() or ""
        tag = tag.lower()
        classes = set()
        for key, value in attrs:
            if key.lower() == "class" and value:
                classes.update(value.split())
        selected = tag in BLOCK_TAGS or (tag == "div" and bool(classes & BLOCK_DIV_CLASSES))
        if not self.skip_depth and selected:
            self.block_stack.append((tag, start + len(token)))
        if not self.skip_depth:
            attr_pattern = re.compile(r'(?i)\b(alt|aria-label|placeholder|title)\s*=\s*(["\'])(.*?)\2', re.S)
            for match in attr_pattern.finditer(token):
                value = match.group(3)
                if useful(value):
                    self.segments.append(Segment(start + match.start(3), start + match.end(3), value, "attribute"))
        if tag in SKIP_TEXT:
            self.skip_depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() in SKIP_TEXT and self.skip_depth:
            self.skip_depth -= 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if not self.skip_depth:
            for index in range(len(self.block_stack) - 1, -1, -1):
                block_tag, content_start = self.block_stack[index]
                if block_tag == tag:
                    del self.block_stack[index:]
                    content_end = self.absolute_offset()
                    value = self.raw[content_start:content_end]
                    visible = re.sub(r"<[^>]+>", " ", value)
                    if useful(visible):
                        self.blocks.append(Segment(content_start, content_end, value, "block"))
                    break
        if tag in SKIP_TEXT and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.skip_depth or not data.strip():
            return
        left = len(data) - len(data.lstrip())
        right = len(data.rstrip())
        core = data[left:right]
        if useful(core):
            start = self.absolute_offset() + left
            self.segments.append(Segment(start, start + len(core), core, "text"))


def useful(text: str) -> bool:
    value = re.sub(r"\s+", " ", text).strip()
    if len(value) < 2 or not re.search(r"[A-Za-z]", value):
        return False
    if re.fullmatch(r"(?:https?://|mailto:|#|\.?\.?/)[^\s]+", value):
        return False
    if re.fullmatch(r"[\w.-]+/[\w./-]+", value):
        return False
    return True


def script_segments(raw: str) -> list[Segment]:
    out: list[Segment] = []
    for script in SCRIPT_RE.finditer(raw):
        attrs, body = script.group(1), script.group(2)
        if re.search(r'(?i)\bsrc\s*=|application/json', attrs):
            continue
        body_start = script.start(2)
        for pattern in (UI_FIELD_RE, UI_CALL_RE):
            for match in pattern.finditer(body):
                text = match.group(2)
                if useful(text):
                    out.append(Segment(body_start + match.start(2), body_start + match.end(2), text, "script-ui"))
    return out


def extract_segments(raw: str) -> list[Segment]:
    parser = SegmentParser(raw)
    parser.feed(raw)
    blocks: list[Segment] = []
    for item in sorted(parser.blocks, key=lambda segment: (segment.start, -segment.end)):
        if not any(item.start >= parent.start and item.end <= parent.end for parent in blocks):
            blocks.append(item)
    uncovered = [item for item in parser.segments
                 if not any(item.start >= block.start and item.end <= block.end for block in blocks)]
    candidates = blocks + uncovered + script_segments(raw)
    unique: dict[tuple[int, int], Segment] = {}
    for item in candidates:
        unique[(item.start, item.end)] = item
    ordered = sorted(unique.values(), key=lambda item: (item.start, item.end))
    for previous, current in zip(ordered, ordered[1:]):
        if previous.end > current.start:
            raise ValueError(f"overlapping translation segments: {previous} / {current}")
    return ordered


def load_env(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def api_key() -> str:
    load_env(ROOT / ".env-dev")
    for name in ("NVIDIA_API_KEY", "NGC_API_KEY"):
        if os.environ.get(name):
            return os.environ[name]
    raise RuntimeError("no NVIDIA_API_KEY or NGC_API_KEY available")


def batches(items: list[tuple[str, str]], max_items: int = 16, max_chars: int = 6000) -> Iterable[list[tuple[str, str]]]:
    batch: list[tuple[str, str]] = []
    chars = 0
    for item in items:
        size = len(item[1])
        if batch and (len(batch) >= max_items or chars + size > max_chars):
            yield batch
            batch, chars = [], 0
        batch.append(item)
        chars += size
    if batch:
        yield batch


def parse_json_array(content: str) -> list[dict[str, str]]:
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.I)
    start, end = content.find("["), content.rfind("]")
    if start < 0 or end < start:
        raise ValueError("model response did not contain a JSON array")
    data = json.loads(content[start:end + 1])
    if not isinstance(data, list):
        raise ValueError("model response was not a JSON list")
    return data


def translate_batch(batch: list[tuple[str, str]], profile: dict, model: str, key: str, polish: bool,
                    ledger: UsageLedger, page: str) -> dict[str, str]:
    terminology = "; ".join(f"{source} => {target}" for source, target in profile.get("preferred_terms", {}).items())
    payload = [{"id": item_id, "source": source} for item_id, source in batch]
    action = ("Edit each Brazilian Portuguese source for grammar, agreement, precision, and natural technical flow. "
              "Do not retranslate English technical tokens that were deliberately preserved."
              if polish else
              "Translate each source into natural Brazilian Portuguese.")
    system = f"""You localize an NVIDIA course for students and software developers in Brazil.
{action}
Produce natural, publication-quality Brazilian Portuguese while preserving full technical meaning and teaching sequence.
Return ONLY a JSON array of objects with exactly keys id and translation, one per input id.
Preserve HTML tags, entities, escaped characters, ${{...}} placeholders, URLs, file paths, code identifiers, API fields,
model IDs, product names, and English titles of cited papers/books. Do not translate model prompts or invent explanations.
Avoid literal calques. Check articles, gender, number, prepositions, and sentence flow after translating. Prefer concise,
fluent instructional prose written for Brazilian software developers. Do not leave the English word loop in learner prose.
Terminology: {terminology}
Never use "IA agentiva", "soquete de raciocínio", "cérebro do agente", "ficheiro", or "equipa"."""
    started = time.monotonic()
    try:
        response = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                "temperature": 0.1,
                "max_tokens": 8000,
            },
            timeout=180,
        )
    except requests.RequestException:
        ledger.record(page, time.monotonic() - started, None, failed=True)
        raise
    try:
        body = response.json()
    except requests.JSONDecodeError:
        body = {}
    usage = body.get("usage", {}) if response.ok else {}
    ledger.record(page, time.monotonic() - started, usage, failed=not response.ok)
    if not response.ok:
        raise RuntimeError(f"translation API HTTP {response.status_code}: {response.text[:300]}")
    content = body["choices"][0]["message"].get("content") or ""
    result = {}
    for row in parse_json_array(content):
        if isinstance(row, dict) and isinstance(row.get("id"), str) and isinstance(row.get("translation"), str):
            result[row["id"]] = row["translation"]
    return result


def protected_tokens(text: str) -> list[str]:
    return PLACEHOLDER_RE.findall(text)


def restore_protected(source: str, target: str) -> str:
    expected = protected_tokens(source)
    matches = list(PLACEHOLDER_RE.finditer(target))
    if len(expected) != len(matches):
        return target
    for match, token in zip(reversed(matches), reversed(expected)):
        target = target[:match.start()] + token + target[match.end():]
    return target


def valid_translation(source: str, target: str) -> bool:
    if not target.strip():
        return False
    return protected_tokens(source) == protected_tokens(target)


def clean_translation(source: str, target: str) -> str:
    if "\\n" not in source:
        target = target.replace("\\n", " ")
    if "\\t" not in source:
        target = target.replace("\\t", " ")
    return target


def cache_key(locale: str, source: str) -> str:
    return hashlib.sha256(f"{TRANSLATION_REVISION}\0{locale}\0{source}".encode("utf-8")).hexdigest()


def load_cache(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(path: Path, cache: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def translate_page(source_path: Path, target_path: Path, profile: dict, model: str, cache_path: Path,
                   dry_run: bool, workers: int, polish: bool, ledger: UsageLedger) -> tuple[int, int]:
    input_path = target_path if polish else source_path
    if polish and not input_path.is_file():
        raise FileNotFoundError(f"cannot polish missing target: {target_path}")
    raw = input_path.read_text(encoding="utf-8")
    segments = extract_segments(raw)
    cache = load_cache(cache_path)
    distinct: dict[str, str] = {}
    for segment in segments:
        distinct.setdefault(cache_key(profile["locale"], segment.text), segment.text)
    missing = [(key, text) for key, text in distinct.items()
               if key not in cache or not valid_translation(text, clean_translation(text, cache[key]))]
    label = f"{source_path.relative_to(ROOT)} ({'polish' if polish else 'translate'})"
    print(f"{label}: {len(segments)} segments, {len(distinct)} distinct, {len(missing)} API", flush=True)
    if dry_run:
        return len(segments), len(missing)
    key = api_key()
    work = list(enumerate(batches(missing), 1))

    def run_batch(index: int, batch: list[tuple[str, str]]) -> tuple[int, dict[str, str]]:
        translated: dict[str, str] | None = None
        for attempt in range(3):
            try:
                translated = translate_batch(batch, profile, model, key, polish, ledger, label)
                break
            except (requests.RequestException, RuntimeError, ValueError, json.JSONDecodeError) as exc:
                if attempt == 2:
                    raise
                print(f"  batch {index}: retry {attempt + 1}: {exc}", flush=True)
                time.sleep(2 ** attempt)
        assert translated is not None
        accepted = {}
        bad = []
        for item_id, source in batch:
            target = clean_translation(source, restore_protected(source, translated.get(item_id, "")))
            if valid_translation(source, target):
                accepted[item_id] = target
            else:
                bad.append((item_id, source))
        for item_id, source in bad:
            repaired = ""
            for attempt in range(3):
                try:
                    one = translate_batch([(item_id, source)], profile, model, key, polish, ledger, label)
                    repaired = clean_translation(source, restore_protected(source, one.get(item_id, "")))
                    if valid_translation(source, repaired):
                        break
                except (requests.RequestException, RuntimeError, ValueError, json.JSONDecodeError):
                    pass
                time.sleep(2 ** attempt)
            if valid_translation(source, repaired):
                accepted[item_id] = repaired
            elif polish:
                accepted[item_id] = source
                print(f"  batch {index}: retained one protected source segment", flush=True)
            else:
                raise ValueError(f"missing/placeholder-invalid translation for {item_id[:10]}")
        return index, accepted

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(run_batch, index, batch) for index, batch in work]
        for future in as_completed(futures):
            index, accepted = future.result()
            cache.update(accepted)
            save_cache(cache_path, cache)
            print(f"  batch {index}/{len(work)}: {len(accepted)} translated", flush=True)
    replacements = []
    for segment in segments:
        value = clean_translation(segment.text, cache[cache_key(profile["locale"], segment.text)])
        replacements.append((segment.start, segment.end, value))
    translated_raw = raw
    for start, end, value in sorted(replacements, reverse=True):
        translated_raw = translated_raw[:start] + value + translated_raw[end:]
    translated_raw = re.sub(r'(<html\b[^>]*\blang=)(["\'])[^"\']*\2',
                            rf'\1"{profile["html_lang"]}"', translated_raw, count=1, flags=re.I)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(translated_raw, encoding="utf-8")
    return len(segments), len(missing)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pages", nargs="+")
    parser.add_argument("--locale", default="pt-BR")
    parser.add_argument("--model", default="meta/llama-3.3-70b-instruct")
    parser.add_argument("--cache", type=Path, default=Path("/tmp/nemoclaw-pt-translation-cache-v2.json"))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--polish", action="store_true")
    parser.add_argument("--usage-report", type=Path,
                        help="write secret-free provider token/request accounting JSON")
    args = parser.parse_args()
    profile_path = ROOT / "scripts" / "translate" / "locales" / args.locale / "profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    locale_root = ROOT / "i18n" / profile["url_code"]
    ledger = UsageLedger(args.model)
    for raw_page in args.pages:
        source = (ROOT / raw_page).resolve()
        try:
            rel = source.relative_to(ROOT)
        except ValueError:
            parser.error(f"outside repository: {raw_page}")
        if not source.is_file() or rel.parts[:2] != ("web", "nemoclaw") or source.suffix != ".html":
            parser.error(f"not a course HTML source: {raw_page}")
        translate_page(source, locale_root / rel, profile, args.model, args.cache, args.dry_run, args.workers,
                       args.polish, ledger)
    if args.usage_report:
        args.usage_report.parent.mkdir(parents=True, exist_ok=True)
        args.usage_report.write_text(json.dumps(ledger.report(), indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
