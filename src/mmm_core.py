"""Weekly national media mix model: data prep and the response function.

  revenue_w = base_w + sum_c beta_c * hill(adstock(spend_cw))
  base_w    = c0 + c1 * category_searches_w + c2 * week_index
  adstock   = truncated, normalized geometric carry-over (8 weekly lags)
  hill      = a / (a + K_c),  K_c = kappa_c * median weekly spend of c

beta_c is written through ROI: beta_c = roi_c * total spend_c / sum_w hill_cw,
so roi_c is the channel's average return over the fitted weeks. That is the
quantity experiments measure, which is what makes calibration direct.

Spend and revenue are in million KRW per week. Search = brand search +
non-brand search + auto-bidding (the switch changed how search is bought,
not whether PAWLY buys search).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CHANNELS = ["search", "short_video", "social", "retargeting"]
LAGS = 8


def weekly() -> pd.DataFrame:
    """National weekly table from sql/marts.sql (mart: national_week)."""
    from build_marts import read
    return read("national_week")


def lag_matrix(x: np.ndarray, lags: int = LAGS) -> np.ndarray:
    """(T, lags+1): column l is x shifted by l weeks (zeros before week 1)."""
    T = len(x)
    out = np.zeros((T, lags + 1))
    for l in range(lags + 1):
        out[l:, l] = x[: T - l]
    return out


def adstock_weights(lam, lags: int = LAGS, xp=np):
    l = xp.arange(lags + 1)
    w = (1 - lam) * lam ** l
    return w / w.sum()


def contributions_np(spend: dict, draws: dict, beta: np.ndarray) -> np.ndarray:
    """Weekly contribution per draw and channel for a spend path.

    spend: channel -> (T,) weekly spend; draws: lam, K arrays (S, C);
    beta: (S, C). Returns (S, T, C).
    """
    S = beta.shape[0]
    T = len(next(iter(spend.values())))
    out = np.empty((S, T, len(CHANNELS)))
    for j, c in enumerate(CHANNELS):
        L = lag_matrix(spend[c])                                   # (T, lags+1)
        lam = draws["lam"][:, j]
        lags = np.arange(LAGS + 1)
        w = (1 - lam[:, None]) * lam[:, None] ** lags[None, :]
        w = w / w.sum(axis=1, keepdims=True)                       # (S, lags+1)
        a = w @ L.T                                                # (S, T)
        h = a / (a + draws["K"][:, j][:, None])
        out[:, :, j] = beta[:, j][:, None] * h
    return out
