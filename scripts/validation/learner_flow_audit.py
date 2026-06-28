#!/usr/bin/env python3
"""Required static contract for progressive disclosure and interactive lab state.

The gate stays course-agnostic: it discovers course directories from course SKILL
beacons and checks shared interaction primitives plus each numbered lesson. It does
not infer GPU availability or hard-code one delivery environment.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

for _p in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
    if (_p / "scripts" / "_bootstrap.py").exists():
        sys.path.insert(0, str(_p / "scripts"))
        break
from _bootstrap import find_repo_root

ROOT = find_repo_root(Path(__file__).resolve())
WEB = ROOT / "web"
CODE_RE = re.compile(r"code:\s*`((?:\\.|[^`\\])*)`", re.S)
MOUNT_RE = re.compile(r"mount(?:RunCell|CanvasFlow)\s*\(")
LAUNCHABLE_HELPER_RE = re.compile(
    r"helpers\.(?:openclawChat|terminal|sandboxExec|policyGet|sandboxNetwork|evalSandboxNetwork|evalSandboxFs)\b"
)
MODEL_HELPER_RE = re.compile(r"(?:helpers\.)?(?:chat|chatStream)\s*\(|helpers\.mountAgentChat\s*\(")
MAX_DEFAULT_OPEN_LINES = 60


def _need(findings: list[str], ok: bool, message: str) -> None:
    if not ok:
        findings.append(message)


def audit_runtime_sources(canvas: str, chat: str) -> list[str]:
    """Check behavior-bearing shared primitives, not page-specific CSS selectors."""
    findings: list[str] = []
    canvas_contract = {
        'class="cf-intro rc-intro"': "RunCell must render its focus-driving intro before implementation details",
        'class="rc-out cell-output-panel" role="status"': "RunCell output must be a programmatic status region",
        '_emptyState("⏹ stopped")': "RunCell Stop must leave an explicit stopped state",
        'if (codeDet && !codeDet.open) codeDet.open = true;': "RunCell errors must reveal code even without CodeMirror",
        '_cellBtnHTML("reset", "↺ Reset", "rc-reset"': "RunCell must expose Reset",
        'btn.textContent = "⏹ Stop"': "RunCell Run must become Stop while work is active",
        '_cellBtnHTML("reset", "↺ Reset code", "cf-btn cf-btn-reset"': "CanvasFlow must expose whole-flow Reset",
        'b.textContent = "⏹ Stop"': "CanvasFlow Run all must become Stop while work is active",
        'resultsDet.open = true': "CanvasFlow must reveal results when a node runs",
        'class="cf-status-bar" role="status"': "CanvasFlow completion state must be a programmatic status region",
        "running = false, runEpoch = 0": "CanvasFlow resets must invalidate stale async completion",
        "const epoch = ++runEpoch;": "RunCell resets must invalidate stale async completion",
    }
    for token, message in canvas_contract.items():
        _need(findings, token in canvas, message)
    error_scope = canvas.find("const _rcCode = cm ? cm.getValue() : ta.value;")
    open_error = canvas.find("if (codeDet && !codeDet.open) codeDet.open = true;", error_scope)
    cm_only = canvas.find("if (_ep !== null && cm)", error_scope)
    _need(findings, error_scope >= 0 and open_error > error_scope and cm_only > open_error,
          "RunCell errors must reveal code before the CodeMirror-only line marker")
    _need(findings, "out.scrollIntoView" not in canvas,
          "RunCell must not move the page viewport after Run")

    chat_contract = {
        'class="chatui-state" role="status"': "chat readiness/run/error state must be programmatically visible",
        "const setDisabled = (blocked": "chat artifacts need a reusable prerequisite gate",
        'sendBtn.textContent = "⏹ Stop"': "chat Send must become Stop while work is active",
        'button class="chatui-reset"': "chat artifacts must expose New chat/Reset",
        'setState("Error. Read the message, then edit or retry."': "chat errors need a stable visible state",
        'class="da-console-state" role="status"': "console readiness/run/error state must be programmatically visible",
        'class="da-chip da-stop"': "console commands must expose Stop",
        'runAC = new AbortController()': "console Stop must own an AbortController",
        'onSubmit(line, con, { signal: runAC.signal })': "console commands must receive the Stop signal",
        'class="da-chip da-clear"': "console commands must expose Clear",
        "resetEpoch = 0": "chat Reset must invalidate stale async completion",
    }
    for token, message in chat_contract.items():
        _need(findings, token in chat, message)
    _need(findings, "input.scrollIntoView" not in chat,
          "console completion must not move the page viewport")
    return findings


def _mount_blocks(text: str) -> list[tuple[int, str, bool]]:
    mounts = list(MOUNT_RE.finditer(text))
    blocks: list[tuple[int, str, bool]] = []
    for index, mount in enumerate(mounts):
        end = mounts[index + 1].start() if index + 1 < len(mounts) else len(text)
        blocks.append((mount.start(), text[mount.start():end], text.startswith("mountRunCell", mount.start())))
    return blocks


def audit_lesson(path: Path, text: str) -> list[str]:
    findings: list[str] = []
    rel = path.relative_to(ROOT).as_posix()
    blocks = _mount_blocks(text)
    model_call = MODEL_HELPER_RE.search(text)
    if model_call:
        model_markers = [text.find('id="key-status"'), text.find('data-prerequisite="model"')]
        _need(findings, any(0 <= marker < model_call.start() for marker in model_markers),
              f"{rel}: model-dependent lesson must expose model readiness before use")

    if LAUNCHABLE_HELPER_RE.search(text):
        first_call = LAUNCHABLE_HELPER_RE.search(text).start()
        launchable_markers = [text.find('id="claw-status"'), text.find('data-prerequisite="launchable"')]
        _need(findings, any(0 <= marker < first_call for marker in launchable_markers),
              f"{rel}: launchable-dependent lesson must expose launchable readiness before use")
        _need(findings, "03a-kickstart.html" in text,
              f"{rel}: launchable-dependent lesson must link its setup path to Module 3a")

    for start, block, is_run_cell in blocks:
        if not is_run_cell:
            continue
        line = text[:start].count("\n") + 1
        code_match = CODE_RE.search(block)
        if not code_match:
            findings.append(f"{rel}:{line}: RunCell has no inspectable code literal")
            continue
        code = code_match.group(1)
        options = block[:code_match.start()]
        _need(findings, bool(re.search(r"\blabel\s*:\s*[\"']", options)),
              f"{rel}:{line}: RunCell needs a learner-facing label")
        if re.search(r"\bopenCode\s*:\s*true\b", options):
            lines = code.count("\n") + 1
            _need(findings, lines <= MAX_DEFAULT_OPEN_LINES,
                  f"{rel}:{line}: default-open implementation has {lines} lines; limit is {MAX_DEFAULT_OPEN_LINES}")
            _need(findings, bool(re.search(r"\bintro\s*:\s*[\"']", options)),
                  f"{rel}:{line}: default-open implementation needs a focus-driving intro")

        mounts_live_artifact = "helpers.mountChatUI" in code or "helpers.mountAgentChat" in code or "helpers.mountConsole" in code
        uses_launchable = bool(LAUNCHABLE_HELPER_RE.search(code))
        if mounts_live_artifact and uses_launchable:
            _need(findings, bool(re.search(r"\bdisabled\s*:", code)),
                  f"{rel}:{line}: launchable artifact must disable input until its prerequisite is ready")
            _need(findings, bool(re.search(r"\bdisabledMsg\s*:", code)),
                  f"{rel}:{line}: disabled launchable artifact must explain how to become ready")
            _need(findings, "signal: ctx.signal" in code,
                  f"{rel}:{line}: launchable artifact must pass its Stop signal into long-running helpers")
    return findings


def course_dirs() -> list[Path]:
    dirs = []
    for skill in WEB.glob("*/SKILL.html"):
        if '"schema": "course-skill/' in skill.read_text(encoding="utf-8", errors="ignore"):
            dirs.append(skill.parent)
    return sorted(dirs)


def audit_home(text: str) -> list[str]:
    findings: list[str] = []
    _need(findings, "CPU-based" in text and "do not require a learner-managed GPU" in text,
          "web/nemoclaw/index.html: setup must state the CPU baseline and that learner-managed GPU hardware is not required")
    return findings


def audit_workflow_wiring(gitlab: str, github: str, pre_push: str, bundle: str) -> list[str]:
    findings: list[str] = []
    self_test = "python3 scripts/validation/learner_flow_audit.py --self-test"
    _need(findings, self_test in gitlab,
          ".gitlab-ci.yml: required test job must run learner-flow mutation tests")
    _need(findings, self_test in github,
          ".github/workflows/pages.yml: Pages test job must run learner-flow mutation tests")
    _need(findings, "learner_flow_audit.py\" --self-test" in pre_push,
          "scripts/git-hooks/pre-push: local push gate must run learner-flow mutation tests")
    _need(findings, "import learner_flow_audit as lfa" in bundle and
          '("learner_flow", "Learner interaction flow", "required"' in bundle and
          "learner_flow_find = lfa.audit_tree()" in bundle,
          "scripts/validation/validate_bundle.py: learner-flow audit must remain a required release suite")
    return findings


def audit_tree(root: Path = ROOT) -> list[str]:
    findings = audit_runtime_sources(
        (root / "web/nemoclaw/scripts/_canvas.js").read_text(encoding="utf-8"),
        (root / "web/nemoclaw/scripts/_chat.js").read_text(encoding="utf-8"),
    )
    discovered = course_dirs() if root == ROOT else []
    for course in discovered:
        for page in sorted(course.glob("0*.html")):
            findings.extend(audit_lesson(page, page.read_text(encoding="utf-8")))
    home = (root / "web/nemoclaw/index.html").read_text(encoding="utf-8")
    findings.extend(audit_home(home))
    findings.extend(audit_workflow_wiring(
        (root / ".gitlab-ci.yml").read_text(encoding="utf-8"),
        (root / ".github/workflows/pages.yml").read_text(encoding="utf-8"),
        (root / "scripts/git-hooks/pre-push").read_text(encoding="utf-8"),
        (root / "scripts/validation/validate_bundle.py").read_text(encoding="utf-8"),
    ))
    return findings


def self_test() -> list[str]:
    """Mutation tests prove each high-risk rule detects the regression it names."""
    misses: list[str] = []
    canvas = (ROOT / "web/nemoclaw/scripts/_canvas.js").read_text(encoding="utf-8")
    chat = (ROOT / "web/nemoclaw/scripts/_chat.js").read_text(encoding="utf-8")
    runtime_mutations = [
        ("ignored RunCell intro", canvas.replace('class="cf-intro rc-intro"', 'class="rc-intro"', 1), chat, "focus-driving intro"),
        ("blank RunCell stop", canvas.replace('_emptyState("⏹ stopped")', 'out.innerHTML = ""', 1), chat, "explicit stopped state"),
        ("console auto-scroll", canvas, chat.replace('input.focus();', 'input.focus(); input.scrollIntoView();', 1), "must not move"),
        ("missing chat prerequisite gate", canvas, chat.replace("const setDisabled = (blocked", "const ignoreDisabled = (blocked", 1), "prerequisite gate"),
        ("missing chat reset epoch", canvas, chat.replace("resetEpoch = 0", "resetEpochMissing = 0", 1), "stale async completion"),
    ]
    for label, mutated_canvas, mutated_chat, expected in runtime_mutations:
        if not any(expected in finding for finding in audit_runtime_sources(mutated_canvas, mutated_chat)):
            misses.append(f"detector missed {label}")

    page_path = ROOT / "web/nemoclaw/03b-openclaw.html"
    page = page_path.read_text(encoding="utf-8")
    page_cases = [
        ("missing launchable status", page.replace('id="claw-status"', 'id="removed-claw-status"', 1), "launchable readiness"),
        ("enabled-before-ready chat", re.sub(r"\n\s*disabled:\s*\(\)\s*=>[^\n]+", "", page, count=1), "disable input"),
        ("missing stop signal", page.replace("signal: ctx.signal", "signal: null", 1), "Stop signal"),
    ]
    for label, mutated, expected in page_cases:
        if not any(expected in finding for finding in audit_lesson(page_path, mutated)):
            misses.append(f"detector missed {label}")

    heavy_path = ROOT / "web/nemoclaw/04b-modern-clis.html"
    heavy = heavy_path.read_text(encoding="utf-8")
    heavy = heavy.replace('mountRunCell("#cell-jsagent", {\n      openCode: false,', 'mountRunCell("#cell-jsagent", {\n      openCode: true,', 1)
    if not any("default-open implementation" in finding for finding in audit_lesson(heavy_path, heavy)):
        misses.append("detector missed oversized default-open implementation")

    home = (ROOT / "web/nemoclaw/index.html").read_text(encoding="utf-8")
    broken = home.replace("CPU-based", "unspecified", 1)
    if not any("CPU baseline" in finding for finding in audit_home(broken)):
        misses.append("detector missed missing CPU baseline")

    gitlab = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
    github = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
    pre_push = (ROOT / "scripts/git-hooks/pre-push").read_text(encoding="utf-8")
    bundle = (ROOT / "scripts/validation/validate_bundle.py").read_text(encoding="utf-8")
    broken_gitlab = gitlab.replace("python3 scripts/validation/learner_flow_audit.py --self-test", "echo skipped", 1)
    if not any(".gitlab-ci.yml" in finding for finding in audit_workflow_wiring(broken_gitlab, github, pre_push, bundle)):
        misses.append("detector missed missing GitLab learner-flow wiring")
    return misses


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    findings = self_test() if args.self_test else audit_tree()
    if findings:
        print("learner_flow_audit: FAIL")
        for finding in findings:
            print(f"  - {finding}")
        return 1
    print("learner_flow_audit: OK" + (" (mutation self-test)" if args.self_test else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
