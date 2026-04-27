# Add New MLB Team — Morning Brief Checklist

Use this document to add any new team to the Morning Brief system. Replace `<team>` with the lowercase team slug (e.g. `giants`, `mariners`, `athletics`, `dodgers`) and `<TEAM>` with the Python constant name (e.g. `GIANTS`, `MARINERS`).

This document is designed to be handed directly to Claude Code:
> "Use `docs/ADD_NEW_TEAM.md` to add the Giants."

---

## A. Required Team Config Fields

Gather these values before touching any code.

| Field | Type | Notes |
|---|---|---|
| `team_id` | int | MLB Stats API team ID — look up at `statsapi.mlb.com/api/v1/teams?sportId=1` |
| `team_abbr` | str | Short label shown in linescore/scoreboards (e.g. `"SF"`, `"SEA"`) |
| `team_name` | str | Short team name (e.g. `"Giants"`, `"Mariners"`) |
| `team_city` | str | City name (e.g. `"San Francisco"`, `"Seattle"`) |
| `home_venue` | str | Full venue name (e.g. `"Oracle Park"`, `"T-Mobile Park"`) |
| `home_venue_short` | str | Short venue name for subheads (e.g. `"Oracle"`, `"T-Mobile"`) |
| `league_id` | int | `104` = NL, `103` = AL |
| `division_id` | int | See table below |
| `division_name` | str | (e.g. `"NL West"`, `"AL West"`) |
| `division_short` | str | Direction word only: `"West"`, `"East"`, `"Central"` |
| `tz_offset` | int | UTC offset during DST (e.g. `-7` = PT, `-5` = CT, `-4` = ET) |
| `tz_label` | str | Timezone abbreviation (e.g. `"PT"`, `"ET"`) |
| `site_url` | str | Published brief URL (e.g. `"https://bdavey619.github.io/giants/"`) |
| `accent_color` | str | Primary brand hex color (e.g. `"#FD5A1E"` for Giants) |

**Division IDs:**

| Division | ID |
|---|---|
| AL East | 201 |
| AL Central | 202 |
| AL West | 200 |
| NL East | 204 |
| NL Central | 205 |
| NL West | 203 |

**Timezone note:** Use the UTC offset *during the MLB season (DST)*. PT = -7, MT = -6, CT = -5, ET = -4.

**Accent color:** Use the team's primary brand color, not necessarily the dominant jersey color. Dark colors work better for the brief's design aesthetic. Check the team's official style guide.

---

## B. Files and Folders to Create

```
<team>/
├── build_brief.py        (copy from yankees/, change import + CFG line)
├── index.html            (copy from yankees/, update title + division labels)
├── app.js                (copy from yankees/)
├── styles.css            (copy from yankees/, update accent_color CSS variable)
├── email_template.html   (copy from yankees/)
├── brief.json            (placeholder — see scaffold below)
├── story_state.json      (placeholder — see scaffold below)
└── hook_history.json     (placeholder — see scaffold below)
```

**brief.json placeholder** — keeps `render_email.py` from crashing before the first real run:
```json
{}
```

**story_state.json placeholder:**
```json
{
  "trend": "neutral",
  "driver": "balanced",
  "confidence": "low",
  "pressure": "none",
  "record_w": 0,
  "record_l": 0,
  "streak": "",
  "last10_w": 0,
  "era": 0.0,
  "ops": 0.0,
  "gb": 0.0,
  "division_rank": 0,
  "last_result": "",
  "date": "",
  "game_emotion_level": "normal"
}
```

**hook_history.json placeholder:**
```json
{
  "recent_types": []
}
```

---

## C. Files to Update

### 1. `engine/team_config.py`

Add a new `TeamConfig` constant at the bottom of the file. Follow the exact pattern of `PADRES` and `YANKEES`:

