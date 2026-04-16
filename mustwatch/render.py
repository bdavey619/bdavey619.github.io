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
_OUTPUT    = _DIR / "index.html"

# Human-readable flag labels (shown as small badges on each card)
_FLAG_LABELS = {
    "rivalry":           "Rivalry",
    "playoff_rematch":   "Playoff Rematch",
    "first_place_clash": "First Place",
    "elimination_game":  "Elimination",
    "ace_duel":          "Ace Duel",
    "marquee_starter":   "Marquee Starter",
}

# Short labels for diagnostics table
_DIAG_FLAG_SHORT = {
    "rivalry":           "rivalry",
    "playoff_rematch":   "pl-rematch",
    "first_place_clash": "1st-place",
    "elimination_game":  "elimination",
    "ace_duel":          "ace-duel",
    "marquee_starter":   "mq-starter",
}

_TOP_N = 5


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
# Diagnostics section
# ---------------------------------------------------------------------------

def _diag_table(candidates: list[ScoredEvent]) -> str:
    cutoff_score = (
        candidates[_TOP_N - 1].total_score if len(candidates) >= _TOP_N else None
    )

    rows: list[str] = []
    for i, se in enumerate(candidates, start=1):
        ev = se.raw

        near = ""
        if i > _TOP_N and cutoff_score is not None:
            gap = cutoff_score - se.total_score
            if gap < 5.0:
                near = f'<span class="diag-near">&#9650;{gap:.1f}</span>'

        flag_parts = [
            f'<span class="diag-flag">{_esc(_DIAG_FLAG_SHORT.get(f, f))}</span>'
            for f in se.flags
        ]
        if ev.sport == "MLB" and (ev.away_probable_pitcher or ev.home_probable_pitcher):
            ap = _esc(ev.away_probable_pitcher or "TBD")
            hp = _esc(ev.home_probable_pitcher or "TBD")
            flag_parts.append(f'<span class="diag-pitchers">{ap} vs {hp}</span>')
        flags_html = " ".join(flag_parts)

        row_cls = "diag-row " + ("diag-above" if i <= _TOP_N else "diag-below")
        sport_esc = _esc(ev.sport)

        rows.append(
            f'<tr class="{row_cls}" data-sport="{sport_esc}">'
            f'<td class="diag-rk">#{i}</td>'
            f'<td class="diag-sport">{sport_esc}</td>'
            f'<td class="diag-matchup">{_esc(ev.away_name)} @ {_esc(ev.home_name)}</td>'
            f'<td class="dn">{round(se.total_score)}{near}</td>'
            f'<td class="dn">{round(se.stakes_score)}</td>'
            f'<td class="dn">{round(se.competitive_balance_score)}</td>'
            f'<td class="dn">{round(se.momentum_score)}</td>'
            f'<td class="dn">{round(se.star_power_score)}</td>'
            f'<td class="dn">{round(se.narrative_flags_score)}</td>'
            f'<td class="diag-flags-cell">{flags_html}</td>'
            f'</tr>'
        )

        if i == _TOP_N and len(candidates) > _TOP_N:
            rows.append(
                '<tr class="diag-cut-row">'
                '<td colspan="10">&#9660; below top 5</td>'
                '</tr>'
            )

    return (
        '<div class="diag-tbl-wrap">'
        '<table class="diag-tbl">'
        '<thead><tr>'
        '<th>RK</th><th>SPT</th><th>Matchup</th>'
        '<th>Tot</th><th>Stk</th><th>Bal</th>'
        '<th>Mom</th><th>Str</th><th>Nar</th>'
        '<th>Flags / Pitchers</th>'
        '</tr></thead>'
        '<tbody>' + "".join(rows) + '</tbody>'
        '</table></div>'
    )


def _diag_sport_leaders(candidates: list[ScoredEvent]) -> str:
    leaders: dict[str, tuple[int, ScoredEvent]] = {}
    for i, se in enumerate(candidates, start=1):
        s = se.raw.sport
        if s not in leaders:
            leaders[s] = (i, se)

    if not leaders:
        return ""

    items: list[str] = []
    for sport in sorted(leaders):
        rank_i, se = leaders[sport]
        matchup = f"{se.raw.away_name} @ {se.raw.home_name}"
        in_top = rank_i <= _TOP_N
        status_cls = "diag-in" if in_top else "diag-out"
        status = f"#{rank_i} · in top 5" if in_top else f"#{rank_i} · outside top 5"
        items.append(
            f'<div class="diag-leader">'
            f'<span class="diag-leader-spt">{_esc(sport)}</span>'
            f'<span class="diag-leader-game">{_esc(matchup)}</span>'
            f'<span class="diag-leader-score">{round(se.total_score)}/100</span>'
            f'<span class="{status_cls}">{_esc(status)}</span>'
            f'</div>'
        )

    return (
        '<div class="diag-leaders">'
        '<div class="diag-lbl">Highest by sport</div>'
        + "".join(items)
        + '</div>'
    )


