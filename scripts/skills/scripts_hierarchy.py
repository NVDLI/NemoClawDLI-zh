#!/usr/bin/env python3
"""Guardrail for the scripts/ hierarchy.

Root scripts keep compatibility entrypoints because existing commands use paths such as
`python3 scripts/validate_bundle.py` and `bash scripts/run_engine.sh`. Real implementations
belong in named subdirectories with their own SKILL.html beacon. This check catches drift in
both directions: a wrapper that no longer points at its implementation, or a new root-level
implementation that flattens the tree again.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"

GROUP_SKILLS = (
    "build", "compliance", "dev", "edx", "figures", "materials", "runtime", "security",
    "skills", "translate", "validation",
)

WRAPPERS = {
    "build_branch_manifest.py": "build/build_branch_manifest.py",
    "build_language_manifest.py": "build/build_language_manifest.py",
    "build_pages.sh": "build/build_pages.sh",
    "bundle_standalone.py": "build/bundle_standalone.py",
    "install-hooks.sh": "build/install-hooks.sh",
    "publish_edx.py": "build/publish_edx.py",
    "push_pages.sh": "build/push_pages.sh",
    "build_cli_readmes.py": "materials/build_cli_readmes.py",
    "build_rag_index.py": "materials/build_rag_index.py",
    "pull_materials.py": "materials/pull_materials.py",
    "vendor_glossary.py": "materials/vendor_glossary.py",
    "vendor_navigator.py": "materials/vendor_navigator.py",
    "source_gate.py": "compliance/source_gate.py",
    "engine.js": "runtime/engine.js",
    "link_graph.html": "runtime/link_graph.html",
    "link_projection.py": "runtime/link_projection.py",
    "module_check.py": "runtime/module_check.py",
    "render_check.py": "runtime/render_check.py",
    "run_engine.sh": "runtime/run_engine.sh",
    "run_node.sh": "runtime/run_node.sh",
    "test_page_runtime.js": "runtime/test_page_runtime.js",
    "lab_runtime_test.sh": "runtime/lab_runtime_test.sh",
    "check_figures.mjs": "figures/check_figures.mjs",
    "run_figcheck.sh": "figures/run_figcheck.sh",
    "edx_getting_started.html": "edx/edx_getting_started.html",
    "edx_navigator_quick.html": "edx/edx_navigator_quick.html",
    "gen_skill_hierarchy.py": "skills/gen_skill_hierarchy.py",
    "skill_audit.py": "skills/skill_audit.py",
    "skill_consistency.py": "skills/skill_consistency.py",
    "skill_contract.py": "skills/skill_contract.py",
    "scripts_hierarchy.py": "skills/scripts_hierarchy.py",
    "cell_audit.py": "validation/cell_audit.py",
    "code_hygiene.py": "validation/code_hygiene.py",
    "color_theme.py": "validation/color_theme.py",
    "figure_audit.py": "validation/figure_audit.py",
    "fix_comment_hygiene.py": "validation/fix_comment_hygiene.py",
    "grounding.py": "validation/grounding.py",
    "nb_audit.py": "validation/nb_audit.py",
    "prose_variety.py": "validation/prose_variety.py",
    "reference_graph.py": "validation/reference_graph.py",
    "tenets.py": "validation/tenets.py",
    "validate_bundle.py": "validation/validate_bundle.py",
    "validate_canvas_html.py": "validation/validate_canvas_html.py",
    "validate_layout.py": "validation/validate_layout.py",
    "push": "dev/push",
}

ROOT_ALLOW = {".gitkeep", "SKILL.html", "_bootstrap.py", *WRAPPERS}
SKIP_DIRS = {"__pycache__", ".figtools", "git-hooks", "grounding_cache"}
REQUIRED_RUNTIME_ASSETS = ("runtime/lab-runtime/Containerfile",)


def _ok_wrapper(name: str, target: str, text: str) -> bool:
    if name.endswith(".py"):
        module = target[:-3].replace("/", ".")
        return f'_importlib.import_module("{module}")' in text and f"scripts/{target}" in text
    if name.endswith((".js", ".mjs")):
        return f'import "./{target}"' in text and f"scripts/{target}" in text
    if name.endswith(".sh") or name == "push":
        return target in text and "Compatibility entrypoint" in text
    if name.endswith(".html"):
        return target in text and "Moved to scripts/" in text
    return False


def findings() -> list[str]:
    out: list[str] = []
    for dirname in GROUP_SKILLS:
        if not (SCRIPTS / dirname / "SKILL.html").is_file():
            out.append(f"missing scripts/{dirname}/SKILL.html")
    for rel in REQUIRED_RUNTIME_ASSETS:
        if not (SCRIPTS / rel).is_file():
            out.append(f"missing required runtime asset scripts/{rel}")
    for root_name, target in sorted(WRAPPERS.items()):
        root = SCRIPTS / root_name
        impl = SCRIPTS / target
        if not impl.exists():
            out.append(f"missing implementation scripts/{target}")
            continue
        if not root.exists():
            out.append(f"missing root compatibility entrypoint scripts/{root_name}")
            continue
        try:
            text = root.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            out.append(f"root entrypoint scripts/{root_name} is not UTF-8 text")
            continue
        if not _ok_wrapper(root_name, target, text):
            out.append(f"root entrypoint scripts/{root_name} does not point cleanly at scripts/{target}")
    for p in SCRIPTS.iterdir():
        if p.is_dir():
            if p.name not in GROUP_SKILLS and p.name not in SKIP_DIRS:
                out.append(f"unexpected root scripts/ directory {p.name}; add a SKILL.html or classify it")
            continue
        if p.name not in ROOT_ALLOW:
            out.append(f"unexpected root scripts/ file {p.name}; move implementation into a subdirectory or add an explicit wrapper contract")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="validate scripts/ hierarchy")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rows = findings()
    if args.json:
        print(json.dumps({"findings": rows}, indent=2))
    elif rows:
        print("scripts_hierarchy: FAIL")
        for row in rows:
            print(f"  - {row}")
    else:
        print("scripts_hierarchy: OK")
    return 1 if rows else 0


if __name__ == "__main__":
    raise SystemExit(main())
