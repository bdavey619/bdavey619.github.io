"""
engine/narrative.py — Shared State of Play narrative engine.

Used by padres/build_brief.py and yankees/build_brief.py.
All team-specific strings (team_name, story_state_path) are passed as parameters.
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta
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
            print(
                f"  warn [insight guardrail]: speculative phrase detected — {phrase!r}",
                file=sys.stderr,
            )


# ---------------------------------------------------------------------------
# Game Emotion Classification
# ---------------------------------------------------------------------------

def classify_game_emotion(last_game, team_win_pct=None, prev_division_rank=None,
                          curr_division_rank=None):
    """
    Classify the emotional intensity of the last game.
    Returns 'normal' | 'high' | 'extreme' based on structured game data only.

    extreme: walk-off win, 4+ runs in 9th or later (and win), comeback from 4+ deficit,
             extra-innings win after trailing by 2+
    high:    go-ahead run in 7th+, extra-innings win, comeback from 2-3 deficit,
             10+ K start, 2+ HR game, shutout/near-shutout with 6+ inning start,
             extra-inning win (floor rule — 10+ innings always at least "high"),
             win vs higher-win-pct opponent that improves division rank
    normal:  everything else

    Optional params for elevation triggers:
      team_win_pct      — team's current season win percentage (float 0–1)
      prev_division_rank — division rank before this game (from prev story_state)
      curr_division_rank — division rank after this game (from current team data)
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

    # FLOOR: any extra-inning win is always at least "high"
    if is_win and num_innings >= 10:
        return "high"

    # ELEVATION: win vs higher-win-pct opponent that improves division standing
    opp_win_pct = last_game.get("opp_win_pct") if last_game else None
    if (
        is_win
        and opp_win_pct is not None
        and team_win_pct is not None
        and opp_win_pct > team_win_pct
        and prev_division_rank is not None
        and curr_division_rank is not None
        and curr_division_rank < prev_division_rank
    ):
        return "high"

    return "normal"


def _detect_drama_sequence(last_game):
    """
    Detect the setup + payoff drama structure: team trailed, tied in inning 7+,
    then won in extras or on a walkoff.

    Returns a dict with tying_inning and walkoff_inning when the sequence is found,
    or None otherwise.  Used to instruct the model to name the tying moment before
    the walkoff rather than collapsing both into a single abstract statement.
    """
    if not last_game:
        return None

    result = last_game.get("result", "")
    home   = last_game.get("home", False)
    if result != "W":
        return None

    linescore = last_game.get("linescore") or [[], []]
    def _to_int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    sd_inn  = [_to_int(v) for v in (linescore[0] if linescore else [])]
    opp_inn = [_to_int(v) for v in (linescore[1] if len(linescore) > 1 else [])]
    n = min(len(sd_inn), len(opp_inn))
    if n < 7:
        return None

    sd_cum  = [sum(sd_inn[:i + 1]) for i in range(n)]
    opp_cum = [sum(opp_inn[:i + 1]) for i in range(n)]

    # Confirm team trailed at some point
    ever_trailed = any(opp_cum[i] > sd_cum[i] for i in range(n))
    if not ever_trailed:
        return None

    # Find the first inning >= 7 where team tied or took lead after trailing
    tying_inning = None
    for i in range(6, n):
        if opp_cum[i - 1] > sd_cum[i - 1] and sd_cum[i] >= opp_cum[i]:
            tying_inning = i + 1  # 1-indexed
            break

    if tying_inning is None:
        return None

    # Confirm this is a walkoff or extra-innings win
    num_innings = len(sd_inn)
    is_extra    = num_innings > 9
    is_walkoff  = home and num_innings >= 9 and len(sd_inn) == len(opp_inn) and sd_inn[-1] > 0

    if not (is_extra or is_walkoff):
        return None

    walkoff_inning = num_innings  # the inning the winning run scored

    return {
        "tying_inning":   tying_inning,
        "walkoff_inning": walkoff_inning,
    }


# ---------------------------------------------------------------------------
# Story State
# ---------------------------------------------------------------------------

_TREND_ORDER    = {"surging": 4, "stabilizing": 3, "fragile": 2, "slipping": 1}
_CONF_ORDER     = {"high": 3, "medium": 2, "low": 1}
_PRESSURE_ORDER = {"low": 1, "building": 2, "high": 3}


def build_story_state(team, last_game, prev_state=None):
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

    last_result    = (last_game or {}).get("result", "")
    game_date      = (last_game or {}).get("date", "")
    prev_division_rank = (prev_state or {}).get("division_rank")
    game_emotion_level = classify_game_emotion(
        last_game,
        team_win_pct=win_pct,
        prev_division_rank=prev_division_rank,
        curr_division_rank=division_rank,
    )
    drama_sequence     = _detect_drama_sequence(last_game)

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
        "drama_sequence":     drama_sequence,
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
                return f"The box score changed in one swing. {clutch_last} ended the debate."
            return "One swing rewrote the scoreboard. This team is learning when to bide its time."

        if max_deficit >= 4:
            _n = _DEFICIT_WORDS.get(max_deficit, str(max_deficit))
            if has_dual and driver_hr >= 2:
                return (f"Down {_n}. {driver_last} kept them alive. "
                        f"{clutch_last} finished the climb.")
            if has_dual:
                return (f"Down {_n}. {driver_last} supplied the power. "
                        f"{clutch_last} delivered the turn.")
            if clutch_last:
                return f"Down {_n}. {clutch_last}'s {clutch_event_lower} was the turn."
            return f"Down {_n} and still standing. This team found a way back."

        if late_runs >= 5:
            if has_dual:
                return (f"A quiet game until it wasn't. {driver_last} did the damage. "
                        f"{clutch_last}'s {clutch_event_lower} sealed it.")
            if clutch_last:
                return (f"A quiet game until it wasn't. {clutch_last}'s {clutch_event_lower}"
                        f" was the inning everyone will remember.")
            return "The box score says win; the inning chart says escape."

        if max_deficit >= 2:
            _n = _DEFICIT_WORDS.get(max_deficit, str(max_deficit))
            if has_dual:
                return (f"Down {_n}. {driver_last} powered them back. "
                        f"{clutch_last} finished the job.")
            if clutch_last:
                return f"Down {_n}. {clutch_last} delivered the play that mattered."
            return "They trailed and found a way. This team survives ugly games."

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
            return "The loss stings. A game that revealed as much as it cost."
        if emotion == "high":
            return "They had the moments. They didn't have the finish."

    return ""


# ---------------------------------------------------------------------------
# Narrative generation — Claude writes from structured context
# ---------------------------------------------------------------------------

