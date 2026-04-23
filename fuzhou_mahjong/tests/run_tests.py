"""Zero-dependency test runner: collects test_* functions and executes them.

Usable when pytest isn't installed.  On the user's machine, `pytest` works
identically because all tests use plain `assert`.

    python -m fuzhou_mahjong.tests.run_tests
"""
from __future__ import annotations

import importlib
import pkgutil
import sys
import traceback
from typing import List, Tuple


def discover() -> List[Tuple[str, callable]]:
    """Return (dotted_name, fn) tuples for every test_* function found."""
    from fuzhou_mahjong import tests as test_pkg
    out: List[Tuple[str, callable]] = []
    for mi in pkgutil.iter_modules(test_pkg.__path__):
        if not mi.name.startswith("test_"):
            continue
        mod = importlib.import_module(f"fuzhou_mahjong.tests.{mi.name}")
        for attr in dir(mod):
            if not attr.startswith("test_"):
                continue
            fn = getattr(mod, attr)
            if callable(fn):
                out.append((f"{mi.name}.{attr}", fn))
    return out


def main() -> int:
    tests = discover()
    n_pass = 0
    failures: List[Tuple[str, str]] = []
    for name, fn in tests:
        try:
            fn()
        except AssertionError as e:
            failures.append((name, f"AssertionError: {e}\n{traceback.format_exc()}"))
            print(f"  FAIL  {name}")
        except Exception as e:
            failures.append((name, f"{type(e).__name__}: {e}\n{traceback.format_exc()}"))
            print(f"  ERR   {name}")
        else:
            n_pass += 1
            print(f"  ok    {name}")
    print(f"\n{n_pass}/{len(tests)} passed")
    if failures:
        print("\n--- Failures ---")
        for name, msg in failures:
            print(f"\n* {name}\n{msg}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
