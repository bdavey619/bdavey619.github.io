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
    EMAIL_BCC_[TEAM] — BCC recipient(s), comma-separated (e.g. EMAIL_BCC_PADRES)
    EMAIL_FROM       — verified sender address; also used as the visible To (e.g. brief@yourdomain.com)

Optional:
    EMAIL_SUBJECT   — override the default subject line
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent

sys.path.insert(0, str(ROOT))
from engine.team_config import PADRES, YANKEES, GIANTS, ATHLETICS  # noqa: E402

_TEAM_CONFIGS = {
    "padres":    PADRES,
    "yankees":   YANKEES,
    "giants":    GIANTS,
    "athletics": ATHLETICS,
}

_TEAM_DISPLAY = {
    "padres":    "Padres",
    "yankees":   "Yankees",
    "giants":    "Giants",
    "athletics": "A's",
}

RESEND_API_URL = "https://api.resend.com/emails"


def load_brief(team_dir):
    with open(team_dir / "brief.json") as f:
        return json.load(f)


def _recap_date():
    """Yesterday's date — the game date we expect to recap this morning."""
    return datetime.now().date() - timedelta(days=1)


def should_send(brief, team_slug):
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
        return False, f"no recap-worthy game yesterday for {team_slug} (status={status!r})"

    lg_date_str = last_game.get("date", "")
    try:
        lg_date = datetime.strptime(lg_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return False, f"last_game.date unparseable ({lg_date_str!r}) — skipping"

    recap_date = _recap_date()
    if lg_date != recap_date:
        return False, (
            f"no recap-worthy game yesterday for {team_slug} "
            f"(last_game.date={lg_date_str}, recap_date={recap_date})"
        )

    return True, "ok"


def _sent_marker_path(brief, team_dir):
    """Return the path to the sent marker for this brief's send date."""
    last_game   = brief.get("last_game", {})
    lg_date_str = last_game.get("date", "")
    try:
        lg_date = datetime.strptime(lg_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    send_date = (lg_date + timedelta(days=1)).strftime("%Y-%m-%d")
    return team_dir / "archive" / "sent" / f"{send_date}.json"


def is_already_sent(brief, team_dir):
    """
    Duplicate-run guard: return True if the sent marker for this brief's
    send date exists, meaning the email was already delivered today.

    Checks archive/sent/{send_date}.json — written only after a successful
    Resend API call. The brief archive file (archive/{send_date}.json) is
    intentionally NOT used here because it is written before email send.
    """
    path = _sent_marker_path(brief, team_dir)
    return path is not None and path.exists()


def write_sent_marker(brief, team_dir, team_slug):
    """Write archive/sent/{send_date}.json after a successful email send."""
    path = _sent_marker_path(brief, team_dir)
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump({
            "sent_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "team": team_slug,
        }, f, indent=2)
    print(f"[email] wrote sent marker: {path}")


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


def build_subject(brief, cfg):
    override = os.environ.get("EMAIL_SUBJECT", "").strip()
    if override:
        return override

    last_game  = brief.get("last_game", {})
    status     = last_game.get("status", "")
    date_str   = last_game.get("date", "")

    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        date_label = d.strftime("%b %-d")
    except Exception:
        date_label = date_str

    if status == "postponed":
        ha  = "vs" if last_game.get("home") else "@"
        opp = last_game.get("opponent", "")
        return f"{cfg.team_name} postponed {ha} {opp} | Morning Brief ({date_label})"

    result = last_game.get("result", "")
    score  = last_game.get("score", {})
    if result in ("W", "L") and isinstance(score, dict) and "team" in score and "opp" in score:
        verb = "win" if result == "W" else "lose"
        return f"{cfg.team_name} {verb} {score['team']}\u2013{score['opp']} | Morning Brief ({date_label})"

    return f"{cfg.team_name} Morning Brief | {date_label}"


def send_email(api_key, bcc_addrs, from_addr, subject, html_content, team_name):
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
    team_key  = os.environ.get(f"{team_slug.upper()}_RESEND_API_KEY", "").strip()
    global_key = os.environ.get("RESEND_API_KEY", "").strip()
    api_key   = team_key or global_key
    bcc_env_key = f"EMAIL_BCC_{team_slug.upper()}"
    print(f"[email] env {bcc_env_key} present: {bcc_env_key in os.environ}")
    bcc_raw   = os.environ.get(bcc_env_key, "")
    bcc_addrs = [r.strip() for r in bcc_raw.split(",") if r.strip()]
    from_email_raw = os.environ.get("EMAIL_FROM", "").strip()
    # Extract bare address if the secret accidentally contains a full display name.
    # e.g. "Giants - Morning Brief <brief@mail.bdavey.co>" becomes "brief@mail.bdavey.co"
    import re as _re
    _addr_match = _re.search(r'<([^>]+)>', from_email_raw)
    from_email   = _addr_match.group(1) if _addr_match else from_email_raw
    team_display = _TEAM_DISPLAY.get(team_slug, "Morning Brief")
    from_addr    = f"{team_display} | Morning Brief <{from_email}>" if from_email else ""

    missing = [
        name for name, val in [
            (f"{team_slug.upper()}_RESEND_API_KEY or RESEND_API_KEY", api_key),
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
    brief = load_brief(team_dir)
    send, reason = should_send(brief, team_slug)
    if not send:
        print(f"[email] skipped: {reason}")
        sys.exit(0)
    if is_already_sent(brief, team_dir) and not force_send:
        print(f"[email] skipped: {team_slug} email already sent today (duplicate run guard)")
        sys.exit(0)
    if force_send:
        print("[email] FORCE_SEND enabled — bypassing duplicate guard")
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

    print(f"[email] sending to {len(bcc_addrs)} BCC recipients for team: {team_slug}")
    if not bcc_addrs:
        print(f"[email] No BCC recipients found for team: {team_slug}")

    print(f"Sending: {subject}")
    print(f"  From/To: {from_addr}")
    if bcc_addrs:
        print(f"  Bcc: {', '.join(bcc_addrs)}")

    try:
        status, body = send_email(api_key, bcc_addrs, from_addr, subject, html_content, cfg.team_name)
        print(f"Resend API response {status}: {body}")
        print("Email sent.")
        write_sent_marker(brief, team_dir, team_slug)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"ERROR: Resend returned {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
