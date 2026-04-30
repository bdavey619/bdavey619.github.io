"""
build_brief.py — Padres Morning Brief data fetcher

Pulls Padres data from the MLB Stats API and writes brief.json
matching the agreed schema. No API key required.
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, quote_plus

import requests

# ---------------------------------------------------------------------------
# Team config — the only section that differs between teams
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).parent.parent))
from engine.team_config import PADRES  # noqa: E402
from engine.narrative import (  # noqa: E402
    check_insight_language,
    classify_game_emotion,
    build_story_state,
    load_story_state,
    save_story_state,
    compute_story_delta,
    generate_narrative_copy,
    generate_postponed_narrative,
    build_story_threads,
    build_story_hook,
)
from engine.clutch import identify_clutch_player  # noqa: E402
from engine.story_signals import identify_game_driver  # noqa: E402

CFG = PADRES

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API = "https://statsapi.mlb.com/api/v1"
SEASON = datetime.now().year
TIMEOUT = 15


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def get(path, **params):
    url = f"{API}/{path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Schedule helpers
# ---------------------------------------------------------------------------

def _fetch_schedule(start, end):
    """Fetch Padres schedule between two dates (inclusive)."""
    data = get(
        "schedule",
        sportId=1,
        teamId=CFG.team_id,
        startDate=start.strftime("%Y-%m-%d"),
        endDate=end.strftime("%Y-%m-%d"),
        hydrate="linescore,decisions,probablePitcher,team,venue",
    )
    games = []
    for day in data.get("dates", []):
        games.extend(day.get("games", []))
    return games


def _is_postponed(game):
    """Return True if the game was postponed per any MLB status field."""
    s = game.get("status", {})
    return (
        s.get("detailedState") == "Postponed"
        or s.get("statusCode") == "P"
        or s.get("codedGameState") == "P"
    )


def _format_postponed_game(game):
    """Return a minimal last_game dict for a postponed game — no score, no box score."""
    home      = _is_home(game)
    opp       = _opponent_abbr(game)
    game_date = game.get("officialDate") or game["gameDate"][:10]
    venue     = game.get("venue", {}).get("name", "")
    reason    = game.get("status", {}).get("reason", "")
    print(
        f"  [postponed] {opp} on {game_date}"
        + (f" — {reason}" if reason else ""),
        file=sys.stderr,
    )
    return {
        "status":           "postponed",
        "gamePk":           game["gamePk"],
        "date":             game_date,
        "opponent":         opp,
        "home":             home,
        "venue":            venue,
        "postponed_reason": reason,
        "makeup_date":      None,
    }


def get_last_game():
    """
    Return the most recent relevant game: the newest Final or Postponed game
    in the last 14 days. A postponed game that is newer than the last Final
    is returned as status='postponed' so the brief can acknowledge it.
    """
    end   = datetime.now().date()
    start = end - timedelta(days=14)
    games = _fetch_schedule(start, end)

    games_sorted = sorted(games, key=lambda g: (g["gameDate"], g["gamePk"]), reverse=True)
    for g in games_sorted:
        s = g.get("status", {})
        # Postponed check BEFORE abstractGameState=="Final": the MLB API sometimes
        # returns abstractGameState="Final" for postponed games, making detailedState /
        # statusCode / codedGameState the only reliable signal.
        if _is_postponed(g):
            print(
                f"  [game_select] build_path=postponed"
                f"  detailedState={s.get('detailedState')!r}"
                f"  statusCode={s.get('statusCode')!r}"
                f"  codedGameState={s.get('codedGameState')!r}"
                f"  abstractGameState={s.get('abstractGameState')!r}",
                file=sys.stderr,
            )
            return _format_postponed_game(g)
        if s.get("abstractGameState") == "Final":
            print(
                f"  [game_select] build_path=final"
                f"  detailedState={s.get('detailedState')!r}"
                f"  statusCode={s.get('statusCode')!r}"
                f"  codedGameState={s.get('codedGameState')!r}",
                file=sys.stderr,
            )
            return _format_last_game(g)

    return {"status": "off_day"}


def get_next_game():
    """Next scheduled (not yet final) game. Returns (formatted_dict, raw_game) or (None, None)."""
    start = datetime.now().date()
    end = start + timedelta(days=14)
    games = _fetch_schedule(start, end)

    upcoming = [
        g for g in games
        if g.get("status", {}).get("abstractGameState") in ("Preview", "Live")
    ]
    if not upcoming:
        return None, None

    upcoming.sort(key=lambda g: g["gameDate"])
    g = upcoming[0]
    return _format_next_game(g), g


# ---------------------------------------------------------------------------
# Game formatting
# ---------------------------------------------------------------------------

def _is_home(game):
    return game["teams"]["home"]["team"]["id"] == CFG.team_id


def _opponent_abbr(game):
    side = "away" if _is_home(game) else "home"
    return game["teams"][side]["team"].get("abbreviation") \
        or game["teams"][side]["team"]["name"]


def _generate_game_note(sd_row, opp_row, score, opponent, key_hitters, result,
                        clutch=None, emotion="normal"):
    """
    One-sentence editorial game note derived from line score and clutch context.
    When emotion is high/extreme and a clutch player exists, leads with their moment.
    """
    def _int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    sd_ints = [_int(v) for v in sd_row]
    opp_ints = [_int(v) for v in opp_row]

    margin = score.get("team", 0) - score.get("opp", 0)

    # Best hitter — prefer the HR guy
    hitter_last = ""
    hitter_line = ""
    if key_hitters:
        best = next((h for h in key_hitters if "HR" in h.get("line", "")), key_hitters[0])
        parts = best.get("name", "").split()
        if len(parts) >= 2:
            hitter_last = parts[-1] if parts[-1] != "Jr." else " ".join(parts[-2:])
        else:
            hitter_last = best.get("name", "")
        hitter_line = best.get("line", "")

    # Clutch player context
    clutch_last        = ""
    clutch_event_lower = ""
    clutch_inning      = None
    clutch_reason      = ""
    if clutch and isinstance(clutch, dict) and clutch.get("confidence") == "high":
        name  = clutch.get("name", "")
        parts = name.split()
        clutch_last       = parts[-1] if (len(parts) >= 2 and parts[-1] != "Jr.") else name
        clutch_event_lower = (clutch.get("event") or "").lower()
        clutch_inning      = clutch.get("inning")
        clutch_reason      = (clutch.get("reason") or "").lower()

    # Biggest inning for each team: returns (inning_index, runs)
    def _biggest(ints):
        best = (-1, 0)
        for i, v in enumerate(ints):
            if v is not None and v > best[1]:
                best = (i, v)
        return best

    sd_big  = _biggest(sd_ints)
    opp_big = _biggest(opp_ints)

    if result == "W":
        # --- Clutch-aware note for high/extreme emotion games ---
        if emotion in ("high", "extreme") and clutch_last:
            ci_word = _ordinal_word(clutch_inning or 9)
            is_walkoff  = "walk-off" in clutch_reason
            is_go_ahead = "go-ahead" in clutch_reason
            is_rally    = "rally" in clutch_reason
            is_tying    = "tying" in clutch_reason

            if is_walkoff:
                return (f"{clutch_last} walked it off in the {ci_word}"
                        f". {CFG.team_city} needed all nine.")

            if is_go_ahead and sd_big[1] >= 3:
                big_inn = _ordinal_word(sd_big[0] + 1)
                inning_clause = "" if big_inn == ci_word else f" in the {ci_word}"
                return (f"A {sd_big[1]}-run {big_inn} flipped the game"
                        f". {clutch_last}'s go-ahead {clutch_event_lower}"
                        f"{inning_clause} was the turn that mattered.")

            if is_go_ahead:
                return (f"{clutch_last} hit the go-ahead {clutch_event_lower}"
                        f" in the {ci_word}"
                        f" to give {CFG.team_city} a lead they didn't surrender.")

            if is_rally and sd_big[1] >= 3:
                big_inn = _ordinal_word(sd_big[0] + 1)
                return (f"{clutch_last} triggered the {big_inn}-inning rally"
                        f" that {CFG.team_city} needed to close the game.")

            if is_tying:
                return (f"{clutch_last} tied it in the {ci_word}"
                        f". {CFG.team_city} finished the comeback from there.")

        # Large SD inning (4+ runs)
        if sd_big[1] >= 4:
            inn = _ordinal_word(sd_big[0] + 1)
            if hitter_last and "HR" in hitter_line:
                return (f"A {sd_big[1]}-run {inn}. {hitter_last}'s home run "
                        f"gave {CFG.team_city} the cushion it needed.")
            return f"A {sd_big[1]}-run {inn} inning gave {CFG.team_city} the separation it needed."

        # 3-run inning
        if sd_big[1] == 3:
            inn = _ordinal_word(sd_big[0] + 1)
            if hitter_last and "HR" in hitter_line:
                return (f"{hitter_last}'s home run was part of a 3-run {inn} "
                        f"that put the {CFG.team_name} in front for good.")
            return f"A 3-run {inn} put {CFG.team_city} in control and they never looked back."

        # Comfortable win driven by a standout hitter
        if margin >= 4 and hitter_last:
            if "HR" in hitter_line:
                return f"{hitter_last}'s home run powered a comfortable {CFG.team_name} win."
            m = re.search(r"(\d+) RBI", hitter_line)
            if m and int(m.group(1)) >= 3:
                return f"{hitter_last} drove in {m.group(1)} runs to fuel the {CFG.team_name} offense."

        # Late-inning pull-away
        if len(sd_ints) >= 8:
            late_sd = sum(v for v in sd_ints[6:] if v is not None)
            late_opp = sum(v for v in opp_ints[6:] if v is not None)
            if late_sd >= 3 and late_sd >= late_opp + 2:
                return (f"The {CFG.team_name} answered in the late innings, outscoring "
                        f"{opponent} {late_sd}–{late_opp} in the final frames.")

        # Generic W with a hitter hook
        if hitter_last:
            return f"{hitter_last}'s bat helped the {CFG.team_name} hold off {opponent}."
        return f"{CFG.team_city} controlled the game and handled {opponent} without drama."

    else:  # Loss
        # Opponent had a big inning
        if opp_big[1] >= 4:
            inn = _ordinal_word(opp_big[0] + 1)
            return f"{opponent}'s {opp_big[1]}-run {inn} proved to be the difference."
        if opp_big[1] == 3:
            inn = _ordinal_word(opp_big[0] + 1)
            return f"A 3-run {inn} by {opponent} was more than the {CFG.team_name} could answer."

        # One-run loss
        if abs(margin) == 1:
            return f"{CFG.team_city} couldn't manufacture the run they needed in a tight one."

        return f"The {CFG.team_name} couldn't find enough offense to keep pace with {opponent}."


def _highlights_url(home: bool, opponent: str, game_date: str) -> str:
    """Return a YouTube search URL for the game highlight video.

    Uses away vs home team convention and the full game date so the
    official MLB YouTube clip typically surfaces as the first result.
    No API key required.
    """
    try:
        dt = datetime.strptime(game_date, "%Y-%m-%d")
        date_label = dt.strftime("%B %-d %Y")
    except Exception:
        date_label = game_date
    away_abbr = opponent if home else CFG.team_abbr
    home_abbr = CFG.team_abbr if home else opponent
    query = f"{away_abbr} vs {home_abbr} highlights {date_label} MLB"
    return f"https://www.youtube.com/results?search_query={quote_plus(query)}"


def _format_last_game(game):
    home = _is_home(game)
    sd_side = "home" if home else "away"
    opp_side = "away" if home else "home"

    # Prefer linescore totals (authoritative) over schedule's score field
    ls = game.get("linescore", {})
    ls_teams = ls.get("teams", {})
    sd_runs = ls_teams.get(sd_side, {}).get("runs", game["teams"][sd_side].get("score", 0))
    opp_runs = ls_teams.get(opp_side, {}).get("runs", game["teams"][opp_side].get("score", 0))
    result = "W" if sd_runs > opp_runs else "L"

    linescore = _format_linescore(ls, home)

    # Context line: venue, home/away, day/night
    venue_name = game.get("venue", {}).get("name", "")
    day_night = game.get("dayNight", "")
    context_parts = ["Home" if home else "Away"]
    if venue_name:
        context_parts.append(venue_name)
    if day_night:
        context_parts.append(f"{day_night.capitalize()} game")
    context_line = " · ".join(context_parts)

    # Boxscore: authoritative source for both decisions team affiliation and starter
    key_hitters, key_pitcher, decisions, full_box = [], None, {}, None
    try:
        box = get(f"game/{game['gamePk']}/boxscore")
        key_hitters, key_pitcher = _extract_key_performers(box, sd_side)
        decisions = _format_decisions(game.get("decisions", {}), box, sd_side)
        full_box = _extract_full_box_score(box, sd_side)
    except Exception as e:
        print(f"  warn: boxscore fetch failed for {game['gamePk']}: {e}", file=sys.stderr)
        decisions = _format_decisions(game.get("decisions", {}), None, sd_side)

    score = {"team": sd_runs, "opp": opp_runs}
    game_note = _generate_game_note(
        linescore[0], linescore[1], score, _opponent_abbr(game), key_hitters, result
    )

    game_date = game.get("officialDate") or game["gameDate"][:10]
    out = {
        "status": "final",
        "gamePk": game["gamePk"],
        "date": game_date,
        "opponent": _opponent_abbr(game),
        "home": home,
        "result": result,
        "score": score,
        "linescore": linescore,
        "decisions": decisions,
        "key_hitters": key_hitters,
        "key_pitcher": key_pitcher,
        "context_line": context_line,
        "highlights_url": _highlights_url(home, _opponent_abbr(game), game_date),
    }
    if game_note:
        out["game_note"] = game_note
    if full_box:
        out["full_box"] = full_box
    return out


def _format_linescore(ls, sd_is_home):
    """Return [[sd_innings...], [opp_innings...]]. Padres always row 0."""
    innings = ls.get("innings", [])
    sd_row, opp_row = [], []
    for inn in innings:
        h = inn.get("home", {}).get("runs", "")
        a = inn.get("away", {}).get("runs", "")
        if sd_is_home:
            sd_row.append(h); opp_row.append(a)
        else:
            sd_row.append(a); opp_row.append(h)
    return [sd_row, opp_row]


def _format_decisions(dec, box, sd_side):
    """
    Map win/loss/save to the correct labels.
    Cross-checks each named pitcher against the boxscore to determine team.
    Always emits the labels relative to the actual game outcome.
    """
    out = {}
    if not dec:
        return out

    # Build name -> side and name -> role lookups from the boxscore
    name_to_side = {}
    name_to_role = {}
    if box:
        opp_side = "away" if sd_side == "home" else "home"
        for side in (sd_side, opp_side):
            team = box.get("teams", {}).get(side, {})
            starter_id = (team.get("pitchers") or [None])[0]
            for key, p in team.get("players", {}).items():
                name = p.get("person", {}).get("fullName")
                if not name:
                    continue
                name_to_side[name] = side
                pid = p.get("person", {}).get("id")
                name_to_role[name] = "SP" if pid and pid == starter_id else "RP"

    for api_key, label in (("winner", "win"), ("loser", "loss"), ("save", "save")):
        person = dec.get(api_key)
        if not person:
            continue
        name = person.get("fullName")
        out[label] = name
        role = name_to_role.get(name)
        if role:
            out[f"{label}_role"] = role
        # Annotate with team side when we can verify
        side = name_to_side.get(name)
        if side and side != sd_side:
            out[f"{label}_team"] = "opp"
        elif side == sd_side:
            out[f"{label}_team"] = "team"
    return out


def _extract_key_performers(box, sd_side):
    """
    Top 2 hitters by hits/HR.
    Key pitcher = the actual Padres starter (boxscore.pitchers[0]),
    falling back to most-IP if the pitchers array is missing.
    """
    sd_team = box["teams"][sd_side]
    players = sd_team.get("players", {})

    # ---- Hitters ----
    hitters = []
    for p in players.values():
        bat = p.get("stats", {}).get("batting", {})
        if not bat or bat.get("atBats", 0) == 0:
            continue
        name = p.get("person", {}).get("fullName", "")
        hits = bat.get("hits", 0)
        ab = bat.get("atBats", 0)
        hr = bat.get("homeRuns", 0)
        rbi = bat.get("rbi", 0)
        line = f"{hits}-{ab}"
        if hr: line += f", {hr} HR"
        if rbi: line += f", {rbi} RBI"
        pos = p.get("position", {}).get("abbreviation", "")
        season_avg = p.get("seasonStats", {}).get("batting", {}).get("avg", "")
        hitters.append({
            "name": name, "_hits": hits, "_hr": hr, "_rbi": rbi,
            "line": line, "pos": pos, "season_avg": season_avg,
        })
    hitters.sort(key=lambda h: (h["_hits"], h["_hr"], h["_rbi"]), reverse=True)
    top_hitters = []
    for h in hitters[:2]:
        entry = {"name": h["name"], "line": h["line"]}
        if h.get("pos"):
            entry["pos"] = h["pos"]
        if h.get("season_avg"):
            entry["season_avg"] = h["season_avg"]
        top_hitters.append(entry)

    # ---- Key pitcher: actual starter from ordered pitchers array ----
    pitcher_ids = sd_team.get("pitchers", [])  # ordered, [0] is the starter
    key_pitcher = None

    def _format_pitcher(pid, role="SP"):
        key = f"ID{pid}"
        p = players.get(key)
        if not p:
            return None
        pit = p.get("stats", {}).get("pitching", {})
        if not pit:
            return None
        name = p.get("person", {}).get("fullName", "")
        ip = pit.get("inningsPitched", "0")
        er = pit.get("earnedRuns", 0)
        k = pit.get("strikeOuts", 0)
        h = pit.get("hits", 0)
        season_era = p.get("seasonStats", {}).get("pitching", {}).get("era", "")
        entry = {"name": name, "line": f"{ip} IP, {h} H, {er} ER, {k} K", "role": role}
        if season_era:
            entry["season_era"] = season_era
        return entry

    if pitcher_ids:
        key_pitcher = _format_pitcher(pitcher_ids[0], role="SP")

    # Fallback: most IP among Padres pitchers if starter lookup failed
    if not key_pitcher:
        best = None
        for p in players.values():
            pit = p.get("stats", {}).get("pitching", {})
            if not pit or not pit.get("inningsPitched"):
                continue
            try:
                ip_val = float(pit.get("inningsPitched", 0))
            except (TypeError, ValueError):
                continue
            if best is None or ip_val > best["_ip"]:
                season_era = p.get("seasonStats", {}).get("pitching", {}).get("era", "")
                best = {
                    "_ip": ip_val,
                    "name": p.get("person", {}).get("fullName", ""),
                    "line": f"{pit.get('inningsPitched')} IP, "
                            f"{pit.get('hits', 0)} H, "
                            f"{pit.get('earnedRuns', 0)} ER, "
                            f"{pit.get('strikeOuts', 0)} K",
                    "role": "SP",
                    "season_era": season_era,
                }
        if best:
            entry = {"name": best["name"], "line": best["line"], "role": best["role"]}
            if best.get("season_era"):
                entry["season_era"] = best["season_era"]
            key_pitcher = entry

    return top_hitters, key_pitcher


def _extract_full_box_score(box, sd_side):
    """
    Full batting + pitching table for the Padres in this game.
    Returns None if no data is usable.
    """
    sd_team = box["teams"][sd_side]
    players = sd_team.get("players", {})
    pitcher_ids = sd_team.get("pitchers", [])

    def _plate_appearances(bat):
        """Any official plate appearance: AB + BB + HBP + SF + SH."""
        return (bat.get("atBats", 0) + bat.get("baseOnBalls", 0)
                + bat.get("hitByPitch", 0) + bat.get("sacFlies", 0)
                + bat.get("sacBunts", 0))

    def _batter_row(p, bat):
        pos = p.get("position", {}).get("abbreviation", "")
        avg = p.get("seasonStats", {}).get("batting", {}).get("avg", "")
        return {
            "name": p.get("person", {}).get("fullName", ""),
            "pos":  pos,
            "avg":  avg,
            "ab":  bat.get("atBats", 0),
            "r":   bat.get("runs", 0),
            "h":   bat.get("hits", 0),
            "rbi": bat.get("rbi", 0),
            "bb":  bat.get("baseOnBalls", 0),
            "so":  bat.get("strikeOuts", 0),
        }

    # Batting — collect all batters with PAs, then sort by per-player battingOrder.
    # Each player object carries a battingOrder field (e.g. "100" = starter in slot 1,
    # "401" = first sub in slot 4).  Starters end in "00"; subs increment the last two
    # digits.  Sorting numerically therefore preserves the actual lineup slot AND
    # puts subs immediately after the starter they replaced — not appended at the end.
    batting_rows = []
    for key, p in players.items():
        if not key.startswith("ID"):
            continue
        bat = p.get("stats", {}).get("batting", {})
        if not bat or _plate_appearances(bat) == 0:
            continue
        try:
            order_val = int(p.get("battingOrder") or 99999)
        except (TypeError, ValueError):
            order_val = 99999
        batting_rows.append((order_val, _batter_row(p, bat)))

    batting_rows.sort(key=lambda t: t[0])
    batting = [row for _, row in batting_rows]

    # Pitching — follow pitching order
    pitching = []
    for pid in pitcher_ids:
        p = players.get(f"ID{pid}")
        if not p:
            continue
        pit = p.get("stats", {}).get("pitching", {})
        if not pit or not pit.get("inningsPitched"):
            continue
        pitching.append({
            "name": p.get("person", {}).get("fullName", ""),
            "ip":  pit.get("inningsPitched", "0"),
            "h":   pit.get("hits", 0),
            "er":  pit.get("earnedRuns", 0),
            "k":   pit.get("strikeOuts", 0),
            "bb":  pit.get("baseOnBalls", 0),
        })

    if not batting and not pitching:
        return None
    return {"batting": batting, "pitching": pitching}


def _format_next_game(game):
    home = _is_home(game)
    gd = datetime.fromisoformat(game["gameDate"].replace("Z", "+00:00"))
    pt = gd.astimezone(timezone(timedelta(hours=CFG.tz_offset)))

    sd_side = "home" if home else "away"
    opp_side = "away" if home else "home"

    probable = {}
    sd_pp = game["teams"][sd_side].get("probablePitcher", {})
    opp_pp = game["teams"][opp_side].get("probablePitcher", {})
    if sd_pp: probable["team"] = sd_pp.get("fullName", "TBD")
    if opp_pp: probable["opp"] = opp_pp.get("fullName", "TBD")

    return {
        "gamePk": game["gamePk"],
        "date": game.get("officialDate") or game["gameDate"][:10],
        "opponent": _opponent_abbr(game),
        "home": home,
        "time_local": pt.strftime(f"%-I:%M %p {CFG.tz_label}"),
        "probable": probable,
    }


# ---------------------------------------------------------------------------
# Standings
# ---------------------------------------------------------------------------

def get_standings():
    data = get("standings", leagueId=CFG.league_id, season=SEASON, standingsTypes="regularSeason")
    rows = []
    for record in data.get("records", []):
        if record.get("division", {}).get("id") != CFG.division_id:
            continue
        for tr in record.get("teamRecords", []):
            last10 = next(
                (r for r in tr.get("records", {}).get("splitRecords", []) if r["type"] == "lastTen"),
                None,
            )
            rows.append({
                "team": tr["team"]["abbreviation"] if "abbreviation" in tr["team"] else tr["team"]["name"],
                "w": tr.get("wins", 0),
                "l": tr.get("losses", 0),
                "gb": tr.get("gamesBack", "-"),
                "last10": f"{last10['wins']}-{last10['losses']}" if last10 else "-",
            })
    return rows


# ---------------------------------------------------------------------------
# Team summary + snapshot
# ---------------------------------------------------------------------------

def get_team_summary_and_snapshot():
    """Pulls record / streak / run diff / last10 + season AVG, OPS, ERA."""
    standings = get("standings", leagueId=CFG.league_id, season=SEASON)
    sd_record = None
    for record in standings.get("records", []):
        for tr in record.get("teamRecords", []):
            if tr["team"]["id"] == CFG.team_id:
                sd_record = tr
                break

    summary = {}
    if sd_record:
        wins = sd_record.get("wins", 0)
        losses = sd_record.get("losses", 0)
        rs = sd_record.get("runsScored", 0)
        ra = sd_record.get("runsAllowed", 0)
        diff = rs - ra
        last10 = next(
            (r for r in sd_record.get("records", {}).get("splitRecords", []) if r["type"] == "lastTen"),
            None,
        )
        summary = {
            "record": f"{wins}-{losses}",
            "streak": sd_record.get("streak", {}).get("streakCode", "-"),
            "run_diff": f"{diff:+d}",
            "last10": f"{last10['wins']}-{last10['losses']}" if last10 else "-",
            "division_rank": int(sd_record.get("divisionRank", 0)) if sd_record.get("divisionRank") else None,
            "games_back": sd_record.get("gamesBack", "-"),
        }

    # Team stats — hitting + pitching
    stats = get(f"teams/{CFG.team_id}/stats", stats="season", group="hitting,pitching", season=SEASON)
    avg = ops = era = "-"
    for s in stats.get("stats", []):
        group = s.get("group", {}).get("displayName")
        splits = s.get("splits", [])
        if not splits:
            continue
        st = splits[0].get("stat", {})
        if group == "hitting":
            avg = st.get("avg", "-")
            ops = st.get("ops", "-")
        elif group == "pitching":
            era = st.get("era", "-")

    summary["avg"] = avg
    summary["ops"] = ops
    summary["era"] = era
    return summary


# ---------------------------------------------------------------------------
# Editorial helpers
# ---------------------------------------------------------------------------

def _ordinal_word(n):
    words = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
             6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth"}
    return words.get(n, f"{n}th")


def _cardinal_word(n):
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
             6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}
    return words.get(n, str(n))


def _parse_pitcher_line(line):
    """Return (ip_float, er_int) or (None, None) if unparseable."""
    try:
        ip = float(line.split(" IP")[0])
        er_match = re.search(r'(\d+) ER', line)
        er = int(er_match.group(1)) if er_match else 99
        return ip, er
    except (ValueError, IndexError, AttributeError):
        return None, None


# ---------------------------------------------------------------------------
# Subhead generation (runs server-side so it has full context)
# ---------------------------------------------------------------------------

def build_subhead(last_game, team):
    """Return a concise editorial deck line — one tight sentence."""
    status = last_game.get("status") if last_game else None
    if status not in ("final", "postponed"):
        return ""
    if status == "postponed":
        ha     = "vs" if last_game.get("home") else "@"
        opp    = last_game.get("opponent", "")
        reason = last_game.get("postponed_reason", "")
        suffix = f" — {reason.lower()}" if reason else ""
        return f"POSTPONED {ha} {opp}{suffix}"

    result = last_game.get("result")
    streak = team.get("streak", "")
    score = last_game.get("score", {})
    opponent = last_game.get("opponent", "")
    decisions = last_game.get("decisions", {})
    key_hitters = last_game.get("key_hitters", [])
    key_pitcher = last_game.get("key_pitcher", {})
    games_back = team.get("games_back", "-")
    last10 = team.get("last10", "-")
    home = last_game.get("home", True)

    # Parse streak
    streak_num, streak_type = 0, ""
    m = re.match(r'^([WL])(\d+)$', streak)
    if m:
        streak_type, streak_num = m.group(1), int(m.group(2))

    # Parse last10
    last10_wins = 0
    if last10 and "-" in last10:
        try:
            last10_wins = int(last10.split("-")[0])
        except ValueError:
            pass

    # Standings tail (only append if meaningfully close)
    gb_tail = ""
    try:
        gb_val = float(str(games_back))
        if gb_val <= 3.0:
            gb_tail = f" | {games_back} back in the {CFG.division_short}"
        elif gb_val <= 5.5:
            gb_tail = f", staying in the {CFG.division_name} hunt"
    except (ValueError, TypeError):
        pass  # games_back == "-" means first place; no tail needed

    # Best offensive performer — prefer the HR/RBI guy
    top_hitter_last = ""
    if key_hitters:
        best = key_hitters[0]
        for h in key_hitters:
            if "HR" in h.get("line", ""):
                best = h
                break
        name_parts = best.get("name", "").split()
        # Use last name, but keep "Jr." attached to avoid awkward truncation
        if len(name_parts) >= 2:
            top_hitter_last = name_parts[-1] if name_parts[-1] != "Jr." else " ".join(name_parts[-2:])
        else:
            top_hitter_last = best.get("name", "")

    # Starting pitcher worth headlining? Require quality start: 6+ IP, ≤3 ER
    pitcher_last = ""
    if key_pitcher and decisions.get("win_team") == "team":
        ip, er = _parse_pitcher_line(key_pitcher.get("line", ""))
        if ip is not None and ip >= 6.0 and er <= 3:
            pitcher_last = key_pitcher["name"].split()[-1]

    # Build the lead clause
    if result == "W":
        if streak_type == "W" and streak_num >= 3:
            n = _ordinal_word(streak_num)
            lead = f"{CFG.team_name} win their {n} straight"
        elif last10_wins >= 7:
            lead = f"{CFG.team_city} stays hot. {last10} in the last ten"
        elif home:
            lead = f"{CFG.team_name} take it at {CFG.home_venue_short}"
        else:
            lead = f"{CFG.team_name} win on the road vs. {opponent}"

        # Attach standout performer(s)
        if pitcher_last and top_hitter_last:
            lead += f" behind {pitcher_last} and {top_hitter_last}"
        elif pitcher_last:
            lead += f" behind a strong {pitcher_last} outing"
        elif top_hitter_last:
            lead += f", {top_hitter_last} leading the way"

        return lead + gb_tail + "."

    else:
        if streak_type == "L" and streak_num >= 3:
            n = _ordinal_word(streak_num)
            return f"{CFG.team_name} drop their {n} straight. Time to stop the slide{gb_tail}."
        return f"{CFG.team_city} falls to {opponent}{gb_tail}."


# ---------------------------------------------------------------------------
# Insight (editorial interpretation, not just facts)
# ---------------------------------------------------------------------------

def get_insight(team, last_game=None):
    """
    Generate an editorial takeaway with interpretation.
    Identifies whether pitching or offense is driving the recent run,
    layers in standings context, and gives the fan something to carry.
    """
    avg = team.get("avg", "-")
    era = team.get("era", "-")
    ops = team.get("ops", "-")
    last10 = team.get("last10", "-")
    games_back = team.get("games_back", "-")

    # Parse numerics safely
    def _f(val, default):
        try:
            return float(str(val).replace("+", ""))
        except (ValueError, TypeError):
            return default

    era_val = _f(era, 4.00)
    ops_val = _f(ops, 0.720)

    last10_wins, last10_losses = 0, 0
    if last10 and "-" in last10:
        try:
            w, l = last10.split("-")
            last10_wins, last10_losses = int(w), int(l)
        except ValueError:
            pass

    try:
        gb_val = float(str(games_back))
        in_race = 0 < gb_val <= 4.0
        leading = False
    except (ValueError, TypeError):
        gb_val = 0.0
        in_race = False
        leading = (games_back == "-")

    # Classify the current form
    pitching_strong = era_val < 3.80   # ~top-third of MLB
    offense_weak    = ops_val < 0.700  # below league average
    offense_strong  = ops_val > 0.750
    hot_streak      = last10_wins >= 7

    # Pick the most interesting angle and write to it
    if hot_streak and pitching_strong and offense_weak:
        headline = f"The pitching staff is carrying this run."
        detail = (
            f"{CFG.team_city} has won {_cardinal_word(last10_wins)} of their last ten "
            f"despite a {ops} OPS. Staff ERA of {era} has done the "
            f"heavy lifting."
        )
        if in_race:
            detail += (
                f" {games_back} back in the {CFG.division_name}. "
                f"Staff has kept them in it."
            )
        elif leading:
            detail += (
                f" Sitting in first place on a {era} ERA while the offense has been quiet "
                f"means the pitching is carrying more than its share."
            )

    elif hot_streak and offense_strong:
        headline = f"The lineup is the engine right now."
        detail = (
            f"A {ops} OPS over the season, with the bats showing real pop. "
            f"The staff ERA sits at {era}. "
        )
        if in_race:
            detail += f"At {games_back} back, the {CFG.team_name} are right in the {CFG.division_name} race."
        elif leading:
            detail += f"{CFG.team_city} is setting the pace in the division."

    elif hot_streak:
        headline = f"Balanced ball. {CFG.team_name} are {last10} in the last ten."
        detail = (
            f"Both sides have contributed: {avg} average, {ops} OPS at the plate, "
            f"{era} ERA from the staff. "
        )
        if in_race:
            detail += f"At {games_back} back in the {CFG.division_short}, they're squarely in the race."

    elif last10_wins <= 3:
        headline = f"A {last10} stretch over the last ten is a real concern."
        if era_val > 4.30 and ops_val >= 0.700:
            # Rotation is the primary drag
            detail = (
                f"The {CFG.team_name} are batting {avg} ({ops} OPS). "
                f"Good enough to compete. But a {era} ERA has cost them. "
                f"The pitching is the problem."
            )
        elif ops_val < 0.700 and era_val <= 4.30:
            # Offense is the primary drag
            detail = (
                f"A {ops} OPS over this stretch has made it hard to win. "
                f"Staff ERA is {era}. The runs haven't been there."
            )
        else:
            # Both sides struggling
            detail = (
                f"The {CFG.team_name} are batting {avg} ({ops} OPS) "
                f"with a {era} ERA. Neither side has stopped the slide."
            )
        if in_race:
            detail += f" They're {games_back} back in the {CFG.division_name}."
        elif leading:
            detail += f" Sitting in first despite the slide."

    else:
        # Middle-of-the-road — surface the most relevant tension or mismatch
        if pitching_strong:
            # Good pitching, but the results haven't followed
            headline = f"A {era} ERA should be winning more games."
            detail = (
                f"Staff ERA is {era}. That's held up. But {CFG.team_city} "
                f"is just {last10} in the last ten. "
                f"A {ops} OPS hasn't turned good pitching into wins."
            )
        elif era_val > 4.30:
            # Weak rotation is the drag on results
            headline = f"The rotation is what's held them back."
            detail = (
                f"The {CFG.team_name} are putting up {ops} OPS at the plate, "
                f"but a {era} ERA from the staff has cancelled it out. "
                f"That gap explains the {last10} stretch."
            )
        elif offense_weak:
            # Average pitching, offense is the bottleneck
            headline = f"The offense hasn't matched the pitching."
            detail = (
                f"The staff is holding at {era} ERA, but a {ops} OPS at the plate "
                f"has made it difficult. {CFG.team_city} sits at {last10} over their last ten "
                f"with neither side pulling ahead."
            )
        else:
            # True middle — everything average, no dominant signal
            headline = f"Neither side has clicked. {last10} in the last ten."
            detail = (
                f"{avg} average, {ops} OPS, {era} ERA. "
                f"When no side takes control, the results end up in the middle."
            )
        if in_race:
            detail += f" They're {games_back} back in the {CFG.division_name}."
        elif leading:
            detail += f" Still in first, but the inconsistency is real."

    # Build compact "why" line — 2–3 editorial signals, not raw labels
    why_signals = []
    if era_val < 3.80:
        why_signals.append(f"staff carrying ({era} ERA)")
    elif era_val > 4.30:
        why_signals.append(f"rotation a concern ({era} ERA)")
    else:
        why_signals.append(f"ERA at {era}")

    if ops_val < 0.700:
        why_signals.append(f"quiet bats ({ops} OPS)")
    elif ops_val > 0.750:
        why_signals.append(f"offense clicking ({ops} OPS)")
    else:
        why_signals.append(f"OPS at {ops}")

    if last10 and "-" in last10:
        w_str, l_str = last10.split("-")
        why_signals.append(f"{w_str}\u2013{l_str} in the last ten")

    why = " · ".join(why_signals[:3]) if why_signals else None

    result = {"headline": headline, "detail": detail.strip()}
    if why:
        result["why"] = why

    _check_insight_language(headline + " " + detail)
    return result


# ---------------------------------------------------------------------------
# Anti-speculation guardrail (shared — imported from engine.narrative)
# ---------------------------------------------------------------------------

def _check_insight_language(text):
    check_insight_language(text)


# ---------------------------------------------------------------------------
# Looking Ahead hook — scored candidate system
# ---------------------------------------------------------------------------

HOOK_HISTORY_PATH = Path(__file__).with_name("hook_history.json")
STORY_STATE_PATH  = Path(__file__).with_name("story_state.json")

# Score weights — tune these to shift emphasis between dimensions
_HOOK_WEIGHTS = {
    "game_relevance": 0.35,  # how tied is this to tonight's specific game
    "fact_strength":  0.30,  # how strong/unusual is the underlying signal
    "specificity":    0.20,  # how concrete/recent is the framing
    "stakes":         0.15,  # does this raise the importance of tonight
}

# Novelty penalties applied to hook score when the same type appeared recently
_NOVELTY_PENALTY_YESTERDAY = 0.10   # same type used in yesterday's brief
_NOVELTY_PENALTY_RECENT    = 0.05   # same type appeared 2–3 briefs ago

# Distinctiveness penalty — applied when the hook's primary theme is already
# covered by the subhead or the main insight on the same page.
# Soft nudge: a repeated-theme hook can still win if its signal is clearly stronger.
_DISTINCTIVENESS_PENALTY_DIRECT = 0.10   # hook theme directly mirrors page content

# Hook is omitted entirely if best score falls below this threshold
_MIN_HOOK_SCORE = 0.45

# Primary editorial theme each hook type addresses.
# Used by _detect_page_themes() + score_looking_ahead_hook() to penalise themes
# the reader already encountered in the subhead / main insight.
# None = hook covers a fresh angle with no direct page-level counterpart.
_HOOK_TYPE_THEMES = {
    "race_context":         "race",      # division standings / games-back context
    "team_momentum":        "momentum",  # team recent-form / win-streak context
    "pitcher_form":         "pitching",  # tonight's SP performance angle
    "opponent_weakness":    None,        # matchup edge — distinct from general pitching narrative
    "opponent_cold_streak": None,        # opponent's form — not covered by subhead/insight
}


def _detect_page_themes(subhead, insight):
    """
    Infer which editorial themes are already present in the subhead and main insight.
    Returns a frozenset of theme strings used to penalise redundant hook candidates.

    Themes detected
    ---------------
    "race"     — standings position / division race is the lead angle
    "momentum" — Padres win streak or recent-form hot-take is the focus
    "pitching" — Padres pitching staff is explicitly called the run driver

    Detection is keyword-based: fast, transparent, and easy to tune by editing
    the keyword lists below.
    """
    parts = [subhead or ""]
    if isinstance(insight, dict):
        parts.append(insight.get("headline") or "")
        parts.append(insight.get("detail") or "")
    text = " ".join(parts).lower()

    themes = set()

    # Race / standings angle (subhead gb_tail, insight race mention)
    if any(kw in text for kw in [
        "back in the", "nl west race", "division race", "games back",
        "back in the west", "back in the nl west",
    ]):
        themes.add("race")

    # Padres momentum / streak angle (subhead win-streak lead, insight hot_streak)
    if any(kw in text for kw in [
        "straight", "win streak", "last ten", "last 10",
        "hot streak", "won their",
    ]):
        themes.add("momentum")

    # Pitching-carries-the-team angle (insight pitching_strong + offense_weak branch)
    if any(kw in text for kw in [
        "pitching staff", "staff is carrying", "carrying this run",
        "staff era", "era has been doing", "doing the heavy",
    ]):
        themes.add("pitching")

    return frozenset(themes)


def load_hook_history():
    """Return list of recent hook types (most recent first, max 3)."""
    try:
        if HOOK_HISTORY_PATH.exists():
            data = json.loads(HOOK_HISTORY_PATH.read_text())
            return data.get("recent_types", [])[:3]
    except Exception:
        pass
    return []


def save_hook_history(hook_type, current_history):
    """Prepend hook_type to history and persist, keeping last 3 entries."""
    updated = ([hook_type] + current_history)[:3]
    try:
        HOOK_HISTORY_PATH.write_text(json.dumps({"recent_types": updated}, indent=2))
    except Exception as e:
        print(f"  warn: could not write hook_history.json: {e}", file=sys.stderr)


def _get_team_hitting_stats(team_id):
    """Fetch a team's season hitting stats. Returns stat dict or {}."""
    try:
        data = get(f"teams/{team_id}/stats", stats="season", group="hitting", season=SEASON)
        for s in data.get("stats", []):
            if s.get("group", {}).get("displayName") == "hitting":
                splits = s.get("splits", [])
                if splits:
                    return splits[0].get("stat", {})
    except Exception:
        pass
    return {}


