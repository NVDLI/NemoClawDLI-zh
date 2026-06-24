#!/usr/bin/env python3
"""Compatibility entrypoint for scripts/gen_skill_hierarchy.py. Implementation lives in scripts/skills/gen_skill_hierarchy.py."""

if __name__ == "__main__":
    import runpy as _runpy
    _runpy.run_module("skills.gen_skill_hierarchy", run_name="__main__")
else:
    import importlib as _importlib

    _impl = _importlib.import_module("skills.gen_skill_hierarchy")
    _exported = {
        _name: getattr(_impl, _name)
        for _name in dir(_impl)
        if _name not in {"__builtins__", "__cached__", "__loader__", "__name__", "__package__", "__spec__"}
    }
    globals().update(_exported)
