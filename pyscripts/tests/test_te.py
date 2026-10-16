#!/usr/bin/env python3
"""
Snapshot regression tests for the te.py HTML parsers.

The upstream site (tennisexplorer.com) is server-rendered HTML and can change
its markup without notice.  These tests pin the parsers against constructed
fragments that mirror the current markup, so a silent upstream change breaks
the build loudly instead of corrupting the data.

Run:  python3 -m unittest discover -s pyscripts/tests -v
"""

from __future__ import annotations

import os
import sys
import unittest

# Make ``import te`` and ``from wtalib import ...`` work from the tests dir.
_PYSCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PYSCRIPTS not in sys.path:
    sys.path.insert(0, _PYSCRIPTS)

import te  # noqa: E402
from wtalib import score_text  # noqa: E402


RANK_HTML = """
<table>
  <tr class="head"><th colspan="5">Player name</th></tr>
  <tr>
    <td class="rank first">1.</td>
    <td class="prevrank"><div class="oup">13</div></td>
    <td class="t-name"><a href="/player/sinner-8b8e8/">Sinner Jannik</a></td>
    <td class="tl"><span class="fl fl-it"></span>Italy</td>
    <td class="long-point">11,500</td>
  </tr>
  <tr>
    <td class="rank">2.</td>
    <td class="prevrank"><div class="odown">2</div></td>
    <td class="t-name"><a href="/player/alcaraz-carlitos/">Alcaraz Carlos</a></td>
    <td class="tl"><span class="fl fl-es"></span>Spain</td>
    <td class="long-point">9,010</td>
  </tr>
</table>
"""

DETAIL_HTML = """
<table class="plDetail">
  <tr><td><img src="/res/img/player/sinner-8b8e8/5d24.jpg" alt=""></td></tr>
  <tr><td>Sinner Jannik Country: Italy Height / Weight: 188 cm / 76 kg
      Age: 25 (16. 8. 2001) Current/Highest rank - singles: 1. / 1.
      Current/Highest rank - doubles: - / 34. Sex: man Plays: right</td></tr>
</table>
"""

RESULTS_HTML = """
<table class="result">
  <tr class="head flags">
    <td class="t-name"><a href="/results/event-biella-challenger/">
      <span class="fl fl-it"></span>Biella Challenger</a></td>
  </tr>
  <tr id="s10">
    <td class="first time">17.09. 12:00</td>
    <td class="t-name"><a href="/player/sinner-8b8e8/">Sinner Jannik</a></td>
    <td class="result">3</td>
    <td class="score">6</td>
    <td class="score">7<sup>4</sup></td>
    <td class="score">6</td>
  </tr>
  <tr id="s10b">
    <td class="first time">17.09. 12:00</td>
    <td class="t-name"><a href="/player/zhizhen-z/">Zhang Zhizhen</a></td>
    <td class="result">1</td>
    <td class="score">3</td>
    <td class="score">6<sup>4</sup></td>
    <td class="score">1</td>
  </tr>
</table>
"""

BALANCE_HTML = """
<table class="result">
  <tr class="head"><th>Year</th><th>Summary</th><th>Clay</th><th>Hard</th>
      <th>Indoors</th><th>Grass</th><th>Not set</th></tr>
  <tr><td>Summary:</td><td>465/138</td><td>125/38</td><td>210/62</td>
      <td>75/22</td><td>55/16</td><td>0/0</td></tr>
  <tr><td>2025</td><td>73/6</td><td>14/2</td><td>42/3</td>
      <td>12/1</td><td>5/0</td><td>0/0</td></tr>
  <tr><td>2024</td><td>69/6</td><td>16/1</td><td>38/4</td>
      <td>9/1</td><td>6/0</td><td>0/0</td></tr>
</table>
"""


class TestParseRankings(unittest.TestCase):
    def test_parses_rank_and_meta(self):
        rows = te.parse_rankings(RANK_HTML)
        self.assertEqual(len(rows), 2)

        top = rows[0]
        self.assertEqual(top["rank"], 1)
        self.assertEqual(top["id"], "sinner-8b8e8")
        self.assertEqual(top["slug"], "sinner")  # display slug drops the trailing id hash
        self.assertEqual(top["name"], "Jannik Sinner")  # surname-first → given-first
        self.assertEqual(top["country"], "Italy")
        self.assertEqual(top["flag"], "IT")
        self.assertEqual(top["points"], 11500)
        self.assertEqual(top["move"], 13)
        self.assertEqual(top["moveDir"], "up")

        second = rows[1]
        self.assertEqual(second["rank"], 2)
        self.assertEqual(second["move"], -2)
        self.assertEqual(second["moveDir"], "down")

    def test_empty_doc_returns_empty(self):
        self.assertEqual(te.parse_rankings("<html></html>"), [])