def _get_pitcher_recent_starts(pitcher_id, n=4):
    """Fetch pitcher's last N starts from game log. Returns list of stat dicts."""
    try:
        data = get(f"people/{pitcher_id}/stats", stats="gameLog", group="pitching", season=SEASON)
        for s in data.get("stats", []):
            if s.get("group", {}).get("displayName") == "pitching":
                starts = [
                    sp.get("stat", {})
                    for sp in s.get("splits", [])
                    if int(sp.get("stat", {}).get("gamesStarted", 0) or 0) > 0
                ]
                return starts[-n:] if len(starts) >= n else starts
    except Exception:
        pass
    return []


def _era_from_stats(stat_list):
    """Compute ERA from a list of pitching stat dicts. Returns float or None."""
    try:
        total_er = sum(int(s.get("earnedRuns", 0) or 0) for s in stat_list)
        total_ip = sum(float(s.get("inningsPitched", "0") or "0") for s in stat_list)
        return round((total_er * 9) / total_ip, 2) if total_ip > 0 else None
    except (ValueError, TypeError):
        return None


def build_looking_ahead_hook_candidates(raw_game, team, standings):
    """
    Build all eligible hook candidates for the Looking Ahead section.
    Returns a list of dicts: {type, text, fact_strength, game_relevance, specificity, stakes, _meta}.

    Hook types: pitcher_form, opponent_weakness, opponent_cold_streak,
                race_context, padres_momentum.
    """
    if not raw_game:
        return []

    home = _is_home(raw_game)
    sd_side = "home" if home else "away"
    opp_side = "away" if home else "home"
    opponent_abbr = _opponent_abbr(raw_game)
    opp_team_id = raw_game["teams"][opp_side]["team"]["id"]

    sd_pp = raw_game["teams"][sd_side].get("probablePitcher", {})
    pitcher_id = sd_pp.get("id")
    pitcher_name = sd_pp.get("fullName", "")
    pitcher_last = pitcher_name.split()[-1] if pitcher_name else ""

    candidates = []

    # ---- 1. Pitcher form ----
    if pitcher_id and pitcher_last:
        recent = _get_pitcher_recent_starts(pitcher_id, n=4)
        if len(recent) >= 3:
            n_starts = len(recent)
            era = _era_from_stats(recent)
            wins = sum(1 for s in recent if int(s.get("wins", 0) or 0) > 0)

            if era is not None and era < 3.50:
                # Fact strength scales with how low the ERA is
                if era < 1.80:
                    fact_str = 1.00
                elif era < 2.20:
                    fact_str = 0.90
                elif era < 2.60:
                    fact_str = 0.78
                elif era < 3.00:
                    fact_str = 0.65
                else:
                    fact_str = 0.50

                text = (
                    f"{pitcher_last} has a {era:.2f} ERA over his last {n_starts} starts"
                    f". He takes the mound tonight."
                )
                candidates.append({
                    "type": "pitcher_form",
                    "text": text,
                    "fact_strength": fact_str,
                    "game_relevance": 0.90,  # directly about tonight's named starter
                    "specificity":    0.85,  # named pitcher + specific recent window
                    "stakes":         0.55,
                    "_meta": {"era": era, "n_starts": n_starts, "pitcher": pitcher_last},
                })

            if wins >= 3 and (era is None or era >= 3.50):
                # Wins-based fallback when ERA alone doesn't clear the bar
                fact_str = 0.85 if wins == n_starts else 0.68
                text = (
                    f"{pitcher_last} has won {wins} of his last {n_starts} starts"
                    f". He gets the ball tonight."
                )
                candidates.append({
                    "type": "pitcher_form",
                    "text": text,
                    "fact_strength": fact_str,
                    "game_relevance": 0.88,
                    "specificity":    0.78,
                    "stakes":         0.50,
                    "_meta": {"wins": wins, "n_starts": n_starts, "pitcher": pitcher_last},
                })

    # ---- 2. Opponent offensive weakness ----
    opp_hit = _get_team_hitting_stats(opp_team_id)
    if opp_hit:
        avg_str = opp_hit.get("avg", "")
        ops_str = opp_hit.get("ops", "")
        try:
            avg_val = float(avg_str)
        except (ValueError, TypeError):
            avg_val = None
        try:
            ops_val = float(ops_str)
        except (ValueError, TypeError):
            ops_val = None

        if avg_val and avg_val < 0.235:
            if avg_val < 0.205:
                fact_str = 0.95
            elif avg_val < 0.215:
                fact_str = 0.82
            elif avg_val < 0.225:
                fact_str = 0.68
            else:
                fact_str = 0.52

            if pitcher_last:
                text = (
                    f"{opponent_abbr}'s {avg_str} average gives {pitcher_last}"
                    f" a favorable matchup tonight."
                )
                spec = 0.78
            else:
                text = (
                    f"{opponent_abbr} is batting {avg_str} as a team"
                    f". Favorable matchup for {CFG.team_city} tonight."
                )
                spec = 0.62

            candidates.append({
                "type": "opponent_weakness",
                "text": text,
                "fact_strength": fact_str,
                "game_relevance": 0.75,
                "specificity":    spec,
                "stakes":         0.48,
                "_meta": {"avg": avg_val, "avg_str": avg_str, "opponent": opponent_abbr},
            })

        elif ops_val and ops_val < 0.690:
            # OPS hook only when avg didn't already fire
            if ops_val < 0.640:
                fact_str = 0.90
            elif ops_val < 0.660:
                fact_str = 0.75
            else:
                fact_str = 0.58

            if pitcher_last:
                text = (
                    f"{opponent_abbr} ranks among the weakest offenses in baseball"
                    f". {pitcher_last} draws a favorable matchup tonight."
                )
                spec = 0.70
            else:
                text = (
                    f"{opponent_abbr} has a {ops_str} OPS"
                    f". The {CFG.team_name} have a favorable matchup tonight."
                )
                spec = 0.55

            candidates.append({
                "type": "opponent_weakness",
                "text": text,
                "fact_strength": fact_str,
                "game_relevance": 0.72,
                "specificity":    spec,
                "stakes":         0.45,
                "_meta": {"ops": ops_val, "ops_str": ops_str, "opponent": opponent_abbr},
            })

    # ---- 3. Opponent cold streak (NL West only) ----
    opp_row = next(
        (r for r in standings if r["team"].upper() == opponent_abbr.upper()),
        None,
    )
    if opp_row and opp_row.get("last10") and "-" in opp_row["last10"]:
        opp_l10 = opp_row["last10"]
        try:
            opp_l10_wins = int(opp_l10.split("-")[0])
            if opp_l10_wins <= 4:
                if opp_l10_wins <= 2:
                    fact_str = 0.90
                elif opp_l10_wins == 3:
                    fact_str = 0.70
                else:
                    fact_str = 0.52

                text = (
                    f"{opponent_abbr} has gone just {opp_l10} in their last ten"
                    f". The {CFG.team_name} catch them at the right time."
                )
                candidates.append({
                    "type": "opponent_cold_streak",
                    "text": text,
                    "fact_strength": fact_str,
                    "game_relevance": 0.68,
                    "specificity":    0.65,
                    "stakes":         0.58,
                    "_meta": {"opp_l10": opp_l10, "opp_l10_wins": opp_l10_wins},
                })
        except ValueError:
            pass

    # ---- 4. Race context ----
    games_back = team.get("games_back", "-")
    streak = team.get("streak", "")
    m_streak = re.match(r'^W(\d+)$', streak)
    streak_n = int(m_streak.group(1)) if m_streak else 0

    try:
        gb_val = float(str(games_back))
        if 0 < gb_val <= 3.5:
            if gb_val <= 1.0:
                stakes = 0.95
            elif gb_val <= 2.0:
                stakes = 0.82
            elif gb_val <= 2.5:
                stakes = 0.70
            else:
                stakes = 0.58

            if streak_n >= 2:
                text = (
                    f"{CFG.team_city} is {games_back} back in the {CFG.division_name} on a {streak_n}-game"
                    f" win streak. Tonight matters."
                )
                fact_str = min(0.65 + (streak_n - 2) * 0.06, 0.90)
                spec = 0.72
            else:
                text = (
                    f"{CFG.team_city} sits just {games_back} back in the {CFG.division_name}"
                    f". Every game in this stretch counts."
                )
                fact_str = 0.52
                spec = 0.52

            candidates.append({
                "type": "race_context",
                "text": text,
                "fact_strength": fact_str,
                "game_relevance": 0.62,
                "specificity":    spec,
                "stakes":         stakes,
                "_meta": {"gb": gb_val, "streak_n": streak_n},
            })
    except (ValueError, TypeError):
        # First place — only worth a hook on a meaningful win streak
        if games_back == "-" and streak_n >= 3:
            text = (
                f"{CFG.team_city} leads the {CFG.division_name} on a {streak_n}-game win streak"
                f". Tonight is a chance to extend it."
            )
            candidates.append({
                "type": "race_context",
                "text": text,
                "fact_strength": min(0.62 + streak_n * 0.04, 0.90),
                "game_relevance": 0.62,
                "specificity":    0.68,
                "stakes":         0.75,
                "_meta": {"leading": True, "streak_n": streak_n},
            })

    # ---- 5. Padres momentum ----
    last10 = team.get("last10", "-")
    if last10 and "-" in last10:
        try:
            l10_wins = int(last10.split("-")[0])
            if l10_wins >= 7:
                if l10_wins >= 9:
                    fact_str = 0.88
                elif l10_wins == 8:
                    fact_str = 0.68
                else:
                    fact_str = 0.52

                text = (
                    f"{CFG.team_name} have won {l10_wins} of their last ten"
                    f". They carry that form into tonight."
                )
                candidates.append({
                    "type": "team_momentum",
                    "text": text,
                    "fact_strength": fact_str,
                    "game_relevance": 0.58,  # general form, not tonight-specific
                    "specificity":    0.52,
                    "stakes":         0.50,
                    "_meta": {"l10_wins": l10_wins},
                })
        except ValueError:
            pass

    return candidates


