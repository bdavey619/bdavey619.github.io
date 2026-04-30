"""
engine/signals.py — Deterministic "Signals" callouts for team briefs.

build_signals(last_game, season, team_id) -> list[dict], max 2 items.

Each signal is {"label": str, "value": str}, e.g.
  {"label": "Logan Webb", "value": "quality start, 6.1 IP / 2 ER"}
  {"label": "Matt Chapman", "value": "MLB HR leader, 12 HR"}

Signal 1 — quality start: derived from full_box.pitching[0], no API call.
Signal 2 — league leader: one stats/leaders call for HR, OPS, ERA, saves.
"""

import requests
from urllib.parse import urlencode

API = "https://statsapi.mlb.com/api/v1"
TIMEOUT = 15

_LEADER_CATEGORIES = ["homeRuns", "onBasePlusSlugging", "earnedRunAverage", "saves"]

# (bullet value format string)
_LEADER_VALUE = {
    "homeRuns":           "MLB HR leader, {v} HR",
    "onBasePlusSlugging": "MLB OPS leader, {v}",
    "earnedRunAverage":   "MLB ERA leader, {v}",
    "saves":              "MLB saves leader, {v} SV",
}


def _get(path, **params):
    url = f"{API}/{path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def _parse_ip(ip_str):
    """Convert MLB fractional IP string ('6.1' = 6⅓) to real float."""
    try:
        parts = str(ip_str).split(".")
        whole = int(parts[0])
        thirds = int(parts[1]) if len(parts) > 1 else 0
        return whole + thirds / 3.0
    except (ValueError, TypeError, IndexError):
        return 0.0


def quality_start_signal(last_game):
    """Return a quality-start signal dict, or None."""
    if not last_game or last_game.get("status") != "final":
        return None
    box = last_game.get("full_box") or {}
    pitching = box.get("pitching") or []
    if not pitching:
        return None
    starter = pitching[0]
    ip = _parse_ip(starter.get("ip", 0))
    try:
        er = int(starter.get("er", 99))
    except (ValueError, TypeError):
        return None
    if ip >= 6.0 and er <= 3:
        name = starter.get("name", "Starter")
        return {"label": name, "value": f"quality start, {starter['ip']} IP / {er} ER"}
    return None


def fetch_league_leaders(season, team_id):
    """Return a league-leader signal dict for team_id, or None.

    Calls stats/leaders once for HR, OPS, ERA, saves. Returns the first
    category where the #1 leader is on this team.
    """
    try:
        data = _get(
            "stats/leaders",
            leaderCategories=",".join(_LEADER_CATEGORIES),
            season=season,
            sportId=1,
            limit=50,
        )
    except Exception:
        return None

    for cat_block in data.get("leagueLeaders", []):
        category = cat_block.get("leaderCategory", "")
        leaders = cat_block.get("leaders", [])
        if not leaders:
            continue
        top = leaders[0]
        team = top.get("team") or {}
        if int(team.get("id", -1)) != int(team_id):
            continue
        name = (top.get("person") or {}).get("fullName", "")
        if not name:
            continue
        value = str(top.get("value", ""))
        fmt = _LEADER_VALUE.get(category, "MLB {cat} leader, {v}").format(v=value, cat=category)
        return {"label": name, "value": fmt}

    return None


def build_signals(last_game, season, team_id):
    """Return list of up to 2 signal dicts: [{"label": str, "value": str}, ...]."""
    signals = []

    qs = quality_start_signal(last_game)
    if qs:
        signals.append(qs)

    if len(signals) < 2:
        leader = fetch_league_leaders(season, team_id)
        if leader:
            signals.append(leader)

    return signals
