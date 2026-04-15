"""
models.py — Frozen dataclasses for Must Watch This Week.

Data shapes only — no logic.
"""

from dataclasses import dataclass, field
from datetime import datetime, date


@dataclass(frozen=True)
class TeamContext:
    """Enriched team data used for scoring."""
    abbr: str               # Team abbreviation (as returned by API)
    name: str               # Display name
    sport: str              # "MLB" or "NBA"
    wins: int
    losses: int
    win_pct: float
    l10_wins: int
    l10_losses: int
    streak_type: str        # "W" or "L"
    streak_n: int
    games_played: int       # For season-phase multiplier

    # MLB-specific (None for NBA)
    division_rank: int | None   = None
    games_back: float | None    = None      # From division leader; None = first place
    wild_card_rank: int | None  = None
    wc_games_back: float | None = None      # From last wild card spot; None = in WC

    # NBA-specific (None for MLB)
    conference: str | None      = None      # "East" or "West"
    conference_rank: int | None = None      # 1 = best in conference


@dataclass(frozen=True)
class RawEvent:
    """Normalized game event before scoring."""
    game_id: str
    sport: str              # "MLB" or "NBA"
    home_abbr: str
    away_abbr: str
    home_name: str
    away_name: str
    game_time_utc: datetime
    game_date: date         # Local date in ET
    venue: str
    is_postseason: bool = False   # playoffs OR play-in
    is_playin: bool     = False   # explicit NBA play-in (ESPN season.type == 5)


@dataclass
class ScoredEvent:
    """Event after enrichment and scoring."""
    raw: RawEvent
    home_ctx: TeamContext
    away_ctx: TeamContext

    # Score components
    stakes_score:              float = 0.0
    competitive_balance_score: float = 0.0
    momentum_score:            float = 0.0
    star_power_score:          float = 0.0
    narrative_flags_score:     float = 0.0
    total_score:               float = 0.0

    # Narrative flags
    flags: list[str] = field(default_factory=list)

    # Display
    timing_label: str = ""

    # Transparency
    stakes_detail:     str = ""
    star_power_detail: str = ""
