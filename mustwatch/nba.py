"""
nba.py — NBA data fetcher for Must Watch This Week.

Fetches schedule + standings from the ESPN unofficial API.
Returns (list[RawEvent], dict[str, TeamContext]) keyed by "NBA:{abbr}".
"""

import sys
from datetime import datetime, date, timedelta, timezone

import requests

from models import RawEvent, TeamContext

ESPN_API      = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
ESPN_API_V2   = "https://site.api.espn.com/apis/v2/sports/basketball/nba"
TIMEOUT       = 15

# ESPN uses non-standard abbreviations for some teams — normalize to match config.py
ESPN_ABBR_MAP = {
    "GS":   "GSW",   # Golden State Warriors
    "NY":   "NYK",   # New York Knicks
    "SA":   "SAS",   # San Antonio Spurs
    "NO":   "NOP",   # New Orleans Pelicans
    "WSH":  "WAS",   # Washington Wizards
    "UTAH": "UTA",   # Utah Jazz
    "PHO":  "PHX",   # Phoenix Suns (alternate ESPN form)
}


def _get(url: str, **params) -> dict:
    r = requests.get(url, params=params or None, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def fetch_week(week_start: date, week_end: date) -> tuple[list[RawEvent], dict[str, TeamContext]]:
    """
    Fetch all NBA games in [week_start, week_end] plus standings.
    Returns (events, contexts) where contexts is keyed by "NBA:{abbr}".
    """
    print("  [NBA] fetching standings...", file=sys.stderr)
    contexts = _fetch_standings()
    print(f"  [NBA] standings loaded for {len(contexts)} teams", file=sys.stderr)

    print("  [NBA] fetching schedule...", file=sys.stderr)
    events = []
    current = week_start
    while current <= week_end:
        date_str = current.strftime("%Y%m%d")
        try:
            day_events = _fetch_day(date_str)
            events.extend(day_events)
        except Exception as e:
            print(f"  [NBA] warn: failed fetching {date_str}: {e}", file=sys.stderr)
        current += timedelta(days=1)

    print(f"  [NBA] {len(events)} events normalized", file=sys.stderr)
    return events, contexts


def _fetch_day(date_str: str) -> list[RawEvent]:
    data = _get(f"{ESPN_API}/scoreboard", dates=date_str, limit=20)
    events = []
    for ev in data.get("events", []):
        raw = _normalize_event(ev)
        if raw:
            events.append(raw)
    return events


def _normalize_event(ev: dict) -> RawEvent | None:
    try:
        comp        = ev.get("competitions", [{}])[0]
        competitors = comp.get("competitors", [])
        if len(competitors) < 2:
            return None

        home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

        home_team = home.get("team", {})
        away_team = away.get("team", {})

        game_time_str = ev.get("date", comp.get("date", ""))
        game_time     = datetime.fromisoformat(game_time_str.replace("Z", "+00:00"))

        # Local date in ET
        et        = timezone(timedelta(hours=-4))
        local_dt  = game_time.astimezone(et)
        game_date = local_dt.date()

        # season.type: 1=pre, 2=regular, 3=postseason (includes play-in)
        season_type   = ev.get("season", {}).get("type", 2)
        is_postseason = (season_type == 3)

        venue = comp.get("venue", {}).get("fullName", "")

        # Normalize abbreviations to match config.py
        h_abbr = ESPN_ABBR_MAP.get(home_team.get("abbreviation", ""), home_team.get("abbreviation", ""))
        a_abbr = ESPN_ABBR_MAP.get(away_team.get("abbreviation", ""), away_team.get("abbreviation", ""))

        return RawEvent(
            game_id=str(ev.get("id", "")),
            sport="NBA",
            home_abbr=h_abbr,
            away_abbr=a_abbr,
            home_name=home_team.get("displayName", home_team.get("name", "")),
            away_name=away_team.get("displayName", away_team.get("name", "")),
            game_time_utc=game_time,
            game_date=game_date,
            venue=venue,
            is_postseason=is_postseason,
        )
    except Exception as e:
        print(f"  [NBA] warn: could not normalize event {ev.get('id')}: {e}", file=sys.stderr)
        return None


def _fetch_standings() -> dict[str, TeamContext]:
    """Returns contexts keyed by "NBA:{abbr}" using normalized abbreviations."""
    data     = _get(f"{ESPN_API_V2}/standings")
    contexts: dict[str, TeamContext] = {}

    for conf_group in data.get("children", []):
        conf_name_raw = conf_group.get("name", "")
        conference    = "East" if "Eastern" in conf_name_raw else "West"

        entries = conf_group.get("standings", {}).get("entries", [])
        for entry in entries:
            team_info = entry.get("team", {})
            raw_abbr  = team_info.get("abbreviation", "")
            if not raw_abbr:
                continue

            # Normalize ESPN abbreviation to match config.py keys
            abbr = ESPN_ABBR_MAP.get(raw_abbr, raw_abbr)

            stats = {s["name"]: s for s in entry.get("stats", [])}

            wins    = int(_stat_val(stats, "wins",   0))
            losses  = int(_stat_val(stats, "losses", 0))
            gp      = wins + losses
            win_pct = wins / gp if gp > 0 else 0.0

            # Use playoffSeed as conference rank (available end of season / playoffs)
            seed = _stat_val(stats, "playoffSeed", None)
            try:
                conf_rank = int(seed) if seed is not None else None
            except (ValueError, TypeError):
                conf_rank = None

            # Streak — displayValue is "W3" or "L2"
            streak_dv             = _stat_display(stats, "streak", "")
            streak_type, streak_n = _parse_streak(streak_dv)

            # L10 — ESPN stat name is "Last Ten Games"
            l10_wins, l10_losses = _extract_l10(stats)

            ctx = TeamContext(
                abbr=abbr,
                name=team_info.get("displayName", team_info.get("name", abbr)),
                sport="NBA",
                wins=wins,
                losses=losses,
                win_pct=win_pct,
                l10_wins=l10_wins,
                l10_losses=l10_losses,
                streak_type=streak_type,
                streak_n=streak_n,
                games_played=gp,
                conference=conference,
                conference_rank=conf_rank,
            )
            contexts[f"NBA:{abbr}"] = ctx

    return contexts


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _stat_val(stats: dict, name: str, default):
    s = stats.get(name)
    if s is None:
        return default
    v = s.get("value")
    return v if v is not None else default


def _stat_display(stats: dict, name: str, default: str) -> str:
    s = stats.get(name)
    if s is None:
        return default
    dv = s.get("displayValue")
    return str(dv) if dv is not None else default


def _parse_streak(val: str) -> tuple[str, int]:
    if not val:
        return "W", 0
    val = val.strip()
    # Format "W3" or "L2"
    if val and val[0] in ("W", "L"):
        try:
            return val[0], int(val[1:])
        except ValueError:
            pass
    # Numeric: positive = wins, negative = losses (some ESPN formats)
    try:
        n = int(val)
        return ("W" if n >= 0 else "L"), abs(n)
    except ValueError:
        pass
    return "W", 0


def _extract_l10(stats: dict) -> tuple[int, int]:
    """Try to extract last-10 record from ESPN stats; fall back to neutral."""
    for key in ("Last Ten Games", "Last 10", "last10", "l10", "lastTen", "Last Ten"):
        s = stats.get(key)
        if s:
            dv = s.get("displayValue", "")
            if "-" in str(dv):
                try:
                    w, l = str(dv).split("-")[:2]
                    return int(w), int(l)
                except (ValueError, TypeError):
                    pass
    # Not available — return neutral (won't distort momentum)
    return 5, 5
