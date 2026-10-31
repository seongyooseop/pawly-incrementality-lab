"""Run PAWLY's actual 104 weeks and the counterfactual for each chapter.

Writes
  data/observed_daily.parquet   what the analyst sees (all 104 weeks)
  data/truth/effects.json       true effect of each event, for grading only

Trap 4: a retail partner runs a promotion in one control region during the geo
test. The region is picked after the design (the control member of pair 6) so
that the trap lands where it hurts: an inflated control makes the go-dark loss
look bigger than it is.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from world import (AUTO_BID_BUDGET_UP_WEEK, AUTO_BID_SWITCH_WEEK, GEO_TEST_WEEKS, HISTORY_WEEKS,
                   VIDEO_PAUSE_WEEKS, World, actual_plan, week_mask)

ROOT = Path(__file__).resolve().parents[1]
PROMO_PAIR = 6
COOL = (GEO_TEST_WEEKS[0], GEO_TEST_WEEKS[1] + 2)  # test + 2-week cooldown


def total(df: pd.DataFrame, col: str, weeks: tuple, geos=None) -> float:
    m = (df["week"] >= weeks[0]) & (df["week"] <= weeks[1])
    if geos is not None:
        m &= df["geo"].isin(geos)
    return float(df.loc[m, col].sum())


def main():
    world = World()
    asg = pd.read_csv(ROOT / "data" / "geo_assignment.csv")
    idx = {g: i for i, g in enumerate(world.geo_ids)}
    go_dark_geos = asg.loc[asg.group == "go_dark", "geo"].tolist()
    go_dark = np.array([idx[g] for g in go_dark_geos])
    promo_geo_id = asg[(asg.pair == PROMO_PAIR) & (asg.group == "control")]["geo"].item()
    promo_geo = idx[promo_geo_id]

    obs, truth = world.simulate(actual_plan(world, go_dark, promo_geo))
    obs.to_parquet(ROOT / "data" / "observed_daily.parquet", index=False)
    truth.to_parquet(ROOT / "data" / "truth" / "actual_truth.parquet", index=False)

    # history must be identical to what the design used
    hist = pd.read_parquet(ROOT / "data" / "history_daily.parquet")
    same = np.allclose(hist["revenue"].to_numpy(),
                       obs.loc[obs.week <= HISTORY_WEEKS, "revenue"].to_numpy())

    cf_geo, _ = world.simulate(actual_plan(world, go_dark, promo_geo, geo_test=False))
    cf_pause, _ = world.simulate(actual_plan(world, go_dark, promo_geo, pause=False))
    cf_switch, _ = world.simulate(actual_plan(world, go_dark, promo_geo, switch=False))
    cf_up, _ = world.simulate(actual_plan(world, go_dark, promo_geo, budget_up=False))

    test_spend_cf = total(cf_geo, "spend_short_video", GEO_TEST_WEEKS, go_dark_geos)
    geo_rev = (total(obs, "revenue", GEO_TEST_WEEKS, go_dark_geos)
               - total(cf_geo, "revenue", GEO_TEST_WEEKS, go_dark_geos))
    geo_bsv = (total(obs, "brand_search_volume", GEO_TEST_WEEKS, go_dark_geos)
               - total(cf_geo, "brand_search_volume", GEO_TEST_WEEKS, go_dark_geos))
    pause_rev = total(obs, "revenue", VIDEO_PAUSE_WEEKS) - total(cf_pause, "revenue", VIDEO_PAUSE_WEEKS)
    pause_spend = total(cf_pause, "spend_short_video", VIDEO_PAUSE_WEEKS)
    sw = (AUTO_BID_SWITCH_WEEK, AUTO_BID_SWITCH_WEEK + 3)
    switch_rev = total(obs, "revenue", sw) - total(cf_switch, "revenue", sw)
    rep_cols = [f"reported_rev_{c}" for c in ("brand_search", "nonbrand_search", "auto_bid")]
    rep_actual = sum(total(obs, c, sw) for c in rep_cols)
    rep_cf = sum(total(cf_switch, c, sw) for c in rep_cols)

    effects = {
        "history_unchanged": bool(same),
        "promo_region": promo_geo_id,
        "geo_test": {
            "weeks": GEO_TEST_WEEKS,
            "true_revenue_effect_krw": round(geo_rev),
            "true_brand_search_effect": round(geo_bsv),
            "video_spend_withheld_krw": round(test_spend_cf),
            "true_iroas": round(-geo_rev / test_spend_cf, 3),
            "go_dark_revenue_cf_krw": round(total(cf_geo, "revenue", GEO_TEST_WEEKS, go_dark_geos)),
            "by_region": {g: {"effect_krw": round(total(obs, "revenue", GEO_TEST_WEEKS, [g])
                                                  - total(cf_geo, "revenue", GEO_TEST_WEEKS, [g])),
                              "withheld_krw": round(total(cf_geo, "spend_short_video", GEO_TEST_WEEKS, [g])),
                              "bsv_effect": round(total(obs, "brand_search_volume", GEO_TEST_WEEKS, [g])
                                                  - total(cf_geo, "brand_search_volume", GEO_TEST_WEEKS, [g])),
                              "bsv_cf": round(total(cf_geo, "brand_search_volume", GEO_TEST_WEEKS, [g])),
                              "effect_cool_krw": round(total(obs, "revenue", COOL, [g])
                                                       - total(cf_geo, "revenue", COOL, [g]))}
                          for g in go_dark_geos},
            "cooldown_weeks": [GEO_TEST_WEEKS[1] + 1, COOL[1]],
        },
        "video_pause": {
            "weeks": VIDEO_PAUSE_WEEKS,
            "true_revenue_effect_krw": round(pause_rev),
            "video_spend_saved_krw": round(pause_spend),
            "true_iroas": round(-pause_rev / pause_spend, 3),
        },
        "auto_bid_switch": {
            "weeks": sw,
            "true_revenue_effect_krw": round(switch_rev),
            "true_effect_pct_of_revenue": round(100 * switch_rev / total(cf_switch, "revenue", sw), 2),
            "reported_search_revenue_increase_krw": round(rep_actual - rep_cf),
            "reported_increase_pct": round(100 * (rep_actual / rep_cf - 1), 1),
        },
        "budget_up": {
            "weeks": (AUTO_BID_BUDGET_UP_WEEK, AUTO_BID_BUDGET_UP_WEEK + 3),
            "true_revenue_effect_krw": round(total(obs, "revenue", (AUTO_BID_BUDGET_UP_WEEK, 104))
                                             - total(cf_up, "revenue", (AUTO_BID_BUDGET_UP_WEEK, 104))),
            "extra_spend_krw": round(total(obs, "spend_auto_bid", (AUTO_BID_BUDGET_UP_WEEK, 104))
                                     - total(cf_up, "spend_auto_bid", (AUTO_BID_BUDGET_UP_WEEK, 104))),
        },
    }
    bu = effects["budget_up"]
    bu["true_marginal_iroas"] = round(bu["true_revenue_effect_krw"] / bu["extra_spend_krw"], 3)
    (ROOT / "data" / "truth" / "effects.json").write_text(json.dumps(effects, indent=2))
    # the advertiser's own media plan: what was booked for the weeks it cancelled
    media_plan = {"video_pause_weeks": VIDEO_PAUSE_WEEKS,
                  "cancelled_video_budget_krw": round(pause_spend),
                  "geo_test_weeks": GEO_TEST_WEEKS,
                  "geo_test_withheld_video_budget_krw": round(test_spend_cf)}
    (ROOT / "data" / "media_plan.json").write_text(json.dumps(media_plan, indent=2))
    print(json.dumps(effects, indent=2))


if __name__ == "__main__":
    main()
