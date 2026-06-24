#!/usr/bin/env python3
"""Compatibility entrypoint for scripts/skill_consistency.py. Implementation lives in scripts/skills/skill_consistency.py."""
import importlib as _importlib

_impl = _importlib.import_module("skills.skill_consistency")
_exported = {
    _name: getattr(_impl, _name)
    for _name in dir(_impl)
    if _name not in {"__builtins__", "__cached__", "__loader__", "__name__", "__package__", "__spec__"}
}
globals().update(_exported)

if __name__ == "__main__":
    _main = getattr(_impl, "main", None)
    if _main is None:
        raise SystemExit("scripts/skills/skill_consistency.py has no main() entrypoint")
    raise SystemExit(_main())
