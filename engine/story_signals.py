"""engine/story_signals.py — Deterministic game driver detection.

Identifies the player most responsible for shaping the game overall,
distinct from the clutch moment (Turning Point / highest-leverage single play).

No AI inference. All decisions derive from box score stats only.
"""

import re


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_hr(line):
    """Parse HR count from a key hitter line like '2-4, 2 HR, 2 RBI'."""
    m = re.search(r'(\d+)\s*HR', line or "")
    return int(m.group(1)) if m else 0


def _parse_rbi(line):
    m = re.search(r'(\d+)\s*RBI', line or "")
    return int(m.group(1)) if m else 0


def _parse_hits(line):
    """Parse H from '2-4, ...' style lines (first number before the dash)."""
    m = re.match(r'(\d+)-\d+', line or "")
    return int(m.group(1)) if m else 0


# ---------------------------------------------------------------------------
# Hitter driver detection
# ---------------------------------------------------------------------------

def _detect_hitter_driver(key_hitters, full_box):
    """Return hitter game driver from key hitter lines, or None."""
    if not key_hitters:
        return None

    # High-confidence pass: 2+ HR or 4+ RBI
    for h in key_hitters:
        name = h.get("name", "")
        line = h.get("line", "")
        hr   = _parse_hr(line)
        rbi  = _parse_rbi(line)

        if hr >= 2:
            return {
                "name":        name,
                "type":        "hitter",
                "reason":      f"{hr}-HR game",
                "description": f"powered the offense with {hr} home runs.",
                "confidence":  "high",
            }

        if rbi >= 4:
            return {
                "name":        name,
                "type":        "hitter",
                "reason":      f"{rbi}-RBI game",
                "description": f"drove in {rbi} runs to fuel the offense.",
                "confidence":  "high",
            }

    # Medium-confidence pass: 3+ RBI or HR + 2+ RBI
    for h in key_hitters:
        name = h.get("name", "")
        line = h.get("line", "")
        hr   = _parse_hr(line)
        rbi  = _parse_rbi(line)

        if rbi >= 3:
            return {
                "name":        name,
                "type":        "hitter",
                "reason":      f"{rbi}-RBI game",
                "description": f"drove in {rbi} runs to fuel the offense.",
                "confidence":  "medium",
            }

        if hr >= 1 and rbi >= 2:
            return {
                "name":        name,
                "type":        "hitter",
                "reason":      f"{hr} HR, {rbi} RBI",
                "description": f"led the offense with a home run and {rbi} RBI.",
                "confidence":  "medium",
            }

    return None


# ---------------------------------------------------------------------------
# Pitcher driver detection
# ---------------------------------------------------------------------------

def _detect_pitcher_driver(key_pitcher, full_box):
    """Return pitcher game driver from full box score, or None."""
    if not key_pitcher:
        return None

    pitching = (full_box or {}).get("pitching") or []
    if not pitching:
        return None

    starter = pitching[0]
    name = starter.get("name") or key_pitcher.get("name", "")

    try:
        ip = float(str(starter.get("ip", "0")))
    except (TypeError, ValueError):
        ip = 0.0

    try:
        er = int(starter.get("er", 99))
    except (TypeError, ValueError):
        er = 99

    try:
        k = int(starter.get("k", 0))
    except (TypeError, ValueError):
        k = 0

    # High confidence: 10+ K
    if k >= 10:
        return {
            "name":        name,
            "type":        "pitcher",
            "reason":      f"{k}-strikeout outing",
            "description": f"dominated with {k} strikeouts.",
            "confidence":  "high",
        }

    # High confidence: 6+ IP, 0 ER
    if ip >= 6.0 and er == 0:
        return {
            "name":        name,
            "type":        "pitcher",
            "reason":      f"{ip:.1f} IP, shutout",
            "description": f"shut down the opposition over {ip:.1f} scoreless innings.",
            "confidence":  "high",
        }

    # High confidence: 7+ IP, ≤1 ER
    if ip >= 7.0 and er <= 1:
        return {
            "name":        name,
            "type":        "pitcher",
            "reason":      f"{ip:.1f} IP, {er} ER",
            "description": f"went {ip:.1f} innings and allowed just {er} earned run.",
            "confidence":  "high",
        }

    # Medium confidence: 6+ IP, 1 ER
    if ip >= 6.0 and er <= 1:
        return {
            "name":        name,
            "type":        "pitcher",
            "reason":      f"{ip:.1f} IP, {er} ER",
            "description": f"delivered quality innings, allowing {er} earned run over {ip:.1f} frames.",
            "confidence":  "medium",
        }

    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def identify_game_driver(full_box, key_hitters, key_pitcher):
    """
    Deterministically identify the player who most shaped the game overall.
    Complements the clutch moment (Turning Point); does not replace it.

    Detection priority:
    - Hitter with 2+ HR      → high confidence
    - Hitter with 4+ RBI     → high confidence
    - Dominant starter       → high confidence (10+ K, 6+ IP 0 ER, 7+ IP ≤1 ER)
    - Hitter with 3+ RBI     → medium
    - Hitter with HR + 2 RBI → medium
    - Starter 6+ IP, 1 ER   → medium

    When hitter and pitcher both qualify at high confidence, a 2+ HR hitter wins
    (offense is more memorable to fans). Otherwise the higher-confidence driver wins,
    with hitters preferred on ties.

    Returns a dict with name, type, reason, description, confidence — or None.
    """
    hitter_driver  = _detect_hitter_driver(key_hitters, full_box)
    pitcher_driver = _detect_pitcher_driver(key_pitcher, full_box)

    if hitter_driver and pitcher_driver:
        hd_conf = hitter_driver["confidence"]
        pd_conf = pitcher_driver["confidence"]

        # Both high: 2+ HR hitter beats pitcher; otherwise pitcher wins
        if hd_conf == "high" and pd_conf == "high":
            if "HR" in hitter_driver.get("reason", ""):
                return hitter_driver
            return pitcher_driver

        if hd_conf == "high":
            return hitter_driver
        if pd_conf == "high":
            return pitcher_driver

        # Both medium → prefer hitter
        return hitter_driver

    return hitter_driver or pitcher_driver
