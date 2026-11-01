# PAWLY Incrementality Lab (synthetic data)

A measurement portfolio project for a **fictional** Korean pet-food brand, "PAWLY", that sells direct to consumers
and through two marketplaces in 40 regions. It answers five questions a small, fast-growing advertiser asks about its
ads, each with the study that fits the question. PAWLY was chosen as a typical fast-growing small D2C advertiser whose
profit depends on repeat purchases; the methods apply to any e-commerce advertiser. All data is simulated from a known
process, so every estimate is graded against the truth. Shared data preparation is done in SQL (DuckDB, [`sql/marts.sql`](sql/marts.sql)); the
studies are in Python (PyMC, statsmodels).

**Live demo:** https://seongyooseop.github.io/pawly-incrementality-lab/site/ (or open `site/index.html`: one
self-contained file, seven tabs, each with a "How to read this tab" guide).

## At a glance

| Question | Study | Naive answer | This study | Truth |
|---|---|---|---|---|
| Does short-form video add sales? | Geo experiment, 20 matched region pairs, 6 weeks | Platform ROAS 0.30 | iROAS **1.20** (95%: 0.58-1.81) | 1.48 |
| What did a 4-week video pause cost? | Causal impact (Bayesian structural time series) | Before/after: KRW 245M | **KRW 93M** (32-164M) | KRW 115M |
| Reported search revenue +93% after AI auto-bidding. Real? | Total sales around the switch, 456 placebo dates | +KRW 242M reported | **-KRW 4M** (-42 to +33M), p = 0.92 | +KRW 13M |
| Did the 30% budget increase that followed pay back? | Same design at the increase | Reported ROAS 6.87 | Marginal iROAS **0.15** (-0.35 to 0.64) | 0.61 |
| Every platform claims the sale. Whose numbers? | Cross-platform: platform claims vs calibrated MMM | Claims add up to KRW 6.9B | Ads added **KRW 5.3B** (4.1-6.9B): claims are **1.3x** what ads added | 1.4x |
| How to split next year's budget? | Response curves, marginal ROI, plans run through the true world | - | Next won returns under a won in every channel; risk-aware plan keeps **64%** of the best possible gain | marginal ROI 0.3-0.8 |

All 11 headline intervals contain the truth. The advertiser readout is in
[`docs/advertiser_readout.md`](docs/advertiser_readout.md), with a plain-language Korean version for the business owner
in [`docs/advertiser_readout_ko.md`](docs/advertiser_readout_ko.md).

## Chapters

0. **Pick the study from the question.** A decision table: which study answers which question, the minimum budget and
   duration each needs (eligibility), computed from PAWLY's own history, and what to do when an advertiser is below
   the geo-test threshold.
1. **Geo experiment.** Regions paired by size, one per pair switched off. Before launch, past weeks are replayed as
   fake tests to measure power: a 6-week test detects a 2.6% revenue drop (any iROAS of 0.70 or more); 8 weeks adds
   almost nothing. The readout uses time-based regression (TBR); a pair diagnostic catches a retail promotion in one
   control region, and 60 re-runs on fresh noise show the contaminated readout overstates iROAS by 0.34 on average.
   Part of video's effect lands after the test, so a second read adds a 2-week cooldown (iROAS 1.52 vs true 1.69;
   the 6-week read understates the fuller effect by 0.15 on average). Design options compared on the same history:
   a 30% go-dark share detects a return of 0.75 (vs 0.70) with about 60% of the sales at risk, so the next test uses
   it; a heavy-up can only detect a marginal return of 1.40, above anything this advertiser earns at the margin.
2. **Causal impact.** A national pause with no holdout. The counterfactual comes from a Bayesian structural time series
   in PyMC with pet-food category searches as the control series; geo-test weeks are masked. A before/after view
   doubles the loss because the pause fell in the summer dip.
3. **Auto-bidding.** Regression discontinuity in time on total sales, with separate slopes on each side and placebo
   dates. 95-100% of the reported increase is sales that were already happening, re-credited to search.
4. **Budget.** A weekly Bayesian MMM fitted before the tests and again with both experiment results as calibration
   terms. A cross-platform view sets each platform's self-reported revenue against what it added: short video is the
   only channel credited with less than it adds; search and retargeting are credited 3-4 times their contribution.
   Marginal ROI at today's budget, response curves, then reallocations run through the true world.
5. **Advertiser readout.** Bottom line, confidence, next year's budget, what the returns mean in profit (the repeat
   buying each channel needs to pay back at an assumed margin), a quarterly learning agenda for 2027 (search holdout,
   total-budget step-down, retargeting audience holdout, recalibrated MMM with a brand lift survey), what the advertiser
   needs to provide, and internal notes for the account team (growth opportunity, how to position the search test,
   which parts are reusable for the next client).

