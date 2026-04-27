"""
engine/narrative.py — Shared State of Play narrative engine.

Used by padres/build_brief.py and yankees/build_brief.py.
All team-specific strings (team_name, story_state_path) are passed as parameters.
"""

import json
import os
import re
from pathlib import Path

import requests


# ---------------------------------------------------------------------------
# Anti-speculation guardrail
# ---------------------------------------------------------------------------

_BANNED_SPECULATIVE_PHRASES = [
    "if the offense",
    "if they",
    "if the bats",
    "could be",
    "might be",
    "watch out",
    "gets dangerous",
    "when it clicks",
    "when they click",
    "what's ahead",
    "hard to see",
    "slowing down",
    "this team gets",
]


def check_insight_language(text):
    """Log a warning if speculative language appears in insight text."""
    lower = text.lower()
    for phrase in _BANNED_SPECULATIVE_PHRASES:
        if phrase in lower:
            import sys
            print(
                f"  warn [insight guardrail]: speculative phrase detected — {phrase!r}",
                file=sys.stderr,
            )


# ---------------------------------------------------------------------------
# Game Emotion Classification
# ---------------------------------------------------------------------------

def classify_game_emotion(last_game):
    """
    Classify the emotional intensity of the last game.
    Returns 'normal' | 'high' | 'extreme' based on structured game data only.

    extreme: walk-off win, 4+ runs in 9th or later (and win), comeback from 4+ deficit,
             extra-innings win after trailing by 2+
    high:    go-ahead run in 7th+, extra-innings win, comeback from 2-3 deficit,
             10+ K start, 2+ HR game, shutout/near-shutout with 6+ inning start
    normal:  everything else
    """
    if not last_game:
        return "normal"

    result    = last_game.get("result", "")
    home      = last_game.get("home", False)
    score     = last_game.get("score") or {}
    opp_runs  = int(score.get("opp", 0) or 0)
    linescore = last_game.get("linescore") or [[], []]

    def _to_int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    sd_inn  = [_to_int(v) for v in (linescore[0] if linescore else [])]
    opp_inn = [_to_int(v) for v in (linescore[1] if len(linescore) > 1 else [])]
    num_innings = len(sd_inn)

    if num_innings == 0:
        return "normal"

    n = min(len(sd_inn), len(opp_inn))
    sd_cum  = [sum(sd_inn[:i + 1]) for i in range(n)]
    opp_cum = [sum(opp_inn[:i + 1]) for i in range(n)]

    max_deficit = max((opp_cum[i] - sd_cum[i] for i in range(n)), default=0)

    is_win   = result == "W"
    is_extra = num_innings > 9

    # EXTREME triggers
    is_walkoff = (
        is_win and home and num_innings >= 9
        and len(sd_inn) == len(opp_inn)
        and sd_inn[-1] > 0
    )
    late_explosion  = is_win and sum(sd_inn[8:]) >= 4
    big_comeback    = is_win and max_deficit >= 4
    extra_big_swing = is_win and is_extra and max_deficit >= 2

    if is_walkoff or late_explosion or big_comeback or extra_big_swing:
        return "extreme"

    # HIGH triggers
    go_ahead_late = False
    if is_win and n > 6:
        for i in range(6, n):
            if sd_cum[i - 1] <= opp_cum[i - 1] and sd_cum[i] > opp_cum[i]:
                go_ahead_late = True
                break

    extra_innings_win  = is_win and is_extra
    moderate_comeback  = is_win and max_deficit >= 2

    full_box  = last_game.get("full_box") or {}
    pitching  = full_box.get("pitching") or []
    starter_k = int(pitching[0].get("k", 0)) if pitching else 0
    dominant_k = starter_k >= 10

    key_hitters = last_game.get("key_hitters") or []
    total_hr = 0
    max_hr_single = 0
    for h in key_hitters:
        m = re.search(r'(\d+)\s*HR', h.get("line", ""))
        if m:
            hr = int(m.group(1))
            total_hr += hr
            max_hr_single = max(max_hr_single, hr)
    big_hr = total_hr >= 2 or max_hr_single >= 2

    try:
        starter_ip = float(str(pitching[0].get("ip", "0"))) if pitching else 0.0
    except (TypeError, ValueError):
        starter_ip = 0.0
    near_shutout = is_win and opp_runs <= 1 and starter_ip >= 6.0

    if (go_ahead_late or extra_innings_win or moderate_comeback
            or dominant_k or big_hr or near_shutout):
        return "high"

    return "normal"


# ---------------------------------------------------------------------------
# Story State
# ---------------------------------------------------------------------------

_TREND_ORDER    = {"surging": 4, "stabilizing": 3, "fragile": 2, "slipping": 1}
_CONF_ORDER     = {"high": 3, "medium": 2, "low": 1}
_PRESSURE_ORDER = {"low": 1, "building": 2, "high": 3}


