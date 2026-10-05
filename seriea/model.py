"""Dynamic hierarchical Poisson model for Serie A (after Baio and Blangiardo, 2010).

For match i, played in season s(i) between home team h(i) and away team a(i):

    y_home[i] ~ Poisson(lambda_home[i]),   y_away[i] ~ Poisson(lambda_away[i])
    log lambda_home[i] = mu[s(i)] + home + att[h(i), s(i)] - def[a(i), s(i)]
    log lambda_away[i] = mu[s(i)]        + att[a(i), s(i)] - def[h(i), s(i)]

Team strengths evolve across seasons k with a first-order autoregression:

    att[t, 1] ~ N(0, sigma_att^2)
    att[t, k] ~ N(rho * att[t, k-1] + entry * is_entry[t, k], sd_shock_att^2),   k >= 2
    sd_shock_att = sigma_att * sqrt(1 - rho^2)        (keeps the spread constant)

and the same for def; mu[k] ~ N(mu0, sigma_mu^2). Priors:

    home, mu0 ~ N(0, 100^2)    rho ~ U(0, 1)    entry ~ N(0, 0.5^2)
    tau_att, tau_def, tau_mu ~ Gamma(0.01, 0.01),   sigma = 1 / sqrt(tau)

Sampled with NUTS, the strengths are written non-centred:
att[t, k] = rho * att[t, k-1] + entry * is_entry[t, k] + sd_shock * z[t, k],
z ~ N(0, 1). It is the same distribution, in a form NUTS explores more easily.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import pandas as pd
import pymc as pm
import pytensor.tensor as pt


@dataclass
class Setup:
    """Everything one fit needs: forecast season `target` after `m` of its matchdays."""
    fit: pd.DataFrame        # matches entering the likelihood
    done: pd.DataFrame       # target-season matches already played (points are banked)
    todo: pd.DataFrame       # target-season matches to simulate
    seasons: list            # season labels; index k-1
    target: int              # target season, 1-based
    n_teams: int
    is_entry: np.ndarray     # (n_teams, n_seasons)
    team_names: pd.Series    # index: team id
    m: int


def fit_setup(df: pd.DataFrame, target_season: str, m: int) -> Setup:
    seasons = sorted(df.season.unique())
    seasons = seasons[: seasons.index(target_season) + 1]
    df = df[df.season.isin(seasons)].copy()
    df["s"] = df.season.map({s: i + 1 for i, s in enumerate(seasons)})
    target = len(seasons)

    names = pd.concat([df[["h", "home_team"]].set_axis(["id", "team"], axis=1),
                       df[["a", "away_team"]].set_axis(["id", "team"], axis=1)])
    names = names.drop_duplicates("id").set_index("id").team.sort_index()
    n_teams = int(names.index.max())

    # is_entry = 1 in the first season a team appears in the data (if not season 1)
    first = {t: df[(df.h == t) | (df.a == t)].s.min() for t in names.index}
    is_entry = np.zeros((n_teams, target))
    for t, k in first.items():
        if k > 1:
            is_entry[t - 1, k - 1] = 1

    tgt = df[df.s == target]
    done = tgt[(tgt.matchweek <= m) & tgt.played]
    todo = tgt[~tgt.index.isin(done.index)]
    fit = pd.concat([df[(df.s < target) & df.played], done])
    return Setup(fit, done, todo, seasons, target, n_teams, is_entry, names, m)


def build_model(su: Setup) -> pm.Model:
    f = su.fit
    h, a, s = f.h.values - 1, f.a.values - 1, f.s.values - 1
    T, K = su.n_teams, su.target

    with pm.Model() as model:
        home = pm.Normal("home", 0, 100)
        mu0 = pm.Normal("mu0", 0, 100)
        rho = pm.Uniform("rho", 0, 1)
        entry = pm.Normal("entry", 0, 0.5)
        tau_att = pm.Gamma("tau_att", alpha=0.01, beta=0.01)
        tau_def = pm.Gamma("tau_def", alpha=0.01, beta=0.01)
        tau_mu = pm.Gamma("tau_mu", alpha=0.01, beta=0.01)

        sigma_att = pm.Deterministic("sigma_att", 1 / pt.sqrt(tau_att))
        sigma_def = pm.Deterministic("sigma_def", 1 / pt.sqrt(tau_def))
        sigma_mu = 1 / pt.sqrt(tau_mu)
        sd_shock_att = pm.Deterministic("sd_shock_att", sigma_att * pt.sqrt(1 - rho**2))
        sd_shock_def = pm.Deterministic("sd_shock_def", sigma_def * pt.sqrt(1 - rho**2))

        z_att = pm.Normal("z_att", 0, 1, shape=(T, K))
        z_def = pm.Normal("z_def", 0, 1, shape=(T, K))
        z_mu = pm.Normal("z_mu", 0, 1, shape=K)
        E = pt.as_tensor_variable(su.is_entry)

        att_cols = [sigma_att * z_att[:, 0]]
        def_cols = [sigma_def * z_def[:, 0]]
        for k in range(1, K):
            att_cols.append(rho * att_cols[-1] + entry * E[:, k] + sd_shock_att * z_att[:, k])
            def_cols.append(rho * def_cols[-1] + entry * E[:, k] + sd_shock_def * z_def[:, k])
        att = pm.Deterministic("att", pt.stack(att_cols, axis=1))
        dfn = pm.Deterministic("def", pt.stack(def_cols, axis=1))
        mu = pm.Deterministic("mu", mu0 + sigma_mu * z_mu)

        pm.Poisson("home_gol", mu=pt.exp(mu[s] + home + att[h, s] - dfn[a, s]),
                   observed=f.home_gol.values.astype(int))
        pm.Poisson("away_gol", mu=pt.exp(mu[s] + att[a, s] - dfn[h, s]),
                   observed=f.away_gol.values.astype(int))
    return model


GLOBALS = ["home", "mu0", "rho", "entry", "tau_att", "tau_def", "tau_mu", "sigma_att", "sd_shock_att"]


def fit(su: Setup, draws=2000, tune=1500, chains=4, seed=1, cores=None, progressbar=False):
    cores = cores or min(chains, os.cpu_count() or 1)
    with build_model(su):
        return pm.sample(draws=draws, tune=tune, chains=chains, cores=cores, random_seed=seed,
                         target_accept=0.95, progressbar=progressbar,
                         var_names=GLOBALS + ["att", "def", "mu"])


def target_draws(su: Setup, idata):
    """All posterior draws of the quantities needed to simulate the target season."""
    post = idata.posterior
    att = post["att"].values.reshape(-1, su.n_teams, su.target)[:, :, su.target - 1]
    dfn = post["def"].values.reshape(-1, su.n_teams, su.target)[:, :, su.target - 1]
    mu = post["mu"].values.reshape(-1, su.target)[:, su.target - 1]
    home = post["home"].values.reshape(-1)
    return att, dfn, mu, home
