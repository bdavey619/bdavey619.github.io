#!/usr/bin/env python3
"""
test_offseason.py — Regression test for offseason rendering.

build_brief emits last_game = {"status": "off_day"} once no Final game falls in
its 14-day lookback, and next_game = None once nothing is scheduled. That is the
state every morning of the offseason, and it used to crash render_email with
KeyError: 'score' (render_email.py:429), failing the workflow before the send
gate in send_email.py could skip the send.

Renders into a temp tree so no tracked file is touched.

Run from repo root:
    python3 test_offseason.py
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

import render_email

TEAMS = ["padres", "giants", "yankees", "athletics"]
REPO = Path(__file__).parent

OFFSEASON_BRIEF = {
    "generated_at": "2026-11-24T10:25:00-08:00",
    "season": 2026,
    "team": {"record": "82-80", "streak": "", "run_diff": "+12", "last10": ""},
    "last_game": {"status": "off_day"},
    "next_game": None,
    "standings": [],
    "insight": {},
}

MIDSEASON_GAP_BRIEF = dict(
    OFFSEASON_BRIEF,
    next_game={
        "date": "2026-11-25",
        "opponent": "LAD",
        "home": True,
        "time_local": "6:40 PM PT",
        "probable": {"team": "Michael King", "opp": "Tyler Glasnow"},
    },
)


def render_with(team, brief):
    """Render one brief into a throwaway tree; return the HTML."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        team_dir = tmp / team
        team_dir.mkdir()
        (team_dir / "brief.json").write_text(json.dumps(brief))
        shutil.copy(REPO / team / "email_template.html", team_dir / "email_template.html")
        with patch.object(render_email, "ROOT", tmp), \
             patch.object(sys, "argv", ["render_email.py", "--team", team]):
            render_email.main()
        return (team_dir / "email_preview.html").read_text()


def test_offseason_renders():
    for team in TEAMS:
        html = render_with(team, OFFSEASON_BRIEF)
        assert "OFFSEASON" in html, f"[{team}] expected an OFFSEASON label"
        assert "No games scheduled" in html, f"[{team}] expected the no-schedule teaser"
        assert "The season has ended" in html, f"[{team}] expected the offseason note"
        assert "{{" not in html, f"[{team}] unfilled placeholder left in output"
        assert "&middot;  &middot;" not in html, f"[{team}] dangling separator in teaser"
    print("✓  offseason brief renders for all four teams")


def test_gap_with_scheduled_game():
    for team in TEAMS:
        html = render_with(team, MIDSEASON_GAP_BRIEF)
        assert "NO RECENT GAMES" in html, f"[{team}] expected a NO RECENT GAMES label"
        assert "vs LAD" in html, f"[{team}] expected the scheduled opponent"
        assert "6:40 PM PT" in html, f"[{team}] expected the scheduled time"
        assert "No completed games in the past two weeks." in html, f"[{team}] expected the gap note"
        assert "{{" not in html, f"[{team}] unfilled placeholder left in output"
    print("✓  off_day with a game on the schedule renders the teaser")


def test_final_game_unaffected():
    """The in-season path must render exactly as before: score, result, 4-part teaser."""
    for team in TEAMS:
        brief = json.loads((REPO / team / "brief.json").read_text())
        lg, ng = brief["last_game"], brief["next_game"]
        if lg.get("status") != "final" or not ng:
            print(f"   (skipped {team}: committed brief.json is not a final game)")
            continue
        html = render_with(team, brief)
        score = f"{lg['score']['team']}–{lg['score']['opp']}"
        assert score in html, f"[{team}] expected the score {score}"
        assert ("WIN" if lg["result"] == "W" else "LOSS") in html, f"[{team}] expected a result label"
        expected_teaser = " &middot; ".join([
            render_email.next_day_label(ng.get("date", "")),
            f"{'vs' if ng.get('home') else '@'} {ng.get('opponent', '')}",
            ng.get("time_local", ""),
            f"{(ng.get('probable') or {}).get('team', 'TBD')} vs {(ng.get('probable') or {}).get('opp', 'TBD')}",
        ])
        assert expected_teaser in html, f"[{team}] teaser line changed:\n  want {expected_teaser}"
        assert "{{" not in html, f"[{team}] unfilled placeholder left in output"
    print("✓  final-game rendering unchanged")


if __name__ == "__main__":
    test_offseason_renders()
    test_gap_with_scheduled_game()
    test_final_game_unaffected()
    print("\nAll offseason rendering tests passed.")
