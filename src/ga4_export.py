"""A GA4 export for PAWLY's own site: revenue by default channel group, data-driven attribution.

Part of the simulated world, not of the analysis: it stands in for the GA4
report an advertiser would share. It is built from the same touches the ad
platforms see (their claimed revenue) under the rules in world.GA4: only the
website's consented sessions are visible, and the visible revenue is split
across channels once, so nothing is counted twice. Organic and direct take the
revenue no paid channel touched.

Inputs: data/observed_daily.parquet. Writes data/ga4_channel_week.parquet.
Run after run_timeline.py, before build_marts.py.
"""
from pathlib import Path

import pandas as pd

from world import GA4

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {"search": "Paid Search", "short_video": "Paid Video", "social": "Paid Social",
          "retargeting": "Display (retargeting)"}


def main():
    obs = pd.read_parquet(ROOT / "data" / "observed_daily.parquet")
    wk = obs.groupby("week").sum(numeric_only=True)
    claims = pd.DataFrame({
        "search": wk.reported_rev_brand_search + wk.reported_rev_nonbrand_search + wk.reported_rev_auto_bid,
        "short_video": wk.reported_rev_short_video,
        "social": wk.reported_rev_social,
        "retargeting": wk.reported_rev_retargeting,
    })
    weight = claims * pd.Series(GA4["dda_vs_claim"])
    weight["organic_direct"] = (wk.revenue - claims.sum(axis=1)).clip(lower=0)
    visible = wk.revenue * GA4["site_share"] * GA4["observed_share"]
    credit = weight.div(weight.sum(axis=1), axis=0).mul(visible, axis=0)

    rows = credit.rename(columns={**GROUPS, "organic_direct": "Organic & direct"}).reset_index()
    long = rows.melt(id_vars="week", var_name="channel_group", value_name="ga4_revenue")
    long["channel"] = long.channel_group.map({v: k for k, v in GROUPS.items()}).fillna("organic_direct")
    long.to_parquet(ROOT / "data" / "ga4_channel_week.parquet", index=False)
    print(f"GA4 sees {visible.sum() / wk.revenue.sum():.1%} of revenue; paid share of GA4 revenue "
          f"{credit.drop(columns='organic_direct').sum().sum() / visible.sum():.1%}")


if __name__ == "__main__":
    main()
