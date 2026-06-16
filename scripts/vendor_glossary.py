#!/usr/bin/env python3
"""Vendor NVIDIA glossary pages into mats/glossary_raw/ as markdown + local images.

For each glossary term it fetches the page, extracts the main article (the AEM
`div.root.responsivegrid` container, minus the header/nav/footer/script chrome),
converts it to GitHub-flavored markdown, downloads the page's content images into
`mats/glossary_raw/images/`, rewrites the image references to those local files,
and records a version log (source URL, fetch date, content hash, image list) in
`mats/glossary_raw/_versions.json`.

These pages are NVIDIA marketing content. See mats/glossary_raw/README.md for why
they are vendored as primary sources to read critically, not quoted as ground truth.

Dependencies: requests, beautifulsoup4, markdownify, lxml
  pip install requests beautifulsoup4 markdownify lxml

Usage:
  python3 scripts/vendor_glossary.py                 # vendor the default TERMS list
  python3 scripts/vendor_glossary.py deep-agents      # vendor one or more named slugs
  python3 scripts/vendor_glossary.py --list           # print the default TERMS and exit

Static-HTML limitation: images injected by client-side JavaScript (some inline
step diagrams) are not in the fetched HTML and are not captured. The hero image,
SVG figures, and card images that ship in the static markup are.
"""
from __future__ import annotations
import sys
import os
import re
import glob
import json
import hashlib
import datetime
import mimetypes
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as to_md

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)                       # scripts/ sits directly under the repo root
RAW = os.path.join(REPO, "mats", "glossary_raw")
IMG = os.path.join(RAW, "images")
VERSIONS = os.path.join(RAW, "_versions.json")
BASE = "https://www.nvidia.com/en-us/glossary/{slug}/"
UA = {"User-Agent": "Mozilla/5.0 (NVIDIA DLI course glossary vendoring)"}

# The glossary terms that back an entry in ../nvidia_agent_glossary.md. Add a slug
# here to vendor more (e.g. "generative-ai", "artificial-intelligence", "cot-prompting"
# are discoverable cross-references, left out of the default to keep the set lean).
TERMS = [
    "ai-agents",
    "ai-reasoning",
    "deep-agents",
    "retrieval-augmented-generation",
    "large-language-models",
    "ai-inference",
    "vector-database",
]

# Chrome to drop before converting: by CSS selector and by element id.
# NOTE: <noscript> is NOT stripped here. NVIDIA lazy-loads images with JS and puts
# the real <img src> in a <noscript> fallback, so those tags are unwrapped (their
# children promoted) before extraction; deleting them drops the page's diagrams.
STRIP_SELECTORS = ["script", "style", "header", "nav", "iframe",
                   ".global-footer", ".page-footer-wrapper"]
STRIP_IDS = ["main-header", "brandFooter", "globalFooter", "country-selector-modal"]


def fetch(url: str) -> str:
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    return r.text


def page_title(soup: BeautifulSoup) -> str:
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        return og["content"].strip()
    if soup.title and soup.title.string:
        return soup.title.string.split("|")[0].strip()
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else "Untitled"


def clean_aem_image_url(src: str) -> str:
    # AEM emits responsive templates like `coreimg.100{.width}.jpeg`; strip the
    # width token so the URL resolves to a concrete asset.
    src = re.sub(r"\.\d+\{\.width\}", "", src)
    src = src.replace("{.width}", "")
    return src


def content_root(soup: BeautifulSoup):
    root = soup.select_one("div.root.responsivegrid")
    return root or soup.body


def vendor_images(node, slug: str, page_url: str) -> list[str]:
    # Drop any images from a previous run of this slug so re-fetches stay reproducible.
    for old in glob.glob(os.path.join(IMG, f"{slug}-*")):
        os.remove(old)
    saved: list[str] = []
    for img in node.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src or src.startswith("data:"):
            img.decompose()
            continue
        if "img.youtube.com" in src:
            # video poster, not a representative diagram; leave the external ref as-is
            continue
        absu = urljoin(page_url, clean_aem_image_url(src))
        try:
            r = requests.get(absu, headers=UA, timeout=30)
            r.raise_for_status()
        except Exception as exc:  # noqa: BLE001 - a missing asset must not abort the page
            print(f"      ! image skipped ({exc}): {absu[:90]}")
            img.decompose()
            continue
        ext = os.path.splitext(urlparse(absu).path)[1].split("?")[0].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"):
            guessed = mimetypes.guess_extension((r.headers.get("content-type", "").split(";")[0]).strip())
            ext = guessed or ".img"
        fname = f"{slug}-{len(saved) + 1}{ext}"
        with open(os.path.join(IMG, fname), "wb") as fh:
            fh.write(r.content)
        img["src"] = f"images/{fname}"
        # srcset would re-introduce remote/templated URLs after markdown conversion
        if img.has_attr("srcset"):
            del img["srcset"]
        saved.append(fname)
    return saved


def absolutize_links(node, page_url: str) -> None:
    for a in node.find_all("a", href=True):
        href = a["href"].strip()
        if href and not href.startswith(("http://", "https://", "#", "mailto:")):
            a["href"] = urljoin(page_url, href)


def vendor(slug: str, versions: dict, today: str) -> None:
    url = BASE.format(slug=slug)
    soup = BeautifulSoup(fetch(url), "lxml")
    title = page_title(soup)
    node = content_root(soup)
    # Promote <noscript> image fallbacks into the tree (the real <img src> lives there).
    for ns in node.find_all("noscript"):
        ns.unwrap()
    for sel in STRIP_SELECTORS:
        for el in node.select(sel):
            el.decompose()
    for el_id in STRIP_IDS:
        el = node.find(id=el_id)
        if el:
            el.decompose()
    images = vendor_images(node, slug, url)
    absolutize_links(node, url)

    body = to_md(str(node), heading_style="ATX", bullets="-")
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    out = f"# [{title}]({url})\n\n{body}\n"
    with open(os.path.join(RAW, f"{slug}.md"), "w", encoding="utf-8") as fh:
        fh.write(out)

    versions[slug] = {
        "url": url,
        "fetched": today,
        "sha256": hashlib.sha256(out.encode("utf-8")).hexdigest()[:16],
        "bytes": len(out),
        "images": images,
    }
    print(f"  {slug}: {len(out)} bytes, {len(images)} image(s)")


def main() -> int:
    args = sys.argv[1:]
    if "--list" in args:
        print("\n".join(TERMS))
        return 0
    slugs = [a for a in args if not a.startswith("-")] or TERMS
    os.makedirs(IMG, exist_ok=True)
    versions = {}
    if os.path.exists(VERSIONS):
        with open(VERSIONS, encoding="utf-8") as fh:
            versions = json.load(fh)
    today = datetime.date.today().isoformat()
    for slug in slugs:
        try:
            vendor(slug, versions, today)
        except Exception as exc:  # noqa: BLE001 - report and continue with the rest
            print(f"  {slug}: FAILED ({exc})")
    with open(VERSIONS, "w", encoding="utf-8") as fh:
        json.dump(dict(sorted(versions.items())), fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"  -> {VERSIONS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
