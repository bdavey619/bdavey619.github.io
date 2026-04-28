#!/usr/bin/env python3
"""Archive a team morning brief.

Usage:
    python archive_brief.py --team padres
    python archive_brief.py --team yankees
    python archive_brief.py --team giants

Reads <team>/brief.json, writes <team>/archive/YYYY-MM-DD.json, and
rebuilds <team>/archive/index.json from all existing archive files.
The archive date is the brief's generated_at date (brief publication date).
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

TEAM_NAMES = {
    "padres": "Padres",
    "yankees": "Yankees",
    "giants": "Giants",
}


def main():
    parser = argparse.ArgumentParser(description="Archive a team morning brief")
    parser.add_argument("--team", required=True, choices=list(TEAM_NAMES))
    args = parser.parse_args()

    team = args.team
    brief_path = Path(f"{team}/brief.json")
    archive_dir = Path(f"{team}/archive")
    archive_dir.mkdir(exist_ok=True)

    with open(brief_path) as f:
        brief = json.load(f)

    # Use generated_at date (brief publication date) as primary; fall back to last_game.date
    date_str = None
    generated_at = brief.get("generated_at", "")
    if generated_at:
        date_str = generated_at[:10]

    if not date_str:
        last_game = brief.get("last_game", {})
        if last_game.get("date"):
            date_str = last_game["date"]

    if not date_str:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Write snapshot
    snapshot_path = archive_dir / f"{date_str}.json"
    with open(snapshot_path, "w") as f:
        json.dump(brief, f, indent=2)
    print(f"Saved {snapshot_path}")

    # Rebuild index from all archive files
    team_name = TEAM_NAMES[team]
    entries = []

    for p in sorted(archive_dir.glob("*.json")):
        if p.name == "index.json":
            continue
        try:
            with open(p) as f:
                d = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        last = d.get("last_game", {})
        result_str = ""
        opponent = ""

        if last.get("status") == "final":
            result = last.get("result", "")
            score = last.get("score", {})
            team_score = score.get("team", "")
            opp_score = score.get("opp", "")
            opponent = last.get("opponent", "")
            if result and team_score != "" and opp_score != "":
                result_str = f"{result} {team_score}–{opp_score}"

        entries.append({
            "date": p.stem,
            "title": f"{team_name} Morning Brief",
            "result": result_str,
            "opponent": opponent,
            "subhead": d.get("subhead", ""),
            "url": f"archive/{p.name}",
        })

    # Newest first
    entries.sort(key=lambda e: e["date"], reverse=True)

    index_path = archive_dir / "index.json"
    with open(index_path, "w") as f:
        json.dump(entries, f, indent=2)
    print(f"Updated {index_path} ({len(entries)} entries)")


if __name__ == "__main__":
    main()
