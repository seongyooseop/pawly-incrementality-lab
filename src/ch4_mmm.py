"""Chapter 4: how should next year's budget be split?

  1. weekly national MMM (mmm_core) fitted in PyMC three ways:
       before_tests  - revenue of the 78 history weeks only: the model the
                       advertiser had before running any experiment
       after_tests   - same 78 weeks, plus the two experiment results as extra
                       likelihood terms: the model's predicted revenue loss in
                       the geo-test weeks and in the pause weeks must match what
                       chapters 1 and 2 measured, within their uncertainty
       all_weeks     - all 104 weeks, no calibration (reference: the tests
                       themselves also add spend variation to the data)
  2. channel ROI with intervals, graded against the true ROI over the same weeks
  3. response curves for next year's plan (each channel x0 ... x2)
  4. two reallocations per model (each channel 0.5x-1.5x, total fixed):
       mean plan       - maximizes the expected gain
       risk-aware plan - maximizes a pessimistic gain (mean - 0.84 sd, about the
                         20th percentile), so the budget moves only where the
                         model is confident
     each plan is then run through the true world and compared with the best
     possible reallocation
Writes outputs/ch4_mmm.json. Fits are cached in models/ (rerun with --refit).
"""
import json
import sys
from pathlib import Path

import arviz as az
import numpy as np
import pandas as pd
import pymc as pm
import pytensor.tensor as pt
from scipy.optimize import minimize

import world as W
from mmm_core import CHANNELS, LAGS, contributions_np, lag_matrix, weekly

ROOT = Path(__file__).resolve().parents[1]
GEO_WEEKS = (79, 84)
PAUSE_WEEKS = (89, 92)
HISTORY_WEEKS = 78
PLAN_WEEKS = (53, 104)          # "next year" is evaluated on this calendar
EXCLUDE_FROM_PLAN = (79, 92)    # test and pause weeks are not normal spend
BOUNDS = (0.5, 1.5)
RISK_Z = 0.84
MULTS = np.round(np.arange(0, 2.01, 0.25), 2)
MODELS = {  # name: (calibrate, fitted weeks, seed)
    "before_tests": (False, HISTORY_WEEKS, 21),
    "after_tests": (True, HISTORY_WEEKS, 22),
    "all_weeks": (False, 104, 11),
}


def calibration_targets():
    plan = json.loads((ROOT / "data" / "media_plan.json").read_text())
    ch1 = json.loads((ROOT / "outputs" / "ch1_readout.json").read_text())["after_check"]["revenue"]
    ch2 = json.loads((ROOT / "outputs" / "ch2_causal_impact.json").read_text())["causal_impact"]
    withheld = plan["geo_test_withheld_video_budget_krw"] / 1e6
    cancelled = plan["cancelled_video_budget_krw"] / 1e6
    geo = {"lift": ch1["iroas"] * withheld,
           "se": (ch1["iroas_ci"][1] - ch1["iroas_ci"][0]) / (2 * 1.96) * withheld,
           "weeks": GEO_WEEKS, "extra_per_week": withheld / (GEO_WEEKS[1] - GEO_WEEKS[0] + 1)}
    pause = {"lift": -ch2["effect_krw_m"],
             "se": (ch2["ci_krw_m"][1] - ch2["ci_krw_m"][0]) / (2 * 1.96),
             "weeks": PAUSE_WEEKS, "extra_per_week": cancelled / (PAUSE_WEEKS[1] - PAUSE_WEEKS[0] + 1)}
    return {"geo_test": geo, "video_pause": pause}


def counterfactual_video(df, target):
    x = df.short_video.to_numpy().copy()
    m = ((df.week >= target["weeks"][0]) & (df.week <= target["weeks"][1])).to_numpy()
    x[m] += target["extra_per_week"]
    return x, m


