#!/usr/bin/env python3
"""
Fetch MLB schedule for the current month and write <team>/schedule.json.

Usage:
    python build_schedule.py --team padres
    python build_schedule.py --team yankees
    python build_schedule.py --team giants
"""

import argparse
import calendar
import json
import os
from datetime import datetime, timedelta, timezone

import requests

from engine.team_config import TEAM_CONFIGS, get_team_config

TEAM_ABBRS = {
    108: "LAA", 109: "ARI", 110: "BAL", 111: "BOS", 112: "CHC",
    113: "CIN", 114: "CLE", 115: "COL", 116: "DET", 117: "HOU",
    118: "KC",  119: "LAD", 120: "WSH", 121: "NYM", 133: "OAK",
    134: "PIT", 135: "SD",  136: "SEA", 137: "SF",  138: "STL",
    139: "TB",  140: "TEX", 141: "TOR", 142: "MIN", 143: "PHI",
    144: "ATL", 145: "CWS", 146: "MIA", 147: "NYY", 158: "MIL",
}


def mlb_fetch(path, params):
    url = f"https://statsapi.mlb.com/api/v1/{path}?{params}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()


def parse_game_time(game_date_utc, tz_offset, tz_name):
    try:
        dt = datetime.fromisoformat(game_date_utc.replace("Z", "+00:00"))
        if dt.hour == 0 and dt.minute == 0:
            return "TBD"
        local = dt + timedelta(hours=tz_offset)
        h = local.hour % 12 or 12
        ap = "AM" if local.hour < 12 else "PM"
        return f"{h}:{local.minute:02d} {ap} {tz_name}"
    except Exception:
        return "TBD"


def load_archive_map(archive_dir):
    """Returns {game_date: archive.html?date=brief_date} by reading archive index."""
    index_path = os.path.join(archive_dir, "index.json")
    if not os.path.exists(index_path):
        return {}
    with open(index_path) as f:
        index = json.load(f)
    mapping = {}
    for entry in index:
        archive_file = os.path.join(archive_dir, os.path.basename(entry["url"]))
        if not os.path.exists(archive_file):
            continue
        try:
            with open(archive_file) as f:
                brief = json.load(f)
            game_date = brief.get("last_game", {}).get("date")
            if game_date:
                mapping[game_date] = f"archive.html?date={entry['date']}"
        except Exception:
            pass
    return mapping


def build_entry(date_str, game, team_id, tz_name, tz_offset, archive_map):
    game_pk = game["gamePk"]
    teams = game.get("teams", {})
    home = teams.get("home", {})
    away = teams.get("away", {})

    is_home = home.get("team", {}).get("id") == team_id
    my_side = home if is_home else away
    opp_side = away if is_home else home
    opp_id = opp_side.get("team", {}).get("id", 0)
    opp_abbr = TEAM_ABBRS.get(opp_id, "???")

    abstract = game.get("status", {}).get("abstractGameState", "")

    entry = {
        "date": date_str,
        "opponent": opp_abbr,
        "home": is_home,
        "gamePk": game_pk,
    }

    if abstract == "Final":
        team_score = my_side.get("score", 0)
        opp_score = opp_side.get("score", 0)
        result = "W" if my_side.get("isWinner") else "L"
        entry["status"] = "final"
        entry["result"] = result
        entry["score"] = f"{team_score}–{opp_score}"
        archive_url = archive_map.get(date_str)
        if archive_url:
            entry["archive_url"] = archive_url
    elif abstract == "Live":
        entry["status"] = "live"
        entry["time_local"] = "Live"
    else:
        entry["status"] = "scheduled"
        entry["time_local"] = parse_game_time(game.get("gameDate", ""), tz_offset, tz_name)
        home_prob = home.get("probablePitcher")
        away_prob = away.get("probablePitcher")
        my_prob = home_prob if is_home else away_prob
        opp_prob = away_prob if is_home else home_prob
        probable = {}
        if my_prob:
            probable["team"] = my_prob.get("lastName") or my_prob.get("fullName", "TBD")
        if opp_prob:
            probable["opp"] = opp_prob.get("lastName") or opp_prob.get("fullName", "TBD")
        if probable:
            entry["probable"] = probable

    return entry


def compute_summary(games, brief_path):
    wins = sum(1 for g in games if g.get("status") == "final" and g.get("result") == "W")
    losses = sum(1 for g in games if g.get("status") == "final" and g.get("result") == "L")
    streak = ""
    last_10 = ""
    if os.path.exists(brief_path):
        with open(brief_path) as f:
            brief = json.load(f)
        team = brief.get("team", {})
        streak = team.get("streak", "")
        last_10 = team.get("last10", "").replace("-", "–")
    return {
        "month_record": f"{wins}–{losses}",
        "current_streak": streak,
        "last_10": last_10,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--team", required=True, choices=list(TEAM_CONFIGS))
    args = parser.parse_args()

    cfg = get_team_config(args.team)
    now = datetime.now(timezone.utc)
    year, month = now.year, now.month
    last_day = calendar.monthrange(year, month)[1]
    start = f"{year}-{month:02d}-01"
    end = f"{year}-{month:02d}-{last_day}"

    print(f"Fetching {cfg.team_name} schedule {start} to {end}...")
    params = (
        f"sportId=1&teamId={cfg.team_id}"
        f"&startDate={start}&endDate={end}"
        f"&hydrate=probablePitcher,decisions,linescore,teams"
    )
    data = mlb_fetch("schedule", params)

    root = os.path.dirname(os.path.abspath(__file__))
    team_dir = os.path.join(root, args.team)
    archive_dir = os.path.join(team_dir, "archive")
    brief_path = os.path.join(team_dir, "brief.json")
    archive_map = load_archive_map(archive_dir)

    games = []
    for date_entry in data.get("dates", []):
        date_str = date_entry["date"]
        for game in date_entry.get("games", []):
            games.append(build_entry(date_str, game, cfg.team_id, cfg.tz_label, cfg.tz_offset, archive_map))

    games.sort(key=lambda g: (g["date"], g.get("gamePk", 0)))

    output = {
        "team": cfg.team_name,
        "team_slug": args.team,
        "month": f"{year}-{month:02d}",
        "division_name": cfg.division_name,
        "generated_at": now.isoformat(),
        "games": games,
        "summary": compute_summary(games, brief_path),
    }

    out_path = os.path.join(team_dir, "schedule.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Wrote {out_path} ({len(games)} games)")


if __name__ == "__main__":
    main()