def score_looking_ahead_hook(candidate, recent_hook_types=None, page_themes=None):
    """
    Weighted score for a hook candidate with soft novelty and distinctiveness penalties.
    Returns a float roughly in [0.0, 1.0].

    Penalties (all soft — a penalised hook can still win if its signal is strongest):
      novelty_pen   — same hook type used in a recent brief (day-over-day repetition)
      distinct_pen  — hook's primary theme already covered by subhead / main insight
    """
    base = (
        candidate["game_relevance"] * _HOOK_WEIGHTS["game_relevance"]
        + candidate["fact_strength"] * _HOOK_WEIGHTS["fact_strength"]
        + candidate["specificity"]   * _HOOK_WEIGHTS["specificity"]
        + candidate["stakes"]        * _HOOK_WEIGHTS["stakes"]
    )

    novelty_pen = 0.0
    if recent_hook_types:
        hook_type = candidate["type"]
        # Yesterday = most recent entry
        if recent_hook_types[0] == hook_type:
            novelty_pen += _NOVELTY_PENALTY_YESTERDAY
        # 2–3 days ago
        if len(recent_hook_types) >= 2 and hook_type in recent_hook_types[1:3]:
            novelty_pen += _NOVELTY_PENALTY_RECENT

    # Distinctiveness penalty — nudge away from themes already on the page
    # Tune by adjusting _DISTINCTIVENESS_PENALTY_DIRECT or _HOOK_TYPE_THEMES
    distinct_pen = 0.0
    if page_themes:
        hook_theme = _HOOK_TYPE_THEMES.get(candidate["type"])
        if hook_theme and hook_theme in page_themes:
            distinct_pen += _DISTINCTIVENESS_PENALTY_DIRECT

    return round(base - novelty_pen - distinct_pen, 4)


