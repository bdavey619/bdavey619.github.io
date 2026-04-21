"""
review.py — AI editorial review layer for Must Watch This Week.

Advisory only. Does not modify rankings or explanations.

Public API
----------
    generate_review(
        candidates:   list[ScoredEvent],   # full top-10 candidate pool
        final:        list[ScoredEvent],   # the selected top-5
        explanations: dict[str, str],      # game_id → explanation text
    ) -> dict
        Returns a structured review dict.
        Falls back gracefully if API key is missing or call fails.
"""

from __future__ import annotations

import json
import os
import re
import sys
from models import ScoredEvent

_MODEL = "claude-opus-4-6"


# ---------------------------------------------------------------------------
# Context block builder
# ---------------------------------------------------------------------------

def _record(ctx) -> str:
    return f"{ctx.wins}-{ctx.losses}"


def _l10(ctx) -> str:
    return f"L10 {ctx.l10_wins}-{ctx.l10_losses}"


def _streak(ctx) -> str:
    if ctx.streak_n == 0:
        return "no streak"
    return f"{ctx.streak_type}{ctx.streak_n}"


def _clean_stakes_detail(detail: str) -> str:
    return re.sub(r"\s*×[\d.]+$", "", detail).strip()


def _build_context(
    candidates: list[ScoredEvent],
    final: list[ScoredEvent],
    explanations: dict[str, str],
) -> str:
    final_ids = {se.raw.game_id for se in final}
    final_rank_by_id = {
        se.raw.game_id: i for i, se in enumerate(final, start=1)
    }
    pool_rank_by_id = {
        se.raw.game_id: i for i, se in enumerate(candidates, start=1)
    }

    lines = ["CANDIDATE POOL (ranked by score):"]
    lines.append("")

    for i, se in enumerate(candidates, start=1):
        ev   = se.raw
        home = se.home_ctx
        away = se.away_ctx

        selected_tag = ""
        if ev.game_id in final_ids:
            pub_rank = final_rank_by_id[ev.game_id]
            selected_tag = f"  [SELECTED → published as #{pub_rank}]"

        lines.append(
            f"#{i}  [{ev.sport}]  {away.name} @ {home.name}{selected_tag}"
            f"  —  score {se.total_score:.1f}/100"
        )
        lines.append(
            f"    Stakes {se.stakes_score:.1f}/30  Balance {se.competitive_balance_score:.1f}/20"
            f"  Momentum {se.momentum_score:.1f}/15  Stars {se.star_power_score:.1f}/15"
            f"  Narrative {se.narrative_flags_score:.1f}/20"
        )
        lines.append(
            f"    Away: {away.name} {_record(away)}  {_l10(away)}  {_streak(away)}"
        )
        lines.append(
            f"    Home: {home.name} {_record(home)}  {_l10(home)}  {_streak(home)}"
        )

        if se.flags:
            lines.append(f"    Flags: {', '.join(se.flags)}")

        if ev.sport == "MLB" and (ev.away_probable_pitcher or ev.home_probable_pitcher):
            ap = ev.away_probable_pitcher or "TBD"
            hp = ev.home_probable_pitcher or "TBD"
            lines.append(f"    Pitchers: {ap} (away) vs {hp} (home)")

        if se.stakes_detail:
            lines.append(f"    Stakes context: {_clean_stakes_detail(se.stakes_detail)}")

        if se.star_power_detail and se.star_power_detail != "no marquee players":
            lines.append(f"    Star players: {se.star_power_detail}")

        lines.append("")

    lines.append("FINAL SELECTION (top 5 chosen for publication):")
    lines.append("")

    for i, se in enumerate(final, start=1):
        pool_rank = pool_rank_by_id.get(se.raw.game_id)
        pool_note = f"  (pool rank #{pool_rank})" if pool_rank is not None else ""
        lines.append(f"#{i}  {se.raw.away_name} @ {se.raw.home_name}{pool_note}")

    lines.append("")
    lines.append("GENERATED EXPLANATIONS (one per selected game):")
    lines.append("")

    for i, se in enumerate(final, start=1):
        expl = explanations.get(se.raw.game_id, "[no explanation generated]")
        lines.append(f"#{i}  {se.raw.away_name} @ {se.raw.home_name}:")
        for ln in expl.splitlines():
            lines.append(f"    {ln}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are the skeptical editorial reviewer for Must Watch This Week.

This is a weekly sports column that picks the five most narratively compelling \
games for a busy adult with limited time. The scoring model ranks games on \
five dimensions: stakes (30 pts), competitive balance (20 pts), recent \
momentum (15 pts), star power (15 pts), and narrative flags — rivalry, \
elimination game, ace duel, first-place clash, playoff rematch (20 pts).

Your job is not to validate the list. Your job is to find where the ranking \
may be wrong, over-reliant on score math, or failing to communicate what \
actually makes a game worth planning around.

Review standard: could a busy person read the top 5 and say "I know which \
game I'm watching Thursday, and I could explain why to my partner"? If not, \
something failed.

Be specific. Be critical. Reference only the data provided in the input — \
do not recall or invent standings, stats, injuries, or storylines not present.

Output a single valid JSON object using this schema exactly:
{
  "summary": "<1–2 sentence critical overall assessment>",
  "what_looks_right": ["<specific reason, not generic praise>"],
  "possible_overrated": [
    { "rank": <int>, "matchup": "<Away @ Home>", "reason": "<data-backed reason>" }
  ],
  "possible_underrated": [
    { "rank": <int or null if outside pool>, "matchup": "<Away @ Home>", "reason": "<reason>" }
  ],
  "missed_storylines": ["<specific narrative context the flags did not capture>"],
  "scoring_suggestions": ["<exactly 1 suggestion tied to a specific scoring dimension>"],
  "explanation_suggestions": ["<exactly 1: name the game and what the explanation should sharpen>"],
  "editor_confidence": "<high|medium|low>"
}

Hard rules:
- You must name at least 1 possibly overrated game and 1 possibly underrated or missing game.
- "what_looks_right" max 2 items. Each must cite a specific fact from the data.
- "possible_overrated" and "possible_underrated" max 2 items each.
- "missed_storylines" max 2 items.
- No generic praise. "Looks good overall" is not an allowed response.
- Do not repeat the full candidate table back. Refer to games by matchup only.
- If editor_confidence is "high", the summary must say what specifically earns it.
- Output only the JSON object — no preamble, no trailing commentary.\
"""


def _build_user_prompt(
    candidates: list[ScoredEvent],
    final: list[ScoredEvent],
    explanations: dict[str, str],
) -> str:
    context = _build_context(candidates, final, explanations)
    return (
        "Review this week's Must Watch output. Return the JSON review object.\n\n"
        + context
    )


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

_FALLBACK: dict = {
    "summary": "[AI review unavailable]",
    "what_looks_right": [],
    "possible_overrated": [],
    "possible_underrated": [],
    "missed_storylines": [],
    "scoring_suggestions": [],
    "explanation_suggestions": [],
    "editor_confidence": "low",
}


def _parse_response(text: str) -> dict:
    text = text.strip()

    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?\s*```$", "", text).strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"Warning: could not parse review JSON — {exc}", file=sys.stderr)
        return {**_FALLBACK, "summary": "[review output could not be parsed]"}

    # Ensure all expected keys are present
    for key, default in _FALLBACK.items():
        if key not in result:
            result[key] = default

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_review(
    candidates: list[ScoredEvent],
    final: list[ScoredEvent],
    explanations: dict[str, str],
) -> dict:
    """
    Generate an advisory editorial review of the current Must Watch output.

    Uses a single Claude API call. Prompt caching is applied to the system
    message. Falls back gracefully if the API key is missing or the call fails.

    Returns a structured dict with keys:
        summary, what_looks_right, possible_overrated, possible_underrated,
        missed_storylines, scoring_suggestions, explanation_suggestions,
        editor_confidence
    """
    if not final:
        return {**_FALLBACK, "summary": "[no final events to review]"}

    try:
        import anthropic
    except ImportError:
        print("Warning: anthropic package not installed — skipping review.",
              file=sys.stderr)
        return {**_FALLBACK, "summary": "[anthropic package not installed]"}

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Warning: ANTHROPIC_API_KEY not set — skipping review.",
              file=sys.stderr)
        return {**_FALLBACK, "summary": "[ANTHROPIC_API_KEY not set]"}

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
                {
                    "role": "user",
                    "content": _build_user_prompt(candidates, final, explanations),
                }
            ],
        )
    except Exception as exc:
        print(f"Warning: review API call failed — {exc}", file=sys.stderr)
        return {**_FALLBACK, "summary": "[review API call failed]"}

    return _parse_response(response.content[0].text)
