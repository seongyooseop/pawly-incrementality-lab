# AI workflow log

Built with Claude Code. Each entry is a problem a check caught, what caused it, and the fix. The checks matter more than the code: every number on the page has to survive them.

## Day 1 — world and geo test design (2026-10-31)

**1. Video and search spend moved almost in lockstep (weekly correlation 0.98).**
The world is meant to have marketers raise search when video runs, so an observational MMM over-credits search (trap 3). At 0.98 the two channels are indistinguishable even in principle, which is not a fair test of any method. Loosened the coupling to 0.85.

**2. A/A tests showed a fake positive effect (mean z = +0.95, 22% false positives).**
TBR with an intercept, fitted on 12 weeks of daily totals, flattens the slope because the control total carries daily noise (regression dilution). When revenue grows between the pre-period and the test window, the prediction lags behind and the gap looks like a positive effect, whichever group is "treated". Switched to the proportional form (no intercept). Mean A/A z fell to about 0.05.

**3. The interval was still too narrow (about 1.5x).**
The AR(1) correction handles day-to-day correlation but not slow drift between region groups (regions differ in growth and in how much of their revenue comes from ads, so flights move them differently). Multiplied the standard error by a factor learned from A/A tests of the same length: learned on the earlier half of past windows, checked on the later half. Held-out false positives: 0.4-2.5% depending on length (target 5%; slightly conservative).

**Result.** A 6-week go-dark test with 20 matched pairs detects a 2.6% revenue drop in the go-dark regions, which is any iROAS of 0.70 or more, with 80% power. Eight weeks only reaches 2.5%. Brand searches: 2.1% at 6 weeks.

## Day 2 — readouts for the geo test, the pause and the auto-bidding switch (2026-10-31)

**4. Removing the contaminated pair moved the estimate away from the truth.**
The pair diagnostic flagged pair 6 (control region G26 ran 18% above the other controls; robust z = -3.5): the planted retail promotion. With all pairs the iROAS read 1.49 against a true 1.48; without pair 6 it read 1.20. One simulated test is one draw of noise, so this cannot say which procedure is right. Re-ran the same design on 60 fresh noise draws: with the contaminated pair the iROAS is biased by +0.34 on average and the 95% interval covers the truth 87% of the time; without it, bias +0.06 and coverage 98%. The first draw simply had the promotion's upward bias cancel a low noise draw. The diagnostic catches the promotion in 82% of draws but also flags a clean pair in 22%, so the rule is "check with the advertiser, then drop", not "drop automatically".

**5. Grading a trimmed estimate against the all-region truth is unfair.**
Dropping a pair also drops its go-dark region. Each estimate is now graded against the true iROAS of exactly the regions it covers (stored per region in the truth file).

**6. CausalImpact sampler: 24 divergences.**
Raised target acceptance to 0.99 and tuning to 1,500 steps: 0 divergences, R-hat 1.003. The geo-test weeks plus two weeks of carry-over are masked out of the pre-period, since half the regions had no video then.

**7. Wrong denominator for the pause iROAS.**
"What would have been spent" was first estimated from older weeks (KRW 126M); the booked budget that was cancelled was KRW 86M. An advertiser knows this from its media plan, so the plan is now an input (data/media_plan.json). iROAS moved from 0.73 to 1.09 (truth 1.34, inside the interval [0.36, 1.89]).

**8. After the auto-bidding switch, total sales rose 8.5% on a raw before/after view.**
That rise is short video coming back after the pause, not the switch. The regression discontinuity (separate slopes on each side, category searches as control) measures -0.2% [-2.0%, +1.6%]; truth +0.64%. 456 placebo dates give p = 0.92. About 95-100% of the +93% reported increase is sales already happening, now credited to auto-bidding (truth 94%).

**Results.** Geo test iROAS 1.20 [0.58, 1.81] after the check (truth for those regions 1.48). Pause: CausalImpact -93.6M [-162.4M, -30.5M] vs truth -114.7M; naive before/after -244.7M. Budget raised 30% after reported ROAS 6.87: marginal iROAS 0.15 [-0.35, 0.64], truth 0.61.

## Day 3 — media mix model, calibration and budget plans (2026-10-31)

**9. Calibration looked useless at first, because the model was fitted on the wrong weeks.**
Fitted on all 104 weeks, the uncalibrated model already got short video right (ROI 1.61 vs true 1.75): the geo test and the 4-week pause are themselves big swings in video spend, so the data contained natural experiments. The question an advertiser actually faces is different: the model built on the 78 weeks before any test, versus the same model calibrated with the test results. Restructured the chapter around that comparison (before_tests / after_tests), with all_weeks kept as a reference.

**10. Calibration moved little, and the reason is worth showing.**
Before any test, the model's predicted loss for the geo-test weeks was KRW 60.5M; the test measured 64.8M. The model already agreed with the experiment, so calibration narrowed the video interval (90%: 1.53-2.38 to 1.50-2.24) without moving it much. For the pause, the model predicted 129M against a measured 93.0M (truth 114.7M); calibration pulled it to 125M. (Figures as of the refit in entry 15.) A calibration term is only as strong as the experiment's interval.

**11. Trap 3 did not do what it was designed to do.**
Video and search spend move together (weekly correlation 0.85). The plan was that an observational model would hand video's effect to search. It did not: search came out *under*-valued (ROI 1.03 vs true 1.28; the response curve is about 30% too flat) and became the least certain channel (90% interval 0.39-2.03). Kept the result as it is rather than tuning the world until the trap fires.