def fit(df, calibrate: bool, n_fit: int, targets: dict, seed: int):
    """Revenue likelihood on the first n_fit weeks; spend paths run through
    week 104 so experiment weeks can be scored even when not fitted."""
    y = df.revenue.to_numpy()[:n_fit]
    spend = {c: df[c].to_numpy() for c in CHANNELS}
    med = {c: np.median(spend[c][:n_fit][spend[c][:n_fit] > 0]) for c in CHANNELS}
    lmat = {c: lag_matrix(spend[c]) for c in CHANNELS}
    tidx = np.arange(len(df)) / 52.0

    with pm.Model(coords={"channel": CHANNELS}):
        roi = pm.LogNormal("roi", 0.0, 0.7, dims="channel")
        lam = pm.Beta("lam", 2.0, 3.0, dims="channel")
        kappa = pm.LogNormal("kappa", 0.0, 0.5, dims="channel")
        c0 = pm.Normal("c0", 0.0, 150.0)
        c1 = pm.Normal("c1", 400.0, 150.0)
        c2 = pm.Normal("c2", 0.0, 50.0)
        sigma = pm.HalfNormal("sigma", 30.0)

        lags = np.arange(LAGS + 1)
        contrib, betas, Ks, ws = [], [], [], []
        for j, c in enumerate(CHANNELS):
            w = (1 - lam[j]) * lam[j] ** lags
            w = w / w.sum()
            a = pt.dot(lmat[c], w)
            K = kappa[j] * med[c]
            h = a / (a + K)
            beta = roi[j] * spend[c][:n_fit].sum() / h[:n_fit].sum()
            contrib.append(beta * h)
            betas.append(beta)
            Ks.append(K)
            ws.append(w)
        pm.Deterministic("beta", pt.stack(betas), dims="channel")
        pm.Deterministic("K", pt.stack(Ks), dims="channel")
        media = pt.stack(contrib, axis=1)
        mu = c0 + c1 * df.category.to_numpy() + c2 * tidx + media.sum(axis=1)
        pm.Deterministic("mu", mu)
        pm.Normal("y", mu[:n_fit], sigma, observed=y)

        j = CHANNELS.index("short_video")
        for name, tgt in targets.items():
            x_cf, mask = counterfactual_video(df, tgt)
            a_cf = pt.dot(lag_matrix(x_cf), ws[j])
            h_cf = a_cf / (a_cf + Ks[j])
            lift = (betas[j] * h_cf - contrib[j])[mask].sum()
            pm.Deterministic(f"lift_{name}", lift)  # tracked for every model
            if calibrate:
                pm.Normal(f"cal_{name}", lift, tgt["se"], observed=tgt["lift"])

        idata = pm.sample(1000, tune=1500, chains=4, target_accept=0.95,
                          random_seed=seed, progressbar=False)
    return idata


def summarize_fit(idata) -> dict:
    """Everything later steps need, as plain arrays (cached to models/)."""
    post = idata.posterior.to_dataset().stack(s=("chain", "draw"))
    summ = az.summary(idata, var_names=["roi", "lam", "kappa", "c0", "c1", "c2", "sigma"])
    out = {"roi": post["roi"].values.T, "lam": post["lam"].values.T,
           "K": post["K"].values.T, "beta": post["beta"].values.T,
           "mu": post["mu"].values.T,
           "max_rhat": np.array(float(summ["r_hat"].max())),
           "divergences": np.array(int(idata.sample_stats["diverging"].values.sum()))}
    for k in ("geo_test", "video_pause"):
        out[f"lift_{k}"] = post[f"lift_{k}"].values
    return out


def load_or_fit(df, name, targets, refit=False):
    calibrate, n_fit, seed = MODELS[name]
    path = ROOT / "models" / f"ch4_{name}.npz"
    if path.exists() and not refit:
        return dict(np.load(path))
    path.parent.mkdir(exist_ok=True)
    d = summarize_fit(fit(df, calibrate, n_fit, targets, seed))
    np.savez_compressed(path, **d)
    return d


def plan_paths(df, mult):
    """Weekly spend paths: actual weeks before the plan, flat x mult in the plan."""
    in_plan = (df.week >= PLAN_WEEKS[0]).to_numpy()
    normal = in_plan & ~((df.week >= EXCLUDE_FROM_PLAN[0]) & (df.week <= EXCLUDE_FROM_PLAN[1])).to_numpy()
    flat = {c: df.loc[normal, c].mean() for c in CHANNELS}
    paths = {}
    for j, c in enumerate(CHANNELS):
        x = df[c].to_numpy().copy()
        x[in_plan] = flat[c] * mult[j]
        paths[c] = x
    return paths, in_plan, flat


def model_gain(d, df, mult):
    base_paths, in_plan, _ = plan_paths(df, np.ones(len(CHANNELS)))
    new_paths, _, _ = plan_paths(df, mult)
    base = contributions_np(base_paths, d, d["beta"])[:, in_plan].sum(axis=(1, 2))
    new = contributions_np(new_paths, d, d["beta"])[:, in_plan].sum(axis=(1, 2))
    return new - base  # (S,)


