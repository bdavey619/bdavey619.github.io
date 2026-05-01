#!/usr/bin/env python3
"""
DEPRECATED — This per-team script is no longer used by CI.
All teams are handled by the top-level send_email.py via --team flag.

    python3 send_email.py --team padres
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
BRIEF_PATH = HERE / "brief.json"
HTML_PATH = HERE / "email_preview.html"

RESEND_API_URL = "https://api.resend.com/emails"


def load_brief():
    with open(BRIEF_PATH) as f:
        return json.load(f)


def is_stale_recap(brief):
    """See send_email.py:is_stale_recap — same logic, hardcoded for padres."""
    last_game = brief.get("last_game", {})
    if last_game.get("status") not in ("final", "postponed"):
        return False
    ng_date   = brief.get("next_game", {}).get("date", "")
    today     = datetime.now().date()
    today_str = today.strftime("%Y-%m-%d")
    if ng_date == today_str:
        return False
    lg_date_str = last_game.get("date", "")
    try:
        lg_date = datetime.strptime(lg_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return False
    expected_send_date = (lg_date + timedelta(days=1)).strftime("%Y-%m-%d")
    if expected_send_date == today_str:
        return False
    return (HERE / "archive" / f"{expected_send_date}.json").exists()


def is_off_day(brief):
    """
    Return True when there is nothing worth sending: no recent game to recap
    AND no game scheduled today. If today has a game, the brief still goes out.
    """
    if brief.get("last_game", {}).get("status") != "off_day":
        return False
    ng_date = brief.get("next_game", {}).get("date", "")
    today   = datetime.now().strftime("%Y-%m-%d")
    return ng_date != today


def safety_check(brief):
    """
    Return (ok: bool, reason: str).

    Guards against sending a brief that is incomplete or based on a game
    that hasn't finished. Fails safe: any missing or unexpected value blocks
    the send rather than allowing a broken email through.
    """
    last_game = brief.get("last_game", {})

    # Game must be fully completed
    status = last_game.get("status")

    # off_day with a game today: is_off_day() already decided not to skip.
    if status == "off_day":
        return True, "ok"

    if status != "final":
        return False, f"last_game.status is '{status}' — game may not be complete, skipping send"

    # Score must have both sides
    score = last_game.get("score", {})
    if "team" not in score or "opp" not in score:
        return False, "last_game.score is missing team/opp fields — skipping send"

    # Result must be a clean W or L
    result = last_game.get("result")
    if result not in ("W", "L"):
        return False, f"last_game.result is '{result}' — skipping send"

    # Opponent must be present (sanity check for completely empty data)
    if not last_game.get("opponent"):
        return False, "last_game.opponent is missing — skipping send"

    return True, "ok"


def build_subject(brief):
    override = os.environ.get("EMAIL_SUBJECT", "").strip()
    if override:
        return override

    last_game = brief.get("last_game", {})
    date_str = last_game.get("date", "")
    result = last_game.get("result", "")
    score = last_game.get("score", {})

    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        date_label = d.strftime("%b %-d")
    except Exception:
        date_label = date_str

    if result in ("W", "L") and isinstance(score, dict) and "team" in score and "opp" in score:
        verb = "win" if result == "W" else "lose"
        return f"Padres {verb} {score['team']}\u2013{score['opp']} | Morning Brief ({date_label})"

    return f"Padres Morning Brief | {date_label}"


def send_email(api_key, bcc_addrs, from_addr, subject, html_content):
    payload_dict = {
        "from": from_addr,
        "to": [from_addr],
        "subject": subject,
        "html": html_content,
    }
    if bcc_addrs:
        payload_dict["bcc"] = bcc_addrs
    payload = json.dumps(payload_dict).encode("utf-8")

    req = urllib.request.Request(
        RESEND_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "padres-morning-brief/1.0",
        },
        method="POST",
    )

    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, body


def main():
    # Validate required env vars before doing any file I/O
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    print(f"[email] env EMAIL_BCC_PADRES present: {'EMAIL_BCC_PADRES' in os.environ}")
    bcc_raw = os.environ.get("EMAIL_BCC_PADRES", "")
    bcc_addrs = [r.strip() for r in bcc_raw.split(",") if r.strip()]
    from_addr = os.environ.get("EMAIL_FROM", "").strip()

    missing = [
        name for name, val in [
            ("RESEND_API_KEY", api_key),
            ("EMAIL_FROM", from_addr),
        ]
        if not val
    ]
    if missing:
        print(f"ERROR: Missing required env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    # Load brief and run off-day + safety checks
    brief = load_brief()
    if is_off_day(brief):
        print("[email] skipped: off day for padres")
        sys.exit(0)
    if is_stale_recap(brief):
        print("[email] skipped: no game today and last game already recapped for padres")
        sys.exit(0)
    ok, reason = safety_check(brief)
    if not ok:
        # Exit 0 so the workflow step doesn't fail — skipping is expected behaviour
        print(f"Safety guard: {reason}")
        print("No email sent.")
        sys.exit(0)

    # Load rendered HTML
    if not HTML_PATH.exists():
        print(f"ERROR: {HTML_PATH} not found — run render_email.py first", file=sys.stderr)
        sys.exit(1)

    html_content = HTML_PATH.read_text()
    subject = build_subject(brief)

    print(f"[email] sending to {len(bcc_addrs)} BCC recipients for team: padres")
    if not bcc_addrs:
        print("[email] No BCC recipients found for team: padres")

    print(f"Sending: {subject}")
    print(f"  From/To: {from_addr}")
    if bcc_addrs:
        print(f"  Bcc: {', '.join(bcc_addrs)}")

    try:
        status, body = send_email(api_key, bcc_addrs, from_addr, subject, html_content)
        print(f"Resend API response {status}: {body}")
        print("Email sent.")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"ERROR: Resend returned {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
