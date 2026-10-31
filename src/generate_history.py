"""Simulate PAWLY's first 78 weeks (business as usual) and check the world.

Writes
  data/history_daily.parquet      observed geo-day data the analyst sees
  data/truth/bau_truth.parquet    hidden truth, for validation only
  outputs/world_check.json        true ROI per channel at BAU (counterfactual)
"""
import json
from pathlib import Path

import numpy as np

from world import CHANNELS, HISTORY_WEEKS, World, bau_plan, week_mask

ROOT = Path(__file__).resolve().parents[1]


def main():
    world = World()
    plan = bau_plan(world)
    obs, truth = world.simulate(plan)

    hist = week_mask(world, 1, HISTORY_WEEKS)
    keep = np.repeat(hist, len(world.geo_ids))
    (ROOT / "data" / "truth").mkdir(parents=True, exist_ok=True)
    obs[keep].to_parquet(ROOT / "data" / "history_daily.parquet", index=False)
    truth[keep].to_parquet(ROOT / "data" / "truth" / "bau_truth.parquet", index=False)

    # true ROI over the history window: switch one channel off, same world
    rev = obs.loc[keep, "revenue"].sum()
    check = {"history_weeks": HISTORY_WEEKS,
             "revenue_bn_krw_per_year": round(rev / 1e9 / (HISTORY_WEEKS / 52), 1),
             "channels": {}}
    for c in CHANNELS:
        spend = obs.loc[keep, f"spend_{c}"].sum()
        if spend == 0:
            continue
        off = plan.copy()
        off.spend[c][:] = 0
        obs_off, _ = world.simulate(off)
        lift = rev - obs_off.loc[keep, "revenue"].sum()
        reported = obs.loc[keep, f"reported_rev_{c}"].sum()
        check["channels"][c] = {
            "spend_bn_krw_per_year": round(spend / 1e9 / (HISTORY_WEEKS / 52), 2),
            "true_roi": round(lift / spend, 2),
            "reported_roas": round(reported / spend, 2),
        }
    total_spend = sum(obs.loc[keep, f"spend_{c}"].sum() for c in CHANNELS)
    check["ad_to_sales"] = round(total_spend / rev, 3)
    weekly = obs[keep].groupby("week")[["spend_short_video", "spend_brand_search"]].sum()
    check["corr_video_search_weekly"] = round(weekly.corr().iloc[0, 1], 2)

    (ROOT / "outputs").mkdir(exist_ok=True)
    (ROOT / "outputs" / "world_check.json").write_text(json.dumps(check, indent=2))
    print(json.dumps(check, indent=2))


if __name__ == "__main__":
    main()
