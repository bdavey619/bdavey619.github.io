#!/usr/bin/env python3
"""
render_email.py — Render a Morning Brief as an HTML email.

Usage:
    python3 render_email.py --team padres
    python3 render_email.py --team yankees

Reads {team}/brief.json, renders {team}/email_template.html,
writes {team}/email_preview.html. No external dependencies required.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent

# Load the team config for SITE_URL
sys.path.insert(0, str(ROOT))
from engine.team_config import PADRES, YANKEES  # noqa: E402

_TEAM_CONFIGS = {
    "padres":  PADRES,
    "yankees": YANKEES,
}


def get_team_dir(team_slug):
    return ROOT / team_slug


def load_brief(team_dir):
    with open(team_dir / "brief.json") as f:
        return json.load(f)


def render(template_path, context):
    """Replace {{key}} placeholders. No external deps."""
    html = template_path.read_text()
    for key, value in context.items():
        html = html.replace("{{" + key + "}}", str(value))
    return html


def fmt_brief_date():
    """Today's date — the publication date of this brief."""
    return datetime.now().strftime("%A, %B %-d, %Y")


def fmt_game_date_short(date_str):
    """Short game date for the context line: e.g. 'Sat, Apr 12'."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%a, %b %-d")
    except Exception:
        return date_str


def fmt_generated_at(ts_str):
    try:
        dt = datetime.fromisoformat(ts_str)
        return dt.strftime("Updated %B %-d, %Y")
    except Exception:
        return ts_str


def build_highlights_link(url, accent_color):
    """Return an inline HTML highlights CTA, or empty string if no URL."""
    if not url:
        return ""
    return (
        '<p style="margin:8px 0 0;">'
        f'<a href="{url}" style="font-family:-apple-system,BlinkMacSystemFont,\'Helvetica Neue\',Arial,sans-serif;'
        'font-size:11px;letter-spacing:0.08em;text-transform:uppercase;'
        f'color:{accent_color};font-weight:600;text-decoration:none;">'
        "Watch highlights &#8594;</a></p>"
    )


def build_hitter_rows(hitters):
    rows = []
    for i, h in enumerate(hitters):
        is_last = i == len(hitters) - 1
        border = "none" if is_last else "1px dotted #d8d2c4"
        rows.append(
            f'          <tr>\n'
            f'            <td>\n'
            f'              <table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" style="border-bottom:{border};">\n'
            f'                <tr>\n'
            f'                  <td style="font-family:-apple-system,BlinkMacSystemFont,\'Helvetica Neue\',Arial,sans-serif;font-size:14px;font-weight:600;color:#1a1613;padding:4px 0;">{h["name"]}</td>\n'
            f'                  <td align="right" style="font-family:\'Courier New\',Courier,monospace;font-size:13px;color:#5a534c;padding:4px 0;">{h["line"]}</td>\n'
            f'                </tr>\n'
            f'              </table>\n'
            f'            </td>\n'
            f'          </tr>'
        )
    return "\n".join(rows)


def _strip_markdown(text):
    """Remove bold/italic markdown markers that render as literal chars in email."""
    import re
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # **bold**
    text = re.sub(r'\*(.+?)\*',     r'\1', text)  # *italic*
    text = re.sub(r'__(.+?)__',     r'\1', text)  # __bold__
    text = re.sub(r'_(.+?)_',       r'\1', text)  # _italic_
    return text


def _build_game_driver_block(game_driver, clutch_name=None):
    """Return a <tr> block for the Game Driver callout, or empty string.

    Only rendered when confidence is high or medium and the driver is a
    different player than the clutch player (Turning Point).
    """
    if not game_driver or game_driver.get("confidence") not in ("high", "medium"):
        return ""
    name = game_driver.get("name", "")
    description = game_driver.get("description", "")
    if not name or not description:
        return ""
    if clutch_name and name == clutch_name:
        return ""
    return (
        '<tr>'
        '<td style="padding-top:14px;padding-bottom:8px;">'
        '<p style="margin:0 0 4px;font-family:-apple-system,BlinkMacSystemFont,\'Helvetica Neue\',Arial,sans-serif;'
        'font-size:10px;text-transform:uppercase;letter-spacing:0.12em;color:#5a534c;font-weight:700;">'
        'Game Driver</p>'
        '<p style="margin:0;font-family:-apple-system,BlinkMacSystemFont,\'Helvetica Neue\',Arial,sans-serif;'
        f'font-size:15px;font-style:italic;color:#1a1613;line-height:1.5;">'
        f'<strong style="font-style:normal;font-weight:700;">{name}</strong> {description}</p>'
        '</td>'
        '</tr>'
    )


def _build_clutch_block(clutch):
    """Return a <tr> block for the Turning Point callout, or empty string."""
    if not clutch or clutch.get("confidence") != "high":
        return ""
    name = clutch.get("name", "")
    description = clutch.get("description", "")
    if not name or not description:
        return ""
    return (
        '<tr>'
        '<td style="padding-top:14px;padding-bottom:16px;border-bottom:1px solid #d8d2c4;">'
        '<p style="margin:0 0 4px;font-family:-apple-system,BlinkMacSystemFont,\'Helvetica Neue\',Arial,sans-serif;'
        'font-size:10px;text-transform:uppercase;letter-spacing:0.12em;color:#5a534c;font-weight:700;">'
        'Turning Point</p>'
        '<p style="margin:0;font-family:-apple-system,BlinkMacSystemFont,\'Helvetica Neue\',Arial,sans-serif;'
        f'font-size:15px;font-style:italic;color:#1a1613;line-height:1.5;">'
        f'<strong style="font-style:normal;font-weight:700;">{name}</strong> {description}</p>'
        '</td>'
        '</tr>'
    )


def _build_story_hook_block(story_hook):
    """Return a <tr> block for the story hook below the subhead, or empty string."""
    if not story_hook:
        return ""
    return (
        '<tr>'
        '<td align="center" style="padding:0 0 18px;">'
        '<p style="margin:0;font-family:Georgia,\'Times New Roman\',serif;'
        'font-size:14px;font-style:italic;font-weight:400;color:#8a8278;line-height:1.45;">'
        f'{story_hook}</p>'
        '</td>'
        '</tr>'
    )


def _build_what_to_watch_block(text):
    """Return a self-contained <table> block for the What to Watch section.
    Returns empty string when no text — the {{what_to_watch_block}} placeholder
    collapses cleanly without leaving stray markup.
    """
    if not text:
        return ""
    safe = _strip_markdown(text)
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation"'
        ' style="border-top:1px solid rgba(47,36,29,0.20);margin-top:12px;">'
        '<tr>'
        '<td style="padding-top:10px;">'
        '<p style="margin:0 0 4px;font-family:-apple-system,BlinkMacSystemFont,\'Helvetica Neue\',Arial,sans-serif;'
        'font-size:10px;text-transform:uppercase;letter-spacing:0.1em;color:#5a534c;font-weight:600;">'
        'What to Watch</p>'
        '<p style="margin:0;font-family:Georgia,\'Times New Roman\',serif;'
        'font-size:13px;font-style:italic;color:#2f241d;line-height:1.6;">'
        f'{safe}</p>'
        '</td>'
        '</tr>'
        '</table>'
    )


def main():
    parser = argparse.ArgumentParser(description="Render a Morning Brief email.")
    parser.add_argument("--team", required=True, choices=list(_TEAM_CONFIGS.keys()),
                        help="Team slug (e.g. padres, yankees)")
    args = parser.parse_args()

    team_slug = args.team
    cfg = _TEAM_CONFIGS[team_slug]
    team_dir = get_team_dir(team_slug)

    brief_path    = team_dir / "brief.json"
    template_path = team_dir / "email_template.html"
    output_path   = team_dir / "email_preview.html"

    if not brief_path.exists():
        print(f"ERROR: {brief_path} not found", file=sys.stderr)
        sys.exit(1)
    if not template_path.exists():
        print(f"ERROR: {template_path} not found", file=sys.stderr)
        sys.exit(1)

    brief = load_brief(team_dir)
    lg = brief["last_game"]

    # Game identity
    team_score = lg["score"]["team"]
    opp_score  = lg["score"]["opp"]
    home_away  = "vs" if lg["home"] else "@"
    score_display = f"{team_score}\u2013{opp_score}"
    vs_line = f"{home_away} {lg['opponent']}"

    result = lg["result"]
    result_label = "WIN" if result == "W" else "LOSS"
    result_color = cfg.accent_color if result == "W" else "#5a534c"

    # Performers
    key_hitters_rows = build_hitter_rows(lg.get("key_hitters", []))
    pitcher = lg.get("key_pitcher", {})

    # Next game teaser
    ng = brief.get("next_game", {})
    ng_home_away = "vs" if ng.get("home") else "@"
    ng_prob = ng.get("probable", {})
    next_probables = f"{ng_prob.get('team', 'TBD')} vs {ng_prob.get('opp', 'TBD')}" if ng_prob else "TBD"
    ng_insight = ng.get("insight", "")
    if ng_insight:
        next_insight_row = (
            '<tr><td style="padding-bottom:20px;" align="center">'
            '<p style="margin:0;font-family:-apple-system,BlinkMacSystemFont,\'Helvetica Neue\',Arial,sans-serif;'
            'font-size:12px;font-style:italic;color:#8a8278;">'
            f'{ng_insight}</p></td></tr>'
        )
        next_insight_pb = "6px"
    else:
        next_insight_row = ""
        next_insight_pb = "20px"

    # State of Play — prefer AI narrative when available, fall back to deterministic insight
    narrative = brief.get("narrative", {})
    insight   = brief.get("insight", {})
    if narrative.get("top_frame"):
        insight_headline    = _strip_markdown(narrative["top_frame"])
        insight_detail      = _strip_markdown(narrative.get("what_this_means", ""))
        what_to_watch_text  = narrative.get("what_to_watch", "")
    else:
        insight_headline    = insight.get("headline", "")
        insight_detail      = insight.get("detail", "")
        what_to_watch_text  = ""

    # Game date label prepended to context line for clarity (brief date ≠ game date on off days)
    game_date_short = fmt_game_date_short(lg["date"])
    existing_context = lg.get("context_line", "")
    context_line_with_date = f"{game_date_short} · {existing_context}" if existing_context else game_date_short

    clutch = lg.get("clutch_player") or {}
    clutch_name = clutch.get("name", "") if clutch else ""

    context = {
        "brief_date":           fmt_brief_date(),
        "subhead":              brief.get("subhead", ""),
        "story_hook_block":     _build_story_hook_block(brief.get("story_hook", "")),
        "score_display":        score_display,
        "result_label":         result_label,
        "result_color":         result_color,
        "vs_line":              vs_line,
        "context_line":         context_line_with_date,
        "game_note":            lg.get("game_note", ""),
        "highlights_link":      build_highlights_link(lg.get("highlights_url"), cfg.accent_color),
        "game_driver_block":    _build_game_driver_block(lg.get("game_driver"), clutch_name),
        "clutch_block":         _build_clutch_block(lg.get("clutch_player")),
        "key_hitters_rows":  key_hitters_rows,
        "pitcher_name":      pitcher.get("name", ""),
        "pitcher_line":      pitcher.get("line", ""),
        "insight_headline":    insight_headline,
        "insight_detail":      insight_detail,
        "what_to_watch_block": _build_what_to_watch_block(what_to_watch_text),
        "next_opponent":     f"{ng_home_away} {ng.get('opponent', '')}",
        "next_time":         ng.get("time_local", ""),
        "next_probables":    next_probables,
        "next_insight_row":  next_insight_row,
        "next_insight_pb":   next_insight_pb,
        "site_url":          cfg.site_url,
        "generated_at":      fmt_generated_at(brief.get("generated_at", "")),
    }

    html = render(template_path, context)
    output_path.write_text(html)
    print(f"✓  Written to {output_path}")


if __name__ == "__main__":
    main()
