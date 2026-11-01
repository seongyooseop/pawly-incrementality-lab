"""Chapter 2: PAWLY paused short video nationwide for 4 weeks. What did it cost?

No holdout was planned, so there is no control region. The counterfactual
comes from a Bayesian structural time series (the model behind Google's
CausalImpact), written in PyMC:

  log revenue_t = level_t + b * log category_searches_t + day-of-week_t + e_t
  level_t       = level_{t-1} + u_t          (local level, random walk)

Fitted on the pre-period only. The geo-test weeks (and two weeks of carry-over
after them) are masked: half the regions had no video then, so they would
teach the model a depressed baseline. Pet-food category searches move with the
season and promotions but not with PAWLY's ads, which is what lets the model
separate the summer dip from the pause. A simple before/after comparison
cannot (trap 1).

Placebo runs on quiet past windows check that the model finds nothing where
nothing happened.
Writes outputs/ch2_causal_impact.json
"""
import json
from pathlib import Path

import arviz as az
import numpy as np
import pandas as pd
import pymc as pm
import pytensor.tensor as pt

from build_marts import read as read_mart

ROOT = Path(__file__).resolve().parents[1]
PAUSE = (89, 92)


def causal_impact(nat: pd.DataFrame, pre_weeks: tuple, post_weeks: tuple,
                  mask_weeks: tuple | None = None, seed: int = 1) -> dict:
    win = nat[(nat.week >= pre_weeks[0]) & (nat.week <= post_weeks[1])].reset_index(drop=True)
    is_post = (win.week >= post_weeks[0]).to_numpy()
    observed = ~is_post
    if mask_weeks:
        observed &= ~((win.week >= mask_weeks[0]) & (win.week <= mask_weeks[1])).to_numpy()
    ly = np.log(win.revenue.to_numpy())
    lx = np.log(win.category_search_index.to_numpy())
    lx_c = lx - lx[observed].mean()
    dow = win.date.dt.dayofweek.to_numpy()
    obs_idx = np.where(observed)[0]
    T = len(win)

    with pm.Model():
        sigma_level = pm.HalfNormal("sigma_level", 0.01)
        sigma_obs = pm.HalfNormal("sigma_obs", 0.1)
        b = pm.Normal("b", 1.0, 0.5)
        dow_eff = pm.ZeroSumNormal("dow", sigma=0.1, shape=7)
        level0 = pm.Normal("level0", ly[obs_idx[:7]].mean(), 0.2)
        z = pm.Normal("z", 0.0, 1.0, shape=T)
        level = level0 + pt.cumsum(sigma_level * z)
        mu = level + b * lx_c + dow_eff[dow]
        pm.Deterministic("mu", mu)
        pm.Normal("y", mu[obs_idx], sigma_obs, observed=ly[obs_idx])
        idata = pm.sample(1000, tune=1500, chains=4, target_accept=0.99,
                          random_seed=seed, progressbar=False)

    post = idata.posterior
    mu_s = post["mu"].stack(s=("chain", "draw")).values            # (T, S)
    so = post["sigma_obs"].stack(s=("chain", "draw")).values       # (S,)
    rng = np.random.default_rng(seed)
    cf = np.exp(mu_s + rng.normal(0, 1, mu_s.shape) * so[None, :])  # posterior predictive
    actual = win.revenue.to_numpy()
    eff_draws = (actual[is_post, None] - cf[is_post]).sum(axis=0)
    summ = az.summary(idata, var_names=["sigma_level", "sigma_obs", "b", "level0"])
    rhat = float(summ["r_hat"].max())
    divergences = int(idata.sample_stats["diverging"].values.sum())

    return {
        # CausalImpact's standard read-out: posterior probability of an effect
        "p_negative": float(np.mean(eff_draws < 0)),
        "effect": float(np.median(eff_draws)),
        "ci": [float(np.quantile(eff_draws, 0.025)), float(np.quantile(eff_draws, 0.975))],
        "effect_pct": float(np.median(eff_draws) / np.median(cf[is_post].sum(axis=0)) * 100),
        "max_rhat": round(rhat, 3),
        "divergences": divergences,
        "b": round(float(post["b"].mean()), 3),
        "series": {"date": win.date.dt.strftime("%Y-%m-%d").tolist(),
                   "actual": actual.round().tolist(),
                   "cf_median": np.median(cf, axis=1).round().tolist(),
                   "cf_low": np.quantile(cf, 0.025, axis=1).round().tolist(),
                   "cf_high": np.quantile(cf, 0.975, axis=1).round().tolist(),
                   "observed": observed.tolist(), "post": is_post.tolist()},
    }


