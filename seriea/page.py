"""Build the forecast web page (docs/index.html, served by GitHub Pages)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent


def build(forecast_dir, backtest_dir, out, last_update="", repo="MB0mba/serie-a-bayesian-forecast"):
    fdir, bdir = Path(forecast_dir), Path(backtest_dir)
    summary = pd.read_csv(fdir / "summary.csv")
    m_now = int(summary.m.max())
    fc = pd.read_csv(fdir / f"forecast_m{m_now}.csv")
    pre = pd.read_csv(fdir / "forecast_m0.csv").set_index("team")
    probs = pd.read_csv(fdir / f"rank_probs_m{m_now}.csv", index_col=0)
    params = pd.read_csv(fdir / f"params_m{m_now}.csv", index_col=0)["mean"]
    table = pd.read_csv(fdir / "standings.csv").set_index("team")
    row_now = summary.set_index("m").loc[m_now]

    rows = []
    for _, r in fc.iterrows():
        t = r.team
        rows.append(dict(
            team=t, now_pts=int(table.loc[t, "pts"]), played=int(table.loc[t, "played"]),
            pred=round(r.predicted, 1), lo=int(r.lo90), hi=int(r.hi90),
            title=round(r.p_title, 4), top4=round(r.p_top4, 4), rel=round(r.p_relegation, 4),
            pre=round(float(pre.loc[t, "predicted"]), 1),
            pre_lo=int(pre.loc[t, "lo90"]), pre_hi=int(pre.loc[t, "hi90"]),
            pos=[round(float(x), 4) for x in probs.loc[t].values],
        ))

    track = None
    if (bdir / "meta.json").exists():
        meta = json.load(open(bdir / "meta.json"))
        bs = pd.read_csv(bdir / "summary.csv")
        ef = meta.get("error_floor", {})
        track = dict(rows=[dict(m=int(r.m), mae=r.mae, width=r.mean_width, coverage=r.coverage_90,
                                corr=r.correlation) for _, r in bs.iterrows()],
                     naive=ef.get("naive"), floor=ef.get("floor"), gap=ef.get("gap_closed"))

    data = dict(m=m_now, updated=last_update, n_sims=int(row_now.n_sims),
                divergences=int(row_now.divergences), max_rhat=round(float(row_now.max_rhat), 3),
                params=dict(home=round(params["home"], 3), rho=round(params["rho"], 3),
                            shock=round(params["sd_shock_att"], 3)),
                rows=rows, track=track)
    body = (HERE / "page_body.html").read_text(encoding="utf-8")
    body = body.replace("__DATA__", json.dumps(data, ensure_ascii=False)).replace("__REPO__", repo)
    html = (HERE / "page_template.html").read_text(encoding="utf-8").replace("__BODY__", body)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(html, encoding="utf-8")
    return data
