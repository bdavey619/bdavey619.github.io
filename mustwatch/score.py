"""
score.py — Pure scoring functions for Must Watch This Week.

No I/O. All functions take data, return numbers.
"""

from config import (
    MARQUEE_PLAYERS,
    SEASON_PHASE_MULTIPLIERS,
    MLB_TOTAL_GAMES, NBA_TOTAL_GAMES,
    MLB_RACE_THRESHOLD,
    NBA_PLAYOFF_RANK_CUTOFF, NBA_PLAYIN_RANK_CUTOFF,
)
from models import TeamContext, ScoredEvent


# ---------------------------------------------------------------------------
# Team quality (0–10) — input to competitive_balance
# ---------------------------------------------------------------------------

def team_quality(win_pct: float) -> float:
    """Map win percentage to a quality score from 2–10."""
    if win_pct >= 0.650: return 10.0
    if win_pct >= 0.620: return 9.0
    if win_pct >= 0.580: return 8.0
    if win_pct >= 0.540: return 7.0
    if win_pct >= 0.520: return 6.0
    if win_pct >= 0.500: return 5.0
    if win_pct >= 0.480: return 4.0
    if win_pct >= 0.460: return 3.0
    return 2.0


# ---------------------------------------------------------------------------
# Season phase multiplier
# ---------------------------------------------------------------------------

def season_phase_multiplier(games_played: int, total_games: int) -> float:
    if total_games == 0:
        return 1.0
    pct = games_played / total_games
    if pct < 0.20:
        return SEASON_PHASE_MULTIPLIERS["early"]
    if pct < 0.70:
        return SEASON_PHASE_MULTIPLIERS["mid"]
    return SEASON_PHASE_MULTIPLIERS["late"]


# ---------------------------------------------------------------------------
# Stakes (0–30)
# ---------------------------------------------------------------------------

def score_stakes(
    home: TeamContext,
    away: TeamContext,
    is_postseason: bool,
    is_playin: bool = False,
) -> tuple[float, str]:
    """Returns (score, detail_string)."""
    if is_postseason:
        # Prefer the explicit play-in flag (ESPN season.type == 5).
        # Keep seed-range inference as fallback in case the type field is absent.
        if is_playin:
            return 25.0, "play-in game"

        if home.sport == "NBA":
            home_rank = home.conference_rank or 99
            away_rank = away.conference_rank or 99
            if (NBA_PLAYOFF_RANK_CUTOFF < home_rank <= NBA_PLAYIN_RANK_CUTOFF and
                    NBA_PLAYOFF_RANK_CUTOFF < away_rank <= NBA_PLAYIN_RANK_CUTOFF):
                return 25.0, "play-in game (inferred)"

        return 29.0, "postseason"

    if home.sport == "MLB":
        base, detail = _mlb_stakes_base(home, away)
        mult = season_phase_multiplier(
            max(home.games_played, away.games_played),
            MLB_TOTAL_GAMES,
        )
    else:
        base, detail = _nba_stakes_base(home, away)
        mult = season_phase_multiplier(
            max(home.games_played, away.games_played),
            NBA_TOTAL_GAMES,
        )

    raw    = round(base * mult, 1)
    detail = f"{detail} ×{mult:.2f}"
    return raw, detail


def _in_mlb_race(ctx: TeamContext) -> bool:
    """True if team is in a meaningful playoff/division race."""
    # Division leader
    if ctx.games_back is None:
        return True
    # Within 5 of division leader
    if ctx.games_back <= MLB_RACE_THRESHOLD:
        return True
    # Within 5 of last wild card spot
    if ctx.wc_games_back is not None and ctx.wc_games_back <= MLB_RACE_THRESHOLD:
        return True
    return False


def _mlb_stakes_base(home: TeamContext, away: TeamContext) -> tuple[float, str]:
    home_in = _in_mlb_race(home)
    away_in = _in_mlb_race(away)

    if home_in and away_in:
        avg_wpct = (home.win_pct + away.win_pct) / 2
        if avg_wpct >= 0.550:
            return 22.0, "both in race (strong)"
        return 18.0, "both in race"

    if home_in or away_in:
        return 15.0, "one team in race"

    avg_wpct = (home.win_pct + away.win_pct) / 2
    if avg_wpct >= 0.520:
        return 12.0, "both above .500"
    return 5.0, "no meaningful stakes"


def _nba_stakes_base(home: TeamContext, away: TeamContext) -> tuple[float, str]:
    home_rank = home.conference_rank or 99
    away_rank = away.conference_rank or 99

    # Both in direct playoff position (top 6)
    if home_rank <= NBA_PLAYOFF_RANK_CUTOFF and away_rank <= NBA_PLAYOFF_RANK_CUTOFF:
        avg_wpct = (home.win_pct + away.win_pct) / 2
        if avg_wpct >= 0.600:
            return 22.0, "top-6 playoff teams (elite)"
        return 18.0, "both in direct playoff position"

    home_playin = NBA_PLAYOFF_RANK_CUTOFF < home_rank <= NBA_PLAYIN_RANK_CUTOFF
    away_playin = NBA_PLAYOFF_RANK_CUTOFF < away_rank <= NBA_PLAYIN_RANK_CUTOFF

    if (home_rank <= NBA_PLAYOFF_RANK_CUTOFF and away_playin) or \
       (away_rank <= NBA_PLAYOFF_RANK_CUTOFF and home_playin) or \
       (home_playin and away_playin):
        return 16.0, "playoff/play-in implications"

    if home_playin or away_playin:
        return 14.0, "one team in play-in race"

    avg_wpct = (home.win_pct + away.win_pct) / 2
    if avg_wpct >= 0.520:
        return 10.0, "both above .500"
    return 5.0, "no meaningful stakes"


