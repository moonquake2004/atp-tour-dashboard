#!/usr/bin/env python3
"""
Compare the Python pipeline output against the Node implementation it replaces.

Both pipelines write the same snapshots, so a structural comparison of every
file is direct evidence that the port is faithful.  Floats are compared with a
small tolerance (the two languages round differently) and object key order is
ignored, but every key, value and list length must match.

    python3 pyscripts/compare_outputs.py <old-data-dir> <new-data-dir>
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

TOLERANCE = 0.02

# Fields that record when the build ran rather than what it found; a Python and a
# Node build can never agree on these and they carry no meaning for comparison.
VOLATILE = {"generatedAt", "lastUpdated"}


def diff(path: str, a, b, out: list[str], limit: int = 12) -> None:
    """Collect the first few differences between two parsed snapshots."""
    if len(out) >= limit:
        return
    if type(a) is not type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        out.append(f"{path}: type {type(a).__name__} vs {type(b).__name__}")
        return

    if isinstance(a, dict):
        for key in sorted(set(a) | set(b)):
            if key in VOLATILE:
                continue
            if key not in a:
                out.append(f"{path}.{key}: missing in old")
            elif key not in b:
                out.append(f"{path}.{key}: missing in new")
            else:
                diff(f"{path}.{key}", a[key], b[key], out, limit)
            if len(out) >= limit:
                return
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append(f"{path}: length {len(a)} vs {len(b)}")
            return
        for index, (x, y) in enumerate(zip(a, b)):
            diff(f"{path}[{index}]", x, y, out, limit)
            if len(out) >= limit:
                return
    elif isinstance(a, float) or isinstance(b, float):
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            out.append(f"{path}: {a!r} vs {b!r}")
        elif not math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=TOLERANCE):
            out.append(f"{path}: {a} vs {b}")
    elif a != b:
        out.append(f"{path}: {a!r} vs {b!r}")


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    old_dir, new_dir = Path(sys.argv[1]), Path(sys.argv[2])

    files = sorted(p.name for p in old_dir.glob("*.json"))
    failures = 0

    print(f"Comparing {len(files)} snapshots: {old_dir} → {new_dir}\n")
    for name in files:
        new_path = new_dir / name
        if not new_path.exists():
            print(f"  ✗ {name}: missing in the new output")
            failures += 1
            continue

        with (old_dir / name).open(encoding="utf-8") as handle:
            old = json.load(handle)
        with new_path.open(encoding="utf-8") as handle:
            new = json.load(handle)

        problems: list[str] = []
        diff("$", old, new, problems)
        if problems:
            failures += 1
            print(f"  ✗ {name}  ({len(problems)}+ differences)")
            for line in problems:
                print(f"      {line}")
        else:
            size_old = (old_dir / name).stat().st_size
            size_new = new_path.stat().st_size
            print(f"  ✓ {name}  ({size_old / 1024:.0f} KB → {size_new / 1024:.0f} KB)")

    print()
    if failures:
        print(f"✗ {failures}/{len(files)} snapshots differ")
        return 1
    print(f"✓ All {len(files)} snapshots match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
