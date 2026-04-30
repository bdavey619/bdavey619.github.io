#!/usr/bin/env python3
"""
test_postponed.py — Regression test for postponed-game detection.

Verifies that a game with detailedState="Postponed" + abstractGameState="Final"
(the exact MLB API state that caused the Giants 0–0 loss bug on 2026-04-30) is
returned as status="postponed", never status="final".

Run from repo root:
    python3 test_postponed.py
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

POSTPONED_GAME = {
    "gamePk": 823471,
    "gameDate": "2026-04-30T20:15:00Z",
    "officialDate": "2026-04-30",
    "status": {
        "abstractGameState": "Final",   # ← the misleading field that caused the bug
        "detailedState": "Postponed",
        "statusCode": "P",
        "codedGameState": "P",
    },
    "teams": {
        "home": {"team": {"id": 137, "name": "San Francisco Giants", "abbreviation": "SF"}},
        "away": {"team": {"id": 143, "name": "Philadelphia Phillies", "abbreviation": "PHI"}},
    },
    "venue": {"name": "Oracle Park"},
    "linescore": {},
}

FINAL_GAME = {
    "gamePk": 823230,
    "gameDate": "2026-04-26T20:15:00Z",
    "officialDate": "2026-04-26",
    "status": {
        "abstractGameState": "Final",
        "detailedState": "Final",
        "statusCode": "F",
        "codedGameState": "F",
    },
    "teams": {
        "home": {"team": {"id": 137, "name": "San Francisco Giants", "abbreviation": "SF"}},
        "away": {"team": {"id": 146, "name": "Miami Marlins", "abbreviation": "MIA"}},
    },
    "venue": {"name": "Oracle Park"},
    "linescore": {
        "teams": {
            "home": {"runs": 6},
            "away": {"runs": 3},
        },
        "innings": [],
    },
    "decisions": {},
}


def _run_for_team(module_path, team_games):
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_brief", module_path)
    mod = importlib.util.load_from_spec(spec)
    spec.loader.exec_module(mod)

    with patch.object(mod, "_fetch_schedule", return_value=team_games), \
         patch.object(mod, "_format_last_game", side_effect=lambda g: {
             "status": "final", "gamePk": g["gamePk"],
             "result": "W", "score": {"team": 6, "opp": 3},
         }):
        return mod.get_last_game()


def test_postponed_beats_final_abstract_state():
    """
    A game with detailedState=Postponed must be returned as postponed even when
    abstractGameState is Final.  The postponed game here is newer, so it wins.
    """
    games = [FINAL_GAME, POSTPONED_GAME]  # unsorted; get_last_game sorts newest-first

    for team in ("giants", "yankees", "padres", "athletics"):
        path = Path(__file__).parent / team / "build_brief.py"
        result = _run_for_team(str(path), games)
        assert result["status"] == "postponed", (
            f"[{team}] Expected status='postponed', got {result['status']!r}. "
            "abstractGameState='Final' incorrectly overrode detailedState='Postponed'."
        )
        assert "result" not in result, f"[{team}] Postponed game must not have a 'result' field"
        assert "score" not in result, f"[{team}] Postponed game must not have a 'score' field"
        print(f"  [{team}] PASS — status={result['status']!r} opponent={result.get('opponent')!r}")


def test_normal_final_unaffected():
    """A genuine Final game with no postponed indicators must still return status='final'."""
    games = [FINAL_GAME]

    for team in ("giants", "yankees", "padres", "athletics"):
        path = Path(__file__).parent / team / "build_brief.py"
        result = _run_for_team(str(path), games)
        assert result["status"] == "final", (
            f"[{team}] Expected status='final' for a clean Final game, got {result['status']!r}"
        )
        print(f"  [{team}] PASS — normal final game unaffected")


if __name__ == "__main__":
    import importlib.util

    # Patch exec_module since load_from_spec isn't real — use a simpler approach
    # that directly imports via importlib without the two-step mistake above.

    def _run(module_path, team_games):
        spec = importlib.util.spec_from_file_location("build_brief_" + Path(module_path).parent.name, module_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        with patch.object(mod, "_fetch_schedule", return_value=team_games), \
             patch.object(mod, "_format_last_game", side_effect=lambda g: {
                 "status": "final", "gamePk": g["gamePk"],
                 "result": "W", "score": {"team": 6, "opp": 3},
             }):
            return mod.get_last_game()

    # Override the helper used by test functions
    globals()["_run_for_team"] = _run

    print("=== test_postponed_beats_final_abstract_state ===")
    test_postponed_beats_final_abstract_state()
    print()
    print("=== test_normal_final_unaffected ===")
    test_normal_final_unaffected()
    print()
    print("All tests passed.")
