"""Posterior predictive simulation of the rest of a season.

Every posterior draw gives one set of scoring rates for the matches still to
play; goals are drawn from the Poisson, points (3/1/0) are added to those
already banked. All draws are used, so with 4 chains x 2000 draws there are
8000 simulated seasons.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .model import Setup, target_draws


def points(gh, ga, h, a, n_teams):
    """gh, ga: (R, n_matches) goals. Returns (R, n_teams) points."""
    P = np.zeros((gh.shape[0], n_teams))
    draw = (gh == ga) * 1
    np.add.at(P.T, h, ((gh > ga) * 3 + draw).T)
    np.add.at(P.T, a, ((ga > gh) * 3 + draw).T)
    return P


def _goals_for_against(gh, ga, h, a, n_teams):
    gf = np.zeros((gh.shape[0], n_teams)); gs = np.zeros_like(gf)
    np.add.at(gf.T, h, gh.T); np.add.at(gf.T, a, ga.T)
    np.add.at(gs.T, h, ga.T); np.add.at(gs.T, a, gh.T)
    return gf, gs


def _rank(total, gd, rng):
    """Rank by points, then goal difference, then at random."""
    key = total * 1000 + gd + rng.random(total.shape) * 0.1
    return (-key).argsort(axis=1).argsort(axis=1) + 1


def _season_teams(su: Setup):
    tgt = pd.concat([su.done, su.todo])
    return np.sort(pd.unique(pd.concat([tgt.h, tgt.a]))) - 1


def simulate(su: Setup, idata, seed=2, cumulative=False):
    att, dfn, mu, home = target_draws(su, idata)
    T = su.n_teams
    h, a = su.todo.h.values - 1, su.todo.a.values - 1
    lh = np.exp(mu[:, None] + home[:, None] + att[:, h] - dfn[:, a])
    la = np.exp(mu[:, None] + att[:, a] - dfn[:, h])
    rng = np.random.default_rng(seed)
    gh, ga = rng.poisson(lh), rng.poisson(la)

    d = su.done
    dh, da = d.h.values - 1, d.a.values - 1
    dgh, dga = d.home_gol.values.astype(int)[None], d.away_gol.values.astype(int)[None]
    banked = points(dgh, dga, dh, da, T)[0]
    bgf, bgs = _goals_for_against(dgh, dga, dh, da, T)

    pts = points(gh, ga, h, a, T) + banked
    gf, gs = _goals_for_against(gh, ga, h, a, T)
    gd = gf - gs + (bgf - bgs)[0]

    teams = _season_teams(su)
    out = dict(points=pts[:, teams], rank=_rank(pts[:, teams], gd[:, teams], rng),
               teams=teams, names=su.team_names.loc[teams + 1].values, banked=banked[teams])

    if cumulative:   # mean and 90% band of points after each matchday
        n_md = int(pd.concat([su.done, su.todo]).matchweek.max())
        C = np.zeros((gh.shape[0], T, n_md), dtype=np.float32)
        md = su.todo.matchweek.values - 1
        draw = (gh == ga)
        np.add.at(C, (slice(None), h, md), (gh > ga) * 3 + draw)
        np.add.at(C, (slice(None), a, md), (ga > gh) * 3 + draw)
        bmd = d.matchweek.values - 1
        Cb = np.zeros((T, n_md))
        np.add.at(Cb, (dh, bmd), ((dgh > dga) * 3 + (dgh == dga))[0])
        np.add.at(Cb, (da, bmd), ((dga > dgh) * 3 + (dgh == dga))[0])
        C = np.cumsum(C + Cb, axis=2)[:, teams, :]
        out["cum_mean"] = C.mean(0)
        out["cum_lo"] = np.percentile(C, 5, axis=0)
        out["cum_hi"] = np.percentile(C, 95, axis=0)
    return out


def actual_points(su: Setup):
    """Final points of each team, if the target season is complete (else None)."""
    tgt = pd.concat([su.done, su.todo])
    if not tgt.played.all():
        return None
    P = points(tgt.home_gol.values[None].astype(int), tgt.away_gol.values[None].astype(int),
               tgt.h.values - 1, tgt.a.values - 1, su.n_teams)[0]
    return P[_season_teams(su)]


def actual_cumulative(su: Setup):
    tgt = pd.concat([su.done, su.todo])
    tgt = tgt[tgt.played]
    teams = _season_teams(su)
    n_md = int(pd.concat([su.done, su.todo]).matchweek.max())
    C = np.zeros((su.n_teams, n_md))
    gh, ga = tgt.home_gol.values.astype(int), tgt.away_gol.values.astype(int)
    md = tgt.matchweek.values - 1
    np.add.at(C, (tgt.h.values - 1, md), (gh > ga) * 3 + (gh == ga))
    np.add.at(C, (tgt.a.values - 1, md), (ga > gh) * 3 + (gh == ga))
    return np.cumsum(C, axis=1)[teams]


def forecast_table(sim, actual=None) -> pd.DataFrame:
    P, R = sim["points"], sim["rank"]
    n = P.shape[1]
    tab = pd.DataFrame({
        "team": sim["names"],
        "banked": sim["banked"].astype(int),
        "predicted": P.mean(0),
        "lo90": np.percentile(P, 5, axis=0),
        "hi90": np.percentile(P, 95, axis=0),
        "p_title": (R == 1).mean(0),
        "p_top4": (R <= 4).mean(0),
        "p_relegation": (R > n - 3).mean(0),
        "exp_rank": R.mean(0),
    })
    if actual is not None:
        tab["actual"] = actual
        tab["error"] = tab.predicted - tab.actual
        tab["inside"] = (tab.actual >= tab.lo90) & (tab.actual <= tab.hi90)
    return tab.sort_values("predicted", ascending=False).reset_index(drop=True)


def rank_probabilities(sim) -> pd.DataFrame:
    R = sim["rank"]
    n = R.shape[1]
    probs = pd.DataFrame([(R == r).mean(0) for r in range(1, n + 1)], columns=sim["names"]).T
    probs.columns = range(1, n + 1)
    return probs


def accuracy(tab: pd.DataFrame) -> dict:
    return dict(correlation=float(np.corrcoef(tab.predicted, tab.actual)[0, 1]),
                mae=float(tab.error.abs().mean()),
                mean_width=float((tab.hi90 - tab.lo90).mean()),
                coverage_90=float(tab.inside.mean()))


def error_floor(su_full: Setup, idata, n=8000, seed=3):
    """Replay the whole target season with strengths fixed at their posterior means.

    The spread that survives is Poisson randomness alone: the error no model of
    this family could remove. `su_full` should be a late cut-off (e.g. m = 28),
    whose strengths are the best available estimate of the real ones.
    """
    att, dfn, mu, home = (x.mean(0) for x in target_draws(su_full, idata))
    tgt = pd.concat([su_full.done, su_full.todo])
    h, a = tgt.h.values - 1, tgt.a.values - 1
    lh = np.exp(mu + home + att[h] - dfn[a])
    la = np.exp(mu + att[a] - dfn[h])
    rng = np.random.default_rng(seed)
    gh = rng.poisson(np.broadcast_to(lh, (n, len(lh))))
    ga = rng.poisson(np.broadcast_to(la, (n, len(la))))
    teams = _season_teams(su_full)
    P = points(gh, ga, h, a, su_full.n_teams)[:, teams]
    gf, gs = _goals_for_against(gh, ga, h, a, su_full.n_teams)
    R = _rank(P, (gf - gs)[:, teams], rng)
    names = su_full.team_names.loc[teams + 1].values
    return dict(mae=float(np.abs(P - P.mean(0)).mean()),
                sd=float(P.std(0).mean()),
                title=pd.Series((R == 1).mean(0), index=names).sort_values(ascending=False))
