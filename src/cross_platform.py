"""Cross-platform view: what each platform claims vs what it adds (chapter 4).

Every ad platform reports the revenue it credits to itself. Added up across
platforms, those claims are compared with the incremental revenue the
calibrated MMM (weeks 1-78, checked against two experiments) attributes to each
channel, and with the truth. Channels the platforms under-credit are where the
headroom is; channels they over-credit are where budget is safest to trim.

A second view uses the advertiser's GA4 data: GA4 counts each website sale once
(data-driven attribution), so its paid total cannot add up past the truth the
way platform claims do; but it sees only the site, and its credit still follows
clicks. Each channel's share of GA4 paid credit is set against its share of what
ads added: a channel GA4 under-shares is the media-mix headroom.

Inputs: marts platform_claims, period_revenue and ga4_channels (sql/marts.sql), the cached
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

    # GA4 view: share of GA4 paid credit vs share of incremental revenue
    ga4 = read_mart("ga4_channels").query("period == @PERIOD").set_index("channel")
    ga4_paid = ga4.loc[CHANNELS, "ga4_revenue"].to_numpy()
    ga4_share = ga4_paid / ga4_paid.sum()
    incr_share = incr / total_incr[:, None]                                     # (S, C)
    true_share = truth / truth.sum()
    ga4_rows = []
    for j, c in enumerate(CHANNELS):
        lo, hi = (float(np.quantile(incr_share[:, j], q)) for q in (0.05, 0.95))
        med = float(np.median(incr_share[:, j]))
        ga4_rows.append({
            "channel": c,
            "channel_group": ga4.loc[c, "channel_group"],
            "ga4_krw_m": round(ga4_paid[j] / 1e6, 1),
            "ga4_roas": round(ga4_paid[j] / spend[j], 2),
            "ga4_share_pct": round(100 * ga4_share[j], 1),
            "incremental_share_pct": round(100 * med, 1),
            "incremental_share_ci90_pct": [round(100 * lo, 1), round(100 * hi, 1)],
            "true_share_pct": round(100 * true_share[j], 1),
            "verdict": ("headroom" if ga4_share[j] < lo else "over-weighted in GA4" if ga4_share[j] > hi else "unclear"),
            "true_verdict": "headroom" if ga4_share[j] < true_share[j] else "over-weighted in GA4",
        })
    ga4_total = float(ga4.ga4_revenue.sum())
    ga4_view = {
        "channels": ga4_rows,
        "ga4_paid_krw_m": round(ga4_paid.sum() / 1e6, 1),
        "ga4_sees_pct_of_revenue": round(100 * ga4_total / revenue, 1),
        "ga4_paid_vs_added": round(ga4_paid.sum() / float(np.median(total_incr)), 2),
        "true_ga4_paid_vs_added": round(ga4_paid.sum() / truth.sum(), 2),
        "note": ("GA4 counts each website sale once, so its paid total stays below what ads added instead of above it: "
                 "it misses marketplace orders and unconsented sessions. Within the mix its credit still follows clicks."),
    }

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
        "ga4": ga4_view,
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
    print(f"GA4 sees {ga4_view['ga4_sees_pct_of_revenue']}% of revenue; GA4 paid {ga4_view['ga4_paid_krw_m']}M = "
          f"x{ga4_view['ga4_paid_vs_added']} of what ads added (true x{ga4_view['true_ga4_paid_vs_added']})")
    for r in ga4_rows:
        print(f"{r['channel']:12s} GA4 share {r['ga4_share_pct']:5.1f}%  added share {r['incremental_share_pct']:5.1f}% "
              f"{r['incremental_share_ci90_pct']}  truth {r['true_share_pct']:5.1f}%  {r['verdict']} (true: {r['true_verdict']})")


if __name__ == "__main__":
    main()
