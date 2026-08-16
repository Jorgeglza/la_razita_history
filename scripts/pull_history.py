"""
Pull all available ESPN Fantasy Football data for a league's past (completed) seasons.

IMPORTANT / KNOWN LIMITATION:
As of an ESPN API change (~Aug 2025), completed/past seasons no longer expose
deep data (weekly matchups/schedule, per-player box scores, draft picks,
transactions) through the API -- confirmed by testing every documented view
(mMatchupScore, mBoxscore, mRoster, mDraftDetail, mTransactions2, mScoreboard,
mSchedule, mLiveScoring) against both the `leagues` and `leagueHistory`
endpoints, and by confirming the ESPN website itself no longer renders old
box score pages. Only summary data survives for past seasons:
  - final standings (W/L/T, points for/against totals, final rank, seed)
  - league settings (scoring rules, roster rules, playoff format, size)
  - team/division/owner metadata

This script pulls everything that IS still available for the given years.

Auth note: the SWID cookie's curly braces MUST be URL-encoded (%7B / %7D) in
the Cookie header or ESPN's API silently 404s every request. This is the fix
for the "League does not exist" / "Not Found" errors seen with raw braces.
"""
import json
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR / "config.json"
DATA_DIR = SCRIPT_DIR.parent / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "fantasy_league.db"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_cookie_header(espn_s2: str, swid: str) -> str:
    # SWID braces MUST be percent-encoded or ESPN's cookie parser rejects the request.
    swid_encoded = swid.replace("{", "%7B").replace("}", "%7D")
    return f"espn_s2={espn_s2}; SWID={swid_encoded}"


def fetch(url: str, cookie_header: str, retries: int = 3):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Cookie": cookie_header, "Accept": "application/json"})
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            last_err = f"HTTP {e.code}: {body[:300]}"
        except Exception as e:
            last_err = str(e)
        if attempt < retries:
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"Failed to fetch {url} -> {last_err}")


def pull_year(league_id: int, year: int, cookie_header: str) -> dict:
    """Pull everything available for one past season."""
    views = "&".join([f"view={v}" for v in ["mTeam", "mSettings", "mStandings", "mRoster"]])
    url = f"{BASE}/leagueHistory/{league_id}?seasonId={year}&{views}"
    data = fetch(url, cookie_header)
    if isinstance(data, list):
        data = data[0] if data else {}
    return data