def build_story_state(team, last_game):
    """
    Compute a lightweight story-state object from available structured data.

    trend:              surging | stabilizing | fragile | slipping
    driver:             pitching | offense | balanced | unclear
    confidence:         high | medium | low
    pressure:           low | building | high
    game_emotion_level: normal | high | extreme
    """
    def _f(val, default=0.0):
        try:
            return float(str(val).replace("+", ""))
        except (ValueError, TypeError):
            return default

    era_val = _f(team.get("era"), 4.00)
    ops_val = _f(team.get("ops"), 0.720)

    last10   = team.get("last10", "5-5")
    last10_w = int(last10.split("-")[0]) if last10 and "-" in last10 else 5

    streak   = team.get("streak", "")
    streak_m = re.match(r'^([WL])(\d+)$', streak)
    streak_type = streak_m.group(1) if streak_m else ""
    streak_num  = int(streak_m.group(2)) if streak_m else 0

    gb_raw = team.get("games_back", "5")
    try:
        gb = float(str(gb_raw))
    except (ValueError, TypeError):
        gb = 0.0

    division_rank = team.get("division_rank", 3)

    record = team.get("record", "0-0")
    try:
        rec_w, rec_l = map(int, record.split("-"))
    except (ValueError, AttributeError):
        rec_w, rec_l = 0, 0

    # trend
    if last10_w >= 8 or (last10_w >= 7 and streak_type == "W" and streak_num >= 3):
        trend = "surging"
    elif last10_w >= 6 and streak_type != "L":
        trend = "stabilizing"
    elif last10_w <= 3 or (streak_type == "L" and streak_num >= 3):
        trend = "slipping"
    else:
        trend = "fragile"

    # driver
    if era_val < 3.80 and ops_val < 0.700:
        driver = "pitching"
    elif ops_val > 0.750 and era_val >= 3.80:
        driver = "offense"
    elif era_val < 3.80 and ops_val >= 0.700:
        driver = "balanced"
    elif era_val >= 4.30 and ops_val < 0.700:
        driver = "unclear"
    else:
        driver = "balanced"

    # confidence
    total_g  = rec_w + rec_l
    win_pct  = rec_w / total_g if total_g > 0 else 0.5
    if trend == "surging" and win_pct >= 0.550:
        confidence = "high"
    elif trend == "slipping" or (trend == "fragile" and gb > 3.0):
        confidence = "low"
    else:
        confidence = "medium"

    # pressure
    if gb <= 1.5 and trend in ("fragile", "slipping"):
        pressure = "high"
    elif gb <= 3.0 or (trend in ("fragile", "slipping") and gb <= 5.0):
        pressure = "building"
    else:
        pressure = "low"

    last_result = (last_game or {}).get("result", "")
    game_date   = (last_game or {}).get("date", "")
    game_emotion_level = classify_game_emotion(last_game)

    return {
        "trend":              trend,
        "driver":             driver,
        "confidence":         confidence,
        "pressure":           pressure,
        "record_w":           rec_w,
        "record_l":           rec_l,
        "streak":             streak,
        "last10_w":           last10_w,
        "era":                round(era_val, 2),
        "ops":                round(ops_val, 3),
        "gb":                 gb,
        "division_rank":      division_rank,
        "last_result":        last_result,
        "date":               game_date,
        "game_emotion_level": game_emotion_level,
    }