**12. The expected-gain budget plan captured only a fraction of the possible gain.**
Each model's plan was run through the real world. Maximizing the expected gain cut search to 0.81x, following the under-valued median: true gain KRW 12.6-13.3M, 27-28% of the best possible 47.1M (all_weeks model: 5%). The model's own 90% interval for that gain, -75M to +140M, already said the move was a coin flip. Added a risk-aware plan that maximizes mean - 0.84 sd (about the 20th percentile), so budget moves only where the model is confident: 31% of the best gain for the before-test model, 36% for the calibrated after-test model, 64% for the all-weeks model (figures as of the refit in entry 15). The next experiment should be on search, the channel whose uncertainty costs the most.

## Day 4 — validation table, advertiser readout and page (2026-10-31)

**13. The brand-search lift had no truth to be graded against.**
Chapter 1 reported a brand-search effect, but the truth file only held revenue. Added region-level truth for brand searches; the estimate after the check is -5.3% (95%: -6.7% to -3.9%) against a true -4.0%. With it, all 10 headline intervals on the scorecard contain the truth.

**14. The first readout contradicted itself.**
It recommended trimming search by 12% while warning that cutting search would be a gamble. Rewrote the line to say what the plan actually does: a plan built on the model's average would cut search 27%; the risk-aware plan trims it 12% and leaves any bigger cut to the search test.

## Day 5 — review against the two job postings (2026-11-01)

A review against the Google and TikTok postings found three gaps: no SQL (a minimum qualification), no cross-platform analysis (one of the four named solutions), and response curves without marginal returns.

**15. Moved shared data preparation into SQL, and checked nothing changed.**
National daily and weekly tables, the pair diagnostic (median and MAD in SQL) and the platform-claims table now come from sql/marts.sql in DuckDB. Every mart matched the earlier pandas results exactly, and chapters 1 and 3 reproduced byte for byte. Chapter 2 differed only by sampler noise when re-run (pause loss -93.6M to -93.0M, same interval and verdict); the calibrated MMM was refitted to the new figure so the chapters stay consistent.

**16. The cross-platform verdict for social was wrong at first.**
Calling a channel under- or over-credited by comparing its report with the model's median put social in "under-credited" (model ROI 1.42 vs reported 1.24); the truth (1.10) says slightly over-credited. The report sits inside the model's 90% range, so the verdict now uses the range: under or over only when the report falls outside it, otherwise "unclear". Short video: under-credited (reported 0.30, model 1.50-2.24). Search and retargeting: over-credited 3-4x.

**17. Every channel's marginal ROI is below 1.**
Average ROI says which channels paid back; marginal ROI says where the next won should go. At today's budget the truth is 0.31-0.78 across channels, and all three models' 90% ranges sit below 1 (calibrated model covers the truth for 4 of 4). Reallocation within a fixed total is the first step; the total budget itself is worth testing lower. Added to the readout.

**18. The 6-week geo read missed the part of video's effect that lands after the test.**
Video's awareness effect builds and fades slowly, so when video came back on in weeks 85-86 the go-dark regions were still behind: 12.5% of the true loss falls after the test. Added a second read over the test plus a 2-week cooldown, using the 8-week A/A calibration factor: iROAS 1.52 (95%: 0.77-2.28) against a true 1.69. Over 60 noise draws the 6-week read understates the fuller effect by 0.15 on average; the 8-week read runs 0.13 high and is noisier (RMSE 0.30 vs 0.23), with the same 98% coverage. Both are reported rather than picking the flattering one.

**19. "Next test" was a single item; an advertiser needs a sequence.**
Added a 2027 learning agenda to the readout, one study per quarter, each tied to the number that justifies it: search holdout (widest model range), total-budget step-down (marginal ROI below 1 everywhere), retargeting audience holdout (credited about 4x what it adds), then a recalibrated MMM with a brand lift survey for the upper funnel.

**20. Two limits were true but unstated.**
The causal-impact control series follows true demand with only 5% noise, cleaner than any real covariate. And the geo readout uses TBR with A/A calibration rather than Trimmed Match, which would trim outlier pairs automatically; here the pair diagnostic and an advertiser check do it by hand. Both are now written on the page and in the README.

## Day 5, second review — as a teammate and a hiring manager would read it (2026-11-01)

**21. The 50% go-dark design was not the cheapest that works.**
A teammate's first question: would an account team accept switching video off in half the regions? Compared design options on the same history and A/A calibration. A 30% go-dark share (chosen within size bands) detects a return of 0.75 against 0.70 for half the regions, with about 60% of the sales at risk. In hindsight it was the better recommendation; the next test in the agenda uses it. A heavy-up, which never switches video off, reads the marginal return and can only detect 1.40 or more, above every channel's marginal return here, so it would come back "no effect".

**22. Every return was in sales, none in profit.**
An iROAS of 1.2 is not profit. With gross margin only the advertiser knows (40% used as a placeholder), the readout now states how much repeat buying each channel needs to pay back: short video needs a new customer's lifetime purchases to reach 1.6x their first; the next won in any channel needs 3x or more. Margin and repeat rates are added to what the advertiser is asked to provide.

**23. The readout spoke to analysts, not to a small-business owner.**
Added a three-sentence Korean summary in plain words (no iROAS, no intervals) at the top of the readout, and a full Korean version in docs/advertiser_readout_ko.md. Also added a playbook row for advertisers below the geo-test threshold: platform conversion lift or a planned on/off period read, with the warning that an underpowered test should read "can't tell yet", not "no effect".

**24. The readout had no answer to "what does this mean for the account?"**
Added internal notes for the account team: the growth opportunity (short video +15%, about KRW 192M more a year, backed by an experiment), positioning the search holdout as "prove, then reinvest" rather than a cut, why a budget step-down test builds trust, the studies to propose next, and which parts are reusable for the next client.
