"""engine/clutch.py — Deterministic clutch moment detector.

Fetches MLB Stats API play-by-play for a game and identifies the
highest-leverage player/moment for a given team.

No AI inference. Returns structured data that build_brief.py embeds in
brief.json; engine/narrative.py uses it to anchor the editorial narrative.
"""

import sys
import requests
from urllib.parse import urlencode

API = "https://statsapi.mlb.com/api/v1"
TIMEOUT = 15


def _get(path, **params):
    url = f"{API}/{path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def fetch_play_by_play(game_pk):
    """Return allPlays list for game_pk, or [] on failure."""
    try:
        data = _get(f"game/{game_pk}/playByPlay")
        return data.get("allPlays", [])
    except Exception as exc:
        print(f"  warn: play-by-play fetch failed for {game_pk}: {exc}", file=sys.stderr)
        return []


_ORDINAL = {
    1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
    6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth",
    11: "eleventh", 12: "twelfth",
}


def _ordinal(n):
    return _ORDINAL.get(n, f"{n}th")


# Events that can start or continue a rally (at-bat-level, not actions)
_RALLY_STARTERS = {
    "Single", "Double", "Triple", "Home Run", "Ground Rule Double",
    "Walk", "Hit By Pitch", "Intent Walk", "Sac Fly", "Sac Bunt",
}


def _annotate_plays(all_plays, is_home):
    """
    Walk through ALL plays in game order, tracking cumulative score.
    For each team at-bat, record score_before / score_after / runs_scored.

    Returns list of dicts for team batting plays only.
    """
    team_half = "bottom" if is_home else "top"
    prev_away = 0
    prev_home = 0
    annotated = []

    for p in all_plays:
        about = p.get("about", {})
        result = p.get("result", {})
        matchup = p.get("matchup", {})

        # Scores AFTER this play (cumulative totals from the API)
        cur_away = result.get("awayScore", prev_away)
        cur_home = result.get("homeScore", prev_home)

        if result.get("type") == "atBat" and about.get("halfInning") == team_half:
            if is_home:
                tb, ob, ta, oa = prev_home, prev_away, cur_home, cur_away
            else:
                tb, ob, ta, oa = prev_away, prev_home, cur_away, cur_home

            annotated.append({
                "inning":            about.get("inning", 0),
                "batter":            matchup.get("batter", {}).get("fullName", ""),
                "event":             result.get("event", ""),
                "raw_description":   result.get("description", ""),
                "rbi":               result.get("rbi", 0),
                "team_score_before": tb,
                "opp_score_before":  ob,
                "team_score_after":  ta,
                "opp_score_after":   oa,
                "runs_scored":       ta - tb,
                "is_scoring":        about.get("isScoringPlay", False),
            })

        # Always advance score tracker (covers opponent at-bats between team half-innings)
        prev_away = cur_away
        prev_home = cur_home

    return annotated


def _build_description(event, inning, reason, team_after, opp_after, total_runs, rbi):
    """Generate a short factual sentence (player name NOT included)."""
    ordinal = _ordinal(inning) if inning else "late"
    ev = event.lower() if event else "play"

    if "walk-off" in reason:
        return f"walked it off in the {ordinal} with a {ev}."
    if "go-ahead" in reason:
        return f"hit the go-ahead {ev} in the {ordinal} ({team_after}–{opp_after})."
    if "tying" in reason:
        return f"tied it in the {ordinal} with a {ev}."
    if "rally" in reason:
        return f"started the {ordinal}-inning rally ({total_runs} runs scored) with a {ev}."
    if "RBI" in reason:
        return f"drove in {rbi} in the {ordinal} with a {ev}."
    return f"came through in the {ordinal} with a {ev}."


def _make_result(batter, event, inning, reason, confidence,
                 team_after=None, opp_after=None, total_runs=None, rbi=None):
    description = _build_description(
        event, inning, reason, team_after, opp_after, total_runs, rbi
    )
    return {
        "name":        batter,
        "event":       event,
        "inning":      inning,
        "description": description,
        "reason":      reason,
        "confidence":  confidence,
    }


def _fallback(hitters):
    if not hitters:
        return None
    best = hitters[0]
    name = best.get("name", "")
    line = best.get("line", "")
    if not name:
        return None
    return {
        "name":        name,
        "event":       line,
        "inning":      None,
        "description": f"led the offense with {line}.",
        "reason":      "top hitter by box score (no play-by-play clutch moment detected)",
        "confidence":  "low",
    }


