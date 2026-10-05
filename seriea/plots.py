"""Figures, in one consistent style: thin marks, hairline grid, one hue per role."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

MODEL = "#2a78d6"        # the model
MODEL_SOFT = "#9ec5f4"   # its intervals
ACTUAL = "#eb6834"       # what really happened
GREY = "#898781"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.size": 10.5, "axes.titlesize": 12.5, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
    "figure.dpi": 110, "savefig.dpi": 160, "savefig.bbox": "tight",
})


def _save(fig, path):
    fig.savefig(path)
    plt.close(fig)


def poisson_fit(df, path):
    from scipy.stats import poisson
    y = np.r_[df.home_gol.astype(int), df.away_gol.astype(int)]
    lam, kmax = y.mean(), 6
    obs = np.bincount(np.minimum(y, kmax), minlength=kmax + 1) / len(y)
    poi = np.r_[poisson.pmf(np.arange(kmax), lam), 1 - poisson.cdf(kmax - 1, lam)]
    x = np.arange(kmax + 1)
    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax.bar(x - 0.19, obs, 0.36, color=MODEL, label=f"observed ({len(df)} matches)")
    ax.bar(x + 0.19, poi, 0.36, color=MODEL_SOFT, label=f"Poisson({lam:.2f})")
    ax.set_xticks(x, [*map(str, range(kmax)), f"{kmax}+"])
    ax.set_xlabel("goals scored by one team in one match"); ax.set_ylabel("share of team-matches")
    ax.grid(axis="x", visible=False); ax.legend()
    ax.set_title(f"Goals per team per match: variance/mean = {y.var(ddof=1) / lam:.3f}")
    _save(fig, path)


def posteriors(idata, path):
    fig, axes = plt.subplots(1, 3, figsize=(10, 3))
    for ax, p, lab in zip(axes, ["home", "rho", "entry"], ["home advantage", "persistence ρ", "entry effect"]):
        v = idata.posterior[p].values.ravel()
        ax.hist(v, bins=60, color=MODEL_SOFT, edgecolor=SURFACE, linewidth=0.3)
        lo, hi = np.percentile(v, [2.5, 97.5])
        ax.axvline(v.mean(), color=MODEL, lw=2)
        for q in (lo, hi):
            ax.axvline(q, color=GREY, lw=1)
        ax.set_title(lab); ax.set_yticks([])
        ax.set_xlabel(f"mean {v.mean():.3f}   95% [{lo:.3f}, {hi:.3f}]", fontsize=9.5)
        ax.grid(axis="y", visible=False)
    _save(fig, path)


def strengths(tab, path, title):
    fig, axes = plt.subplots(1, 2, figsize=(10, 6.2), sharey=False)
    for ax, k, lab in zip(axes, ["att", "def"], ["Attack (higher = scores more)", "Defence (higher = concedes less)"]):
        t = tab.sort_values(f"{k}_mean")
        y = np.arange(len(t))
        ax.hlines(y, t[f"{k}_lo90"], t[f"{k}_hi90"], color=MODEL_SOFT, lw=3.5)
        ax.plot(t[f"{k}_mean"], y, "o", color=MODEL, ms=5.5, mec=SURFACE, mew=1.2)
        ax.set_yticks(y, t.team); ax.axvline(0, color=GREY, lw=1)
        ax.set_title(lab); ax.grid(axis="y", visible=False)
    fig.suptitle(title, x=0.01, ha="left", fontsize=10, color=INK2)
    fig.tight_layout()
    _save(fig, path)


def predicted_vs_actual(tab, path, title):
    fig, ax = plt.subplots(figsize=(7, 6.3))
    out = ~tab.inside
    ax.hlines(tab.actual, tab.lo90, tab.hi90, color=MODEL_SOFT, lw=3, label="90% predictive interval")
    ax.plot(tab.predicted[~out], tab.actual[~out], "o", color=MODEL, ms=7, mec=SURFACE, mew=1.5, label="inside the interval")
    ax.plot(tab.predicted[out], tab.actual[out], "o", color=ACTUAL, ms=7, mec=SURFACE, mew=1.5, label="outside")
    lo, hi = min(tab.lo90.min(), tab.actual.min()) - 3, max(tab.hi90.max(), tab.actual.max()) + 3
    ax.plot([lo, hi], [lo, hi], color=GREY, lw=1)
    for _, r in tab.iterrows():
        ax.annotate(r.team, (r.predicted, r.actual), xytext=(0, 6), textcoords="offset points",
                    ha="center", fontsize=7.5, color=INK if not r.inside else INK2)
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
    ax.set_xlabel("points predicted (posterior predictive mean)"); ax.set_ylabel("points actually obtained")
    ax.set_title(title); ax.legend(loc="upper left", fontsize=9)
    _save(fig, path)


def accuracy_by_cutoff(summary, naive, path):
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    ax = axes[0]
    ax.plot(summary.m, summary.mae, "-o", color=MODEL, lw=2, ms=7, mec=SURFACE, mew=1.5)
    ax.axhline(naive, color=GREY, lw=1)
    ax.text(summary.m.max(), naive - 0.4, "naive benchmark (every team at the mean)", ha="right", va="top", fontsize=9, color=INK2)
    for _, r in summary.iterrows():
        ax.annotate(f"{r.mae:.2f}", (r.m, r.mae), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=9)
    ax.set_ylim(0, naive * 1.12); ax.set_xlabel("cut-off matchday m"); ax.set_ylabel("mean absolute error (points)")
    ax.set_title("Error against the final table")
    ax = axes[1]
    ax.plot(summary.m, summary.mean_width, "-o", color=MODEL, lw=2, ms=7, mec=SURFACE, mew=1.5)
    for _, r in summary.iterrows():
        ax.annotate(f"{r.mean_width:.0f}  ({r.coverage_90:.0%} inside)", (r.m, r.mean_width), xytext=(4, 8),
                    textcoords="offset points", fontsize=8.5)
    ax.set_ylim(0, summary.mean_width.max() * 1.2); ax.set_xlabel("cut-off matchday m")
    ax.set_ylabel("mean width of the 90% interval (points)"); ax.set_title("Width of the intervals")
    fig.tight_layout()
    _save(fig, path)


def every_team(tabs: dict, path):
    ms = sorted(tabs)
    shades = ["#c3d3e6", "#8fabcc", "#4c76a8", "#1f4e79"][-len(ms):]
    final = tabs[ms[0]].set_index("team").actual.sort_values()
    fig, ax = plt.subplots(figsize=(8.5, 9.5))
    for i, team in enumerate(final.index):
        ax.vlines(final[team], i - 0.45, i + 0.45, color=ACTUAL, lw=2.4)
        for j, m in enumerate(ms):
            r = tabs[m].set_index("team").loc[team]
            y = i + (len(ms) / 2 - 0.5 - j) * 0.19
            ax.hlines(y, r.lo90, r.hi90, color=shades[j], lw=3.5)
            ax.plot(r.predicted, y, "o", color=shades[j], ms=3.5, mec="white", mew=0.8)
    ax.set_yticks(range(len(final)), final.index); ax.grid(axis="y", visible=False)
    ax.set_xlabel("points")
    handles = [plt.Line2D([], [], color=c, lw=3.5) for c in shades] + [plt.Line2D([], [], color=ACTUAL, lw=2.4)]
    ax.legend(handles, [f"after matchday {m}" for m in ms] + ["actual points"], loc="lower right", fontsize=9)
    ax.set_title("Every team, every cut-off: 90% interval and forecast")
    _save(fig, path)


def error_floor(naive, model, floor, path):
    fig, ax = plt.subplots(figsize=(7, 4))
    labels = ["naive benchmark\n(every team at the mean)", "model\nbefore matchday 1", "floor: strengths known,\nchance only"]
    v = [naive, model, floor]
    ax.bar(range(3), v, 0.55, color=[GREY, MODEL, MODEL_SOFT])
    for i, x in enumerate(v):
        ax.text(i, x + 0.25, f"{x:.2f}", ha="center", fontsize=11, fontweight="bold")
    ax.set_xticks(range(3), labels); ax.grid(axis="x", visible=False)
    ax.set_ylabel("mean absolute error (points)"); ax.set_ylim(0, max(v) * 1.18)
    ax.set_title(f"The model closes {(naive - model) / (naive - floor):.0%} of the error that can be closed")
    _save(fig, path)


def title_race(series, path, title):
    s = series[series >= 0.005]
    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.bar(range(len(s)), s.values, 0.6, color=MODEL)
    for i, v in enumerate(s.values):
        ax.text(i, v + 0.01, f"{v:.0%}", ha="center", fontsize=9)
    ax.set_xticks(range(len(s)), s.index, rotation=30, ha="right"); ax.grid(axis="x", visible=False)
    ax.set_ylabel("probability of winning the title"); ax.set_ylim(0, s.max() * 1.15)
    ax.set_title(title)
    _save(fig, path)


def cumulative_teams(cum, teams, path, coach_changes=None):
    names = list(cum["names"])
    fig, axes = plt.subplots(1, len(teams), figsize=(4 * len(teams), 3.8), sharey=True)
    x = np.arange(1, cum["mean"].shape[1] + 1)
    for ax, t in zip(np.atleast_1d(axes), teams):
        i = names.index(t)
        ax.fill_between(x, cum["lo"][i], cum["hi"][i], color=MODEL, alpha=0.12, lw=0, label="pre-season 90% band")
        ax.plot(x, cum["mean"][i], color=MODEL, lw=2, label="pre-season forecast")
        ax.plot(x, cum["actual"][i], color=ACTUAL, lw=2.2, label="actual")
        ax.text(x[-1] + 0.6, cum["actual"][i][-1], f"{int(cum['actual'][i][-1])}", va="center", fontsize=9, color=INK)
        if coach_changes and t in coach_changes:
            ax.axvline(coach_changes[t], color=GREY, lw=1)
            ax.text(coach_changes[t] + 0.5, 4, "new coach", fontsize=8.5, color=INK2)
        ax.set_title(t); ax.set_xlabel("matchday"); ax.set_xlim(1, x[-1] + 3)
    np.atleast_1d(axes)[0].set_ylabel("cumulative points")
    np.atleast_1d(axes)[0].legend(loc="upper left", fontsize=8.5)
    fig.tight_layout()
    _save(fig, path)


def forecast_strip(tab, path, title):
    t = tab.iloc[::-1].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(8.5, 7.5))
    y = np.arange(len(t))
    ax.hlines(y, t.lo90, t.hi90, color=MODEL_SOFT, lw=5)
    ax.plot(t.predicted, y, "o", color=MODEL, ms=7, mec=SURFACE, mew=1.5, label="expected final points")
    ax.plot(t.banked, y, "|", color=INK, ms=12, mew=2, label="points already won")
    for i, r in t.iterrows():
        for xx, p in [(117, r.p_title), (129, r.p_top4), (142, r.p_relegation)]:
            ax.text(xx, i, f"{p:.0%}" if p >= 0.005 else "–", va="center", fontsize=9, ha="right")
    for xx, lab in [(117, "title"), (129, "top 4"), (142, "releg.")]:
        ax.text(xx, len(t) - 0.2, lab, ha="right", fontsize=9, color=INK2, fontweight="bold")
    ax.axvline(104, color=GRID, lw=0.8)
    ax.set_yticks(y, t.team); ax.set_xlim(0, 144); ax.set_xticks(range(0, 101, 20))
    ax.grid(axis="y", visible=False); ax.set_xlabel("points")
    ax.legend(loc="lower left", fontsize=9, bbox_to_anchor=(0, -0.13), ncol=2)
    ax.set_title(title)
    _save(fig, path)


def position_heatmap(probs, order, path, title):
    P = probs.loc[order].values
    n = P.shape[1]
    cmap = matplotlib.colors.ListedColormap(["#f0efec", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"])
    bounds = [0, 0.005, 0.02, 0.05, 0.10, 0.20, 0.35, 0.50, 1.0]
    norm = matplotlib.colors.BoundaryNorm(bounds, cmap.N)
    fig, ax = plt.subplots(figsize=(10, 7))
    im = ax.imshow(P, cmap=cmap, norm=norm, aspect="auto")
    for i in range(P.shape[0]):
        for j in range(n):
            if P[i, j] >= 0.10:
                ax.text(j, i, f"{P[i, j] * 100:.0f}", ha="center", va="center", fontsize=7.5,
                        color="white" if P[i, j] >= 0.20 else INK)
    ax.set_xticks(range(n), range(1, n + 1)); ax.set_yticks(range(len(order)), order)
    ax.axvline(3.5, color=INK2, lw=1); ax.axvline(n - 3.5, color=INK2, lw=1)
    ax.grid(False); ax.set_xlabel("final position")
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02, ticks=bounds[1:-1])
    cb.ax.set_yticklabels(["0.5%", "2%", "5%", "10%", "20%", "35%", "50%"])
    cb.outline.set_visible(False)
    ax.set_title(title)
    _save(fig, path)
