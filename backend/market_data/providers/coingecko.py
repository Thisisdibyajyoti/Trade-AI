"""CoinGecko source — crypto REST fallback and the searchable coin list.

Used for (a) last-resort crypto price polling when Binance is unreachable and
(b) the Target Scanner's coin search surface, so the UI renders real DOM rows
built from live data rather than a hard-coded catalog.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx
import pandas as pd

from .base import HistoryResult, MarketDataProvider

logger = logging.getLogger("provider.coingecko")

BASE = "https://api.coingecko.com/api/v3"

# Registry base token -> CoinGecko id
COINGECKO_IDS = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "ADA": "cardano",
    "DOGE": "dogecoin", "XRP": "ripple", "BNB": "binancecoin", "AVAX": "avalanche-2",
    "DOT": "polkadot", "LINK": "chainlink", "LTC": "litecoin", "MATIC": "matic-network",
    "POL": "polygon-ecosystem-token", "TRX": "tron", "SHIB": "shiba-inu",
    "UNI": "uniswap", "ATOM": "cosmos", "ETC": "ethereum-classic", "FIL": "filecoin",
    "APT": "aptos", "ARB": "arbitrum", "OP": "optimism", "NEAR": "near",
    "INJ": "injective-protocol",
}


def _coingecko_id(asset) -> Optional[str]:
    base = asset.display.split("/")[0].upper()
    return COINGECKO_IDS.get(base)


class CoinGeckoProvider(MarketDataProvider):
    name = "coingecko"
    freshness = "DELAYED"
    supports_stream = False

    async def get_history(self, asset, timeframe: str, lookback_days: int) -> HistoryResult:
        cid = _coingecko_id(asset)
        if not cid:
            return HistoryResult(status="ERROR", source="CoinGecko", message="Unknown CoinGecko id")
        days = max(1, min(365, lookback_days))
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{BASE}/coins/{cid}/ohlc",
                    params={"vs_currency": "usd", "days": days},
                )
                resp.raise_for_status()
                rows = resp.json()
        except Exception as exc:
            return HistoryResult(status="ERROR", source="CoinGecko", message=str(exc))
        if not rows:
            return HistoryResult(status="ERROR", source="CoinGecko", message="No CoinGecko OHLC")
        df = pd.DataFrame(rows, columns=["ts", "Open", "High", "Low", "Close"])
        df["Timestamp"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
        df["Volume"] = 0.0
        df = df[["Timestamp", "Open", "High", "Low", "Close", "Volume"]]
        return HistoryResult(status="SUCCESS", dataframe=df, source="CoinGecko", timeframe=timeframe)

    async def get_latest_price(self, asset) -> Optional[float]:
        cid = _coingecko_id(asset)
        if not cid:
            return None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{BASE}/simple/price",
                    params={"ids": cid, "vs_currencies": "usd"},
                )
                resp.raise_for_status()
                data = resp.json()
                return float(data[cid]["usd"])
        except Exception as exc:
            logger.warning("CoinGecko price failed: %s", exc)
            return None


async def fetch_crypto_market_list(limit: int = 60) -> list[dict]:
    """
    Return a real, live crypto market list for the Target Scanner.
    Every field comes straight from CoinGecko's public markets endpoint.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{BASE}/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": limit,
                    "page": 1,
                    "sparkline": "false",
                    "price_change_percentage": "7d,30d",
                },
            )
            resp.raise_for_status()
            rows = resp.json()
    except Exception as exc:
        logger.warning("CoinGecko markets list failed: %s", exc)
        return []

    out: list[dict] = []
    for row in rows:
        sym = (row.get("symbol") or "").upper()
        out.append(
            {
                "id": row.get("id"),
                "name": row.get("name"),
                "symbol": sym,
                "ticker": sym,
                "trade_symbol": f"{sym}/USDT",
                "price": row.get("current_price"),
                "market_cap": row.get("market_cap"),
                "rank": row.get("market_cap_rank"),
                "change_7d": row.get("price_change_percentage_7d_in_currency"),
                "change_30d": row.get("price_change_percentage_30d_in_currency"),
                "image": row.get("image"),
                "as_of": time.time(),
            }
        )
    return out