# ------------------------------------------------------------- the truth
class Truth:
    """Grades a plan by running it through the real world."""

    GROUPS = {"search": ["brand_search", "nonbrand_search", "auto_bid"],
              "short_video": ["short_video"], "social": ["social"], "retargeting": ["retargeting"]}

    def __init__(self, df):
        self.world = W.World()
        _, _, self.flat = plan_paths(df, np.ones(len(CHANNELS)))
        self.base_rev = self._revenue(np.ones(len(CHANNELS)))

    def _plan(self, mult):
        world = self.world
        plan = W.bau_plan(world)
        days = world.week >= PLAN_WEEKS[0]
        for c in W.CHANNELS:
            plan.spend[c][days] = 0.0
        mapping = {"search": "auto_bid", "short_video": "short_video",
                   "social": "social", "retargeting": "retargeting"}
        for j, c in enumerate(CHANNELS):
            daily = self.flat[c] * 1e6 / 7 * mult[j]
            plan.spend[mapping[c]][days] = daily * world.share[None, :]
        return plan

    def _revenue(self, mult):
        obs, _ = self.world.simulate(self._plan(mult))
        return obs.loc[obs.week >= PLAN_WEEKS[0], "revenue"].sum() / 1e6

    def gain(self, mult):
        return self._revenue(np.asarray(mult)) - self.base_rev

    def channel_roi(self, obs_actual, asg, promo_geo, last_week):
        """Average ROI over weeks 1..last_week: switch the channel off throughout."""
        idx = {g: i for i, g in enumerate(self.world.geo_ids)}
        go_dark = np.array([idx[g] for g in asg.loc[asg.group == "go_dark", "geo"]])
        plan = W.actual_plan(self.world, go_dark, idx[promo_geo])
        days = self.world.week <= last_week
        rev = obs_actual.loc[obs_actual.week <= last_week, "revenue"].sum()
        out = {}
        for c, members in self.GROUPS.items():
            off = plan.copy()
            spend = sum(off.spend[m][days].sum() for m in members)
            for m in members:
                off.spend[m][:] = 0.0
            o, _ = self.world.simulate(off)
            out[c] = (rev - o.loc[o.week <= last_week, "revenue"].sum()) / spend
        return out


def optimize(objective, flat):
    S = np.array([flat[c] for c in CHANNELS])
    cons = {"type": "eq", "fun": lambda m: (m * S).sum() - S.sum()}
    best = None
    for start in [np.ones(4), np.array([1.3, 1.3, 0.7, 0.7]), np.array([0.7, 1.3, 1.0, 1.0]),
                  np.array([1.0, 1.2, 1.0, 0.6])]:
        r = minimize(lambda m: -objective(m), start, method="SLSQP",
                     bounds=[BOUNDS] * len(CHANNELS), constraints=cons,
                     options={"maxiter": 200, "ftol": 1e-6})
        if best is None or r.fun < best.fun:
            best = r
    return np.clip(best.x, *BOUNDS)