# ---------------------------------------------------------------------------
# Competitive balance (0–20)
# ---------------------------------------------------------------------------

def score_competitive_balance(home: TeamContext, away: TeamContext) -> float:
    """
    min(team1_quality, team2_quality) × 2.
    One weak team tanks the score regardless of how strong the opponent is.
    """
    q_home = team_quality(home.win_pct)
    q_away = team_quality(away.win_pct)
    return round(min(q_home, q_away) * 2, 1)


# ---------------------------------------------------------------------------
# Momentum (0–15)
# ---------------------------------------------------------------------------

def score_momentum(home: TeamContext, away: TeamContext) -> float:
    """
    L10 quality for each team (0–6 pts each) + streak bonus (0–3).
    Max: 15.
    """
    def _l10_score(ctx: TeamContext) -> float:
        total = ctx.l10_wins + ctx.l10_losses
        if total == 0:
            return 3.0
        pct = ctx.l10_wins / total
        if pct >= 0.80: return 6.0
        if pct >= 0.70: return 5.0
        if pct >= 0.60: return 4.0
        if pct >= 0.40: return 3.0
        if pct >= 0.30: return 2.0
        return 1.0

    base = _l10_score(home) + _l10_score(away)  # 2–12

    # Bonus: any team on a 7+ game win streak
    streak_bonus = 0.0
    for ctx in (home, away):
        if ctx.streak_type == "W" and ctx.streak_n >= 7:
            streak_bonus = 3.0
            break

    return round(min(base + streak_bonus, 15.0), 1)


# ---------------------------------------------------------------------------
# Star power (0–15)
# ---------------------------------------------------------------------------

def score_star_power(home: TeamContext, away: TeamContext) -> tuple[float, str]:
    """Returns (score, detail_string)."""
    home_key = f"{home.sport}:{home.abbr}"
    away_key = f"{away.sport}:{away.abbr}"

    home_players = MARQUEE_PLAYERS.get(home_key, [])
    away_players = MARQUEE_PLAYERS.get(away_key, [])

    home_supers = [p for p in home_players if p["tier"] == "superstar"]
    home_stars  = [p for p in home_players if p["tier"] == "star"]
    away_supers = [p for p in away_players if p["tier"] == "superstar"]
    away_stars  = [p for p in away_players if p["tier"] == "star"]

    has_home_super = bool(home_supers)
    has_away_super = bool(away_supers)
    has_home_star  = bool(home_stars) or has_home_super
    has_away_star  = bool(away_stars) or has_away_super

    if has_home_super and has_away_super:
        score  = 15.0
        detail = f"{home_supers[0]['name']} vs {away_supers[0]['name']}"
    elif has_home_super and has_away_star:
        score  = 12.0
        star_name = away_stars[0]["name"] if away_stars else away_supers[0]["name"]
        detail = f"{home_supers[0]['name']} vs {star_name}"
    elif has_home_star and has_away_super:
        score  = 12.0
        star_name = home_stars[0]["name"] if home_stars else home_supers[0]["name"]
        detail = f"{star_name} vs {away_supers[0]['name']}"
    elif has_home_star and has_away_star:
        score  = 10.0
        h_name = (home_stars or home_supers)[0]["name"]
        a_name = (away_stars or away_supers)[0]["name"]
        detail = f"{h_name} vs {a_name}"
    elif has_home_star or has_away_star:
        score  = 6.0
        top    = (home_stars or home_supers or away_stars or away_supers)[0]["name"]
        detail = f"{top} (one side)"
    else:
        score  = 3.0
        detail = "no marquee players"

    return score, detail


# ---------------------------------------------------------------------------
# Narrative flags (0–20)
# ---------------------------------------------------------------------------

def score_narrative_flags(flags: list[str]) -> float:
    """
    Tier 1: elimination_game = 20, no stacking.
    Tier 2: rivalry=8, playoff_rematch=6, first_place_clash=5, ace_duel=6,
            marquee_starter=3. Capped at 12.
    marquee_starter only fires when ace_duel is absent (enforced in enrich.py).
    """
    if "elimination_game" in flags:
        return 20.0

    tier2 = 0.0
    if "rivalry"           in flags: tier2 += 8.0
    if "playoff_rematch"   in flags: tier2 += 6.0
    if "first_place_clash" in flags: tier2 += 5.0
    if "ace_duel"          in flags: tier2 += 6.0
    if "marquee_starter"   in flags: tier2 += 3.0

    return min(tier2, 12.0)


# ---------------------------------------------------------------------------
# Main scoring entry point
# ---------------------------------------------------------------------------

def score_event(se: ScoredEvent) -> ScoredEvent:
    """
    Compute all score components. Mutates se in place and returns it.
    """
    home = se.home_ctx
    away = se.away_ctx

    stakes, stakes_detail        = score_stakes(home, away, se.raw.is_postseason, se.raw.is_playin)
    comp_balance                  = score_competitive_balance(home, away)
    momentum                      = score_momentum(home, away)
    star_power, star_power_detail = score_star_power(home, away)
    flags_score                   = score_narrative_flags(se.flags)

    se.stakes_score              = stakes
    se.competitive_balance_score = comp_balance
    se.momentum_score            = momentum
    se.star_power_score          = star_power
    se.narrative_flags_score     = flags_score
    se.total_score               = round(stakes + comp_balance + momentum + star_power + flags_score, 1)
    se.stakes_detail             = stakes_detail
    se.star_power_detail         = star_power_detail

    return se
