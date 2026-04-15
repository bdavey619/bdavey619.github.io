"""
mlb.py — MLB data fetcher for Must Watch This Week.

Fetches schedule + standings from statsapi.mlb.com/api/v1.
Returns (list[RawEvent], dict[str, TeamContext]) keyed by "MLB:{abbr}".
"""

import sys
from datetime import datetime, date, timedelta, timezone
from urllib.parse import urlencode

import requests

from models import RawEvent, TeamContext

MLB_API = "https://statsapi.mlb.com/api/v1"
TIMEOUT = 15
SEASON  = 2026


def _get(path: str, **params) -> dict:
    url = f"{MLB_API}/{path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def fetch_week(week_start: date, week_end: date) -> tuple[list[RawEvent], dict[str, TeamContext]]:
    """
    Fetch all MLB games in [week_start, week_end] plus league-wide standings.
    Returns (events, contexts) where contexts is keyed by "MLB:{abbr}".
    """
    print("  [MLB] fetching schedule...", file=sys.stderr)
    raw_games = _fetch_schedule(week_start, week_end)
    print(f"  [MLB] {len(raw_games)} raw games found", file=sys.stderr)

    print("  [MLB] fetching standings...", file=sys.stderr)
    contexts = _fetch_standings()
    print(f"  [MLB] standings loaded for {len(contexts)} teams", file=sys.stderr)

    events = []
    for g in raw_games:
        ev = _normalize_game(g)
        if ev:
            events.append(ev)

    print(f"  [MLB] {len(events)} events normalized", file=sys.stderr)
    return events, contexts


def _fetch_schedule(start: date, end: date) -> list[dict]:
    data = _get(
        "schedule",
        sportId=1,
        startDate=start.strftime("%Y-%m-%d"),
        endDate=end.strftime("%Y-%m-%d"),
        hydrate="team,venue",
    )
    games = []
    for day in data.get("dates", []):
        games.extend(day.get("games", []))
    return games


def _normalize_game(g: dict) -> RawEvent | None:
    try:
        home_team = g["teams"]["home"]["team"]
        away_team = g["teams"]["away"]["team"]

        game_time = datetime.fromisoformat(g["gameDate"].replace("Z", "+00:00"))
        # Use ET for local date (UTC-4 during DST in April)
        et = timezone(timedelta(hours=-4))
        local_dt  = game_time.astimezone(et)
        game_date = local_dt.date()

        # Detect postseason by game type
        game_type    = g.get("gameType", "R")
        is_postseason = game_type in ("P", "D", "L", "W", "F", "C")

        return RawEvent(
            game_id=str(g["gamePk"]),
            sport="MLB",
            home_abbr=home_team.get("abbreviation", home_team["name"]),
            away_abbr=away_team.get("abbreviation", away_team["name"]),
            home_name=home_team.get("teamName", home_team["name"]),
            away_name=away_team.get("teamName", away_team["name"]),
            game_time_utc=game_time,
            game_date=game_date,
            venue=g.get("venue", {}).get("name", ""),
            is_postseason=is_postseason,
        )
    except Exception as e:
        print(f"  [MLB] warn: could not normalize game {g.get('gamePk')}: {e}", file=sys.stderr)
        return None


def _fetch_standings() -> dict[str, TeamContext]:
    """Returns contexts keyed by "MLB:{abbr}"."""
    data = _get(
        "standings",
        leagueId="103,104",
        season=SEASON,
        standingsTypes="regularSeason",
        hydrate="team,league,division",
    )

    contexts: dict[str, TeamContext] = {}

    for record in data.get("records", []):
        for tr in record.get("teamRecords", []):
            team = tr["team"]
            abbr = team.get("abbreviation", team["name"])

            wins    = tr.get("wins", 0)
            losses  = tr.get("losses", 0)
            gp      = wins + losses
            win_pct = wins / gp if gp > 0 else 0.0

            # L10
            l10 = next(
                (r for r in tr.get("records", {}).get("splitRecords", [])
                 if r["type"] == "lastTen"),
                None,
            )
            l10_wins   = l10["wins"]   if l10 else 0
            l10_losses = l10["losses"] if l10 else 0

            # Streak — code like "W3" or "L2"
            streak_code = tr.get("streak", {}).get("streakCode", "W0")
            streak_type = streak_code[0] if streak_code else "W"
            try:
                streak_n = int(streak_code[1:])
            except (ValueError, IndexError):
                streak_n = 0

            # Division games back (None = first place)
            gb_raw = tr.get("gamesBack", "-")
            try:
                games_back = float(gb_raw)
            except (ValueError, TypeError):
                games_back = None

            # Wild card games back
            wc_gb_raw = tr.get("wildCardGamesBack", "-")
            try:
                wc_games_back = float(wc_gb_raw)
            except (ValueError, TypeError):
                wc_games_back = None

            div_rank = None
            try:
                div_rank = int(tr.get("divisionRank", 0))
            except (ValueError, TypeError):
                pass

            wc_rank = None
            try:
                wc_rank = int(tr.get("wildCardRank", 0))
            except (ValueError, TypeError):
                pass

            ctx = TeamContext(
                abbr=abbr,
                name=team.get("teamName", team["name"]),
                sport="MLB",
                wins=wins,
                losses=losses,
                win_pct=win_pct,
                l10_wins=l10_wins,
                l10_losses=l10_losses,
                streak_type=streak_type,
                streak_n=streak_n,
                games_played=gp,
                division_rank=div_rank,
                games_back=games_back,
                wild_card_rank=wc_rank,
                wc_games_back=wc_games_back,
            )
            contexts[f"MLB:{abbr}"] = ctx

    return contexts
