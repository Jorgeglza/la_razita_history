"""
Build the La Razita league-history static site.

Reads data/fantasy_league.db (produced by pull_history.py) plus the
hand-authored content files in site_src/content/, merges everything into one
JSON blob, and renders site_src/templates/index.html with it into docs/.

`docs/` is the whole build output — it's disposable and safe to delete/rerun.
docs/ is used (rather than a top-level index.html) because GitHub Pages can
serve straight from a repo's /docs folder with zero branch juggling once this
project is pushed.

Usage:
    cd scripts
    python build_site.py

Requires: jinja2 (pip install jinja2)
"""
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
DB_PATH = REPO_ROOT / "data" / "fantasy_league.db"
SITE_SRC = REPO_ROOT / "site_src"
CONTENT_DIR = SITE_SRC / "content"
TEMPLATES_DIR = SITE_SRC / "templates"
STATIC_DIR = SITE_SRC / "static"
OUT_DIR = REPO_ROOT / "docs"


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM seasons ORDER BY year")
    seasons = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM teams ORDER BY year, final_rank")
    teams = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM divisions ORDER BY year, division_id")
    divisions = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM owners")
    owners = {r["swid"]: dict(r) for r in cur.fetchall()}

    conn.close()
    return seasons, teams, divisions, owners


def build_manager_lookup(managers_cfg: list) -> dict:
    """
    Map (year, team_name) -> manager entry, and swid -> manager entry,
    so every team-season can be attributed to a manager card when known.
    """
    by_alias = {}
    by_swid = {}
    for m in managers_cfg:
        if m.get("swid"):
            by_swid[m["swid"]] = m
        for alias in m.get("team_aliases", []):
            by_alias[(alias["year"], alias["team_name"])] = m
    return by_alias, by_swid


def identity_key(team: dict, by_alias: dict, by_swid: dict):
    """
    Resolve a team-season to a stable identity: prefer a linked manager,
    fall back to the raw team_name (flagged unlinked) so nothing is dropped
    from all-time standings just because ESPN never recorded an owner SWID.

    A manager can be linked (found via swid or team_aliases) but still
    "unclaimed" (managers.json has no real display_name for them yet) — in
    that case we still group all their seasons under one row (so the
    cross-year aggregation isn't lost), but label the row with their most
    recent team name instead of inventing a "Manager A/B/C" placeholder tag,
    and keep it flagged unlinked so it's visibly a franchise still needing a
    real name.
    """
    swid = team["owners"] or None
    manager = None
    if swid and swid in by_swid:
        manager = by_swid[swid]
    else:
        manager = by_alias.get((team["year"], team["team_name"]))

    if manager:
        claimed = bool(manager.get("claimed")) and bool(manager.get("display_name"))
        if claimed:
            return manager["id"], manager["display_name"], False
        aliases = manager.get("team_aliases") or []
        fallback_label = aliases[-1]["team_name"] if aliases else team["team_name"]
        return manager["id"], fallback_label, True
    # unlinked fallback: group by team_name so at least repeat names collapse
    return f"team:{team['team_name']}", team["team_name"], True


def build_all_time_standings(teams, by_alias, by_swid):
    buckets = {}
    for t in teams:
        key, display_name, unlinked = identity_key(t, by_alias, by_swid)
        b = buckets.setdefault(key, {
            "key": key,
            "display_name": display_name,
            "unlinked": unlinked,
            "seasons_played": 0,
            "championships": 0,
            "runner_ups": 0,
            "wall_of_shame": 0,
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "points_for": 0.0,
            "points_against": 0.0,
            "years": [],
            "by_year": [],
        })
        b["seasons_played"] += 1
        b["wins"] += t["wins"] or 0
        b["losses"] += t["losses"] or 0
        b["ties"] += t["ties"] or 0
        b["points_for"] += t["points_for"] or 0.0
        b["points_against"] += t["points_against"] or 0.0
        b["years"].append(t["year"])
        b["by_year"].append({
            "year": t["year"],
            "team_name": t["team_name"],
            "wins": t["wins"] or 0,
            "losses": t["losses"] or 0,
            "ties": t["ties"] or 0,
            "points_for": round(t["points_for"] or 0.0, 2),
            "points_against": round(t["points_against"] or 0.0, 2),
            "final_rank": t["final_rank"],
        })
        if t["final_rank"] == 1:
            b["championships"] += 1
        if t["final_rank"] == 2:
            b["runner_ups"] += 1

    # wall of shame per year computed separately, flag it in after
    by_year_last = {}
    for t in teams:
        y = t["year"]
        if t["final_rank"] and t["final_rank"] > by_year_last.get(y, (0, None))[0]:
            by_year_last[y] = (t["final_rank"], t)
    for y, (rank, t) in by_year_last.items():
        key, _, _ = identity_key(t, by_alias, by_swid)
        if key in buckets:
            buckets[key]["wall_of_shame"] += 1

    standings = list(buckets.values())
    for b in standings:
        gp = b["wins"] + b["losses"] + b["ties"]
        b["win_pct"] = round(b["wins"] / gp, 3) if gp else 0.0
        b["points_for"] = round(b["points_for"], 2)
        b["points_against"] = round(b["points_against"], 2)
        b["years"] = sorted(b["years"])
        b["by_year"] = sorted(b["by_year"], key=lambda s: -s["year"])
    standings.sort(key=lambda b: -b["wins"])
    return standings


