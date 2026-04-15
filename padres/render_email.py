#!/usr/bin/env python3
"""
render_email.py — Render Padres Morning Brief as an HTML email.

Usage:
    python3 render_email.py

Reads brief.json, renders email_template.html, writes email_preview.html.
No external dependencies required.
"""

import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
BRIEF_PATH = HERE / "brief.json"
TEMPLATE_PATH = HERE / "email_template.html"
OUTPUT_PATH = HERE / "email_preview.html"

SITE_URL = "https://bdavey619.github.io/padres/"


def load_brief():
    with open(BRIEF_PATH) as f:
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
    brief = load_brief()
    lg = brief["last_game"]

    # Game identity
    sd_score = lg["score"]["team"]
    opp_score = lg["score"]["opp"]
    home_away = "vs" if lg["home"] else "@"
    score_display = f"{sd_score}\u2013{opp_score}"
    vs_line = f"{home_away} {lg['opponent']}"

    result = lg["result"]
    result_label = "WIN" if result == "W" else "LOSS"
    result_color = "#2f241d" if result == "W" else "#5a534c"

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

    # Game date label prepended to context line for clarity (brief date ≠ game date on off days)
    game_date_short = fmt_game_date_short(lg["date"])
    existing_context = lg.get("context_line", "")
    context_line_with_date = f"{game_date_short} · {existing_context}" if existing_context else game_date_short

    context = {
        "brief_date":        fmt_brief_date(),
        "subhead":           brief.get("subhead", ""),
        "score_display":     score_display,
        "result_label":      result_label,
        "result_color":      result_color,
        "vs_line":           vs_line,
        "context_line":      context_line_with_date,
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
        "site_url":          SITE_URL,
        "generated_at":      fmt_generated_at(brief.get("generated_at", "")),
    }

    html = render(TEMPLATE_PATH, context)
    OUTPUT_PATH.write_text(html)
    print(f"✓  Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
