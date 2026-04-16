# Must Watch — Decision Log

Chronological record of key product and implementation decisions.

---

## 2026-04-14 — Weekly cadence, not nightly

**Decision:** Publish once weekly (Monday morning), not daily or nightly.

**Rationale:** "Must Watch Tonight" already exists — it's ESPN. A weekly format is a differentiated planning tool: read it Monday, decide where to spend your attention for the week. It also reduces data ops complexity significantly for Phase 1. A nightly variant may be added later as a lightweight companion.

---

## 2026-04-14 — Unified ranked list, not grouped by sport

**Decision:** One ranked list across MLB and NBA — not "best MLB game + best NBA game" separately.

**Rationale:** Grouping by sport avoids the hard question. A unified list forces the engine to actually answer: is this NBA game more compelling than that MLB game this week? That's where the editorial value lives. Grouping by sport produces a schedule, not a ranking.

---

## 2026-04-14 — Start with MLB + NBA only

**Decision:** Phase 1 covers only MLB and NBA. NFL, NHL, Premier League, PGA, and ATP deferred.

**Rationale:** Both sports are in season simultaneously in April–June. Both have good free data sources. Both have enough weekly events that ranking is meaningful. Adding leagues too early produces shallow coverage across many sports instead of sharp coverage across two. Expand only after the core engine is validated.

---

## 2026-04-14 — Rank story setup, not predicted game quality

**Decision:** The engine scores narrative going *into* a game, not whether the game will actually be good.

**Rationale:** Game quality cannot be reliably predicted. Story setup can be evaluated objectively from standings, form, stakes, and context. A high-narrative game that ends in a blowout is not a product failure — we're a preview engine, not a guarantee. Being explicit about this constraint also makes the product's scope honest and defensible.

---

## 2026-04-14 — Manual editorial override required in Phase 1

**Decision:** After automated scoring, a human editor reviews the top 10 candidates and may reorder the top 5 or swap one event before output is generated.

**Rationale:** The scoring framework will produce defensible but imperfect results, especially in edge cases involving cross-sport comparisons, early-season MLB calibration, and events not captured by the 4 narrative flags. The override is not a fallback — it is a designed part of the Phase 1 product. Scoring removes the need to evaluate every game; editorial judgment makes the final call.

---

## 2026-04-14 — Include Monday events with a 1-hour buffer filter

**Decision:** Include upcoming Monday events in the weekly ranking. Exclude any event already started or starting within 1 hour of the generation timestamp.

**Rationale:** Excluding all Monday events wastes legitimate content — a Monday night playoff game is compelling regardless of the day. The 1-hour buffer ensures the ranked list is always actionable (users won't find a game that just started). Same-day events are labeled `TONIGHT` to communicate immediacy without restructuring the list.

---

## 2026-04-14 — Dry-run milestone before rendering or explanations

**Decision:** Milestone 1 is terminal output only — ranked candidates with score breakdowns, no HTML, no LLM explanations, no editorial CLI.

**Rationale:** The most important thing to validate first is whether real data flows into defensible rankings. Building the rendering and explanation layers before the scoring is validated wastes effort — if the ranking logic is wrong, the explanations are wrong too. Dry-run first; polish second.

---

## 2026-04-14 — Use statsapi.mlb.com for MLB, ESPN unofficial API for NBA

**Decision:** MLB data from `statsapi.mlb.com/api/v1`. NBA data from `site.api.espn.com` (unofficial).

**Rationale:** `statsapi.mlb.com` is already used in this repo (padres/yankees briefs) and proven reliable. ESPN's unofficial API is the most accessible free source for NBA schedule and standings data. Neither requires an API key for Phase 1 data needs. Risk: ESPN schema is undocumented and can change — log raw responses during early runs.

---

## 2026-04-14 — Tier 2 narrative flags capped at 12, not 20

**Decision:** `rivalry` + `playoff_rematch` + `first_place_clash` can stack but are capped at 12 points combined. `elimination_game` (Tier 1) is a hard 20 with no stacking.

**Rationale:** Preserving the top of the narrative range (13–20) for genuinely terminal events. A regular season rivalry game with a playoff rematch flavor is interesting (14 raw → capped at 12), but it should not score as high as an actual elimination game. The cap enforces that distinction without requiring complex conditional logic.

---

## 2026-04-14 — Season-phase multiplier for regular season MLB stakes

**Decision:** Regular season stakes scores are multiplied by a season-phase factor: ×0.60 (first 20% of games), ×0.85 (middle 50%), ×1.00 (final 30%).

**Rationale:** A close division race in Game 15 of 162 is meaningfully less urgent than the same race in Game 140. The multiplier prevents April games from inflating to the same stakes level as September games — a defensible editorial judgment. Risk: this may suppress genuinely compelling early-season storylines. The editorial override exists precisely for this case.

---

## 2026-04-14 — Static marquee player list in config.py, manually maintained

**Decision:** `MARQUEE_PLAYERS` is a dict in `config.py` rather than a dynamically fetched roster list.

**Rationale:** Dynamic roster APIs add complexity and fragility for minimal gain in Phase 1. The set of truly marquee players (superstars and stars worth surfacing in rankings) is small and slow-changing. A curated static list is more reliable and more editorially intentional. Review quarterly and after major trades/injuries.

---

## 2026-04-16 — Automation via mustwatch-auto branch + PR review gate

**Decision:** GitHub Actions generates `mustwatch/index.html` on a Monday schedule and pushes it to a dedicated `mustwatch-auto` branch, then opens (or updates) a PR against `main`. Nothing publishes live until the PR is manually merged.

**Pattern chosen:** Option A (auto-generate to branch + PR review), not artifact-only (Option B) or manual-trigger-only (Option C).

**Rationale:** Preserves editorial control — merge = publish, no accidental live updates. The PR interface is familiar, low-friction, and provides a natural review surface. GitHub sends a notification for new PRs. The diff is always just `mustwatch/index.html` because `mustwatch-auto` is reset from `main` on each run, keeping the PR diff clean. Option B (artifacts) adds download friction. Option C alone doesn't eliminate the repetitive generation step.

**Non-interactive mode:** `run.py --auto` flag accepts the default top 5 without stdin. This is the only change to the pipeline — the interactive local workflow is unchanged.

**Editorial posture in CI:** Default top 5, no override. The scoring engine's best guess goes into the PR. The editor reviews and either merges as-is, edits `mustwatch/index.html` on the branch before merging, or closes the PR entirely.

**Secrets required:** `ANTHROPIC_API_KEY` (GitHub repo secret). `GITHUB_TOKEN` is provided automatically by Actions.