def load_story_state(path):
    """Load previous story state from disk, or return None."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_story_state(state, path):
    Path(path).write_text(json.dumps(state, indent=2))


# ---------------------------------------------------------------------------
# Story Delta
# ---------------------------------------------------------------------------

def compute_story_delta(prev, curr):
    """
    Compare previous and current story states.
    Returns a delta dict with human-readable signals list.
    """
    if not prev:
        return {
            "has_prev":         False,
            "trend_changed":    False,
            "trend_direction":  "unknown",
            "conf_changed":     False,
            "pressure_changed": False,
            "driver_changed":   False,
            "signals":          ["First tracked game — establishing baseline narrative."],
        }

    signals = []

    trend_changed = prev.get("trend") != curr.get("trend")
    trend_direction = "unchanged"
    if trend_changed:
        pv = _TREND_ORDER.get(prev["trend"], 2)
        cv = _TREND_ORDER.get(curr["trend"], 2)
        trend_direction = "improved" if cv > pv else "declined"
        signals.append(f"trend {trend_direction}: {prev['trend']} → {curr['trend']}")

    conf_changed = prev.get("confidence") != curr.get("confidence")
    if conf_changed:
        direction = "up" if _CONF_ORDER.get(curr["confidence"], 2) > _CONF_ORDER.get(prev["confidence"], 2) else "down"
        signals.append(f"confidence {direction}: {prev['confidence']} → {curr['confidence']}")

    pressure_changed = prev.get("pressure") != curr.get("pressure")
    if pressure_changed:
        direction = "increased" if _PRESSURE_ORDER.get(curr["pressure"], 2) > _PRESSURE_ORDER.get(prev["pressure"], 2) else "decreased"
        signals.append(f"pressure {direction}: {prev['pressure']} → {curr['pressure']}")

    driver_changed = prev.get("driver") != curr.get("driver")
    if driver_changed:
        signals.append(f"driver shifted: {prev['driver']} → {curr['driver']}")

    last_result = curr.get("last_result", "")
    if last_result == "W":
        signals.append("won last game")
    elif last_result == "L":
        signals.append("lost last game")

    prev_streak = prev.get("streak", "")
    curr_streak = curr.get("streak", "")
    if prev_streak != curr_streak:
        pm = re.match(r'^([WL])(\d+)$', prev_streak)
        cm = re.match(r'^([WL])(\d+)$', curr_streak)
        if pm and cm:
            if pm.group(1) != cm.group(1):
                signals.append(f"streak flipped: {prev_streak} → {curr_streak}")
            elif cm.group(1) == "W" and int(cm.group(2)) > int(pm.group(2)):
                signals.append(f"win streak extended to {curr_streak}")

    era_delta = round(curr.get("era", 4.0) - prev.get("era", 4.0), 2)
    ops_delta = round(curr.get("ops", 0.7) - prev.get("ops", 0.7), 3)
    if abs(era_delta) >= 0.05:
        direction = "improved" if era_delta < 0 else "worsened"
        signals.append(f"ERA {direction}: {prev['era']:.2f} → {curr['era']:.2f}")
    if abs(ops_delta) >= 0.010:
        direction = "up" if ops_delta > 0 else "down"
        signals.append(f"OPS {direction}: {prev['ops']:.3f} → {curr['ops']:.3f}")

    gb_delta = round(curr.get("gb", 0.0) - prev.get("gb", 0.0), 1)
    if abs(gb_delta) >= 0.5:
        direction = "gained" if gb_delta < 0 else "fell back"
        signals.append(
            f"division gap: {direction} {abs(gb_delta):.1f} game(s) ({curr['gb']} back)"
        )

    if not signals:
        signals.append("narrative unchanged — same trend, driver, and pressure as yesterday")

    return {
        "has_prev":         True,
        "trend_changed":    trend_changed,
        "trend_direction":  trend_direction,
        "conf_changed":     conf_changed,
        "pressure_changed": pressure_changed,
        "driver_changed":   driver_changed,
        "signals":          signals,
    }


# ---------------------------------------------------------------------------
# Story Threads — lightweight recurring narrative tags (internal, not rendered)
# ---------------------------------------------------------------------------

def build_story_threads(story_state, last_game):
    """
    Derive lightweight recurring story threads from current state and game.
    Returns a list of short thread labels used internally by the narrative engine.
    Not rendered on page. Capped at 4 threads.
    """
    threads = []

    driver   = story_state.get("driver", "")
    ops      = story_state.get("ops", 0.720)
    emotion  = story_state.get("game_emotion_level", "normal")
    trend    = story_state.get("trend", "")
    pressure = story_state.get("pressure", "low")
    streak   = story_state.get("streak", "")

    if driver == "pitching" and ops < 0.710:
        threads.append("pitching carrying quiet offense")

    if driver == "balanced" and trend == "surging":
        threads.append("both sides clicking")

    if emotion in ("high", "extreme"):
        lg = last_game or {}
        clutch = lg.get("clutch_player")
        if clutch and clutch.get("confidence") == "high":
            inn = clutch.get("inning") or 0
            if inn >= 7:
                threads.append("late-inning rallies")

    if pressure in ("building", "high"):
        threads.append("division pressure")

    if emotion in ("high", "extreme"):
        lg = last_game or {}
        clutch = lg.get("clutch_player")
        key_hitters = lg.get("key_hitters") or []
        if (clutch and clutch.get("confidence") == "high" and key_hitters
                and clutch.get("name") != key_hitters[0].get("name")):
            threads.append("clutch role players")

    m = re.match(r'^W(\d+)$', streak)
    if m and int(m.group(1)) >= 3:
        threads.append("win streak momentum")

    if trend in ("slipping", "fragile"):
        threads.append("inconsistency")

    return threads[:4]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_DEFICIT_WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven"}


def _compute_max_deficit(last_game):
    """Return the largest run deficit the team faced during the game (0 if never trailing)."""
    if not last_game:
        return 0
    linescore = last_game.get("linescore") or [[], []]

    def _to_int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    sd_inn  = [_to_int(v) for v in (linescore[0] if linescore else [])]
    opp_inn = [_to_int(v) for v in (linescore[1] if len(linescore) > 1 else [])]
    n = min(len(sd_inn), len(opp_inn))
    if n == 0:
        return 0
    sd_cum  = [sum(sd_inn[:i + 1]) for i in range(n)]
    opp_cum = [sum(opp_inn[:i + 1]) for i in range(n)]
    return max((opp_cum[i] - sd_cum[i] for i in range(n)), default=0)


# ---------------------------------------------------------------------------
# Story Hook — one-sentence emotional framing for the masthead
# ---------------------------------------------------------------------------

def build_story_hook(story_state, last_game, story_threads=None, game_driver=None):
    """
    Generate a one-sentence emotional story hook for placement below the subhead.

    Returns empty string when game_emotion_level is 'normal' or no strong hook
    is warranted. All hooks are grounded in actual game data.

    Rules:
    - Specific and textured — no generic lines ("Big win", "They found a way")
    - One sentence max
    - When game_driver and clutch_player are different, name both
    - Should preview the tension explored later in State of Play
    """
    emotion = story_state.get("game_emotion_level", "normal")
    if emotion == "normal":
        return ""

    if not last_game:
        return ""

    result  = last_game.get("result", "")
    clutch  = last_game.get("clutch_player")
    threads = story_threads or []

    def _to_int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    linescore   = last_game.get("linescore") or [[], []]
    sd_inn      = [_to_int(v) for v in (linescore[0] if linescore else [])]
    opp_inn     = [_to_int(v) for v in (linescore[1] if len(linescore) > 1 else [])]
    is_home     = last_game.get("home", False)
    num_innings = len(sd_inn)
    late_runs   = sum(sd_inn[8:]) if len(sd_inn) > 8 else 0
    max_deficit = _compute_max_deficit(last_game)

    is_walkoff = (
        result == "W" and is_home and num_innings >= 9
        and len(sd_inn) == len(opp_inn)
        and sd_inn[-1] > 0
    )

    clutch_last        = ""
    clutch_event_lower = ""
    clutch_reason      = ""
    if clutch and clutch.get("confidence") == "high":
        name = clutch.get("name", "")
        parts = name.split()
        clutch_last       = parts[-1] if (len(parts) >= 2 and parts[-1] != "Jr.") else name
        clutch_event_lower = (clutch.get("event") or "").lower()
        clutch_reason      = (clutch.get("reason") or "").lower()

    # Game driver context — only use when high/medium confidence
    driver_last  = ""
    driver_hr    = 0
    driver_conf  = ""
    driver_name  = ""
    if game_driver and game_driver.get("confidence") in ("high", "medium"):
        driver_name = game_driver.get("name", "")
        driver_conf = game_driver.get("confidence", "")
        dparts = driver_name.split()
        driver_last = dparts[-1] if (len(dparts) >= 2 and dparts[-1] not in ("Jr.", "Sr.")) else driver_name
        m = re.search(r'(\d+)-HR', game_driver.get("reason") or "")
        driver_hr = int(m.group(1)) if m else 0

    # Determine if we have two distinct players to name
    has_dual = (
        driver_last
        and clutch_last
        and driver_name != (clutch or {}).get("name", "")
    )

    if result == "W":
        if is_walkoff:
            if has_dual:
                return (f"{driver_last} powered the offense; {clutch_last} ended it.")
            if clutch_last:
                return f"The box score changed in one swing — {clutch_last} ended the debate."
            return "One swing rewrote the scoreboard. This team is learning when to bide its time."

        if max_deficit >= 4:
            _n = _DEFICIT_WORDS.get(max_deficit, str(max_deficit))
            if has_dual and driver_hr >= 2:
                return (f"Down {_n} — {driver_last} kept them alive, "
                        f"{clutch_last} finished the climb.")
            if has_dual:
                return (f"Down {_n} — {driver_last} supplied the power, "
                        f"{clutch_last} delivered the turn.")
            if clutch_last:
                return f"Down {_n} — {clutch_last}'s {clutch_event_lower} was the turn."
            return f"Down {_n} and still standing — this team found a way back."

        if late_runs >= 5:
            if has_dual:
                return (f"A quiet game until it wasn't — {driver_last} did the damage, "
                        f"{clutch_last}'s {clutch_event_lower} sealed it.")
            if clutch_last:
                return (f"A quiet game until it wasn't — {clutch_last}'s {clutch_event_lower}"
                        f" was the inning everyone will remember.")
            return "The box score says win; the inning chart says escape."

        if max_deficit >= 2:
            _n = _DEFICIT_WORDS.get(max_deficit, str(max_deficit))
            if has_dual:
                return (f"Down {_n} — {driver_last} powered them back, "
                        f"{clutch_last} finished the job.")
            if clutch_last:
                return f"Down {_n} — {clutch_last} delivered the play that mattered."
            return "They trailed and found a way — this team has learned to survive ugly games."

        if "pitching carrying quiet offense" in threads:
            if has_dual:
                return f"The pitching held the door open; {driver_last} and {clutch_last} walked through it."
            if clutch_last:
                return f"The pitching held the door open; {clutch_last} walked through it."

        if emotion == "high":
            if has_dual:
                return f"{driver_last} powered it; {clutch_last} finished it."
            if clutch_last:
                return f"{clutch_last} delivered the swing that changed the game's shape."

    elif result == "L":
        if emotion == "extreme":
            return "The loss stings more for how close it came — a game that revealed as much as it cost."
        if emotion == "high":
            return "They had the moments. They didn't have the finish."

    return ""


# ---------------------------------------------------------------------------
# Narrative generation — Claude writes from structured context
# ---------------------------------------------------------------------------

def _build_narrative_system(team_name):
    return (
        f"You are the editorial voice of the {team_name} Morning Brief — "
        "a daily dispatch that answers: \"What changed about the team's story today?\"\n\n"
        "You take editorial stances. You explain *why* something matters, not just *what* happened. "
        "You write for a fan who already knows the score and wants to understand what it means."
    )


def _build_narrative_prompt(brief_data, story_state, delta, team_name,
                            story_threads=None, story_hook=None, looking_ahead_hook=None,
                            game_driver=None):
    team      = brief_data["team"]
    last_game = brief_data.get("last_game") or {}
    next_game = brief_data.get("next_game") or {}

    delta_lines = "\n".join(f"  - {s}" for s in delta.get("signals", []))

    kp = last_game.get("key_pitcher") or {}
    kh = last_game.get("key_hitters") or []
    pitcher_text = (
        f"{kp.get('name')} — {kp.get('line')} (season ERA: {kp.get('season_era', '?')})"
        if kp else "N/A"
    )
    hitters_text = (
        "; ".join(f"{h['name']} {h['line']}" for h in kh)
        if kh else "N/A"
    )

    ng_prob = next_game.get("probable") or {}
    next_text = (
        f"vs {next_game.get('opponent')} on {next_game.get('date')} at "
        f"{next_game.get('time_local', 'TBD')}. SP: {ng_prob.get('team', 'TBD')}"
        if next_game else "N/A"
    )

    score = last_game.get("score") or {}
    result_line = (
        f"{last_game.get('result', '?')} "
        f"{score.get('team', '?')}–{score.get('opp', '?')} "
        f"vs {last_game.get('opponent', '?')} · {last_game.get('context_line', '')}"
    )

    batting = (last_game.get("full_box") or {}).get("batting") or []
    team_hits = sum(b.get("h", 0) for b in batting)
    team_ks   = sum(b.get("so", 0) for b in batting)
    offense_note = f"{team_hits} hits, {team_ks} strikeouts" if batting else ""

    # Clutch moment context (deterministic, from play-by-play)
    clutch = last_game.get("clutch_player")
    if clutch and clutch.get("confidence") == "high":
        clutch_block = (
            f"\nTURNING POINT (play-by-play, HIGH CONFIDENCE):\n"
            f"  {clutch['name']} — {clutch['event']}, inning {clutch['inning']}\n"
            f"  {clutch['name']} {clutch['description']}\n"
            f"  Reason: {clutch['reason']}"
        )
    elif clutch and clutch.get("confidence") == "low":
        clutch_block = (
            f"\nTURNING POINT (fallback — box score only, LOW CONFIDENCE):\n"
            f"  {clutch['name']}: {clutch['event']}\n"
            f"  Do NOT anchor the narrative on this player."
        )
    else:
        clutch_block = "\nTURNING POINT: none detected"

    # Game driver context (deterministic, from box score)
    # Enhance description to be role-based and game-aware when context allows
    gd = game_driver or last_game.get("game_driver")
    if gd and gd.get("confidence") in ("high", "medium"):
        gd_desc = gd.get("description", "")
        max_def = _compute_max_deficit(last_game)
        if (gd.get("type") == "hitter"
                and "HR" in gd.get("reason", "")
                and last_game.get("result") == "W"):
            hr_m = re.search(r'(\d+)-HR', gd["reason"])
            hr_n = int(hr_m.group(1)) if hr_m else 2
            if max_def >= 3:
                gd_desc = f"kept the offense alive with {hr_n} home runs."
            else:
                gd_desc = f"supplied the lineup's power with {hr_n} home runs."
        game_driver_block = (
            f"\nGAME DRIVER (overall performance that most shaped the game, {gd['confidence'].upper()} CONFIDENCE):\n"
            f"  {gd['name']} — {gd['reason']}\n"
            f"  {gd['name']} {gd_desc}"
        )
    else:
        game_driver_block = "\nGAME DRIVER: none detected"

    emotion = story_state.get("game_emotion_level", "normal")
    if emotion == "extreme":
        voice_block = """VOICE — EXTREME EMOTION (game_emotion_level: extreme):
