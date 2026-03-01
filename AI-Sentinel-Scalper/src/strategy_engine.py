from __future__ import annotations

import json
from pathlib import Path


def _rsi(series, period: int = 14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def build_signal(df, strategy: dict):
    """Return 0/1 position signal from strategy contract.

    Regime A: EMA trend + RSI guard
    Regime B: Bollinger mean-reversion + RSI confirmation
    Regime C / flat: no trades
    """
    import pandas as pd

    regime = strategy.get("regime", "C")
    status = strategy.get("status", "flat")
    params = strategy.get("parameters", {})
    ind = params.get("indicators", {})

    close = df["close"].astype(float)
    ema_fast_n = int(ind.get("ema_fast", 9))
    ema_slow_n = int(ind.get("ema_slow", 21))
    rsi_n = int(ind.get("rsi_period", 14))
    bb_std = float(ind.get("bb_std_dev", 2.5))

    ema_fast = close.ewm(span=ema_fast_n, adjust=False).mean()
    ema_slow = close.ewm(span=ema_slow_n, adjust=False).mean()
    rsi = _rsi(close, rsi_n).fillna(50)

    ma = close.rolling(20).mean()
    std = close.rolling(20).std().fillna(0)
    bb_upper = ma + bb_std * std
    bb_lower = ma - bb_std * std

    if regime == "C" or status in {"flat", "paused"}:
        return pd.Series(0.0, index=df.index)

    if regime == "A":
        # momentum: trend alignment + avoid overbought spike entries
        sig = ((close > ema_fast) & (ema_fast > ema_slow) & (rsi < 65)).astype(float)
        return sig

    if regime == "B":
        # mean-reversion: buy lower band with RSI oversold
        sig = ((close < bb_lower) & (rsi < 35)).astype(float)
        return sig

    return pd.Series(0.0, index=df.index)


def load_strategy(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
