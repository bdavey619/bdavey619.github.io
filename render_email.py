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


def fmt_game_date(date_str):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%A, %B %-d, %Y")
    except Exception:
        return date_str


def fmt_generated_at(ts_str):
    try:
        dt = datetime.fromisoformat(ts_str)
        return dt.strftime("Updated %B %-d, %Y")
    except Exception:
        return ts_str


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

    # Insight
    insight = brief.get("insight", {})

    context = {
        "brief_date":        fmt_game_date(lg["date"]),
        "subhead":           brief.get("subhead", ""),
        "score_display":     score_display,
        "result_label":      result_label,
        "result_color":      result_color,
        "vs_line":           vs_line,
        "context_line":      lg.get("context_line", ""),
        "game_note":         lg.get("game_note", ""),
        "key_hitters_rows":  key_hitters_rows,
        "pitcher_name":      pitcher.get("name", ""),
        "pitcher_line":      pitcher.get("line", ""),
        "insight_headline":  insight.get("headline", ""),
        "insight_detail":    insight.get("detail", ""),
        "insight_why":       insight.get("why", ""),
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
