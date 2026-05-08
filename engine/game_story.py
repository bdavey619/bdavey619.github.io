"""engine/game_story.py — Play-by-play narrative signal detection.

Converts raw MLB Stats API allPlays into structured game-story signals.
All analysis is deterministic — no LLM calls.  The resulting game_story
dict is written into brief.json and will feed Phase 3 narrative generation.

Phase 1 (this file): threat_events, missed_opportunities, rally_sequences,
                     momentum_swings, and a summary block.
Phase 2 (TODO): bullpen_events (inherited runner tracking), game_archetype,
                emotional_core.

Public API
----------
analyze_game_flow(all_plays, is_home, full_box=None) -> dict | None
"""

import sys

_BASE_MAP = {"1B": 1, "2B": 2, "3B": 3}


# ---------------------------------------------------------------------------
# Internal: annotate every at-bat with score context, base state, outs
# ---------------------------------------------------------------------------

def _annotate_all_plays(all_plays, is_home):
    """
    Walk all plays in game order and annotate EVERY at-bat from both teams.

    Each record contains:
      inning, half, side ("team"|"opp"), batter, pitcher, event, description,
      outs_before, runners_before, team_score_before, opp_score_before,
      team_score_after, opp_score_after, runs_scored (batting-team runs on
      this play), is_scoring.

    score fields are always from the tracked team's perspective:
      team = the team we care about (Padres / Yankees / etc.)
      opp  = the opposing team

    runs_scored = runs the batting team scored on this specific play.
      For team plays  → team_score_after  - team_score_before
      For opp plays   → opp_score_after   - opp_score_before

    Base state resets at each half-inning boundary (correct for both sides).
    Stationary runners (not in the runners array) are preserved automatically
    because the two-pass update only touches runners that actually moved.
    """
    team_half = "bottom" if is_home else "top"
    prev_away = 0
    prev_home = 0
    annotated = []
    base_state = set()   # occupied bases: subset of {1, 2, 3}
    prev_half = None

    for p in all_plays:
        about   = p.get("about", {})
        result  = p.get("result", {})
        matchup = p.get("matchup", {})
        runners = p.get("runners", [])

        cur_away = result.get("awayScore", prev_away)
        cur_home = result.get("homeScore", prev_home)

        current_half = about.get("halfInning")

        # Reset base state at every half-inning boundary
        if current_half != prev_half and prev_half is not None:
            base_state = set()
        prev_half = current_half

        if result.get("type") == "atBat":
            is_team = (current_half == team_half)

            if is_home:
                tb, ob, ta, oa = prev_home, prev_away, cur_home, cur_away
            else:
                tb, ob, ta, oa = prev_away, prev_home, cur_away, cur_home

            runs_scored = (ta - tb) if is_team else (oa - ob)

            annotated.append({
                "inning":            about.get("inning", 0),
                "half":              current_half,
                "side":              "team" if is_team else "opp",
                "batter":            matchup.get("batter", {}).get("fullName", ""),
                "pitcher":           matchup.get("pitcher", {}).get("fullName", ""),
                "event":             result.get("event", ""),
                "description":       result.get("description", ""),
                "rbi":               result.get("rbi", 0),
                "outs_before":       about.get("outs", 0),
                "runners_before":    sorted(base_state),
                "team_score_before": tb,
                "opp_score_before":  ob,
                "team_score_after":  ta,
                "opp_score_after":   oa,
                "runs_scored":       runs_scored,
                "is_scoring":        about.get("isScoringPlay", False),
            })

        # Two-pass base-state update.
        # Pass 1: remove bases that runners departed (preserves runners not in array)
        for r in runners:
            mv = r.get("movement", {})
            origin = mv.get("originBase") or mv.get("start")
            if origin:
                origin_num = _BASE_MAP.get(origin)
                if origin_num:
                    base_state.discard(origin_num)
        # Pass 2: add bases that runners arrived at (batter reaching has originBase=null)
        for r in runners:
            mv = r.get("movement", {})
            end    = mv.get("end")
            is_out = mv.get("isOut", False)
            if end and end.lower() != "score" and not is_out:
                end_num = _BASE_MAP.get(end)
                if end_num:
                    base_state.add(end_num)

        prev_away = cur_away
        prev_home = cur_home

    return annotated


