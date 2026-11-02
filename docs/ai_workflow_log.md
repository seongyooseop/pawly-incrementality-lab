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
Before any test, the model's predicted loss for the geo-test weeks was KRW 60.5M; the test measured 64.8M. The model already agreed with the experiment, so calibration narrowed the video interval (90%: 1.53-2.38 to 1.50-2.24) without moving it much. For the pause, the model predicted 129M against a measured 94.0M (truth 114.7M); calibration pulled it to 125M. (Figures as of the refit in entry 29.) A calibration term is only as strong as the experiment's interval.

**11. Trap 3 did not do what it was designed to do.**
Video and search spend move together (weekly correlation 0.85). The plan was that an observational model would hand video's effect to search. It did not: search came out *under*-valued (ROI 1.03 vs true 1.28; the response curve is about 30% too flat) and became the least certain channel (90% interval 0.39-2.03). Kept the result as it is rather than tuning the world until the trap fires.

**12. The expected-gain budget plan captured only a fraction of the possible gain.**
Each model's plan was run through the real world. Maximizing the expected gain cut search to 0.81x, following the under-valued median: true gain KRW 12.6M for the before-test model, 27% of the best possible 47.1M (all_weeks model: 5%). The model's own 90% interval for that gain, -75M to +140M, already said the move was a coin flip. Added a risk-aware plan that maximizes mean - 0.84 sd (about the 20th percentile), so budget moves only where the model is confident: 31% of the best gain for the before-test model (average plan 27%), 64% for the all-weeks model (average plan 5%). For the calibrated after-test model the two came out close (34% vs 36%), so the risk-aware plan is not always ahead; its case is that it moves less money on weaker evidence (figures as of the refit in entry 29). The next experiment should be on search, the channel whose uncertainty costs the most.

## Day 4 — validation table, advertiser readout and page (2026-10-31)

**13. The brand-search lift had no truth to be graded against.**
Chapter 1 reported a brand-search effect, but the truth file only held revenue. Added region-level truth for brand searches; the estimate after the check is -5.3% (95%: -6.7% to -3.9%) against a true -4.0%. With it, all 10 headline intervals on the scorecard contain the truth.

**14. The first readout contradicted itself.**
It recommended trimming search by 12% while warning that cutting search would be a gamble. Rewrote the line to say what the plan actually does: a plan built on the model's average would cut search 27%; the risk-aware plan trims it 12% and leaves any bigger cut to the search test.

## Day 5 — review against the job posting (2026-11-01)

A review against the posting found three gaps: no SQL (a minimum qualification), no cross-platform analysis (one of the measurement solutions the role covers), and response curves without marginal returns.

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

## Day 6 — what a measurement lead would still ask (2026-11-02)

**25. Before any study, is the data good enough to measure?**
Most measurement disputes with a small advertiser start with two numbers that disagree, not with a method. Added a readiness checklist to chapter 0: platform conversions reconcile with the advertiser's own orders, sales outside the website (marketplaces) are counted, daily sales by region exist for at least a year, conversion signals are complete enough after consent choices and app tracking limits, and the media plan and promotion calendar are shared. Each check says why it matters, how to do it, and where PAWLY stands.

**26. The causal-impact read gave an interval but not the number an advertiser asks for.**
"How sure are you the pause cost us sales?" Added CausalImpact's standard read-out, the posterior probability of a loss: 99.7% for the pause, against 64% and 80% for the two placebo windows, whose intervals contain zero. A placebo with a high probability but an interval across zero is the reason both are shown.

**27. Was the measuring itself worth it?**
The geo test cost about KRW 27M in sales net of the video budget withheld. Against that: a repeat of the summer pause would cost about KRW 94M, keeping the 30% search increase would have lost about KRW 264M a year, and the reallocation is expected to add about KRW 57M (90%: -16M to 113M). Added to the readout in sales terms, with the margin caveat.

