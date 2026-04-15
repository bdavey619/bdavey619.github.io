"""
run.py — Must Watch This Week entrypoint.

Usage:
  python run.py --dry-run
  python run.py --dry-run --date 2026-04-14
"""

import argparse
import sys
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import TOP_N_CANDIDATES
from mlb import fetch_week as fetch_mlb
from nba import fetch_week as fetch_nba
from enrich import enrich_events
from score import score_event
from rank import rank_events
from models import ScoredEvent, TeamContext


# ---------------------------------------------------------------------------
# Week range
# ---------------------------------------------------------------------------

def week_range(from_date: date) -> tuple[date, date]:
    """Return (monday, sunday) for the week containing from_date."""
    monday = from_date - timedelta(days=from_date.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _record(ctx: TeamContext) -> str:
    return f"{ctx.wins}-{ctx.losses}"


def _l10(ctx: TeamContext) -> str:
    return f"{ctx.l10_wins}-{ctx.l10_losses}"


def _streak(ctx: TeamContext) -> str:
    if ctx.streak_n == 0:
        return "-"
    return f"{ctx.streak_type}{ctx.streak_n}"


def _gb(ctx: TeamContext) -> str:
    if ctx.sport != "MLB":
        return ""
    if ctx.games_back is None:
        return "1st"
    return f"{ctx.games_back:.1f} GB"


def _conf_rank(ctx: TeamContext) -> str:
    if ctx.sport != "NBA" or ctx.conference_rank is None:
        return ""
    return f"#{ctx.conference_rank} {ctx.conference or ''}"


# ---------------------------------------------------------------------------
# Dry-run output
# ---------------------------------------------------------------------------

SEP  = "=" * 72
LINE = "-" * 72


def print_dry_run(
    week_start: date,
    week_end: date,
    generation_dt: datetime,
    total_fetched: int,
    excluded: list,
    ranked: list[ScoredEvent],
) -> None:
    print(SEP)
    print("  MUST WATCH THIS WEEK — DRY RUN")
    print(SEP)
    print(f"  Generated : {generation_dt.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Week      : {week_start.strftime('%b %-d')} – {week_end.strftime('%b %-d, %Y')}")
    print(f"  Fetched   : {total_fetched} total events")
    print(f"  Excluded  : {len(excluded)} events")
    print()

    # --- Exclusion summary ---
    if excluded:
        print("  EXCLUDED")
        print(LINE)

        started = missing = soon = 0
        for ev, reason in excluded:
            if "already started" in reason:
                started += 1
            elif "<1hr" in reason:
                soon += 1
            elif "missing" in reason:
                missing += 1

        if started: print(f"  Already started         : {started:3d}")
        if soon:    print(f"  Starting <1hr           : {soon:3d}")
        if missing: print(f"  Missing team context    : {missing:3d}")

        other = len(excluded) - started - soon - missing
        if other:   print(f"  Other                   : {other:3d}")
        print()

    # --- Ranked candidates ---
    print(f"  TOP {len(ranked)} CANDIDATES")
    print(SEP)
    print()

    for i, se in enumerate(ranked, start=1):
        home = se.home_ctx
        away = se.away_ctx
        ev   = se.raw

        matchup   = f"{away.name} @ {home.name}"
        sport_tag = f"[{ev.sport}]"

        print(f"  #{i:<2d} {matchup:<44s} {sport_tag}  score: {se.total_score:.1f}")
        print(f"       {se.timing_label}")
        if ev.venue:
            print(f"       {ev.venue}")
        print()

        # Team info rows
        for ctx, label in ((away, "Away"), (home, "Home")):
            rec     = _record(ctx)
            l10_str = _l10(ctx)
            stk     = _streak(ctx)
            extra   = _gb(ctx) or _conf_rank(ctx)
            extra_s = f"  {extra}" if extra else ""
            print(f"       {label}  {ctx.name:<26s}  {rec:<7s}  L10: {l10_str}  Streak: {stk}{extra_s}")
        print()

        # Score breakdown
        print(f"       SCORE BREAKDOWN  (total: {se.total_score:.1f} / 100)")
        print(f"         Stakes         : {se.stakes_score:5.1f} / 30   {se.stakes_detail}")
        print(f"         Balance        : {se.competitive_balance_score:5.1f} / 20")
        print(f"         Momentum       : {se.momentum_score:5.1f} / 15")
        print(f"         Star Power     : {se.star_power_score:5.1f} / 15   {se.star_power_detail}")
        print(f"         Narrative      : {se.narrative_flags_score:5.1f} / 20")
        print()

        # Flags
        flag_str = ", ".join(se.flags) if se.flags else "none"
        print(f"       FLAGS: {flag_str}")
        print()
        print(LINE)
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Must Watch This Week")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch data, score events, print ranked output")
    parser.add_argument("--date",
                        help="Override generation date YYYY-MM-DD (default: today ET)")
    args = parser.parse_args()

    if not args.dry_run:
        print("Pass --dry-run to see ranked output.")
        sys.exit(0)

    now = datetime.now(timezone.utc)

    if args.date:
        gen_date = date.fromisoformat(args.date)
    else:
        et_offset = timezone(timedelta(hours=-4))
        gen_date  = now.astimezone(et_offset).date()

    week_start, week_end = week_range(gen_date)

    print(f"\nFetching data for {week_start} – {week_end}...", file=sys.stderr)
    print("", file=sys.stderr)

    # --- Fetch ---
    mlb_events, mlb_contexts = fetch_mlb(week_start, week_end)
    nba_events, nba_contexts = fetch_nba(week_start, week_end)

    all_events   = mlb_events + nba_events
    all_contexts = {**mlb_contexts, **nba_contexts}   # no key collisions: "MLB:X" vs "NBA:X"

    total_fetched = len(all_events)
    print(f"\nTotal fetched: {total_fetched} events", file=sys.stderr)

    # --- Enrich + filter ---
    scored_events, excluded = enrich_events(all_events, all_contexts, gen_date, now)
    print(f"After timing filter: {len(scored_events)} remaining, {len(excluded)} excluded",
          file=sys.stderr)

    if not scored_events:
        print("\nNo upcoming events found after filtering.", file=sys.stderr)
        sys.exit(0)

    # --- Score ---
    for se in scored_events:
        score_event(se)

    # --- Rank ---
    ranked = rank_events(scored_events)

    # --- Print ---
    print("", file=sys.stderr)
    print_dry_run(week_start, week_end, now, total_fetched, excluded, ranked)


if __name__ == "__main__":
    main()
