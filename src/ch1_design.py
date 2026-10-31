"""Chapter 1 design: can a go-dark geo test read short-video incrementality?

Uses only the 78-week history (what the advertiser has before the test).
  1. pair the 40 regions by pre-period revenue (adjacent ranks) -> 20 pairs
  2. randomize one region per pair into the go-dark group (video off)
  3. A/A tests on past windows: nothing injected -> how often does TBR cry wolf?
  4. power by simulation: inject a known revenue loss into the go-dark group on
     past windows, for 2/4/6/8-week tests -> minimum detectable effect (MDE)
  5. turn the MDE into eligibility: the smallest video budget at which an
     incremental ROAS (iROAS) of 1.0 would show up as significant
Writes outputs/ch1_design.json and data/geo_assignment.csv
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from geo_tbr import Z95, calibration_factor, tbr

ROOT = Path(__file__).resolve().parents[1]
PRE_FIT_DAYS = 84            # 12 weeks of pre-period for the TBR fit
PAIRING_WEEKS = (27, 78)     # last 52 weeks of history
DURATIONS = [2, 4, 6, 8]     # test length in weeks
DELTAS = np.round(np.arange(0.0, 0.0801, 0.001), 3)  # revenue loss in go-dark group
N_ASSIGN = 40                # random assignments per past window
PLANNED_VIDEO_M = 2.5        # planned national video budget during test, M KRW/day
PRIOR_IROAS = (0.5, 2.0)     # plausible range before testing (not the reported 0.3)
ASSIGN_SEED = 79


def matrix(df: pd.DataFrame, col: str) -> tuple[np.ndarray, list]:
    wide = df.pivot(index="date", columns="geo", values=col).sort_index()
    return wide.to_numpy(), list(wide.columns)


def make_pairs(Y: np.ndarray, weeks: np.ndarray) -> np.ndarray:
    mask = (weeks >= PAIRING_WEEKS[0]) & (weeks <= PAIRING_WEEKS[1])
    order = np.argsort(-Y[mask].sum(axis=0))
    return order.reshape(-1, 2)


def assign(pairs: np.ndarray, rng) -> tuple[np.ndarray, np.ndarray]:
    flip = rng.integers(0, 2, len(pairs))
    treat = pairs[np.arange(len(pairs)), flip]
    ctrl = pairs[np.arange(len(pairs)), 1 - flip]
    return treat, ctrl


def assign_share(order: np.ndarray, share: float, rng) -> tuple[np.ndarray, np.ndarray]:
    """Unequal split: regions ranked by size in blocks of 10, `share` of each block treated."""
    blocks = order.reshape(-1, 10)
    k = int(round(10 * share))
    treat = np.concatenate([rng.choice(b, k, replace=False) for b in blocks])
    return treat, np.setdiff1d(order, treat)


def past_windows(n_days: int, test_days: int) -> list[int]:
    first = PAIRING_WEEKS[0] * 7 - 7 + PRE_FIT_DAYS  # pre-fit stays inside the pairing year
    return list(range(first, n_days - test_days + 1, 7))


def simulate_power(Y: np.ndarray, draw, rng, durations=DURATIONS) -> dict:
    """For each duration: A/A calibration, power curve over DELTAS, MDE.

    `draw(rng)` returns one random (treated, control) assignment. Every past
    window is an A/A test (nothing happened there). The SE factor is learned on
    the earlier half of windows and checked on the later half, then re-learned
    on all windows for the power curve and the real readout.
    """
    n_days = Y.shape[0]
    out = {}
    for weeks in durations:
        d = weeks * 7
        starts, effects, ses, totals = [], [], [], []
        for s in past_windows(n_days, d):
            pre, test = slice(s - PRE_FIT_DAYS, s), slice(s, s + d)
            for _ in range(N_ASSIGN):
                t, c = draw(rng)
                yt, yc = Y[:, t].sum(axis=1), Y[:, c].sum(axis=1)
                r = tbr(yt, yc, pre, test)
                starts.append(s)
                effects.append(r["effect"])
                ses.append(r["se_raw"])
                totals.append(r["actual"])
        s_, e, se_raw, tot = map(np.array, (starts, effects, ses, totals))
        z = e / se_raw
        early = s_ < np.median(s_)
        k_early = calibration_factor(z[early])
        holdout_fpr = float(np.mean(np.abs(z[~early]) > Z95 * k_early))
        k = calibration_factor(z)
        se = se_raw * k
        # injecting a loss of delta * (go-dark revenue) shifts the TBR effect by
        # exactly that amount; detection = whole 95% interval below zero
        shifted = e[:, None] - DELTAS[None, :] * tot[:, None]
        detected = (shifted + Z95 * se[:, None]) < 0
        power = detected.mean(axis=0)
        idx = np.where(power >= 0.8)[0]
        mde = float(DELTAS[idx[0]]) if len(idx) else None
        out[weeks] = {"power": power.round(3).tolist(),
                      "aa_false_positive_uncalibrated": round(float(np.mean(np.abs(z) > Z95)), 3),
                      "aa_mean_z": round(float(z.mean()), 2),
                      "se_scale": round(k, 2),
                      "aa_false_positive_holdout": round(holdout_fpr, 3),
                      "mde_share": mde, "n_sims": int(len(e)),
                      "mean_test_revenue": float(tot.mean())}
    return out


def main():
    hist = pd.read_parquet(ROOT / "data" / "history_daily.parquet")
    Y, geos = matrix(hist, "revenue")
    B, _ = matrix(hist, "brand_search_volume")
    V, _ = matrix(hist, "spend_short_video")
    weeks = hist.drop_duplicates("date").sort_values("date")["week"].to_numpy()

    pairs = make_pairs(Y, weeks)
    rng = np.random.default_rng(ASSIGN_SEED)
    treat, ctrl = assign(pairs, rng)

    # balance and pre-period fit for the chosen assignment (last 12 weeks)
    n = Y.shape[0]
    pre = slice(n - PRE_FIT_DAYS, n)
    yt, yc = Y[:, treat].sum(axis=1), Y[:, ctrl].sum(axis=1)
    ratio = yt[pre].sum() / yc[pre].sum()
    resid = yt[pre] - ratio * yc[pre]
    prefit = {"ratio": round(float(ratio), 3),
              "mape": round(float(np.mean(np.abs(resid) / yt[pre])), 4),
              "corr": round(float(np.corrcoef(yt[pre], yc[pre])[0, 1]), 3)}
    rev_share = float(Y[pre][:, treat].sum() / Y[pre].sum())
    video_share = float(V[pre][:, treat].sum() / V[pre].sum())

    sim_rng = np.random.default_rng(2026)
    paired = lambda r: assign(pairs, r)  # noqa: E731
    power_rev = simulate_power(Y, paired, sim_rng)
    power_bsv = simulate_power(B, paired, sim_rng)

    eligibility = []
    for w in DURATIONS:
        p = power_rev[w]
        days = w * 7
        mde_krw = p["mde_share"] * p["mean_test_revenue"] if p["mde_share"] else None
        saved = PLANNED_VIDEO_M * 1e6 * video_share * days
        min_iroas = mde_krw / saved if mde_krw else None
        min_budget = mde_krw / (video_share * days * 1.0) / 1e6 if mde_krw else None
        eligibility.append({
            "weeks": w,
            "aa_false_positive_uncalibrated": p["aa_false_positive_uncalibrated"],
            "se_scale": p["se_scale"],
            "aa_false_positive_holdout": p["aa_false_positive_holdout"],
            "mde_revenue_pct": round(100 * p["mde_share"], 1) if p["mde_share"] else None,
            "mde_revenue_krw_m": round(mde_krw / 1e6, 1) if mde_krw else None,
            "mde_brand_search_pct": (round(100 * power_bsv[w]["mde_share"], 1)
                                     if power_bsv[w]["mde_share"] else None),
            "video_spend_withheld_krw_m": round(saved / 1e6, 1),
            "min_detectable_iroas": round(min_iroas, 2) if min_iroas else None,
            "min_national_video_budget_for_iroas1_m_per_day": round(min_budget, 2) if min_budget else None,
            "revenue_at_risk_krw_m": [round(r * saved / 1e6, 1) for r in PRIOR_IROAS],
        })

    # design options an advertiser may push for: a smaller go-dark share, or a
    # heavy-up (+50% video in treated regions) that never switches video off
    alt_rng = np.random.default_rng(2027)
    order = pairs.ravel()
    third = lambda r: assign_share(order, 0.3, r)  # noqa: E731
    power_30 = simulate_power(Y, third, alt_rng, durations=[6, 8])
    share_30 = float(np.mean([V[pre][:, t].sum() / V[pre].sum()
                              for t, _ in (third(alt_rng) for _ in range(400))]))

    def option(name, measures, p, weeks, video_share_, spend_mult, at_risk):
        days = weeks * 7
        mde_krw = p["mde_share"] * p["mean_test_revenue"]
        moved = PLANNED_VIDEO_M * 1e6 * video_share_ * days * spend_mult
        return {"design": name, "measures": measures, "weeks": weeks,
                "treated_share_of_video_pct": round(100 * video_share_),
                "mde_revenue_pct": round(100 * p["mde_share"], 1),
                "mde_revenue_krw_m": round(mde_krw / 1e6, 1),
                "spend_moved_krw_m": round(moved / 1e6, 1),
                "min_detectable_return": round(mde_krw / moved, 2),
                "revenue_at_risk_krw_m": [round(r * moved / 1e6, 1) for r in PRIOR_IROAS] if at_risk else None}

    design_options = [
        option("Go-dark, half the regions (chosen)", "average return", power_rev[6], 6, video_share, 1.0, True),
        option("Go-dark, 30% of regions", "average return", power_30[6], 6, share_30, 1.0, True),
        option("Go-dark, 30% of regions", "average return", power_30[8], 8, share_30, 1.0, True),
        option("Heavy-up +50%, half the regions", "marginal return", power_rev[6], 6, video_share, 0.5, False),
    ]

    chosen = next(e for e in eligibility if e["weeks"] == 6)
    design = {
        "question": "Does short-form video drive incremental revenue for PAWLY?",
        "design": "Go-dark geo test: short video switched off in one region of each matched pair",
        "test_weeks": [79, 84],
        "pre_fit_days": PRE_FIT_DAYS,
        "kpis": ["revenue (primary)", "brand search volume (secondary, search lift)"],
        "planned_video_budget_m_per_day": PLANNED_VIDEO_M,
        "prior_iroas_range": PRIOR_IROAS,
        "pairs": [[geos[i] for i in p] for p in pairs],
        "go_dark": [geos[i] for i in treat],
        "control": [geos[i] for i in ctrl],
        "balance": {"go_dark_revenue_share": round(rev_share, 3),
                    "go_dark_video_spend_share": round(video_share, 3)},
        "prefit_last_12_weeks": prefit,
        "eligibility": eligibility,
        "design_options": design_options,
        "power_curves": {
            "deltas_pct": (100 * DELTAS).round(1).tolist(),
            "revenue": {w: power_rev[w]["power"] for w in DURATIONS},
            "brand_search": {w: power_bsv[w]["power"] for w in DURATIONS},
            "n_sims": {w: power_rev[w]["n_sims"] for w in DURATIONS},
        },
        "recommendation": {
            "weeks": 6,
            "why": (f"6 weeks detects a {chosen['mde_revenue_pct']}% revenue drop in the go-dark "
                    f"regions, i.e. any iROAS of {chosen['min_detectable_iroas']} or more, with 80% power. "
                    f"That covers most of the plausible range {PRIOR_IROAS[0]}-{PRIOR_IROAS[1]}; "
                    f"8 weeks adds little. A/A false positives "
                    f"{chosen['aa_false_positive_holdout']:.1%} on held-out past windows."),
        },
        "estimator": ("Proportional time-based regression (TBR) on daily group totals; "
                      "95% interval = AR(1)-adjusted SE x A/A calibration factor"),
        "se_scale": {w: power_rev[w]["se_scale"] for w in DURATIONS},
        "se_scale_brand_search": {w: power_bsv[w]["se_scale"] for w in DURATIONS},
        "aa_mean_z": {w: power_rev[w]["aa_mean_z"] for w in DURATIONS},
    }
    (ROOT / "outputs" / "ch1_design.json").write_text(json.dumps(design, indent=2))
    pd.DataFrame({"geo": geos,
                  "group": ["go_dark" if i in set(treat) else "control" for i in range(len(geos))],
                  "pair": [int(np.where(pairs == i)[0][0]) + 1 for i in range(len(geos))]}
                 ).to_csv(ROOT / "data" / "geo_assignment.csv", index=False)

    print(json.dumps({k: design[k] for k in ("balance", "prefit_last_12_weeks", "recommendation")}, indent=2))
    print(pd.DataFrame(eligibility).to_string(index=False))


if __name__ == "__main__":
    main()
