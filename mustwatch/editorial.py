"""
editorial.py — Interactive editorial review for Must Watch This Week.

Displays the top-N scored candidates and lets the editor either accept the
default top-5 or enter a custom ordering by picking slot numbers.

Public API
----------
    show_candidates(ranked)           → prints the review table
    editorial_review(ranked)          → prompts, returns (final_5, override_info)
"""

from __future__ import annotations

import sys
from models import ScoredEvent


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOP_N_FINAL   = 5
SEP  = "=" * 72
LINE = "-" * 72


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _short_label(se: ScoredEvent) -> str:
    """One-line game description for the review table."""
    ev   = se.raw
    home = se.home_ctx
    away = se.away_ctx
    day  = ev.game_date.strftime("%a %b %-d")
    return f"{away.name} @ {home.name}  ({day})"


def show_candidates(ranked: list[ScoredEvent]) -> None:
    """Print a compact numbered table of all candidates."""
    print()
    print(SEP)
    print(f"  EDITORIAL REVIEW — TOP {len(ranked)} CANDIDATES")
    print(SEP)
    print(f"  {'#':<4}  {'Sport':<5}  {'Score':>5}   {'Matchup'}")
    print(LINE)
    for i, se in enumerate(ranked, start=1):
        sport = se.raw.sport
        score = f"{se.total_score:.1f}"
        label = _short_label(se)
        flag_str = ""
        if se.flags:
            flag_str = "  [" + ", ".join(se.flags) + "]"
        print(f"  {i:<4}  {sport:<5}  {score:>5}   {label}{flag_str}")
    print(LINE)
    print()


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

def _read_line(prompt: str) -> str:
    """Read a line from stdin, handling EOF gracefully."""
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)


def _parse_selection(raw: str, max_n: int) -> list[int] | None:
    """
    Parse a space-separated list of candidate numbers.
    Returns a list of zero-based indices, or None if invalid.

    Accepts: "1 3 2 7 4"  →  [0, 2, 1, 6, 3]
    """
    parts = raw.split()
    if len(parts) != TOP_N_FINAL:
        return None
    indices = []
    for p in parts:
        if not p.isdigit():
            return None
        n = int(p)
        if n < 1 or n > max_n:
            return None
        zero = n - 1
        if zero in indices:
            return None   # duplicate
        indices.append(zero)
    return indices


# ---------------------------------------------------------------------------
# Main editorial flow
# ---------------------------------------------------------------------------

def editorial_review(
    ranked: list[ScoredEvent],
) -> tuple[list[ScoredEvent], dict]:
    """
    Show the review table and prompt for editorial input.

    Returns
    -------
    final : list[ScoredEvent]
        Exactly TOP_N_FINAL events in the editor-approved order.
    override_info : dict
        Records how the final list was produced:
          {
            "mode":           "accepted" | "custom",
            "selected_ranks": [1, 2, 3, 4, 5],   # 1-based positions in input
          }
    """
    show_candidates(ranked)

    n = len(ranked)
    default_ranks = list(range(1, TOP_N_FINAL + 1))

    print(f"  Default top {TOP_N_FINAL}: {' '.join(str(r) for r in default_ranks)}")
    print()
    print(f"  Press ENTER to accept, or type {TOP_N_FINAL} numbers from the list above")
    print(f"  (e.g. \"1 3 2 7 4\" to pick those slots in that order)")
    print()

    while True:
        raw = _read_line("  Your selection: ")

        # Accept default
        if raw == "" or raw.lower() in ("y", "yes"):
            selected_ranks = default_ranks
            mode = "accepted"
            break

        # Parse custom selection
        indices = _parse_selection(raw, n)
        if indices is None:
            print(f"  Invalid — enter exactly {TOP_N_FINAL} unique numbers "
                  f"between 1 and {n}, space-separated.")
            continue

        selected_ranks = [i + 1 for i in indices]   # convert back to 1-based for the record
        mode = "custom"
        break

    final = [ranked[r - 1] for r in selected_ranks]
    override_info = {
        "mode":           mode,
        "selected_ranks": selected_ranks,
    }
    return final, override_info


# ---------------------------------------------------------------------------
# Override summary (printed by run.py after review)
# ---------------------------------------------------------------------------

def print_override_summary(override_info: dict) -> None:
    mode   = override_info["mode"]
    ranks  = override_info["selected_ranks"]

    print()
    print(SEP)
    print("  EDITORIAL OVERRIDE STATE")
    print(SEP)
    if mode == "accepted":
        print("  Mode   : accepted (default top 5)")
    else:
        print("  Mode   : custom")
        print(f"  Order  : {' → '.join(f'#{r}' for r in ranks)}")
    print(LINE)


# ---------------------------------------------------------------------------
# Final top-5 display
# ---------------------------------------------------------------------------

def print_final_five(
    final: list[ScoredEvent],
    explanations: list[str] | None = None,
) -> None:
    """
    Print the approved top-5 list.

    If `explanations` is provided it must be the same length as `final`;
    each explanation is printed beneath its event header.
    """
    print()
    print(SEP)
    print("  MUST WATCH THIS WEEK — FINAL TOP 5")
    print(SEP)
    for i, se in enumerate(final, start=1):
        ev   = se.raw
        home = se.home_ctx
        away = se.away_ctx
        day  = ev.game_date.strftime("%a %b %-d")
        flags_str = ""
        if se.flags:
            flags_str = "  [" + ", ".join(se.flags) + "]"
        print(f"  #{i}  [{ev.sport}]  {away.name} @ {home.name}")
        print(f"       {day}  •  score: {se.total_score:.1f}{flags_str}")
        if ev.venue:
            print(f"       {ev.venue}")
        if explanations and i - 1 < len(explanations):
            # Indent each sentence of the explanation for readability
            for line in explanations[i - 1].splitlines():
                print(f"       {line}")
        print()
    print(LINE)
    print()
