#!/usr/bin/env python3
"""
Weekly refresh: the whole pipeline with weekly-appropriate depth.

This used to run a "light" list of its own — rankings, draws, derive, site — which
silently skipped the calendar and the day-by-day results crawl.  The published
feed then froze at whatever day that crawl had last been run, so the site kept
showing last month's matches while the ranking table stayed current.

Rather than keep a second step list that can drift, this now runs build.py with
the environment the weekly schedule needs:

  ATP_PLAYER_REFRESH=1   player profiles are otherwise fetched once and kept, so
                         their season W/L and title counts never move
  ATP_RESULT_SEASONS=1   keep the published dataset at the current season, which
                         is what the pages are built against
  ATP_PLAYER_WORKERS=4   a full profile refresh is the slowest step

    python3 pyscripts/refresh_rankings.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from wtalib import ROOT, log

WEEKLY_ENV = {
    "ATP_PLAYER_REFRESH": "1",
    "ATP_RESULT_SEASONS": "1",
    "ATP_PLAYER_WORKERS": "4",
}


def main() -> int:
    here = Path(__file__).resolve().parent
    env = {**os.environ, **WEEKLY_ENV}
    log("refresh", "weekly refresh → build.py " + " ".join(f"{k}={v}" for k, v in WEEKLY_ENV.items()))
    code = subprocess.run([sys.executable, str(here / "build.py")], cwd=ROOT, env=env).returncode
    if code != 0:
        return code
    log("refresh", "Weekly refresh complete — calendar, results, profiles and the site are current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