def _build_narrative_system(team_name):
    return (
        f"You are the editorial voice of the {team_name} Morning Brief. "
        "You watched this game. You have opinions about it.\n\n"
        "You write like a friend who knows baseball deeply and is texting after the game. "
        "Sharp. Slightly unhinged. Always controlled. You take a side and defend it.\n\n"
        "No em dashes. Vary sentence length: mix short (3–6 words), medium (8–14 words), "
        "and occasional longer sentences for buildup and flow. "
        "Do not stack more than two short sentences in a row. "
        "Combine related ideas into one sentence when it improves flow. "
        "Avoid hedge words: 'somewhat', 'kind of', 'may', 'could', 'appears'. "
        "Say what happened. Say what it means. End with something that lingers.\n\n"
        "You explain *why* something matters, not just *what* happened. "
        "The reader already knows the score. Give them something to think about."
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

    # Bullpen block — all relievers from full_box.pitching[1:]
    _pitching_rows = (last_game.get("full_box") or {}).get("pitching") or []
    _starter_row   = _pitching_rows[0] if _pitching_rows else None
    _relief_rows   = _pitching_rows[1:]

    # Starter exit note
    if _starter_row:
        try:
            _starter_ip = float(str(_starter_row.get("ip", "0")))
        except (TypeError, ValueError):
            _starter_ip = 0.0
        if _starter_ip < 5.0:
            _starter_exit = f" (short outing — exited after {_starter_row['ip']} IP)"
        elif _starter_ip < 6.0:
            _starter_exit = f" (went {_starter_row['ip']} IP)"
        else:
            _starter_exit = ""
    else:
        _starter_exit = ""

    pitcher_text = (
        f"{kp.get('name')} — {kp.get('line')} (season ERA: {kp.get('season_era', '?')}){_starter_exit}"
        if kp else "N/A"
    )

    # Build bullpen block with all relievers regardless of IP
    if _relief_rows:
        def _bp_line(p):
            base = f"  {p['name']}: {p['ip']} IP, {p['er']} ER, {p['k']} K"
            badges = []
            if p.get("sv"):
                badges.append("SV")
            if p.get("hld"):
                badges.append("H")
            if p.get("bs"):
                badges.append("BS")
            return f"{base} ({', '.join(badges)})" if badges else base

        _bullpen_lines = "\n".join(_bp_line(p) for p in _relief_rows)
        # Total bullpen IP for the prompt instruction
        _total_bp_ip = 0.0
        for _p in _relief_rows:
            try:
                _total_bp_ip += float(str(_p.get("ip", "0")))
            except (TypeError, ValueError):
                pass
        bullpen_block = (
            f"\nBULLPEN ({len(_relief_rows)} pitcher{'s' if len(_relief_rows) != 1 else ''}"
            f", {_total_bp_ip:.1f} IP total after starter):\n{_bullpen_lines}"
        )
    else:
        bullpen_block = ""

    hitters_text = (
        "; ".join(f"{h['name']} {h['line']}" for h in kh)
        if kh else "N/A"
    )

    ng_prob  = next_game.get("probable") or {}
    _our_sp  = ng_prob.get("team") or "TBD"
    _opp_sp  = ng_prob.get("opp")  or "TBD"
    _opp_era = ng_prob.get("opp_era")
    _opp_sp_text = f"{_opp_sp} (season ERA: {_opp_era})" if _opp_era else _opp_sp
    next_text = (
        f"vs {next_game.get('opponent')} on {next_game.get('date')} at "
        f"{next_game.get('time_local', 'TBD')}. "
        f"Our SP: {_our_sp}. Opp SP: {_opp_sp_text}"
        if next_game else "N/A"
    )

    # Day label for the next game (Tonight / Tomorrow / Friday / etc.)
    def _day_label(date_str):
        if not date_str:
            return "next game"
        try:
            gd = datetime.strptime(date_str, "%Y-%m-%d").date()
            today = datetime.now().date()
            if gd == today:
                return "tonight"
            elif gd == today + timedelta(days=1):
                return "tomorrow"
            return gd.strftime("%A").lower()
        except (ValueError, TypeError):
            return "next game"

    next_day_label = _day_label((next_game or {}).get("date", ""))

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

    # Drama sequence — injected when team trailed, tied late (7th+), then won in extras/walkoff
    ds = story_state.get("drama_sequence")
    if ds and story_state.get("game_emotion_level") == "extreme":
        drama_sequence_block = (
            f"\nDRAMA SEQUENCE (tying moment before walkoff — instruct model to name both):\n"
            f"  Team trailed, then tied the game in inning {ds['tying_inning']}.\n"
            f"  Team won in inning {ds['walkoff_inning']}.\n"
            f"  INSTRUCTION: Name the tying play FIRST in WHAT THIS GAME MEANS, then the walkoff.\n"
            f"  Do NOT collapse both into one abstract statement."
        )
    else:
        drama_sequence_block = ""

    emotion = story_state.get("game_emotion_level", "normal")
    if emotion == "extreme":
        voice_block = """VOICE — EXTREME EMOTION (game_emotion_level: extreme):
- The dramatic event is the TURNING POINT in the structured context above. Use it.
  If TURNING POINT confidence is HIGH: TOP FRAME must open with that player's name or the exact inning.
  Do NOT write "the dramatic event" generically — name the player and what they did.
  Example forms: "Rodriguez walked it off in the twelfth." / "The ninth inning was one pitch."
- DRAMA SEQUENCE RULE: If a DRAMA SEQUENCE block appears in the structured context above,
  the tying moment is the emotional spine — name it FIRST in WHAT THIS GAME MEANS, then resolve to the walkoff.
  Example: "Castellanos tied it with a home run in the ninth. Machado finished it in the tenth."
  Do NOT compress both into a single vague statement. Name each moment separately.
- WHAT THIS GAME MEANS: Name the inning. Name the count or game situation if available (2 out, tying run, etc.).
  The drama lives in the specifics. "He tied it with two outs in the ninth" is vivid.
  "The late rally" is not.
- Stay editorial. No all-caps, no exclamation marks, no manufactured urgency.
- Genuine energy comes from the facts themselves — let the situation carry the weight.
- Forbidden phrases: "for the ages", "absolute madness", "unbelievable scenes", "one they'll never forget",
  "chaos", "mayhem". All BANNED VOCABULARY terms apply here with extra force."""
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
  "scratched out" / "just enough" / "held up" / "didn't break" / "won by one run again"

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
  "should have" / "cost" / "threshold" / "exposed" / "standard" / "didn't finish it"

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
    elif team_name == "Giants":
        team_voice_block = """TEAM VOICE PROFILE — GIANTS (apply subtly, do NOT announce):
Identity: streaky, weathered, experienced. Wins feel managed, not dominant. Nothing is ever easy.

Language to lean into (1–2 uses per brief, not every sentence):
  "ground out" / "worked through" / "just enough again" / "never comfortable" / "they made it hold"

Editorial bias:
- Expect uneven performance — this team runs hot and cold
- See wins as managed outcomes, not dominant statements
- Lean into veteran/crafty tone over power or flash
- NL West division rivals are Dodgers, Padres, Rockies, Diamondbacks — not AL East

Sentence feel: dry, understated, slightly world-weary. More craft than power. Grounded in process.
Reference vibe: "They didn't blow anyone out. They didn't need to."

Application rules:
- 1–2 word choices or sentence rhythm shifts only. Not an entire costume.
- Do not announce or name the voice.
- Game truth still wins over voice consistency."""
    elif team_name == "Athletics":
        team_voice_block = """TEAM VOICE PROFILE — ATHLETICS (apply subtly, do NOT announce):
Identity: scrappy, strange, opportunistic. Low expectation but alert. Rebuild/chaos energy without condescension.

Language to lean into (1–2 uses per brief, not every sentence):
  "found something" / "made it weird" / "kept hanging around" / "not pretty" / "enough to matter" / "small edge" / "young pieces"

Editorial bias:
- Nobody expects polish from this team — wins feel like found money
- Role players and development are part of the story, not an asterisk
- Weird games are expected, not surprising
- Be more interested in signs of life and unexpected competitiveness than in confirming failure
- Do not mock the team; do not write like they are hopeless
- Less judgmental than Yankees voice; less "fragile contender" than Padres voice
- AL West division rivals are Astros, Rangers, Mariners, Angels — not NL teams

Sentence feel: alert, scrappy, slightly chaotic. Low-stakes in the right way. Grounded in possibility.
Reference vibe: "They are not supposed to be polished. They are supposed to find things worth keeping."

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

    # Doubleheader context — build a full two-game brief for the prompt
    if last_game.get("is_doubleheader"):
        dh_games = last_game.get("doubleheader_games") or []
        if len(dh_games) >= 2:
            g1 = dh_games[0]
            g2 = dh_games[1]
            g1_sc = g1.get("score") or {}
            g2_sc = g2.get("score") or {}
            g1_moment = f" ({g1['key_moment']})" if g1.get("key_moment") else ""
            g2_moment = f" ({g2['key_moment']})" if g2.get("key_moment") else ""
            g1_line = (
                f"Game 1: {g1['result']} {g1_sc.get('team', '?')}–{g1_sc.get('opp', '?')}"
                f"{g1_moment}"
            )
            g2_line = (
                f"Game 2 (primary box score): {g2['result']} "
                f"{g2_sc.get('team', '?')}–{g2_sc.get('opp', '?')}"
                f"{g2_moment}"
            )
            # Build explicit walk-off loss framing when both games ended that way
            g1_walkoff = g1.get("walkoff", False)
            g2_walkoff = g2.get("walkoff", False)
            g1_t = g1_sc.get('team', '?')
            g1_o = g1_sc.get('opp', '?')
            g2_t = g2_sc.get('team', '?')
            g2_o = g2_sc.get('opp', '?')
            g1_km = g1.get("key_moment", "")
            g2_km = g2.get("key_moment", "")
            if g1_walkoff and g2_walkoff:
                walkoff_block = (
                    f"\n  WALK-OFF CONTEXT (critical — use these exact facts):\n"
                    f"  Both games were walk-off losses.\n"
                    f"  Game 1: lost {g1_t}–{g1_o} — {g1_km}.\n"
                    f"  Game 2: lost {g2_t}–{g2_o} — {g2_km}.\n"
                    f"  The narrative must frame the full day: two games, two late losses, both walk-offs.\n"
                    f"  Do NOT focus only on one player moment from one game."
                )
            elif g1_walkoff:
                walkoff_block = (
                    f"\n  WALK-OFF CONTEXT: Game 1 ended on an opponent walk-off{g1_moment}."
                )
            elif g2_walkoff:
                walkoff_block = (
                    f"\n  WALK-OFF CONTEXT: Game 2 ended on an opponent walk-off{g2_moment}."
                )
            else:
                walkoff_block = ""
        else:
            dh_note = last_game.get("doubleheader_note", "")
            g2_sc   = last_game.get("score") or {}
            g2_res  = last_game.get("result", "?")
            g1_line = dh_note
            g2_line = f"Game 2 (primary): {g2_res} {g2_sc.get('team', '?')}–{g2_sc.get('opp', '?')}"
            walkoff_block = ""

        walkoff_sep = f"\n{walkoff_block}" if walkoff_block else ""
        doubleheader_hint = (
            f"\n\nDOUBLEHEADER — TWO GAMES YESTERDAY:\n"
            f"  {g1_line}\n"
            f"  {g2_line}"
            f"{walkoff_sep}\n"
            f"\n"
            f"  INSTRUCTION: State of Play MUST account for both games. Do not write as if only\n"
            f"  Game 2 happened. Open by framing the full day — both outcomes matter.\n"
            f"  Game 2 detail is in the box score above and can anchor the analysis,\n"
            f"  but the story must contain both results."
        )
    else:
        doubleheader_hint = ""

    # Game story signals block
    game_story = brief_data.get("game_story")
    if game_story:
        s          = game_story["summary"]
        gs         = game_story.get("game_shape") or {}
        missed_opps     = game_story.get("missed_opportunities") or []
        rally_seqs      = game_story.get("rally_sequences") or []
        momentum_swings = game_story.get("momentum_swings") or []

        missed_lines = []
        for m in missed_opps:
            missed_lines.append(
                f"    inning {m['inning']}: {m['risp_at_bats']} RISP AB,"
                f" ~{m['runners_left']} LOB, severity={m['severity']}"
            )

        rally_lines = []
        for r in rally_seqs:
            tags = []
            if r.get("came_from_behind"):
                tags.append("from behind")
            if r.get("lead_change"):
                tags.append("lead change")
            tag_str = f" ({', '.join(tags)})" if tags else ""
            rally_lines.append(f"    inning {r['inning']}: {r['runs']} runs{tag_str}")

        swing_lines = []
        for sw in momentum_swings:
            dir_label = "team scored" if sw["direction"] == "for" else "opp scored"
            extra = " [go-ahead]" if sw.get("go_ahead") else (" [lead change]" if sw.get("lead_change") else "")
            swing_lines.append(
                f"    inning {sw['inning']}: {dir_label} {sw['runs']} runs{extra}"
            )

        # Game-shape lines (Phase 3.1 guardrail data)
        _trailed      = gs.get("team_ever_trailed", False)
        _max_def      = gs.get("max_deficit_faced", 0)
        _led          = gs.get("team_ever_led", False)
        _max_lead     = gs.get("max_lead_held", 0)
        _tied_late    = gs.get("was_tied_late", False)
        _decided      = gs.get("game_decided_by_inning")
        _blowout      = gs.get("blowout_by_5th", False)
        _inn_trailed  = gs.get("innings_team_trailed") or []
        _inn_led      = gs.get("innings_team_led") or []
        # Phase 3.3: end-of-inning state (correct per-inning snapshots)
        _end_inn_led      = gs.get("end_inning_team_led") or []
        _end_inn_trailed  = gs.get("end_inning_team_trailed") or []
        _end_inn_tied     = gs.get("end_inning_tied") or []
        _end_score_states = gs.get("end_inning_score_states") or []

        def _yn(v):
            return "YES" if v else "NO"

        def _fmt_inn_ranges(innings):
            """Format a sorted inning list as compact ranges: [1,2,3,7,8,9] → '1–3, 7–9'."""
            if not innings:
                return "none"
            ranges = []
            start = end = innings[0]
            for i in innings[1:]:
                if i == end + 1:
                    end = i
                else:
                    ranges.append(str(start) if start == end else f"{start}–{end}")
                    start = end = i
            ranges.append(str(start) if start == end else f"{start}–{end}")
            return ", ".join(ranges)

        _decided_str = str(_decided) if _decided is not None else "none"
        # Use end-of-inning data for GAME SHAPE display (avoids mid-inning state confusion)
        _trailed_str = _fmt_inn_ranges(_end_inn_trailed) if _end_inn_trailed else "never"
        _led_str     = _fmt_inn_ranges(_end_inn_led)     if _end_inn_led     else "never"

        # Phase 3.3: RISP conversion data
        _risp_conv    = game_story.get("risp_conversion") or {}
        _rc_total     = _risp_conv.get("total_risp_pa", 0)
        _rc_scored    = _risp_conv.get("risp_pa_with_run_scored", 0)
        _rc_conv_inn  = _risp_conv.get("risp_converted_innings") or []
        _rc_empty_inn = _risp_conv.get("risp_empty_innings") or []

        _risp_conv_suffix = (
            f" · converted: {_rc_scored}/{_rc_total} PAs scored"
            f" · innings with run: {_rc_conv_inn or 'none'}"
            f" · empty innings: {_rc_empty_inn or 'none'}"
            if _risp_conv else ""
        )

        _gs_lines = [
            "\nGAME STORY SIGNALS (deterministic, from play-by-play):",
            f"  RISP situations: {s['total_risp_situations']}{_risp_conv_suffix}",
            f"  Missed opportunity innings: {s['missed_opportunity_innings']}"
            f" ({s['critical_misses']} critical, {s['significant_misses']} significant)",
        ]
        _gs_lines.extend(missed_lines)
        _gs_lines.append(f"  Multi-run innings: {s['multi_run_innings']}")
        _gs_lines.extend(rally_lines)
        _gs_lines.append(f"  Momentum swings (2+ runs): {s['momentum_swing_count']}")
        _gs_lines.extend(swing_lines)
        _gs_lines += [
            "",
            "  GAME SHAPE (factual — hard guardrails for framing):",
            f"    Team ever trailed:        {_yn(_trailed)} · Max deficit: {_max_def} runs · Trailed at end of inning(s): {_trailed_str}",
            f"    Team ever led:            {_yn(_led)} · Max lead held: {_max_lead} runs · Led at end of inning(s): {_led_str}",
            f"    Score tied in inning 6+:  {_yn(_tied_late)}",
            f"    Game decided by inning:   {_decided_str}",
            f"    Blowout by 5th inning:    {_yn(_blowout)}",
        ]

        # Phase 3.2: LEAD CHRONOLOGY block
        _first_lead  = gs.get("first_team_lead_inning")
        _first_trail = gs.get("first_team_trail_inning")
        _last_tied   = gs.get("last_tied_inning")
        _lc_count    = gs.get("lead_changes_count", 0)

        _lead_lines = ["", "  LEAD CHRONOLOGY:"]
        _lead_lines.append(
            f"    - Team first led in inning {_first_lead}"
            if _first_lead is not None else
            "    - Team never led"
        )
        _lead_lines.append(
            f"    - Team first trailed in inning {_first_trail}"
            if _first_trail is not None else
            "    - Team never trailed"
        )
        _lead_lines.append(
            f"    - Game was last tied after inning {_last_tied}"
            if _last_tied is not None else
            "    - Game was never tied at inning end"
        )
        _lead_lines.append(f"    - Lead changes: {_lc_count}")
        _gs_lines.extend(_lead_lines)

        # Phase 3.3: END-OF-INNING CHRONOLOGY
        if _end_score_states:
            _gs_lines.append("")
            _gs_lines.append("  END-OF-INNING CHRONOLOGY (score state at end of each inning):")
            if _end_inn_led:
                _gs_lines.append(
                    f"    - Led after innings:     {_fmt_inn_ranges(_end_inn_led)}"
                )
            if _end_inn_tied:
                _gs_lines.append(
                    f"    - Tied after innings:    {_fmt_inn_ranges(_end_inn_tied)}"
                )
            if _end_inn_trailed:
                _gs_lines.append(
                    f"    - Trailed after innings: {_fmt_inn_ranges(_end_inn_trailed)}"
                )

        # Phase 3.2: GAME TEXTURE block
        gt = game_story.get("game_texture") or {}
        if gt:
            _gt_primary   = gt.get("primary", "")
            _gt_secondary = gt.get("secondary") or ""
            _gt_reason    = gt.get("reason", "")
            _gt_tone      = gt.get("tone_guidance", "")
            _secondary_str = f" / {_gt_secondary}" if _gt_secondary else ""
            _gs_lines += [
                "",
                "  GAME TEXTURE (classifier — calibrate tone and framing):",
                f"    Primary:        {_gt_primary}{_secondary_str}",
                f"    Reason:         {_gt_reason}",
                f"    Tone guidance:  {_gt_tone}",
            ]

        game_story_block = "\n".join(_gs_lines)
    else:
        gs = {}
        game_story_block = "\nGAME STORY SIGNALS: not available"

    # ---------------------------------------------------------------------------
    # Phase 3.1 + 3.2: Build factual guardrail block from game_shape fields.
    # These are injected directly into the prompt as HARD RULES so the model
    # cannot invent a deficit, comeback, or blowout tension that did not occur.
    # ---------------------------------------------------------------------------
    _gs_trailed    = gs.get("team_ever_trailed", False)
    _gs_max_def    = gs.get("max_deficit_faced", 0)
    _gs_blowout    = gs.get("blowout_by_5th", False)
    _gs_decided    = gs.get("game_decided_by_inning")
    _gs_tied_late  = gs.get("was_tied_late", False)
    _gs_led        = gs.get("team_ever_led", False)
    # Phase 3.2 chronology fields
    _gs_first_lead  = gs.get("first_team_lead_inning")
    _gs_first_trail = gs.get("first_team_trail_inning")
    _gs_last_tied   = gs.get("last_tied_inning")
    _gs_lc_count    = gs.get("lead_changes_count", 0)

    _guardrail_lines = []

    if _gs_trailed is False and game_story:
        # Team never trailed — ban all comeback/deficit language
        _guardrail_lines.append(
            "DEFICIT GUARDRAIL (HARD — team NEVER trailed in this game · max deficit: 0 runs):\n"
            "  Do NOT use: comeback, fought back, rallied from behind, two runs down, dug out,\n"
            "              deficit, climbed back, rescued, behind at any point, responded to.\n"
            "  Late scoring is a BREAKTHROUGH from a tied or leading position — not a comeback.\n"
            "  If the team was TIED going into the late innings, frame it as breaking a deadlock,\n"
            "  not overcoming a deficit."
        )

    if _gs_blowout and game_story:
        # Decided early — ban manufactured urgency
        decided_clause = (
            f"  The game was decided by inning {_gs_decided}."
            if _gs_decided else ""
        )
        _guardrail_lines.append(
            "BLOWOUT GUARDRAIL (HARD — game decided by 5th inning or earlier):\n"
            "  Write FLAT and COMPRESSED. The outcome was not in doubt late.\n"
            f"{decided_clause}\n"
            "  Do NOT use: 'swallowed a team whole', 'put up a fight', 'season pressure',\n"
            "              'division doesn't wait', 'couldn't recover', philosophical overreach.\n"
            "  State what happened early and move on. Do not dramatize a resolved game."
        )
    elif _gs_decided is not None and _gs_decided <= 4 and game_story:
        _guardrail_lines.append(
            f"EARLY-DECISION GUARDRAIL (game decided by inning {_gs_decided}):\n"
            "  Do NOT imply late drama. Do NOT say the offense 'put up a fight' unless they\n"
            "  scored 3+ runs. The outcome was essentially determined before the middle innings.\n"
            "  Frame as decided early — not as a missed late opportunity."
        )

    # Phase 3.2: chronology guardrails
    if (game_story
            and _gs_first_lead is not None
            and _gs_first_trail is not None
            and _gs_first_trail > _gs_first_lead):
        # Team held a lead before eventually falling behind — NOT an early comeback game
        _guardrail_lines.append(
            f"CHRONOLOGY GUARDRAIL (HARD — team led first, then fell behind):\n"
            f"  Team first led in inning {_gs_first_lead}. Team first trailed in inning {_gs_first_trail}.\n"
            f"  The team was NEVER behind until inning {_gs_first_trail}.\n"
            f"  Do NOT write 'trailed after the second' or any early inning — factually wrong.\n"
            f"  Do NOT write 'tied it up' — the team led, was caught, then fell behind; they never trailed first.\n"
            f"  Do NOT write 'chasing', 'chased', or 'spent the night chasing'.\n"
            f"  Do NOT describe this as an early comeback, 'chasing from the start', or a deficit game.\n"
            f"  The team held the lead — this is a story of a lead LOST, not a hole CLIMBED OUT OF.\n"
            f"  If the team lost: frame as 'lead lost in inning {_gs_first_trail}' or 'game turned late'.\n"
            f"  If the team won: frame as a late rally that recaptured a lead they had already held."
        )
    elif (game_story
          and _gs_led
          and _gs_first_trail is not None
          and _gs_first_trail >= 7):
        # Team led, then fell behind late — frame as late-turn, not chasing
        _guardrail_lines.append(
            f"CHRONOLOGY GUARDRAIL — LATE TURN (HARD — team led, fell behind in inning {_gs_first_trail}):\n"
            f"  The team held the lead through most of the game before losing it in inning {_gs_first_trail}.\n"
            f"  They were NOT trailing before inning {_gs_first_trail}.\n"
            f"  Do NOT write 'trailed after the second/third/fourth/fifth' — factually wrong.\n"
            f"  Do NOT write 'tied it up' — they led first; they did not trail and then equalize.\n"
            f"  Do NOT write 'chasing', 'spent the night chasing', or any chasing language.\n"
            f"  Frame as: 'lead lost late' or 'game turned in inning {_gs_first_trail}'."
        )

    if (game_story
            and _gs_last_tied is not None
            and _gs_last_tied >= 6
            and _gs_max_def <= 1):
        # Game broke open late from a tie — not a comeback
        _guardrail_lines.append(
            f"CHRONOLOGY GUARDRAIL — LATE-BREAKING GAME (last tied after inning {_gs_last_tied}):\n"
            f"  Max deficit was only {_gs_max_def} run(s). This is a late-breaking game, NOT a comeback.\n"
            f"  Do NOT use comeback language. Frame as a tied game that broke open late.\n"
            f"  The drama is in the breaking point — not in overcoming a deficit."
        )

    # Phase 3.3: RISP conversion guardrail
    if game_story:
        _risp_gs      = (game_story.get("risp_conversion") or {})
        _rc_scored_gs = _risp_gs.get("risp_pa_with_run_scored", 0)
        _rc_empty_gs  = _risp_gs.get("risp_empty_innings") or []
        if _rc_scored_gs > 0:
            _no_empty_clause = (
                " There were no innings where RISP situations went completely unscored."
                if not _rc_empty_gs else ""
            )
            _guardrail_lines.append(
                f"RISP GUARDRAIL (HARD — team scored on {_rc_scored_gs} of their RISP"
                f" plate appearance(s)):\n"
                f"  Do NOT write: 'nothing to show for RISP chances', 'came up empty',\n"
                f"  'couldn't convert', 'left runners stranded without producing', or any phrase\n"
                f"  implying zero RISP production.{_no_empty_clause}\n"
                f"  The team scored at least {_rc_scored_gs} run(s) in RISP situations — acknowledge it."
            )

    factual_guardrails = (
        "\n\n".join(_guardrail_lines)
        if _guardrail_lines else ""
    )
    _guardrail_block = (
        f"\nFACTUAL GAME-SHAPE GUARDRAILS (violations = factual errors — fix before returning):\n"
        f"{factual_guardrails}\n"
        if factual_guardrails else ""
    )

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
  Offense:     {offense_note}{doubleheader_hint}
{bullpen_block}
{game_driver_block}
{clutch_block}
{drama_sequence_block}
{game_story_block}

TEAM CONTEXT:
  Record: {team.get('record')} · Streak: {team.get('streak')} · Last 10: {team.get('last10')}
  ERA: {team.get('era')} · OPS: {team.get('ops')} · Avg: {team.get('avg')}
  Division: Rank {team.get('division_rank')} · {team.get('games_back')} back

NEXT GAME:
  {next_text}

NEXT GAME HOOK ({next_day_label} — use to ground the forward-looking WHAT TO WATCH section):
  {looking_ahead_line}

--- OUTPUT INSTRUCTIONS ---
{_guardrail_block}
GAME STORY PRIORITY (applies when GAME STORY SIGNALS are present above):
When GAME STORY SIGNALS are available, your job is not to rediscover the story from the box score. Your job is to write the game story implied by these signals. Box score stats are supporting evidence only.

If GAME STORY SIGNALS are not available, fall back to TURNING POINT and GAME DRIVER as the primary spine.

TONAL MODE (internal — do NOT output or name this):
Before writing, select one mode based on the game. Let it shape word choice and sentence feel — do not announce it.

  CLINICAL   → routine win or loss, no strong swing either way
  GRITTY     → close game, comeback, ugly win, survival
  DOMINANT   → blowout or an overpowering individual performance
  FRAGILE    → win or loss that exposes a real weakness
  CHAOTIC    → wild swings, high-scoring, genuinely weird game

The mode is felt in rhythm and word choice, not stated. One or two choices that fit the game — not every sentence.

GAME TEXTURE TONE LOCK (when GAME TEXTURE is present in GAME STORY SIGNALS):
Use GAME TEXTURE to override or sharpen your TONAL MODE selection. The texture_guidance field is a direct instruction about register — follow it.

Texture-specific rules:
  pitching_duel      → write compressed and pitcher-forward; do NOT inflate into a comeback story,
                        identity claim, or philosophical meditation; keep it tight; one or two
                        sentences max per paragraph; the pitcher's line belongs in the lead.
  offensive_breakout → write expansively; name the runs; name who drove them; do not undersell.
  blowout            → write flat; state what happened and when; no manufactured late drama.
  dead_offense_loss  → write honest and direct; name what failed; do not reach for silver linings.
  late_breakthrough  → build the section chronologically; the late scoring is the payoff not the premise.
  bullpen_grind      → the BULLPEN section in LAST GAME above has the specific names and lines. Use them.
                        Do NOT write "the bullpen held" without naming who held it and their line.
                        Example: "Marinaccio threw two scoreless. Estrada struck out two in the eighth."
  back_and_forth     → do not anchor on one moment; the shape of the game is the story.
  routine_win        → plain and measured; no forced energy.
  routine_loss       → analytical; explain what fell short specifically.

PITCHING CONTEXT RULE (applies when BULLPEN section is present in LAST GAME above):
When the BULLPEN section lists pitchers who covered 3 or more total IP, at least one named reliever
must appear in WHAT THIS GAME MEANS — with their line or the role they played.
Do NOT summarize with "the bullpen held" or "the pen came through" without naming who.
If a reliever threw 2+ IP or recorded the final out, name them and what they did.

When secondary = offense_wasted_pitching:
  The narrative must include both the starter's quality line AND the offensive failure.
  Do NOT write as if pitching alone cost the game — the offense is the missing piece.
  Do NOT write as if offense alone cost the game — the pitching was good enough to win.

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

STORY HOOK NON-REPEAT (HARD RULE):
The story hook already rendered above is: "{story_hook_line}"
Your TOP FRAME must NOT open with these words or any rearrangement of them.
If your draft TOP FRAME begins with the story hook text, discard it and write from a different angle:
  - the game shape ("Tied through six innings until France made it matter.")
  - the pitching story ("Waldron bought them six innings — the offense cashed it late.")
  - the outcome as identity ("This team doesn't need to lead early to win.")
Do NOT name two players in one TOP FRAME sentence unless the two-player relationship IS the story and both roles are clearly distinct.

Good: "They played six tied innings and then broke it open." / "Waldron held the door — the offense walked through." / "This is what 22-14 looks like from the inside."
Avoid: opening with the story hook wording, multi-clause sentences, listing multiple players, explaining event sequences.

GAME STORY LENS (when GAME STORY SIGNALS available):
The TOP FRAME should usually reflect the game shape (e.g., tied game broken late, wire-to-wire hold, blowout controlled early), the turning point, or the dominant shape in the signals. Do not default to the best player's stat line unless that is clearly the story and no other angle is stronger.

BANNED VOCABULARY — HARD RULE (applies to ALL three sections — TOP FRAME, WHAT THIS GAME MEANS, WHAT TO WATCH):
Every instance of the following is a violation. Scan before returning. If found, rewrite the sentence.

Abstract nouns that replace specific facts:
  "pattern"   → say what recurred: "they left 7 runners on base again" / "the starter left before the 6th for the third time"
  "formula"   → say the actual mechanism: "the bullpen held STL to 0 in three innings" / "the defense turned two"
  "traffic"   → say the actual baserunner situation: "runners on second and third" / "two men on with one out"
  "margin"    → say the run differential: "up by one" / "won by two for the third time this week"
  "noise"     → delete; restate as what actually happened
  "narrative" → delete; make a direct claim without naming the concept
  "signal"    → say what changed: "the bullpen blew its third save this month" / "he's 0-for-12 in this spot"

Generic framing phrases:
  "that's the formula"          → say what the actual mechanism was
  "this is the formula"         → same
  "the formula broke"           → say what broke: "Rodón lasted 4.1 innings"
  "this is the pattern"         → say what repeated: "they led through six and gave it back in one inning"
  "that's the margin"           → say the actual score context
  "this is how stretches start" → banned entirely — too generic
  "this is what happens when"   → restate as a direct claim about this game
  "the story is"                → delete preamble; make the claim directly
  "the problem is"              → state the problem specifically, not as a concept
  "this is the cost"            → say what the cost was: "the base on balls in the eighth cost them two runs"
  "the division doesn't wait"   → banned entirely

Motivational / recycled momentum language (also banned from WHAT TO WATCH):
  "build on"    → banned
  "momentum"    → say what changed: "they scored 3 in the 9th" / "the lineup went quiet after the fourth"
  "bounce back" → banned
  "keep it going" → banned
  "carry that"  → banned

SILENT SCAN: Before returning, check every sentence for these words. If any appear, rewrite the sentence with the specific fact it was hiding.

2. WHAT THIS GAME MEANS (90–120 words max)
Job: interpretation and identity claim — not factual recap, not sequence retelling. The game_note already handled the vivid factual summary. The Game Driver and Turning Point are already shown as memory anchors. Your job is to answer: What does this game reveal about who this team is?

GAME SHAPE CONNECTION (when GAME STORY SIGNALS available):
WHAT THIS GAME MEANS should connect the game shape to team identity, season pressure, or recent trend. It should not merely restate the final score, player lines, or standings.

CHRONOLOGICAL TENSION (use when signals provide it):
When missed opportunities, rally sequences, and momentum swings are available, build the section using chronological tension: setup → pressure or missed chance → turning point → payoff. Do not open with the conclusion and walk backwards.

Do NOT restate the story_hook, game_note, Game Driver, or Turning Point — those facts are displayed separately and the reader already has them. Instead, answer: What is different about this team today because of this game? Use the STORY DELTA to identify one clear thing that changed — a weakness showed up again in the same inning type, a strength held in a new situation, a previously reliable piece failed at a key moment. Reference the Game Driver or Turning Point briefly if it supports the "what changed" answer — but do not retell the sequence. Connect the game to the team's current trend. Be precise.

Prefer one strong thesis over several smaller observations. One claim argued well is more memorable than three things that happened. Build to your identity sentence — do not spread the argument thin.

Make a clear claim about the team's identity. The section must include at least one sentence that could stand alone as an editorial take — something that answers "what is this team becoming?" or "what does this game reveal about how they win?" Frame it around a specific recurring situation, not an abstraction. Acceptable forms: "This is a team that...", "They are now...", "This works because...", "This breaks if...". Do NOT use "The pattern has become..." — say what the pattern IS: "They keep leaving runners on in the sixth" / "The bullpen has not blown a lead in 11 games." Weave at least one STORY THREAD naturally into the section — do not list it or name it explicitly; let it shape the argument.

The section must end with a short, memorable punchline under 12 words that captures the core takeaway. It must stand alone as the FINAL sentence of this section — do not bury it mid-paragraph and do not follow it with anything. Examples: "France gave them two swings when they needed one." / "This only works until it doesn't." / "Three straight one-run wins. That math gets harder." See PUNCHLINE RULE below for more examples and enforcement.

Use plain, direct fan language. Replace analytical constructions ("this represents", "this illustrates") with concrete statements ("they needed it", "he delivered", "that was the game"). Avoid academic tone, over-qualification, and unnecessary metaphors.

RHYTHM CONTROL:
No em dashes. No run-on sentences.

Use a mix of sentence lengths:
- Short (3–6 words): for punch and emphasis only
- Medium (8–14 words): for development and cause-effect
- Longer (15+ words): occasionally, for buildup before a short payoff

Rules:
- Never stack more than 2 short sentences in a row
- If two sentences share the same subject, consider merging them
- Combine related ideas into one sentence when it improves flow
- Use conjunctions naturally (and, but) instead of fragmenting into separate sentences
- Preserve punchlines as standalone final sentences — do not merge them

Bad: "They had chances. They didn't convert. The offense stalled. It cost them."
Good: "They had chances but didn't convert. The offense stalled. That's what cost them."

Do not over-explain the thesis.
State the idea once, clearly, then support it with one concrete example.

Avoid repeating the same concept in multiple forms.
Trust the reader to carry the idea forward.

MOBILE READABILITY — WHAT THIS GAME MEANS:

Write in short paragraphs (1–2 sentences each).

Break paragraphs whenever:
- a new idea or claim is introduced
- a supporting stat or example is introduced
- the narrative shifts (cause → consequence → judgment)
- a conclusion or forward-looking statement is made

Rules:
- No paragraph longer than 3 sentences
- Prefer 1 sentence when the line is strong
- Each paragraph should express ONE idea

Good:
"They had chances. They didn't convert them."

Bad:
"They had chances but didn't convert them and that's been the issue all season because..."

STRUCTURE (implicit — do NOT label in output):
1. Hook (strong opening claim)
2. What happened (1–2 short paragraphs)
3. Key supporting insight (stats or pattern)
4. Core judgment (what this means)
5. Forward implication or constraint

ANTI-DENSITY:
If a paragraph contains multiple ideas, split it.
If a sentence contains multiple clauses expressing different ideas, split into separate sentences.

RHYTHM RULE:
Vary paragraph length.
Do not make every paragraph one sentence.
Mix:
- 1-sentence paragraphs for emphasis
- 2-sentence paragraphs for development
Avoid overly fragmented, choppy writing.

COMPLETE SENTENCES — HARD RULE:
Every sentence must have a subject and a verb. No fragments.

Fragments are banned even when used for rhythmic effect. These are all violations:
  ❌ "That alignment."
  ❌ "Is becoming their identity."
  ❌ "Bullpen holding, bats arriving late."
  ❌ "Not a comeback. A correction."
  ❌ "The box score said close. The game didn't."
  ❌ "Starvation disguised as control."  ← noun + participial phrase, no finite verb — BANNED
  ❌ "Precision without reward."          ← noun phrase with no verb — BANNED
  ❌ "A team with answers, but no runs."  ← same structure — BANNED

Rewrite every fragment into a complete sentence before returning:
  ✅ "The alignment held — pitching and offense converging at the right moment."
  ✅ "That is becoming their identity."
  ✅ "The bullpen held, and the bats arrived late."
  ✅ "This was not a comeback. It was a correction."
  ✅ "The box score said it was close. The game did not feel that way."
  ✅ "It looked like control and felt like starvation."  ← same idea, now a sentence

If a line is punchy and short, it can still be a complete sentence:
  ✅ "They held on." / "Judge hit one for show." / "The rest found nothing."
The requirement is not length — it is grammatical completeness.

SILENT CHECK: Before returning, scan every sentence. If any sentence has no verb, rewrite it.

OPENING LINE RULE:
The first sentence must be specific to THIS game and non-transferable.

Avoid:
- "they survived"
- "they found a way"
- "they didn't fold"

Force:
- what decided the game
- when it was decided
- how it was held

Test: if you can swap team names and it still works → rewrite it.

CONVICTION RULE:
Do not soften the core claim to improve readability.
The opening sentence and final judgment must still carry a strong, specific take about THIS game.

Avoid safe summaries like:
- "the lineup worked"
- "execution under pressure won the game"

Prefer:
- what actually decided the game
- what did NOT matter
- what this reveals about the team

Readability improves structure — not by weakening the take.

GUARDRAIL:
Do NOT simplify the thinking.
Do NOT reduce conviction.
Do NOT make the writing generic.
Only improve readability and flow.
Strong takes are required.

STATE OF PLAY — STRUCTURE LOCK:
Enforce this exact structure for WHAT THIS GAME MEANS:

1. Opening (max 2 sentences)
   - Must reference a specific moment, stat, or turning point from THIS game
   - Must take a clear stance (what actually mattered)

2. Body (4–6 sentences max)
   - Each sentence must reference a concrete detail from THIS game (stat, player performance, sequence, or outcome)
   - Interpret those details — do not just list them
   - No general baseball commentary

3. Final sentence (punchline)
   - Maximum 12 words
   - No commas
   - Must make a definitive claim about the game
   - Must feel quotable and self-contained
   - Do not add any sentence after this

NO GENERIC ANALYSIS:
Do not explain baseball.
Avoid statements that could apply to any team or game, including phrases like:
  - "when it works"
  - "teams like this"
(See BANNED VOCABULARY above for the complete list of banned abstract terms and phrases.)
If a sentence could describe any MLB game, rewrite or delete it.

SPECIFICITY REQUIREMENT:
Every sentence must pass this test:
→ Could this only be written about THIS game?
If not, rewrite it to include:
  - a stat (hits, strikeouts, innings, runs)
  - a specific player
  - a specific moment (early innings, late innings, key sequence)

TENSION REQUIREMENT:
Each WHAT THIS GAME MEANS must include at least one tension, such as:
  - offense vs pitching
  - early vs late
  - control vs collapse
  - opportunity vs execution
The narrative should revolve around that tension.

SENTENCE DISCIPLINE:
  - Each sentence = one idea only
  - Avoid chaining ideas with "and" unless tightly related
  - If two sentences share the same subject, consider merging them
  - Do not stack more than two short sentences in a row (maintain rhythm)

FINAL CHECK (silent, do not output):
Before returning:
  - Does every sentence reference this specific game?
  - Is there exactly one clear narrative angle?
  - Is the final sentence a punchline (≤12 words, no commas)?
  - Are there zero generic or filler phrases?
If any answer is no, rewrite before returning.

EXPLANATION MODE — HARD STOP:
After the third sentence in WHAT THIS GAME MEANS, stop explaining and start concluding.
- Do not introduce new concepts after sentence three
- Do not generalize to "how baseball works"
- Do not explain patterns of the sport
- From sentence four onward, drive toward a conclusion
If a sentence sounds like analysis or commentary, cut it.

NO ANALYST VOICE:
Disallow explanatory framing entirely. Do NOT write:
- "This is about…"
- "The real problem is…"
- "This shows that…"
- "This is how…"
(See BANNED VOCABULARY above for the full list of banned formula/pattern phrases.)
Replace with direct observations and conclusions. Write like someone who watched the game, not someone explaining it after.

SENTENCE PURPOSE RULE:
Each sentence in WHAT THIS GAME MEANS must do exactly one of:
1. State what happened (specific moment or stat)
2. Interpret what that meant in THIS game
3. Push toward the conclusion
If a sentence does not clearly fit one of these, delete it.

SENTENCE SEPARATION — HARD RULE:
- One sentence = one idea
- Do not combine stat + conclusion in the same sentence
- Do not join ideas with "and" unless tightly identical
- If a sentence contains multiple clauses, split it
Short sentences are preferred over dense ones.

IDEA PURITY — HARD RULE:
One sentence must express exactly one baseball idea. Do not combine multiple subjects in a single sentence.

Disallowed combinations:
- pitching + hitting in the same sentence
- player performance + team outcome in the same sentence
- multiple moments in one sentence

If a sentence contains more than one idea, split it.

Bad: "Rodríguez struggled and the offense didn't respond."
Good: "Rodríguez struggled." / "The offense didn't respond."

Clarity is more important than flow.

BODY LIMIT — ENFORCED:
Maximum 5 sentences in the body of WHAT THIS GAME MEANS.
If more than 5:
- Cut the weakest sentence
- Prefer cutting explanation over cutting observation
Shorter is better than complete.

PUNCHLINE — NON-NEGOTIABLE:
The final sentence is mandatory and must meet ALL of the following:
- ≤ 12 words
- No commas
- No conjunctions ("and", "but", "because")
- No explanation
- Must make a definitive claim about the game

Bad: "The offense didn't show up and that's why they lost"
Good: "They never made it matter."

If the final sentence does not feel quotable, rewrite it.

PUNCHLINE ESCALATION:
The final sentence must be stronger than the sentence before it.
It should feel like a verdict, a closing argument, something a fan would repeat.
Never end on a descriptive sentence.

PUNCHLINE — SPECIFICITY UPGRADE:
The final sentence is mandatory and must meet ALL conditions:
- ≤ 12 words
- No commas
- No conjunctions (and, but, so, because, etc.)
- Must reference something specific from THIS game (stat, situation, or failure)
- Must NOT be reusable for another team or game
- Must feel like a verdict, not a summary

Bad (too generic): "That's the cost of losing games like this."
Good (specific + grounded): "Eight left on base. Nothing to show for it."

PUNCHLINE — FORCE GROUNDING:
If the punchline does not contain:
- a number (strikeouts, hits, runners, innings), OR
- a clear game situation (runners left, shutout, late chances, etc.)
→ rewrite it.
The reader should be able to recall the game from the punchline alone.

CUT THE LAST SENTENCE TEST (silent):
After writing the paragraph, remove the final sentence mentally.
If the paragraph still feels complete → the punchline is weak.
Rewrite until removing the final sentence makes the paragraph feel unfinished.

ANTI-COMPRESSION CHECK (silent — run before returning):
- No sentence contains two separate ideas
- No sentence uses "and" to merge unrelated concepts
- Each sentence stands on its own
If violated → split the sentence.

INTERNAL AUDIT (silent — run before returning):
- Did explanation mode stop after sentence 3?
- Is the body ≤ 5 sentences?
- Does every sentence reference THIS game?
- Is the final sentence a punchline (≤12 words, no commas, no conjunctions)?
- Is the final sentence grounded in a specific stat or game situation?
- Is the final sentence NOT reusable for another game?
- Is the final sentence stronger than the rest?
If any fail → rewrite.

3. WHAT TO WATCH (2 sentences max)
FUNCTION OVERRIDE — this section previews the next game ONLY. It does not reference yesterday in any way.

DATA LOCK — HARD RULE:
The NEXT GAME context above provides exactly: Our SP, Opp SP, opponent abbreviation, date, and time.
  - Opponent's starter for this preview: {_opp_sp} (the "Opp SP" above)
  - Our team's starter for this preview: {_our_sp} (the "Our SP" above — NOT the opponent's pitcher)
Do NOT name any pitcher not listed in the NEXT GAME context. Do NOT invent a pitcher.
If you are about to attribute "{_our_sp}" to the opposing team, stop — that is our pitcher.
The opponent is starting {_opp_sp}. Use that name if you reference an opposing starter.
Do NOT invent a venue or ballpark name. Only reference home/away from the "vs" or "@" in NEXT GAME.

DATE LOCK — HARD RULE:
The game is {next_day_label} ({next_game.get('date', 'TBD')}).
Write "tonight", "tomorrow", or "{next_day_label}" — these come from the verified date above.
Do NOT write any other day of the week. Do NOT guess "Sunday", "Monday", etc. from training data.

STRUCTURAL LOCK — HARD RULE:
Your WHAT TO WATCH section MUST open with the next opponent's name or the opposing pitcher's name.
If your draft does not begin with the opponent name or pitcher name, it fails. Rewrite from scratch.

It must:
- Open with: next opponent name (e.g. "MIL…") OR opposing pitcher name (e.g. "{_opp_sp}…")
- Name one specific matchup detail (pitcher's recent ERA, the opponent's offensive weakness, series context, ballpark factor)

Banned from this section:
- Any word that references yesterday's game, result, or players (no "after last night", no player names from yesterday's box score)
- "looking to" — say what the matchup actually is, not what the team hopes
- Abstract team identity claims — this section is a preview, not a verdict
- All terms in BANNED VOCABULARY apply here too: "momentum", "build on", "bounce back", "keep it going", "carry that", "the division doesn't wait"

Length: 1–2 sentences. One tight sentence is better than two vague ones. Not a recap.

SILENT CHECK: Does your first word name the opponent or opposing pitcher? If not, rewrite.

REWRITE LOOP:
After drafting WHAT THIS GAME MEANS, run a second pass if ANY of the following are true:
- a banned phrase appears (see CLARITY OVER POETRY and ANTI-GENERIC LANGUAGE)
- a sentence could describe any game by any team
- a sentence contains no observable detail (no inning, moment, player action, or sequence)

On the second pass:
- rewrite only the failing sentences
- keep the structure and punchline intact
- do not add length — shorter is better if in doubt

Maximum 2 passes. If still failing after 2, prefer shorter and blunter over longer and vague.

INTERNAL AUDIT (do not include in output — run silently before returning):
Check each item. If any required item is "N", fix before returning.

  [ ] Specific moment included? (inning / sequence / stat-as-scene)
  [ ] Final sentence is a standalone punchline?
  [ ] No banned phrases present?
  [ ] No sentence that could describe any game?

Pattern break is optional — skip if no natural pivot exists.

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

Personality allowed: dry understatement, mild edge, concise judgment, fan-aware phrasing, slight exasperation when the team earns it.
Personality to avoid: sports-radio clichés, exaggerated doom, fake hype, academic phrasing, generic motivational language.

PUNCHLINE RULE:
The final sentence of WHAT THIS GAME MEANS must be a standalone punchline. Short. Specific. Something that lingers after the reader moves on. It should feel like the natural end of an argument, not a summary.

Acceptable punchline forms:
- "That's not a slump. That's a warning light."
- "Good teams don't let nights like this stack."
- "This is how stretches start."
- "The scoreboard said close. The game did not."
- "You don't lose games like this by accident."
- "They've beaten this problem before. Not yet, though."

The punchline must be the FINAL sentence of WHAT THIS GAME MEANS. Do not follow it with another sentence. Do not soften it with a qualifier. If it doesn't work as the last thing the reader sees from this section, rewrite it.

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

CLARITY OVER POETRY:
When a sentence becomes abstract or vague, rewrite it into something literal and observable.

Do NOT write:
- "never found the moment"
- "couldn't get it going"
- "failed to capitalize"
- "didn't do enough"
- "couldn't put it together"
- "wasn't able to answer"

Write what didn't happen, when it didn't happen, and what it looked like:
- "They didn't do anything until the fifth."
- "They had two on in the eighth and got nothing."
- "Three straight empty at-bats ended it."
- "They left six on base and scored once."

Prefer blunt clarity over poetic phrasing. If it sounds elegant but says nothing specific, cut it.

CONCRETE OVER ABSTRACT:
Avoid abstract phrasing. Prefer concrete moments — when something happened, who did it, what the game looked like at that point.

Bad:  "the lineup struggled to produce"
Good: "they didn't do anything until the fifth"

Bad:  "the bullpen had a difficult outing"
Good: "two runs scored before anyone got warm"

Bad:  "they failed to capitalize on opportunities"
Good: "they left two on in the sixth and never got another chance"

If a sentence could describe any game by any team, rewrite it until it could only describe this one.

SPECIFICITY TRIGGER:
WHAT THIS GAME MEANS must contain at least one concrete, game-specific detail that anchors the narrative to this actual game.

Acceptable forms (pick one — do not stack):
- An inning: "they didn't score until the seventh"
- A moment: "after the leadoff double, nothing came of it"
- A stat used as a scene: "ten strikeouts and it still felt close"
- A sequence: "three straight empty at-bats with the tying run on second"

Rules:
- Use exactly one. Not zero, not two.
- Integrate it into a sentence naturally — not as a parenthetical, not as a standalone stat.
- Draw only from data already in LAST GAME context. Do not invent.
- The detail should make the reader feel like they watched the game, not like they read a box score.

ANTI-GENERIC LANGUAGE:
Avoid phrases that summarize broadly without adding a specific angle or judgment.

Do NOT write:
- "the inconsistency that has defined the season"
- "this team has struggled with..."
- "they have shown flashes but..."
- "the season has been up and down"

BANNED HEDGE WORDS — do not use:
- "somewhat" / "kind of" / "a bit" / "fairly"
- "may" / "could" / "might" / "appears to"
- "seems like" / "looks like" / "it's possible"
- "for the most part" / "in some ways"

BANNED FILLER PHRASES — do not use:
- "held up its end"
- "wasn't enough" (say what fell short instead)
- "going forward"
- "ultimately"
- "at the end of the day"
- "the story was"
- "found a way" (say HOW)
- "showed up" (say WHAT they did)

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

BOX SCORE HONESTY — GAME DRIVER ≠ ONLY OFFENSE:
Do not frame a Game Driver as the only source of offense if the team box score shows broad production.

If the team has:
- 10+ hits, OR
- 6+ runs, OR
- 5+ players with hits, OR
- multiple players with RBI

Then avoid phrases like:
- "only real firepower"
- "only reason they were in it"
- "carried the offense alone"
- "no one else showed up"

Instead frame the Game Driver as:
- the separator
- the finisher
- the swing that mattered
- the player who converted runners on base into runs
- the player who made broad production count

Good examples:
  ✅ "The lineup got runners on. [Player] drove them in."
  ✅ "This was a team offense with one clear separator."
  ✅ "Everyone touched the game; [Player] changed it."
  ✅ "The bats showed up. [Player] made it matter."

Strong takes are still allowed. The rule is not "be softer."
The rule is: make the strong take match the box score.
If production is broad, the take should distinguish impact from exclusivity.

TONAL VARIATION:
Let the game type shape the writing — subtly, not conspicuously.
  GRITTY     → shorter sentences, physical verbs ("held on", "scratched out", "didn't break", "survived")
  DOMINANT   → confident, declarative ("they controlled this game", "this wasn't close")
  FRAGILE    → tension, skepticism in reserve ("this works until it doesn't", "they won by one run again")
  CHAOTIC    → slightly more energy, irregular rhythm, comma-sparse sentences
  CLINICAL   → plain, even, no added heat — let the facts do the work
Do not overdo this. The shift should be felt across 2–3 word choices, not performed as a style.

BLOWOUT TONE — HARD RULE (applies when blowout_by_5th = YES or game decided by inning ≤ 4):
Write matter-of-factly. The game was decided early. There is no late tension to manufacture.

Banned in blowout contexts:
  "swallowed a team whole"
  "put up a fight" (unless the team actually scored 3+ runs)
  "couldn't recover"
  "the season pressure"
  "exposed" (unless naming a specific structural weakness clearly caused by this game)
  philosophical overreach about what this means for the division race
  (See BANNED VOCABULARY for additional banned abstract terms.)

Required in blowout contexts:
  State what happened early and when — one clear sentence about when control was established.
  Keep the WHAT THIS GAME MEANS tight (aim for 70–90 words, not 120).
  The punchline should be simple and direct, not grand.

Example: "Warren gave Texas six runs in four innings. The game was over by the time the lineup woke up. Judge hit one for show. The rest of the offense logged nine strikeouts and left early."
Do not write a blowout like a drama. It was not.

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

VOICE VARIATION — CONTROLLED UNHINGED:
The brief should read like a sharp human observer, not a template. Keep it accurate and grounded — but allow slightly more edge, surprise, and personality.

1. DO NOT reuse abstract framing across briefs.
   When you reach for any abstract framing phrase, replace it with a concrete observation from the actual game.
   (See BANNED VOCABULARY earlier in these instructions for the full list with replacement guidance.)

2. Replace abstract framing with something sharper and game-specific.
   Bad:  "This is the pattern getting louder."
   Good: "Six hits and no runs is not a slump. It's a locked door."

   Bad:  "That's the margin they're working with."
   Good: "They won by one run for the third time in five games. That math gets harder."

3. Allow up to one controlled unhinged line per State of Play section.
   Use it only if it naturally fits the game. Do not force it into low-event or straightforward games.
   Requirements for that line:
   - Grounded in something that actually happened in the game
   - Short — the effect comes from brevity
   - Memorable — a reader should still be thinking about it 10 seconds later
   - Not random, not meme-like, not mean-spirited toward an individual player
   Examples of the register:
   - "The bats didn't go cold. They left the building."
   - "Two runners on, two outs, nobody home. Three times."
   - "A one-run lead is not a plan."
   - "Five hits is not offense. It's attendance."
   - "They brought a pocketknife to a bullpen game."
   If no line of this quality can be written from the actual game, skip it. Do not force the register.

4. Vary sentence openings.
   Do not start multiple sentences in the same section with the same word or phrase.
   Avoid opening consecutive sentences with:
   - "They"
   - "This"
   - "That"
   - "The offense"
   - "The lineup"
   If you notice two sentences opening the same way, rewrite the second.

5. Vary punchline structure.
   The final sentence of WHAT THIS GAME MEANS must not always follow the same form.
   Use different modes — pick the one that fits the game:
   - verdict:  "They wasted the window."
   - image:    "The door was open. Nobody walked through."
   - contrast: "The pitching gave them air. The bats gave it back."
   - blunt fact: "Eight left on base. Zero reward."
   Do not default to the same mode two days running.
   The punchline must connect directly to something mentioned earlier in the paragraph.
   Do not introduce a new abstract idea in the final sentence.

6. Do not stack metaphors.
   Use at most one metaphor or image per paragraph.
   If a metaphor is used, the next sentence must return to concrete baseball detail.

7. Do not be clever for the sake of being clever.
   If a line feels decorative instead of observational — something that would read the same regardless of what happened in the game — remove or rewrite it.

8. Accuracy is non-negotiable.
   Do not invent emotion, drama, streaks, injuries, quotes, broadcast narratives, or league context not present in the data. The edge must come from a real game observation stated more sharply — not from fabricated stakes.

9. If you can swap team names and the paragraph still works, rewrite it.

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

SPECIFICITY RULE — prefer naming the pitcher over generic phrases:
When a reliever or closer appears in the box score or in high-leverage moments (7th inning onward, close game, save situation), name them directly.
Examples:
* "Doval closed it out."
* "Rogers bridged the gap into the ninth."
* "Hader got the call and it wasn't close."

Avoid generic phrasing:
* DO NOT write "the bullpen held" or "the bullpen did its job" or "the back end delivered" when a specific pitcher drove the outcome.

Keep any bullpen reference to ONE clause max — do not expand into a full bullpen recap.

Do NOT force bullpen mention if:
* Starter went deep and dominated
* Game was not close late

But if:
* Starter exits early
* Game is close late
* Lead changes hands after the 6th

→ bullpen should be part of the explanation, with the relevant pitcher named if identifiable.

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

GAME STORY GUARDRAILS (when GAME STORY SIGNALS are present):
- Do not contradict GAME STORY SIGNALS. If signals show 0 missed opportunities, do not write about squandered chances. If no rally sequence is detected, do not describe a comeback.
- Do not claim atmosphere, crowd reaction, broadcast tone, or ballpark energy unless explicitly provided in the context data.
- Do not describe a player as dominant, clean, clutch, or the rescuer unless TURNING POINT or GAME DRIVER data with HIGH confidence supports it.
- Do not print a game archetype or shape label directly in the output. Let it guide structure and word choice — do not announce it.

{voice_block}

FINAL VOICE AUDIT (silent — do NOT include in output, run before returning):
Answer each question internally. If any answer fails, rewrite before returning.

  [ ] Can team names be swapped and the paragraph still work?
        If yes → rewrite. At least one sentence must be anchored to a detail only this game produced.
  [ ] Does any sentence use banned abstract framing ("this is the pattern", "that's the margin",
        "this is the formula", "this is the cost", "this is what happens when", "the story is", "the problem is")?
        If yes → replace with a concrete observation from the actual game.
  [ ] Is there one concrete, memorable line in State of Play that a reader would recall?
        If no → find the sharpest moment in the game and write it more directly.
  [ ] Is any edge or sharpness grounded in the actual game — not invented drama?
        If no → soften or rewrite. Accuracy is not optional.
  [ ] Does WHAT TO WATCH name the next opponent or probable pitcher with at least one specific detail?
        If no → rewrite using NEXT GAME context.
  [ ] Do multiple sentences in the same section start with the same word?
        If yes → rewrite the second sentence's opening.
  [ ] Was a metaphor or image used? If yes — is it limited to one per paragraph, and is it followed by concrete baseball detail?
        If no → remove the second metaphor or add the grounding sentence.
  [ ] Does the punchline connect directly to something mentioned earlier in the paragraph?
        If no → rewrite the punchline so it lands on prior content, not a new abstraction.
  [ ] Does any line feel decorative — clever-sounding but not observational?
        If yes → remove or rewrite it.
  [ ] If the game was low-scoring or uneventful, does the writing still read naturally rather than forced?
        If no → remove any strained edge and let the plain facts carry it.

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
- WHAT TO WATCH must be 2 sentences max. It previews the next game only — name the opponent and/or probable pitcher. Do NOT reference yesterday's game, result, or players. Do NOT use pattern language ("build on", "momentum", "bounce back"). Do NOT quote or restate the NEXT GAME HOOK stat verbatim.
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


def generate_postponed_narrative(last_game: dict, next_game: dict | None = None) -> dict:
    """
    Deterministic narrative for a postponed game — no Claude call.
    Returns the same shape as generate_narrative_copy() so callers need no branching.
    """
    reason = last_game.get("postponed_reason", "").strip()
    makeup = last_game.get("makeup_date")

    # State of Play: one sharp acknowledgment. Reason stated once, briefly.
    if reason:
        top_frame = f"No game last night. {reason.capitalize()} got it."
    else:
        top_frame = "No game last night. Postponed."

    # What to Watch: makeup status + next game. No restatement of the cause.
    what_to_watch_parts = []

    if makeup:
        what_to_watch_parts.append(f"Makeup date: {makeup}.")
    else:
        what_to_watch_parts.append("Makeup date TBD.")

    if next_game:
        ng_ha   = "vs" if next_game.get("home") else "@"
        ng_opp  = next_game.get("opponent", "")
        ng_date = next_game.get("date", "")
        if ng_opp and ng_date:
            try:
                from datetime import datetime as _dt
                d = _dt.strptime(ng_date, "%Y-%m-%d")
                ng_date_label = d.strftime("%A, %B %-d")
            except Exception:
                ng_date_label = ng_date
            what_to_watch_parts.append(f"Next up: {ng_ha} {ng_opp} on {ng_date_label}.")

    return {
        "top_frame":       top_frame,
        "what_this_means": "",
        "what_to_watch":   " ".join(what_to_watch_parts),
    }


def clean_narrative_text(text: str) -> str:
    """
    Post-processing guardrail: strip markdown formatting and replace em dashes.
    Prevents markdown headers, bold labels, and em dashes from reaching HTML output.
    """
    if not text:
        return text

    # Strip markdown bold/italic and headers that the model occasionally emits
    text = re.sub(r"^\s*#+\s*", "", text, flags=re.MULTILINE)  # ## headers
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)             # **bold**
    text = re.sub(r"\*([^*]+)\*", r"\1", text)                 # *italic*
    text = text.strip()

    if "—" not in text:
        return text

    def _replace(m):
        after = m.group(1)
        if after:
            return ". " + after[0].upper() + after[1:]
        return ". "

    result = re.sub(r"\s*—\s*(\S?)", _replace, text)
    result = re.sub(r"\.\.+", ".", result)   # collapse double periods
    result = re.sub(r"  +", " ", result)     # collapse double spaces
    return result.strip()


def _is_structural_label(text: str) -> bool:
    """
    Returns True if a paragraph is a structural label the model emits despite
    being told not to — e.g. '# YANKEES MORNING BRIEF', '**TOP FRAME**', '1. TOP FRAME'.
    These are never valid narrative content and should be skipped by the parser.
    """
    t = text.strip()
    # Markdown heading
    if re.match(r"^#+\s", t):
        return True
    # Pure bold label: **SOME LABEL** (whole paragraph is just the bold span)
    if re.match(r"^\*\*[A-Z0-9 ]+\*\*$", t):
        return True
    # Numbered section header: "1. TOP FRAME" or "3. WHAT TO WATCH"
    if re.match(r"^\d+\.\s+[A-Z ]+$", t):
        return True
    # All-caps short label (≤ 8 words, no sentence punctuation)
    if re.match(r"^[A-Z][A-Z0-9 ]{0,60}$", t) and "." not in t and "," not in t:
        return True
    return False


def _narrative_fallback(reason):
    import sys
    print(f"  [narrative] Falling back to deterministic insight because: {reason}", file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# Phase 3.2: Validation helpers — fragment defense and WHAT TO WATCH lock
# ---------------------------------------------------------------------------

# Conservative fragment patterns: only known offenders, not generic heuristics
_FRAGMENT_PATTERNS = [
    # Sentence opens with "Is" or "Was" without a subject
    re.compile(r'^(Is|Was)\s+\w', re.IGNORECASE),
    # Prepositional phrase used as sentence: "Against St. Louis, at home..."
    re.compile(r'^Against\s+[A-Z]'),
    # Noun-phrase with location: "That margin in the sixth."
    re.compile(r'^That\s+\w+\s+(in|at|of|through|during|by)\b.*\.$'),
]


def _detect_fragments(text):
    """Return list of sentences matching known fragment patterns."""
    if not text:
        return []
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    violations = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        for pat in _FRAGMENT_PATTERNS:
            if pat.match(s):
                violations.append(s)
                break
    return violations


def _check_watch_preview(text, ng_opponent, ng_probable):
    """
    Return True if the first sentence of WHAT TO WATCH names the next opponent
    or the probable pitcher. Comparison is case-insensitive, word-level.
    """
    if not text:
        return False
    first_sentence = re.split(r'(?<=[.!?])\s+', text.strip())[0].lower()
    for name in (ng_opponent, ng_probable):
        if not name:
            continue
        for word in name.lower().split():
            if len(word) >= 3 and word in first_sentence:
                return True
    return False


def generate_narrative_copy(brief_data, story_state, delta, team_name,
                            story_threads=None, story_hook=None, looking_ahead_hook=None,
                            game_driver=None):
    """
    Call the Anthropic API to generate AI-written narrative copy.
    Returns a dict with top_frame, what_this_means, what_to_watch — or None on failure.
    Logs a clear reason on every fallback path.

    Phase 3.2: validates fragments in what_this_means and opponent/pitcher in
    what_to_watch.  On first-attempt violations, retries once with an explicit
    RETRY VIOLATION NOTICE appended to the prompt.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _narrative_fallback("ANTHROPIC_API_KEY is not set")

    next_game   = brief_data.get("next_game") or {}
    ng_opponent = (next_game.get("opponent") or "").strip()
    _ng_prob    = (next_game.get("probable") or {})
    # Validate that the model names the OPPONENT's starter (opp), not ours (team).
    # Fallback to our SP only when no opp SP is available.
    ng_probable = (_ng_prob.get("opp") or _ng_prob.get("team") or "").strip()

    base_prompt = _build_narrative_prompt(
        brief_data, story_state, delta, team_name,
        story_threads=story_threads,
        story_hook=story_hook,
        looking_ahead_hook=looking_ahead_hook,
        game_driver=game_driver,
    )
    system = _build_narrative_system(team_name)

    last_result    = None
    violation_note = ""

    for attempt in range(2):
        prompt = base_prompt + violation_note if violation_note else base_prompt

        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key":         api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type":      "application/json",
                },
                json={
                    "model":      "claude-sonnet-4-6",
                    "max_tokens": 900,
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

        all_paras  = [p.strip() for p in raw.split("\n\n") if p.strip()]
        paragraphs = [p for p in all_paras if not _is_structural_label(p)]
        if len(paragraphs) < 2:
            return _narrative_fallback(
                f"response had fewer than 2 content paragraphs "
                f"(got {len(paragraphs)} after stripping labels)"
            )

        top_frame       = clean_narrative_text(paragraphs[0])
        what_this_means = clean_narrative_text(paragraphs[1])
        what_to_watch   = clean_narrative_text(paragraphs[2]) if len(paragraphs) >= 3 else ""

        last_result = {
            "top_frame":       top_frame,
            "what_this_means": what_this_means,
            "what_to_watch":   what_to_watch,
        }

        # --- Phase 3.2 validation ---
        violations = []

        frags = _detect_fragments(what_this_means)
        if frags:
            for f in frags:
                print(f"  warn [fragment_violation]: {f!r}", file=sys.stderr)
            violations.append(
                "FRAGMENT VIOLATIONS detected in WHAT THIS GAME MEANS:\n"
                + "\n".join(f"  - {f!r}" for f in frags)
                + "\n  Every sentence must have a subject and a finite verb. "
                "Rewrite each fragment into a complete sentence."
            )

        if not _check_watch_preview(what_to_watch, ng_opponent, ng_probable):
            print(
                f"  warn [watch_preview_violation]: WHAT TO WATCH did not open with "
                f"opponent ({ng_opponent!r}) or pitcher ({ng_probable!r})",
                file=sys.stderr,
            )
            violations.append(
                "WHAT TO WATCH VIOLATION:\n"
                f"  Your WHAT TO WATCH did not open with the next opponent name or probable pitcher.\n"
                f"  Required: first sentence must begin with or clearly name '{ng_opponent}' "
                f"or pitcher '{ng_probable}'.\n"
                "  Rewrite WHAT TO WATCH from scratch. First word must be the opponent or pitcher name."
            )

        # Phase 3.3: chronology violation check
        _gs_chron = (brief_data.get("game_story") or {}).get("game_shape") or {}
        _ftt_val  = _gs_chron.get("first_team_trail_inning")
        if _ftt_val is not None and _ftt_val >= 7:
            _chron_text = f"{what_this_means} {what_to_watch}"
            _chron_pats = [
                (
                    re.compile(
                        r'\btrailed after the (first|second|third|fourth|fifth)\b',
                        re.IGNORECASE,
                    ),
                    "false early-trail phrase",
                ),
                (
                    re.compile(r'\btied it up\b', re.IGNORECASE),
                    "'tied it up' implies the team trailed then equalized — they did not",
                ),
                (
                    re.compile(r'\bspent.{0,20}chasing\b', re.IGNORECASE),
                    "chasing language when team led early",
                ),
            ]
            _chron_hits = [label for pat, label in _chron_pats if pat.search(_chron_text)]
            if _chron_hits:
                for _ch in _chron_hits:
                    print(f"  warn [chronology_violation]: {_ch}", file=sys.stderr)
                violations.append(
                    f"CHRONOLOGY VIOLATION — team did NOT trail until inning {_ftt_val}:\n"
                    + "\n".join(f"  - {h}" for h in _chron_hits)
                    + f"\n  Do NOT write 'trailed after the second' (or any early inning),"
                    f" 'tied it up', or 'spent the night chasing'.\n"
                    f"  The team LED or was TIED until inning {_ftt_val}."
                    f" Frame as: lead held, game tied, lead lost in inning {_ftt_val}."
                )

        # Phase 3.3: RISP production check
        _risp_val  = (brief_data.get("game_story") or {}).get("risp_conversion") or {}
        _rc_sc_val = _risp_val.get("risp_pa_with_run_scored", 0)
        if _rc_sc_val > 0:
            _risp_empty_pats = [
                re.compile(r'\bnothing to show\b', re.IGNORECASE),
                re.compile(r'\bcame up empty\b', re.IGNORECASE),
            ]
            for _rp in _risp_empty_pats:
                if _rp.search(what_this_means):
                    print(
                        "  warn [risp_violation]: false RISP-empty claim in what_this_means",
                        file=sys.stderr,
                    )
                    violations.append(
                        f"RISP PRODUCTION VIOLATION:\n"
                        f"  WHAT THIS GAME MEANS implies zero RISP production, but the team\n"
                        f"  scored on {_rc_sc_val} RISP plate appearance(s).\n"
                        f"  Do NOT write 'nothing to show', 'came up empty', or similar.\n"
                        f"  Rewrite to acknowledge the {_rc_sc_val} run(s) scored in RISP situations."
                    )
                    break

        if not violations:
            print("  [narrative] AI narrative generated successfully", file=sys.stderr)
            return last_result

        if attempt == 0:
            violation_note = (
                "\n\n--- RETRY VIOLATION NOTICE (fix ALL issues before returning) ---\n"
                + "\n\n".join(violations)
                + "\n--- END VIOLATION NOTICE ---"
            )
            print(
                f"  [narrative] attempt 1 had {len(violations)} violation(s) — retrying",
                file=sys.stderr,
            )

    # Return last attempt even if validation still fails on retry
    print("  [narrative] AI narrative generated (with unresolved violations)", file=sys.stderr)
    return last_result
