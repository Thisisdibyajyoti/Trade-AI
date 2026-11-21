"""Binance public market data (no API key required).

REST for history / last price, WebSocket for live trades and 1m klines.
Used as the primary live source for crypto pairs such as BTC/USDT.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

import httpx
import pandas as pd

from .base import EmitFn, HistoryResult, MarketDataProvider

logger = logging.getLogger("provider.binance")

REST_HOSTS = ("https://data-api.binance.vision", "https://api.binance.com")
# data-stream.binance.vision is Binance's market-data-only host and is reachable
# in more environments than the main stream host, so it is tried first.
WS_HOSTS = ("wss://data-stream.binance.vision", "wss://stream.binance.com:9443")

_INTERVAL_SECONDS = {
    "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "1d": 86400, "1w": 604800,
}

_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=15.0)
    return _client


class BinanceProvider(MarketDataProvider):
    name = "binance"
    freshness = "LIVE"
    supports_stream = True

    async def _rest_get(self, path: str, params: dict) -> Optional[dict | list]:
        client = _get_client()
        last_err: Optional[Exception] = None
        for host in REST_HOSTS:
            try:
                resp = await client.get(host + path, params=params)
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:  # try the next host
                last_err = exc
        logger.warning("Binance REST failed: %s", last_err)
        return None

    async def get_history(self, asset, timeframe: str, lookback_days: int) -> HistoryResult:
        interval = timeframe if timeframe in _INTERVAL_SECONDS else "1d"
        pair = asset.provider_symbol
        step_ms = _INTERVAL_SECONDS[interval] * 1000

        # How many bars do we need? Cap to keep responses sane.
        max_bars = {
            "1m": 1440, "5m": 1440, "15m": 2000, "30m": 2000,
            "1h": 2000, "4h": 1500, "1d": 3650, "1w": 520,
        }.get(interval, 1000)

        end_ms = int(time.time() * 1000)
        start_ms = int((time.time() - lookback_days * 86400) * 1000)
        needed = min(max_bars, max(120, int((end_ms - start_ms) / step_ms)))
        start_ms = end_ms - needed * step_ms

        rows: list = []
        cursor = start_ms
        guard = 0
        while cursor < end_ms and len(rows) < needed and guard < 30:
            guard += 1
            batch = await self._rest_get(
                "/api/v3/klines",
                {"symbol": pair, "interval": interval, "startTime": cursor, "limit": 1000},
            )
            if not batch:
                break
            rows.extend(batch)
            if len(batch) < 1000:
                break
            cursor = int(batch[-1][0]) + step_ms

        if not rows:
            return HistoryResult(
                status="ERROR",
                source="Binance",
                message=f"No Binance klines returned for {pair} ({interval}).",
                timeframe=interval,
            )

        # De-duplicate by open time, keep chronological order.
        by_time = {int(r[0]): r for r in rows}
        ordered = [by_time[k] for k in sorted(by_time)]

        df = pd.DataFrame(
            {
                "Timestamp": pd.to_datetime([int(r[0]) for r in ordered], unit="ms", utc=True),
                "Open": [float(r[1]) for r in ordered],
                "High": [float(r[2]) for r in ordered],
                "Low": [float(r[3]) for r in ordered],
                "Close": [float(r[4]) for r in ordered],
                "Volume": [float(r[5]) for r in ordered],
            }
        )

        if len(df) < 30:
            return HistoryResult(
                status="INSUFFICIENT_DATA",
                dataframe=df,
                source="Binance",
                message=f"Only {len(df)} candles available for {pair} ({interval}).",
                timeframe=interval,
            )

        return HistoryResult(status="SUCCESS", dataframe=df, source="Binance", timeframe=interval)

    async def get_latest_price(self, asset) -> Optional[float]:
        data = await self._rest_get("/api/v3/ticker/price", {"symbol": asset.provider_symbol})
        if isinstance(data, dict) and "price" in data:
            try:
                return float(data["price"])
            except (TypeError, ValueError):
                return None
        return None

    async def stream(self, asset, emit: EmitFn, poll_interval: float = 15.0) -> None:
        import websockets

        pair = asset.provider_symbol.lower()
        streams = f"{pair}@aggTrade/{pair}@kline_1m"

        last_err: Optional[Exception] = None
        for host in WS_HOSTS:
            url = f"{host}/stream?streams={streams}"
            try:
                async with websockets.connect(
                    url, ping_interval=20, ping_timeout=20, open_timeout=10
                ) as ws:
                    logger.info("Binance WS connected for %s", pair)
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                        except Exception:
                            continue
                        payload = msg.get("data", msg)
                        kind = payload.get("e")
                        if kind == "aggTrade":
                            await emit(
                                {
                                    "type": "tick",
                                    "price": float(payload["p"]),
                                    "volume": float(payload.get("q", 0.0)),
                                    "ts": float(payload.get("T", time.time() * 1000)) / 1000.0,
                                    "source": self.name,
                                }
                            )
                        elif kind == "kline":
                            k = payload["k"]
                            await emit(
                                {
                                    "type": "kline",
                                    "interval": k.get("i", "1m"),
                                    "open": float(k["o"]),
                                    "high": float(k["h"]),
                                    "low": float(k["l"]),
                                    "close": float(k["c"]),
                                    "volume": float(k["v"]),
                                    "open_time": float(k["t"]) / 1000.0,
                                    "is_closed": bool(k.get("x", False)),
                                    "source": self.name,
                                }
                            )
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_err = exc
                logger.warning("Binance WS host %s failed: %s", host, exc)
                await asyncio.sleep(1)
        raise RuntimeError(f"All Binance WS hosts failed: {last_err}")
