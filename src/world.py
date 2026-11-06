"""PAWLY world: the true data-generating process behind every chapter.

PAWLY is a fictional Korean pet-food D2C brand (own site + two marketplaces)
selling in 40 regions. All random noise is drawn once when the World is built,
so simulate(plan) is deterministic: running the same world under two plans
gives the exact counterfactual. That is how every chapter is graded against
the truth.

Analysis scripts only ever see the "observed" columns. The "truth" columns
(incremental revenue by channel, baseline) are written to data/truth/ and are
read only by the validation steps.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

START = pd.Timestamp("2024-11-04")  # a Monday
N_DAYS = 728                        # 104 weeks
N_GEO = 40
WORLD_SEED = 20261031
PLAN_SEED = 7

CHANNELS = ["brand_search", "nonbrand_search", "auto_bid",
            "short_video", "social", "retargeting"]

# Timeline (1-based week numbers). Weeks 1-78 are the history the advertiser
# has before the first test.
HISTORY_WEEKS = 78
GEO_TEST_WEEKS = (79, 84)       # chapter 1: 6-week go-dark geo test on short video
VIDEO_PAUSE_WEEKS = (89, 92)    # chapter 2: national 4-week video pause (summer dip)
AUTO_BID_SWITCH_WEEK = 97       # chapter 3: search moves to AI auto-bidding
AUTO_BID_BUDGET_UP_WEEK = 101   # advertiser raises search budget after high reported ROAS
TEST_VIDEO_M = 2.5              # stable national video budget during the geo test
LOCAL_PROMO_WEEKS = (80, 83)    # trap 4: a retail partner's promo in one control region
LOCAL_PROMO_LIFT = 1.25

AOV = 38_000  # KRW per order

# True response parameters. Spend is in million KRW per day, expressed as the
# national-equivalent level (geo spend / geo share), so one curve fits all geos.
# beta = incremental revenue (million KRW/day, national) at full saturation.
TRUE = {
    "base_rev": 40.0,          # organic revenue not tied to brand search, M KRW/day
    "brand_origin_rev": 10.0,  # revenue from people who search the brand name
    "bsv": 20_000,             # brand searches per day, national
    "growth": 0.15,            # yearly growth
    "short_video": {"beta": 6.0, "K": 2.5, "slope": 1.2, "decay": 0.80},
    "awareness": {"K": 2.5, "slope": 1.0, "decay": 0.95, "bsv_lift": 0.25},
    "nonbrand_search": {"beta": 4.8, "K": 1.5, "slope": 1.0, "decay": 0.50},
    "social": {"beta": 2.4, "K": 1.2, "slope": 1.0, "decay": 0.70},
    "retargeting": {"beta": 0.8, "K": 0.8, "slope": 1.0, "decay": 0.30},
    # brand search ads mostly harvest people who would have bought anyway:
    # without ads only ~6% of brand-origin revenue is lost to competitors.
    "brand_search": {"protect": 0.06, "K": 0.5, "slope": 1.0, "decay": 0.0},
    # auto-bidding: spend split like the old manual mix, ~10% more efficient.
    "auto_bid": {"efficiency": 1.10, "nonbrand_part": 0.6},
}

# How the ad platforms report (last-click style, click-through windows).
REPORTED = {
    "brand_search_clickshare": 0.60,   # share of brand-origin revenue credited
    "nonbrand_over": 1.30,             # credited / true incremental
    "video_click_share": 0.25,         # click-only reporting misses views
    "social_over": 0.80,
    "social_base_capture": 0.02,
    "retarget_base_capture": 0.08,     # returning customers credited to retargeting
    "auto_brand_capture": 0.85,        # auto-bid takes brand searches...
    "auto_base_capture": 0.10,         # ...and returning visitors (7-day window)
}

# How GA4 on PAWLY's own site sees the same sales (read by ga4_export.py).
# GA4 de-duplicates across channels, but it only sees the website, only
# consented sessions, and its data-driven credit still follows clicks.
GA4 = {
    "site_share": 0.55,        # own-site share of revenue; marketplace orders are invisible to GA4
    "observed_share": 0.85,    # site revenue GA4 records after consent choices and browser limits
    # data-driven credit relative to each platform's own claim, once paths are de-duplicated:
    # late touches share credit with earlier ones; engaged video views earn some credit
    "dda_vs_claim": {"search": 0.80, "short_video": 1.80, "social": 0.85, "retargeting": 0.55},
}


def hill(x: np.ndarray, K: float, slope: float) -> np.ndarray:
    x = np.maximum(x, 0.0)
    xs = x ** slope
    return xs / (xs + K ** slope)


def adstock(x: np.ndarray, decay: float) -> np.ndarray:
    """Normalized geometric carry-over along axis 0 (days)."""
    if decay == 0:
        return x.copy()
    out = np.empty_like(x)
    out[0] = x[0]
    for t in range(1, len(x)):
        out[t] = decay * out[t - 1] + (1 - decay) * x[t]
    return out


@dataclass
class Plan:
    """Daily spend (KRW) per channel and geo, plus geo-day demand shocks."""
    spend: dict[str, np.ndarray]
    local_promo: np.ndarray = field(default=None)  # (days, geos) multiplier

    def copy(self) -> "Plan":
        return Plan({c: s.copy() for c, s in self.spend.items()},
                    None if self.local_promo is None else self.local_promo.copy())


class World:
    def __init__(self, seed: int = WORLD_SEED, noise_seed: int | None = None):
        """noise_seed keeps the regions (sizes, demand, growth) and redraws only
        the noise: the same market on a different luck draw, for Monte Carlo."""
        rng = np.random.default_rng(seed)
        self.dates = pd.date_range(START, periods=N_DAYS, freq="D")
        self.week = np.arange(N_DAYS) // 7 + 1
        self.geo_ids = [f"G{i + 1:02d}" for i in range(N_GEO)]

        pop = rng.lognormal(0.0, 0.7, N_GEO)
        self.share = pop / pop.sum()
        self.geo_eff = rng.uniform(0.85, 1.15, N_GEO)      # demand per capita
        self.geo_growth = rng.normal(0.0, 0.05, N_GEO)     # extra yearly growth
        if noise_seed is not None:
            rng = np.random.default_rng(noise_seed)

        # revenue noise: geo AR(1) shock + daily idiosyncratic noise
        eps = rng.normal(0.0, 0.04, (N_DAYS, N_GEO))
        ar = np.zeros_like(eps)
        for t in range(1, N_DAYS):
            ar[t] = 0.7 * ar[t - 1] + eps[t]
        self.rev_noise = ar + rng.normal(0.0, 0.08, (N_DAYS, N_GEO))
        self.bsv_noise = rng.normal(0.0, 0.10, (N_DAYS, N_GEO))
        self.aov_noise = rng.normal(0.0, 0.03, (N_DAYS, N_GEO))
        # separate stream so adding it left the original noise untouched
        cat_seed = seed + 1 if noise_seed is None else noise_seed + 100_000
        self.cat_noise = np.random.default_rng(cat_seed).normal(0.0, 0.05, (N_DAYS, N_GEO))

        self.demand = self._demand_curve()  # (days, geos), no noise

    # ---------------------------------------------------------------- demand
    def _demand_curve(self) -> np.ndarray:
        doy = self.dates.dayofyear.values
        season = (1 + 0.06 * np.cos(2 * np.pi * (doy - 15) / 365)
                  - 0.15 * np.exp(-((doy - 212) / 14.0) ** 2))   # summer-holiday dip
        dow = np.array([1.04, 1.00, 0.98, 0.97, 1.00, 0.96, 1.05])[self.dates.dayofweek.values]
        promo = np.ones(N_DAYS)
        for d, m in {"2024-11-11": 1.8, "2025-03-03": 1.4, "2025-11-11": 1.8,
                     "2026-03-03": 1.4}.items():
            promo[self.dates.get_loc(pd.Timestamp(d))] = m
        years = np.arange(N_DAYS) / 365.0
        trend = (1 + TRUE["growth"]) ** years
        common = season * dow * promo * trend
        geo_trend = 1 + np.outer(years, self.geo_growth)
        return common[:, None] * geo_trend * self.geo_eff[None, :]

    # -------------------------------------------------------------- simulate
    def simulate(self, plan: Plan) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Return (observed, truth), both long format: one row per geo-day."""
        sh = self.share[None, :]
        promo = np.ones((N_DAYS, N_GEO)) if plan.local_promo is None else plan.local_promo
        demand = self.demand * promo
        # national-equivalent spend in million KRW / day
        x = {c: plan.spend[c] / sh / 1e6 for c in CHANNELS}

        trend_only = (1 + TRUE["growth"]) ** (np.arange(N_DAYS) / 365.0)
        scale = sh * trend_only[:, None]  # ad response grows with the business

        # short video: direct effect + slow awareness that lifts brand search
        pv = TRUE["short_video"]
        video_direct = scale * pv["beta"] * hill(adstock(x["short_video"], pv["decay"]), pv["K"], pv["slope"])
        pa = TRUE["awareness"]
        awareness = hill(adstock(x["short_video"], pa["decay"]), pa["K"], pa["slope"])
        aware_mult = 1 + pa["bsv_lift"] * awareness

        noise = np.exp(self.rev_noise)
        base = TRUE["base_rev"] * sh * demand * noise
        brand_origin = TRUE["brand_origin_rev"] * sh * demand * aware_mult * np.exp(0.5 * self.rev_noise)
        bsv = TRUE["bsv"] * sh * demand * aware_mult * np.exp(self.bsv_noise)
        brand_origin_no_video = brand_origin / aware_mult
        video_indirect = brand_origin - brand_origin_no_video

        def resp(ch):
            p = TRUE[ch]
            return scale * p["beta"] * hill(adstock(x[ch], p["decay"]), p["K"], p["slope"])

        nonbrand = resp("nonbrand_search")
        social = resp("social")
        retarget = resp("retargeting")

        pb = TRUE["brand_search"]
        bs_share = hill(x["brand_search"], pb["K"], pb["slope"])
        brand_inc = pb["protect"] * brand_origin * bs_share

        pab = TRUE["auto_bid"]
        pn = TRUE["nonbrand_search"]
        xa = x["auto_bid"]
        auto_nb = scale * pn["beta"] * hill(adstock(pab["nonbrand_part"] * xa, pn["decay"]), pn["K"], pn["slope"])
        auto_share = hill((1 - pab["nonbrand_part"]) * xa, pb["K"], pb["slope"])
        auto_inc = pab["efficiency"] * (auto_nb + pb["protect"] * brand_origin * auto_share)

        incr = {
            "brand_search": brand_inc,
            "nonbrand_search": nonbrand,
            "auto_bid": auto_inc,
            "short_video": video_direct + video_indirect,
            "social": social,
            "retargeting": retarget,
        }
        # brand-origin revenue already contains the video lift and is reduced
        # when nobody protects the brand term; brand_inc is the protected part.
        unprotected_loss = pb["protect"] * brand_origin  # lost if no brand/auto ads
        revenue = (base + brand_origin - unprotected_loss + brand_inc + auto_inc
                   + nonbrand + social + retarget + video_direct) * 1e6

        R = REPORTED
        auto_on = hill(xa, 1.0, 1.0)
        reported = {
            "brand_search": R["brand_search_clickshare"] * brand_origin * bs_share,
            "nonbrand_search": R["nonbrand_over"] * nonbrand,
            "auto_bid": (R["auto_brand_capture"] * brand_origin * auto_on
                         + R["auto_base_capture"] * base * auto_on
                         + R["nonbrand_over"] * auto_inc),
            "short_video": R["video_click_share"] * video_direct,
            "social": R["social_over"] * social + R["social_base_capture"] * base * hill(x["social"], 1.2, 1.0),
            "retargeting": retarget + R["retarget_base_capture"] * base * hill(x["retargeting"], 0.8, 1.0),
        }

        orders = np.round(revenue / (AOV * np.exp(self.aov_noise)))
        idx = pd.MultiIndex.from_product([self.dates, self.geo_ids], names=["date", "geo"])
        # pet-food category searches in each region: market demand only,
        # untouched by PAWLY's ads or PAWLY-specific promotions
        category = 100 * N_GEO * sh * self.demand * np.exp(self.cat_noise)
        obs = {"week": np.repeat(self.week, N_GEO),
               "revenue": revenue.ravel(), "orders": orders.ravel(),
               "brand_search_volume": np.round(bsv.ravel()),
               "category_search_index": category.ravel().round(1)}
        for c in CHANNELS:
            obs[f"spend_{c}"] = plan.spend[c].ravel()
            obs[f"reported_rev_{c}"] = (reported[c] * 1e6).ravel()
        observed = pd.DataFrame(obs, index=idx).reset_index()

        tr = {"week": np.repeat(self.week, N_GEO),
              "base_rev": ((base + brand_origin_no_video - unprotected_loss) * 1e6).ravel(),
              "awareness": np.broadcast_to(awareness, (N_DAYS, N_GEO)).ravel()}
        for c in CHANNELS:
            tr[f"incr_rev_{c}"] = (incr[c] * 1e6).ravel()
        truth = pd.DataFrame(tr, index=idx).reset_index()
        return observed, truth