def build_seasons_view(seasons, teams, divisions):
    teams_by_year = {}
    for t in teams:
        teams_by_year.setdefault(t["year"], []).append(t)

    out = []
    for s in seasons:
        year = s["year"]
        yr_teams = sorted(teams_by_year.get(year, []), key=lambda t: (t["final_rank"] or 999))
        champion = next((t for t in yr_teams if t["final_rank"] == 1), None)
        runner_up = next((t for t in yr_teams if t["final_rank"] == 2), None)
        last_place = max(yr_teams, key=lambda t: t["final_rank"] or 0) if yr_teams else None
        points_champ = max(yr_teams, key=lambda t: t["points_for"] or 0) if yr_teams else None
        out.append({
            "year": year,
            "league_name": s["league_name"],
            "size": s["size"],
            "scoring_type": s["scoring_type"],
            "playoff_team_count": s["playoff_team_count"],
            "champion": champion,
            "runner_up": runner_up,
            "last_place": last_place,
            "points_champ": points_champ,
            "teams": yr_teams,
        })
    out.sort(key=lambda s: -s["year"])
    return out


def build_records(teams):
    scored = [t for t in teams if t["points_for"]]
    if not scored:
        return {}
    highest = max(scored, key=lambda t: t["points_for"])
    lowest = min(scored, key=lambda t: t["points_for"])
    best_record = max(teams, key=lambda t: ((t["wins"] or 0) - (t["losses"] or 0)))
    worst_record = min(teams, key=lambda t: ((t["wins"] or 0) - (t["losses"] or 0)))
    return {
        "highest_single_season_points": highest,
        "lowest_single_season_points": lowest,
        "best_single_season_record": best_record,
        "worst_single_season_record": worst_record,
        "note": "Weekly/matchup-level records (highest single game, longest streak, "
                "head-to-head) aren't available — ESPN stopped serving that data for "
                "completed seasons. See README's Known limitation section.",
    }


def merge_managers(managers_cfg, all_time_standings):
    standings_by_key = {b["key"]: b for b in all_time_standings}
    merged = []
    for m in managers_cfg:
        stats = standings_by_key.get(m["id"], {
            "wins": 0, "losses": 0, "ties": 0, "points_for": 0.0,
            "points_against": 0.0, "championships": 0, "runner_ups": 0,
            "wall_of_shame": 0, "seasons_played": 0, "win_pct": 0.0,
        })
        merged.append({**m, "stats": stats})
    return merged


def main():
    seasons, teams, divisions, owners = fetch_db()
    managers_cfg = load_json(CONTENT_DIR / "managers.json")["managers"]
    league_info = load_json(CONTENT_DIR / "league_info.json")
    # Default every flag to off so a missing key in league_info.json fails
    # closed (hides content) rather than open (accidentally publishing a
    # placeholder section).
    default_visibility = {
        "rivalries": False,
        "futures_ballot": False,
        "tribute": False,
        "draft_countdown": False,
        "show_ops_details": False,
        "show_manager_bios": False,
    }
    league_info["section_visibility"] = {
        **default_visibility,
        **league_info.get("section_visibility", {}),
    }

    by_alias, by_swid = build_manager_lookup(managers_cfg)
    all_time_standings = build_all_time_standings(teams, by_alias, by_swid)
    seasons_view = build_seasons_view(seasons, teams, divisions)
    records = build_records(teams)
    managers_view = merge_managers(managers_cfg, all_time_standings)

    current_season = seasons_view[0] if seasons_view else None

    league_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "league": {
            "name": seasons[-1]["league_name"] if seasons else "La Razita",
            "founded": min((s["year"] for s in seasons), default=None),
            "years": sorted(s["year"] for s in seasons),
        },
        "current_season": current_season,
        "seasons": seasons_view,
        "wall_of_shame": [s["last_place"] for s in seasons_view if s["last_place"]],
        "all_time_standings": all_time_standings,
        "records": records,
        "managers": managers_view,
        "league_info": league_info,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "data").mkdir(parents=True, exist_ok=True)

    with open(OUT_DIR / "data" / "league_data.json", "w", encoding="utf-8") as f:
        json.dump(league_data, f, indent=2, default=str)

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    # {{ value|commas }} -> "11,676.9" — thousands separator + 1 decimal place.
    env.filters["commas"] = lambda v: "{:,.1f}".format(v or 0)
    template = env.get_template("index.html")
    # Escape "</" so the inline JSON can't accidentally close the <script> tag early.
    safe_json = json.dumps(league_data, default=str).replace("</", "<\\/")
    html = template.render(data=league_data, data_json=safe_json)
    with open(OUT_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(html)

    static_out = OUT_DIR / "static"
    # Merge-copy rather than rmtree+copytree: on Windows/OneDrive the old
    # folder can be transiently locked (sync, an open preview server, etc.)
    # and rmtree throws PermissionError. dirs_exist_ok just overwrites files.
    shutil.copytree(STATIC_DIR, static_out, dirs_exist_ok=True)

    print("=== Build summary ===")
    print(f"  Seasons:  {len(seasons_view)}")
    print(f"  Teams:    {len(teams)}")
    print(f"  Managers: {len(managers_view)}")
    print(f"  All-time standings entries: {len(all_time_standings)}")
    print(f"\nOutput: {OUT_DIR}")


if __name__ == "__main__":
    main()
