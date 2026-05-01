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


def _recap_date():
    """Yesterday's date — the game date we expect to recap this morning."""
    return datetime.now().date() - timedelta(days=1)


def should_send(brief):
    """
    Primary send gate: only send when last_game.date == yesterday AND
    status is final or postponed (including doubleheaders).

    Returns (ok: bool, reason: str).

    next_game.date == today is explicitly NOT a send trigger — preview-only
    emails (stale recap + game today) are suppressed here.
    """
    last_game = brief.get("last_game", {})
    status    = last_game.get("status")

    if status not in ("final", "postponed"):
        return False, f"no recap-worthy game yesterday for padres (status={status!r})"

    lg_date_str = last_game.get("date", "")
    try:
        lg_date = datetime.strptime(lg_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return False, f"last_game.date unparseable ({lg_date_str!r}) — skipping"

    recap_date = _recap_date()
    if lg_date != recap_date:
        return False, (
            f"no recap-worthy game yesterday for padres "
            f"(last_game.date={lg_date_str}, recap_date={recap_date})"
        )

    return True, "ok"


def is_already_archived(brief):
    """
    Duplicate-run guard: return True if the archive file for this brief's
    send date already exists, meaning the email was already sent today.
    """
    last_game   = brief.get("last_game", {})
    lg_date_str = last_game.get("date", "")
    try:
        lg_date = datetime.strptime(lg_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return False
    send_date = (lg_date + timedelta(days=1)).strftime("%Y-%m-%d")
    return (HERE / "archive" / f"{send_date}.json").exists()


def safety_check(brief):
    """
    Return (ok: bool, reason: str).

    Guards against sending a brief that is incomplete or based on a game
    that hasn't finished. Only reached after should_send() passes, so
    status is guaranteed to be 'final' or 'postponed'.
    """
    last_game = brief.get("last_game", {})
    status    = last_game.get("status")

    if status == "postponed":
        if not last_game.get("opponent"):
            return False, "last_game.opponent is missing in postponed brief — skipping send"
        return True, "ok"

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

    force_send = os.getenv("FORCE_SEND", "").lower() == "true"
    print(f"[email] env FORCE_SEND: {str(force_send).lower()}")

    # Load brief and run send-gate + safety checks
    brief = load_brief()
    send, reason = should_send(brief)
    if not send:
        print(f"[email] skipped: {reason}")
        sys.exit(0)
    if is_already_archived(brief) and not force_send:
        print("[email] skipped: padres brief already archived (duplicate run guard)")
        sys.exit(0)
    if force_send:
        print("[email] FORCE_SEND enabled — bypassing duplicate guard")
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
