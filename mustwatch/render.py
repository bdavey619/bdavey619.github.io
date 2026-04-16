"""
render.py — HTML rendering for Must Watch This Week.

Takes the final top-5 ScoredEvent list + explanations, injects them into
templates/weekly.html using simple {{key}} replacement, and writes the result
to mustwatch/weekly.html.

Public API
----------
    render_weekly(
        final:        list[ScoredEvent],
        explanations: list[str],
        week_start:   date,
        week_end:     date,
        generated_at: datetime,
    ) -> Path
        Returns the path of the written file.
"""

from __future__ import annotations

import html
from datetime import date, datetime
from pathlib import Path
from models import ScoredEvent

_DIR       = Path(__file__).parent
_TEMPLATE  = _DIR / "templates" / "weekly.html"
_OUTPUT    = _DIR / "weekly.html"

# Human-readable flag labels (shown as small badges on each card)
_FLAG_LABELS = {
    "rivalry":           "Rivalry",
    "playoff_rematch":   "Playoff Rematch",
    "first_place_clash": "First Place",
    "elimination_game":  "Elimination",
}


# ---------------------------------------------------------------------------
# Event block builder
# ---------------------------------------------------------------------------

def _esc(value: str) -> str:
    """HTML-escape a string."""
    return html.escape(str(value), quote=True)


def _render_flags(flags: list[str]) -> str:
    if not flags:
        return ""
    items = "".join(
        f'<span class="flag">{_esc(_FLAG_LABELS.get(f, f))}</span>'
        for f in flags
    )
    return f'<div class="flags">{items}</div>'


def _render_breakdown(se: ScoredEvent) -> str:
    items = [
        ("Stakes",   se.stakes_score,              30),
        ("Balance",  se.competitive_balance_score, 20),
        ("Momentum", se.momentum_score,             15),
        ("Stars",    se.star_power_score,           15),
        ("Narrative",se.narrative_flags_score,      20),
    ]
    cells = []
    for label, value, max_val in items:
        cells.append(
            f'<div class="breakdown-item">'
            f'<span class="breakdown-label">{label}</span>'
            f'<span class="breakdown-value">{round(value)}</span>'
            f'<span class="breakdown-max">/{max_val}</span>'
            f'</div>'
        )
    return '<div class="breakdown">' + "".join(cells) + "</div>"


def _render_event(rank: int, se: ScoredEvent, explanation: str) -> str:
    ev       = se.raw
    matchup  = _esc(f"{ev.away_name} @ {ev.home_name}")
    sport    = _esc(ev.sport)
    timing   = _esc(se.timing_label)
    venue    = _esc(ev.venue) if ev.venue else ""
    total    = round(se.total_score)

    # Detail line: timing · venue (venue only if available)
    detail_inner = (
        f'<span class="sport-tag">{sport}</span>'
        f'<span>{timing}</span>'
    )
    if venue:
        detail_inner += f'<span class="detail-sep">·</span><span>{venue}</span>'

    flags_html     = _render_flags(se.flags)
    breakdown_html = _render_breakdown(se)
    expl_html      = _esc(explanation)

    return (
        f'<div class="event">\n'
        f'  <div class="event-top">\n'
        f'    <div class="rank">#{rank}</div>\n'
        f'    <div class="event-identity">\n'
        f'      <div class="matchup">{matchup}</div>\n'
        f'      <div class="event-detail">{detail_inner}</div>\n'
        f'    </div>\n'
        f'    <div class="score-badge">{total}/100</div>\n'
        f'  </div>\n'
        f'  {flags_html}\n'
        f'  <p class="explanation">{expl_html}</p>\n'
        f'  {breakdown_html}\n'
        f'</div>\n'
    )


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

def _render(template_path: Path, context: dict) -> str:
    """Replace {{key}} placeholders. No external dependencies."""
    text = template_path.read_text()
    for key, value in context.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_weekly(
    final:        list[ScoredEvent],
    explanations: dict[str, str],
    week_start:   date,
    week_end:     date,
    generated_at: datetime,
) -> Path:
    """
    Render the final top-5 list to mustwatch/weekly.html.

    Parameters
    ----------
    final        : list[ScoredEvent]  — exactly 5, in display order
    explanations : dict[str, str]     — game_id → explanation text
    week_start   : date               — Monday of the ranking week
    week_end     : date               — Sunday of the ranking week
    generated_at : datetime           — generation timestamp (UTC)

    Returns
    -------
    Path to the written file.
    """
    events_html = "\n".join(
        _render_event(i + 1, se, explanations.get(se.raw.game_id, ""))
        for i, se in enumerate(final)
    )

    week_label = (
        f"Week of {week_start.strftime('%B %-d')}–"
        f"{week_end.strftime('%-d, %Y')}"
    )
    generated_str = generated_at.strftime("%B %-d, %Y")

    context = {
        "week_label":   week_label,
        "events_html":  events_html,
        "generated_at": generated_str,
    }

    html_out = _render(_TEMPLATE, context)
    _OUTPUT.write_text(html_out)
    return _OUTPUT
