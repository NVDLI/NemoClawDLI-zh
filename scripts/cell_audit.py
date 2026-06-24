#!/usr/bin/env python3
"""Compatibility entrypoint for scripts/cell_audit.py. Implementation lives in scripts/validation/cell_audit.py."""
import importlib as _importlib

_impl = _importlib.import_module("validation.cell_audit")
_exported = {
    _name: getattr(_impl, _name)
    for _name in dir(_impl)
    if _name not in {"__builtins__", "__cached__", "__loader__", "__name__", "__package__", "__spec__"}
}
globals().update(_exported)

if __name__ == "__main__":
    _main = getattr(_impl, "main", None)
    if _main is None:
        raise SystemExit("scripts/validation/cell_audit.py has no main() entrypoint")
    raise SystemExit(_main())
