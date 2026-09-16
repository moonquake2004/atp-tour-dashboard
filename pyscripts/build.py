#!/usr/bin/env python3
"""
One-shot data build: refresh every snapshot from the official WTA API and
regenerate the derived aggregates and the published site.

    python3 pyscripts/build.py                    # full refresh
    python3 pyscripts/build.py --skip-players --skip-matches
    WTA_RANK_DEPTH=100 python3 pyscripts/build.py
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from wtalib import ROOT, log

STEPS = [
    ("rankings", "fetch_rankings.py", False),
    ("players", "fetch_players.py", True),
    ("matches", "fetch_matches.py", True),
    ("tournaments", "fetch_tournaments.py", True),
    ("event-results", "fetch_events.py", True),
    ("h2h", "fetch_h2h.py", False),
    ("derive", "derive.py", False),
    ("compact", "compact.py", False),
    ("zh", "fetch_zh.py", True),
    ("dashboard-data", "generate_data.py", False),
    ("dashboard-site", "build_site.py", False),
    ("verify-dashboard", "verify_dashboard.py", False),
    ("check-links", "check_links.py", False),
]


def main() -> int:
    args = set(sys.argv[1:])
    started = time.time()
    here = Path(__file__).resolve().parent

    for name, script, skippable in STEPS:
        if skippable and f"--skip-{name.split('-')[0]}s" in args:
            log(name, f"skipped ({script})")
            continue
        print("\n" + "─" * 64 + f"\n▶ {script}\n" + "─" * 64, flush=True)
        code = subprocess.run([sys.executable, str(here / script)], cwd=ROOT).returncode
        if code != 0:
            print(f"\n✗ {script} exited with code {code} — stopping.")
            return code

    print("\n" + "─" * 64)
    print(f"✓ Build complete in {time.time() - started:.1f}s")
    print("─" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
