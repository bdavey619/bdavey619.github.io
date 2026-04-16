# Must Watch This Week

A weekly, objective ranking of the most compelling upcoming sports events.

---

## 1. Product Overview

**What it is:** A sports editorial engine that looks at the week's upcoming MLB and NBA events and surfaces the 5 most narratively compelling ones — with specific, evidence-based reasoning for why each made the list.

**What problem it solves:** There are too many sports events and too little signal. Most fans don't have time to monitor every league, watch SportsCenter, or track every storyline. This product narrows the field and answers a single question with editorial sharpness:

> *Which sports events this week are actually worth watching?*

**The core job-to-be-done:** Help a sports fan with limited time decide where to direct their attention — without requiring them to already follow a specific team or league.

**What it is not:** A personalized feed. A team-specific brief. A score aggregator. A prediction engine.

---

## 2. Product Principles

**Objectivity over fandom.**
A Padres game should not outrank a more compelling event just because the reader follows the Padres. Rankings are sport-agnostic and team-agnostic.

**Explainability builds trust.**
Users should be able to see why an event ranked where it did. The score breakdown is part of the product, not just debugging.

**Story setup, not predicted game quality.**
We score the narrative going *into* a game — stakes, momentum, context, history. We do not predict whether the game will be good. A compelling setup that produces a blowout is not a product failure.

**Story > noise.**
Big markets and big-name teams do not automatically rank higher. An NHL team on a historic streak or a small-market rivalry with elimination implications can outrank a Knicks/Lakers game with nothing at stake.

**No generic sports media language.**
Every explanation must be specific and evidence-based. Prohibited: "this should be a great one," "two teams collide," "fans won't want to miss this." Required: specific records, specific numbers, specific context.

**Ranking logic is the product.**
The page design and email format are secondary. The core value is the scoring engine — the mechanism that produces a defensible, non-obvious ranked list.

---

## 3. Phase 1 MVP Scope

| Parameter | Decision |
|---|---|
| Sports | MLB + NBA only |
| Cadence | Weekly |
| Published | Monday morning |
| Ranking window | Monday (if upcoming) through Sunday |
| Time filter | Exclude events already started or within 1 hour of start |
| Output | Unified top 5 ranked list |
| Editorial | Manual override allowed and expected |

**Timing labels:**
- Events on the generation day (Monday): labeled `TONIGHT`
- All other events: labeled with weekday + date (e.g., `Thursday, April 17`)
- No list sections or splits — single unified ranking. Labels are display-only.

**Not in Phase 1:**
- NHL, Premier League, PGA, ATP
- Nightly variant
- Email rendering
- HTML output
- LLM-generated explanations
- Personalization of any kind

---

## 4. Scoring Framework

Total score: **0–100 points** across five dimensions.

### Stakes (0–30 pts)
The primary driver. Determines how much the result of this game matters.

- Playoff / elimination: 28–30
- Play-In game: 25
- Both teams in active playoff/division race: 18–22
- One team fighting for cutoff: 14–16
- Both above .500, no immediate stakes: 10–14
- No meaningful stakes: 5

Adjusted by **season-phase multiplier** for regular season games:
- First 20% of season: ×0.60
- Mid-season (20–70%): ×0.85
- Final 30%: ×1.00
- Postseason: no multiplier (already at max)

### Competitive Balance (0–20 pts)
Both teams must be good for the game to be watchable. Uses `min(team1_quality, team2_quality) × 2` — one weak team tanks the score regardless of opponent strength.

Team quality is derived from win percentage (0.650+ = 10, down to <0.460 = 2).

### Momentum (0–15 pts)
Combined recent form (L10 records) + streak bonus. Rewards games where both teams are in interesting form. A team on a 7+ game win streak adds a bonus.

### Star Power (0–15 pts)
Based on a manually maintained `MARQUEE_PLAYERS` list in `config.py`. Tiers: `superstar` and `star`. Active status cross-referenced against injury data where available.

- Both sides have an active superstar: 15
- One superstar + one star: 12
- Both teams have a star: 10
- One star, other side nothing notable: 6
- No marquee players on either side: 3

### Narrative Flags (0–20 pts)
Rules-based bonuses for specific detectable conditions. **Phase 1 supports six flags:**

| Flag | Sport | Tier | Points |
|---|---|---|---|
| `elimination_game` | NBA | 1 | 20 (no stacking) |
| `rivalry` | MLB/NBA | 2 | 8 |
| `playoff_rematch` | MLB/NBA | 2 | 6 |
| `ace_duel` | MLB | 2 | 6 |
| `first_place_clash` | MLB/NBA | 2 | 5 |
| `marquee_starter` | MLB | 2 | 3 |

`ace_duel` fires when both probable starters are in `MARQUEE_PITCHERS`.
`marquee_starter` fires when exactly one starter is in `MARQUEE_PITCHERS` (mutually exclusive with `ace_duel`).

Tier 1 flags do not stack — `elimination_game` alone = 20.
Tier 2 flags stack but are **capped at 12** (rivalry + playoff_rematch = 14 → capped at 12).

---