- TOP FRAME must open with the dramatic event. Make the moment feel real and earned — not hyped.
- WHAT THIS GAME MEANS: be vivid. Lead with the emotional core of what happened, then connect it back to the larger team narrative.
- Genuine energy is appropriate. But stay editorial. No all-caps, no exclamation marks, no manufactured urgency.
- Earned emotion comes from the game situation itself — late rally, blown lead, walk-off, big comeback, dominant pitching, gutty escape. Let the situation carry the weight. Do not narrate the feeling; show it through the facts.
- Forbidden phrases: "for the ages", "absolute madness", "unbelievable scenes", "one they'll never forget", "chaos", "mayhem"."""
    elif emotion == "high":
        voice_block = """VOICE — HIGH EMOTION (game_emotion_level: high):
- TOP FRAME should acknowledge the key game event — the go-ahead run, the comeback, the dominant individual performance.
- WHAT THIS GAME MEANS: open with what happened, then zoom out to what it signals about this team right now.
- Show more feeling where the game earns it — late rally, comeback, dominant pitching, gutty escape. Do not manufacture drama where the game does not warrant it.
- Some energy is appropriate but stay controlled. Analytical precision should still come through."""
    else:
        voice_block = """VOICE — NORMAL (game_emotion_level: normal):
- Lead with pattern and meaning, not game events. The editorial stance is the value.
- Stay calm, analytical, and grounded. Do not manufacture drama from a routine result."""

    # Team voice profile — team-specific editorial filter applied on top of general voice rules
    if team_name == "Padres":
        team_voice_block = """TEAM VOICE PROFILE — PADRES (apply subtly, do NOT announce):
