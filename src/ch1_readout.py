"""Chapter 1 readout: what did switching short video off in 20 regions cost?

  1. TBR on all 20 pairs (revenue, then brand searches) with the 6-week
     A/A calibration factor from the design
  2. pair diagnostics: each pair's change in go-dark/control ratio from the
     pre-period to the test; a pair far from the rest (robust z > 3) is
     checked with the advertiser before anything is dropped
  3. re-read without the flagged pair; leave-one-pair-out range as a check
  4. grade against the truth (only here, in a separate block)
Writes outputs/ch1_readout.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from build_marts import read as read_mart
from geo_tbr import tbr

ROOT = Path(__file__).resolve().parents[1]
TEST = (79, 84)
PRE_FIT_DAYS = 84
COOLDOWN_WEEKS = 2


def wide(df, col):
    return df.pivot(index="date", columns="geo", values=col).sort_index()


def read(Y, cols_t, cols_c, pre, test, k):
    return tbr(Y[:, cols_t].sum(axis=1), Y[:, cols_c].sum(axis=1), pre, test, se_scale=k)


def main():
    obs = pd.read_parquet(ROOT / "data" / "observed_daily.parquet")
    design = json.loads((ROOT / "outputs" / "ch1_design.json").read_text())
    asg = pd.read_csv(ROOT / "data" / "geo_assignment.csv")

    R = wide(obs, "revenue")
    geos = list(R.columns)
    Y, B = R.to_numpy(), wide(obs, "brand_search_volume").to_numpy()
    weeks = obs.drop_duplicates("date").sort_values("date")["week"].to_numpy()
    t0 = int(np.argmax(weeks == TEST[0]))
    t1 = int(np.where(weeks == TEST[1])[0][-1]) + 1
    pre, test = slice(t0 - PRE_FIT_DAYS, t0), slice(t0, t1)
    k_rev = design["se_scale"]["6"]
    k_bsv = design["se_scale_brand_search"]["6"]

    pairs = []
    for p, g in asg.groupby("pair"):
        t = geos.index(g.loc[g.group == "go_dark", "geo"].item())
        c = geos.index(g.loc[g.group == "control", "geo"].item())
        pairs.append((p, t, c))
    T = np.array([t for _, t, _ in pairs])
    C = np.array([c for _, _, c in pairs])

    withheld_per_geo = {}
    planned = design["planned_video_budget_m_per_day"] * 1e6
    pre_spend = wide(obs, "spend_short_video").to_numpy()[pre]
    share = pre_spend.sum(axis=0) / pre_spend.sum()
    days = t1 - t0
    for i in T:
        withheld_per_geo[i] = planned * share[i] * days

    def summarize(r, tset):
        withheld = sum(withheld_per_geo[i] for i in tset)
        return {"effect_krw_m": round(r["effect"] / 1e6, 1),
                "ci_krw_m": [round(r["ci_low"] / 1e6, 1), round(r["ci_high"] / 1e6, 1)],
                "effect_pct": round(100 * r["effect"] / r["counterfactual"], 2),
                "iroas": round(-r["effect"] / withheld, 2),
                "iroas_ci": [round(-r["ci_high"] / withheld, 2), round(-r["ci_low"] / withheld, 2)],
                "significant": bool(r["ci_high"] < 0 or r["ci_low"] > 0),
                "video_withheld_krw_m": round(withheld / 1e6, 1)}

    all_rev = read(Y, T, C, pre, test, k_rev)
    all_bsv = read(B, T, C, pre, test, k_bsv)

    # pair diagnostics: log change of the go-dark/control ratio, test vs pre,
    # in robust z-units (computed in SQL: sql/marts.sql, mart geo_test_pairs)
    diag = read_mart("geo_test_pairs").set_index("pair").loc[[p for p, _, _ in pairs]]
    d, z = diag.log_ratio_change.to_numpy(), diag.robust_z.to_numpy()
    flagged = [int(pairs[i][0]) for i in np.where(np.abs(z) > 3)[0]]
    keep = [i for i in range(len(pairs)) if int(pairs[i][0]) not in flagged]
    trim_rev = read(Y, T[keep], C[keep], pre, test, k_rev)
    trim_bsv = read(B, T[keep], C[keep], pre, test, k_bsv)

    # test + 2-week cooldown: video is back on everywhere in weeks 85-86, but the
    # go-dark regions' slower awareness takes time to rebuild, so some of the
    # loss lands after the test. Read over 8 weeks with the 8-week A/A factor.
    c1 = int(np.where(weeks == TEST[1] + COOLDOWN_WEEKS)[0][-1]) + 1
    cool = slice(t0, c1)
    cool_rev = read(Y, T[keep], C[keep], pre, cool, design["se_scale"]["8"])

    loo = []
    for i in range(len(pairs)):
        rest = [j for j in range(len(pairs)) if j != i]
        r = read(Y, T[rest], C[rest], pre, test, k_rev)
        loo.append(-r["effect"] / sum(withheld_per_geo[T[j]] for j in rest))

    flagged_detail = []
    for p in flagged:
        i = [j for j in range(len(pairs)) if pairs[j][0] == p][0]
        _, t, c = pairs[i]
        side = "control" if d[i] < 0 else "go-dark"
        ctrl_jump = Y[test, c].sum() / Y[pre, c].sum() / (Y[test, C[keep]].sum() / Y[pre, C[keep]].sum()) - 1
        flagged_detail.append({"pair": p, "go_dark": geos[t], "control": geos[c],
                               "robust_z": round(float(z[i]), 1), "suspect_side": side,
                               "control_vs_other_controls_pct": round(100 * float(ctrl_jump), 1)})

    truth = json.loads((ROOT / "data" / "truth" / "effects.json").read_text())["geo_test"]
    by = truth["by_region"]

    def true_iroas(tset, key="effect_krw"):
        names = [geos[i] for i in tset]
        return round(-sum(by[g][key] for g in names) / sum(by[g]["withheld_krw"] for g in names), 3)

    out = {
        "question": design["question"],
        "test_weeks": TEST,
        "all_pairs": {"revenue": summarize(all_rev, T),
                      "brand_search": {"effect": round(all_bsv["effect"]),
                                       "effect_pct": round(100 * all_bsv["effect"] / all_bsv["counterfactual"], 2),
                                       "significant": bool(all_bsv["ci_high"] < 0)}},
        "pair_diagnostics": {"log_ratio_change": [round(float(x), 4) for x in d],
                             "robust_z": [round(float(x), 2) for x in z],
                             "pairs": [int(p) for p, _, _ in pairs],
                             "flagged": flagged_detail},
        "after_check": {
            "note": "Advertiser confirmed a retail partner promotion in the flagged control region during weeks 80-83; pair excluded.",
            "revenue": summarize(trim_rev, T[keep]),
            "brand_search": {"effect": round(trim_bsv["effect"]),
                             "effect_pct": round(100 * trim_bsv["effect"] / trim_bsv["counterfactual"], 2),
                             "ci_pct": [round(100 * trim_bsv["ci_low"] / trim_bsv["counterfactual"], 2),
                                        round(100 * trim_bsv["ci_high"] / trim_bsv["counterfactual"], 2)],
                             "significant": bool(trim_bsv["ci_high"] < 0)},
            "leave_one_pair_out_iroas": [round(min(loo), 2), round(max(loo), 2)],
        },
        "with_cooldown": {
            "weeks": [TEST[0], TEST[1] + COOLDOWN_WEEKS],
            "revenue": summarize(cool_rev, T[keep]),
            "truth_iroas": true_iroas(T[keep], "effect_cool_krw"),
            "share_of_loss_after_test_pct": round(100 * (1 - true_iroas(T[keep]) / true_iroas(T[keep], "effect_cool_krw")), 1),
        },
        "validation_against_truth": {
            "note": "Each estimate is graded against the true iROAS of the regions it covers.",
            "true_effect_pct_all": round(100 * truth["true_revenue_effect_krw"] / truth["go_dark_revenue_cf_krw"], 2),
            "true_brand_search_effect_all": truth["true_brand_search_effect"],
            "all_pairs": {"estimate": summarize(all_rev, T)["iroas"], "truth": true_iroas(T),
                          "ci": summarize(all_rev, T)["iroas_ci"]},
            "after_check": {"estimate": summarize(trim_rev, T[keep])["iroas"], "truth": true_iroas(T[keep]),
                            "ci": summarize(trim_rev, T[keep])["iroas_ci"]},
            "flagged_pair_go_dark_true_iroas": {geos[T[i]]: true_iroas([T[i]])
                                               for i in range(len(pairs)) if i not in keep},
            "brand_search_after_check": {
                "estimate_pct": round(100 * trim_bsv["effect"] / trim_bsv["counterfactual"], 2),
                "ci_pct": [round(100 * trim_bsv["ci_low"] / trim_bsv["counterfactual"], 2),
                           round(100 * trim_bsv["ci_high"] / trim_bsv["counterfactual"], 2)],
                "truth_pct": round(100 * sum(by[geos[i]]["bsv_effect"] for i in T[keep])
                                   / sum(by[geos[i]]["bsv_cf"] for i in T[keep]), 2)},
        },
    }
    (ROOT / "outputs" / "ch1_readout.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in ("all_pairs", "after_check", "validation_against_truth")}, indent=2))
    print("flagged:", flagged_detail)


if __name__ == "__main__":
    main()
