"""Chapter 3: search moved to AI auto-bidding and reported revenue jumped. Real?

  1. what the platform reports: search-credited revenue and ROAS, 4 weeks
     before vs 4 weeks after the switch
  2. what total sales did: regression discontinuity in time (RDiT) on daily
     log revenue, +-28 days, separate slopes on each side, day-of-week and
     log category searches as controls, HAC standard errors
  3. placebo test: the same regression at every quiet past date; how often
     does normal business produce a jump as large as the one measured?
  4. split the reported increase into true incremental sales and sales that
     were already happening and are now credited to auto-bidding
  5. after the budget increase: ad spend per won of sales
Writes outputs/ch3_auto_bidding.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

from build_marts import read as read_mart

ROOT = Path(__file__).resolve().parents[1]
SWITCH_WEEK = 97
BUDGET_UP_WEEK = 101
BANDWIDTH = 28
SEARCH = ["brand_search", "nonbrand_search", "auto_bid"]
PLACEBO_WEEKS = (6, 74)  # windows fully inside the history, before the geo test


def rdit(nat: pd.DataFrame, cut: int) -> dict:
    """Jump in log revenue at day index `cut`."""
    w = nat.iloc[cut - BANDWIDTH: cut + BANDWIDTH].copy()
    t = np.arange(-BANDWIDTH, BANDWIDTH)
    post = (t >= 0).astype(float)
    X = pd.DataFrame({"post": post, "t": t, "t_post": t * post,
                      "log_cat": np.log(w.category_search_index.to_numpy())})
    dow = pd.get_dummies(w.date.dt.dayofweek, prefix="d", drop_first=True).astype(float)
    X = sm.add_constant(pd.concat([X.reset_index(drop=True), dow.reset_index(drop=True)], axis=1))
    fit = sm.OLS(np.log(w.revenue.to_numpy()), X).fit(cov_type="HAC", cov_kwds={"maxlags": 7})
    return {"jump": float(fit.params["post"]), "se": float(fit.bse["post"])}


def main():
    nat = read_mart("national_day")  # sql/marts.sql
    cut = int(np.argmax(nat.week.to_numpy() == SWITCH_WEEK))
    before = nat.iloc[cut - BANDWIDTH: cut]
    after = nat.iloc[cut: cut + BANDWIDTH]

    rep_b, rep_a = before.search_reported.sum(), after.search_reported.sum()
    sp_b, sp_a = before.search_spend.sum(), after.search_spend.sum()
    reported = {
        "reported_search_revenue_before_krw_m": round(rep_b / 1e6, 1),
        "reported_search_revenue_after_krw_m": round(rep_a / 1e6, 1),
        "reported_increase_pct": round(100 * (rep_a / rep_b - 1), 1),
        "reported_roas_before": round(rep_b / sp_b, 2),
        "reported_roas_after": round(rep_a / sp_a, 2),
        "ad_credited_share_of_revenue_before_pct": round(100 * before[[f"reported_rev_{c}" for c in SEARCH]].sum().sum() / before.revenue.sum(), 1),
        "ad_credited_share_of_revenue_after_pct": round(100 * after[[f"reported_rev_{c}" for c in SEARCH]].sum().sum() / after.revenue.sum(), 1),
        "total_revenue_change_pct_raw": round(100 * (after.revenue.sum() / before.revenue.sum() - 1), 1),
        "brand_search_volume_change_pct": round(100 * (after.brand_search_volume.sum() / before.brand_search_volume.sum() - 1), 1),
    }

    r = rdit(nat, cut)
    pct = np.exp(r["jump"]) - 1
    lo, hi = np.exp(r["jump"] - 1.96 * r["se"]) - 1, np.exp(r["jump"] + 1.96 * r["se"]) - 1
    incr = after.revenue.sum() * (1 - np.exp(-r["jump"]))
    incr_lo = after.revenue.sum() * (1 - 1 / (1 + lo))
    incr_hi = after.revenue.sum() * (1 - 1 / (1 + hi))

    weeks = nat.week.to_numpy()
    cand = [i for i in range(BANDWIDTH, len(nat) - BANDWIDTH)
            if weeks[i - BANDWIDTH] >= PLACEBO_WEEKS[0] and weeks[i + BANDWIDTH - 1] <= PLACEBO_WEEKS[1] + 4]
    placebo = np.array([rdit(nat, i)["jump"] for i in cand])
    p_placebo = float(np.mean(np.abs(placebo) >= abs(r["jump"])))

    rep_increase = rep_a - rep_b
    recredited = rep_increase - incr

    # the budget increase that followed the high reported ROAS: what did it buy?
    cut_up = int(np.argmax(nat.week.to_numpy() == BUDGET_UP_WEEK))
    r_up = rdit(nat, cut_up)
    up_after = nat.iloc[cut_up: cut_up + BANDWIDTH]
    up_before = nat.iloc[cut_up - BANDWIDTH: cut_up]
    extra_spend = up_after.search_spend.sum() - up_before.search_spend.sum()
    up_incr = up_after.revenue.sum() * (1 - np.exp(-r_up["jump"]))
    up_lo = up_after.revenue.sum() * (1 - np.exp(-(r_up["jump"] - 1.96 * r_up["se"])))
    up_hi = up_after.revenue.sum() * (1 - np.exp(-(r_up["jump"] + 1.96 * r_up["se"])))
    search_ratio_before = before.search_spend.sum() / before.revenue.sum()
    search_ratio_after = up_after.search_spend.sum() / up_after.revenue.sum()

    effects = json.loads((ROOT / "data" / "truth" / "effects.json").read_text())
    truth, truth_up = effects["auto_bid_switch"], effects["budget_up"]
    out = {
        "question": "Reported search revenue jumped after the switch to AI auto-bidding. Did sales?",
        "switch_week": SWITCH_WEEK, "bandwidth_days": BANDWIDTH,
        "platform_view": reported,
        "total_sales_rdit": {
            "jump_pct": round(100 * pct, 2), "ci_pct": [round(100 * lo, 2), round(100 * hi, 2)],
            "incremental_revenue_4w_krw_m": round(incr / 1e6, 1),
            "incremental_ci_krw_m": [round(incr_lo / 1e6, 1), round(incr_hi / 1e6, 1)],
            "placebo_dates": len(cand), "placebo_p": round(p_placebo, 3),
            "placebo_jumps_pct": (100 * (np.exp(placebo) - 1)).round(2).tolist(),
        },
        "decomposition_4w": {
            "reported_increase_krw_m": round(rep_increase / 1e6, 1),
            "true_incremental_krw_m": round(incr / 1e6, 1),
            "recredited_krw_m": round(recredited / 1e6, 1),
            "recredited_share_pct": round(100 * recredited / rep_increase, 1),
        },
        "budget_increase": {
            "week": BUDGET_UP_WEEK,
            "extra_search_spend_4w_krw_m": round(extra_spend / 1e6, 1),
            "revenue_jump_pct": round(100 * (np.exp(r_up["jump"]) - 1), 2),
            "incremental_revenue_4w_krw_m": round(up_incr / 1e6, 1),
            "incremental_ci_krw_m": [round(up_lo / 1e6, 1), round(up_hi / 1e6, 1)],
            "marginal_iroas": round(up_incr / extra_spend, 2),
            "marginal_iroas_ci": [round(up_lo / extra_spend, 2), round(up_hi / extra_spend, 2)],
            "search_spend_per_sales_before_switch_pct": round(100 * search_ratio_before, 2),
            "search_spend_per_sales_after_increase_pct": round(100 * search_ratio_after, 2),
        },
        "series": {"date": nat.date.dt.strftime("%Y-%m-%d").iloc[cut - BANDWIDTH: cut + BANDWIDTH].tolist(),
                   "revenue": nat.revenue.iloc[cut - BANDWIDTH: cut + BANDWIDTH].round().tolist(),
                   "search_reported": nat.search_reported.iloc[cut - BANDWIDTH: cut + BANDWIDTH].round().tolist()},
        "validation_against_truth": {
            "true_incremental_krw_m": round(truth["true_revenue_effect_krw"] / 1e6, 1),
            "true_effect_pct": truth["true_effect_pct_of_revenue"],
            "truth_inside_ci": bool(incr_lo <= truth["true_revenue_effect_krw"] <= incr_hi),
            "true_recredited_share_pct": round(100 * (1 - truth["true_revenue_effect_krw"]
                                                      / truth["reported_search_revenue_increase_krw"]), 1),
            "budget_increase_true_marginal_iroas": truth_up["true_marginal_iroas"],
            "budget_increase_truth_inside_ci": bool(up_lo / extra_spend <= truth_up["true_marginal_iroas"]
                                                    <= up_hi / extra_spend),
        },
    }
    (ROOT / "outputs" / "ch3_auto_bidding.json").write_text(json.dumps(out, indent=2))
    show = {k: v for k, v in out.items() if k != "series"}
    show["total_sales_rdit"] = {k: v for k, v in out["total_sales_rdit"].items() if k != "placebo_jumps_pct"}
    print(json.dumps(show, indent=2))


if __name__ == "__main__":
    main()