# ---------------------------------------------------------------------------
# Detection functions
# ---------------------------------------------------------------------------

def detect_threat_events(all_annotated):
    """
    Every team at-bat where there was a runner on 2nd or 3rd (RISP situation).

    Returns list of annotated play dicts filtered to team RISP at-bats.
    Each entry is the full annotated play record (inning, event, runners_before, etc.).
    """
    return [
        p for p in all_annotated
        if p["side"] == "team" and any(b in p["runners_before"] for b in (2, 3))
    ]


def detect_missed_opportunities(all_annotated):
    """
    Innings where the team had at least one RISP situation but scored zero runs.

    Severity:
      critical    — 2+ PA with RISP and ≤1 out, 0 runs scored
      significant — 2+ PA with RISP (any out count), 0 runs scored
      mild        — 1 PA with RISP, 0 runs scored

    Returns list of dicts (one per missed inning), sorted by inning.
    """
    team_plays = [p for p in all_annotated if p["side"] == "team"]

    by_inning = {}
    for p in team_plays:
        by_inning.setdefault(p["inning"], []).append(p)

    missed = []
    for inning, plays in sorted(by_inning.items()):
        risp_plays = [
            p for p in plays
            if any(b in p["runners_before"] for b in (2, 3))
        ]
        if not risp_plays:
            continue

        total_runs = sum(p["runs_scored"] for p in plays)
        if total_runs > 0:
            continue  # they converted, not a miss

        # High-leverage subset: RISP with 0 or 1 out
        risp_prime = [p for p in risp_plays if p["outs_before"] <= 1]

        if len(risp_prime) >= 2:
            severity = "critical"
        elif len(risp_plays) >= 2:
            severity = "significant"
        else:
            severity = "mild"

        # Approximate LOB: bases still occupied after the inning's last play.
        # Uses runners_before of the final play as a rough proxy (most accurate
        # when the last play is the third out with runners on).
        last_play = plays[-1]
        runners_left = len(last_play.get("runners_before", []))

        missed.append({
            "inning":       inning,
            "risp_at_bats": len(risp_plays),
            "runners_left": runners_left,
            "events":       [p["event"] for p in risp_plays],
            "severity":     severity,
        })

    return missed


def detect_rally_sequences(all_annotated):
    """
    Innings where the team scored 2+ runs (multi-run half-innings).

    Returns list of dicts, one per multi-run inning, sorted by inning.
    Each includes the scoring plays, whether the team was trailing/tied at
    the start, and whether a lead change resulted.
    """
    team_plays = [p for p in all_annotated if p["side"] == "team"]

    by_inning = {}
    for p in team_plays:
        by_inning.setdefault(p["inning"], []).append(p)

    rallies = []
    for inning, plays in sorted(by_inning.items()):
        total_runs = sum(p["runs_scored"] for p in plays)
        if total_runs < 2:
            continue

        first = plays[0]
        last  = plays[-1]

        came_from_behind = first["team_score_before"] < first["opp_score_before"]
        was_tied         = first["team_score_before"] == first["opp_score_before"]
        lead_change      = (
            first["team_score_before"] <= first["opp_score_before"]
            and last["team_score_after"] > last["opp_score_after"]
        )

        scoring_plays = [
            {"batter": p["batter"], "event": p["event"], "rbi": p["rbi"]}
            for p in plays
            if p["runs_scored"] > 0
        ]

        rallies.append({
            "inning":           inning,
            "runs":             total_runs,
            "scoring_plays":    scoring_plays,
            "came_from_behind": came_from_behind,
            "was_tied":         was_tied,
            "lead_change":      lead_change,
        })

    return rallies