class TestParsePlayerDetail(unittest.TestCase):
    def test_parses_career_fields(self):
        out = te.parse_player_detail(DETAIL_HTML)
        self.assertEqual(out["country"], "Italy")
        self.assertEqual(out["height"], 188)
        self.assertEqual(out["weight"], 76)
        self.assertEqual(out["age"], 25)
        self.assertEqual(out["birth"], "2001-08-16")
        self.assertEqual(out["rank"], 1)
        self.assertEqual(out["highRank"], 1)
        self.assertEqual(out["highRankDoubles"], 34)
        self.assertEqual(out["hand"], "Right")
        self.assertTrue(out["photo"].startswith("/res/img/player/"))

    def test_missing_table_returns_empty(self):
        self.assertEqual(te.parse_player_detail("<html></html>"), {})


class TestParseResultsDay(unittest.TestCase):
    def test_pairs_winner_loser_with_tiebreak_score(self):
        out = te.parse_results_day(RESULTS_HTML)
        self.assertEqual(set(out["tournaments"]), {"/results/event-biella-challenger/"})

        event = out["tournaments"]["/results/event-biella-challenger/"]
        self.assertEqual(event["name"], "Biella Challenger")
        self.assertEqual(event["flag"], "IT")
        self.assertEqual(event["matches"], 1)

        self.assertEqual(len(out["matches"]), 1)
        match = out["matches"][0]
        self.assertEqual(match["winner"]["id"], "sinner-8b8e8")
        self.assertEqual(match["loser"]["id"], "zhizhen-z")
        self.assertEqual(match["sets"], 3)
        self.assertEqual(match["score"], ["6-3", "7-6(4)", "6-1"])

    def test_empty_doc_is_benign(self):
        out = te.parse_results_day("<html></html>")
        self.assertEqual(out["tournaments"], {})
        self.assertEqual(out["matches"], [])


class TestBuildScore(unittest.TestCase):
    def test_tiebreak_pairs(self):
        winner = [{"g": "6", "tb": None}, {"g": "7", "tb": "5"}, {"g": "6", "tb": None}]
        loser = [{"g": "7", "tb": "5"}, {"g": "6", "tb": None}, {"g": "3", "tb": None}]
        self.assertEqual(te._build_score(winner, loser), ["6-7(5)", "7-6(5)", "6-3"])

    def test_degraded_short_sets_keeps_winner_games(self):
        winner = [{"g": "6", "tb": None}]
        self.assertEqual(te._build_score(winner, []), ["6"])

    def test_mismatched_length_falls_back(self):
        winner = [{"g": "6", "tb": None}, {"g": "6", "tb": None}]
        loser = [{"g": "4", "tb": None}]
        self.assertEqual(te._build_score(winner, loser), ["6", "6"])


class TestScoreText(unittest.TestCase):
    def test_score_text_examples(self):
        # Pairs already paired by _build_score pass through unchanged.
        self.assertEqual(score_text(["6-3", "7-6(4)", "6-1"]), "6-3 7-6(4) 6-1")
        # Dict shape: each set joined, tiebreak in parens (unpaired cells).
        self.assertEqual(
            score_text([{"g": "6", "tb": None}, {"g": "7", "tb": "4"}]),
            "6 7(4)",
        )
        # Older snapshot kept plain winner games — joined as stored.
        self.assertEqual(score_text(["6", "6"]), "6 6")
        # Missing / empty.
        self.assertEqual(score_text(None), "—")
        self.assertEqual(score_text([]), "—")
        # Strings pass through untouched.
        self.assertEqual(score_text("6-7(5) 6-3"), "6-7(5) 6-3")


class TestParsePlayerBalance(unittest.TestCase):
    def test_career_and_seasons(self):
        out = te.parse_player_balance(BALANCE_HTML)
        self.assertIn("career", out)
        self.assertEqual(out["career"]["total"], {"w": 465, "l": 138})
        self.assertEqual(out["career"]["bySurface"]["Clay"], {"w": 125, "l": 38})
        self.assertEqual(out["seasons"][2025]["total"], {"w": 73, "l": 6})
        self.assertEqual(out["seasons"][2024]["bySurface"]["Grass"], {"w": 6, "l": 0})


if __name__ == "__main__":
    unittest.main()
