"""Finnhub source for live US equity ticks (requires FINNHUB_API_KEY).

When the key is present the WebSocket gives genuine real-time trades and the
feed can honestly claim LIVE freshness. Without a key the provider reports
itself as unavailable and the feed manager falls back to Yahoo (DELAYED).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Optional

import httpx

from .base import EmitFn, HistoryResult, MarketDataProvider

logger = logging.getLogger("provider.finnhub")

WS_URL = "wss://ws.finnhub.io"


class FinnhubProvider(MarketDataProvider):
    name = "finnhub"
    freshness = "LIVE"
    supports_stream = True

    @staticmethod
    def api_key() -> Optional[str]:
        return os.getenv("FINNHUB_API_KEY") or None

    def available(self) -> bool:
        return bool(self.api_key())

    async def get_history(self, asset, timeframe: str, lookback_days: int) -> HistoryResult:
        key = self.api_key()
        if not key:
            return HistoryResult(status="ERROR", source="Finnhub", message="FINNHUB_API_KEY not set")
        resolution = {"1m": "1", "5m": "5", "15m": "15", "30m": "30",
                      "1h": "60", "1d": "D"}.get(timeframe, "D")
        import time as _t

        now = int(_t.time())
        frm = now - lookback_days * 86400
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://finnhub.io/api/v1/stock/candle",
                    params={"symbol": asset.provider_symbol, "resolution": resolution,
                            "from": frm, "to": now, "token": key},
                )
                data = resp.json()
        except Exception as exc:
            return HistoryResult(status="ERROR", source="Finnhub", message=str(exc))
        if not isinstance(data, dict) or data.get("s") != "ok":
            return HistoryResult(status="ERROR", source="Finnhub", message="No Finnhub candles")
        import pandas as pd

        df = pd.DataFrame(
            {
                "Timestamp": pd.to_datetime(data["t"], unit="s", utc=True),
                "Open": data["o"], "High": data["h"], "Low": data["l"],
                "Close": data["c"], "Volume": data["v"],
            }
        )
        return HistoryResult(status="SUCCESS", dataframe=df, source="Finnhub", timeframe=timeframe)

    async def get_latest_price(self, asset) -> Optional[float]:
        key = self.api_key()
        if not key:
            return None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://finnhub.io/api/v1/quote",
                    params={"symbol": asset.provider_symbol, "token": key},
                )
                data = resp.json()
                price = data.get("c")
                return float(price) if price else None
        except Exception as exc:
            logger.warning("Finnhub quote failed: %s", exc)
            return None

    async def stream(self, asset, emit: EmitFn, poll_interval: float = 15.0) -> None:
        import websockets

        key = self.api_key()
        if not key:
            raise RuntimeError("FINNHUB_API_KEY not set")
        url = f"{WS_URL}?token={key}"
        async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
            await ws.send(json.dumps({"type": "subscribe", "symbol": asset.provider_symbol}))
            logger.info("Finnhub WS subscribed to %s", asset.provider_symbol)
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                if msg.get("type") != "trade":
                    continue
                for trade in msg.get("data", []):
                    price = trade.get("p")
                    if price is None:
                        continue
                    await emit(
                        {
                            "type": "tick",
                            "price": float(price),
                            "volume": float(trade.get("v", 0.0)),
                            "ts": float(trade.get("t", 0)) / 1000.0,
                            "source": self.name,
                        }
                    )
