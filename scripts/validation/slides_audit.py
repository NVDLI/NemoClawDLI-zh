#!/usr/bin/env python3
# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Validate the hosted repository-overview deck and its source manifest.

The audit deliberately reuses prose_variety.py for writing quality, then adds
presentation-only contracts: claim scope, module narrative coverage, source
evidence breadth, text density, speaker-note depth, screenshot contrast,
isolated SVG variables, generated HTML freshness, and capture provenance.
Mutation tests prove the unique detectors reject known regressions.
"""
from __future__ import annotations

import argparse
import copy
import html
import json
import math
import re
import struct
import sys
import tempfile
import zlib
from pathlib import Path
from zipfile import BadZipFile, ZipFile

for _path in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
    if (_path / "scripts" / "_bootstrap.py").exists():
        sys.path.insert(0, str(_path / "scripts"))
        break
from _bootstrap import add_script_paths, find_repo_root

ROOT = find_repo_root(Path(__file__).resolve())
add_script_paths(ROOT / "scripts")
sys.path.insert(0, str(ROOT / "scripts" / "build"))
import prose_variety as pv  # noqa: E402
import build_repository_overview_html as html_builder  # noqa: E402

MANIFEST = ROOT / "docs" / "repository-overview.slides.json"
HTML = ROOT / "docs" / "repository-overview.html"
PPTX = ROOT / "docs" / "repository-overview.pptx"
CAPTURES = ROOT / "docs" / "assets" / "repository-overview" / "captures.json"
ALLOWED_LAYOUTS = {"title", "screenshot", "sequence", "comparison", "gates", "layers", "tree", "lanes", "review"}
ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
VAR_USE_RE = re.compile(r"var\(\s*(--[\w-]+)(\s*,[^)]*)?\)")
VAR_DEF_RE = re.compile(r"(--[\w-]+)\s*:")
WORD_RE = re.compile(r"\b[\w'-]+\b")
MAX_TITLE_CHARS = 50
MAX_LEAD_CHARS = 110
MAX_DETAIL_CHARS = 100
ALLOWED_CLAIM_SCOPES = {"course", "repository", "module:1", "module:2", "module:3", "module:4",
                        "page:01a", "page:01b", "page:01c", "page:02a", "page:02b", "page:02c",
                        "page:03a", "page:03b", "page:03c", "page:04a", "page:04b", "page:04c"}
MODULE_EVIDENCE = {
    "module:1": {"web/nemoclaw/01a-loop.html", "web/nemoclaw/01b-react.html", "web/nemoclaw/01c-tools.html"},
    "module:2": {"web/nemoclaw/02a-routing.html", "web/nemoclaw/02b-rag.html", "web/nemoclaw/02c-deep.html"},
    "module:3": {"web/nemoclaw/03a-kickstart.html", "web/nemoclaw/03b-openclaw.html", "web/nemoclaw/03c-always-on.html"},
    "module:4": {"web/nemoclaw/04a-safety.html", "web/nemoclaw/04b-modern-clis.html", "web/nemoclaw/04c-going-further.html"},
}
PAGE_EVIDENCE = {
    "page:01a": "web/nemoclaw/01a-loop.html", "page:01b": "web/nemoclaw/01b-react.html",
    "page:01c": "web/nemoclaw/01c-tools.html", "page:02a": "web/nemoclaw/02a-routing.html",
    "page:02b": "web/nemoclaw/02b-rag.html", "page:02c": "web/nemoclaw/02c-deep.html",
    "page:03a": "web/nemoclaw/03a-kickstart.html", "page:03b": "web/nemoclaw/03b-openclaw.html",
    "page:03c": "web/nemoclaw/03c-always-on.html", "page:04a": "web/nemoclaw/04a-safety.html",
    "page:04b": "web/nemoclaw/04b-modern-clis.html", "page:04c": "web/nemoclaw/04c-going-further.html",
}
# Mirrors the module map in web/nemoclaw/index.html. These groups prevent a
# narrow page concept from being promoted to a module thesis simply by listing
# all three page files as evidence.
MODULE_REQUIRED_TERMS = {
    "module:1": (("loop",), ("react",), ("tool",)),
    "module:2": (("workflow",), ("rag", "retriev"), ("deep", "sub-agent")),
    "module:3": (("openclaw",), ("gateway",), ("workspace",), ("skill",), ("schedul",)),
    "module:4": (("openshell",), ("cli",), ("safety", "policy", "contain")),
}


def finding(code: str, path: str, detail: str) -> dict:
    return {"code": code, "path": path, "detail": detail}


def safe_path(root: Path, value: str) -> Path | None:
    candidate = (root / value).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def slide_texts(slide: dict) -> list[tuple[str, str]]:
    """Return prose fields; labels, paths, ids, and status tokens are UI metadata."""
    out = []
    for key in ("title", "lead", "notes"):
        if slide.get(key):
            out.append((key, slide[key]))
    visual = slide.get("visual") or {}
    if visual.get("caption"):
        out.append(("caption", visual["caption"]))
    if visual.get("outcome"):
        out.append(("outcome", visual["outcome"]))
    for key in ("points",):
        for index, value in enumerate(visual.get(key, []), 1):
            out.append((f"{key}[{index}]", value))
    for key in ("items", "steps", "lanes"):
        for index, item in enumerate(visual.get(key, []), 1):
            if item.get("detail"):
                out.append((f"{key}[{index}].detail", item["detail"]))
    return out


def shared_prose_findings(manifest: dict) -> list[dict]:
    """Recycle the course's grammar, buzz, and vacuous-meta detectors verbatim."""
    out = []
    for slide in manifest.get("slides", []):
        sid = slide.get("id", "?")
        for field, text in slide_texts(slide):
            for kind, sentence in pv.antithesis_hits([text]):
                out.append(finding("shared-prose-buzz", f"{sid}.{field}", f"[{kind}] {sentence}"))
            for kind, sentence in pv.grammar_hits([text]):
                out.append(finding("shared-prose-grammar", f"{sid}.{field}", f"[{kind}] {sentence}"))
            for phrase, sentence in pv._vacuous_meta_text([text]):
                out.append(finding("shared-prose-meta", f"{sid}.{field}", f"{phrase}: {sentence}"))
    return out


