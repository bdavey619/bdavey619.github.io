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

# Target sentence count — 2 is the default; 3 only when a third carries a
# genuinely distinct fact that the first two cannot hold.
_TARGET_SENTENCES = 2


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
You write event explanations for a weekly sports "Must Watch" column.

Length: 2 sentences. Use a third only when it carries a genuinely distinct \
fact the first two cannot hold — not to elaborate, qualify, or transition.

Each explanation must answer three things inside those 2 sentences:
  — Why does this game rank here? (the structural reason: standings, stakes, elimination)
  — What is the single most concrete fact that makes it compelling?
  — Why should a neutral fan care?

Voice and mechanics:
  Use strong, direct verbs: leads, trails, needs, holds, faces, enters, forces.
  State the story. Do not introduce it.
  Use factual contrast: "Team A is 8-2 in their last 10; Team B has lost four \
straight" — not "while Team A has been hot, Team B has struggled recently."
  Every sentence must contain at least one specific fact from the event data.

Second sentence rule:
  The second sentence must introduce tension, contrast, or asymmetry — not \
describe or elaborate on sentence one.
  It should feel like a conclusion: the variable, the edge, or the asymmetry \
that the first sentence sets up but does not resolve.
  Patterns that work:
    "[X] decides this."
    "There's no edge here except [specific fact]."
    "The structure is clear; the variable is [Z]."
    "Both teams are [equal fact] — the difference is [specific asymmetry]."
    "That said, [contrasting fact that complicates or sharpens the picture]."
  Patterns that fail:
    Neutral description: "They are also divisional rivals." (no tension added)
    Restatement: "That makes this game significant for both sides." (says nothing new)
    Elaboration: "A win here would go a long way toward securing their position." \
(weaker version of what sentence one already established)

Forbidden constructions — do not use these or close variants:
  "adds texture"
  "what makes this matter" / "what makes this matter now"
  "turning this into"
  "square off in"
  "the stakes are high"
  "on the line"
  "adds to the intrigue"
  Any sentence that restates what the previous sentence already said
  Any prediction about game quality, outcome, or atmosphere
  Any generic sports hype language (epic, blockbuster, electric, must-see, \
thrilling, exciting, showcase)

Constraint: use only the facts in the event data provided. Do not recall or \
invent statistics, scores, injury reports, or season context beyond what is given.

Output: exactly 5 blocks. Format each as:
EVENT 1:
[explanation]

EVENT 2:
[explanation]

...through EVENT 5. No other text."""


def _build_user_prompt(final: list[ScoredEvent]) -> str:
    blocks = [_build_event_block(i, se) for i, se in enumerate(final, start=1)]
    joined = "\n\n".join(blocks)
    return (
        f"Write a {_TARGET_SENTENCES}-sentence explanation for each of the "
        f"5 events below. Use a third sentence only if a distinct fact cannot "
        f"fit in two.\n\n"
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
