"""Forecast the Serie A 2026/27 table: before matchday 1 and after the matchdays played so far.

    python scripts/03_forecast_2026_27.py            # m = 0, standard cut-offs reached, latest matchday
    python scripts/03_forecast_2026_27.py 0 7        # only the cut-offs given

Writes results/2026-27/.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from seriea import data, pipeline  # noqa: E402

SEASON = "2026/2027"
df = data.load(ROOT / "data" / "seriea_2020_2027.csv")
done = data.complete_matchdays(df, SEASON)
if len(sys.argv) > 1:
    cutoffs = [int(x) for x in sys.argv[1:]]
else:
    cutoffs = sorted({0, done} | {c for c in (12, 19, 28) if c <= done})
print(f"{SEASON}: {done} complete matchdays, cut-offs {cutoffs}")
pipeline.run(df, SEASON, cutoffs, ROOT / "results" / "2026-27")