```python
GIANTS = TeamConfig(
    team_id=137,
    team_abbr="SF",
    team_name="Giants",
    team_city="San Francisco",
    home_venue="Oracle Park",
    home_venue_short="Oracle",
    league_id=104,
    division_id=203,
    division_name="NL West",
    division_short="West",
    tz_offset=-7,
    tz_label="PT",
    site_url="https://bdavey619.github.io/giants/",
    accent_color="#FD5A1E",
)
```

### 2. `render_email.py` (root-level)

Two changes:

**Line 23 — update import:**
```python
from engine.team_config import PADRES, YANKEES, GIANTS
```

**Lines 25-28 — update `_TEAM_CONFIGS` dict:**
```python
_TEAM_CONFIGS = {
    "padres":  PADRES,
    "yankees": YANKEES,
    "giants":  GIANTS,
}
```

### 3. `send_email.py` (root-level)

Same two changes as `render_email.py` above (same structure, same lines).

### 4. `<team>/build_brief.py`

Copy `yankees/build_brief.py`. Make exactly two changes:

- **Line with `from engine.team_config import`** — add the new team constant to the import
- **Line `CFG = YANKEES`** — change to `CFG = <TEAM>`

No other changes needed. The entire pipeline is config-driven through `CFG`.

### 5. `<team>/index.html`

Copy `yankees/index.html`. Update:
- `<title>` tag: `"<TeamName> Morning Brief"`
- `<h1 class="masthead-title">`: `"<TeamName> Morning Brief"`
- Division label in `#summary-bar` (e.g. `<span class="label">NL West</span>`)
- Any hardcoded venue or team references

### 6. `<team>/styles.css`

Copy `yankees/styles.css`. Update the CSS accent color variable (search for `#003087` or equivalent):
```css
--accent: <accent_color>;
```

### 7. `.github/workflows/<team>-brief.yml`

Create a new workflow file (see Section D).

### 8. Homepage / Projects page (optional)

The root `index.html` has no team-brief links — no update needed.

The `projects/index.html` has a "Padres Newsletter" entry in "Current Builds" — add a similar entry for the new team if desired (it currently has no link, just description text).

---

## D. Workflow File

Create `.github/workflows/<team>-brief.yml`. Copy `yankees-brief.yml` and make these changes:

```yaml
name: <TeamName> Morning Brief

on:
  schedule:
    # <description of local time>
    # Stagger at least 35 minutes from other team workflows to avoid resource contention.
    - cron: "<minute> <hour> * * *"
  workflow_dispatch:

jobs:
  build-brief:
    runs-on: ubuntu-latest

    permissions:
      contents: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install requests

      - name: Generate brief.json
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python <team>/build_brief.py

      - name: Render email HTML
        run: python render_email.py --team <team>

      - name: Send email
        env:
          RESEND_API_KEY: ${{ secrets.<TEAM>_RESEND_API_KEY }}
          EMAIL_TO: ${{ secrets.<TEAM>_EMAIL_TO }}
          EMAIL_FROM: ${{ secrets.<TEAM>_EMAIL_FROM }}
        run: python send_email.py --team <team>

      - name: Commit and push if changed
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add <team>/brief.json <team>/story_state.json
          if git diff --cached --quiet; then
            echo "No changes to brief.json — skipping commit."
          else
            git commit -m "chore: update <TeamName> morning brief [skip ci]"
            git push
          fi
```

**Current cron schedule (avoid these slots):**
- Padres: `25 10 * * *` (6:25 AM ET)
- Yankees: `0 11 * * *` (7:00 AM ET)

Space new teams at least 35 minutes apart from any existing slot.

---

## E. Secrets Checklist

Add the following secrets in the GitHub repo under **Settings → Secrets and variables → Actions**:

| Secret name | Description |
|---|---|
| `<TEAM>_RESEND_API_KEY` | Resend API key (`re_...`) for this team's sender |
| `<TEAM>_EMAIL_TO` | Recipient address(es), comma-separated |
| `<TEAM>_EMAIL_FROM` | Verified sender address (e.g. `brief@yourdomain.com`) |
| `ANTHROPIC_API_KEY` | Already exists — shared across all teams |