def pick_best_looking_ahead_hook(candidates, recent_hook_types=None, page_themes=None):
    """
    Score all candidates and return (text, type) for the best one.
    Returns (None, None) if the best score is below _MIN_HOOK_SCORE.
    """
    if not candidates:
        return None, None

    scored = sorted(
        ((score_looking_ahead_hook(c, recent_hook_types, page_themes), c) for c in candidates),
        key=lambda t: t[0],
        reverse=True,
    )

    # Debug: log per-candidate breakdown (base, novelty, distinctiveness, final)
    print("  hook scoring breakdown:", file=sys.stderr)
    for final_score, c in scored:
        base = round(
            c["game_relevance"] * _HOOK_WEIGHTS["game_relevance"]
            + c["fact_strength"] * _HOOK_WEIGHTS["fact_strength"]
            + c["specificity"]   * _HOOK_WEIGHTS["specificity"]
            + c["stakes"]        * _HOOK_WEIGHTS["stakes"],
            4,
        )
        n_pen = 0.0
        if recent_hook_types:
            if recent_hook_types[0] == c["type"]:
                n_pen += _NOVELTY_PENALTY_YESTERDAY
            if len(recent_hook_types) >= 2 and c["type"] in recent_hook_types[1:3]:
                n_pen += _NOVELTY_PENALTY_RECENT
        hook_theme = _HOOK_TYPE_THEMES.get(c["type"])
        d_pen = (
            _DISTINCTIVENESS_PENALTY_DIRECT
            if (page_themes and hook_theme and hook_theme in page_themes)
            else 0.0
        )
        print(
            f"    {c['type']:25s}  base={base:.4f}"
            f"  novelty=-{n_pen:.4f}  distinct=-{d_pen:.4f}  final={final_score:.4f}",
            file=sys.stderr,
        )

    best_score, best = scored[0]
    if best_score < _MIN_HOOK_SCORE:
        print(f"  no hook: best score {best_score:.4f} below threshold {_MIN_HOOK_SCORE}", file=sys.stderr)
        return None, None

    return best["text"], best["type"]


