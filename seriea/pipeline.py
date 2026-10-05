"""Fit the model at a set of cut-off matchdays and save everything to disk."""
from __future__ import annotations

import json
import time
import warnings
from pathlib import Path

import arviz as az
import numpy as np
import pandas as pd

from . import model as M
from . import simulate as S

warnings.filterwarnings("ignore", category=FutureWarning)


def standings(df: pd.DataFrame, season: str, m: int | None = None) -> pd.DataFrame:
    """Real table of `season` after matchday m (all played matches if m is None)."""
    cur = df[(df.season == season) & df.played]
    if m is not None:
        cur = cur[cur.matchweek <= m]
    teams = pd.unique(df[df.season == season][["home_team", "away_team"]].values.ravel())
    rows = []
    for t in teams:
        d = cur[(cur.home_team == t) | (cur.away_team == t)]
        gf = np.where(d.home_team == t, d.home_gol, d.away_gol).astype(int)
        ga = np.where(d.home_team == t, d.away_gol, d.home_gol).astype(int)
        rows.append(dict(team=t, played=len(d), w=int((gf > ga).sum()), d=int((gf == ga).sum()),
                         l=int((gf < ga).sum()), gf=int(gf.sum()), ga=int(ga.sum()),
                         pts=int(3 * (gf > ga).sum() + (gf == ga).sum())))
    tab = pd.DataFrame(rows)
    tab["gd"] = tab.gf - tab.ga
    return tab.sort_values(["pts", "gd", "gf"], ascending=False).reset_index(drop=True)


def run(df: pd.DataFrame, season: str, cutoffs, outdir, draws=2000, tune=1500, chains=4,
        seed=1, error_floor=True, log=print):
    out = Path(outdir)
    (out / "posteriors").mkdir(parents=True, exist_ok=True)
    summary, meta = [], {"season": season, "cutoffs": list(cutoffs), "fits": {}}

    for m in cutoffs:
        su = M.fit_setup(df, season, m)
        log(f"[{season}] m = {m}: {len(su.fit)} matches in the likelihood, {len(su.todo)} to simulate")
        t0 = time.time()
        idata = M.fit(su, draws=draws, tune=tune, chains=chains, seed=seed)
        secs = time.time() - t0
        idata.to_netcdf(out / "posteriors" / f"posterior_m{m}.nc")

        # diagnostics
        n_div = int(idata.sample_stats.diverging.sum())
        rh = az.rhat(idata)
        max_rhat = float(max(rh[v].max() for v in rh.data_vars))
        params = az.summary(idata, var_names=M.GLOBALS, hdi_prob=0.95)
        params.to_csv(out / f"params_m{m}.csv")

        # strengths of the target season
        post = idata.posterior
        k = su.target - 1
        att = post["att"].values.reshape(-1, su.n_teams, su.target)[:, :, k]
        dfn = post["def"].values.reshape(-1, su.n_teams, su.target)[:, :, k]
        teams = np.sort(pd.unique(pd.concat([su.done.h, su.todo.h]))) - 1
        pd.DataFrame({"team": su.team_names.loc[teams + 1].values,
                      "att_mean": att[:, teams].mean(0), "att_sd": att[:, teams].std(0),
                      "att_lo90": np.percentile(att[:, teams], 5, 0), "att_hi90": np.percentile(att[:, teams], 95, 0),
                      "def_mean": dfn[:, teams].mean(0), "def_sd": dfn[:, teams].std(0),
                      "def_lo90": np.percentile(dfn[:, teams], 5, 0), "def_hi90": np.percentile(dfn[:, teams], 95, 0),
                      }).to_csv(out / f"strengths_m{m}.csv", index=False)

        # simulation with every draw
        sim = S.simulate(su, idata, cumulative=(m == 0))
        actual = S.actual_points(su)
        tab = S.forecast_table(sim, actual)
        tab.to_csv(out / f"forecast_m{m}.csv", index=False)
        S.rank_probabilities(sim).to_csv(out / f"rank_probs_m{m}.csv")
        np.savez_compressed(out / f"points_m{m}.npz", points=sim["points"].astype(np.int16),
                            names=np.array([str(x) for x in sim["names"]], dtype="U32"))
        if m == 0:
            np.savez_compressed(out / "cumulative_m0.npz", mean=sim["cum_mean"], lo=sim["cum_lo"],
                                hi=sim["cum_hi"], names=np.array([str(x) for x in sim["names"]], dtype="U32"),
                                actual=S.actual_cumulative(su))

        row = dict(m=m, matches_used=len(su.fit), matches_simulated=len(su.todo),
                   n_sims=int(sim["points"].shape[0]), divergences=n_div,
                   max_rhat=round(max_rhat, 4), seconds=round(secs))
        if actual is not None:
            row.update({k2: round(v, 4) for k2, v in S.accuracy(tab).items()})
        summary.append(row)
        log(f"    {row}")
        meta["fits"][m] = row

    pd.DataFrame(summary).to_csv(out / "summary.csv", index=False)
    standings(df, season).to_csv(out / "standings.csv", index=False)

    # error floor and title race: only for a finished season
    if error_floor and S.actual_points(M.fit_setup(df, season, max(cutoffs))) is not None:
        m_best = max(cutoffs)
        su = M.fit_setup(df, season, m_best)
        idata = az.from_netcdf(out / "posteriors" / f"posterior_m{m_best}.nc")
        floor = S.error_floor(su, idata)
        tab0 = pd.read_csv(out / f"forecast_m{min(cutoffs)}.csv")
        naive = float((tab0.actual - tab0.actual.mean()).abs().mean())
        mae0 = float(tab0.error.abs().mean())
        meta["error_floor"] = dict(naive=naive, model_m0=mae0, floor=floor["mae"],
                                   chance_sd=floor["sd"],
                                   gap_closed=(naive - mae0) / (naive - floor["mae"]),
                                   strengths_from_m=m_best)
        floor["title"].rename("p_title").to_csv(out / "title_race_fixed_strengths.csv")
        log(f"    error floor: {meta['error_floor']}")

    json.dump(meta, open(out / "meta.json", "w"), indent=2, default=float)
    return meta