Identity: gritty, resourceful, slightly suspicious of their own success. Wins feel earned, not assumed.

Language to lean into (1–2 uses per brief, not every sentence):
  "scratched out" / "just enough" / "held up" / "didn't break" / "thin margin"

Editorial bias:
- Trust the pitching more than the offense
- Stay skeptical of whether the bats can sustain what the staff sets up
- Treat close wins as earned, but fragile — not as confirmation of excellence

Sentence feel: slightly physical, grounded, a little scrappy. Understated rather than grand.
Reference vibe: "They didn't have much. They had enough."

Application rules:
- 1–2 word choices or sentence rhythm shifts only. Not an entire costume.
- Do not announce or name the voice.
- Game truth still wins over voice consistency."""
    elif team_name == "Yankees":
        team_voice_block = """TEAM VOICE PROFILE — YANKEES (apply subtly, do NOT announce):
Identity: expectation-heavy, analytical, impatient with avoidable failure. Wins are expected; losses demand explanation.

Language to lean into (1–2 uses per brief, not every sentence):
  "should have" / "margin" / "cost" / "threshold" / "exposed" / "standard"

Editorial bias:
- Hold the team to a higher baseline expectation
- Be less forgiving of sloppy, avoidable losses
- When something fails, name what failed to meet the standard

Sentence feel: cleaner, sharper, slightly colder, more evaluative than warm.
Reference vibe: "They had the game. They didn't finish it."

Application rules:
- 1–2 word choices or sentence rhythm shifts only. Not an entire costume.
- Do not announce or name the voice.
- Game truth still wins over voice consistency."""
    else:
        team_voice_block = ""

    # Story threads + hook context
    threads_text = (
        "  " + "\n  ".join(story_threads)
        if story_threads else "  none detected"
    )
    story_hook_line = story_hook or "none"

    # Looking ahead hook — from brief_data if not passed explicitly
    if not looking_ahead_hook:
        ng = brief_data.get("next_game") or {}
        looking_ahead_hook = ng.get("insight", "")
    looking_ahead_line = looking_ahead_hook or "see next game context above"

    return f"""Write the editorial core of today's {team_name} Morning Brief.

--- STRUCTURED CONTEXT ---

STORY STATE (today):
  Trend:              {story_state['trend']}
  Driver:             {story_state['driver']}
  Confidence:         {story_state['confidence']}
  Pressure:           {story_state['pressure']}
  Game Emotion Level: {emotion}

STORY DELTA (what changed vs. yesterday):
{delta_lines}

STORY THREADS (recurring themes — stay consistent with what the season is about):
{threads_text}

STORY HOOK (emotional compression — already rendered above the brief; do NOT repeat or paraphrase it):
  {story_hook_line}
  This hook already handled: situation + turn, compressed to one line. Your TOP FRAME picks up from that emotional beat — it does not retread it.

LAST GAME:
  Result:      {result_line}
  Key pitcher: {pitcher_text}
  Key hitters: {hitters_text}
  Offense:     {offense_note}
{game_driver_block}
{clutch_block}

TEAM CONTEXT:
  Record: {team.get('record')} · Streak: {team.get('streak')} · Last 10: {team.get('last10')}
  ERA: {team.get('era')} · OPS: {team.get('ops')} · Avg: {team.get('avg')}
  Division: Rank {team.get('division_rank')} · {team.get('games_back')} back

NEXT GAME:
  {next_text}

TONIGHT'S HOOK (for WHAT TO WATCH — connect to this specific tension):
  {looking_ahead_line}

--- OUTPUT INSTRUCTIONS ---

TONAL MODE (internal — do NOT output or name this):
Before writing, select one mode based on the game. Let it shape word choice and sentence feel — do not announce it.

  CLINICAL   → routine win or loss, no strong swing either way
  GRITTY     → close game, comeback, ugly win, survival
  DOMINANT   → blowout or an overpowering individual performance
  FRAGILE    → win or loss that exposes a real weakness
  CHAOTIC    → wild swings, high-scoring, genuinely weird game

The mode is felt in rhythm and word choice, not stated. One or two choices that fit the game — not every sentence.

PRIMARY LENS (internal — do NOT output or name this):
Before writing WHAT THIS GAME MEANS, select ONE lens. Let it drive the section — do not try to cover multiple.

  IDENTITY  → what this team is becoming
  TENSION   → what is unstable, what could break
  PLAYER    → who defined this game and why it matters beyond the box score
  SYSTEM    → how the team is winning structurally
  CONTEXT   → opponent, environment, or situation shaping the result

The lens is not a label. It is the angle of argument — the question the section is answering.

Write exactly three sections. No headers. No labels. No bullet points. Just clean prose.

1. TOP FRAME (1 sentence, max 18 words)
Job: the editorial stance — not emotional compression (the story hook did that), not recap, not preview. ONE idea only. Choose exactly one of:
  - the situation ("Down four…")
  - the outcome ("They didn't fold.")
  - the identity claim ("This team doesn't fold.")
Do NOT include both players and conclusion. Do NOT list multiple events. If more than one clause appears, simplify to one.
Emotionally clear. Do NOT include both Game Driver and Turning Point in the same sentence. Not a score recap. A stance.
Do NOT repeat or rephrase the story hook in different words — that section already handled the compressed emotional beat.

Good: "Down four—and they didn't blink." / "This team doesn't fold." / "They had no business winning this game."
Avoid: multi-clause sentences, listing multiple players, explaining the sequence of events, restating the story hook.

2. WHAT THIS GAME MEANS (90–120 words max)
Job: interpretation and identity claim — not factual recap, not sequence retelling. The game_note already handled the vivid factual summary. The Game Driver and Turning Point are already shown as memory anchors. Your job is to answer: What does this game reveal about who this team is?

Do NOT restate the story_hook, game_note, Game Driver, or Turning Point — those facts are displayed separately and the reader already has them. Instead, answer: What is different about this team today because of this game? Use the STORY DELTA to identify one clear thing that changed — the pattern got louder, the margin for error shifted, a weakness became harder to ignore, a strength carried into a new kind of win, or the formula held in a new situation. Reference the Game Driver or Turning Point briefly if it supports the "what changed" answer — but do not retell the sequence. Connect the game to the team's current trend. Be precise.

