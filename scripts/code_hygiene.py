#!/usr/bin/env python3
"""Compatibility entrypoint for scripts/code_hygiene.py. Implementation lives in scripts/validation/code_hygiene.py."""
import importlib as _importlib

_impl = _importlib.import_module("validation.code_hygiene")
_exported = {
    _name: getattr(_impl, _name)
    for _name in dir(_impl)
    if _name not in {"__builtins__", "__cached__", "__loader__", "__name__", "__package__", "__spec__"}
}
globals().update(_exported)

if __name__ == "__main__":
    _main = getattr(_impl, "main", None)
    if _main is None:
        raise SystemExit("scripts/validation/code_hygiene.py has no main() entrypoint")
    raise SystemExit(_main())
