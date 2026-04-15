# Must Watch — TODO

---

## NOW (Phase 1 — Milestone 1)

Build dry-run pipeline. Terminal output only.

- [ ] `config.py` — weights, marquee players, rivalries, season config
- [ ] `models.py` — dataclasses
- [ ] `mlb.py` — schedule + standings from statsapi.mlb.com
- [ ] `nba.py` — schedule + standings from ESPN
- [ ] `enrich.py` — normalize events, timing filter, flag detection
- [ ] `score.py` — scoring functions
- [ ] `rank.py` — sort + candidate selection
- [ ] `run.py` — entrypoint with `--dry-run` flag
- [ ] Log excluded events (started / <1hr) for sanity checking
- [ ] Validate: does the ranked output feel defensible?
- [ ] Tune scoring weights if early results are obviously off

---

## NEXT (Phase 1 — Milestone 2)

Add editorial layer + explanation generation + output rendering.

- [ ] `editorial.py` — CLI review + override (top 10 → pick 5)
- [ ] `explain.py` — LLM explanations fed from structured context
- [ ] `render.py` + `templates/weekly.html` — HTML output
- [ ] Email rendering (match existing `render_email.py` pattern)
- [ ] End-to-end test: full Monday morning run → published HTML

---

## LATER (Phase 2+)

Do not start until Phase 1 is running weekly and validated.

- [ ] Intraweek refresh (injury updates, etc.)
- [ ] Series context within regular season multi-game series
- [ ] Milestone / record proximity detection
- [ ] Betting market implied closeness as balance signal
- [ ] Rivalry list expansion + auto-detection
- [ ] NHL support
- [ ] Premier League support
- [ ] "Must Watch Tonight" nightly lightweight variant
- [ ] Review marquee player list for accuracy
- [ ] PGA / ATP (requires separate scoring model — not team-vs-team)
