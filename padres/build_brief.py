"""
build_brief.py — Padres Morning Brief data fetcher

Pulls Padres data from the MLB Stats API and writes brief.json
matching the agreed schema. No API key required.
"""

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API = "https://statsapi.mlb.com/api/v1"
PADRES_ID = 135
NL_LEAGUE_ID = 104
NL_WEST_DIVISION_ID = 203
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
        teamId=PADRES_ID,
        startDate=start.strftime("%Y-%m-%d"),
        endDate=end.strftime("%Y-%m-%d"),
        hydrate="linescore,decisions,probablePitcher,team,venue",
    )
    games = []
    for day in data.get("dates", []):
        games.extend(day.get("games", []))
    return games


def get_last_game():
    """Most recent completed game (ignores in-progress, walks back if needed)."""
    end = datetime.now().date()
    start = end - timedelta(days=14)
    games = _fetch_schedule(start, end)

    finals = [g for g in games if g.get("status", {}).get("abstractGameState") == "Final"]
    if not finals:
        return {"status": "off_day"}

    # Most recent: sort by gameDate, then gamePk as doubleheader tiebreaker
    finals.sort(key=lambda g: (g["gameDate"], g["gamePk"]), reverse=True)
    g = finals[0]
    return _format_last_game(g)


def get_next_game():
    """Next scheduled (not yet final) game."""
    start = datetime.now().date()
    end = start + timedelta(days=14)
    games = _fetch_schedule(start, end)

    upcoming = [
        g for g in games
        if g.get("status", {}).get("abstractGameState") in ("Preview", "Live")
    ]
    if not upcoming:
        return None

    upcoming.sort(key=lambda g: g["gameDate"])
    g = upcoming[0]
    return _format_next_game(g)


# ---------------------------------------------------------------------------
# Game formatting
# ---------------------------------------------------------------------------

def _is_home(game):
    return game["teams"]["home"]["team"]["id"] == PADRES_ID


def _opponent_abbr(game):
    side = "away" if _is_home(game) else "home"
    return game["teams"][side]["team"].get("abbreviation") \
        or game["teams"][side]["team"]["name"]