## What did not go to plan

- **Calibration moved the MMM little.** Before any test, the model's predicted loss for the geo-test weeks was
  KRW 60.5M; the test measured 64.8M. The model already agreed with the experiment.
- **Trap 3 behaved differently from its design.** Video and search spend move together (correlation 0.85), meant to
  make the model hand video's effect to search. Instead search came out *under*-valued and least certain. The world
  was left as it is rather than tuned until the trap fired.
- **Plans that follow the model's average lose most of the possible gain** (5-28%), because they cut the under-valued
  search channel. Plans that move budget only where the model is confident keep 31-64%.
- **Social cannot be called.** The model puts social's return above what the platform reports; the truth puts it
  slightly below. Its interval contains the report, so the cross-platform view says "unclear" instead of guessing.

Every problem the checks caught is in [`docs/ai_workflow_log.md`](docs/ai_workflow_log.md) (24 entries), including
an A/A test that showed the textbook TBR crying wolf 22% of the time.

## How the methods map to platform tools

The study is written in platform-neutral terms. The closest named tools:

| This project | Google | TikTok |
|---|---|---|
| Geo experiment with TBR, A/A-calibrated | GeoX (geo experiments), TBR / Trimmed Match | Lift studies (conversion lift) |
| Brand-search lift as a second KPI | Search Lift, Brand Lift | Brand Lift Study |
| Causal impact (Bayesian structural time series) | CausalImpact (open source) | - |
| Reported vs incremental under AI auto-bidding | Smart Bidding, Performance Max | Automated campaign solutions |
| Cross-platform view: platform claims vs incremental revenue | Cross-platform analysis (GA4 data) | 1P vs 3P measurement |
| Bayesian MMM with experiment calibration, response curves | Meridian (open source) | MMM with measurement partners |

## Pipeline

```
python src/generate_history.py   # world check + the 78 weeks before any test
python src/ch1_design.py         # pairing, A/A calibration, power, eligibility
python src/ch0_playbook.py       # question -> study table
python src/run_timeline.py       # all 104 weeks + counterfactual truth per chapter
python src/build_marts.py        # sql/marts.sql in DuckDB -> data/marts (national tables, pair diagnostic, platform claims)
python src/ch1_readout.py        # geo test readout and pair diagnostic
python src/ch1_montecarlo.py     # the same readout on 60 noise draws
python src/ch2_causal_impact.py  # Bayesian structural time series (PyMC)
python src/ch3_auto_bidding.py   # RDiT + placebo dates; budget increase
python src/ch4_mmm.py            # MMM before/after tests, marginal ROI, response curves, plans (--refit to refit)
python src/cross_platform.py     # platform claims vs incremental revenue
python src/validation.py         # every headline number vs truth
python src/ch5_report.py         # advertiser readout (JSON + docs/advertiser_readout.md)
python src/build_page.py         # site/index.html
```

Python 3.12; packages in `requirements.txt`. Set `PYTHONUTF8=1` on Windows. The MMM fits take a few minutes and
are cached in `models/`.

## Layout

```
src/world.py        the simulated world: true response curves, reporting rules, plans, counterfactuals
src/geo_tbr.py      proportional TBR with A/A calibration
src/mmm_core.py     weekly MMM response function
sql/marts.sql       DuckDB marts shared by the chapters
data/               observed data and data/marts/; data/truth/ is read only by grading steps
outputs/            one JSON per chapter, plus validation.json
site/               template.html + built index.html
docs/               work log and advertiser readout
```

## Honest limits

- One simulated world. The geo test was re-run on 60 noise draws; the other chapters were checked with placebo
  windows, not repeated worlds.
- The control series is cleaner than real ones. The category-search index behind the causal-impact model follows true
  demand with 5% noise; real covariates (search trends, competitor sales) are noisier and can be touched by the
  campaign itself, which widens intervals and can bias them.
- TBR with A/A calibration instead of Trimmed Match. TBR reads the go-dark test from group totals, as in GeoX, and its
  interval was fixed with historical A/A tests. Trimmed Match, the pair-level estimator that trims outlier pairs
  automatically, is the more robust choice when pairs differ a lot; here the pair diagnostic and an advertiser check do
  that trimming by hand.
- The cross-platform view uses each platform's self-reported revenue. User-level paths, as in GA4 data-driven
  attribution, are not simulated.
- The world is mine, so the methods were tested against problems I chose. The work log records where a method failed
  a check and what changed, including results that came out differently from the plan.
- Built with Claude Code; every number on the page is produced by the scripts above.
