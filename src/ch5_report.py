"""Chapter 5: the readout an account team hands to the advertiser.

Plain language, numbers with ranges, one recommendation, a learning agenda,
what it means in profit, and what the advertiser needs to provide; a Korean
version for the advertiser; and internal notes for the account team.
The budget plan uses the model fitted on all 104 weeks (the tests added the
spend variation the earlier model lacked) and the risk-aware objective, which
moves money only where the model is sure.

Profit figures rest on two numbers only the advertiser has: gross margin and how
much a new customer buys over their lifetime. GROSS_MARGIN is a placeholder to
replace; the report states the repeat-buying a channel needs to pay back.

Writes outputs/ch5_report.json, docs/advertiser_readout.md (English) and
docs/advertiser_readout_ko.md (Korean)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = {"search": "Search (incl. auto-bidding)", "short_video": "Short-form video",
         "social": "Social", "retargeting": "Retargeting"}
NAMES_KO = {"search": "검색 광고(자동 입찰 포함)", "short_video": "숏폼 영상", "social": "소셜", "retargeting": "리타깃팅"}
GROSS_MARGIN = 0.40  # placeholder: replace with the advertiser's gross margin


def load(name):
    return json.loads((ROOT / "outputs" / name).read_text())


def m(x):
    return f"KRW {x:,.0f}M"


def eok(x_m):
    """Million KRW -> Korean 억/만 원 wording."""
    return f"{x_m / 100:,.1f}억 원" if abs(x_m) >= 100 else f"{x_m * 100:,.0f}만 원"


def main():
    r1, c2, c3, c4 = load("ch1_readout.json"), load("ch2_causal_impact.json"), load("ch3_auto_bidding.json"), load("ch4_mmm.json")
    d1 = load("ch1_design.json")
    geo = r1["after_check"]["revenue"]
    cool = r1["with_cooldown"]["revenue"]
    mr_all = c4["marginal_roi"]["models"]["all_weeks"]
    roi_all = c4["models"]["all_weeks"]["roi"]
    xp_rows = {r["channel"]: r for r in load("cross_platform.json")["channels"]}
    ci, au, bu = c2["causal_impact"], c3["total_sales_rdit"], c3["budget_increase"]
    final = c4["models"]["all_weeks"]["plans"]["risk_aware"]
    xp = load("cross_platform.json")["totals"]
    ga = load("cross_platform.json")["ga4"]
    gch = {r["channel"]: r for r in ga["channels"]}
    mr = {c: v["median"] for c, v in mr_all.items()}
    spend = c4["plan_weekly_spend_krw_m"]
    opt50 = d1["design_options"][0]
    opt30 = next(o for o in d1["design_options"] if o["design"].startswith("Go-dark, 30%") and o["weeks"] == 6)
    risk_share = round(100 * opt30["spend_moved_krw_m"] / opt50["spend_moved_krw_m"])

    budget = []
    for c in c4["channels"]:
        mult = final["multipliers"][c]
        budget.append({"channel": NAMES[c], "channel_ko": NAMES_KO[c], "now_krw_m_per_week": spend[c],
                       "proposed_krw_m_per_week": round(spend[c] * mult, 1),
                       "change_pct": round(100 * (mult - 1))})
    video_extra_year = (budget[1]["proposed_krw_m_per_week"] - budget[1]["now_krw_m_per_week"]) * 52

    # profit: a won of ad spend pays back when return x margin x lifetime multiple >= 1
    profit = []
    for c in c4["channels"]:
        avg, nxt = roi_all[c]["median"], mr[c]
        profit.append({"channel": NAMES[c], "channel_ko": NAMES_KO[c],
                       "average_return": avg, "next_won_return": nxt,
                       "lifetime_multiple_needed_average": round(1 / (GROSS_MARGIN * avg), 1),
                       "lifetime_multiple_needed_next_won": round(1 / (GROSS_MARGIN * nxt), 1)})
    p_video = next(p for p in profit if p["channel"] == NAMES["short_video"])

    # was measuring worth it? cost of the geo test vs the decisions it supports
    test_cost = -cool["effect_krw_m"] - cool["video_withheld_krw_m"]          # sales lost net of spend saved
    up_waste_4w = bu["extra_search_spend_4w_krw_m"] - bu["incremental_revenue_4w_krw_m"]
    worth = {
        "rows": [
            {"item": "Cost of the geo test (sales lost incl. cooldown, minus video budget withheld)", "krw_m": round(test_cost, 1),
             "basis": f"{-cool['effect_krw_m']:.1f}M sales lost vs {cool['video_withheld_krw_m']:.1f}M not spent, 19 pairs"},
            {"item": "Sales a repeat of the 4-week video pause would cost", "krw_m": round(-ci["effect_krw_m"], 1),
             "basis": "Causal impact read of the summer pause; the geo test shows the loss is real"},
            {"item": "Yearly loss if the 30% search increase had been kept", "krw_m": round(up_waste_4w * 13, 1),
             "basis": f"{bu['extra_search_spend_4w_krw_m']:.1f}M extra spend returned {bu['incremental_revenue_4w_krw_m']:.1f}M sales per 4 weeks, x13"},
            {"item": "Expected yearly gain from the reallocation", "krw_m": round(final["predicted_gain_krw_m"]["median"], 1),
             "basis": f"Model, 90%: {final['predicted_gain_krw_m']['ci90'][0]:.0f} to {final['predicted_gain_krw_m']['ci90'][1]:.0f}M"},
        ],
        "note": (f"The geo test cost about {m(test_cost)} in sales. Each decision it and the follow-up reads support is worth "
                 f"several times that a year. In sales terms; profit depends on margin and repeat buying."),
    }
    p_min_next = min(p["lifetime_multiple_needed_next_won"] for p in profit)

    report = {
        "to": "PAWLY marketing lead",
        "from": "Measurement team, with the account team",
        "period": "Nov 2024 - Oct 2026 (104 weeks)",
        "bottom_line": [
            f"Short-form video pays back in sales: about KRW {geo['iroas']:.1f} of extra sales per won during the test "
            f"(range {geo['iroas_ci'][0]:.1f}-{geo['iroas_ci'][1]:.1f}), and about {cool['iroas']:.1f} counting the two weeks after it, "
            f"when part of the effect lands. The 4-week summer pause cost about "
            f"{m(-ci['effect_krw_m'])} in sales (range {m(-ci['ci_krw_m'][1])}-{m(-ci['ci_krw_m'][0])}), "
            f"not the {m(-c2['naive_before_after']['effect_krw_m'])} a before/after view suggests.",
            f"The jump in reported search revenue after switching to AI auto-bidding "
            f"(+{c3['platform_view']['reported_increase_pct']:.0f}%) is almost entirely sales that were already "
            f"happening, now credited to search. Total sales did not move ({au['jump_pct']:+.1f}%, range "
            f"{au['ci_pct'][0]:+.1f}% to {au['ci_pct'][1]:+.1f}%).",
            f"The 30% search budget increase that followed returned about KRW {bu['marginal_iroas']:.2f} per won "
            f"(range {bu['marginal_iroas_ci'][0]:.2f} to {bu['marginal_iroas_ci'][1]:.2f}): below break-even.",
            f"Added up, the platforms claim {xp['claimed_vs_added']:.1f} times the sales that ads actually added. Short video is the "
            f"only channel credited with less than it adds. Your own GA4, which counts each website sale once, points the same way: "
            f"it gives search {gch['search']['ga4_share_pct']:.0f}% of the paid credit against a {gch['search']['incremental_share_pct']:.0f}% share of "
            f"what ads added, and short video {gch['short_video']['ga4_share_pct']:.0f}% against {gch['short_video']['incremental_share_pct']:.0f}%. At today's spend, the next won returns less than a won in every channel "
            f"(model: {min(mr.values()):.1f}-{max(mr.values()):.1f}), so shift budget first and then test a smaller total.",
            f"In profit terms (gross margin assumed at {GROSS_MARGIN:.0%}), short video pays back if a new customer's lifetime "
            f"purchases reach {p_video['lifetime_multiple_needed_average']}x their first; the next won in any channel needs at least "
            f"{p_min_next}x. Your repeat-purchase data decides whether to add budget.",
        ],
        "korean_summary": [
            f"숏폼 영상 광고는 효과가 있습니다. 광고비 1원당 매출이 약 {geo['iroas']:.1f}원(실험 직후 2주까지 보면 약 {cool['iroas']:.1f}원) "
            f"늘었습니다. 광고 플랫폼 화면에는 0.3원으로 나와 크게 과소평가되어 있습니다.",
            f"검색 광고를 자동 입찰로 바꾼 뒤 화면상 매출은 {c3['platform_view']['reported_increase_pct']:.0f}% 늘었지만, "
            f"실제 전체 매출은 그대로였습니다. 원래 사던 손님이 광고 덕분으로 다시 집계된 것입니다. 그 숫자를 보고 늘린 예산은 회수되지 않았습니다.",
            f"내년에는 리타깃팅을 줄이고 숏폼 영상을 늘리되, 총예산은 그대로 둡니다. 검색은 먼저 일부 지역에서 꺼 보는 실험으로 "
            f"확인한 뒤 결정합니다. 광고 1원을 더 쓸 때 돌아오는 매출이 모든 채널에서 1원보다 적어, 재구매 데이터로 이익을 확인하는 것이 다음 순서입니다.",
        ],
        "measured": [
            {"question": "Does short video add sales?", "method": "Geo test, 20 matched region pairs, 6 weeks",
             "answer": f"Yes. iROAS {geo['iroas']:.2f} ({geo['iroas_ci'][0]:.2f}-{geo['iroas_ci'][1]:.2f}); {cool['iroas']:.2f} with a 2-week cooldown; "
                       f"brand searches {r1['after_check']['brand_search']['effect_pct']:.1f}% in regions without video",
             "confidence": "High: A/A-checked design, one contaminated pair found and removed"},
            {"question": "What did the summer pause cost?", "method": "Causal impact (Bayesian structural time series)",
             "answer": f"{m(-ci['effect_krw_m'])} ({m(-ci['ci_krw_m'][1])}-{m(-ci['ci_krw_m'][0])})",
             "confidence": "Medium: wide range, but consistent with the geo test"},
            {"question": "Is auto-bidding adding sales?", "method": "Total sales around the switch + 456 placebo dates",
             "answer": f"No measurable change ({au['jump_pct']:+.1f}%); placebo p = {au['placebo_p']:.2f}",
             "confidence": "High for 'no large effect'; a gain under ~2% cannot be ruled out"},
            {"question": "How to split next year's budget?", "method": "Media mix model checked against both experiments",
             "answer": "Move money from retargeting and search to short video; keep the total flat",
             "confidence": "Medium: search is the least certain channel"},
        ],
        "recommendation": {
            "budget": budget,
            "expected_gain_krw_m": final["predicted_gain_krw_m"],
            "note": ("Moves are capped where the model is unsure (risk-aware plan). Revisit search after the next test."),
        },
        "profit": {
            "gross_margin_assumed": GROSS_MARGIN,
            "rows": profit,
            "note": (f"Returns are in sales, from the 104-week model. A won of ad spend pays back when return x gross margin x lifetime multiple is at least 1. "
                     f"'Lifetime multiple' = a new customer's total purchases divided by their first, which only PAWLY's own order data can tell. "
                     f"Margin of {GROSS_MARGIN:.0%} is a placeholder."),
        },
        "worth_it": worth,
        "not_sure": [
            f"Search's return is the widest range in the model (90%: {roi_all['search']['ci90'][0]:.1f}-"
            f"{roi_all['search']['ci90'][1]:.1f}). A plan built on the model's average alone would cut search "
            f"{100 * (1 - c4['models']['all_weeks']['plans']['mean']['multipliers']['search']):.0f}%; this plan trims it "
            f"{100 * (1 - final['multipliers']['search']):.0f}% and leaves any bigger cut to the search test.",
            "The pause estimate rests on a model, not a holdout; treat it as supporting the geo test, not replacing it.",
            "Profit depends on repeat buying we have not measured yet; until then, read every return as sales, not profit.",
        ],
        "next_test": {
            "what": "Search holdout: switch search off in 30% of regions (chosen within size bands) for 6 weeks, plus a 2-week cooldown",
            "why": "Search is where uncertainty costs the most; a direct test settles the next budget decision",
            "eligibility": (f"A 30% holdout detects a return of {opt30['min_detectable_return']} or more, almost as sensitive as switching off half the regions "
                            f"({opt50['min_detectable_return']}), with about {risk_share}% of the sales at risk"),
        },
        "learning_agenda": [
            {"quarter": "Q1 2027", "question": "What does search really add?",
             "study": "Search holdout in 30% of regions, 6 weeks + 2-week cooldown",
             "decides": "Search budget",
             "why_now": f"Widest model range of any channel (90%: {roi_all['search']['ci90'][0]:.1f}-"
                        f"{roi_all['search']['ci90'][1]:.1f}); reported ROAS {xp_rows['search']['reported_roas']:.1f}"},
            {"quarter": "Q2 2027", "question": "Is the total budget too high?",
             "study": "Step-down test: matched regions run all channels 20% lower for 6 weeks",
             "decides": "Total budget",
             "why_now": f"Marginal ROI below 1 in every channel (model {min(mr.values()):.1f}-{max(mr.values()):.1f})"},
            {"quarter": "Q3 2027", "question": "How much of retargeting is re-credited?",
             "study": "Audience holdout: 15% of retargeting audiences not served for 4 weeks",
             "decides": "Retargeting cut size",
             "why_now": f"Credited {xp_rows['retargeting']['credit_ratio']:.0f}x what it adds"},
            {"quarter": "Q4 2027", "question": "What is next year's plan?",
             "study": "Refit the media mix model with every experiment so far as calibration; brand lift survey during a video flight",
             "decides": "2028 budget split and the upper-funnel KPI",
             "why_now": "Each experiment narrows one channel's range; the survey adds the brand side the sales tests miss"},
        ],
        "asks": [
            "Share the media plan before each test: booked budgets are the denominator of every return figure.",
            "Share gross margin and repeat-purchase rates by first-purchase month, so returns can be read as profit.",
            "Tell us about regional promotions during a test (the G26 retail promotion would have inflated the result by about a quarter).",
            "Keep budgets flat during tests, and send daily total sales from your own order system.",
            f"Link GA4 to Google Ads and turn on enhanced conversions and consent mode: GA4 sees about {ga['ga4_sees_pct_of_revenue']:.0f}% of "
            "your sales today, and better signals help both automated bidding and the next study.",
        ],
        "account_team_notes": [
            f"Growth opportunity: short video +{budget[1]['change_pct']}% is about {m(video_extra_year)} more video spend a year, "
            f"backed by an experiment, not by the platform's own report.",
            "Position search as 'prove, then reinvest', not as a cut: the holdout either confirms its value or frees budget for video.",
            "The total-budget step-down builds trust: an advertiser who sees us test spending less believes us when we ask for more.",
            "Studies to propose next: 30% regional holdout for search, audience holdout for retargeting, brand lift survey for video, recalibrated MMM.",
            "Reusable for the next client: the study-selection table and the eligibility calculation (power from past weeks, A/A calibration) "
            "run on any region-by-day sales table in the same format.",
        ],
        # the study is written in method names; for the account team, each finding mapped to the Google solution
        # it argues for and the measurement product that proves it
        "google_solutions": [
            {"finding": f"Short video adds about {r1['after_check']['revenue']['iroas']:.1f} won per won but its platform reports 0.30",
             "solution": "YouTube Shorts through Demand Gen and video campaigns",
             "prove_with": "Geo-based Conversion Lift on the next increase; Brand Lift and Search Lift for the awareness part",
             "pitch": f"Grow video {budget[1]['change_pct']:+d}% on experiment evidence, not on the platform's click report"},
            {"finding": f"Search is the least certain channel (model range {roi_all['search']['ci90'][0]:.1f}-{roi_all['search']['ci90'][1]:.1f})",
             "solution": "Search campaigns and Performance Max with Smart Bidding",
             "prove_with": "GeoX holdout on 30% of regions (Q1)",
             "pitch": "Prove, then reinvest: the holdout either confirms search or frees budget for video"},
            {"finding": "After the switch to auto-bidding, almost all of the reported gain was sales already happening",
             "solution": "Performance Max brand exclusions, new-customer acquisition goal, value-based bidding on margin",
             "prove_with": "Total-sales read around each bidding change (as in chapter 3)",
             "pitch": "Point automated bidding at new buyers and profit, so its reported results move closer to what it adds"},
            {"finding": "Retargeting is credited about 4 times what it adds",
             "solution": "Remarketing audiences in Demand Gen and Display",
             "prove_with": "User-based Conversion Lift with an audience holdout where available, else a geo holdout (Q3)",
             "pitch": "Trim retargeting where the holdout shows little lift and move it to prospecting"},
            {"finding": "GA4 sees about half of sales: marketplaces and unconsented sessions are missing",
             "solution": "Enhanced conversions and consent mode on the site, GA4 linked to Ads",
             "prove_with": "Monthly reconciliation of Ads and GA4 conversions with the order system; marketplace sales, which no click ID reaches, stay with geo tests and the MMM",
             "pitch": "Better signals improve Smart Bidding and every later study; a setup task, not a budget ask"},
            {"finding": "The MMM needs a refresh after any structural change",
             "solution": "Meridian (open source), recalibrated with each lift result",
             "prove_with": "Out-of-sample check after each refit, as on the Budget tab",
             "pitch": "One model the advertiser and Google both read, updated each quarter"},
        ],
    }
    (ROOT / "outputs" / "ch5_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))

    # ----------------------------------------------------------- English
    md = [f"# PAWLY measurement readout", "",
          f"**To:** {report['to']}  ", f"**From:** {report['from']}  ", f"**Period:** {report['period']}  ",
          "*Fictional brand, synthetic data. Korean version: [advertiser_readout_ko.md](advertiser_readout_ko.md).*", "",
          "## Bottom line", ""]
    md += [f"- {b}" for b in report["bottom_line"]]
    md += ["", "## What we measured", "", "| Question | Method | Answer | Confidence |", "|---|---|---|---|"]
    md += [f"| {r['question']} | {r['method']} | {r['answer']} | {r['confidence']} |" for r in report["measured"]]
    md += ["", "## Recommendation for next year", "", "| Channel | Now (KRW M/week) | Proposed | Change |", "|---|---:|---:|---:|"]
    md += [f"| {b['channel']} | {b['now_krw_m_per_week']} | {b['proposed_krw_m_per_week']} | {b['change_pct']:+d}% |"
           for b in report["recommendation"]["budget"]]
    g = report["recommendation"]["expected_gain_krw_m"]
    md += ["", f"Expected extra sales over a year: {m(g['median'])} (90% range {m(g['ci90'][0])} to {m(g['ci90'][1])}). "
           + report["recommendation"]["note"],
           "", "## Does it pay? Sales returns in profit terms", "",
           "| Channel | Sales per won (average) | Sales per next won | Lifetime multiple needed (average) | Lifetime multiple needed (next won) |",
           "|---|---:|---:|---:|---:|"]
    md += [f"| {p['channel']} | {p['average_return']:.2f} | {p['next_won_return']:.2f} | {p['lifetime_multiple_needed_average']}x | "
           f"{p['lifetime_multiple_needed_next_won']}x |" for p in profit]
    md += ["", report["profit"]["note"], "", "## Was measuring worth it?", "", "| Item | KRW M | Basis |", "|---|---:|---|"]
    md += [f"| {w['item']} | {w['krw_m']:,.1f} | {w['basis']} |" for w in worth["rows"]]
    md += ["", worth["note"], "", "## What we are not sure about", ""]
    md += [f"- {x}" for x in report["not_sure"]]
    nt = report["next_test"]
    md += ["", "## Next test", "", f"**{nt['what']}.** {nt['why']}. {nt['eligibility']}.",
           "", "## Learning agenda for 2027", "", "| Quarter | Question | Study | Decides | Why now |", "|---|---|---|---|---|"]
    md += [f"| {a['quarter']} | {a['question']} | {a['study']} | {a['decides']} | {a['why_now']} |" for a in report["learning_agenda"]]
    md += ["", "## What we need from you", ""]
    md += [f"- {x}" for x in report["asks"]]
    md += ["", "---", "", "## Internal: notes for the account team (not sent to the advertiser)", ""]
    md += [f"- {x}" for x in report["account_team_notes"]]
    md += ["", "### Findings mapped to Google solutions", "", "| Finding | Google solution | Prove with | Pitch |", "|---|---|---|---|"]
    md += [f"| {g['finding']} | {g['solution']} | {g['prove_with']} | {g['pitch']} |" for g in report["google_solutions"]]
    (ROOT / "docs" / "advertiser_readout.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # ----------------------------------------------------------- Korean
    ko = ["# PAWLY 광고 효과 측정 결과", "", "*가상 브랜드, 가상 데이터입니다. 영문판: [advertiser_readout.md](advertiser_readout.md)*", "",
          "## 세 줄 요약", ""]
    ko += [f"{i}. {s}" for i, s in enumerate(report["korean_summary"], 1)]
    ko += ["", "## 무엇을 측정했나", "", "| 질문 | 방법 | 결과 |", "|---|---|---|",
           f"| 숏폼 영상이 매출을 늘리나? | 비슷한 지역 20쌍 중 한 곳씩 6주간 영상 중단 | 광고비 1원당 매출 {geo['iroas']:.2f}원 "
           f"(범위 {geo['iroas_ci'][0]:.2f}~{geo['iroas_ci'][1]:.2f}), 실험 뒤 2주 포함 시 {cool['iroas']:.2f}원 |",
           f"| 여름 4주 영상 중단으로 잃은 매출은? | 광고와 무관한 카테고리 검색량으로 '중단 안 했으면' 매출 추정 | 약 {eok(-ci['effect_krw_m'])} "
           f"(단순 전후 비교의 {eok(-c2['naive_before_after']['effect_krw_m'])}은 여름 비수기까지 포함한 과대 추정) |",
           f"| 자동 입찰이 매출을 늘렸나? | 전환 시점 전후 전체 매출 비교 + 과거 456일과 비교 | 변화 없음({au['jump_pct']:+.1f}%) |",
           f"| 플랫폼 화면 숫자는 믿을 만한가? | 플랫폼별 보고 매출 합계 vs 실제 광고 기여 | 보고가 실제의 {xp['claimed_vs_added']:.1f}배 |",
           f"| 우리 GA4 숫자는? | GA4가 채널에 나눠 준 몫 vs 실제 광고 기여 몫 | GA4는 매출의 {ga['ga4_sees_pct_of_revenue']:.0f}%만 봅니다. "
           f"검색에 {gch['search']['ga4_share_pct']:.0f}%를 주지만 실제 몫은 {gch['search']['incremental_share_pct']:.0f}%, "
           f"숏폼 영상은 {gch['short_video']['ga4_share_pct']:.0f}% vs {gch['short_video']['incremental_share_pct']:.0f}% |",
           "", "## 내년 예산 제안 (총액은 동일)", "", "| 채널 | 현재 (주당) | 제안 | 변화 |", "|---|---:|---:|---:|"]
    ko += [f"| {b['channel_ko']} | {eok(b['now_krw_m_per_week'])} | {eok(b['proposed_krw_m_per_week'])} | {b['change_pct']:+d}% |" for b in budget]
    ko += ["", f"예상 추가 매출: 연 약 {eok(g['median'])} (90% 범위 {eok(g['ci90'][0])} ~ {eok(g['ci90'][1])}). "
           "모델이 확신하는 곳에서만 예산을 옮긴 안입니다.",
           "", "## 이익으로 따지면", "",
           f"위 숫자는 모두 매출 기준입니다. 매출총이익률을 {GROSS_MARGIN:.0%}로 가정하면, 숏폼 영상은 새 고객이 평생 첫 구매의 "
           f"{p_video['lifetime_multiple_needed_average']}배 이상 사면 광고비를 회수합니다. 지금보다 1원을 더 쓰는 경우에는 어느 채널이든 "
           f"{p_min_next}배 이상이 필요합니다. 실제 이익률과 재구매 데이터를 주시면 이익 기준으로 다시 계산하겠습니다.",
           "", "## 측정은 할 만했나", "",
           f"지역 실험의 비용은 매출 기준 약 {eok(test_cost)}입니다(실험 뒤 2주 포함 잃은 매출 {eok(-cool['effect_krw_m'])} − 쓰지 않은 영상 광고비 "
           f"{eok(cool['video_withheld_krw_m'])}). 반면 이 측정으로 막거나 얻는 것은 해마다 그 몇 배입니다: 영상 4주 중단을 반복하면 잃을 매출 약 "
           f"{eok(-ci['effect_krw_m'])}, 검색 30% 증액을 유지했다면 1년 손실 약 {eok(up_waste_4w * 13)}, 재배분 기대 이득 연 약 {eok(final['predicted_gain_krw_m']['median'])}.",
           "", "## 2027년 측정 계획", "", "| 분기 | 확인할 질문 | 방법 |", "|---|---|---|",
           "| 1분기 | 검색 광고는 실제로 얼마나 기여하나? | 30% 지역에서 6주간 검색 광고 중단(+2주 관찰) |",
           "| 2분기 | 총예산이 너무 많은가? | 일부 지역에서 모든 광고를 20% 줄여 6주 비교 |",
           "| 3분기 | 리타깃팅 매출 중 원래 살 손님은 얼마나? | 리타깃팅 대상의 15%에게 4주간 광고 미노출 |",
           "| 4분기 | 2028년 예산은? | 모든 실험 결과로 예산 모델 재보정 + 브랜드 인지도 설문 |",
           "", "## 부탁드릴 것", "",
           "- 실험 전에 미디어 플랜(예약 예산)을 공유해 주세요. 모든 효율 계산의 기준입니다.",
           "- 매출총이익률과 첫 구매 월별 재구매율을 공유해 주세요. 매출이 아니라 이익으로 판단할 수 있습니다.",
           "- 실험 기간에 지역 프로모션이 있으면 알려 주세요. 이번 G26 지역 프로모션은 결과를 약 4분의 1 부풀릴 뻔했습니다.",
           "- 실험 중에는 예산을 고정하고, 자사 주문 시스템의 일별 전체 매출을 보내 주세요.",
           f"- GA4를 Google Ads와 연결하고 향상된 전환과 동의 모드를 켜 주세요. 지금 GA4는 매출의 약 {ga['ga4_sees_pct_of_revenue']:.0f}%만 봅니다. "
           "신호가 좋아지면 자동 입찰과 다음 측정이 모두 정확해집니다."]
    (ROOT / "docs" / "advertiser_readout_ko.md").write_text("\n".join(ko) + "\n", encoding="utf-8")
    print("\n".join(md[:20]))
    print("\n".join(ko[:12]))


if __name__ == "__main__":
    main()