def _generate_game_note(sd_row, opp_row, score, opponent, key_hitters, result):
    """
    One-sentence editorial game note derived from line score patterns.
    Keeps logic simple: biggest inning, standout hitter, margin shape.
    """
    def _int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    sd_ints = [_int(v) for v in sd_row]
    opp_ints = [_int(v) for v in opp_row]

    margin = score.get("sd", 0) - score.get("opp", 0)

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

    # Biggest inning for each team: returns (inning_index, runs)
    def _biggest(ints):
        best = (-1, 0)
        for i, v in enumerate(ints):
            if v is not None and v > best[1]:
                best = (i, v)
        return best

    sd_big = _biggest(sd_ints)
    opp_big = _biggest(opp_ints)

    if result == "W":
        # Large SD inning (4+ runs)
        if sd_big[1] >= 4:
            inn = _ordinal_word(sd_big[0] + 1)
            if hitter_last and "HR" in hitter_line:
                return (f"A {sd_big[1]}-run {inn} — highlighted by a {hitter_last} "
                        f"home run — gave San Diego the cushion it needed.")
            return f"A {sd_big[1]}-run {inn} inning gave San Diego the separation it needed."

        # 3-run inning
        if sd_big[1] == 3:
            inn = _ordinal_word(sd_big[0] + 1)
            if hitter_last and "HR" in hitter_line:
                return (f"{hitter_last}'s home run was part of a 3-run {inn} "
                        f"that put the Padres in front for good.")
            return f"A 3-run {inn} put San Diego in control and they never looked back."

        # Comfortable win driven by a standout hitter
        if margin >= 4 and hitter_last:
            if "HR" in hitter_line:
                return f"{hitter_last}'s home run powered a comfortable Padres win."
            m = re.search(r"(\d+) RBI", hitter_line)
            if m and int(m.group(1)) >= 3:
                return f"{hitter_last} drove in {m.group(1)} runs to fuel the Padres offense."

        # Late-inning pull-away
        if len(sd_ints) >= 8:
            late_sd = sum(v for v in sd_ints[6:] if v is not None)
            late_opp = sum(v for v in opp_ints[6:] if v is not None)
            if late_sd >= 3 and late_sd >= late_opp + 2:
                return (f"The Padres answered in the late innings, outscoring "
                        f"{opponent} {late_sd}–{late_opp} in the final frames.")

        # Generic W with a hitter hook
        if hitter_last:
            return f"{hitter_last}'s bat helped the Padres hold off {opponent}."
        return f"San Diego controlled the game and handled {opponent} without drama."

    else:  # Loss
        # Opponent had a big inning
        if opp_big[1] >= 4:
            inn = _ordinal_word(opp_big[0] + 1)
            return f"{opponent}'s {opp_big[1]}-run {inn} proved to be the difference."
        if opp_big[1] == 3:
            inn = _ordinal_word(opp_big[0] + 1)
            return f"A 3-run {inn} by {opponent} was more than the Padres could answer."

        # One-run loss
        if abs(margin) == 1:
            return f"San Diego couldn't manufacture the run they needed in a tight one."

        return f"The Padres couldn't find enough offense to keep pace with {opponent}."


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

    score = {"sd": sd_runs, "opp": opp_runs}
    game_note = _generate_game_note(
        linescore[0], linescore[1], score, _opponent_abbr(game), key_hitters, result
    )

    out = {
        "status": "final",
        "gamePk": game["gamePk"],
        "date": game.get("officialDate") or game["gameDate"][:10],
        "opponent": _opponent_abbr(game),
        "home": home,
        "result": result,
        "score": score,
        "linescore": linescore,
        "decisions": decisions,
        "key_hitters": key_hitters,
        "key_pitcher": key_pitcher,
        "context_line": context_line,
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
            out[f"{label}_team"] = "sd"
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
    # Convert to PT (UTC-7 during DST in April)
    pt = gd.astimezone(timezone(timedelta(hours=-7)))

    sd_side = "home" if home else "away"
    opp_side = "away" if home else "home"

    probable = {}
    sd_pp = game["teams"][sd_side].get("probablePitcher", {})
    opp_pp = game["teams"][opp_side].get("probablePitcher", {})
    if sd_pp: probable["sd"] = sd_pp.get("fullName", "TBD")
    if opp_pp: probable["opp"] = opp_pp.get("fullName", "TBD")

    return {
        "gamePk": game["gamePk"],
        "date": game.get("officialDate") or game["gameDate"][:10],
        "opponent": _opponent_abbr(game),
        "home": home,
        "time_local": pt.strftime("%-I:%M %p PT"),
        "probable": probable,
    }


# ---------------------------------------------------------------------------
# Standings
# ---------------------------------------------------------------------------

def get_standings():
    data = get("standings", leagueId=NL_LEAGUE_ID, season=SEASON, standingsTypes="regularSeason")
    rows = []
    for record in data.get("records", []):
        if record.get("division", {}).get("id") != NL_WEST_DIVISION_ID:
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
    standings = get("standings", leagueId=NL_LEAGUE_ID, season=SEASON)
    sd_record = None
    for record in standings.get("records", []):
        for tr in record.get("teamRecords", []):
            if tr["team"]["id"] == PADRES_ID:
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
    stats = get(f"teams/{PADRES_ID}/stats", stats="season", group="hitting,pitching", season=SEASON)
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
    if not last_game or last_game.get("status") != "final":
        return ""

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
            gb_tail = f" — {games_back} back in the West"
        elif gb_val <= 5.5:
            gb_tail = f", staying in the NL West hunt"
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
    if key_pitcher and decisions.get("win_team") == "sd":
        ip, er = _parse_pitcher_line(key_pitcher.get("line", ""))
        if ip is not None and ip >= 6.0 and er <= 3:
            pitcher_last = key_pitcher["name"].split()[-1]

    # Build the lead clause
    if result == "W":
        if streak_type == "W" and streak_num >= 3:
            n = _ordinal_word(streak_num)
            lead = f"Padres win their {n} straight"
        elif last10_wins >= 7:
            lead = f"San Diego stays hot — {last10} over the last ten"
        elif home:
            lead = "Padres take it at Petco"
        else:
            lead = f"Padres win on the road vs. {opponent}"

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
            return f"Padres drop their {n} straight — time to stop the slide{gb_tail}."
        return f"San Diego falls to {opponent}{gb_tail}."


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
            f"San Diego has won {_cardinal_word(last10_wins)} of their last ten "
            f"despite a {ops} OPS — the staff ERA of {era} has been doing the "
            f"heavy lifting while the lineup finds its footing."
        )
        if in_race:
            detail += (
                f" They're {games_back} back in the NL West. "
                f"If the offense wakes up, this team gets dangerous fast."
            )
        elif leading:
            detail += (
                " Holding down first place while the bats are still warming up "
                "is an encouraging sign for what's ahead."
            )

    elif hot_streak and offense_strong:
        headline = f"The lineup is the engine right now."
        detail = (
            f"A {ops} OPS over the season, with the bats showing real pop. "
            f"The staff ERA sits at {era}. "
        )
        if in_race:
            detail += f"At {games_back} back, the Padres are right in the NL West race."
        elif leading:
            detail += "San Diego is setting the pace in the division."

    elif hot_streak:
        headline = f"Balanced ball — Padres are {last10} over their last ten."
        detail = (
            f"No single weak spot: {avg} average, {ops} OPS at the plate, "
            f"{era} ERA from the staff. "
        )
        if in_race:
            detail += f"At {games_back} back in the West, they're squarely in the race."

    elif last10_wins <= 3:
        headline = f"A {last10} stretch over the last ten is a real concern."
        detail = (
            f"The Padres are batting {avg} as a team ({ops} OPS) "
            f"with a {era} staff ERA. The schedule won't wait — they need to find a rhythm."
        )

    else:
        # Middle-of-the-road, no strong angle
        headline = f"Padres hovering at {last10} over the last ten."
        detail = (
            f"Team line: {avg} average, {ops} OPS, {era} ERA. "
            f"The next stretch of games will define the shape of their season."
        )

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
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build():
    print("Fetching team summary + snapshot...", file=sys.stderr)
    team = get_team_summary_and_snapshot()

    print("Fetching last game...", file=sys.stderr)
    last_game = get_last_game()

    print("Fetching next game...", file=sys.stderr)
    next_game = get_next_game()

    print("Fetching NL West standings...", file=sys.stderr)
    standings = get_standings()

    print("Building editorial layer...", file=sys.stderr)
    subhead = build_subhead(last_game, team)
    insight = get_insight(team, last_game)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "season": SEASON,
        "team": team,
        "last_game": last_game,
        "next_game": next_game,
        "standings": standings,
        "hot_players": {"hitters": [], "pitchers": []},  # placeholder for V1.1
        "subhead": subhead,
        "insight": insight,
    }


if __name__ == "__main__":
    brief = build()
    print(json.dumps(brief, indent=2, default=str))
    out_path = Path(__file__).with_name("brief.json")
    with open(out_path, "w") as f:
        json.dump(brief, f, indent=2, default=str)
    print(f"\nWrote {out_path}", file=sys.stderr)