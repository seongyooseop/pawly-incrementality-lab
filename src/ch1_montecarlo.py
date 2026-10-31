"""Chapter 1 check over many luck draws: is the readout procedure sound?

One simulated test is one draw of noise. Here the same regions, design and
contaminating promotion are re-run on 60 fresh noise draws. For each draw:
  * TBR on all 20 pairs and without the contaminated pair 6
  * the truth for exactly those regions (counterfactual run)
  * whether the pair diagnostic flags pair 6, and how many clean pairs it flags
Writes outputs/ch1_montecarlo.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from geo_tbr import tbr
from world import GEO_TEST_WEEKS, World, actual_plan, week_mask

ROOT = Path(__file__).resolve().parents[1]
N_DRAWS = 60
PRE_FIT_DAYS = 84
PROMO_PAIR = 6


def main():
    design = json.loads((ROOT / "outputs" / "ch1_design.json").read_text())
    k = design["se_scale"]["6"]
    asg = pd.read_csv(ROOT / "data" / "geo_assignment.csv")
    base = World()
    idx = {g: i for i, g in enumerate(base.geo_ids)}
    pairs = []
    for p, g in asg.groupby("pair"):
        pairs.append((int(p), idx[g.loc[g.group == "go_dark", "geo"].item()],
                      idx[g.loc[g.group == "control", "geo"].item()]))
    T = np.array([t for _, t, _ in pairs])
    C = np.array([c for _, _, c in pairs])
    promo_geo = [c for p, _, c in pairs if p == PROMO_PAIR][0]
    keep = np.array([p != PROMO_PAIR for p, _, _ in pairs])

    test = week_mask(base, *GEO_TEST_WEEKS)
    t0 = int(np.argmax(test))
    t1 = int(np.where(test)[0][-1]) + 1
    pre_s, test_s = slice(t0 - PRE_FIT_DAYS, t0), slice(t0, t1)
    cool_s = slice(t0, t1 + 14)          # test + 2-week cooldown
    k8 = design["se_scale"]["8"]

    rows = []
    for s in range(1, N_DRAWS + 1):
        w = World(noise_seed=s)
        plan = actual_plan(w, T, promo_geo)
        cf = actual_plan(w, T, promo_geo, geo_test=False)
        obs, _ = w.simulate(plan)
        obs_cf, _ = w.simulate(cf)
        Y = obs.pivot(index="date", columns="geo", values="revenue").to_numpy()
        Ycf = obs_cf.pivot(index="date", columns="geo", values="revenue").to_numpy()
        withheld = cf.spend["short_video"][test_s].sum(axis=0)

        def est(tt, cc, window=test_s, scale=k):
            r = tbr(Y[:, tt].sum(1), Y[:, cc].sum(1), pre_s, window, se_scale=scale)
            wsum = withheld[tt].sum()
            return -r["effect"] / wsum, -r["ci_high"] / wsum, -r["ci_low"] / wsum

        def truth(tt, window=test_s):
            return -(Y[window][:, tt].sum() - Ycf[window][:, tt].sum()) / withheld[tt].sum()

        a, alo, ahi = est(T, C)
        b, blo, bhi = est(T[keep], C[keep])
        ta, tb = truth(T), truth(T[keep])
        cb, cblo, cbhi = est(T[keep], C[keep], cool_s, k8)
        tcb = truth(T[keep], cool_s)

        d = np.array([np.log(Y[test_s, t].sum() / Y[test_s, c].sum())
                      - np.log(Y[pre_s, t].sum() / Y[pre_s, c].sum()) for _, t, c in pairs])
        z = (d - np.median(d)) / (1.4826 * np.median(np.abs(d - np.median(d))))
        flags = np.abs(z) > 3
        rows.append({"draw": s, "all_est": a, "all_truth": ta, "all_cover": alo <= ta <= ahi,
                     "trim_est": b, "trim_truth": tb, "trim_cover": blo <= tb <= bhi,
                     "cool_est": cb, "cool_truth": tcb, "cool_cover": cblo <= tcb <= cbhi,
                     "test_only_vs_cool_truth": b - tcb,
                     "flag_promo_pair": bool(flags[~keep][0]),
                     "false_flags": int(flags[keep].sum())})
    df = pd.DataFrame(rows)
    summary = {
        "draws": N_DRAWS,
        "all_pairs": {"mean_bias_iroas": round(float((df.all_est - df.all_truth).mean()), 3),
                      "rmse_iroas": round(float(np.sqrt(((df.all_est - df.all_truth) ** 2).mean())), 3),
                      "ci_coverage": round(float(df.all_cover.mean()), 3)},
        "without_contaminated_pair": {"mean_bias_iroas": round(float((df.trim_est - df.trim_truth).mean()), 3),
                                      "rmse_iroas": round(float(np.sqrt(((df.trim_est - df.trim_truth) ** 2).mean())), 3),
                                      "ci_coverage": round(float(df.trim_cover.mean()), 3)},
        "with_cooldown": {"mean_bias_iroas": round(float((df.cool_est - df.cool_truth).mean()), 3),
                          "rmse_iroas": round(float(np.sqrt(((df.cool_est - df.cool_truth) ** 2).mean())), 3),
                          "ci_coverage": round(float(df.cool_cover.mean()), 3),
                          "test_only_bias_vs_full_effect": round(float(df.test_only_vs_cool_truth.mean()), 3)},
        "diagnostic_flags_promo_pair": round(float(df.flag_promo_pair.mean()), 3),
        "draws_with_any_false_flag": round(float((df.false_flags > 0).mean()), 3),
        "mean_true_iroas": round(float(df.all_truth.mean()), 3),
    }
    (ROOT / "outputs" / "ch1_montecarlo.json").write_text(json.dumps(summary, indent=2))
    df.to_csv(ROOT / "outputs" / "ch1_montecarlo_draws.csv", index=False)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
