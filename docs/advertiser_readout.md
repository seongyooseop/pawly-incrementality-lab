# PAWLY measurement readout

**To:** PAWLY marketing lead  
**From:** Measurement team, with the account team  
**Period:** Nov 2024 - Oct 2026 (104 weeks)  
*Fictional brand, synthetic data. Korean version: [advertiser_readout_ko.md](advertiser_readout_ko.md).*

## Bottom line

- Short-form video pays back in sales: about KRW 1.2 of extra sales per won during the test (range 0.6-1.8), and about 1.5 counting the two weeks after it, when part of the effect lands. The 4-week summer pause cost about KRW 94M in sales (range KRW 30M-KRW 161M), not the KRW 245M a before/after view suggests.
- The jump in reported search revenue after switching to AI auto-bidding (+93%) is almost entirely sales that were already happening, now credited to search. Total sales did not move (-0.2%, range -2.0% to +1.6%).
- The 30% search budget increase that followed returned about KRW 0.15 per won (range -0.35 to 0.64): below break-even.
- Added up, the platforms claim 1.3 times the sales that ads actually added. Short video is the only channel credited with less than it adds. At today's spend, the next won returns less than a won in every channel (model: 0.3-0.8), so shift budget first and then test a smaller total.
- In profit terms (gross margin assumed at 40%), short video pays back if a new customer's lifetime purchases reach 1.6x their first; the next won in any channel needs at least 3.2x. Your repeat-purchase data decides whether to add budget.

## What we measured

| Question | Method | Answer | Confidence |
|---|---|---|---|
| Does short video add sales? | Geo test, 20 matched region pairs, 6 weeks | Yes. iROAS 1.20 (0.58-1.81); 1.52 with a 2-week cooldown; brand searches -5.3% in regions without video | High: A/A-checked design, one contaminated pair found and removed |
| What did the summer pause cost? | Causal impact (Bayesian structural time series) | KRW 94M (KRW 30M-KRW 161M) | Medium: wide range, but consistent with the geo test |
| Is auto-bidding adding sales? | Total sales around the switch + 456 placebo dates | No measurable change (-0.2%); placebo p = 0.92 | High for 'no large effect'; a gain under ~2% cannot be ruled out |
| How to split next year's budget? | Media mix model checked against both experiments | Move money from retargeting and search to short video; keep the total flat | Medium: search is the least certain channel |

## Recommendation for next year

| Channel | Now (KRW M/week) | Proposed | Change |
|---|---:|---:|---:|
| Search (incl. auto-bidding) | 19.4 | 17.1 | -12% |
| Short-form video | 25.0 | 28.7 | +15% |
| Social | 8.3 | 8.4 | +1% |
| Retargeting | 5.6 | 4.0 | -28% |

Expected extra sales over a year: KRW 57M (90% range KRW -16M to KRW 113M). Moves are capped where the model is unsure (risk-aware plan). Revisit search after the next test.

## Does it pay? Sales returns in profit terms

| Channel | Sales per won (average) | Sales per next won | Lifetime multiple needed (average) | Lifetime multiple needed (next won) |
|---|---:|---:|---:|---:|
| Search (incl. auto-bidding) | 0.93 | 0.44 | 2.7x | 5.7x |
| Short-form video | 1.61 | 0.78 | 1.6x | 3.2x |
| Social | 1.22 | 0.63 | 2.0x | 4.0x |
| Retargeting | 0.65 | 0.30 | 3.8x | 8.3x |

Returns are in sales, from the 104-week model. A won of ad spend pays back when return x gross margin x lifetime multiple is at least 1. 'Lifetime multiple' = a new customer's total purchases divided by their first, which only PAWLY's own order data can tell. Margin of 40% is a placeholder.

## Was measuring worth it?

| Item | KRW M | Basis |
|---|---:|---|
| Cost of the geo test (sales lost incl. cooldown, minus video budget withheld) | 26.7 | 77.5M sales lost vs 50.8M not spent, 19 pairs |
| Sales a repeat of the 4-week video pause would cost | 94.0 | Causal impact read of the summer pause; the geo test shows the loss is real |
| Yearly loss if the 30% search increase had been kept | 263.9 | 23.7M extra spend returned 3.4M sales per 4 weeks, x13 |
| Expected yearly gain from the reallocation | 57.1 | Model, 90%: -16 to 113M |

The geo test cost about KRW 27M in sales. Each decision it and the follow-up reads support is worth several times that a year. In sales terms; profit depends on margin and repeat buying.