Prefer one strong thesis over several smaller observations. One claim argued well is more memorable than three things that happened. Build to your identity sentence — do not spread the argument thin.

Make a clear claim about the team's identity. The section must include at least one sentence that could stand alone as an editorial take — something that answers "what is this team becoming?" or "what does this game reveal about how they win?" Frame it as a pattern, not a moment. Acceptable forms: "This is a team that...", "The pattern has become...", "They are now...", "This works because...", "This breaks if...". Weave at least one STORY THREAD naturally into the section — do not list it or name it explicitly; let it shape the argument.

The section must also include at least one short, memorable sentence under 12 words that captures the core takeaway. It must stand alone as its own sentence — do not bury it mid-paragraph. Place it as either the first sentence of this section OR the final sentence. Examples: "They needed a swing — France gave them two." / "This only works until it doesn't." / "They're winning on margins that don't last."

Use plain, direct fan language. Replace analytical constructions ("this represents", "this illustrates") with concrete statements ("they needed it", "he delivered", "that was the game"). Avoid academic tone, over-qualification, and unnecessary metaphors.

SENTENCE RHYTHM: Vary sentence length. Mix short punchy lines with medium explanatory sentences. Do not stack multiple one-liners in a row — short sentences land as emphasis, not as a style unto themselves.

Do not over-explain the thesis.
State the idea once, clearly, then support it with one concrete example.

Avoid repeating the same concept in multiple forms.
Trust the reader to carry the idea forward.

3. WHAT TO WATCH (1–2 sentences max, under 45 words)
Job: carry one unresolved tension forward — not a schedule preview, not a generic pregame note. The tension must grow directly out of WHAT THIS GAME MEANS, not introduce a new topic. Make tonight feel like the next chapter of the same story.
Express one clear tension. Avoid multi-clause sentences and abstract phrasing.
Preferred openers: "Now the question is…" / "Tonight will show…" / "The next test is…"
Answer: what tension from today's story continues into tonight? Name the open question that tonight's game will test. Use TONIGHT'S HOOK as context — do NOT quote its stat or restate it. Translate it into narrative tension. Write like the story is still moving, not like a preview.
Avoid broadcast-preview phrasing ("can they keep it going?", "looking to build on", "they'll need"). Frame it as an unresolved question from the argument you just made in WHAT THIS GAME MEANS.

GAME FLOW REALISM:
Write as if you watched the game unfold — not as if you're summarizing a box score.

Anchor the narrative in how the game moved:
* When did it break?
* When did it feel over?
* When did it shift?
* Was it tight late or decided early?

Prefer:
* "They were chasing after the second."
* "The game got away in one inning."
* "They never recovered from that stretch."

Avoid:
* Abstract sequencing ("over the course of the game…")
* Full inning-by-inning recounting

Pattern to follow:
Moment → Meaning → Implication

Not:
Summary → Explanation → Restatement

SMART-FAN VOICE:
Write like someone who watched the game and understands this team's ongoing story. Favor concrete baseball language over generic analysis. Use phrases that feel lived-in and specific, not polished and empty.

Personality allowed: dry understatement, mild edge, concise judgment, fan-aware phrasing.
Personality to avoid: sports-radio clichés, exaggerated doom, fake hype, academic phrasing, generic motivational language.

CLAUSE CONTROL:
Avoid stacking multiple clauses in a single sentence.

Prefer:
* One idea per sentence
* Occasional short sentences for emphasis

Break sentences instead of extending them.

Example:
Instead of:
"Gil struggled early and Houston took advantage and the Yankees never recovered"

Write:
"Gil struggled early. Houston took advantage. They never recovered."

{team_voice_block}

LANGUAGE TIGHTENING:
Prefer shorter phrasing over clever phrasing. Fewer clauses, fewer metaphors, no semicolon constructions that explain themselves ("not a breakout; it was a necessity meeting opportunity"). Write the direct version instead.

ANTI-GENERIC LANGUAGE:
Avoid phrases that summarize broadly without adding a specific angle or judgment.

Do NOT write:
- "the inconsistency that has defined the season"
- "this team has struggled with..."
- "they have shown flashes but..."
- "the season has been up and down"

Force specificity tied to THIS game instead:
  ❌ "the inconsistency that's defined the season got louder"
  ✅ "they needed one clean inning — they didn't get it"
  ✅ "the same problem showed up again, just louder"

  ❌ "this team has struggled to finish games"
  ✅ "they had the game — they didn't finish it"

Every sentence must do at least one of:
  1. Make a claim about TODAY'S game
  2. Extend a CURRENT thread
  3. Make a specific judgment

If it does none of the above → rewrite or cut.

TONAL VARIATION:
Let the game type shape the writing — subtly, not conspicuously.
  GRITTY     → shorter sentences, physical verbs ("held on", "scratched out", "didn't break", "survived")
  DOMINANT   → confident, declarative ("they controlled this game", "this wasn't close")
  FRAGILE    → tension, skepticism in reserve ("this works until it doesn't", "the margin is real")
  CHAOTIC    → slightly more energy, irregular rhythm, comma-sparse sentences
  CLINICAL   → plain, even, no added heat — let the facts do the work
Do not overdo this. The shift should be felt across 2–3 word choices, not performed as a style.

SENTENCE VARIATION:
Avoid the same opening structure day after day.
- Do not always start TOP FRAME with "This team…"
- Do not always anchor WHAT THIS GAME MEANS with "The pattern is…"
- Vary sentence length, clause order, and paragraph shape.
Natural variation only — do not force novelty. Clarity first, variety second.

PHRASE VARIATION — IDENTITY CLAIMS:
Avoid reusing the same sentence structure or phrasing for identity claims across outputs.

If a sentence feels like a "perfect summary line" (e.g. "the formula broke when it mattered most"), treat it as one valid expression — not the default.

Do NOT recycle these constructions:
- "the formula broke"
- "this is the cost of..."
- "this works until it doesn't"

Vary the angle instead:
  outcome   → "they had the game — they didn't finish it"
  cause     → "it unraveled in the second inning"
  threshold → "this is where the margin disappears"
  structure → "this kind of game doesn't survive early damage"
  judgment  → "this isn't good enough to win in this division"

Each identity claim should feel like a fresh angle on the same truth — not the same sentence reused.
Clarity over novelty. Do not force cleverness — just avoid duplication.