def _diag_mlb_analysis(candidates: list[ScoredEvent]) -> str:
    if len(candidates) < _TOP_N:
        return ""

    mlb = [(i + 1, se) for i, se in enumerate(candidates) if se.raw.sport == "MLB"]

    if not mlb:
        return (
            '<div class="diag-mlb">'
            '<div class="diag-lbl">MLB analysis</div>'
            '<div class="diag-mlb-note">No MLB events in candidate pool.</div>'
            '</div>'
        )

    mlb_rank, mlb_top = mlb[0]
    if mlb_rank <= _TOP_N:
        return ""  # MLB in top 5 — no concern

    cutoff_score = candidates[_TOP_N - 1].total_score
    gap = cutoff_score - mlb_top.total_score
    near_str = "near miss (within 5 pts)" if gap < 5.0 else "well outside — thin MLB week"

    all_mlb = [se for _, se in mlb]
    top5_nba = [se for se in candidates[:_TOP_N] if se.raw.sport == "NBA"]

    def row(lbl: str, val: str) -> str:
        return (
            f'<div class="diag-mlb-row">'
            f'<span class="diag-mlb-lbl">{_esc(lbl)}</span>'
            f'{val}'
            f'</div>'
        )

    rows: list[str] = [
        row("Top MLB",
            f'#{mlb_rank} · {_esc(mlb_top.raw.away_name)} @ {_esc(mlb_top.raw.home_name)}'
            f' · {round(mlb_top.total_score)}/100'),
        row("Gap from #5",
            f'{gap:+.1f} pts · {_esc(near_str)}'),
    ]

    if mlb_top.stakes_detail:
        rows.append(row("Stakes detail", _esc(mlb_top.stakes_detail)))
    if mlb_top.star_power_detail:
        rows.append(row("Star detail", _esc(mlb_top.star_power_detail)))
    if mlb_top.flags:
        rows.append(row("Flags", _esc(", ".join(mlb_top.flags))))
    if mlb_top.raw.away_probable_pitcher or mlb_top.raw.home_probable_pitcher:
        ap = mlb_top.raw.away_probable_pitcher or "TBD"
        hp = mlb_top.raw.home_probable_pitcher or "TBD"
        rows.append(row("Pitchers", f'{_esc(ap)} vs {_esc(hp)}'))
    if all_mlb:
        avg_stk = sum(se.stakes_score for se in all_mlb) / len(all_mlb)
        rows.append(row("Avg MLB stakes", f'{avg_stk:.1f} / 30 ({len(all_mlb)} events)'))
    if top5_nba:
        avg_nba = sum(se.stakes_score for se in top5_nba) / len(top5_nba)
        rows.append(row("Avg top-5 NBA stakes", f'{avg_nba:.1f} / 30'))

    return (
        '<div class="diag-mlb">'
        '<div class="diag-lbl">MLB absent from top 5</div>'
        + "".join(rows)
        + '</div>'
    )


def render_diagnostics(candidates: list[ScoredEvent]) -> str:
    """Build the full diagnostics HTML block — a collapsed <details> section."""
    n = len(candidates)
    table_html   = _diag_table(candidates)
    leaders_html = _diag_sport_leaders(candidates)
    mlb_html     = _diag_mlb_analysis(candidates)

    js = (
        '<script>'
        'function diagFilter(btn,sport){'
        'document.querySelectorAll(".diag-filter-btn")'
        '.forEach(function(b){b.classList.remove("active");});'
        'btn.classList.add("active");'
        'document.querySelectorAll(".diag-row")'
        '.forEach(function(r){'
        'r.style.display=(sport==="all"||r.dataset.sport===sport)?"":"none";'
        '});'
        'var sep=document.querySelector(".diag-cut-row");'
        'if(sep){sep.style.display=sport==="all"?"":"none";}'
        '}'
        '</script>'
    )

    filters = (
        '<div class="diag-filters">'
        '<button class="diag-filter-btn active" onclick="diagFilter(this,\'all\')">All</button>'
        '<button class="diag-filter-btn" onclick="diagFilter(this,\'NBA\')">NBA</button>'
        '<button class="diag-filter-btn" onclick="diagFilter(this,\'MLB\')">MLB</button>'
        '</div>'
    )

    return (
        f'<details class="diag-section">'
        f'<summary class="diag-summary">Diagnostics &middot; {n} candidates</summary>'
        f'<div class="diag-body">'
        + filters
        + table_html
        + leaders_html
        + mlb_html
        + '</div>'
        + js
        + '</details>'
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
    candidates:   list[ScoredEvent] | None = None,
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

    diag_html = render_diagnostics(candidates) if candidates is not None else ""

    context = {
        "week_label":       week_label,
        "events_html":      events_html,
        "generated_at":     generated_str,
        "diagnostics_html": diag_html,
    }

    html_out = _render(_TEMPLATE, context)
    _OUTPUT.write_text(html_out)
    return _OUTPUT