def save_raw(year: int, data: dict):
    year_dir = RAW_DIR / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)
    with open(year_dir / "league_summary.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def init_db(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS seasons (
            year INTEGER PRIMARY KEY,
            league_name TEXT,
            size INTEGER,
            scoring_type TEXT,
            matchup_period_count INTEGER,
            playoff_team_count INTEGER,
            playoff_seeding_rule TEXT,
            first_scoring_period INTEGER,
            final_scoring_period INTEGER,
            is_public INTEGER,
            trade_deadline_ms INTEGER
        );

        CREATE TABLE IF NOT EXISTS divisions (
            year INTEGER,
            division_id INTEGER,
            division_name TEXT,
            PRIMARY KEY (year, division_id)
        );

        CREATE TABLE IF NOT EXISTS teams (
            year INTEGER,
            team_id INTEGER,
            team_name TEXT,
            abbrev TEXT,
            division_id INTEGER,
            logo_url TEXT,
            owners TEXT,
            playoff_seed INTEGER,
            final_rank INTEGER,
            wins INTEGER,
            losses INTEGER,
            ties INTEGER,
            points_for REAL,
            points_against REAL,
            waiver_rank INTEGER,
            PRIMARY KEY (year, team_id)
        );

        CREATE TABLE IF NOT EXISTS scoring_settings (
            year INTEGER,
            stat_id INTEGER,
            points REAL,
            is_reverse_item INTEGER,
            PRIMARY KEY (year, stat_id)
        );

        CREATE TABLE IF NOT EXISTS owners (
            swid TEXT PRIMARY KEY,
            display_name TEXT
        );
        """
    )
    conn.commit()


def upsert_season(conn, year, data):
    settings = data.get("settings", {})
    sched = settings.get("scheduleSettings", {})
    status = data.get("status", {})
    conn.execute(
        """INSERT INTO seasons (year, league_name, size, scoring_type, matchup_period_count,
            playoff_team_count, playoff_seeding_rule, first_scoring_period, final_scoring_period,
            is_public, trade_deadline_ms)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(year) DO UPDATE SET
             league_name=excluded.league_name, size=excluded.size, scoring_type=excluded.scoring_type,
             matchup_period_count=excluded.matchup_period_count, playoff_team_count=excluded.playoff_team_count,
             playoff_seeding_rule=excluded.playoff_seeding_rule, first_scoring_period=excluded.first_scoring_period,
             final_scoring_period=excluded.final_scoring_period, is_public=excluded.is_public,
             trade_deadline_ms=excluded.trade_deadline_ms
        """,
        (
            year,
            settings.get("name"),
            settings.get("size"),
            settings.get("scoringSettings", {}).get("scoringType"),
            sched.get("matchupPeriodCount"),
            sched.get("playoffTeamCount"),
            sched.get("playoffSeedingRule"),
            status.get("firstScoringPeriod"),
            status.get("finalScoringPeriod"),
            int(bool(settings.get("isPublic"))),
            settings.get("tradeSettings", {}).get("deadlineDate"),
        ),
    )

    for div in sched.get("divisions", []):
        conn.execute(
            """INSERT INTO divisions (year, division_id, division_name) VALUES (?,?,?)
               ON CONFLICT(year, division_id) DO UPDATE SET division_name=excluded.division_name""",
            (year, div.get("id"), div.get("name")),
        )

    for item in settings.get("scoringSettings", {}).get("scoringItems", []):
        conn.execute(
            """INSERT INTO scoring_settings (year, stat_id, points, is_reverse_item) VALUES (?,?,?,?)
               ON CONFLICT(year, stat_id) DO UPDATE SET points=excluded.points, is_reverse_item=excluded.is_reverse_item""",
            (year, item.get("statId"), item.get("points"), int(bool(item.get("isReverseItem")))),
        )


def upsert_teams(conn, year, data):
    for t in data.get("teams", []):
        record = t.get("record", {}).get("overall", {})
        owners = t.get("owners", [])
        conn.execute(
            """INSERT INTO teams (year, team_id, team_name, abbrev, division_id, logo_url, owners,
                playoff_seed, final_rank, wins, losses, ties, points_for, points_against, waiver_rank)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(year, team_id) DO UPDATE SET
                 team_name=excluded.team_name, abbrev=excluded.abbrev, division_id=excluded.division_id,
                 logo_url=excluded.logo_url, owners=excluded.owners, playoff_seed=excluded.playoff_seed,
                 final_rank=excluded.final_rank, wins=excluded.wins, losses=excluded.losses, ties=excluded.ties,
                 points_for=excluded.points_for, points_against=excluded.points_against, waiver_rank=excluded.waiver_rank
            """,
            (
                year,
                t.get("id"),
                t.get("name"),
                t.get("abbrev"),
                t.get("divisionId"),
                t.get("logo"),
                ",".join(owners),
                t.get("playoffSeed"),
                t.get("rankCalculatedFinal"),
                record.get("wins"),
                record.get("losses"),
                record.get("ties"),
                record.get("pointsFor"),
                record.get("pointsAgainst"),
                t.get("waiverRank"),
            ),
        )
        for swid in owners:
            conn.execute("INSERT OR IGNORE INTO owners (swid, display_name) VALUES (?, NULL)", (swid,))
        for m in data.get("members", []):
            conn.execute("INSERT OR IGNORE INTO owners (swid, display_name) VALUES (?, NULL)", (m.get("id"),))


def main():
    cfg = load_config()
    league_id = cfg["league_id"]
    cookie_header = build_cookie_header(cfg["espn_s2"], cfg["swid"])
    years = cfg["years"]

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    results = []
    for year in years:
        print(f"Pulling {year} ...", end=" ", flush=True)
        try:
            data = pull_year(league_id, year, cookie_header)
            save_raw(year, data)
            upsert_season(conn, year, data)
            upsert_teams(conn, year, data)
            conn.commit()
            n_teams = len(data.get("teams", []))
            print(f"OK ({n_teams} teams)")
            results.append((year, "OK", n_teams))
        except Exception as e:
            print(f"FAILED: {e}")
            results.append((year, f"FAILED: {e}", 0))
        time.sleep(0.5)

    conn.close()

    print("\n=== Summary ===")
    for year, status, n_teams in results:
        print(f"  {year}: {status}" + (f" - {n_teams} teams" if status == "OK" else ""))
    print(f"\nRaw JSON: {RAW_DIR}")
    print(f"SQLite DB: {DB_PATH}")


if __name__ == "__main__":
    main()