PLAYER LANGUAGE VARIATION:
When naming a player's contribution, vary the construction.
Avoid always using the same verb frame ("France delivered", "Laureano finished").
Allow: "France gave them a chance", "Laureano was the swing that mattered", "France was the only reason they were still in it", "that was Laureano's moment".
Vary phrasing across sections. Do not repeat the same verb for the same player.

BULLPEN AWARENESS:
The bullpen is part of the story — not optional context.

When relevant, include how the game was finished:

Look for:
* Shutdown relief (clean innings, preserved lead)
* Collapse (blew lead, gave game away)
* Bridge moments (middle relief holding a fragile game)
* Closer leverage (tight 9th, pressure outs)

Examples:
* "The bullpen held the line from there."
* "They handed it to the bullpen and it stuck."
* "The lead didn't survive the middle innings."
* "That game was over once it reached the back end."

Do NOT force bullpen mention if irrelevant.

But if:
* Starter exits early
* Game is close late
* Lead changes hands after the 6th

→ bullpen should be part of the explanation.

Closers and high-leverage relievers (e.g. dominant arms) should be named when they define the outcome.

If a reliever or closer has repeatedly protected narrow leads, locked down late innings, or appeared in high-leverage spots across recent games, treat that as a possible player arc — not just a today observation.
Examples:
* "The back end of the bullpen is becoming where games are decided."
* "The bridge to the ninth is starting to look like the real separator."
* "The bullpen didn't just survive the game; it defined the finish."

PLAYER ARC AWARENESS (internal — do NOT output arc labels):
When a player appears repeatedly in meaningful moments, treat them as an evolving story — not a one-off stat line.

Use available context to detect arc potential:
- Same player named as both GAME DRIVER and TURNING POINT today → strongest single-game signal
- A player appearing in STORY THREADS as a recurring presence (e.g. "clutch role players", "pitching carrying quiet offense")
- STORY DELTA showing a performance pattern that is shifting the team's trend

Arc types (internal framing only — never output the label):
  ASCENDING    → player becoming more important; recent impact is increasing
  CARRYING     → team depending on them heavily; repeated high production or high-leverage usage
  FRAGILE      → current success looks hard to sustain — volatile or thin margin
  SLIPPING     → trend moving the wrong direction; repeated missed chances or failed outings
  STABILIZING  → player bringing order to chaos; fits bullpen arms, veteran bats, defensive anchors

How to write arc language (only when evidence supports it):
  "is becoming…" / "is starting to look like…" / "keeps showing up…"
  "is carrying…" / "is stabilizing…" / "is slipping…"

Constraints:
- Do NOT pretend one good game is a trend
- Do NOT force arc language every day
- Do NOT turn every key hitter into a storyline
- Only use arc language when the pattern is visible or strongly suggested by available context
- STORY THREADS are the primary arc memory available — read them as arc signals
- When a thread recurs (e.g. "clutch role players"), the player associated with it is a candidate for arc framing

DATA NOTE: No multi-game player arc history is passed in this prompt. Use STORY THREADS and STORY DELTA as proxies. Future versions may include a player arc history object for stronger arc memory across 5–7 games.

STORY THREAD CONTINUITY:
WHAT THIS GAME MEANS should reinforce or evolve at least one active STORY THREAD when the game supports it. Do not introduce a new storyline unless today's game clearly creates one.

Prefer these thread movements:
  continuation   → the pattern held again
  escalation     → this is becoming more pronounced
  challenge      → this is where the pattern breaks
  confirmation   → this wasn't a one-off

When a thread recurs across days, move it along its natural arc:
  early stage    → observation ("this might be a pattern")
  middle stage   → reinforcement ("this is holding")
  later stage    → conclusion ("this is who they are now")
The thread's stage should feel earned from context — do not force advancement.

Continuity language (use when natural, not as filler):
  "again" / "still" / "once more" / "this continues" / "this is becoming" / "this is starting to look like"

Do not restate the same thread in identical language across days. If a thread recurs, vary the framing, wording, or angle — use a different PRIMARY LENS if needed. Repetition without progression is drift, not continuity.

Not every game must advance a thread. If the game does not materially change the narrative, allow the thread to hold — do not force progression, escalation, or conclusion.

Only advance a thread if the game meaningfully shifts at least one of:
  - margin         → the win/loss was closer or wider than the pattern suggests
  - dependency     → one player carried vs. balanced contribution (or vice versa)
  - repeatability  → pattern held under a new or harder condition
  - pressure       → division stakes, late-inning situation, or opponent quality added weight

If none of these shift, prefer holding. Valid hold outcomes:
  hold               → "nothing new, pattern unchanged"
  light reinforcement → "this looked similar, but didn't add new information"

Holding language (use when appropriate, not reflexively):
  "nothing new here" / "this looked familiar" / "the same pattern, no stronger" / "no new signal yet"

HOLD / ADVANCE BALANCE:
Across a 3–5 game window, avoid all HOLD or all ADVANCE outcomes.
- If the last 2 games held, prefer advancing when a signal is even mildly present.
- If the last 2 games advanced, require a clearer signal to advance again.
This is a bias, not a rule. Game truth still overrides.

HOLD DAY MICRO-UPDATE:
On HOLD days, include one small new detail that did not appear yesterday — a different reliever used, a lineup spot producing, a defensive play, a matchup nuance, or a different player carrying the same thread. One clause only. Do not escalate the main thread unless a real signal changed.

NARRATIVE LENS:
WHAT THIS GAME MEANS should be driven by one dominant lens. Do not cover multiple — pick the one that best fits the game and argue it.

  IDENTITY  → "This is a team that…" / "They are becoming…"
  TENSION   → "This works until…" / "The margin is…"
  PLAYER    → "France's night matters because…" / "That was Laureano's game to carry…"
  SYSTEM    → "The formula is…" / "They won because the structure held…"
  CONTEXT   → "This happened because…" / "The opponent exposed…" / "The environment forced…"

Do not default to IDENTITY every game. Identity claims should appear often, but not reflexively. When the game is better explained by TENSION, PLAYER, SYSTEM, or CONTEXT, use that lens instead.

LENS MEMORY (cross-day variation):
Avoid using the same lens on consecutive days unless the game strongly demands it.
The STORY DELTA and prior story state carry implicit context about what angle drove yesterday's narrative. If the recent pattern suggests IDENTITY was used yesterday, prefer a different lens today unless today's game makes IDENTITY unavoidable.
If no prior context is available, proceed normally.

