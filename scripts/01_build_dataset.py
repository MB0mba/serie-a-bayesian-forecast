"""Download Serie A results 2020/21-2026/27 from openfootball and build data/seriea_2020_2027.csv.

    python scripts/01_build_dataset.py
    python scripts/01_build_dataset.py --check path/to/other_results.csv   # compare with another source

Run it again after every matchday: it pulls the latest results.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from seriea import data  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--check", type=Path, help="CSV with season, matchweek, home_team, away_team, home_gol, away_gol")
args = p.parse_args()

updated = data.download(ROOT / "data" / "openfootball")
df = data.build(ROOT / "data" / "openfootball")
df.to_csv(ROOT / "data" / "seriea_2020_2027.csv", index=False)
(ROOT / "data" / "LAST_UPDATE").write_text(updated + "\n")

print(f"openfootball last update: {updated}")
print(f"{len(df)} matches, {df.played.sum()} played, {df[['home_team', 'away_team']].stack().nunique()} teams")
for season, g in df.groupby("season"):
    print(f"  {season}: {g.played.sum():3d}/380 played, complete matchdays: "
          f"{data.complete_matchdays(df, season)}")
if args.check:
    print("check against", args.check, "->", data.check_against(df, args.check))
