## Summary

What changed and why?

## Issue link

Addresses #

## Current release target

- Course: `web/nemoclaw/` unless this is bundle-wide
- Runtime: CPU service stack (`cpu/`, `workspace/`, `deploy/`) unless stated otherwise
- Bundle scope: course-specific or bundle-wide

## Surfaces touched

- [ ] `web/`
- [ ] `cpu/`
- [ ] `deploy/`
- [ ] `scripts/`
- [ ] `docs/`
- [ ] `materials/source governance`

## Blast radius checked

Describe related files, generated beacons, docs, validators, and runtime paths checked.

## Validation

- [ ] `python3 scripts/validation/validate_layout.py --quiet`
- [ ] `python3 scripts/skills/skill_consistency.py`
- [ ] `python3 scripts/skills/skill_contract.py`
- [ ] `python3 scripts/compliance/source_gate.py`
- [ ] `bash scripts/runtime/run_engine.sh --self-test`
- [ ] `python3 scripts/validation/validate_bundle.py --scope ship`
- [ ] Browser/runtime check, if page JS, Studio, OpenClaw, or runnable cells changed
- [ ] Build check, if navigation, deploy path, or Pages output changed

## Release notes

Learner-facing:

Runtime/deploy:

Governance/process:

## Risk

What could regress? What remains out of scope?
