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
from editorial import editorial_review, print_override_summary, print_final_five
from explain import generate_explanations
from render import render_weekly


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

SEP      = "=" * 72
LINE     = "-" * 72
DIAG_SEP = "=" * 80
DIAG_LINE= "-" * 80


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

        # Probable pitchers (MLB only)
        if ev.sport == "MLB" and (ev.away_probable_pitcher or ev.home_probable_pitcher):
            ap = ev.away_probable_pitcher or "TBD"
            hp = ev.home_probable_pitcher or "TBD"
            print(f"       Pitchers: {ap} (away) vs {hp} (home)")
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
# Diagnostics output
# ---------------------------------------------------------------------------

def print_diagnostics(
    week_start: date,
    week_end: date,
    generation_dt: datetime,
    ranked: list[ScoredEvent],
) -> None:
    """
    Compact, at-a-glance ranking diagnostics.

    Answers:
      - Why is X ranked here?
      - Why is MLB absent from the top 5?
      - Was it a near miss or nowhere close?
      - Is this a genuinely NBA-heavy week, or is the model miscalibrated?
    """
    cutoff = 5   # top-N displayed as "above the line"

    print(DIAG_SEP)
    print("  MUST WATCH — RANKING DIAGNOSTICS")
    print(DIAG_SEP)
    print(f"  Generated : {generation_dt.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Week      : {week_start.strftime('%b %-d')} – {week_end.strftime('%b %-d, %Y')}")
    print(f"  Candidates: {len(ranked)}")
    print()

    # ── Ranked table ──────────────────────────────────────────────────────
    # Column header
    print(f"  {'RK':<4}  {'SPT':<3}  {'MATCHUP':<38}  {'TOT':>5}  {'STK':>5}  {'BAL':>5}  {'MOM':>5}  {'STR':>5}  {'NAR':>5}")
    print("  " + "─" * 78)

    cutoff_score = ranked[cutoff - 1].total_score if len(ranked) >= cutoff else None

    for i, se in enumerate(ranked, start=1):
        if i == cutoff + 1:
            # Visual top-5 cutoff marker
            print()
            print("  " + "─" * 18 + f"  TOP {cutoff} CUTOFF  " + "─" * 18)
            print()

        ev   = se.raw
        home = se.home_ctx
        away = se.away_ctx

        matchup = f"{away.abbr} @ {home.abbr}"
        matchup_long = f"{away.name} @ {home.name}"
        if len(matchup_long) <= 38:
            matchup = matchup_long

        near_miss = ""
        if i > cutoff and cutoff_score is not None:
            gap = cutoff_score - se.total_score
            if gap < 5.0:
                near_miss = f"  ◄ {gap:.1f} pts off"

        print(
            f"  #{i:<3d}  {ev.sport:<3}  {matchup:<38}"
            f"  {se.total_score:>5.1f}"
            f"  {se.stakes_score:>5.1f}"
            f"  {se.competitive_balance_score:>5.1f}"
            f"  {se.momentum_score:>5.1f}"
            f"  {se.star_power_score:>5.1f}"
            f"  {se.narrative_flags_score:>5.1f}"
            f"{near_miss}"
        )

        # Flags + probable pitchers on a detail line
        flag_str = ", ".join(se.flags) if se.flags else "none"
        pitcher_str = ""
        if ev.sport == "MLB" and (ev.away_probable_pitcher or ev.home_probable_pitcher):
            ap = ev.away_probable_pitcher or "TBD"
            hp = ev.home_probable_pitcher or "TBD"
            pitcher_str = f"   ⚾ {ap} vs {hp}"
        print(f"         flags: {flag_str}{pitcher_str}")
        print()

    # ── Sport leaders ─────────────────────────────────────────────────────
    print(DIAG_LINE)
    print("  SPORT LEADERS")
    print()

    sport_leaders: dict[str, tuple[int, ScoredEvent]] = {}
    for i, se in enumerate(ranked, start=1):
        s = se.raw.sport
        if s not in sport_leaders:
            sport_leaders[s] = (i, se)

    for sport in sorted(sport_leaders):
        rank, se = sport_leaders[sport]
        matchup = f"{se.raw.away_name} @ {se.raw.home_name}"
        flag_str = ", ".join(se.flags) if se.flags else "—"
        status = "✓ in top 5" if rank <= cutoff else f"✗ outside top 5"
        print(f"  {sport}  #{rank:<3d}  {matchup}")
        print(f"         score: {se.total_score:.1f}   {status}")
        print(f"         flags: {flag_str}")
        print()

    # ── MLB analysis ──────────────────────────────────────────────────────
    if "MLB" in sport_leaders and len(ranked) >= cutoff:
        mlb_rank, mlb_top = sport_leaders["MLB"]
        print(DIAG_LINE)
        print("  MLB ANALYSIS")
        print()

        if mlb_rank <= cutoff:
            print(f"  MLB top game is #{mlb_rank} — present in top {cutoff}. No concerns.")
        else:
            cutoff_score = ranked[cutoff - 1].total_score
            gap = cutoff_score - mlb_top.total_score
            near = "(NEAR MISS — within 5 pts)" if gap < 5.0 else "(well outside — likely a thin week for MLB)"

            print(f"  Top MLB game is #{mlb_rank} — outside top {cutoff}.")
            print(f"  Gap from #{cutoff}: {gap:+.1f} pts  {near}")
            print()

            # Average stakes comparison
            mlb_events = [se for se in ranked if se.raw.sport == "MLB"]
            top5_nba   = [se for se in ranked[:cutoff] if se.raw.sport == "NBA"]

            if mlb_events:
                avg_mlb_stakes = sum(se.stakes_score for se in mlb_events) / len(mlb_events)
                print(f"  Avg stakes (all MLB in pool)     : {avg_mlb_stakes:.1f}")
            if top5_nba:
                avg_nba_stakes = sum(se.stakes_score for se in top5_nba) / len(top5_nba)
                print(f"  Avg stakes (top-{cutoff} NBA games)     : {avg_nba_stakes:.1f}")
            print()

            # Top MLB game detail
            home = mlb_top.home_ctx
            away = mlb_top.away_ctx
            print(f"  Top MLB: {away.name} @ {home.name}  (#{mlb_rank}, score {mlb_top.total_score:.1f})")
            print(f"    Stakes   : {mlb_top.stakes_score:.1f}  ({mlb_top.stakes_detail})")
            print(f"    Balance  : {mlb_top.competitive_balance_score:.1f}"
                  f"   Momentum : {mlb_top.momentum_score:.1f}"
                  f"   Star     : {mlb_top.star_power_score:.1f}   ({mlb_top.star_power_detail})")
            print(f"    Narrative: {mlb_top.narrative_flags_score:.1f}   flags: {', '.join(mlb_top.flags) or 'none'}")
            if mlb_top.raw.away_probable_pitcher or mlb_top.raw.home_probable_pitcher:
                ap = mlb_top.raw.away_probable_pitcher or "TBD"
                hp = mlb_top.raw.home_probable_pitcher or "TBD"
                print(f"    Pitchers : {ap} (away) vs {hp} (home)")

        print()

    print(DIAG_SEP)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Must Watch This Week")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch data, score events, print full ranked output")
    parser.add_argument("--diag", action="store_true",
                        help="Compact diagnostics view: table + sport leaders + MLB analysis")
    parser.add_argument("--date",
                        help="Override generation date YYYY-MM-DD (default: today ET)")
    args = parser.parse_args()

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

    # --- Output ---
    print("", file=sys.stderr)

    if args.dry_run:
        # Full detailed view — one event per block with team rows and breakdown
        print_dry_run(week_start, week_end, now, total_fetched, excluded, ranked)
    elif args.diag:
        # Compact diagnostics table — sport leaders + MLB analysis
        print_diagnostics(week_start, week_end, now, ranked)
    else:
        # Interactive editorial path
        final, override_info = editorial_review(ranked)

        print("\nGenerating explanations...", file=sys.stderr)
        explanations = generate_explanations(final)

        print_override_summary(override_info)
        print_final_five(final, explanations)

        output_path = render_weekly(final, explanations, week_start, week_end, now, candidates=ranked)
        print(f"\n✓  HTML written to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
