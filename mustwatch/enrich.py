"""
enrich.py — Normalize events, apply timing filter, detect narrative flags.
"""

import sys
from datetime import datetime, date

from config import (
    RIVALRIES, PLAYOFF_REMATCHES, MARQUEE_PITCHERS,
    TIMING_FILTER_SECONDS,
    NBA_PLAYOFF_RANK_CUTOFF, NBA_PLAYIN_RANK_CUTOFF,
)
from models import RawEvent, TeamContext, ScoredEvent


def apply_timing_filter(
    events: list[RawEvent],
    now: datetime,
) -> tuple[list[RawEvent], list[tuple[RawEvent, str]]]:
    """
    Exclude events already started or starting within 1 hour.
    Returns (included, excluded_with_reason).
    """
    included = []
    excluded = []

    for ev in events:
        seconds_until = (ev.game_time_utc - now).total_seconds()
        if seconds_until < TIMING_FILTER_SECONDS:
            if seconds_until < 0:
                reason = "already started"
            else:
                mins = int(seconds_until // 60)
                reason = f"starts in <1hr ({mins}min)"
            excluded.append((ev, reason))
        else:
            included.append(ev)

    return included, excluded


def get_timing_label(ev: RawEvent, generation_date: date) -> str:
    """Return 'TONIGHT' (same day) or 'Weekday, Month Day'."""
    if ev.game_date == generation_date:
        return "TONIGHT"
    return ev.game_date.strftime("%A, %B %-d")


def detect_flags(
    ev: RawEvent,
    home_ctx: TeamContext,
    away_ctx: TeamContext,
) -> list[str]:
    """
    Detect narrative flags for an event.
    Tier 1: elimination_game (20 pts, no stacking)
    Tier 2: rivalry, playoff_rematch, first_place_clash (stackable, capped at 12)
    """
    flags: list[str] = []

    sport    = ev.sport
    home_key = f"{sport}:{home_ctx.abbr}"
    away_key = f"{sport}:{away_ctx.abbr}"
    pair     = frozenset({home_key, away_key})

    # --- Tier 1: elimination_game ---
    if ev.is_postseason and sport == "NBA":
        # Explicit play-in flag (ESPN season.type == 5) is the primary signal.
        if ev.is_playin:
            flags.append("elimination_game")
        else:
            # Fallback: infer from seed range if explicit flag is absent.
            # BOTH teams must be seeds 7–10 — a 2v7 playoff series is not play-in.
            home_rank = home_ctx.conference_rank or 99
            away_rank = away_ctx.conference_rank or 99
            if (NBA_PLAYOFF_RANK_CUTOFF < home_rank <= NBA_PLAYIN_RANK_CUTOFF and
                    NBA_PLAYOFF_RANK_CUTOFF < away_rank <= NBA_PLAYIN_RANK_CUTOFF):
                flags.append("elimination_game")

    # --- Tier 2 (only if Tier 1 not set) ---
    if "elimination_game" not in flags:
        if pair in RIVALRIES:
            flags.append("rivalry")

        if pair in PLAYOFF_REMATCHES:
            flags.append("playoff_rematch")

        if _is_first_place_clash(home_ctx, away_ctx):
            flags.append("first_place_clash")

        # ace_duel — MLB only; fires when BOTH probable starters are in MARQUEE_PITCHERS
        if ev.sport == "MLB":
            home_p = ev.home_probable_pitcher
            away_p = ev.away_probable_pitcher
            if home_p and away_p and MARQUEE_PITCHERS.get(home_p) and MARQUEE_PITCHERS.get(away_p):
                flags.append("ace_duel")

        # marquee_starter — MLB only; fires when exactly one starter is marquee
        # (ace_duel already handles the both-marquee case)
        if ev.sport == "MLB" and "ace_duel" not in flags:
            home_p = ev.home_probable_pitcher
            away_p = ev.away_probable_pitcher
            home_is_marquee = bool(home_p and MARQUEE_PITCHERS.get(home_p))
            away_is_marquee = bool(away_p and MARQUEE_PITCHERS.get(away_p))
            if home_is_marquee or away_is_marquee:
                flags.append("marquee_starter")

    return flags


def _is_first_place_clash(home: TeamContext, away: TeamContext) -> bool:
    """True if both teams are in or within 1 game of first place."""
    if home.sport == "MLB":
        home_gb = home.games_back if home.games_back is not None else 0.0
        away_gb = away.games_back if away.games_back is not None else 0.0
        return home_gb <= 1.0 and away_gb <= 1.0
    else:  # NBA
        home_rank = home.conference_rank or 99
        away_rank = away.conference_rank or 99
        return home_rank <= 2 and away_rank <= 2


def build_scored_event(
    ev: RawEvent,
    home_ctx: TeamContext,
    away_ctx: TeamContext,
    generation_date: date,
) -> ScoredEvent:
    """Build a ScoredEvent shell — scores populated later by score.py."""
    flags        = detect_flags(ev, home_ctx, away_ctx)
    timing_label = get_timing_label(ev, generation_date)

    return ScoredEvent(
        raw=ev,
        home_ctx=home_ctx,
        away_ctx=away_ctx,
        flags=flags,
        timing_label=timing_label,
    )


def enrich_events(
    events: list[RawEvent],
    team_contexts: dict[str, TeamContext],
    generation_date: date,
    now: datetime,
) -> tuple[list[ScoredEvent], list[tuple[RawEvent, str]]]:
    """
    Full enrichment pipeline:
    1. Apply timing filter
    2. Look up team contexts (keyed by "SPORT:ABBR")
    3. Detect flags + build ScoredEvent shells
    Returns (enriched_events, excluded_with_reasons).
    """
    included, excluded = apply_timing_filter(events, now)

    result: list[ScoredEvent] = []
    for ev in included:
        home_ctx = team_contexts.get(f"{ev.sport}:{ev.home_abbr}")
        away_ctx = team_contexts.get(f"{ev.sport}:{ev.away_abbr}")

        if not home_ctx or not away_ctx:
            missing = []
            if not home_ctx:
                missing.append(ev.home_abbr)
            if not away_ctx:
                missing.append(ev.away_abbr)
            excluded.append((ev, f"missing team context: {', '.join(missing)}"))
            continue

        se = build_scored_event(ev, home_ctx, away_ctx, generation_date)
        result.append(se)

    return result, excluded