def identify_clutch_player(game_pk, is_home, fallback_hitters=None):
    """
    Return the highest-leverage player/moment for the team, or None.

    Detection priority (first match wins):
      1. Walk-off play  — home team, inning >= 9, play that takes the lead
      2. Go-ahead play in 7th+  — latest (game-winning) go-ahead swing
      3. Game-tying play in 7th+  — team trailing → tied after
      4. First rally trigger in 3+-run inning in 8th+
      5. Multi-RBI play (2+ RBI) in 8th+
      6. Fallback: top key hitter from box score (confidence: low)

    Returns dict with name, event, inning, description, reason, confidence.
    Returns None only when there are no plays AND no fallback hitters.
    """
    all_plays = fetch_play_by_play(game_pk)
    if not all_plays:
        return _fallback(fallback_hitters)

    annotated = _annotate_plays(all_plays, is_home)
    if not annotated:
        return _fallback(fallback_hitters)

    # --- Priority 1: Walk-off ---
    # Home team, final inning >= 9, play that flips a tie/deficit to a lead
    if is_home:
        max_inning = max(p["inning"] for p in annotated)
        if max_inning >= 9:
            for p in reversed(annotated):
                if (p["inning"] == max_inning
                        and p["team_score_after"] > p["opp_score_after"]
                        and p["team_score_before"] <= p["opp_score_before"]
                        and p["is_scoring"]
                        and p["batter"]):
                    return _make_result(
                        p["batter"], p["event"], p["inning"],
                        "walk-off play", "high",
                        team_after=p["team_score_after"], opp_after=p["opp_score_after"],
                        total_runs=p["runs_scored"], rbi=p["rbi"],
                    )

    # --- Priority 2: Go-ahead play in 7th+ ---
    # Take the LATEST (highest inning) go-ahead swing — it's the game-winner
    # if a lead was surrendered and recaptured, the final go-ahead is what counts.
    go_ahead_plays = sorted(
        [
            p for p in annotated
            if (p["inning"] >= 7
                and p["team_score_before"] <= p["opp_score_before"]
                and p["team_score_after"] > p["opp_score_after"]
                and p["runs_scored"] > 0
                and p["batter"])
        ],
        key=lambda p: p["inning"],
        reverse=True,
    )
    if go_ahead_plays:
        p = go_ahead_plays[0]
        reason = f"go-ahead play in the {_ordinal(p['inning'])}"
        return _make_result(
            p["batter"], p["event"], p["inning"], reason, "high",
            team_after=p["team_score_after"], opp_after=p["opp_score_after"],
            total_runs=p["runs_scored"], rbi=p["rbi"],
        )

    # --- Priority 3: Game-tying play in 7th+ ---
    for p in annotated:
        if (p["inning"] >= 7
                and p["team_score_before"] < p["opp_score_before"]
                and p["team_score_after"] == p["opp_score_after"]
                and p["runs_scored"] > 0
                and p["batter"]):
            reason = f"game-tying play in the {_ordinal(p['inning'])}"
            return _make_result(
                p["batter"], p["event"], p["inning"], reason, "high",
                team_after=p["team_score_after"], opp_after=p["opp_score_after"],
                total_runs=p["runs_scored"], rbi=p["rbi"],
            )

    # --- Priority 4: First rally trigger in 3+-run inning in 8th+ ---
    inning_plays = {}
    for p in annotated:
        inning_plays.setdefault(p["inning"], []).append(p)

    # Check innings from latest to earliest (most impactful late rally wins)
    for inn in sorted((k for k in inning_plays if k >= 8), reverse=True):
        inn_plays = inning_plays[inn]
        total_runs = sum(p["runs_scored"] for p in inn_plays)
        if total_runs >= 3:
            for p in inn_plays:
                if p["event"] in _RALLY_STARTERS and p["batter"]:
                    reason = f"started the {_ordinal(inn)}-inning rally ({total_runs} runs scored)"
                    return _make_result(
                        p["batter"], p["event"], p["inning"], reason, "high",
                        team_after=p["team_score_after"], opp_after=p["opp_score_after"],
                        total_runs=total_runs, rbi=p["rbi"],
                    )

    # --- Priority 5: Multi-RBI play in 8th+ ---
    for p in annotated:
        if p["inning"] >= 8 and p["rbi"] >= 2 and p["batter"]:
            reason = f"{p['rbi']}-RBI play in the {_ordinal(p['inning'])}"
            return _make_result(
                p["batter"], p["event"], p["inning"], reason, "high",
                team_after=p["team_score_after"], opp_after=p["opp_score_after"],
                total_runs=p["runs_scored"], rbi=p["rbi"],
            )

    return _fallback(fallback_hitters)