def build_looking_ahead_hook(raw_game, team, standings, subhead=None, insight=None):
    """
    Return (hook_text, hook_type) for the Looking Ahead section.
    Returns (None, None) when no candidate clears the minimum score threshold.

    Pass subhead and insight so the scorer can apply a distinctiveness penalty
    against themes already covered on the same page.
    """
    recent_hook_types = load_hook_history()
    candidates = build_looking_ahead_hook_candidates(raw_game, team, standings)
    page_themes = _detect_page_themes(subhead, insight)
    if page_themes:
        print(f"  page themes detected: {sorted(page_themes)}", file=sys.stderr)
    return pick_best_looking_ahead_hook(candidates, recent_hook_types, page_themes)


# ---------------------------------------------------------------------------
# Story State + Delta + Narrative (shared — imported from engine.narrative)
# ---------------------------------------------------------------------------

# load_story_state, save_story_state, build_story_state, classify_game_emotion,
# compute_story_delta, generate_narrative_copy are all imported at the top.


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build():
    print("Fetching team summary + snapshot...", file=sys.stderr)
    team = get_team_summary_and_snapshot()

    print("Fetching last game...", file=sys.stderr)
    last_game = get_last_game()

    print("Detecting clutch moment...", file=sys.stderr)
    if last_game.get("status") == "final":
        clutch = identify_clutch_player(
            last_game["gamePk"],
            last_game["home"],
            fallback_hitters=last_game.get("key_hitters"),
        )
        last_game["clutch_player"] = clutch
        if clutch:
            print(
                f"  clutch: {clutch['name']} — {clutch['event']}"
                f" (inn {clutch['inning']}, {clutch['confidence']})",
                file=sys.stderr,
            )
        else:
            print("  clutch: none detected", file=sys.stderr)
    else:
        last_game["clutch_player"] = None

    print("Detecting game driver...", file=sys.stderr)
    if last_game.get("status") == "final":
        game_driver = identify_game_driver(
            last_game.get("full_box"),
            last_game.get("key_hitters") or [],
            last_game.get("key_pitcher"),
        )
        last_game["game_driver"] = game_driver
        if game_driver:
            print(
                f"  game_driver: {game_driver['name']} — {game_driver['reason']}"
                f" ({game_driver['confidence']})",
                file=sys.stderr,
            )
        else:
            print("  game_driver: none detected", file=sys.stderr)
    else:
        last_game["game_driver"] = None

    print("Fetching next game...", file=sys.stderr)
    next_game, next_game_raw = get_next_game()

    print(f"Fetching {CFG.division_name} standings...", file=sys.stderr)
    standings = get_standings()

    print("Building editorial layer...", file=sys.stderr)
    subhead = build_subhead(last_game, team)
    insight = get_insight(team, last_game)

    print("Building Looking Ahead hook...", file=sys.stderr)
    ahead_hook, ahead_hook_type = build_looking_ahead_hook(
        next_game_raw, team, standings, subhead=subhead, insight=insight
    )
    if ahead_hook and next_game:
        next_game["insight"] = ahead_hook
        next_game["hook_type"] = ahead_hook_type
        save_hook_history(ahead_hook_type, load_hook_history())

    print("Computing story state and delta...", file=sys.stderr)
    prev_state   = load_story_state(STORY_STATE_PATH)
    story_state  = build_story_state(team, last_game)
    story_delta  = compute_story_delta(prev_state, story_state)
    print(f"  [emotion] game_emotion_level: {story_state.get('game_emotion_level', 'normal')}", file=sys.stderr)

    # Regenerate game_note with clutch + emotion context now that both are available
    if last_game.get("status") == "final":
        ls = last_game.get("linescore") or [[], []]
        last_game["game_note"] = _generate_game_note(
            ls[0] if ls else [],
            ls[1] if len(ls) > 1 else [],
            last_game.get("score", {}),
            last_game.get("opponent", ""),
            last_game.get("key_hitters") or [],
            last_game.get("result", ""),
            clutch=last_game.get("clutch_player"),
            emotion=story_state.get("game_emotion_level", "normal"),
        )

    # Build story threads + emotional hook
    story_threads = build_story_threads(story_state, last_game)
    story_hook    = build_story_hook(story_state, last_game, story_threads,
                                     game_driver=last_game.get("game_driver"))
    if story_threads:
        print(f"  [story_threads] {story_threads}", file=sys.stderr)
    if story_hook:
        print(f"  [story_hook] {story_hook!r}", file=sys.stderr)

    brief_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "season": SEASON,
        "team": team,
        "last_game": last_game,
        "next_game": next_game,
        "standings": standings,
        "hot_players": {"hitters": [], "pitchers": []},  # placeholder for V1.1
        "subhead": subhead,
        "insight": insight,
        "story_hook": story_hook,
        "story_threads_debug": story_threads,
    }

    print("Generating narrative copy...", file=sys.stderr)
    if last_game.get("status") == "postponed":
        print("  [narrative] postponed — using deterministic narrative", file=sys.stderr)
        narrative_copy = generate_postponed_narrative(last_game, next_game)
    else:
        narrative_copy = generate_narrative_copy(
            brief_data, story_state, story_delta, CFG.team_name,
            story_threads=story_threads,
            story_hook=story_hook,
            looking_ahead_hook=(next_game or {}).get("insight"),
            game_driver=last_game.get("game_driver"),
        )
    save_story_state(story_state, STORY_STATE_PATH)  # always persist so delta works next run
    if narrative_copy:
        brief_data["narrative"] = {
            **narrative_copy,
            "story_state": story_state,
            "story_delta": story_delta,
        }

    return brief_data


if __name__ == "__main__":
    brief = build()
    print(json.dumps(brief, indent=2, default=str))
    out_path = Path(__file__).with_name("brief.json")
    with open(out_path, "w") as f:
        json.dump(brief, f, indent=2, default=str)
    print(f"\nWrote {out_path}", file=sys.stderr)