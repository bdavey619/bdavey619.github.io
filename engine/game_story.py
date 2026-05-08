"""engine/game_story.py — Play-by-play narrative signal detection.

Converts raw MLB Stats API allPlays into structured game-story signals.
All analysis is deterministic — no LLM calls.  The resulting game_story
dict is written into brief.json and will feed Phase 3 narrative generation.

Phase 1 (this file): threat_events, missed_opportunities, rally_sequences,
                     momentum_swings, and a summary block.
Phase 3.1: game_shape — factual lead/deficit timeline for narrative guardrails.
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
# Phase 3.1: Game-shape summary (factual lead/deficit timeline)
# ---------------------------------------------------------------------------

def _empty_game_shape():
    return {
        "team_ever_trailed":      False,
        "max_deficit_faced":      0,
        "team_ever_led":          False,
        "max_lead_held":          0,
        "was_tied_late":          False,
        "innings_team_trailed":   [],
        "innings_team_led":       [],
        "game_decided_by_inning": None,
        "blowout_by_5th":         False,
        # Phase 3.2: lead chronology
        "first_team_lead_inning":  None,
        "first_team_trail_inning": None,
        "last_tied_inning":        None,
        "lead_changes_count":      0,
    }


def detect_game_shape(all_annotated):
    """
    Compute factual lead/deficit fields from annotated plays.

    All fields are derived deterministically from play-by-play data and
    are injected into the LLM prompt as hard guardrails to prevent the
    model from inventing deficits or comebacks that did not occur.

    Fields
    ------
    team_ever_trailed     bool   — team's score was behind at any play boundary
    max_deficit_faced     int    — largest (opp - team) seen; 0 if never trailed
    team_ever_led         bool   — team was ahead at any play boundary
    max_lead_held         int    — largest (team - opp) seen; 0 if never led
    was_tied_late         bool   — score tied (by inning end) in inning 6+
    innings_team_trailed  list   — innings where team was behind at any point
    innings_team_led      list   — innings where team was ahead at any point
    game_decided_by_inning int|None — earliest inning with margin ≥ 5 that
                                      held ≥ 3 for all remaining innings
    blowout_by_5th        bool   — |margin| ≥ 5 at end of inning 5 (or last
                                   inning if game < 5 innings)
    """
    if not all_annotated:
        return _empty_game_shape()

    max_deficit = 0
    max_lead    = 0

    innings_trailed: set = set()
    innings_led:     set = set()

    # inning_end_scores[n] = (team_score, opp_score) after inning n's last play
    inning_end_scores: dict = {}

    for p in all_annotated:
        ts  = p["team_score_after"]
        os_ = p["opp_score_after"]
        inn = p["inning"]

        diff = ts - os_   # positive: team leads; negative: team trails

        if diff < 0:
            innings_trailed.add(inn)
            deficit = -diff
            if deficit > max_deficit:
                max_deficit = deficit
        elif diff > 0:
            innings_led.add(inn)
            lead = diff
            if lead > max_lead:
                max_lead = lead

        # Keep the last play's score for each inning (inning-end snapshot)
        inning_end_scores[inn] = (ts, os_)

    team_ever_trailed = max_deficit > 0
    team_ever_led     = max_lead    > 0

    # Phase 3.2: lead chronology fields
    first_team_lead_inning  = min(innings_led)      if innings_led      else None
    first_team_trail_inning = min(innings_trailed)  if innings_trailed  else None

    # last_tied_inning: last inning where score was exactly tied at inning end
    last_tied_inning = None
    for inn in sorted(inning_end_scores.keys(), reverse=True):
        ts_e, os_e = inning_end_scores[inn]
        if ts_e == os_e:
            last_tied_inning = inn
            break

    # lead_changes_count: number of times the non-tied leader changed hands
    last_non_tied_leader = None
    lead_changes_count   = 0
    for inn in sorted(inning_end_scores.keys()):
        ts_e, os_e = inning_end_scores[inn]
        if ts_e > os_e:
            current_leader = "team"
        elif os_e > ts_e:
            current_leader = "opp"
        else:
            continue  # tied — no leader change at this inning end
        if last_non_tied_leader is not None and current_leader != last_non_tied_leader:
            lead_changes_count += 1
        last_non_tied_leader = current_leader

    # was_tied_late: score exactly tied at end of inning 6+
    was_tied_late = any(
        ts == os_
        for inn, (ts, os_) in inning_end_scores.items()
        if inn >= 6
    )

    # blowout_by_5th: |margin| ≥ 5 at end of the last inning ≤ 5
    early = {inn: sc for inn, sc in inning_end_scores.items() if inn <= 5}
    if early:
        last_early = max(early)
        ts5, os5 = early[last_early]
        blowout_by_5th = abs(ts5 - os5) >= 5
    else:
        blowout_by_5th = False

    # game_decided_by_inning: earliest inning where margin ≥ 5 AND
    # margin stays ≥ 3 for every subsequent inning.
    sorted_innings = sorted(inning_end_scores.keys())
    game_decided_by_inning = None
    for idx, inn in enumerate(sorted_innings):
        ts, os_ = inning_end_scores[inn]
        margin = abs(ts - os_)
        if margin >= 5:
            subsequent = sorted_innings[idx + 1:]
            held = all(
                abs(inning_end_scores[ni][0] - inning_end_scores[ni][1]) >= 3
                for ni in subsequent
            )
            if held:
                game_decided_by_inning = inn
                break

    return {
        "team_ever_trailed":      team_ever_trailed,
        "max_deficit_faced":      max_deficit,
        "team_ever_led":          team_ever_led,
        "max_lead_held":          max_lead,
        "was_tied_late":          was_tied_late,
        "innings_team_trailed":   sorted(innings_trailed),
        "innings_team_led":       sorted(innings_led),
        "game_decided_by_inning": game_decided_by_inning,
        "blowout_by_5th":         blowout_by_5th,
        # Phase 3.2: lead chronology
        "first_team_lead_inning":  first_team_lead_inning,
        "first_team_trail_inning": first_team_trail_inning,
        "last_tied_inning":        last_tied_inning,
        "lead_changes_count":      lead_changes_count,
    }


# ---------------------------------------------------------------------------
# Game-texture classification
# ---------------------------------------------------------------------------

_TEXTURE_PRIMARIES = {
    "pitching_duel",
    "offensive_breakout",
    "blowout",
    "dead_offense_loss",
    "bullpen_grind",
    "late_breakthrough",
    "back_and_forth",
    "routine_win",
    "routine_loss",
}

_TEXTURE_SECONDARIES = {
    "offense_wasted_pitching",
    "dead_offense_loss",
    "late_collapse",
    "bullpen_blown",
}


def _build_texture(primary, secondary, reason, tone_guidance):
    return {
        "primary":      primary,
        "secondary":    secondary,
        "reason":       reason,
        "tone_guidance": tone_guidance,
    }


def detect_game_texture(all_annotated, game_shape, full_box=None):
    """
    Classify the game's dominant narrative texture from play-by-play signals,
    game_shape fields, and (when available) full_box batting/pitching rows.

    Returns a dict:
      primary       — dominant texture label (see _TEXTURE_PRIMARIES)
      secondary     — modifier label or None (see _TEXTURE_SECONDARIES)
      reason        — human-readable explanation of why this label was chosen
      tone_guidance — comma-joined tone words for the narrative prompt

    Priority order (first match wins):
      blowout → pitching_duel → late_breakthrough → dead_offense_loss
      → offensive_breakout → bullpen_grind → back_and_forth → routine_*
    """
    if not all_annotated:
        return _build_texture(
            "routine_loss", None, "no play data", "neutral, analytical"
        )

    # ------------------------------------------------------------------
    # Derive facts from annotated plays
    # ------------------------------------------------------------------
    last_play = all_annotated[-1]
    team_runs = last_play["team_score_after"]
    opp_runs  = last_play["opp_score_after"]
    final_margin = abs(team_runs - opp_runs)
    team_won  = team_runs > opp_runs
    total_runs = team_runs + opp_runs

    # Inning-end snapshot (last play's score per inning)
    inning_end: dict = {}
    for p in all_annotated:
        inning_end[p["inning"]] = (p["team_score_after"], p["opp_score_after"])

    # Tight through 6: every inning-end in 1-6 had margin ≤ 1
    early_inns = [inn for inn in inning_end if inn <= 6]
    tight_through_6 = bool(early_inns) and all(
        abs(inning_end[inn][0] - inning_end[inn][1]) <= 1
        for inn in early_inns
    )

    # Late big inning: team scored 2+ in inning 7+
    team_by_inning: dict = {}
    for p in all_annotated:
        if p["side"] == "team":
            team_by_inning.setdefault(p["inning"], []).append(p)

    late_big_inning = any(
        sum(p["runs_scored"] for p in plays) >= 2
        for inn, plays in team_by_inning.items()
        if inn >= 7
    )

    # ------------------------------------------------------------------
    # Box-score stats (graceful if full_box absent)
    # ------------------------------------------------------------------
    batting  = (full_box or {}).get("batting")  or []
    pitching = (full_box or {}).get("pitching") or []

    team_hits = sum(b.get("h", 0)  for b in batting)
    team_ks   = sum(b.get("so", 0) for b in batting)

    def _to_float(v):
        try:
            return float(str(v).split()[0])
        except (TypeError, ValueError):
            return 0.0

    starter_ip = _to_float(pitching[0].get("ip", 0)) if pitching else None
    starter_er = int(pitching[0].get("er", 0))        if pitching else None

    # ------------------------------------------------------------------
    # Flags from game_shape
    # ------------------------------------------------------------------
    gs             = game_shape or {}
    blowout_by_5th = gs.get("blowout_by_5th", False)
    game_decided   = gs.get("game_decided_by_inning")
    lead_changes   = gs.get("lead_changes_count", 0)
    last_tied_inn  = gs.get("last_tied_inning")

    is_blowout = blowout_by_5th or (
        game_decided is not None and game_decided <= 5
    )

    # ------------------------------------------------------------------
    # Reason fragments assembled per rule
    # ------------------------------------------------------------------
    def _run_note():
        return f"combined {total_runs} run(s) ({team_runs}-{opp_runs})"

    def _starter_note():
        if starter_ip is not None:
            return f"starter: {starter_er} ER in {starter_ip} IP"
        return ""

    def _tightness_note():
        if last_tied_inn and last_tied_inn >= 6:
            return f"tied through inning {last_tied_inn}"
        return "within 1 run through 6 innings"

    # ------------------------------------------------------------------
    # Rule 1 — blowout (highest priority)
    # ------------------------------------------------------------------
    if is_blowout:
        decided_note = (
            f"game decided by inning {game_decided}"
            if game_decided else "blowout by 5th inning"
        )
        return _build_texture(
            "blowout", None,
            f"{_run_note()}; {decided_note}; margin={final_margin}",
            "flat, compressed, state-the-facts, no manufactured drama",
        )

    # ------------------------------------------------------------------
    # Rule 2 — pitching_duel
    # ------------------------------------------------------------------
    starter_held = (
        starter_er is not None and starter_er <= 2
    ) or (starter_er is None) or (total_runs <= 2)

    # Exclude the late_breakthrough case: if team won on a 2+ run late inning
    # the game's story is the breakthrough, not the pitching quality.
    is_pitching_duel = (
        total_runs <= 4
        and tight_through_6
        and starter_held
        and not (late_big_inning and team_won)
    )

    if is_pitching_duel:
        parts = [_run_note(), _tightness_note()]
        if starter_ip is not None:
            parts.append(_starter_note())

        secondary = None
        tone = "compressed, restrained, pitcher-forward, low-scoring"

        if not team_won:
            # Starter held them — offense wasted it
            if starter_er is not None and starter_er <= 2:
                secondary = "offense_wasted_pitching"
                parts.append(
                    f"team scored {team_runs} run(s) despite starter holding it tight"
                )
                tone = "compressed, restrained, pitcher-forward, offense-failure"
            # Offense silenced by opponent pitcher
            elif batting and (team_hits <= 5 or team_ks >= 9):
                secondary = "dead_offense_loss"
                detail = []
                if team_hits <= 5:
                    detail.append(f"{team_hits} hits")
                if team_ks >= 9:
                    detail.append(f"{team_ks} strikeouts")
                parts.append(f"offense suppressed ({', '.join(detail)})")
                tone = "compressed, restrained, pitcher-forward, offense-suppressed"

        return _build_texture("pitching_duel", secondary, "; ".join(parts), tone)

    # ------------------------------------------------------------------
    # Rule 3 — late_breakthrough (tight through 6, team scored big late)
    # ------------------------------------------------------------------
    if tight_through_6 and late_big_inning and team_won:
        parts = [_tightness_note(), "team scored 2+ runs in inning 7+"]
        if starter_ip is not None:
            parts.append(_starter_note())
        return _build_texture(
            "late_breakthrough", None,
            "; ".join(parts),
            "building tension, restrained early, explosive payoff late",
        )

    # ------------------------------------------------------------------
    # Rule 4 — dead_offense_loss
    # ------------------------------------------------------------------
    is_dead_offense = (
        not team_won
        and team_runs <= 2
        and batting
        and (team_hits <= 5 or team_ks >= 9)
    )
    if is_dead_offense:
        detail = []
        if team_hits <= 5:
            detail.append(f"{team_hits} hits")
        if team_ks >= 9:
            detail.append(f"{team_ks} strikeouts")
        parts = [f"team scored {team_runs} run(s)", f"offense silenced ({', '.join(detail)})"]
        secondary = None
        if starter_er is not None and starter_er <= 2:
            secondary = "offense_wasted_pitching"
            parts.append(_starter_note())
        return _build_texture(
            "dead_offense_loss", secondary,
            "; ".join(parts),
            "flat, offense-failure, suppressed energy",
        )

    # ------------------------------------------------------------------
    # Rule 5 — offensive_breakout
    # ------------------------------------------------------------------
    is_breakout = team_runs >= 8 or (team_runs >= 6 and batting and team_hits >= 10)
    if is_breakout:
        hit_note = f"on {team_hits} hits" if batting else ""
        parts = [f"team scored {team_runs} run(s) {hit_note}".strip()]
        return _build_texture(
            "offensive_breakout", None,
            "; ".join(parts),
            "expansive, offense-forward, confident and declarative",
        )

    # ------------------------------------------------------------------
    # Rule 6 — bullpen_grind (starter exited early, game remained close)
    # ------------------------------------------------------------------
    is_bullpen_grind = (
        starter_ip is not None
        and starter_ip < 5.0
        and final_margin <= 2
    )
    if is_bullpen_grind:
        return _build_texture(
            "bullpen_grind", None,
            f"starter lasted {starter_ip} IP; game decided by {final_margin} run(s)",
            "grind, uncertain, bullpen-forward, survival feel",
        )

    # ------------------------------------------------------------------
    # Rule 7 — back_and_forth
    # ------------------------------------------------------------------
    if lead_changes >= 2:
        return _build_texture(
            "back_and_forth", None,
            f"{lead_changes} lead changes; game shifted multiple times",
            "energetic, multi-chapter, avoid anchoring on a single moment",
        )

    # ------------------------------------------------------------------
    # Fallback — routine win / loss
    # ------------------------------------------------------------------
    if team_won:
        return _build_texture(
            "routine_win", None,
            f"{_run_note()}; no dominant feature detected",
            "steady, measured, let facts carry the story",
        )
    return _build_texture(
        "routine_loss", None,
        f"{_run_note()}; no dominant failure mode detected",
        "honest, analytical, no manufactured drama",
    )


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
        game_shape    = detect_game_shape(all_annotated)
        game_texture  = detect_game_texture(all_annotated, game_shape, full_box)

        critical_misses    = sum(1 for m in missed_opps if m["severity"] == "critical")
        significant_misses = sum(1 for m in missed_opps if m["severity"] == "significant")

        return {
            "threat_events":        threat_events,
            "missed_opportunities": missed_opps,
            "rally_sequences":      rally_seqs,
            "momentum_swings":      momentum,
            "bullpen_events":       [],  # TODO Phase 2: inherited runner tracking
            "game_shape":           game_shape,
            "game_texture":         game_texture,
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