# ------------------------------------------------------------------- plans
def bau_plan(world: World, seed: int = PLAN_SEED) -> Plan:
    """Business as usual for all 104 weeks: manual search, video flights.

    Search budgets rise when video runs (marketers push both together; weekly
    correlation 0.85), so an observational MMM struggles to separate the two
    (trap 3). In this world it left search the least certain channel rather
    than over-crediting it; see docs/work_log.md, entry 11.
    """
    rng = np.random.default_rng(seed)
    n_weeks = N_DAYS // 7
    levels = np.array([0.3, 0.7, 1.0, 1.4, 1.8])
    state, video = 2, []
    for _ in range(n_weeks):
        if rng.random() < 0.35:
            state = int(np.clip(state + rng.choice([-2, -1, 1, 2]), 0, len(levels) - 1))
        video.append(levels[state])
    video = np.array(video)
    vnorm = (video - video.mean()) / video.std()
    search = np.clip(1 + 0.15 * vnorm + rng.normal(0, 0.12, n_weeks), 0.5, 1.6)
    social = np.clip(rng.choice([0.6, 0.8, 1.0, 1.2, 1.4], n_weeks), 0.5, 1.5)
    retarget = rng.uniform(0.9, 1.1, n_weeks)

    national_week = {  # million KRW per day
        "brand_search": 1.0 * search,
        "nonbrand_search": 1.5 * search,
        "auto_bid": np.zeros(n_weeks),
        "short_video": 2.5 * video,
        "social": 1.2 * social,
        "retargeting": 0.8 * retarget,
    }
    geo_jitter = rng.normal(1.0, 0.05, (n_weeks, N_GEO))
    spend = {}
    for c, nat in national_week.items():
        weekly = nat[:, None] * world.share[None, :] * geo_jitter * 1e6
        spend[c] = np.repeat(weekly, 7, axis=0)
    return Plan(spend)