def png_stats(path: Path) -> dict:
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not PNG")
    pos, width, height, bit_depth, color_type, compressed = 8, 0, 0, 0, 0, bytearray()
    while pos < len(raw):
        size = struct.unpack(">I", raw[pos:pos + 4])[0]
        kind = raw[pos + 4:pos + 8]
        data = raw[pos + 8:pos + 8 + size]
        pos += 12 + size
        if kind == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", data[:10])
        elif kind == b"IDAT":
            compressed.extend(data)
        elif kind == b"IEND":
            break
    if bit_depth != 8 or color_type not in (2, 6):
        raise ValueError(f"unsupported PNG format bit_depth={bit_depth} color_type={color_type}")
    bpp = 3 if color_type == 2 else 4
    scan = zlib.decompress(bytes(compressed))
    stride = width * bpp
    prior = bytearray(stride)
    values = []
    offset = 0
    sample_every = max(1, (width * height) // 20000)
    sample_index = 0
    for _ in range(height):
        mode = scan[offset]
        row = bytearray(scan[offset + 1:offset + 1 + stride])
        offset += stride + 1
        for i in range(stride):
            left = row[i - bpp] if i >= bpp else 0
            up = prior[i]
            upper_left = prior[i - bpp] if i >= bpp else 0
            if mode == 1:
                row[i] = (row[i] + left) & 255
            elif mode == 2:
                row[i] = (row[i] + up) & 255
            elif mode == 3:
                row[i] = (row[i] + ((left + up) // 2)) & 255
            elif mode == 4:
                p = left + up - upper_left
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - upper_left)
                predictor = left if pa <= pb and pa <= pc else up if pb <= pc else upper_left
                row[i] = (row[i] + predictor) & 255
            elif mode != 0:
                raise ValueError(f"unsupported PNG filter {mode}")
        for i in range(0, stride, bpp):
            if sample_index % sample_every == 0:
                r, g, b = row[i:i + 3]
                values.append((299 * r + 587 * g + 114 * b) / 1000)
            sample_index += 1
        prior = row
    mean = sum(values) / len(values)
    deviation = math.sqrt(sum((x - mean) ** 2 for x in values) / len(values))
    return {"width": width, "height": height, "mean": mean, "deviation": deviation,
            "range": max(values) - min(values), "near_black": sum(x < 8 for x in values) / len(values)}


def svg_variable_findings(path: Path, rel: str) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    definitions = set(VAR_DEF_RE.findall(text))
    out = []
    for name, fallback in VAR_USE_RE.findall(text):
        if name not in definitions and not fallback:
            out.append(finding("isolated-svg-var", rel, f"{name} has no in-file definition or var() fallback"))
    return out


def asset_values(slide: dict) -> list[str]:
    visual = slide.get("visual") or {}
    values = [visual["asset"]] if visual.get("asset") else []
    values.extend(item["asset"] for item in visual.get("images", []) if item.get("asset"))
    return values


def pptx_findings(manifest: dict, path: Path = PPTX) -> list[dict]:
    out = []
    if not path.is_file():
        return [finding("pptx-missing", str(path.relative_to(ROOT)), "PowerPoint projection missing")]
    try:
        with ZipFile(path) as archive:
            if archive.testzip():
                out.append(finding("pptx-corrupt", str(path.relative_to(ROOT)), "ZIP member CRC failed"))
                return out
            names = archive.namelist()
            slide_names = sorted(
                (name for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
                key=lambda value: int(re.search(r"(\d+)", Path(value).stem).group(1)),
            )
            note_names = [name for name in names if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", name)]
            if len(slide_names) != len(manifest["slides"]):
                out.append(finding("pptx-slide-count", str(path.relative_to(ROOT)),
                                   f"contains {len(slide_names)} slides; expected {len(manifest['slides'])}"))
            if len(note_names) != len(manifest["slides"]):
                out.append(finding("pptx-notes", str(path.relative_to(ROOT)),
                                   f"contains {len(note_names)} notes slides; expected {len(manifest['slides'])}"))
            presentation = archive.read("ppt/presentation.xml").decode("utf-8")
            size_match = re.search(r"<p:sldSz\b[^>]*cx=\"(\d+)\"[^>]*cy=\"(\d+)\"", presentation)
            if not size_match or abs(int(size_match.group(1)) / int(size_match.group(2)) - 16 / 9) > .01:
                out.append(finding("pptx-aspect", str(path.relative_to(ROOT)), "slide size is not 16:9"))
            for index, (slide_name, spec) in enumerate(zip(slide_names, manifest["slides"]), 1):
                xml = archive.read(slide_name).decode("utf-8")
                visible = " ".join(html.unescape(value) for value in re.findall(r"<a:t>(.*?)</a:t>", xml))
                if spec["title"] not in visible:
                    out.append(finding("pptx-title", f"slide {index}", f"missing title: {spec['title']}"))
    except (BadZipFile, KeyError, OSError) as exc:
        out.append(finding("pptx-corrupt", str(path), str(exc)))
    return out


def audit_manifest(
    manifest: dict, root: Path = ROOT, html_text: str | None = None, *,
    check_asset_quality: bool = True,
    check_projection: bool = True,
    check_pptx: bool = True,
) -> list[dict]:
    out = []
    slides = manifest.get("slides")
    if manifest.get("schema") != "nemoclaw-stakeholder-slides/2":
        out.append(finding("schema", "manifest", "expected nemoclaw-stakeholder-slides/2"))
    if not isinstance(slides, list) or not (12 <= len(slides) <= 20):
        return out + [finding("slide-count", "manifest", "expected 12 to 20 slides")]
    ids = [slide.get("id", "") for slide in slides]
    if len(ids) != len(set(ids)):
        out.append(finding("duplicate-id", "manifest", "slide ids must be unique"))
    module_positions = [(index, slide.get("claim_scope")) for index, slide in enumerate(slides)
                        if str(slide.get("claim_scope", "")).startswith("module:")]
    expected_module_scopes = ["module:1", "module:2", "module:3", "module:4"]
    actual_module_scopes = [scope for _, scope in module_positions]
    actual_module_positions = [index for index, _ in module_positions]
    if actual_module_scopes != expected_module_scopes:
        out.append(finding("module-sequence", "manifest",
                           f"expected one ordered overview for Modules 1-4; got {actual_module_scopes}"))
    elif actual_module_positions != list(range(actual_module_positions[0], actual_module_positions[0] + 4)):
        out.append(finding("module-sequence", "manifest",
                           "Module 1-4 overview slides must form one uninterrupted block"))
    capture_files = set()
    capture_path = root / "docs" / "assets" / "repository-overview" / "captures.json"
    if capture_path.is_file():
        capture_files = {item.get("file") for item in json.loads(capture_path.read_text(encoding="utf-8")).get("captures", [])}
    else:
        out.append(finding("capture-provenance", "docs/assets/repository-overview/captures.json", "capture manifest missing"))

    for index, slide in enumerate(slides, 1):
        sid = slide.get("id", f"slide-{index}")
        where = f"slides[{index}].{sid}"
        if not ID_RE.match(sid):
            out.append(finding("slide-id", where, "use lowercase kebab-case"))
        if slide.get("layout") not in ALLOWED_LAYOUTS:
            out.append(finding("layout", where, f"unsupported layout {slide.get('layout')!r}"))
        for key in ("claim_scope", "kicker", "title", "notes", "evidence"):
            if not slide.get(key):
                out.append(finding("required-field", where, f"missing {key}"))
        claim_scope = slide.get("claim_scope", "")
        if claim_scope not in ALLOWED_CLAIM_SCOPES:
            out.append(finding("claim-scope", where, f"unsupported claim scope: {claim_scope!r}"))
        evidence = set(slide.get("evidence", []))
        if claim_scope == "course" and not evidence.intersection(
                {"web/nemoclaw/COURSE_CANON.md", "web/nemoclaw/index.html"}):
            out.append(finding("claim-evidence", where, "course claim lacks COURSE_CANON.md or index.html evidence"))
        required_module_evidence = MODULE_EVIDENCE.get(claim_scope, set())
        if required_module_evidence - evidence:
            missing = ", ".join(sorted(required_module_evidence - evidence))
            out.append(finding("claim-evidence", where, f"module claim lacks page evidence: {missing}"))
        required_page_evidence = PAGE_EVIDENCE.get(claim_scope)
        if required_page_evidence and required_page_evidence not in evidence:
            out.append(finding("claim-evidence", where, f"page claim lacks evidence: {required_page_evidence}"))
        module_label = re.search(r"\bModule\s+([1-4])\b", f"{slide.get('kicker', '')} {slide.get('title', '')}")
        if module_label and claim_scope not in {"course", f"module:{module_label.group(1)}"}:
            out.append(finding("claim-scope", where,
                               f"Module {module_label.group(1)} label conflicts with {claim_scope!r}"))
        if claim_scope.startswith("module:") and not module_label:
            out.append(finding("claim-scope", where, f"{claim_scope} claim is not labeled as a module"))
        if claim_scope.startswith("page:"):
            page_label = claim_scope.split(":", 1)[1]
            shown = f"{slide.get('kicker', '')} {slide.get('title', '')}".lower()
            display_label = page_label[1:] if page_label.startswith("0") else page_label
            if display_label not in shown:
                out.append(finding("claim-scope", where, f"{claim_scope} claim does not show its page label"))
        labels = [item.get("label", "") for key in ("items", "steps", "lanes")
                  for item in (slide.get("visual") or {}).get(key, [])]
        claim_text = " ".join([*(text for _, text in slide_texts(slide)), *labels]).lower()
        for alternatives in MODULE_REQUIRED_TERMS.get(claim_scope, ()):
            if not any(term in claim_text for term in alternatives):
                out.append(finding("claim-narrative", where,
                                   f"{claim_scope} claim omits required concept group: {' / '.join(alternatives)}"))
        title = slide.get("title", "")
        if "\n" in title or "\r" in title:
            out.append(finding("title-line", where, "title contains an explicit line break"))
        if len(title) > MAX_TITLE_CHARS:
            out.append(finding("title-length", where,
                               f"title contains {len(title)} characters; maximum is {MAX_TITLE_CHARS}"))
        lead = slide.get("lead", "")
        if len(lead) > MAX_LEAD_CHARS:
            out.append(finding("lead-length", where,
                               f"lead contains {len(lead)} characters; maximum is {MAX_LEAD_CHARS}"))
        visual = slide.get("visual") or {}
        details = list(visual.get("points", []))
        for key in ("items", "steps", "lanes"):
            details.extend(item.get("detail", "") for item in visual.get(key, []))
        for detail_index, detail in enumerate(details, 1):
            if len(detail) > MAX_DETAIL_CHARS:
                out.append(finding("body-length", where,
                                   f"body item {detail_index} contains {len(detail)} characters; maximum is {MAX_DETAIL_CHARS}"))
        note_words = len(WORD_RE.findall(slide.get("notes", "")))
        if not 45 <= note_words <= 120:
            out.append(finding("speaker-notes-depth", where, f"speaker notes contain {note_words} words; expected 45 to 120"))
        for evidence in slide.get("evidence", []):
            target = safe_path(root, evidence)
            if target is None or not target.is_file():
                out.append(finding("evidence", where, f"missing or unsafe evidence path: {evidence}"))
            elif check_asset_quality and target.suffix.lower() == ".svg":
                out.extend(svg_variable_findings(target, evidence))
        for asset in asset_values(slide):
            target = safe_path(root, asset)
            if target is None or not target.is_file():
                out.append(finding("visual-asset", where, f"missing or unsafe visual asset: {asset}"))
                continue
            if check_asset_quality and target.suffix.lower() == ".png":
                try:
                    stats = png_stats(target)
                except Exception as exc:
                    out.append(finding("screenshot-decode", asset, str(exc)))
                    continue
                if stats["width"] < 900 or stats["height"] < 160:
                    out.append(finding("screenshot-size", asset, f"{stats['width']}x{stats['height']} is below 900x160"))
                if stats["deviation"] < 8 or stats["range"] < 32 or stats["near_black"] > .995:
                    out.append(finding("screenshot-contrast", asset, f"image appears blank or near-monochrome: {stats}"))
                if target.name not in capture_files:
                    out.append(finding("capture-provenance", asset, "screenshot missing from captures.json"))

    out.extend(shared_prose_findings(manifest))
    if check_projection and html_text is None and root == ROOT and HTML.is_file():
        html_text = HTML.read_text(encoding="utf-8")
    if check_projection and html_text is not None:
        expected = html_builder.render(manifest)
        if html_text != expected:
            out.append(finding("generated-html", "docs/repository-overview.html", "generated deck is stale"))
        if re.search(r"<(?:script|link|img)\b[^>]+(?:src|href)=[\"']https?://", html_text, re.I):
            out.append(finding("remote-dependency", "docs/repository-overview.html", "hosted deck must use local assets only"))
        rendered_ids = re.findall(r'data-slide-id="([^"]+)"', html_text)
        if rendered_ids != ids:
            out.append(finding("generated-order", "docs/repository-overview.html", "rendered slide ids differ from manifest order"))
        rendered_scopes = re.findall(r'data-claim-scope="([^"]+)"', html_text)
        expected_scopes = [slide.get("claim_scope", "") for slide in slides]
        if rendered_scopes != expected_scopes:
            out.append(finding("generated-scope", "docs/repository-overview.html",
                               "rendered claim scopes differ from manifest order"))
    if check_pptx and root == ROOT:
        out.extend(pptx_findings(manifest))
    return out


def _png_bytes(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    row = bytes(rgb) * width
    raw = b"".join(b"\x00" + row for _ in range(height))
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def self_test() -> list[str]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    failures = []
    def mutation_findings(value: dict) -> list[dict]:
        # Mutation cases exercise manifest rules. Re-decoding every immutable screenshot,
        # rebuilding HTML, and reopening the same PPTX for each case adds no detector evidence.
        return audit_manifest(value, check_asset_quality=False,
                              check_projection=False, check_pptx=False)

    mutated = copy.deepcopy(manifest)
    mutated["slides"][1]["title"] = "One workflow, two implementations"
    if not any(x["code"] == "shared-prose-buzz" for x in mutation_findings(mutated)):
        failures.append("buzz mutation escaped")
    mutated = copy.deepcopy(manifest)
    mutated["slides"][2]["notes"] = "Too short."
    if not any(x["code"] == "speaker-notes-depth" for x in mutation_findings(mutated)):
        failures.append("speaker-note mutation escaped")
    mutated = copy.deepcopy(manifest)
    mutated["slides"][2]["title"] = "This title is intentionally long enough to wrap across multiple rendered lines"
    if not any(x["code"] == "title-length" for x in mutation_findings(mutated)):
        failures.append("long title mutation escaped")
    mutated = copy.deepcopy(manifest)
    mutated["slides"][2]["lead"] = "A " + "needlessly extended explanation " * 6
    if not any(x["code"] == "lead-length" for x in mutation_findings(mutated)):
        failures.append("long lead mutation escaped")
    mutated = copy.deepcopy(manifest)
    mutated["slides"][3]["visual"]["items"][0]["detail"] = "Needlessly extended body text " * 5
    if not any(x["code"] == "body-length" for x in mutation_findings(mutated)):
        failures.append("long body mutation escaped")
    mutated = copy.deepcopy(manifest)
    mutated["slides"][5]["evidence"].remove("web/nemoclaw/03c-always-on.html")
    if not any(x["code"] == "claim-evidence" for x in mutation_findings(mutated)):
        failures.append("narrow module evidence mutation escaped")
    mutated = copy.deepcopy(manifest)
    mutated["slides"][6]["claim_scope"] = "page:04a"
    if not any(x["code"] == "claim-scope" for x in mutation_findings(mutated)):
        failures.append("module/page scope mutation escaped")
    mutated = copy.deepcopy(manifest)
    mutated["slides"][5].update({
        "title": "Module 3 separates API, MCP, and gateway roles",
        "lead": "Model APIs answer requests. MCP connects tools. The gateway carries a persistent session.",
        "notes": "The page compares request-response APIs, Model Context Protocol, and a persistent gateway. Each interface serves a different integration role. The comparison appears at the beginning of Part 3a and explains how the browser changes transport when it connects to a long-running agent. Reviewers can inspect the protocol diagram and supporting page source for the specific request and event lifecycles.",
    })
    mutated["slides"][5]["visual"]["items"] = [
        {"label": "REST", "detail": "One request and one response."},
        {"label": "MCP", "detail": "Tool and resource integration."},
        {"label": "Gateway", "detail": "Long-lived session events."},
    ]
    if not any(x["code"] == "claim-narrative" for x in mutation_findings(mutated)):
        failures.append("narrow Module 3 narrative mutation escaped")
    mutated = copy.deepcopy(manifest)
    browser_index = next(index for index, slide in enumerate(mutated["slides"])
                         if slide.get("id") == "browser-artifact")
    browser_slide = mutated["slides"].pop(browser_index)
    module_three_index = next(index for index, slide in enumerate(mutated["slides"])
                              if slide.get("claim_scope") == "module:3")
    mutated["slides"].insert(module_three_index, browser_slide)
    if not any(x["code"] == "module-sequence" for x in mutation_findings(mutated)):
        failures.append("interrupted module sequence mutation escaped")
    mutated = copy.deepcopy(manifest)
    mutated["slides"][1]["visual"]["asset"] = "docs/assets/repository-overview/missing.png"
    if not any(x["code"] == "visual-asset" for x in mutation_findings(mutated)):
        failures.append("missing screenshot mutation escaped")
    with tempfile.TemporaryDirectory() as tmp:
        temp = Path(tmp)
        black = temp / "black.png"
        black.write_bytes(_png_bytes(900, 160, (0, 0, 0)))
        if png_stats(black)["deviation"] >= 8:
            failures.append("black screenshot mutation escaped")
        svg = temp / "bad.svg"
        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><rect fill="var(--missing)"/></svg>', encoding="utf-8")
        if not svg_variable_findings(svg, "bad.svg"):
            failures.append("isolated SVG variable mutation escaped")
    if not any(x["code"] == "generated-html" for x in audit_manifest(
            manifest, html_text="stale", check_asset_quality=False, check_pptx=False)):
        failures.append("stale HTML mutation escaped")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.self_test:
        failures = self_test()
        if failures:
            for item in failures:
                print(f"slides_audit self-test: FAIL: {item}", file=sys.stderr)
            return 1
        print("slides_audit self-test: PASS")
        return 0
    findings = audit_manifest(json.loads(args.manifest.read_text(encoding="utf-8")))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({"schema": "nemoclaw-slides-audit/1", "findings": findings}, indent=2) + "\n", encoding="utf-8")
    for item in findings:
        print(f"slides_audit: {item['code']}: {item['path']}: {item['detail']}")
    if findings:
        print(f"slides_audit: FAIL ({len(findings)} finding(s))", file=sys.stderr)
        return 1
    print("slides_audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
