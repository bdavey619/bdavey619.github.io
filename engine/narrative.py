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
# Narrative generation — Claude writes from structured context
# ---------------------------------------------------------------------------

def _build_narrative_system(team_name):
    return (
        f"You are the editorial voice of the {team_name} Morning Brief — "
        "a daily dispatch that answers: \"What changed about the team's story today?\"\n\n"
        "You take editorial stances. You explain *why* something matters, not just *what* happened. "
        "You write for a fan who already knows the score and wants to understand what it means."
    )


def _build_narrative_prompt(brief_data, story_state, delta, team_name):
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
            f"\nCLUTCH MOMENT (play-by-play, HIGH CONFIDENCE):\n"
            f"  {clutch['name']} — {clutch['event']}, inning {clutch['inning']}\n"
            f"  {clutch['name']} {clutch['description']}\n"
            f"  Reason: {clutch['reason']}"
        )
    elif clutch and clutch.get("confidence") == "low":
        clutch_block = (
            f"\nCLUTCH MOMENT (fallback — box score only, LOW CONFIDENCE):\n"
            f"  {clutch['name']}: {clutch['event']}\n"
            f"  Do NOT anchor the narrative on this player."
        )
    else:
        clutch_block = "\nCLUTCH MOMENT: none detected"

    emotion = story_state.get("game_emotion_level", "normal")
    if emotion == "extreme":
        voice_block = """VOICE — EXTREME EMOTION (game_emotion_level: extreme):
- TOP FRAME must open with the dramatic event. Make the moment feel real and earned — not hyped.
- WHAT THIS GAME MEANS: be vivid. Lead with the emotional core of what happened, then connect it back to the larger team narrative.
- Genuine energy is appropriate. But stay editorial. No all-caps, no exclamation marks, no manufactured urgency.
- Forbidden phrases: "for the ages", "absolute madness", "unbelievable scenes", "one they'll never forget", "chaos", "mayhem"."""
    elif emotion == "high":
        voice_block = """VOICE — HIGH EMOTION (game_emotion_level: high):
- TOP FRAME should acknowledge the key game event — the go-ahead run, the comeback, the dominant individual performance.
- WHAT THIS GAME MEANS: open with what happened, then zoom out to what it signals about this team right now.
- Some energy is appropriate but stay controlled. Analytical precision should still come through."""
    else:
        voice_block = """VOICE — NORMAL (game_emotion_level: normal):
- Lead with pattern and meaning, not game events. The editorial stance is the value.
- Stay calm, analytical, and grounded. Do not manufacture drama from a routine result."""

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

LAST GAME:
  Result:      {result_line}
  Key pitcher: {pitcher_text}
  Key hitters: {hitters_text}
  Offense:     {offense_note}
{clutch_block}

TEAM CONTEXT:
  Record: {team.get('record')} · Streak: {team.get('streak')} · Last 10: {team.get('last10')}
  ERA: {team.get('era')} · OPS: {team.get('ops')} · Avg: {team.get('avg')}
  Division: Rank {team.get('division_rank')} · {team.get('games_back')} back

NEXT GAME:
  {next_text}

--- OUTPUT INSTRUCTIONS ---

Write exactly three sections. No headers. No labels. No bullet points. Just clean prose.

1. TOP FRAME (1 sentence, max 25 words)
A sharp editorial judgment on what today's result means in the context of the season. Not a score recap. A stance.

2. WHAT THIS GAME MEANS (2–3 sentences)
What does this game confirm, challenge, or reveal about the current narrative? If the story changed, say exactly how. If it held, say what held and why that matters.

3. WHAT TO WATCH (1–2 sentences)
Specific and forward-looking. Name the next game, pitcher, matchup, or pressure point the reader should track. Tie it to what just happened.

{voice_block}

HARD RULES:
- Do NOT summarize the game. The reader already knows the score.
- Do NOT repeat yesterday's framing unless the delta shows nothing changed — if so, say that directly.
- Do NOT use: "bats need to wake up", "must-win", "firing on all cylinders", "big time", "impressive", "heading into", "looking to".
- Do NOT speculate with "could" or "might". Extrapolate from what IS happening.
- Use specific stats from the context above. Do not invent numbers.
- Take a clear editorial stance. Use active voice.
- If trend is "surging": the question is how long can this hold?
- If trend is "fragile" or "slipping": be honest about the problem. Do not soften it.
- If driver is "pitching" and OPS < 0.700: do not frame the offense as fine.
- If delta signals show no change: acknowledge the story did not move today and say what that means.
- CLUTCH MOMENT: If confidence is HIGH, anchor the narrative on that player's moment when writing WHAT THIS GAME MEANS. Name the player and what they did. Use it to explain what fans will remember — not just the outcome, but who made it happen. If confidence is LOW or none detected, do not force a clutch reference.

Output format: three paragraphs separated by a blank line. Nothing else."""


def _narrative_fallback(reason):
    import sys
    print(f"  [narrative] Falling back to deterministic insight because: {reason}", file=sys.stderr)
    return None


def generate_narrative_copy(brief_data, story_state, delta, team_name):
    """
    Call the Anthropic API to generate AI-written narrative copy.
    Returns a dict with top_frame, what_this_means, what_to_watch — or None on failure.
    Logs a clear reason on every fallback path.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _narrative_fallback("ANTHROPIC_API_KEY is not set")

    prompt = _build_narrative_prompt(brief_data, story_state, delta, team_name)
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
