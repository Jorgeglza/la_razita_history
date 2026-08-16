# Content TODO — what's hidden and how to bring it back

The live site (`docs/index.html`) currently only shows sections built from
**real league data**: League at a Glance (core settings only), Podium
History, Wall of Shame, All-Time Standings, and Manager Cards (names/stats
only, no bios yet). Everything below is written and sitting in the content
files, just switched off, because it was placeholder/invented text rather
than real content. Nothing was deleted — flip a flag, fill in real text,
rerun `python scripts/build_site.py`.

All flags live in **`site_src/content/league_info.json`** →
`section_visibility`:

```json
"section_visibility": {
  "rivalries": false,
  "futures_ballot": false,
  "tribute": false,
  "draft_countdown": false,
  "show_ops_details": false,
  "show_manager_bios": false
}
```

## 1. Manager real names (highest value, do this first)

`site_src/content/managers.json` has 6 managers still marked
`"claimed": false, "display_name": null`. The site shows these as
"Unclaimed Franchise" with a `Name TBD` flag — their stats/team history are
already tracked correctly, they just need a real name attached:

| id | franchise / team-name lineage | what's known |
|---|---|---|
| `mgr_02` | Tampiyork → Ponchos → Mad Andrews → Flaccos → Ponchos | swid on file, no name |
| `mgr_03` | XANAX → Capt Gold → Zardashian | swid on file, no name |
| `mgr_04` | Zurdos → Los mazacuatos → chicas supercrikosas → tu recuerdo es mi martirio → La santa grifa | swid on file, no name |
| `mgr_05` | Los Frailes → Tua girls one Kupp | swid on file, no name |
| `mgr_06` | Stlan (same name every year, 2018–2025) | no swid at all — 3x champion, highest-value name to recover |

To fix one: set `"claimed": true` and `"display_name": "Real Name"` on that
entry in `managers.json`, then rerun the build.

## 2. Operational details (`show_ops_details`)

`league_at_a_glance` in `league_info.json` has real, DB-driven fields
already showing (scoring format, league size, playoff field size). The
following are still invented placeholder text and stay hidden until you
write the real versions and flip `show_ops_details` to `true`:

- `draft_date_iso`, `draft_location`
- `trade_deadline_text`
- `waiver_text`
- `playoff_text` (the plain-language blurb under "Playoff Field" — the Top N number itself is already real and shown)

## 3. Draft Countdown (`draft_countdown`)

Depends on a real `draft_date_iso` above. Once that's a real date, flip
`draft_countdown` to `true` to show the ticking countdown section again.

## 4. Manager bios & inside jokes (`show_manager_bios`)

Every manager entry in `managers.json` has placeholder `bio` and
`inside_joke` fields. Write real ones (or leave blank — the template
handles empty strings fine), then flip `show_manager_bios` to `true`.

## 5. Rivalries (`rivalries`)

`league_info.json` → `rivalries` array has two invented placeholder
write-ups. Real head-to-head history isn't available from ESPN for past
seasons (see README's "Known limitation" section), so these have to be
written from memory/screenshots. Replace the `title`/`blurb` text, then
flip `rivalries` to `true`.

## 6. Futures & Ballot (`futures_ballot`)

`league_info.json` → `futures_ballot.entries` — pre-season predictions/prop
bets for the upcoming season. Replace with real ones before each draft,
flip `futures_ballot` to `true`.

## 7. Tribute (`tribute`)

`league_info.json` → `tribute` — empty/placeholder space for an in-memoriam
or retrospective write-up. Fill in or delete the section usage in
`site_src/templates/index.html` if not needed; flip `tribute` to `true` if
keeping it.

## Already done

- ✅ Real logo/mascot artwork wired into the site (`site_src/static/img/`)
- ✅ Jaime Zorrilla (`mgr_07`) and Enrique Sosa (`mgr_08`) confirmed and linked
- ✅ Jorge (`mgr_01`) linked via SWID