**Notes:**
- `ANTHROPIC_API_KEY` is shared. Do not add a duplicate.
- `<TEAM>_EMAIL_FROM` must be a verified domain or address in Resend. Verify before the first scheduled run.
- Padres uses `RESEND_API_KEY` / `EMAIL_TO` / `EMAIL_FROM` (no team prefix) — a historical artifact. All new teams should use the `<TEAM>_` prefix pattern.

---

## F. Local Validation Commands

Run these in order after setting up all files:

```bash
# 1. Generate brief.json (requires ANTHROPIC_API_KEY in env for AI narrative;
#    falls back to deterministic insight if the key is absent)
python <team>/build_brief.py

# 2. Render the email preview
python render_email.py --team <team>

# 3. Open the rendered email in a browser
open <team>/email_preview.html

# 4. Open the web brief in a browser
open <team>/index.html
```

If `brief.json` is empty (placeholder), step 2 will fail — run step 1 first.

---

## G. Website Validation Checklist

After opening `<team>/index.html`:

- [ ] Page title is correct: `"<TeamName> Morning Brief"`
- [ ] Masthead title is correct: `"<TeamName> Morning Brief"`
- [ ] Division label in summary bar matches the team's actual division (e.g. `NL West`, `AL West`)
- [ ] Standings show the correct division — not a leftover division from the copied team
- [ ] The team's own row in the standings table is highlighted
- [ ] State of Play section renders with text (not blank)
- [ ] Game Driver block only appears when `confidence` is `"high"` or `"medium"`
- [ ] Turning Point block only appears when `confidence` is `"high"`
- [ ] `story_hook` appears in the subhead only when meaningful (not on off days or data failures)
- [ ] No debug metadata is visible (no raw JSON, no error messages)
- [ ] Accent color in the result badge matches `<accent_color>` in team config
- [ ] Hard refresh (`Cmd+Shift+R` / `Ctrl+Shift+R`) after any `app.js` or `styles.css` change — browser caches these aggressively

---

## H. Email Validation Checklist

After opening `<team>/email_preview.html`:

- [ ] Subject line will render as: `"<TeamName> Morning Brief — <Month Day>"`
- [ ] CTA link (`site_url`) points to the correct team page (not padres or yankees)
- [ ] Accent color on the WIN/LOSS badge matches the team's `accent_color`
- [ ] Highlights link appears only when a highlights URL is present
- [ ] State of Play headline and detail text render (not blank)
- [ ] "What to Watch" section appears only when AI narrative is available
- [ ] Game Driver block renders only when `confidence` is `"high"` or `"medium"`, and only when the player differs from the Turning Point player
- [ ] Turning Point block renders only when `confidence` is `"high"`
- [ ] No Padres or Yankees leftover text in the template (venue names, division names, color references)
- [ ] Footer `generated_at` shows today's date

---

## I. Narrative / Voice Checklist

Before declaring the team ready for subscribers:

- [ ] A voice profile for the team exists in `engine/narrative.py` — check that the AI prompt references the team's tone and style
- [ ] Voice is subtle, not a costume — avoid "gritty defense"-for-Cubs or "East Coast swagger"-for-Yankees transplanting
- [ ] Division rivalry context is correct for this team's actual division (Giants → NL West rivals: Dodgers, Padres, not AL East)
- [ ] No leftover Padres or Yankees phrasing in narrative output
- [ ] Player arc references are based on actual game data, not forced story templates
- [ ] Review 2-3 consecutive days of narrative output before adding subscribers

---

## J. Common Gotchas

These are issues that have already occurred with Padres/Yankees builds:

