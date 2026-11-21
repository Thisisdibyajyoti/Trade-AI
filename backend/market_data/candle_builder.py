"""Tick -> OHLCV candle aggregation for every supported timeframe.

The builder keeps one *forming* candle per timeframe (`is_closed = False`)
and appends a candle to the closed series the moment a tick crosses into the
next bucket. Models only ever read closed candles, so the forming candle can
be plotted without any risk of look-ahead leaking into predictions.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import pandas as pd

TIMEFRAME_SECONDS: Dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}

MAX_CLOSED_KEPT = 6000


def bucket_start(ts: float, seconds: int) -> float:
    return math.floor(ts / seconds) * seconds


def _new_candle(bucket: float, price: float, volume: float = 0.0) -> dict:
    return {
        "time": bucket,
        "open": float(price),
        "high": float(price),
        "low": float(price),
        "close": float(price),
        "volume": float(volume),
        "is_closed": False,
    }


class CandleBuilder:
    def __init__(self, timeframes: List[str]):
        self.timeframes = [tf for tf in timeframes if tf in TIMEFRAME_SECONDS]
        self.closed: Dict[str, List[dict]] = {tf: [] for tf in self.timeframes}
        self.forming: Dict[str, Optional[dict]] = {tf: None for tf in self.timeframes}

    # -- seeding from historical backfill ------------------------------------
    def seed(self, timeframe: str, df: pd.DataFrame) -> int:
        """Load closed historical candles for one timeframe."""
        if timeframe not in TIMEFRAME_SECONDS or df is None or df.empty:
            return 0
        candles: List[dict] = []
        for _, row in df.iterrows():
            ts = pd.Timestamp(row["Timestamp"])
            if ts.tzinfo is None:
                ts = ts.tz_localize("UTC")
            candles.append(
                {
                    "time": float(ts.timestamp()),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row.get("Volume", 0.0) or 0.0),
                    "is_closed": True,
                }
            )
        candles.sort(key=lambda c: c["time"])
        # de-duplicate on the bucket boundary
        dedup: Dict[float, dict] = {c["time"]: c for c in candles}
        merged = [dedup[k] for k in sorted(dedup)]
        # never let the seeded series be shorter than what we already have
        if len(merged) >= len(self.closed.get(timeframe, [])):
            self.closed[timeframe] = merged[-MAX_CLOSED_KEPT:]
        return len(merged)

    def has_history(self, timeframe: str) -> bool:
        return len(self.closed.get(timeframe, [])) > 0

    # -- live tick ingestion -------------------------------------------------
    def on_tick(self, price: float, volume: float, ts: float) -> List[Tuple[str, dict, bool]]:
        """
        Apply a validated tick. Returns a list of
        `(timeframe, candle, is_closed)` updates for every affected timeframe.
        """
        updates: List[Tuple[str, dict, bool]] = []
        for tf in self.timeframes:
            seconds = TIMEFRAME_SECONDS[tf]
            bucket = bucket_start(ts, seconds)
            forming = self.forming[tf]

            if forming is None:
                if not self.has_history(tf):
                    # Without history we cannot place this tick safely; the
                    # feed backfills before streaming, so this is a no-op guard.
                    continue
                self.forming[tf] = _new_candle(bucket, price, volume)
                updates.append((tf, self.forming[tf], False))
                continue

            if bucket == forming["time"]:
                forming["high"] = max(forming["high"], price)
                forming["low"] = min(forming["low"], price)
                forming["close"] = price
                forming["volume"] += volume
                updates.append((tf, forming, False))
            elif bucket > forming["time"]:
                # Close the old candle and start a new one.
                closed = dict(forming)
                closed["is_closed"] = True
                series = self.closed[tf]
                # Only append if it strictly advances the series (no dupes).
                if not series or series[-1]["time"] < closed["time"]:
                    series.append(closed)
                    if len(series) > MAX_CLOSED_KEPT:
                        del series[: len(series) - MAX_CLOSED_KEPT]
                    updates.append((tf, closed, True))
                self.forming[tf] = _new_candle(bucket, price, volume)
                updates.append((tf, self.forming[tf], False))
            # else: out-of-order tick -> ignored
        return updates

    def closed_candles(self, timeframe: str) -> List[dict]:
        return self.closed.get(timeframe, [])

    def snapshot(self, timeframe: str, limit: int = 500) -> List[dict]:
        """Closed series plus the forming candle, for chart seeding/updates."""
        series = list(self.closed.get(timeframe, [])[-limit:])
        forming = self.forming.get(timeframe)
        if forming is not None:
            series.append(forming)
        return series
