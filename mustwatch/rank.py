"""
rank.py — Deduplicate series games, sort, and select top-N candidates.
"""

from config import TOP_N_CANDIDATES
from models import ScoredEvent


def _series_key(se: ScoredEvent) -> frozenset:
    """Unique key for a matchup — same regardless of home/away ordering."""
    return frozenset({
        f"{se.raw.sport}:{se.raw.home_abbr}",
        f"{se.raw.sport}:{se.raw.away_abbr}",
    })


def deduplicate_series(events: list[ScoredEvent]) -> list[ScoredEvent]:
    """
    Keep only the best-scored game per matchup.
    Same-series games have identical scores; we keep the earliest one by date.
    """
    seen: dict[frozenset, ScoredEvent] = {}
    for se in sorted(events, key=lambda e: (e.raw.game_date, e.raw.game_time_utc)):
        key = _series_key(se)
        if key not in seen:
            seen[key] = se
        elif se.total_score > seen[key].total_score:
            seen[key] = se
    return list(seen.values())


def rank_events(events: list[ScoredEvent], top_n: int = TOP_N_CANDIDATES) -> list[ScoredEvent]:
    """Deduplicate by matchup, sort by total_score descending, return top_n."""
    unique = deduplicate_series(events)
    return sorted(unique, key=lambda e: e.total_score, reverse=True)[:top_n]
