#!/usr/bin/env python3
"""
send_email.py — Send a Morning Brief via Resend.

Usage:
    python3 send_email.py --team padres
    python3 send_email.py --team yankees

Reads {team}/brief.json for safety checks, reads {team}/email_preview.html
for content, sends via the Resend HTTP API. No external dependencies required.

Required environment variables:
    RESEND_API_KEY  — Resend API key (re_...)
    EMAIL_TO        — recipient address(es), comma-separated
    EMAIL_FROM      — verified sender address (e.g. brief@yourdomain.com)

Optional:
    EMAIL_SUBJECT   — override the default subject line
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent

sys.path.insert(0, str(ROOT))
from engine.team_config import PADRES, YANKEES, GIANTS  # noqa: E402

_TEAM_CONFIGS = {
    "padres":  PADRES,
    "yankees": YANKEES,
    "giants":  GIANTS,
}

RESEND_API_URL = "https://api.resend.com/emails"


def load_brief(team_dir):
    with open(team_dir / "brief.json") as f:
        return json.load(f)


def safety_check(brief):
    """
    Return (ok: bool, reason: str).

    Guards against sending a brief that is incomplete or based on a game
    that hasn't finished. Fails safe: any missing or unexpected value blocks
    the send rather than allowing a broken email through.
    """
    last_game = brief.get("last_game", {})

    status = last_game.get("status")
    if status != "final":
        return False, f"last_game.status is '{status}' — game may not be complete, skipping send"

    score = last_game.get("score", {})
    if "team" not in score or "opp" not in score:
        return False, "last_game.score is missing team/opp fields — skipping send"

    result = last_game.get("result")
    if result not in ("W", "L"):
        return False, f"last_game.result is '{result}' — skipping send"

    if not last_game.get("opponent"):
        return False, "last_game.opponent is missing — skipping send"

    return True, "ok"


def build_subject(brief, cfg):
    override = os.environ.get("EMAIL_SUBJECT", "").strip()
    if override:
        return override

    last_game = brief.get("last_game", {})
    date_str = last_game.get("date", "")
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        date_label = d.strftime("%B %-d")
    except Exception:
        date_label = date_str

    return f"{cfg.team_name} Morning Brief \u2014 {date_label}"


def send_email(api_key, to_addrs, from_addr, subject, html_content, team_name):
    payload = json.dumps({
        "from": from_addr,
        "to": to_addrs,
        "subject": subject,
        "html": html_content,
    }).encode("utf-8")

    req = urllib.request.Request(
        RESEND_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"{team_name.lower()}-morning-brief/1.0",
        },
        method="POST",
    )

    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, body


def main():
    parser = argparse.ArgumentParser(description="Send a Morning Brief email.")
    parser.add_argument("--team", required=True, choices=list(_TEAM_CONFIGS.keys()),
                        help="Team slug (e.g. padres, yankees)")
    args = parser.parse_args()

    team_slug = args.team
    cfg = _TEAM_CONFIGS[team_slug]
    team_dir = ROOT / team_slug

    # Validate required env vars before doing any file I/O
    api_key   = os.environ.get("RESEND_API_KEY", "").strip()
    emails    = [e.strip() for e in os.environ.get("EMAIL_TO", "").split(",") if e.strip()]
    from_addr = os.environ.get("EMAIL_FROM", "").strip()

    missing = [
        name for name, val in [
            ("RESEND_API_KEY", api_key),
            ("EMAIL_FROM", from_addr),
        ]
        if not val
    ]
    if not emails:
        missing.append("EMAIL_TO")
    if missing:
        print(f"ERROR: Missing required env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    # Load brief and run safety check
    brief = load_brief(team_dir)
    ok, reason = safety_check(brief)
    if not ok:
        print(f"Safety guard: {reason}")
        print("No email sent.")
        sys.exit(0)

    # Load rendered HTML
    html_path = team_dir / "email_preview.html"
    if not html_path.exists():
        print(f"ERROR: {html_path} not found — run render_email.py --team {team_slug} first",
              file=sys.stderr)
        sys.exit(1)

    html_content = html_path.read_text()
    subject = build_subject(brief, cfg)

    print(f"Sending: {subject}")
    print("Sending to:", emails)
    print(f"  From: {from_addr}")

    try:
        status, body = send_email(api_key, emails, from_addr, subject, html_content, cfg.team_name)
        print(f"Resend API response {status}: {body}")
        print("Email sent.")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"ERROR: Resend returned {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
