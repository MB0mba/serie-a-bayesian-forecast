"""All figures of the README, from the files in results/.

    python scripts/04_figures.py
"""
import json
import sys
from pathlib import Path

import arviz as az
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from seriea import data, plots  # noqa: E402

RES = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results"
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)
df = data.load(ROOT / "data" / "seriea_2020_2027.csv")

# ---- data
past = df[(df.season <= "2025/2026") & df.played]
plots.poisson_fit(past, FIG / "poisson_fit.png")

# ---- backtest 2025/26
bt = RES / "2025-26"
if (bt / "summary.csv").exists():
    meta = json.load(open(bt / "meta.json"))
    summary = pd.read_csv(bt / "summary.csv")
    tabs = {int(m): pd.read_csv(bt / f"forecast_m{m}.csv") for m in summary.m}
    post0 = bt / "posteriors" / "posterior_m0.nc"
    if post0.exists():
        plots.posteriors(az.from_netcdf(post0), FIG / "backtest_posteriors.png")
    plots.strengths(pd.read_csv(bt / "strengths_m0.csv"), FIG / "backtest_strengths.png",
                    "Team strengths for 2025/26 estimated before matchday 1 (posterior mean and 90% interval)")
    plots.predicted_vs_actual(tabs[0], FIG / "backtest_predicted_vs_actual.png",
                              "2025/26: forecast before matchday 1 vs final points")
    ef = meta.get("error_floor")
    if ef:
        plots.accuracy_by_cutoff(summary, ef["naive"], FIG / "backtest_accuracy_by_cutoff.png")
        plots.error_floor(ef["naive"], ef["model_m0"], ef["floor"], FIG / "backtest_error_floor.png")
        title = pd.read_csv(bt / "title_race_fixed_strengths.csv", index_col=0).p_title
        plots.title_race(title, FIG / "backtest_title_race.png",
                         "2025/26 replayed with the same strengths: who wins the title")
    if len(tabs) > 1:
        plots.every_team(tabs, FIG / "backtest_every_team.png")
    cum = dict(np.load(bt / "cumulative_m0.npz", allow_pickle=True))
    plots.cumulative_teams(cum, ["Fiorentina", "Como", "Hellas Verona"], FIG / "backtest_three_misses.png",
                           coach_changes={"Fiorentina": 10.5, "Hellas Verona": 23.5})

# ---- forecast 2026/27
fc = RES / "2026-27"
if (fc / "summary.csv").exists():
    summary = pd.read_csv(fc / "summary.csv")
    m = int(summary.m.max())
    tab = pd.read_csv(fc / f"forecast_m{m}.csv")
    when = "before matchday 1" if m == 0 else f"after matchday {m}"
    plots.forecast_strip(tab, FIG / "forecast_2026_27.png", f"Serie A 2026/27: final table forecast {when}")
    probs = pd.read_csv(fc / f"rank_probs_m{m}.csv", index_col=0)
    plots.position_heatmap(probs, list(tab.team), FIG / "forecast_2026_27_positions.png",
                           f"Serie A 2026/27: probability of each final position ({when}, %)")
print("figures written to", FIG)
