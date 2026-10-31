"""Cross-platform view: what each platform claims vs what it adds (chapter 4).

Every ad platform reports the revenue it credits to itself. Added up across
platforms, those claims are compared with the incremental revenue the
calibrated MMM (weeks 1-78, checked against two experiments) attributes to each
channel, and with the truth. Channels the platforms under-credit are where the
headroom is; channels they over-credit are where budget is safest to trim.

Inputs: marts platform_claims and period_revenue (sql/marts.sql), the cached
after_tests MMM draws, chapter 1's geo-test iROAS, chapter 4's true ROI.
Writes outputs/cross_platform.json
"""
import json
from pathlib import Path

import numpy as np

from build_marts import read as read_mart
from mmm_core import CHANNELS

ROOT = Path(__file__).resolve().parents[1]
PERIOD = "weeks_1_78"


def main():
    claims = read_mart("platform_claims").query("period == @PERIOD").set_index("channel").loc[CHANNELS]
    revenue = float(read_mart("period_revenue").set_index("period").loc[PERIOD, "revenue"])
    draws = np.load(ROOT / "models" / "ch4_after_tests.npz")["roi"]            # (S, C)
    ch4 = json.loads((ROOT / "outputs" / "ch4_mmm.json").read_text())
    true_roi = ch4["true_roi"]["weeks_1_78"]
    geo = json.loads((ROOT / "outputs" / "ch1_readout.json").read_text())["after_check"]["revenue"]

    spend = claims.spend.to_numpy()
    reported = claims.reported.to_numpy()
    incr = draws * spend[None, :]                                                # (S, C) KRW
    truth = np.array([true_roi[c] for c in CHANNELS]) * spend

    def verdict(rep, lo, hi):
        """Under/over-credited only when the report sits outside the model's 90% range."""
        return "under-credited" if rep < lo else "over-credited" if rep > hi else "unclear"

    rows = []
    for j, c in enumerate(CHANNELS):
        med = float(np.median(incr[:, j]))
        lo, hi = (float(np.quantile(incr[:, j], q)) for q in (0.05, 0.95))
        rows.append({
            "channel": c,
            "spend_krw_m": round(spend[j] / 1e6, 1),
            "reported_krw_m": round(reported[j] / 1e6, 1),
            "reported_roas": round(reported[j] / spend[j], 2),
            "incremental_krw_m": round(med / 1e6, 1),
            "incremental_ci90_krw_m": [round(float(np.quantile(incr[:, j], q)) / 1e6, 1) for q in (0.05, 0.95)],
            "incremental_roi": round(med / spend[j], 2),
            "true_incremental_krw_m": round(truth[j] / 1e6, 1),
            "true_roi": true_roi[c],
            "credit_ratio": round(reported[j] / med, 2),          # reported / incremental
            "true_credit_ratio": round(reported[j] / truth[j], 2),
            "verdict": verdict(reported[j], lo, hi),
            "true_verdict": "under-credited" if reported[j] < truth[j] else "over-credited",
        })

    total_incr = incr.sum(axis=1)
    out = {
        "question": "Each platform reports its own results. Added up, how much do they claim, and what do they add?",
        "period": "weeks 1-78 (before any test)",
        "channels": rows,
        "totals": {
            "spend_krw_m": round(spend.sum() / 1e6, 1),
            "reported_krw_m": round(reported.sum() / 1e6, 1),
            "incremental_krw_m": round(float(np.median(total_incr)) / 1e6, 1),
            "incremental_ci90_krw_m": [round(float(np.quantile(total_incr, q)) / 1e6, 1) for q in (0.05, 0.95)],
            "true_incremental_krw_m": round(truth.sum() / 1e6, 1),
            "claimed_vs_added": round(reported.sum() / float(np.median(total_incr)), 2),
            "claimed_vs_added_ci90": [round(reported.sum() / float(np.quantile(total_incr, q)), 2) for q in (0.95, 0.05)],
            "true_claimed_vs_added": round(reported.sum() / truth.sum(), 2),
            "revenue_krw_m": round(revenue / 1e6, 1),
            "share_claimed_by_ads_pct": round(100 * reported.sum() / revenue, 1),
            "share_added_by_ads_pct": round(100 * float(np.median(total_incr)) / revenue, 1),
            "true_share_added_by_ads_pct": round(100 * truth.sum() / revenue, 1),
        },
        "experiment_check": {
            "short_video_geo_test_iroas": geo["iroas"], "short_video_geo_test_ci": geo["iroas_ci"],
            "note": "The geo test (weeks 79-84) independently puts short video's return near the model's, far above the 0.30 its platform reports.",
        },
    }
    (ROOT / "outputs" / "cross_platform.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out["totals"], indent=1))
    for r in rows:
        print(f"{r['channel']:12s} reported ROAS {r['reported_roas']:5.2f}  MMM ROI {r['incremental_roi']:5.2f}  truth {r['true_roi']:5.2f}  "
              f"credit x{r['credit_ratio']:.2f} (true x{r['true_credit_ratio']:.2f})  {r['verdict']}")


if __name__ == "__main__":
    main()
