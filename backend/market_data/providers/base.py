"""Provider abstraction for real market data.

Every data source (Binance, Yahoo, Finnhub, ...) implements `MarketDataProvider`
so the rest of the application — models, APIs, UI — never talks to a vendor
directly. Swapping a source therefore requires no changes elsewhere.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

import pandas as pd

# An event emitted by a live provider.
#   {"type": "tick",  "price": float, "volume": float, "ts": float, "source": str}
#   {"type": "kline", "interval": str, "open": float, "high": float, "low": float,
#    "close": float, "volume": float, "open_time": float, "is_closed": bool}
EmitFn = Callable[[dict], Awaitable[None]]


@dataclass
class HistoryResult:
    """Result of a historical fetch, with honest provenance."""

    status: str                 # SUCCESS | INSUFFICIENT_DATA | ERROR
    dataframe: Optional[pd.DataFrame] = None
    source: str = ""
    message: str = ""
    timeframe: str = "1d"


class MarketDataProvider(abc.ABC):
    """Interface implemented by every market-data source."""

    name: str = "base"
    # Freshness label this source can honestly claim when the market is open.
    freshness: str = "DELAYED"
    supports_stream: bool = False

    @abc.abstractmethod
    async def get_history(self, asset, timeframe: str, lookback_days: int) -> HistoryResult:
        """Return OHLCV bars with a UTC `Timestamp` column."""

    @abc.abstractmethod
    async def get_latest_price(self, asset) -> Optional[float]:
        """Return the most recent price available from this source."""

    async def stream(self, asset, emit: EmitFn, poll_interval: float = 15.0) -> None:
        """
        Run until cancelled, calling `emit` with tick/kline events.

        Streaming providers override this to use a websocket; polling
        providers rely on the default implementation below.
        """
        import asyncio

        while True:
            price = await self.get_latest_price(asset)
            if price is not None:
                import time

                await emit(
                    {
                        "type": "tick",
                        "price": float(price),
                        "volume": 0.0,
                        "ts": time.time(),
                        "source": self.name,
                    }
                )
            await asyncio.sleep(poll_interval)

    async def aclose(self) -> None:  # pragma: no cover - trivial
        return None

    def status(self) -> dict:
        return {"provider": self.name, "freshness": self.freshness, "healthy": True}
