from __future__ import annotations


def compute_micro_trend_score(df):
    """Phase-1 deterministic proxy for micro-trend score (0-100).

    Replace with learned model (e.g., Mamba-based scorer) in later iteration.
    """
    import numpy as np

    close = df["close"].astype(float)
    ret = close.pct_change().fillna(0)
    vol = ret.rolling(20).std().fillna(ret.std() or 1e-9)
    mom = ret.rolling(10).mean().fillna(0)

    raw = (mom / (vol + 1e-9)).clip(-3, 3)
    score = 50 + (raw * 15)
    return score.clip(0, 100)


def build_track_b_signal(df, rsi_series, score_threshold: float = 80.0):
    """AI-filtered mean reversion signal.

    Entry: score>threshold + RSI<30 + bullish close candle.
    """
    import pandas as pd

    close = df["close"].astype(float)
    open_ = df["open"].astype(float) if "open" in df.columns else close.shift(1).fillna(close)
    bullish_close = close > open_

    score = compute_micro_trend_score(df)
    signal = ((score > score_threshold) & (rsi_series < 30) & bullish_close).astype(float)
    return pd.Series(signal, index=df.index)
