"""
explain.py — LLM-based explanation generation for Must Watch This Week.

Generates 2–3 sentence editorial explanations for the final top-5 events,
using only the structured data available in each ScoredEvent. No free recall.

Public API
----------
    generate_explanations(final: list[ScoredEvent]) -> list[str]
        Returns one explanation string per event, in the same order.
        Falls back to placeholder text if the API call fails.
"""

from __future__ import annotations

import re
import os
import sys
from models import ScoredEvent

# Model to use — Opus for editorial quality on the product voice
_MODEL = "claude-opus-4-6"

# How many sentences per explanation
_SENTENCES = "2–3"


# ---------------------------------------------------------------------------
# Structured event block builder
# ---------------------------------------------------------------------------

def _record(ctx) -> str:
    return f"{ctx.wins}-{ctx.losses} ({ctx.win_pct:.3f})"


def _l10(ctx) -> str:
    return f"L10 {ctx.l10_wins}-{ctx.l10_losses}"


def _streak(ctx) -> str:
    if ctx.streak_n == 0:
        return "no streak"
    return f"{ctx.streak_type}{ctx.streak_n}"


def _standing_line(ctx) -> str:
    """Sport-specific standing context."""
    if ctx.sport == "MLB":
        if ctx.games_back is None:
            div = "1st in division"
        else:
            div = f"{ctx.games_back:.1f} GB in division"
        wc = ""
        if ctx.wild_card_rank is not None:
            if ctx.wc_games_back is None:
                wc = ", in wild card"
            else:
                wc = f", {ctx.wc_games_back:.1f} GB from wild card"
        return div + wc
    else:  # NBA
        rank = ctx.conference_rank
        conf = ctx.conference or ""
        if rank:
            return f"#{rank} in {conf}"
        return ""


def _clean_stakes_detail(detail: str) -> str:
    """
    Strip the '×multiplier' suffix from stakes_detail — that is an internal
    scoring artifact, not a fact to surface in an explanation.

    'both in race (strong) ×1.00'  →  'both in race (strong)'
    'postseason'                    →  'postseason'
    """
    return re.sub(r"\s*×[\d.]+$", "", detail).strip()


def _flag_labels(flags: list[str]) -> str:
    label_map = {
        "rivalry":          "rivalry game",
        "playoff_rematch":  "playoff rematch",
        "first_place_clash": "first-place clash",
        "elimination_game": "elimination/play-in game",
    }
    return ", ".join(label_map.get(f, f) for f in flags) if flags else "none"


def _build_event_block(i: int, se: ScoredEvent) -> str:
    ev   = se.raw
    home = se.home_ctx
    away = se.away_ctx

    date_str = ev.game_date.strftime("%A, %B %-d")
    venue    = ev.venue or "venue TBD"

    away_line = (
        f"  Away — {away.name}: {_record(away)}, {_l10(away)}, "
        f"streak: {_streak(away)}, {_standing_line(away)}"
    )
    home_line = (
        f"  Home — {home.name}: {_record(home)}, {_l10(home)}, "
        f"streak: {_streak(home)}, {_standing_line(home)}"
    )

    star_line = ""
    if se.star_power_detail and se.star_power_detail != "no marquee players":
        star_line = f"\n  Star players: {se.star_power_detail}"

    context_type = ""
    if ev.is_playin:
        context_type = "play-in game"
    elif ev.is_postseason:
        context_type = "postseason game"
    else:
        context_type = _clean_stakes_detail(se.stakes_detail)

    lines = [
        f"EVENT {i} — [{ev.sport}]  {away.name} @ {home.name}",
        f"  {date_str}  |  {venue}",
        away_line,
        home_line,
        f"  Context: {context_type}",
        f"  Narrative flags: {_flag_labels(se.flags)}",
    ]
    if star_line:
        lines.append(star_line)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You write editorial explanations for a weekly "Must Watch" sports column.

Rules — follow these exactly:
1. Write exactly {sentences} sentences per event.
2. Reference only the facts provided in the event block. Do not recall or invent statistics, scores, or season history beyond what is given.
3. Lead with the story setup — the stakes, narrative context, or rivalry — not a prediction of game quality or outcome.
4. Be specific: name teams by name (not generic terms), cite standings positions, win streaks, or rivalry context when present in the data.
5. No generic sports media language. Forbidden phrases include: "must-see matchup", "clash of titans", "electric atmosphere", "fun to watch", "showcase", "exciting", "blockbuster", "thrilling", "epic", and similar hype words.
6. No predictions about who will win or how the game will play out.
7. No filler sentences. Every sentence must carry a distinct piece of information from the event data.
8. Write in a direct, confident editorial voice — like a knowledgeable editor telling a reader which game matters and why.

Output format: respond with exactly 5 blocks in this format:
EVENT 1:
[explanation]

EVENT 2:
[explanation]

...and so on through EVENT 5. No other text.""".replace("{sentences}", _SENTENCES)


def _build_user_prompt(final: list[ScoredEvent]) -> str:
    blocks = [_build_event_block(i, se) for i, se in enumerate(final, start=1)]
    joined = "\n\n".join(blocks)
    return (
        f"Write a {_SENTENCES}-sentence explanation for each of the 5 events below.\n\n"
        f"{joined}"
    )


# ---------------------------------------------------------------------------
# API call + response parsing
# ---------------------------------------------------------------------------

def _parse_response(text: str, n: int) -> list[str]:
    """
    Extract n explanation strings from the model's response.
    Expects blocks delimited by 'EVENT N:' headers.
    """
    # Split on EVENT <number>: patterns
    parts = re.split(r"EVENT\s+\d+\s*:\s*\n?", text, flags=re.IGNORECASE)
    # parts[0] is text before first header (empty or preamble); skip it
    explanations = [p.strip() for p in parts[1:] if p.strip()]

    # Pad or trim to exactly n
    while len(explanations) < n:
        explanations.append("[explanation not generated]")
    return explanations[:n]


def generate_explanations(final: list[ScoredEvent]) -> list[str]:
    """
    Generate one 2–3 sentence explanation per event in `final`.

    Uses a single Claude API call with all events in context.
    Prompt caching is applied to the system message.

    Returns a list of explanation strings in the same order as `final`.
    Falls back gracefully if the API call fails.
    """
    if not final:
        return []

    try:
        import anthropic
    except ImportError:
        print("Warning: anthropic package not installed — skipping explanations.",
              file=sys.stderr)
        return ["[anthropic package not installed]"] * len(final)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Warning: ANTHROPIC_API_KEY not set — skipping explanations.",
              file=sys.stderr)
        return ["[ANTHROPIC_API_KEY not set]"] * len(final)

    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model=_MODEL,
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {"role": "user", "content": _build_user_prompt(final)}
            ],
        )
    except Exception as exc:
        print(f"Warning: explanation API call failed — {exc}", file=sys.stderr)
        return [f"[explanation unavailable]"] * len(final)

    raw_text = response.content[0].text
    return _parse_response(raw_text, len(final))
