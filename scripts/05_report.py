"""Update the web page (docs/index.html) and the results tables in README.md.

    python scripts/05_report.py
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from seriea import page  # noqa: E402

FC, BT = ROOT / "results" / "2026-27", ROOT / "results" / "2025-26"
updated = (ROOT / "data" / "LAST_UPDATE").read_text().strip() if (ROOT / "data" / "LAST_UPDATE").exists() else ""
page.build(FC, BT, ROOT / "docs" / "index.html", last_update=updated)
(ROOT / "docs" / ".nojekyll").touch()


def pct(p):
    return "–" if p < 0.005 else (">99%" if p > 0.995 else f"{p:.0%}")


def forecast_md():
    s = pd.read_csv(FC / "summary.csv")
    m = int(s.m.max())
    tab = pd.read_csv(FC / f"forecast_m{m}.csv")
    pre = pd.read_csv(FC / "forecast_m0.csv").set_index("team")
    when = "before matchday 1" if m == 0 else f"after matchday {m} (results up to {updated})"
    lines = [f"**Forecast {when}** — {int(s.set_index('m').loc[m, 'n_sims']):,} simulated seasons.", "",
             "| # | Team | Points now | Expected points | 90% interval | Title | Top 4 | Relegation |"
             + (" Pre-season forecast |" if m > 0 else ""),
             "|--:|:--|--:|--:|:-:|--:|--:|--:|" + ("--:|" if m > 0 else "")]
    for i, r in tab.iterrows():
        row = (f"| {i + 1} | {r.team} | {r.banked} | {r.predicted:.1f} | {r.lo90:.0f}–{r.hi90:.0f} | "
               f"{pct(r.p_title)} | {pct(r.p_top4)} | {pct(r.p_relegation)} |")
        if m > 0:
            row += f" {pre.loc[r.team, 'predicted']:.1f} |"
        lines.append(row)
    return "\n".join(lines)


def backtest_md():
    s = pd.read_csv(BT / "summary.csv")
    meta = json.load(open(BT / "meta.json"))
    ef = meta["error_floor"]
    lines = ["| Forecast made | Matches used | Matches simulated | Correlation | Mean abs. error | 90% interval width | Coverage |",
             "|:--|--:|--:|--:|--:|--:|--:|"]
    for _, r in s.iterrows():
        when = "before matchday 1" if r.m == 0 else f"after matchday {int(r.m)}"
        lines.append(f"| {when} | {int(r.matches_used)} | {int(r.matches_simulated)} | {r.correlation:.3f} | "
                     f"{r.mae:.2f} | {r.mean_width:.1f} | {r.coverage_90:.2f} |")
    lines += ["", f"Naive benchmark (every team at the league average): **{ef['naive']:.2f}** points. "
              f"Error left by chance alone (strengths fixed at their after-matchday-{ef['strengths_from_m']} "
              f"estimates, season replayed 8,000 times): **{ef['floor']:.2f}** points. "
              f"The pre-season model closes **{ef['gap_closed']:.0%}** of the gap that can be closed."]
    return "\n".join(lines)


readme = ROOT / "README.md"
text = readme.read_text(encoding="utf-8")
for name, fn, folder in [("forecast", forecast_md, FC), ("backtest", backtest_md, BT)]:
    if (folder / "summary.csv").exists():
        text = re.sub(rf"<!-- {name}:start -->.*?<!-- {name}:end -->",
                      f"<!-- {name}:start -->\n{fn()}\n<!-- {name}:end -->", text, flags=re.S)
readme.write_text(text, encoding="utf-8")
print("updated docs/index.html and README.md")
