#!/usr/bin/env python3
"""Audit OpenClaw fail-fast and Brev backup guidance."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

for _p in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
    if (_p / "scripts" / "_bootstrap.py").exists():
        sys.path.insert(0, str(_p / "scripts"))
        break
from _bootstrap import find_repo_root

ROOT = find_repo_root(Path(__file__).resolve())
NODE_CANDIDATES = [
    os.environ.get("NODE"),
    shutil.which("node"),
    "/mnt/c/Users/vkudlay/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe",
]

FILES = {
    "kickstart": ROOT / "web" / "nemoclaw" / "03a-kickstart.html",
    "openclaw_js": ROOT / "web" / "nemoclaw" / "scripts" / "_openclaw.js",
    "cors_worker": ROOT / "cors-proxy" / "cors-proxy-worker-openclaw.js",
    "runtime_js": ROOT / "scripts" / "runtime" / "test_page_runtime.js",
    "runtime_sh": ROOT / "scripts" / "runtime" / "lab_runtime_test.sh",
    "runtime_skill": ROOT / "scripts" / "runtime" / "SKILL.html",
    "scripts_skill": ROOT / "scripts" / "SKILL.html",
    "validation_skill": ROOT / "scripts" / "validation" / "SKILL.html",
    "worker_ws_audit": ROOT / "scripts" / "validation" / "openclaw_worker_ws_audit.mjs",
    "gw_transport_audit": ROOT / "scripts" / "validation" / "gw_connect_transport_audit.mjs",
}

REQUIRED = {
    "kickstart": ["EPERM", "Brev App URL", "CF_Authorization", "Fail-fast backup"],
    "openclaw_js": ["EPERM", "CF_Authorization", "Brev session URL", "stop local probing", "${fallback}${hint}", "openclawGatewayWsUrl", "cf_access_jwt", "hideHtmlFrame"],
    "cors_worker": ["WORKER_VERSION", "CF_Authorization", "CF-Access-Jwt-Assertion", "cf_access_jwt", "targetSearch.delete", "upstream.webSocket", "Origin", "http://localhost:8088"],
    "runtime_js": ["OPENCLAW_BACKUP_HINT", "preflightOpenClaw", "resolveOpenClawToken", "OPENCLAW_TOKEN: discovered", "localStorage.setItem('nemoclaw_clawcfjwt'", "RESULT: FAIL (OpenClaw credentials supplied", "toolsMissing) ? 1 : 0", "'/health'"],
    "runtime_sh": ["CLAW_CF=<CF_Authorization>", "Use Brev URL if local OpenClaw fails or shows EPERM"],
    "runtime_skill": ["OpenClaw fallback", "CF_Authorization", "EPERM", "CLAW_CF"],
    "scripts_skill": ["OpenClaw fallback", "python3 scripts/validation/openclaw_fallback_audit.py"],
    "validation_skill": ["openclaw_fallback_audit.py", "OpenClaw fallback"],
    "worker_ws_audit": ["openclaw worker ws audit", "CF_Authorization", "http://localhost:8088", "upstream WebSocket response directly"],
    "gw_transport_audit": ["gw connect transport audit", "falling back to direct browser-cookie WebSocket"],
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def audit() -> list[str]:
    findings: list[str] = []
    for key, tokens in REQUIRED.items():
        path = FILES[key]
        if not path.is_file():
            findings.append(f"missing {path.relative_to(ROOT)}")
            continue
        raw = read(path)
        for token in tokens:
            if token not in raw:
                findings.append(f"{path.relative_to(ROOT)} missing {token}")

    openclaw = read(FILES["openclaw_js"])
    if "try { await runAction(action); }\n      try { await runAction(action); }" in openclaw:
        findings.append("web/nemoclaw/scripts/_openclaw.js runs each probe action twice")
    if "?cf_access_jwt=" in openclaw and "?cf_access_jwt=..." not in openclaw:
        findings.append("web/nemoclaw/scripts/_openclaw.js may log the raw CF Access JWT in gateway output")
    if "cf_access_jwt=..." in openclaw and "__nemoclaw_proxy_meta" not in openclaw:
        findings.append("GW_CONNECT should check the live proxy version before using Brev WebSocket proxy mode")
    if "setOutput(head + `   (HTML" in openclaw and "hideHtmlFrame(true);" not in openclaw:
        findings.append("web/nemoclaw/scripts/_openclaw.js does not clear stale HTML iframe before non-HTML output")

    m = re.search(r"export const GW_CONNECT = `([\s\S]*?)`;", openclaw)
    if not m:
        findings.append("web/nemoclaw/scripts/_openclaw.js missing GW_CONNECT template")
    else:
        # This is not a full JS parser. It catches the exact class of regression where
        # regex slash escapes inside the template literal decode into invalid cell code
        # such as replace(//+$/, ""), which module-level node --check cannot see.
        decoded = m.group(1).replace(r"\/", "/")
        if "replace(//" in decoded:
            findings.append("GW_CONNECT template decodes to invalid regex/comment syntax; avoid slash regex literals inside stringified cells")
        if "openclawGatewayWsUrl" in decoded and 'new RegExp("/+$")' not in decoded:
            findings.append('GW_CONNECT gateway URL helper must avoid slash regex literals; use new RegExp("/+$")')
    node = next((Path(c) for c in NODE_CANDIDATES if c and Path(c).exists()), None)
    if not node:
        findings.append("node runtime not found for openclaw_worker_ws_audit.mjs")
    else:
        for script_key in ("worker_ws_audit", "gw_transport_audit"):
            proc = subprocess.run([str(node), str(FILES[script_key])], cwd=ROOT, text=True, capture_output=True)
            if proc.returncode != 0:
                detail = (proc.stdout + proc.stderr).strip().replace("\n", " | ")
                findings.append(f"{FILES[script_key].name} failed: {detail}")
    return findings


def main() -> int:
    findings = audit()
    if findings:
        for item in findings:
            print(item)
        return 1
    print("openclaw fallback audit: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
