#!/usr/bin/env python3
"""Audit OpenClaw fail-fast, Brev backup, and probe-frame cleanup contracts."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

for _p in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
    if (_p / "scripts" / "_bootstrap.py").exists():
        sys.path.insert(0, str(_p / "scripts"))
        break
from _bootstrap import find_repo_root

ROOT = find_repo_root(Path(__file__).resolve())
NODE_CANDIDATES = [
    os.environ.get("NODE_BIN"),
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
    "gw_recover_compile_audit": ROOT / "scripts" / "validation" / "gw_recover_compile_audit.mjs",
}

REQUIRED = {
    "kickstart": ["EPERM", "Brev App URL", "CF_Authorization", "Fail-fast backup"],
    "openclaw_js": ["EPERM", "CF_Authorization", "Brev session URL", "stop local probing", "${fallback}${hint}", "openclawGatewayWsUrl", "cf_access_jwt", "hideHtmlFrame", ".claw-html-frame[hidden]"],
    "cors_worker": ["WORKER_VERSION", "CF_Authorization", "CF-Access-Jwt-Assertion", "cf_access_jwt", "targetSearch.delete", "upstream.webSocket", "Origin", "http://localhost:8088"],
    "runtime_js": ["OPENCLAW_BACKUP_HINT", "preflightOpenClaw", "resolveOpenClawToken", "OPENCLAW_TOKEN: discovered", "localStorage.setItem('nemoclaw_clawcfjwt'", "RESULT: FAIL (OpenClaw credentials supplied", "toolsMissing) ? 1 : 0", "'/health'"],
    "runtime_sh": ["CLAW_CF=<CF_Authorization>", "Use Brev URL if local OpenClaw fails or shows EPERM"],
    "runtime_skill": ["OpenClaw fallback", "CF_Authorization", "EPERM", "CLAW_CF"],
    "scripts_skill": ["OpenClaw fallback", "python3 scripts/validation/openclaw_fallback_audit.py"],
    "validation_skill": ["openclaw_fallback_audit.py", "OpenClaw fallback"],
    "worker_ws_audit": ["openclaw worker ws audit", "CF_Authorization", "http://localhost:8088", "upstream WebSocket response directly"],
    "gw_transport_audit": ["gw connect transport audit", "falling back to direct browser-cookie WebSocket"],
    "gw_recover_compile_audit": ["gw recover compile audit", "private _uniqueId"],
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def probe_frame_findings(openclaw: str) -> list[str]:
    """Return static contract failures for the learner-visible probe iframe lifecycle."""
    findings: list[str] = []
    if not re.search(r"\.claw-html-frame\[hidden\]\s*\{\s*display\s*:\s*none\s*\}", openclaw):
        findings.append("web/nemoclaw/scripts/_openclaw.js lets .claw-html-frame display:block override the hidden lifecycle")
    hide_fn = re.search(r"function hideHtmlFrame\(clear = false\) \{([\s\S]*?)\n  \}", openclaw)
    if not hide_fn or "fr.hidden = true" not in hide_fn.group(1) or 'fr.removeAttribute("srcdoc")' not in hide_fn.group(1):
        findings.append("web/nemoclaw/scripts/_openclaw.js must hide the probe frame and clear srcdoc when requested")
    output_fn = re.search(r"function setOutput\(text, kind = \"\"\) \{([\s\S]*?)\n  \}\n\n  // Used by runAction", openclaw)
    if not output_fn or 'includes("HTML ·")' not in output_fn.group(1) or "hideHtmlFrame(true)" not in output_fn.group(1):
        findings.append("web/nemoclaw/scripts/_openclaw.js must clear the HTML frame before every non-HTML output")
    run_action = re.search(r"async function runAction\(action\) \{([\s\S]*?)\n  \}\n\n  actions\.forEach", openclaw)
    if not run_action:
        findings.append("web/nemoclaw/scripts/_openclaw.js missing probe runAction lifecycle")
    else:
        body = run_action.group(1)
        start = body.find("…in flight")
        clear = body.find("hideHtmlFrame(true)", start)
        fetch = body.find("await fetch", start)
        if min(start, clear, fetch) < 0 or not start < clear < fetch:
            findings.append("web/nemoclaw/scripts/_openclaw.js must clear stale HTML before the next probe request starts")
        access = re.search(r"if \(/cloudflareaccess[\s\S]*?\n\s*return;", body)
        if not access or "hideHtmlFrame(true)" not in access.group(0):
            findings.append("web/nemoclaw/scripts/_openclaw.js must clear stale HTML when Cloudflare Access returns a login page")
    return findings


def probe_frame_contract(openclaw: str) -> list[str]:
    """Mutate each protected edge and prove the static detector rejects it."""
    cases: list[tuple[str, str, str]] = [
        ("hidden CSS", openclaw.replace(".claw-html-frame[hidden]{display:none}", "", 1), "display:block override"),
        ("hidden flag", openclaw.replace("fr.hidden = true", "fr.hidden = false", 1), "must hide the probe frame"),
        ("srcdoc cleanup", openclaw.replace('fr.removeAttribute("srcdoc")', "void fr.srcdoc", 1), "must hide the probe frame"),
        ("non-HTML output", openclaw.replace('if (!String(text || "").includes("HTML ·")) hideHtmlFrame(true);', "", 1), "before every non-HTML output"),
    ]
    request_clear = "// Hide any previous HTML frame while a new request is in flight.\n    hideHtmlFrame(true);"
    cases.append(("request-start cleanup", openclaw.replace(request_clear, "// cleanup removed", 1), "before the next probe request"))
    access_start = openclaw.find("if (/cloudflareaccess")
    access_end = openclaw.find("return;", access_start)
    if access_start >= 0 and access_end >= 0:
        prefix, block, suffix = openclaw[:access_start], openclaw[access_start:access_end], openclaw[access_end:]
        cases.append(("access-warning cleanup", prefix + block.replace("hideHtmlFrame(true);", "", 1) + suffix, "Cloudflare Access"))
    misses = []
    for label, mutated, expected in cases:
        if not any(expected in finding for finding in probe_frame_findings(mutated)):
            misses.append(f"probe-frame detector missed {label}")
    return misses


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
    findings.extend(probe_frame_findings(openclaw))
    findings.extend(probe_frame_contract(openclaw))

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
        if "_uniqueId(" in decoded:
            findings.append("GW_CONNECT/recover cell code references private module helper _uniqueId; use local nextId")
    node = next((Path(c) for c in NODE_CANDIDATES if c and Path(c).exists()), None)
    if not node:
        findings.append("node runtime not found for openclaw_worker_ws_audit.mjs")
    else:
        node_env = os.environ.copy()
        if node.suffix.lower() != ".exe":
            writable_tmp = tempfile.gettempdir()
            node_env.update({"TMPDIR": writable_tmp, "TMP": writable_tmp, "TEMP": writable_tmp})
        for script_key in ("worker_ws_audit", "gw_transport_audit", "gw_recover_compile_audit"):
            proc = subprocess.run([str(node), str(FILES[script_key])], cwd=ROOT, env=node_env,
                                  text=True, capture_output=True)
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