def detect_momentum_swings(all_annotated):
    """
    Half-innings where the batting team scored 2+ runs.

    "direction" is always from the tracked team's perspective:
      "for"     — team scored 2+ (positive momentum)
      "against" — opponent scored 2+ (negative momentum)

    lead_change — True if the differential flipped sign this half-inning.
    go_ahead    — True if the team moved from tied/trailing to leading.

    Returns list of swing dicts sorted by (inning, half).
    """
    by_half_inning = {}
    for p in all_annotated:
        key = (p["inning"], p["half"])
        by_half_inning.setdefault(key, []).append(p)

    swings = []
    for (inning, half), plays in sorted(by_half_inning.items()):
        if not plays:
            continue

        runs_this_half = sum(p["runs_scored"] for p in plays)
        if runs_this_half < 2:
            continue

        first = plays[0]
        last  = plays[-1]

        team_before = first["team_score_before"]
        opp_before  = first["opp_score_before"]
        team_after  = last["team_score_after"]
        opp_after   = last["opp_score_after"]

        lead_before = team_before - opp_before   # +: team ahead, -: opp ahead
        lead_after  = team_after  - opp_after

        lead_change = (
            (lead_before > 0 and lead_after <= 0)
            or (lead_before < 0 and lead_after >= 0)
            or (lead_before == 0 and lead_after != 0)
        )
        go_ahead = lead_before <= 0 and lead_after > 0

        side = plays[0]["side"]  # all plays in a half-inning share the same side
        direction = "for" if side == "team" else "against"

        swings.append({
            "inning":       inning,
            "half":         half,
            "direction":    direction,
            "runs":         runs_this_half,
            "score_before": {"team": team_before, "opp": opp_before},
            "score_after":  {"team": team_after,  "opp": opp_after},
            "lead_change":  lead_change,
            "go_ahead":     go_ahead,
        })

    return swings


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def analyze_game_flow(all_plays, is_home, full_box=None):
    """
    Convert raw allPlays list into narrative signals.

    Parameters
    ----------
    all_plays : list
        The allPlays array from /game/{game_pk}/playByPlay.
    is_home : bool
        True if the tracked team was the home team.
    full_box : dict | None
        Optional full_box dict from brief.json (reserved for Phase 2).

    Returns
    -------
    dict | None
        game_story dict, or None if all_plays is empty or analysis fails.

    Schema
    ------
    {
      "threat_events":        [...],   # every RISP at-bat for the team
      "missed_opportunities": [...],   # innings with RISP but 0 runs
      "rally_sequences":      [...],   # multi-run half-innings
      "momentum_swings":      [...],   # 2+-run half-innings (both teams)
      "bullpen_events":       [],      # TODO Phase 2
      "summary": {
        "total_risp_situations":     int,
        "missed_opportunity_innings": int,
        "critical_misses":           int,
        "significant_misses":        int,
        "multi_run_innings":         int,
        "momentum_swing_count":      int,
      }
    }
    """
    if not all_plays:
        return None

    try:
        all_annotated = _annotate_all_plays(all_plays, is_home)
        if not all_annotated:
            return None

        threat_events = detect_threat_events(all_annotated)
        missed_opps   = detect_missed_opportunities(all_annotated)
        rally_seqs    = detect_rally_sequences(all_annotated)
        momentum      = detect_momentum_swings(all_annotated)

        critical_misses    = sum(1 for m in missed_opps if m["severity"] == "critical")
        significant_misses = sum(1 for m in missed_opps if m["severity"] == "significant")

        return {
            "threat_events":        threat_events,
            "missed_opportunities": missed_opps,
            "rally_sequences":      rally_seqs,
            "momentum_swings":      momentum,
            "bullpen_events":       [],  # TODO Phase 2: inherited runner tracking
            "summary": {
                "total_risp_situations":      len(threat_events),
                "missed_opportunity_innings": len(missed_opps),
                "critical_misses":            critical_misses,
                "significant_misses":         significant_misses,
                "multi_run_innings":          len(rally_seqs),
                "momentum_swing_count":       len(momentum),
            },
        }

    except Exception as exc:
        print(f"  warn: game_story analysis failed: {exc}", file=sys.stderr)
        return None