def main():
    nat = read_mart("national_day")  # sql/marts.sql
    truth = json.loads((ROOT / "data" / "truth" / "effects.json").read_text())["video_pause"]

    # naive: the four pause weeks against the four weeks before
    before = nat[(nat.week >= 85) & (nat.week <= 88)].revenue.mean()
    during = nat[(nat.week >= PAUSE[0]) & (nat.week <= PAUSE[1])].revenue.mean()
    n_days = int(((nat.week >= PAUSE[0]) & (nat.week <= PAUSE[1])).sum())
    naive = (during - before) * n_days

    main_run = causal_impact(nat, pre_weeks=(63, 88), post_weeks=PAUSE, mask_weeks=(79, 86))
    saved = float(nat[(nat.week >= PAUSE[0]) & (nat.week <= PAUSE[1])].spend_short_video.sum())
    # what would have been spent: the booked budget from the advertiser's media plan
    withheld = json.loads((ROOT / "data" / "media_plan.json").read_text())["cancelled_video_budget_krw"]

    placebos = []
    for pre, post in [((44, 69), (70, 73)), ((50, 75), (76, 78))]:
        r = causal_impact(nat, pre_weeks=pre, post_weeks=post, seed=2)
        placebos.append({"post_weeks": post, "effect_krw_m": round(r["effect"] / 1e6, 1),
                         "p_negative": round(r["p_negative"], 3),
                         "ci_krw_m": [round(x / 1e6, 1) for x in r["ci"]],
                         "contains_zero": bool(r["ci"][0] <= 0 <= r["ci"][1])})

    out = {
        "question": "Short video was paused nationwide for 4 weeks. What did it cost?",
        "pause_weeks": PAUSE,
        "model": "Bayesian structural time series in PyMC: local level + log category searches + day of week, on log revenue",
        "pre_period_weeks": [63, 88], "masked_weeks": [79, 86],
        "video_spend_in_pause_krw_m": round(saved / 1e6, 1),
        "cancelled_video_budget_krw_m": round(withheld / 1e6, 1),
        "naive_before_after": {"effect_krw_m": round(naive / 1e6, 1),
                               "iroas": round(-naive / withheld, 2)},
        "causal_impact": {"effect_krw_m": round(main_run["effect"] / 1e6, 1),
                          "ci_krw_m": [round(x / 1e6, 1) for x in main_run["ci"]],
                          "effect_pct": round(main_run["effect_pct"], 2),
                          "iroas": round(-main_run["effect"] / withheld, 2),
                          "iroas_ci": [round(-main_run["ci"][1] / withheld, 2),
                                       round(-main_run["ci"][0] / withheld, 2)],
                          "max_rhat": main_run["max_rhat"],
                          "divergences": main_run["divergences"],
                          "probability_of_loss": round(main_run["p_negative"], 3),
                          "category_elasticity": main_run["b"]},
        "placebo_checks": placebos,
        "series": main_run["series"],
        "validation_against_truth": {
            "true_effect_krw_m": round(truth["true_revenue_effect_krw"] / 1e6, 1),
            "true_iroas": truth["true_iroas"],
            "truth_inside_iroas_ci": bool(round(-main_run["ci"][1] / withheld, 2) <= truth["true_iroas"]
                                          <= round(-main_run["ci"][0] / withheld, 2)),
            "truth_inside_ci": bool(main_run["ci"][0] <= truth["true_revenue_effect_krw"] <= main_run["ci"][1]),
            "naive_error_krw_m": round((naive - truth["true_revenue_effect_krw"]) / 1e6, 1),
            "causal_impact_error_krw_m": round((main_run["effect"] - truth["true_revenue_effect_krw"]) / 1e6, 1),
        },
    }
    (ROOT / "outputs" / "ch2_causal_impact.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k != "series"}, indent=2))


if __name__ == "__main__":
    main()