def main():
    obs = pd.read_parquet(ROOT / "data" / "observed_daily.parquet")
    df = weekly()
    targets = calibration_targets()
    asg = pd.read_csv(ROOT / "data" / "geo_assignment.csv")
    promo_geo = json.loads((ROOT / "data" / "truth" / "effects.json").read_text())["promo_region"]
    refit = "--refit" in sys.argv
    fits = {name: load_or_fit(df, name, targets, refit) for name in MODELS}

    truth = Truth(df)
    true_roi = {n: truth.channel_roi(obs, asg, promo_geo, n) for n in (HISTORY_WEEKS, 104)}
    _, _, flat = plan_paths(df, np.ones(4))

    out = {"question": "How should next year's budget be split?",
           "channels": CHANNELS,
           "calibration_targets": {k: {"lift_krw_m": round(v["lift"], 1), "se_krw_m": round(v["se"], 1)}
                                   for k, v in targets.items()},
           "plan_weekly_spend_krw_m": {c: round(flat[c], 1) for c in CHANNELS},
           "true_roi": {f"weeks_1_{n}": {c: round(v, 2) for c, v in r.items()} for n, r in true_roi.items()},
           "models": {}}

    true_curves = {c: [round(truth.gain(np.where(np.arange(4) == j, m, 1.0)), 1) for m in MULTS]
                   for j, c in enumerate(CHANNELS)}
    out["true_response_curves"] = {"multipliers": MULTS.tolist(), "gain_krw_m": true_curves}
    # marginal ROI at today's plan: extra revenue per extra won, from +-10% on one channel
    plan_weeks = PLAN_WEEKS[1] - PLAN_WEEKS[0] + 1

    def step(j, m):
        return np.where(np.arange(4) == j, m, 1.0)

    true_mroi = {c: round((truth.gain(step(j, 1.1)) - truth.gain(step(j, 0.9))) / (0.2 * flat[c] * plan_weeks), 2)
                 for j, c in enumerate(CHANNELS)}
    out["marginal_roi"] = {"truth": true_mroi, "models": {}}

    true_best = optimize(lambda m: truth.gain(m), flat)
    best_gain = truth.gain(true_best)
    out["true_best_plan"] = {"multipliers": dict(zip(CHANNELS, true_best.round(2).tolist())),
                             "true_gain_krw_m": round(best_gain, 1)}

    for name, d in fits.items():
        calibrate, n_fit, _ = MODELS[name]
        tr = true_roi[n_fit]
        mu = d["mu"].T
        y = df.revenue.to_numpy()[:n_fit]
        roi = {c: {"median": round(float(np.median(d["roi"][:, j])), 2),
                   "ci90": [round(float(np.quantile(d["roi"][:, j], 0.05)), 2),
                            round(float(np.quantile(d["roi"][:, j], 0.95)), 2)],
                   "truth": round(tr[c], 2),
                   "truth_inside": bool(np.quantile(d["roi"][:, j], 0.05) <= tr[c]
                                        <= np.quantile(d["roi"][:, j], 0.95))}
               for j, c in enumerate(CHANNELS)}
        mroi = {}
        for j, c in enumerate(CHANNELS):
            g = (model_gain(d, df, step(j, 1.1)) - model_gain(d, df, step(j, 0.9))) / (0.2 * flat[c] * plan_weeks)
            mroi[c] = {"median": round(float(np.median(g)), 2),
                       "ci90": [round(float(np.quantile(g, 0.05)), 2), round(float(np.quantile(g, 0.95)), 2)],
                       "truth_inside": bool(np.quantile(g, 0.05) <= true_mroi[c] <= np.quantile(g, 0.95))}
        out["marginal_roi"]["models"][name] = mroi
        curves = {}
        for j, c in enumerate(CHANNELS):
            g = np.array([model_gain(d, df, np.where(np.arange(4) == j, m, 1.0)) for m in MULTS])
            curves[c] = {"median": np.median(g, axis=1).round(1).tolist(),
                         "low": np.quantile(g, 0.05, axis=1).round(1).tolist(),
                         "high": np.quantile(g, 0.95, axis=1).round(1).tolist()}
        plans = {}
        for kind, obj in {"mean": lambda m: model_gain(d, df, m).mean(),
                          "risk_aware": lambda m: (lambda g: g.mean() - RISK_Z * g.std())(model_gain(d, df, m))
                          }.items():
            best = optimize(obj, flat)
            pred = model_gain(d, df, best)
            tg = truth.gain(best)
            plans[kind] = {"multipliers": dict(zip(CHANNELS, best.round(2).tolist())),
                           "predicted_gain_krw_m": {"median": round(float(np.median(pred)), 1),
                                                    "ci90": [round(float(np.quantile(pred, 0.05)), 1),
                                                             round(float(np.quantile(pred, 0.95)), 1)]},
                           "true_gain_krw_m": round(tg, 1),
                           "share_of_best_possible": round(tg / best_gain, 2)}
        out["models"][name] = {
            "calibrated": calibrate, "fitted_weeks": n_fit,
            "max_rhat": round(float(d["max_rhat"]), 3),
            "divergences": int(d["divergences"]),
            "fit_mape_pct": round(float(100 * np.mean(np.abs(y - mu[:n_fit].mean(axis=1)) / y)), 2),
            "roi": roi,
            "experiment_lift_check_krw_m": {
                k: {"model": round(float(np.median(d[f"lift_{k}"])), 1),
                    "model_ci90": [round(float(np.quantile(d[f"lift_{k}"], 0.05)), 1),
                                   round(float(np.quantile(d[f"lift_{k}"], 0.95)), 1)],
                    "experiment": round(targets[k]["lift"], 1)} for k in targets},
            "response_curves": curves,
            "plans": plans,
            "fitted_weekly": mu.mean(axis=1).round(1).tolist(),
        }
    out["weekly_actual"] = df.revenue.round(1).tolist()
    (ROOT / "outputs" / "ch4_mmm.json").write_text(json.dumps(out, indent=2))

    print(json.dumps({k: out[k] for k in ("true_roi", "true_best_plan")}, indent=1))
    for name, m in out["models"].items():
        print("==", name, json.dumps({k: m[k] for k in ("max_rhat", "divergences", "fit_mape_pct", "roi",
                                                         "experiment_lift_check_krw_m", "plans")}, indent=1))


if __name__ == "__main__":
    main()