LENS DISTRIBUTION (balancing instinct, not a quota):
Across multiple days, aim for a natural mix:
  IDENTITY  → appears often, not dominant
  TENSION   → after fragile wins, narrow margins, or exposed weaknesses
  SYSTEM    → after repeated similar wins where the formula, not the player, is the story
  PLAYER    → when one performance clearly defined the game beyond the box score
  CONTEXT   → for unusual opponents, environments, or situations shaping the result
This is not a rotation. It is an editorial instinct — the same lens two days in a row is a signal to look for a different angle.

LENS OVERRIDE:
Game truth always wins. If the game strongly demands a specific lens — extreme comeback, dominant shutdown, a player who carried the team alone — use that lens regardless of distribution guidance. Do not force variety at the cost of accuracy.

LENS AND TONAL MODE ALIGNMENT (guide, not constraint):
  GRITTY     → lean toward PLAYER or TENSION
  DOMINANT   → lean toward SYSTEM or IDENTITY
  FRAGILE    → lean toward TENSION
  CHAOTIC    → lean toward CONTEXT or PLAYER
  CLINICAL   → lean toward SYSTEM

These are tendencies. Override when the game warrants it.

{voice_block}

HARD RULES:
- LAYERING: Each section must add a new layer. Do not let the same sentence idea appear across story_hook, TOP FRAME, WHAT THIS GAME MEANS, and WHAT TO WATCH. If you find yourself writing the same point in different words, cut it from all but the section where it belongs.
- PLAYER MENTIONS ACROSS SECTIONS: If the same player appears in multiple sections, each mention must serve a different purpose — hook = emotional shorthand; TOP FRAME = stance; WHAT THIS GAME MEANS = meaning or pattern; WHAT TO WATCH = continuation or tension. Do not use the same framing twice for the same player.
- GAME DRIVER and TURNING POINT are memory anchors already displayed to the reader. Player name + role + moment is enough when you reference them. Do not over-write them in WHAT THIS GAME MEANS — your thesis is the editorial layer, not a retelling of the play.
- Do NOT summarize the game. The reader already knows the score.
- Do NOT repeat yesterday's framing unless the delta shows nothing changed — if so, say that directly.
- Do NOT use: "bats need to wake up", "must-win", "firing on all cylinders", "big time", "impressive", "heading into", "looking to", "resilience", "found a way".
- Do NOT speculate with "could" or "might". Extrapolate from what IS happening.
- Use specific stats from the context above. Do not invent numbers.
- Take a clear editorial stance. Use active voice.
- WHAT THIS GAME MEANS must be 90–120 words. Tight. Name what changed. Do NOT exceed 120 words.
- WHAT THIS GAME MEANS must NOT simply restate the story_hook, game_note, Game Driver, or Turning Point. These sections are already displayed separately. Build on them — do not repeat them.
- WHAT TO WATCH must be 1–2 sentences, under 45 words. Express one tension. Do NOT quote or restate the TONIGHT'S HOOK stat — translate it into narrative tension.
- If trend is "surging": the question is how long can this hold?
- If trend is "fragile" or "slipping": be honest about the problem. Do not soften it.
- If driver is "pitching" and OPS < 0.700: do not frame the offense as fine.
- If delta signals show no change: acknowledge the story did not move today and say what that means.
- LATE-INNING WEIGHT: Late innings (6th–9th) carry more narrative importance than early innings. If the game turned late, anchor the story there. Early-game events should only matter if they defined the outcome.
- GAME DRIVER vs TURNING POINT: These are different and both matter. The Game Driver explains who shaped the game overall; the Turning Point explains when the game flipped. When both exist and are different players, use both — name the Game Driver in WHAT THIS GAME MEANS and explain their role. Do not let the Turning Point crowd out the Game Driver.
- When a hitter had a 2+ HR game (Game Driver, high confidence), they MUST be mentioned by name in WHAT THIS GAME MEANS, even if someone else had the Turning Point. A go-ahead sac fly does not overshadow a 2-HR game.
- Dual-player framing when Game Driver ≠ Turning Point: briefly name the Game Driver's role first, then the Turning Point's moment. One sentence each. This is context, not recap.
- TURNING POINT: If confidence is HIGH, mention that player's moment in context — but after establishing the Game Driver's contribution if one exists. If no Game Driver, anchor the narrative on the Turning Point player. If confidence is LOW or none detected, do not force a clutch reference.

Output format: three paragraphs separated by a blank line. Nothing else."""


def _narrative_fallback(reason):
    import sys
    print(f"  [narrative] Falling back to deterministic insight because: {reason}", file=sys.stderr)
    return None


def generate_narrative_copy(brief_data, story_state, delta, team_name,
                            story_threads=None, story_hook=None, looking_ahead_hook=None,
                            game_driver=None):
    """
    Call the Anthropic API to generate AI-written narrative copy.
    Returns a dict with top_frame, what_this_means, what_to_watch — or None on failure.
    Logs a clear reason on every fallback path.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _narrative_fallback("ANTHROPIC_API_KEY is not set")

    prompt = _build_narrative_prompt(
        brief_data, story_state, delta, team_name,
        story_threads=story_threads,
        story_hook=story_hook,
        looking_ahead_hook=looking_ahead_hook,
        game_driver=game_driver,
    )
    system = _build_narrative_system(team_name)

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      "claude-haiku-4-5-20251001",
                "max_tokens": 700,
                "system":     system,
                "messages":   [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
    except Exception as exc:
        return _narrative_fallback(f"API request failed — {exc}")

    body = resp.json()

    if body.get("type") == "error":
        err = body.get("error", {})
        return _narrative_fallback(f"API error {err.get('type')}: {err.get('message')}")

    raw = (body.get("content") or [{}])[0].get("text", "").strip()
    if not raw:
        return _narrative_fallback(f"empty response body (HTTP {resp.status_code})")

    paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip()]
    if len(paragraphs) < 2:
        return _narrative_fallback(f"response had fewer than 2 paragraphs (got {len(paragraphs)})")

    import sys
    print("  [narrative] AI narrative generated successfully", file=sys.stderr)
    return {
        "top_frame":       paragraphs[0],
        "what_this_means": paragraphs[1],
        "what_to_watch":   paragraphs[2] if len(paragraphs) >= 3 else "",
    }