**`app.js` / `styles.css` appear unchanged in browser**
Hard refresh required after any frontend edit: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R`. The browser caches these files aggressively.

**Workflow push rejected**
The workflow commit step runs `git push` after `git commit`. If another workflow ran simultaneously and pushed first, this will fail with a non-fast-forward error. Fix: add `git pull --rebase origin main` before `git push` in the workflow:
```yaml
git pull --rebase origin main
git push
```

**Rebase fails — unstaged generated files block it**
If `brief.json` or `story_state.json` have uncommitted local changes, `git pull --rebase` will refuse to run. Fix: add `git restore .` before the rebase to discard any uncommitted generated files:
```yaml
git restore .
git pull --rebase origin main
git push
```

**`brief.json` conflict between local build and cron**
Running `build_brief.py` locally while the cron is active creates a race condition: both write `brief.json`, both try to commit. The cron wins; your local version is overwritten on next pull. Run local builds outside the cron window, or use `workflow_dispatch` to trigger a fresh run instead.

**Missing `ANTHROPIC_API_KEY` in local env**
`build_brief.py` falls back to deterministic insight when the API key is absent — the brief still generates, but `narrative` fields will be empty. The email render falls back gracefully to `insight` fields. This is expected behavior for local testing.

**`story_state.json` and `hook_history.json` must be team-specific**
Both files track per-team narrative state. They must live in `<team>/` and must never be shared across teams. If either file is missing, the narrative engine will initialize them fresh on the next run — this is safe.

**Do not commit `.claude/` files or `.DS_Store`**
The padres directory contains a `.claude/settings.local.json` file. This should never be committed. Check `.gitignore` before the first push for the new team directory.

**Resend sender must be verified before first scheduled run**
If `EMAIL_FROM` is not a verified Resend domain, the send step will return a 403 or 422. Verify the domain in Resend before enabling the cron.

---

## K. Final Go/No-Go Checklist

Complete all items before merging the new team branch or enabling the scheduled workflow:

**Code**
- [ ] `engine/team_config.py` — new constant added, all 14 fields correct
- [ ] `render_email.py` — import updated, `_TEAM_CONFIGS` updated
- [ ] `send_email.py` — import updated, `_TEAM_CONFIGS` updated
- [ ] `<team>/build_brief.py` — import and `CFG` line updated
- [ ] `<team>/index.html` — title, masthead, division label updated
- [ ] `<team>/styles.css` — accent color updated

**Data files**
- [ ] `<team>/brief.json` — placeholder or real data present
- [ ] `<team>/story_state.json` — placeholder present
- [ ] `<team>/hook_history.json` — placeholder present

**Infrastructure**
- [ ] `.github/workflows/<team>-brief.yml` — created, cron slot is clear of conflicts
- [ ] GitHub Secrets: `<TEAM>_RESEND_API_KEY`, `<TEAM>_EMAIL_TO`, `<TEAM>_EMAIL_FROM` all set
- [ ] Resend sender address verified

**Local validation**
- [ ] `python <team>/build_brief.py` runs without error
- [ ] `python render_email.py --team <team>` runs without error
- [ ] Web brief opens and renders correctly (Section G checklist complete)
- [ ] Email preview opens and renders correctly (Section H checklist complete)

**Narrative quality**
- [ ] Voice profile reviewed (Section I checklist complete)
- [ ] 2-3 days of output reviewed before adding subscribers

**Commit hygiene**
- [ ] No `.claude/` files staged
- [ ] No `.DS_Store` files staged
- [ ] `brief.json` / `story_state.json` / `hook_history.json` are the placeholder versions (not a real day's output) in the initial commit

---

## Reference: Quick-Start Command Sequence

```bash
# After all files are created and updated:

# Validate locally
python <team>/build_brief.py
python render_email.py --team <team>
open <team>/email_preview.html
open <team>/index.html

# Commit the new team
git add engine/team_config.py
git add render_email.py send_email.py
git add <team>/
git add .github/workflows/<team>-brief.yml
git status  # verify nothing unexpected is staged
git commit -m "feat: add <TeamName> morning brief"
git push
```

After the first successful push, trigger a test run manually via **GitHub → Actions → `<TeamName> Morning Brief` → Run workflow** before relying on the cron.
