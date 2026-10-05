"""Download and parse Serie A results from openfootball.

openfootball (https://github.com/openfootball/italy) is a public-domain,
plain-text archive of Serie A results, updated weekly. Over 2020/21-2025/26 it
matches FBref match by match (2280 matches, no difference in goals or
matchday), which is checked by `check_against`.

The data set has one row per match: season, matchday, home and away team,
goals, a global team id and `played` (False for fixtures not yet played).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pandas as pd

REPO_URL = "https://github.com/openfootball/italy.git"
SEASONS = ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25", "2025-26", "2026-27"]

# openfootball names -> short names
NAMES = {
    "ACF Fiorentina": "Fiorentina", "Hellas Verona FC": "Hellas Verona", "Verona": "Hellas Verona",
    "Genoa CFC": "Genoa", "Juventus FC": "Juventus", "Parma Calcio 1913": "Parma",
    "US Sassuolo Calcio": "Sassuolo", "AC Milan": "Milan", "Cagliari Calcio": "Cagliari",
    "FC Internazionale Milano": "Inter", "UC Sampdoria": "Sampdoria", "Torino FC": "Torino",
    "FC Crotone": "Crotone", "SSC Napoli": "Napoli", "AS Roma": "Roma", "Spezia Calcio": "Spezia",
    "Bologna FC 1909": "Bologna", "Benevento Calcio": "Benevento", "SS Lazio": "Lazio",
    "Udinese Calcio": "Udinese", "Atalanta BC": "Atalanta", "Empoli FC": "Empoli",
    "US Salernitana 1919": "Salernitana", "Venezia FC": "Venezia", "US Lecce": "Lecce",
    "AC Monza": "Monza", "US Cremonese": "Cremonese", "Frosinone Calcio": "Frosinone",
    "Como 1907": "Como", "AC Pisa 1909": "Pisa", "Pisa SC": "Pisa",
}
SHORT = set(NAMES.values())


def team_name(raw: str) -> str:
    raw = raw.strip()
    if raw in NAMES:
        return NAMES[raw]
    if raw in SHORT:
        return raw
    for suffix in (" FC", " Calcio", " SC", " BC"):
        if raw.endswith(suffix) and raw[: -len(suffix)] in SHORT:
            return raw[: -len(suffix)]
    raise KeyError(f"unknown team name {raw!r}: add it to seriea.data.NAMES")


def download(repo_dir: Path) -> str:
    """Clone the archive, or pull it if already present. Returns the date of the last update."""
    repo_dir = Path(repo_dir)
    if (repo_dir / ".git").exists():
        subprocess.run(["git", "-C", str(repo_dir), "pull", "-q"], check=True)
    else:
        subprocess.run(["git", "clone", "-q", "--depth", "1", REPO_URL, str(repo_dir)], check=True)
    out = subprocess.run(["git", "-C", str(repo_dir), "log", "-1", "--format=%cs"],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


# Three layouts have been used over the years:
#   "18:00  ACF Fiorentina   1-0 (0-0)  Torino FC"            2020/21 - 2023/24
#   "18:30  Genoa CFC  v FC Internazionale Milano  2-2 (1-1)"  2024/25, 2026/27
#   "16:30   Sassuolo  0-2 (0-1)  Napoli"  + scorer lines      2025/26
# A fixture not yet played has no score. The matchday comes from the section header.
HEADER = re.compile(r"▪\s*(?:Matchday|Regular Season\s*-)\s*(\d+)")
TIME = re.compile(r"^\d{1,2}[:.]\d{2}\s+")
WITH_V = re.compile(r"^(?P<h>.+?)\s+v\s+(?P<a>.+?)(?:\s{2,}(?P<gh>\d+)-(?P<ga>\d+)\b.*)?$")
SCORE_MID = re.compile(
    r"^(?P<h>.+?)\s+(?P<gh>\d+)-(?P<ga>\d+)(?:\s+\(\d+-\d+\))?\s+(?P<a>[^\[(]+?)\s*(?:\[.*\])?$")
WEEKDAY = re.compile(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b")


def parse_season(path: Path) -> pd.DataFrame:
    rows, matchday, depth = [], None, 0
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if depth > 0 or s.startswith("("):            # goal scorers (2025/26 layout)
            depth = max(depth + s.count("(") - s.count(")"), 0)
            continue
        m = HEADER.search(s)
        if m:
            matchday = int(m.group(1))
            continue
        if not s or s.startswith(("#", "=")) or WEEKDAY.match(s) or matchday is None:
            continue
        s = TIME.sub("", s)
        m = WITH_V.match(s) if re.search(r"\sv\s", s) else SCORE_MID.match(s)
        if not m:
            raise ValueError(f"{path}: cannot parse line {line!r}")
        gh, ga = m.group("gh"), m.group("ga")
        rows.append(dict(matchweek=matchday,
                         home_team=team_name(m.group("h")), away_team=team_name(m.group("a")),
                         home_gol=int(gh) if gh is not None else pd.NA,
                         away_gol=int(ga) if ga is not None else pd.NA,
                         played=gh is not None))
    return pd.DataFrame(rows)


def season_label(s: str) -> str:
    """'2020-21' -> '2020/2021'"""
    return f"{s[:4]}/{int(s[:4]) + 1}"


def build(repo_dir: Path, seasons=SEASONS) -> pd.DataFrame:
    parts = []
    for s in seasons:
        d = parse_season(Path(repo_dir) / s / "1-seriea.txt")
        if len(d) != 380:
            raise ValueError(f"{s}: {len(d)} matches instead of 380")
        d.insert(0, "season", season_label(s))
        parts.append(d)
    df = pd.concat(parts, ignore_index=True)
    # global team ids, by order of first appearance
    order = pd.unique(df[["home_team", "away_team"]].values.ravel())
    ids = {t: i + 1 for i, t in enumerate(order)}
    df["h"] = df.home_team.map(ids)
    df["a"] = df.away_team.map(ids)
    df["home_gol"] = df.home_gol.astype("Int64")
    df["away_gol"] = df.away_gol.astype("Int64")
    return df


def check_against(df: pd.DataFrame, other_csv: Path) -> dict:
    """Compare with another results file (e.g. the FBref one used for the course project)."""
    old = pd.read_csv(other_csv)
    m = old.merge(df, on=["season", "home_team", "away_team"], how="left", suffixes=("_ref", ""))
    missing = int(m.home_gol.isna().sum())
    ok = m.dropna(subset=["home_gol"])
    return dict(
        matches=len(old), missing=missing,
        different_goals=int(((ok.home_gol_ref != ok.home_gol) | (ok.away_gol_ref != ok.away_gol)).sum()),
        different_matchday=int((ok.matchweek_ref != ok.matchweek).sum()),
    )


def load(path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["played"] = df["played"].astype(bool)
    return df


def complete_matchdays(df: pd.DataFrame, season: str) -> int:
    """Number of the last matchday of `season` whose matches have all been played."""
    cur = df[df.season == season]
    done = cur.groupby("matchweek").played.all()
    done = done[done]
    # the last matchday k such that matchdays 1..k are all complete
    k = 0
    while (k + 1) in done.index:
        k += 1
    return k
