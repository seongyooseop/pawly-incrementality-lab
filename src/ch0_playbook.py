"""Chapter 0: which measurement answers which advertiser question.

A decision table an account team can use before promising a study. The geo
test row takes its eligibility numbers from chapter 1's power analysis; the
other rows state the conditions each method needs to be trusted.
Writes outputs/ch0_playbook.json
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    ch1 = json.loads((ROOT / "outputs" / "ch1_design.json").read_text())
    six = next(e for e in ch1["eligibility"] if e["weeks"] == 6)
    opt50 = ch1["design_options"][0]
    opt30 = next(o for o in ch1["design_options"] if o["design"].startswith("Go-dark, 30%") and o["weeks"] == 6)

    rows = [
        {
            "question": "Is this channel adding sales at all?",
            "method": "Geo experiment (go-dark or heavy-up in matched regions)",
            "chapter": 1,
            "use_when": "The channel can be switched off or raised by region; user-level holdouts are not possible or not trusted",
            "eligibility": (f"PAWLY: 20 matched region pairs, 6 weeks, national budget of at least "
                            f"KRW {six['min_national_video_budget_for_iroas1_m_per_day']}M/day so that an "
                            f"iROAS of 1.0 is detectable (MDE {six['mde_revenue_pct']}% of revenue). "
                            f"A 30% go-dark share detects {opt30['min_detectable_return']} at "
                            f"{round(100 * opt30['spend_moved_krw_m'] / opt50['spend_moved_krw_m'])}% of the revenue at risk"),
            "output": "Incremental revenue and iROAS with a 95% interval; brand-search lift as a second KPI",
            "watch_out": "Spillover between regions, local promotions in control regions, budget changes during the test",
        },
        {
            "question": "Our budget is below the geo-test threshold. What can we still learn?",
            "method": "Platform conversion lift (user-level holdout), or a planned on/off period read with causal impact",
            "chapter": 0,
            "use_when": (f"National budget for the channel under about KRW "
                         f"{six['min_national_video_budget_for_iroas1_m_per_day']}M/day, or fewer than ~20 comparable regions"),
            "eligibility": "Conversion lift: enough conversions per arm to meet the platform's minimum. On/off read: a stable pre-period and one clean change date",
            "output": "A lift estimate with a wide interval; results pool into a calibrated MMM as the business grows",
            "watch_out": "An underpowered test that reads 'no effect' when the honest answer is 'can't tell yet'",
        },
        {
            "question": "We already paused or changed something. What did it do?",
            "method": "Causal impact (Bayesian structural time series)",
            "chapter": 2,
            "use_when": "A single, dated change happened and no holdout was planned",
            "eligibility": "A stable pre-period several times longer than the post-period; control series that the change did not touch",
            "output": "Day-by-day counterfactual and cumulative effect with a credible interval",
            "watch_out": "Seasonality or promotions that coincide with the change; a simple before/after comparison absorbs them",
        },
        {
            "question": "Reported conversions jumped after switching to AI auto-bidding. Is it real?",
            "method": "Total-sales check around the switch (regression discontinuity in time + placebo dates)",
            "chapter": 3,
            "use_when": "Platform-reported results rose but total sales did not obviously move",
            "eligibility": "A clear switch date, daily total sales from the advertiser's own system, no other big change within about four weeks",
            "output": "Split of the reported increase into true incremental sales and sales re-credited from brand search and organic",
            "watch_out": "Attribution window changes; budget increases that follow the high reported ROAS",
        },
        {
            "question": "Every platform says it drove the sale. Whose numbers do we believe?",
            "method": "Cross-platform comparison: each platform's reported revenue vs incremental revenue",
            "chapter": 4,
            "use_when": "Several platforms each report a strong ROAS and their claims add up to more than ads could have driven",
            "eligibility": "Per-channel platform reports plus one incrementality source: an experiment or a calibrated MMM",
            "output": "Credit ratio per channel (reported / incremental); headroom where platforms under-credit",
            "watch_out": "Ranking channels by their own reported ROAS; attribution windows that differ by platform",
        },
        {
            "question": "How should next year's budget be split?",
            "method": "Bayesian media mix model calibrated with experiment results; response curves",
            "chapter": 4,
            "use_when": "Several channels compete for one budget and spend varies over time",
            "eligibility": "About two years of weekly data, real spend variation per channel, at least one experiment to calibrate against",
            "output": "Channel response curves, marginal ROI and a reallocation with expected gain ranges",
            "watch_out": "Channels whose spend moves together; without calibration the model can hand one channel's effect to another",
        },
        {
            "question": "Did the campaign raise interest in the brand?",
            "method": "Search lift (brand search volume as a KPI in the geo test) or a brand lift survey",
            "chapter": 1,
            "use_when": "Upper-funnel goals; purchase effects may take longer than the test",
            "eligibility": (f"PAWLY: the same 6-week geo design detects a {six['mde_brand_search_pct']}% change "
                            f"in brand searches"),
            "output": "Lift in brand searches (or ad recall) with an interval",
            "watch_out": "Brand search ads can steal clicks from organic results; measure searches, not ad clicks",
        },
    ]
    # before any study: is the data good enough to measure at all?
    readiness = [
        {"check": "Platform conversions reconcile with the advertiser's own orders",
         "why": "A study is only as good as its outcome data; most small-advertiser disputes start with two numbers that disagree",
         "how": "Compare the same days on the same basis: attribution window, time zone, cancellations and returns, click vs view",
         "pawly": "Own order system is the outcome for every study; platform reports are compared against it, never used as the outcome"},
        {"check": "Sales outside the website are counted",
         "why": "Ads drive marketplace and offline sales too; site-only data understates every return",
         "how": "Daily totals from the order system across own site and marketplaces",
         "pawly": "Revenue includes the own site and two marketplaces"},
        {"check": "Daily sales by region exist for at least a year",
         "why": "Geo tests and their power estimate need region-level history",
         "how": "Region-by-day revenue; replay past weeks as fake tests before promising one",
         "pawly": "40 regions x 78 weeks before the first test"},
        {"check": "Conversion signals are complete enough",
         "why": "Consent choices and app tracking limits hide part of the conversions, so click-based reports drift from reality",
         "how": "Check how many conversions are observed vs modeled; lean on experiments and total-sales models where signals are thin",
         "pawly": "Every chapter measures total sales, which consent loss does not touch"},
        {"check": "The media plan and promotion calendar are shared",
         "why": "Booked budgets are the denominator of every return; promotions inside a test region can fake an effect",
         "how": "Booked budget per week, planned promotions by region, a promise to hold budgets flat during a test",
         "pawly": "The cancelled budget came from the media plan; an unannounced retail promotion in G26 nearly inflated the geo read by a quarter"},
    ]
    out = {"title": "Measurement playbook: pick the study from the question", "rows": rows, "readiness": readiness}
    (ROOT / "outputs" / "ch0_playbook.json").write_text(json.dumps(out, indent=2))
    for r in rows:
        print(f"- {r['question']} -> {r['method']}\n  {r['eligibility']}")


if __name__ == "__main__":
    main()
