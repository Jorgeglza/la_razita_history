# La Razita — ESPN Fantasy Football Archive (2018–2025)

League ID: 1092134595 · Pulled: 2026-08-13

## 🌐 Live site

**https://jorgeglza.github.io/la_razita_history/**

(Live once GitHub Pages is enabled — see [Deploying to GitHub Pages](#deploying-to-github-pages) below.)

## What's here

```
data/
  raw/{year}/league_summary.json   <- full raw API response per season
  fantasy_league.db                <- SQLite database, normalized tables below
scripts/
  pull_history.py                  <- the puller (rerun anytime to refresh)
  config.json                      <- league id + ESPN auth cookies (keep private)
```

## Database tables (`data/fantasy_league.db`)

- **seasons** — one row per year: league name, size, scoring type, playoff format
- **divisions** — division id/name per year
- **teams** — one row per team per year: name, division, owners (SWID), final
  record (W/L/T, points for/against), final rank, playoff seed
- **scoring_settings** — the full points-per-stat scoring rules for each year
- **owners** — unique SWID → display name map. All SWIDs are filled in;
  display names are blank except yours. Edit this table directly (any SQLite
  tool, or `UPDATE owners SET display_name='X' WHERE swid='{...}'`) to label
  the rest of the league if you want names instead of raw SWIDs in reports.

## Known limitation — read this before asking "where are the matchups?"

ESPN's API stopped serving **weekly matchup schedules, per-player box scores,
draft results, and transaction history for completed seasons** sometime
around August 2025. This was confirmed two ways: every documented API view
was tested directly against ESPN's servers and returned only summary data for
2018–2025, and the ESPN website itself no longer renders old box-score pages
even when logged in — so this isn't an access problem, the data itself is no
longer being served for past seasons.

What survives per season: final standings, full season points for/against
totals, final rank, playoff seed, and the year's scoring/roster/playoff
settings. That's everything captured here.

If you ever locate the missing detail elsewhere (old ESPN recap emails,
screenshots, a spreadsheet someone kept, another platform's export), it can
be imported into this same database alongside what's here.

## Re-running

```
cd scripts
python pull_history.py
```

Safe to rerun — it upserts by year, so it won't duplicate rows.

## Website (`docs/`)

`docs/index.html` is a static "league headquarters" site — podium history,
wall of shame, all-time standings, manager cards, league rules-at-a-glance,
rivalries, futures/predictions, and a draft countdown — built from the data
above. It's a single self-contained page with no server required.

```
scripts/
  build_site.py                  <- the generator (reads the DB + content JSON, writes docs/)
site_src/
  templates/                     <- Jinja2 HTML templates
  static/css, static/js          <- brand system (navy/red/seafoam/sand) + vanilla JS
  content/
    managers.json                <- manager identities, bios, team-name history per year
    league_info.json             <- rules blurbs, rivalries, futures/ballot, tribute, draft date
docs/                             <- BUILD OUTPUT — safe to delete, regenerated every run
```

### Rebuilding the site

```
pip install jinja2   # one-time
cd scripts
python build_site.py
```

Then open `docs/index.html` directly in a browser, or serve `docs/` locally
(e.g. `python -m http.server --directory docs 8000`).

### Editing content

- **Real names / bios / rivalries / predictions**: edit
  `site_src/content/managers.json` and `site_src/content/league_info.json` —
  both are placeholder content marked `PLACEHOLDER` throughout, meant to be
  overwritten. Rerun `build_site.py` after editing.
- **Manager identity linking**: most teams don't have an ESPN-recorded owner
  (see Known limitation above). `managers.json` links a manager to their
  team-name history two ways: by `swid` (when ESPN recorded one) or purely by
  matching team names to years by hand — useful since a manager's `team_id`
  slot is often stable across years even when unnamed by ESPN (confirmed by
  cross-checking ESPN's league-members page). Any team-season that can't be
  matched to a `managers.json` entry falls back to being grouped by its raw
  team name in All-Time Standings, flagged "Unlinked".

### Deploying to GitHub Pages

The repo is already pushed to
[github.com/Jorgeglza/la_razita_history](https://github.com/Jorgeglza/la_razita_history).
One manual step turns it on (GitHub doesn't allow enabling Pages via a plain
`git push`):

1. Go to **https://github.com/Jorgeglza/la_razita_history/settings/pages**
2. Under **Build and deployment → Source**, choose **Deploy from a branch**
3. Under **Branch**, pick **`main`** and folder **`/docs`**, then click **Save**
4. Wait ~1 minute, then reload that Settings → Pages screen — GitHub will
   show a banner: "Your site is live at
   `https://jorgeglza.github.io/la_razita_history/`"

After that, every time you rerun `build_site.py` and push the updated
`docs/` folder to `main`, the live site updates automatically (usually
within a minute) — no further manual steps needed.

`scripts/config.json` holds ESPN auth cookies and is already excluded via
`.gitignore` — never commit it.