**28. The MMM had only been checked against the truth, which a real advertiser never has.**
Added checks that work without a truth: convergence for every fit (max R-hat 1.008, no divergences), and an out-of-sample forecast from a model fitted on weeks 1-92 and tested on weeks 93-104. The forecast error is small (1.37% vs 0.66% in sample), but only 50% of the out-of-sample weeks fall inside the 90% range. The model overshoots the week video returns (93), and from the auto-bidding switch in week 97 it under-predicts every week by 1-2%: search was bought differently after the switch and the training weeks never saw it. The in-sample noise estimate is also too small, partly because the category-search control is cleaner than any real one. Shown as found: refit after a structural change, read the model's ranges as a floor on the uncertainty, and use experiments for the big decisions.

**29. Re-running chapters 2 and 4 moved some figures slightly.**
Adding the probability and the out-of-sample model meant re-running the samplers. The pause loss moved from 93.0M to 94.0M (95%: 30-161M); the calibrated model's plans moved to 36% (average) and 34% (risk-aware) of the best possible gain. Downstream chapters, the scorecard (still 11 of 11 inside their intervals) and the readout were rebuilt from the new fits so every page agrees.

## Day 6, third review — the posting's own words (2026-11-02)

**30. The cross-platform study in the posting uses GA4 data; this one used only the platforms' own reports.**
Added a GA4 export for the own site (src/ga4_export.py, rules in world.GA4): GA4 sees only the website's consented sessions (47% of sales here) and counts each sale once, but its data-driven credit still follows clicks. Its paid total is 2.76B, half of what ads added, the opposite error from the platforms' 1.3x. Within the mix it gives search 63% of the paid credit against a 27% share of what ads added (truth 34%) and short video 13% against 48% (truth 47%): the same headroom, now from data the advertiser owns. Social and retargeting fall inside the model's range and are left unclear, although the truth calls them. The GA4 rules are stated as a limit: channel level, not user paths.

**31. Refitting the MMM after the auto-bidding switch did not fix the forecast at first.**
Refitted on weeks 1-100, the model still under-predicts weeks 101-104 by 1.5% (2 of 4 weeks inside the 90% range, against 0 of 4 before): one search curve for 100 weeks cannot bend for the last four. A level-shift term from the known switch week fixes it: 0.27% error, 4 of 4 inside. The term is not the switch's effect, though: 8.1M a week (90%: 4.1-11.9M) against a true 3.3M, because it also absorbs what the model gets wrong about search. The page says so; what the switch added stays with chapter 3's read on total sales.

**32. Forty geo units of equal size is generous for Korea.**
Added a limit: matched pairs in Korea would be built from city and county clusters, Seoul and Gyeonggi are hard to split, and regional sales need shipping addresses. Where pairs cannot be matched, the playbook's fallback is a user-level conversion lift study.

**33. The account-team notes never named a Google product.**
The study is written in method names on purpose, but an MIE works with the account team to grow adoption of specific solutions. Added a table to the internal notes only: each finding, the Google solution it argues for, the measurement that would prove it, and the pitch (short video to YouTube Shorts through Demand Gen, proved with geo-based Conversion Lift; search to a GeoX holdout before reinvesting; auto-bidding to Performance Max brand exclusions and a new-customer goal; retargeting to a user-based lift holdout; tracking gaps to enhanced conversions and consent mode; the model to Meridian). Two first-draft mappings were wrong and fixed: Search Lift measures searches driven by video ads, so it belongs with video, not search; and offline conversion import cannot reach marketplace orders, which carry no click ID, so those stay with geo tests and the MMM.

**34. The GA4 finding never reached the advertiser, and its limit was understated.**
A last review found the GA4 comparison only on the Budget tab and in the internal notes. The readout now says in its bottom line that the advertiser's own GA4 points the same way (search 63% of paid credit against a 27% share of what ads added; short video 13% against 48%), and asks the advertiser to link GA4 to Google Ads and turn on enhanced conversions and consent mode, with the Korean version to match. The limit now says plainly that the GA4 export is built from the platforms' own claims, so the direction of its mix partly follows them by construction: it shows how to read GA4, not a second independent proof.

