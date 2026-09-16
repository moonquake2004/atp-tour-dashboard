#!/usr/bin/env python3
"""
Light weekly refresh: rankings only.

Rankings are published on Mondays, so a refresh needs the ranking table plus the
derived aggregates and the rebuilt site.  Everything else changes slowly and is
handled by ``build.py``.

    python3 pyscripts/refresh_rankings.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from wtalib import ROOT, log

STEPS = [
    "fetch_rankings.py",
    "fetch_events.py",   # completed events gain champions and results weekly
    "derive.py",
    "fetch_zh.py",       # newly ranked players need Chinese names
    "generate_data.py",
    "build_site.py",
    "verify_dashboard.py",
]


def main() -> int:
    here = Path(__file__).resolve().parent
    for script in STEPS:
        log(script, "running…")
        code = subprocess.run([sys.executable, str(here / script)], cwd=ROOT).returncode
        if code != 0:
            return code
    log("refresh", "Rankings refreshed and the site rebuilt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