def week_mask(world: World, first: int, last: int) -> np.ndarray:
    return (world.week >= first) & (world.week <= last)


def actual_plan(world: World, go_dark: np.ndarray, promo_geo: int | None,
                geo_test: bool = True, pause: bool = True, switch: bool = True,
                budget_up: bool = True) -> Plan:
    """What PAWLY actually did over 104 weeks. Turning a flag off gives the
    counterfactual for that chapter (everything else unchanged)."""
    plan = bau_plan(world)
    sp = plan.spend

    t = week_mask(world, *GEO_TEST_WEEKS)
    # during the test the budget is held flat so the read is clean
    sp["short_video"][t] = TEST_VIDEO_M * 1e6 * world.share[None, :]
    if geo_test:
        sp["short_video"][np.ix_(t, go_dark)] = 0.0

    if pause:
        sp["short_video"][week_mask(world, *VIDEO_PAUSE_WEEKS)] = 0.0

    if switch:
        s = world.week >= AUTO_BID_SWITCH_WEEK
        sp["auto_bid"][s] = sp["brand_search"][s] + sp["nonbrand_search"][s]
        sp["brand_search"][s] = 0.0
        sp["nonbrand_search"][s] = 0.0
        if budget_up:
            up = world.week >= AUTO_BID_BUDGET_UP_WEEK
            sp["auto_bid"][up] *= 1.3

    promo = np.ones((N_DAYS, N_GEO))
    if promo_geo is not None:
        promo[week_mask(world, *LOCAL_PROMO_WEEKS), promo_geo] = LOCAL_PROMO_LIFT
    plan.local_promo = promo
    return plan
