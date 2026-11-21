"""Yahoo Finance source (no API key required).

Used as (a) the historical fallback for stocks/indices and (b) a polling
live fallback when no streaming key/broker is configured. NSE data is
delayed ~15 minutes, hence the DELAYED freshness label.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

import pandas as pd
import yfinance as yf

from ..fetcher import fetch_historical_data
from .base import EmitFn, HistoryResult, MarketDataProvider

logger = logging.getLogger("provider.yahoo")


class YahooProvider(MarketDataProvider):
    name = "yfinance"
    freshness = "DELAYED"
    supports_stream = False

    async def get_history(self, asset, timeframe: str, lookback_days: int) -> HistoryResult:
        res = await asyncio.to_thread(fetch_historical_data, asset.input_symbol, timeframe)
        if res.get("status") == "SUCCESS" and res.get("dataframe") is not None:
            return HistoryResult(
                status="SUCCESS",
                dataframe=res["dataframe"],
                source=res.get("data_source", "Yahoo Finance Feed"),
                timeframe=timeframe,
            )
        return HistoryResult(
            status=res.get("status", "ERROR"),
            source="Yahoo Finance Feed",
            message=res.get("message", "Yahoo Finance returned no data."),
            timeframe=timeframe,
        )

    def _blocking_last_price(self, asset) -> Optional[float]:
        ticker = yf.Ticker(asset.yahoo_symbol)
        # Prefer the fastest available quote.
        try:
            fi = ticker.fast_info
            for attr in ("last_price", "regular_market_price"):
                val = getattr(fi, attr, None)
                if val:
                    return float(val)
        except Exception:
            pass
        for period, interval in (("1d", "1m"), ("5d", "5m"), ("1mo", "1d")):
            try:
                hist = ticker.history(period=period, interval=interval, auto_adjust=True)
                if not hist.empty:
                    return float(hist["Close"].iloc[-1])
            except Exception:
                continue
        return None

    async def get_latest_price(self, asset) -> Optional[float]:
        try:
            return await asyncio.to_thread(self._blocking_last_price, asset)
        except Exception as exc:
            logger.warning("Yahoo last-price failed for %s: %s", asset.yahoo_symbol, exc)
            return None
