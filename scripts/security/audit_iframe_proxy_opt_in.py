#!/usr/bin/env python3
"""Audit that iframe proxy support is explicit, bounded, and documented.

This is a narrow source audit. It does not contact Cloudflare or NVIDIA; it checks
that main keeps iframe execution available without silently routing normal course
traffic through the hosted workers.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]

CHECKS = [
    (
        "runtime exports iframe opt-in controls",
        "web/nemoclaw/_shared.js",
        ["iframeProxyModeEnabled", "setIframeProxyMode", "nemoclaw_iframe_proxy_opt_in"],
        [],
    ),
    (
        "runtime defaults direct and reserves worker for opt-in",
        "web/nemoclaw/_shared.js",
        ["https://integrate.api.nvidia.com/v1", "IFRAME_PROXY_URL", "iframe_proxy", "lms_proxy", "iframeProxy: false", "iframeProxy: true"],
        [r'const\s+DIRECT_URL\s*=\s*"https://nvidia-api-cors-proxy'],
    ),
    (
        "billing header is sent on both direct and iframe-proxy paths",
        "web/nemoclaw/_shared.js",
        ['h.set("X-BILLING-SOURCE", BILLING_SOURCE)', 'const h = { "Content-Type": "application/json", "X-BILLING-SOURCE": BILLING_SOURCE }'],
        [r'if\s*\(cfg\.iframeProxy\).*X-BILLING-SOURCE', r'if\s*\(iframeProxyModeEnabled\(\)\).*X-BILLING-SOURCE'],
    ),
    (
        "key panel exposes explicit learner toggle",
        "web/nemoclaw/_keypanel.js",
        ["iframe-proxy-toggle", "Enable LMS/static iframe execution", "setIframeProxyMode"],
        [],
    ),
    (
        "build proxy has origin allowlist and safe CORS",
        "cors-proxy/cors-proxy-worker-build.js",
        ["ALLOWED_ORIGINS", "ALLOW_ANY_ORIGIN", "Origin not allowed for iframe proxy", "Vary", 'fwd.delete("cookie")'],
        [r'Access-Control-Allow-Origin"\s*:\s*origin\b'],
    ),
    (
        "launchable proxy has origin and upstream allowlists",
        "cors-proxy/cors-proxy-worker-openclaw.js",
        ["ALLOWED_ORIGINS", "ALLOWED_UPSTREAM_HOSTS", "ALLOWED_UPSTREAM_SUFFIXES", "Origin not allowed for launchable proxy", "Upstream host not allowed"],
        [],
    ),
    (
        "landing page names iframe mode as opt-in",
        "web/nemoclaw/index.html",
        ["Enable LMS/static iframe mode only", "hosted CORS worker is used only"],
        [],
    ),
    (
        "proxy explorer documents opt-in carve-out",
        "cors-proxy/SKILL.html",
        ["opt-in", "ALLOWED_ORIGINS", "ALLOW_ANY_ORIGIN"],
        [],
    ),
]


def main() -> int:
    failures: list[str] = []
    for label, rel, required, forbidden in CHECKS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        missing = [needle for needle in required if needle not in text]
        bad = [pat for pat in forbidden if re.search(pat, text)]
        if missing or bad:
            parts = []
            if missing:
                parts.append("missing " + ", ".join(missing))
            if bad:
                parts.append("forbidden " + ", ".join(bad))
            failures.append(f"FAIL {label} ({rel}): " + "; ".join(parts))
        else:
            print(f"PASS {label}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