## 5. Narrative / Editorial Rules

- Every explanation references specific, verified facts — no LLM free recall of stats
- Structured context (records, streaks, flags) is fed explicitly to the LLM
- Explanations are 2–3 sentences max
- No sentence should apply to any generic game ("this should be a fun matchup")
- At least one reason a neutral fan — with no allegiance to either team — should care
- Manual editorial override is allowed in Phase 1, and expected to be used regularly

---

## 6. Data / Architecture Direction

### Data sources
| Sport | Source | Auth |
|---|---|---|
| MLB | `statsapi.mlb.com/api/v1` | None (official, free) |
| NBA | `site.api.espn.com/apis/site/v2/sports/basketball/nba` | None (unofficial) |

### Phase 1 pipeline (high level)
```
Ingest schedule (MLB + NBA, Mon–Sun)
  → Enrich with standings, L10, streak, marquee players
  → Apply timing filter (exclude started or <1hr away)
  → Detect narrative flags (rivalry, elimination, rematch, first_place_clash)
  → Score each event (5 dimensions → total)
  → Sort descending → take top 10 as candidate pool
  → Editorial review (CLI prompt, optional reorder)
  → Generate LLM explanations (fed structured context)
  → Render HTML + email output
```

### File structure
```
mustwatch/
  config.py       # All static data: weights, marquee players, rivalries, season config
  models.py       # Frozen dataclasses: TeamContext, RawEvent, ScoredEvent, WeeklyBrief
  mlb.py          # MLB Stats API client
  nba.py          # ESPN NBA API client
  enrich.py       # Build enriched events, apply time filter, detect flags
  score.py        # Scoring functions (pure, no I/O)
  rank.py         # Filter, sort, return top-N candidates
  editorial.py    # CLI review + override
  explain.py      # LLM explanation generation
  render.py       # HTML/email rendering
  run.py          # Entrypoint — orchestrates full pipeline
  templates/
    weekly.html   # {{key}} template (matches existing repo pattern)
```

### Milestone 1 (terminal dry-run only)
Files: `config.py`, `models.py`, `mlb.py`, `nba.py`, `enrich.py`, `score.py`, `rank.py`, `run.py`

Not yet: `editorial.py`, `explain.py`, `render.py`, HTML template, email output.

---

## 7. Phase 1 Build Order

1. `config.py` — static data, weights, marquee players, rivalries
2. `models.py` — dataclasses only, no logic
3. `mlb.py` — schedule + standings from `statsapi.mlb.com`
4. `nba.py` — schedule + standings from ESPN
5. `enrich.py` — normalize events, apply time filter, detect flags
6. `score.py` — scoring functions (pure)
7. `rank.py` — filter, sort, candidate selection
8. `run.py` — entrypoint, `--dry-run` flag for terminal output

**After Milestone 1 is validated:**
9. `editorial.py` — CLI review + override
10. `explain.py` — LLM explanation generation
11. `render.py` + `templates/weekly.html` — HTML output
12. Email output (mirrors existing `render_email.py` pattern)

---

## 8. Known Risks / Limitations

| Risk | Notes |
|---|---|
| Early MLB season underscores | Season-phase multiplier (×0.60 in first 20%) is intentional but may suppress compelling April games. Tune as needed. |
| Static marquee lists go stale | `MARQUEE_PLAYERS` and `RIVALRIES` in `config.py` must be reviewed periodically — especially during offseason roster moves. |
| Manual override expected | The scoring framework will produce defensible but imperfect results. Human editorial judgment is part of the product in Phase 1, not a fallback. |
| ESPN unofficial API has no SLA | Schema can change without warning. Log raw API responses during early runs and alert on shape changes. |
| Cross-sport normalization is imperfect | Comparing an NBA playoff game to an MLB regular season game requires calibration that no formula fully solves. Editor is the tiebreaker. |
| LLM hallucination risk | Explanations must be generated from structured context only. Never ask the LLM to recall stats from memory. |

---

## 9. Future Directions

**Additional sports** (not before Phase 1 is stable):
- NHL — natural fit; high-stakes playoff structure
- Premier League — strong narrative, strong rivalry infrastructure
- PGA Tour — different structure (individual, not team); needs separate scoring model
- ATP — similar to PGA; separate model needed

**Richer signals** (Phase 2+):
- Intra-series context (Game 2 of a split series vs. Game 1)
- Milestone / record proximity detection
- Betting market implied closeness as a balance signal
- Intraweek ranking updates (injury announcements, etc.)

**Cadence variants:**
- "Must Watch Tonight" as a lightweight daily companion
- Separate weekly newsletter / email edition

**Longer-term product vision:**
A personalized sports newspaper front page — where "Must Watch This Week" is the flagship module, but the product expands to include standings context, player storylines, and league-specific briefs. Personalization, if added, should operate as a filter (opt out of sports), not a bias (boost my team).

---

## 10. Success Criteria (Phase 1)

The product is successful when:
- The top 5 list feels defensible and non-obvious
- Rankings align with human intuition more often than not
- A user can quickly understand *why* each event is ranked

---

*Last updated: April 14, 2026*
