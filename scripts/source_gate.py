#!/usr/bin/env python3
"""Compatibility entrypoint for scripts/source_gate.py. Implementation lives in scripts/compliance/source_gate.py."""

if __name__ == "__main__":
    import runpy as _runpy
    _runpy.run_module("compliance.source_gate", run_name="__main__")
else:
    import importlib as _importlib

    _impl = _importlib.import_module("compliance.source_gate")
    _exported = {
        _name: getattr(_impl, _name)
        for _name in dir(_impl)
        if _name not in {"__builtins__", "__cached__", "__loader__", "__name__", "__package__", "__spec__"}
    }
    globals().update(_exported)
