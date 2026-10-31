"""One table: every headline number against the truth and the naive answer.

"Naive" is what the advertiser would conclude without the study: platform
reported ROAS, a before/after comparison, or the model's mean plan.
Writes outputs/validation.json
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / "outputs" / name).read_text())


def main():
    d1, r1, mc = load("ch1_design.json"), load("ch1_readout.json"), load("ch1_montecarlo.json")
    c2, c3, c4 = load("ch2_causal_impact.json"), load("ch3_auto_bidding.json"), load("ch4_mmm.json")
    hist = pd.read_parquet(ROOT / "data" / "history_daily.parquet")

    def reported(cols):
        return hist[[f"reported_rev_{c}" for c in cols]].sum().sum() / hist[[f"spend_{c}" for c in cols]].sum().sum()

    v1 = r1["validation_against_truth"]
    six = next(e for e in d1["eligibility"] if e["weeks"] == 6)
    rows = [
        {"chapter": 1, "quantity": "Short video iROAS (geo test, 19 pairs after check)",
         "naive": f"{reported(['short_video']):.2f} (platform-reported ROAS)",
         "estimate": v1["after_check"]["estimate"], "interval": v1["after_check"]["ci"],
         "truth": v1["after_check"]["truth"]},
        {"chapter": 1, "quantity": "Brand-search change in go-dark regions, %",
         "naive": "not measured", "estimate": v1["brand_search_after_check"]["estimate_pct"],
         "interval": v1["brand_search_after_check"]["ci_pct"], "truth": v1["brand_search_after_check"]["truth_pct"]},
        {"chapter": 2, "quantity": "Revenue lost in the 4-week video pause, KRW M",
         "naive": f"{c2['naive_before_after']['effect_krw_m']} (before/after)",
         "estimate": c2["causal_impact"]["effect_krw_m"], "interval": c2["causal_impact"]["ci_krw_m"],
         "truth": c2["validation_against_truth"]["true_effect_krw_m"]},
        {"chapter": 2, "quantity": "Short video iROAS from the pause",
         "naive": f"{c2['naive_before_after']['iroas']} (before/after)",
         "estimate": c2["causal_impact"]["iroas"], "interval": c2["causal_impact"]["iroas_ci"],
         "truth": c2["validation_against_truth"]["true_iroas"]},
        {"chapter": 3, "quantity": "Total-sales effect of the auto-bidding switch, KRW M (4 weeks)",
         "naive": f"+{c3['decomposition_4w']['reported_increase_krw_m']} (reported search revenue)",
         "estimate": c3["total_sales_rdit"]["incremental_revenue_4w_krw_m"],
         "interval": c3["total_sales_rdit"]["incremental_ci_krw_m"],
         "truth": c3["validation_against_truth"]["true_incremental_krw_m"]},
        {"chapter": 3, "quantity": "Marginal iROAS of the 30% search budget increase",
         "naive": f"{c3['platform_view']['reported_roas_after']} (reported ROAS)",
         "estimate": c3["budget_increase"]["marginal_iroas"], "interval": c3["budget_increase"]["marginal_iroas_ci"],
         "truth": c3["validation_against_truth"]["budget_increase_true_marginal_iroas"]},
    ]
    after = c4["models"]["after_tests"]["roi"]
    naive_roi = {"search": reported(["brand_search", "nonbrand_search"]),
                 "short_video": reported(["short_video"]), "social": reported(["social"]),
                 "retargeting": reported(["retargeting"])}
    for c in c4["channels"]:
        rows.append({"chapter": 4, "quantity": f"{c.replace('_', ' ').capitalize()} ROI, weeks 1-78 (calibrated MMM, 90%)",
                     "naive": f"{naive_roi[c]:.2f} (platform-reported ROAS)",
                     "estimate": after[c]["median"], "interval": after[c]["ci90"], "truth": after[c]["truth"]})
    xp = load("cross_platform.json")["totals"]
    rows.append({"chapter": 4, "quantity": "Revenue added by all ads, weeks 1-78, KRW M (calibrated MMM, 90%)",
                 "naive": f"{xp['reported_krw_m']:,.0f} (sum of platform reports)",
                 "estimate": xp["incremental_krw_m"], "interval": xp["incremental_ci90_krw_m"],
                 "truth": xp["true_incremental_krw_m"]})
    for r in rows:
        lo, hi = sorted(r["interval"])
        r["truth_inside"] = bool(lo <= r["truth"] <= hi)

    best = c4["true_best_plan"]["true_gain_krw_m"]
    checks = {
        "aa_false_positives_6w": {"uncalibrated": six["aa_false_positive_uncalibrated"],
                                  "calibrated_holdout": six["aa_false_positive_holdout"]},
        "monte_carlo_60_draws": mc,
        "budget_plans_share_of_best": {name: {k: p["share_of_best_possible"] for k, p in m["plans"].items()}
                                       for name, m in c4["models"].items()},
        "best_possible_gain_krw_m": best,
        "placebo": {"ch2": c2["placebo_checks"], "ch3_p": c3["total_sales_rdit"]["placebo_p"],
                    "ch3_dates": c3["total_sales_rdit"]["placebo_dates"]},
        "convergence": {"ch2_max_rhat": c2["causal_impact"]["max_rhat"], "ch2_divergences": c2["causal_impact"]["divergences"],
                        **{f"ch4_{n}_max_rhat": m["max_rhat"] for n, m in c4["models"].items()},
                        **{f"ch4_{n}_divergences": m["divergences"] for n, m in c4["models"].items()}},
    }
    # one channel, six reads: why short video's return differs by source, and what to quote
    cool = r1["with_cooldown"]
    tri = [
        {"source": "Platform-reported ROAS", "weeks": "1-78", "estimate": round(reported(["short_video"]), 2),
         "interval": None, "truth": None, "why": "Counts only clicked sales; misses viewers who buy later"},
        {"source": "Geo test, 6 test weeks", "weeks": "79-84", "estimate": v1["after_check"]["estimate"],
         "interval": v1["after_check"]["ci"], "truth": v1["after_check"]["truth"],
         "why": "Cleanest causal read; misses the effect that lands after video is back on"},
        {"source": "Geo test, + 2-week cooldown", "weeks": "79-86", "estimate": cool["revenue"]["iroas"],
         "interval": cool["revenue"]["iroas_ci"], "truth": cool["truth_iroas"],
         "why": "Adds the slower awareness effect; noisier"},
        {"source": "Pause, causal impact", "weeks": "89-92", "estimate": c2["causal_impact"]["iroas"],
         "interval": c2["causal_impact"]["iroas_ci"], "truth": c2["validation_against_truth"]["true_iroas"],
         "why": "No holdout, model-based; summer weeks at a lower budget"},
        {"source": "MMM, calibrated (90%)", "weeks": "1-78", "estimate": after["short_video"]["median"],
         "interval": after["short_video"]["ci90"], "truth": after["short_video"]["truth"],
         "why": "Average over 78 weeks at varying budgets, including carry-over"},
        {"source": "MMM, all weeks (90%)", "weeks": "1-104", "estimate": c4["models"]["all_weeks"]["roi"]["short_video"]["median"],
         "interval": c4["models"]["all_weeks"]["roi"]["short_video"]["ci90"],
         "truth": c4["models"]["all_weeks"]["roi"]["short_video"]["truth"],
         "why": "Average over all 104 weeks; uses the tests' spend swings as data"},
    ]
    causal = [t["estimate"] for t in tri[1:]]
    video_triangulation = {
        "rows": tri,
        "quote": [v1["after_check"]["estimate"], cool["revenue"]["iroas"]],
        "spread": [min(causal), max(causal)],
        "message": (f"Quote {v1['after_check']['estimate']:.1f}-{cool['revenue']['iroas']:.1f} from the experiment (6 weeks, and with the cooldown). "
                    f"Every causal read lands between {min(causal):.1f} and {max(causal):.1f}, all above break-even on sales; "
                    f"they differ because they cover different weeks, budgets and carry-over, not because they disagree. "
                    f"The platform's {reported(['short_video']):.2f} is the outlier."),
    }

    out = {"rows": rows, "covered": sum(r["truth_inside"] for r in rows), "n": len(rows), "checks": checks,
           "video_triangulation": video_triangulation}
    (ROOT / "outputs" / "validation.json").write_text(json.dumps(out, indent=2))
    for r in rows:
        print(f"{r['chapter']} {r['quantity'][:55]:55s} naive={r['naive']:>32s} est={r['estimate']} {r['interval']} truth={r['truth']} {'OK' if r['truth_inside'] else 'MISS'}")
    print(out["covered"], "/", out["n"])


if __name__ == "__main__":
    main()
