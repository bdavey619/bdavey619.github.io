# Must Watch — TODO

---

## NOW (Product definition + quality refinement)

The engine is running and publishing weekly. Before expanding scope, make sure
the product is actually doing what the vision says it should.

**Product definition**
- [ ] Read VISION.md and identify where the current output falls short of it
- [ ] Audit the top 5 from the last 2–3 weeks: are the picks defensible to someone with no team allegiance?
- [ ] Identify any recurring false positives (games that keep scoring high but feel wrong) and trace to scoring weights or flag logic

**Ranking clarity**
- [ ] Verify explanations pass the "any game" test — no sentence should apply to a generic matchup
- [ ] Review whether the LLM explanations actually reference the structured context (stakes, flags, streak) or drift into vague language
- [ ] Check that cross-sport rankings feel justifiable — NBA vs. MLB top-5 comparisons should have a reason, not just a score gap

**Near-miss reasoning**
- [ ] Add a "why it didn't make the list" note to the editorial review output for positions 6–8
- [ ] Evaluate whether events sitting just below the cutoff are actually less compelling or are scoring artifacts

**Operational baseline**
- [ ] Confirm the automated Monday run is reliable — check the last 2–3 workflow runs for failures or stale data
- [ ] Review marquee player list for accuracy (injuries, trades, callups since initial setup)
- [ ] Keep observing weekly output; do not expand sport coverage until 4+ consecutive weeks feel right without heavy override

**PRODUCT SHARPNESS (Storyline + Time Value)**
- [ ] Evaluate whether top 5 actually reflects the strongest STORYLINES of the week (not just score output)
- [ ] Identify games with high narrative significance that are under-ranked by the current scoring weights
- [ ] Improve scoring or flags to better capture "don't miss this" moments — events with historic, cultural, or playoff-race significance
- [ ] Ensure explanations clearly communicate WHY this game is worth someone's limited time — not just what makes it interesting, but why it rises above everything else this week
- [ ] Stress test: would a busy person feel confident planning their week around this list? Could they make the case to a partner?
- [ ] Audit: are there games in the top 5 that score well but have no real narrative? Would anyone care in two weeks?

**Cadence**
- [ ] Evaluate M/W/F refresh cadence vs weekly only — does the list need to breathe during the week?
- [ ] Consider whether midweek updates meaningfully improve decision-making (starting pitcher changes, injuries, sudden playoff implications)
- [ ] If midweek updates are added, define what triggers one — not every change, only changes that would move the top 5

---

## NEXT (Phase 1 — Milestone 2)

Add editorial layer + explanation generation + output rendering (if not yet complete).

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
- [ ] PGA / ATP (requires separate scoring model — not team-vs-team)