## What we are not sure about

- Search's return is the widest range in the model (90%: 0.4-1.7). A plan built on the model's average alone would cut search 27%; this plan trims it 12% and leaves any bigger cut to the search test.
- The pause estimate rests on a model, not a holdout; treat it as supporting the geo test, not replacing it.
- Profit depends on repeat buying we have not measured yet; until then, read every return as sales, not profit.

## Next test

**Search holdout: switch search off in 30% of regions (chosen within size bands) for 6 weeks, plus a 2-week cooldown.** Search is where uncertainty costs the most; a direct test settles the next budget decision. A 30% holdout detects a return of 0.75 or more, almost as sensitive as switching off half the regions (0.7), with about 59% of the sales at risk.

## Learning agenda for 2027

| Quarter | Question | Study | Decides | Why now |
|---|---|---|---|---|
| Q1 2027 | What does search really add? | Search holdout in 30% of regions, 6 weeks + 2-week cooldown | Search budget | Widest model range of any channel (90%: 0.4-1.7); reported ROAS 3.4 |
| Q2 2027 | Is the total budget too high? | Step-down test: matched regions run all channels 20% lower for 6 weeks | Total budget | Marginal ROI below 1 in every channel (model 0.3-0.8) |
| Q3 2027 | How much of retargeting is re-credited? | Audience holdout: 15% of retargeting audiences not served for 4 weeks | Retargeting cut size | Credited 4x what it adds |
| Q4 2027 | What is next year's plan? | Refit the media mix model with every experiment so far as calibration; brand lift survey during a video flight | 2028 budget split and the upper-funnel KPI | Each experiment narrows one channel's range; the survey adds the brand side the sales tests miss |

## What we need from you

- Share the media plan before each test: booked budgets are the denominator of every return figure.
- Share gross margin and repeat-purchase rates by first-purchase month, so returns can be read as profit.
- Tell us about regional promotions during a test (the G26 retail promotion would have inflated the result by about a quarter).
- Keep budgets flat during tests, and send daily total sales from your own order system.

---

## Internal: notes for the account team (not sent to the advertiser)

- Growth opportunity: short video +15% is about KRW 192M more video spend a year, backed by an experiment, not by the platform's own report.
- Position search as 'prove, then reinvest', not as a cut: the holdout either confirms its value or frees budget for video.
- The total-budget step-down builds trust: an advertiser who sees us test spending less believes us when we ask for more.
- Studies to propose next: 30% regional holdout for search, audience holdout for retargeting, brand lift survey for video, recalibrated MMM.
- Reusable for the next client: the study-selection table and the eligibility calculation (power from past weeks, A/A calibration) run on any region-by-day sales table in the same format.

### Findings mapped to Google solutions

| Finding | Google solution | Prove with | Pitch |
|---|---|---|---|
| Short video adds about 1.2 won per won but its platform reports 0.30 | YouTube Shorts through Demand Gen and video campaigns | Geo-based Conversion Lift on the next increase; Brand Lift and Search Lift for the awareness part | Grow video +15% on experiment evidence, not on the platform's click report |
| Search is the least certain channel (model range 0.4-1.7) | Search campaigns and Performance Max with Smart Bidding | GeoX holdout on 30% of regions (Q1) | Prove, then reinvest: the holdout either confirms search or frees budget for video |
| After the switch to auto-bidding, almost all of the reported gain was sales already happening | Performance Max brand exclusions, new-customer acquisition goal, value-based bidding on margin | Total-sales read around each bidding change (as in chapter 3) | Point automated bidding at new buyers and profit, so its reported results move closer to what it adds |
| Retargeting is credited about 4 times what it adds | Remarketing audiences in Demand Gen and Display | User-based Conversion Lift with an audience holdout where available, else a geo holdout (Q3) | Trim retargeting where the holdout shows little lift and move it to prospecting |
| GA4 sees about half of sales: marketplaces and unconsented sessions are missing | Enhanced conversions and consent mode on the site, GA4 linked to Ads | Monthly reconciliation of Ads and GA4 conversions with the order system; marketplace sales, which no click ID reaches, stay with geo tests and the MMM | Better signals improve Smart Bidding and every later study; a setup task, not a budget ask |
| The MMM needs a refresh after any structural change | Meridian (open source), recalibrated with each lift result | Out-of-sample check after each refit, as on the Budget tab | One model the advertiser and Google both read, updated each quarter |
