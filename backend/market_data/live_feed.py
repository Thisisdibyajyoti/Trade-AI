"""Live feed manager.

One shared upstream connection per instrument, fanned out to every connected
browser. Handles backfill-then-stream, tick validation, auto-reconnect with
exponential backoff, staleness detection and market-hours awareness.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List, Optional, Set, Tuple

from .candle_builder import TIMEFRAME_SECONDS, CandleBuilder
from .providers.base import MarketDataProvider
from .providers.binance import BinanceProvider
from .providers.coingecko import CoinGeckoProvider
from .providers.finnhub import FinnhubProvider
from .providers.local_csv import LocalCsvProvider
from .providers.yahoo import YahooProvider
from .symbols import AssetInfo, is_market_open

logger = logging.getLogger("live_feed")

# Lookback window fetched per timeframe for chart backfill.
LOOKBACK_DAYS = {
    "1m": 3, "5m": 10, "15m": 30, "30m": 60,
    "1h": 180, "4h": 400, "1d": 3650, "1w": 3650,
}

ALL_TIMEFRAMES = list(TIMEFRAME_SECONDS.keys())

# Wall-clock seconds without a tick before a feed is considered STALE.
STALE_SECONDS = {"crypto": 30.0, "default": 120.0}

FLUSH_INTERVAL = 0.25          # UI update throttle (~4 per second)
MIN_TICK_INTERVAL_GUARD = 0.0  # accept every tick, validated below
MAX_TICK_JUMP = 0.20           # 20% single-tick move requires confirmation

_PROVIDERS: Dict[str, MarketDataProvider] = {
    "binance": BinanceProvider(),
    "yfinance": YahooProvider(),
    "finnhub": FinnhubProvider(),
    "coingecko": CoinGeckoProvider(),
    # Offline fallback: used for history only, never for streaming.
    "local": LocalCsvProvider(),
}

# Providers whose bars are a stored snapshot rather than a live/streamed feed.
OFFLINE_SOURCES = ("Offline dataset",)


def is_offline_source(source: str) -> bool:
    return bool(source) and source.startswith(OFFLINE_SOURCES)


def provider_chain(asset: AssetInfo) -> List[MarketDataProvider]:
    """Ordered list of providers able to serve this asset right now."""
    chain: List[MarketDataProvider] = []
    for name in asset.live_providers:
        provider = _PROVIDERS.get(name)
        if provider is None:
            continue
        available = getattr(provider, "available", None)
        if callable(available) and not available():
            continue
        chain.append(provider)
    yahoo = _PROVIDERS["yfinance"]
    if yahoo not in chain:
        chain.append(yahoo)
    return chain


async def fetch_history(asset: AssetInfo, timeframe: str, days: Optional[int] = None):
    """Fetch historical OHLCV, trying each provider in priority order."""
    from .providers.base import HistoryResult

    days = days or LOOKBACK_DAYS.get(timeframe, 365)
    last: HistoryResult = HistoryResult(status="ERROR", message="No provider returned data")
    for provider in provider_chain(asset):
        result = await provider.get_history(asset, timeframe, days)
        if result.status == "SUCCESS" and result.dataframe is not None:
            return result
        last = result
    # Last resort: the bundled offline datasets (a static snapshot, not live).
    offline = await _offline_history(asset, timeframe, days)
    return offline or last


async def _offline_history(asset: AssetInfo, timeframe: str, days: int):
    """Try the offline dataset provider, or return None when unavailable."""
    local = _PROVIDERS["local"]
    available = getattr(local, "available", None)
    if callable(available) and not available():
        return None
    result = await local.get_history(asset, timeframe, days)
    if result.status == "SUCCESS" and result.dataframe is not None:
        logger.info(
            "Serving %s %s from offline dataset: %d candles",
            asset.display, timeframe, len(result.dataframe),
        )
        return result
    return None


class LiveFeed:
    """Shared upstream feed for a single instrument."""

    def __init__(self, asset: AssetInfo):
        self.asset = asset
        self.builder = CandleBuilder(ALL_TIMEFRAMES)
        self.subscribers: Set[asyncio.Queue] = set()
        self.active_timeframes: Set[str] = set()

        self.mode: str = "CONNECTING"   # LIVE | DELAYED | CLOSED | STALE | OFFLINE | RECONNECTING
        self.source: str = ""
        self.offline: bool = False      # history came from a stored offline dataset
        self.last_tick_ts: Optional[float] = None
        self.last_price: Optional[float] = None
        self.last_message: str = ""
        self.latency_ms: Optional[float] = None
        self.rejected_ticks: int = 0

        self._task: Optional[asyncio.Task] = None
        self._flusher: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._backfill_lock = asyncio.Lock()
        self._prediction_lock = asyncio.Lock()
        self._prediction_pending: Set[str] = set()
        self._last_prediction_ts: Dict[str, float] = {}
        self._backtest_cache: Dict[str, dict] = {}
        self._prune_at = time.time() + 90
        self._pending_confirm: List[float] = []   # prices awaiting jump confirmation

    # -- lifecycle -----------------------------------------------------------
    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._supervisor(), name=f"feed-{self.asset.display}")
            self._flusher = asyncio.create_task(self._flush_loop(), name=f"flush-{self.asset.display}")

    def stop(self) -> None:
        self._stop.set()
        for task in (self._task, self._flusher):
            if task and not task.done():
                task.cancel()

    # -- subscription --------------------------------------------------------
    async def subscribe(self, timeframe: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self.subscribers.add(queue)
        timeframe = timeframe if timeframe in TIMEFRAME_SECONDS else "1d"
        self.active_timeframes.add(timeframe)
        self.start()
        await self._ensure_history(timeframe)

        # Seed the client with closed history + feed status immediately.
        await queue.put(self._history_message(timeframe))
        await queue.put(self._status_message())
        # Kick off an initial prediction for this timeframe.
        self._schedule_prediction(timeframe)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self.subscribers.discard(queue)
        if not self.subscribers:
            # Keep the feed warm briefly; the manager prunes idle feeds.
            self._prune_at = time.time() + 90

    async def change_timeframe(self, queue: asyncio.Queue, timeframe: str) -> None:
        """Switch an existing subscriber to another timeframe in place."""
        timeframe = timeframe if timeframe in TIMEFRAME_SECONDS else "1d"
        self.active_timeframes.add(timeframe)
        await self._ensure_history(timeframe)
        await queue.put(self._history_message(timeframe))
        self._schedule_prediction(timeframe)

    @property
    def idle(self) -> bool:
        return not self.subscribers and time.time() > self._prune_at

    # -- provider selection --------------------------------------------------
    def _provider_chain(self) -> List[MarketDataProvider]:
        return provider_chain(self.asset)

    @property
    def _stale_threshold(self) -> float:
        return STALE_SECONDS["crypto"] if self.asset.asset_class == "crypto" else STALE_SECONDS["default"]

    # -- backfill ------------------------------------------------------------
    async def _ensure_history(self, timeframe: str) -> None:
        if self.builder.has_history(timeframe):
            return
        async with self._backfill_lock:
            if self.builder.has_history(timeframe):
                return
            days = LOOKBACK_DAYS.get(timeframe, 365)
            for provider in self._provider_chain():
                result = await provider.get_history(self.asset, timeframe, days)
                if result.status == "SUCCESS" and result.dataframe is not None:
                    self.builder.seed(timeframe, result.dataframe)
                    self.source = provider.name
                    logger.info(
                        "Backfilled %s %s: %d candles from %s",
                        self.asset.display, timeframe, len(result.dataframe), provider.name,
                    )
                    return
            # Offline dataset fallback (static snapshot; never streamed).
            offline = await _offline_history(self.asset, timeframe, days)
            if offline is not None:
                self.builder.seed(timeframe, offline.dataframe)
                self.source = "offline dataset"
                self.offline = True
                self.last_message = (
                    f"No live feed available — showing the stored offline dataset "
                    f"({len(offline.dataframe)} candles)."
                )
                return
            self.last_message = f"No historical data available for {self.asset.display} ({timeframe})."

    # -- supervisor / streaming ---------------------------------------------
    async def _supervisor(self) -> None:
        chain = self._provider_chain()
        index = 0
        failures = 0
        while not self._stop.is_set():
            # Outside market hours, do not stream fake movement.
            if not is_market_open(self.asset):
                self._set_mode("CLOSED", source=self.source or chain[0].name)
                await asyncio.sleep(20)
                continue

            provider = chain[index % len(chain)]
            try:
                self._set_mode("RECONNECTING" if failures else "LIVE", source=provider.name)
                self.last_message = f"Streaming from {provider.name}"
                await provider.stream(self.asset, self._on_event, poll_interval=15.0)
                failures = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                failures += 1
                # Exponential backoff: 1s, 2s, 4s, 8s, 16s, capped at 30s.
                backoff = min(30.0, float(2 ** min(failures - 1, 5)))
                self._set_mode("RECONNECTING", source=provider.name)
                self.last_message = (
                    f"{provider.name} stream dropped ({exc}). Reconnecting in {backoff:.0f}s."
                )
                logger.warning("Feed %s: %s", self.asset.display, self.last_message)
                # After several failures, fall back to the next provider.
                if failures >= 4 and len(chain) > 1:
                    index += 1
                    failures = 0
                    if provider.freshness == "LIVE":
                        self._set_mode("DELAYED", source=chain[index % len(chain)].name)
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                    return
                except asyncio.TimeoutError:
                    continue
            await asyncio.sleep(0.5)

    # -- tick validation -----------------------------------------------------
    def _validate_tick(self, price: float, ts: float) -> bool:
        if price is None or price <= 0:
            self.rejected_ticks += 1
            return False
        if ts is not None and self.last_tick_ts is not None and ts < self.last_tick_ts - 5:
            self.rejected_ticks += 1  # out-of-order timestamp
            return False
        if self.last_price:
            jump = abs(price - self.last_price) / self.last_price
            if jump > MAX_TICK_JUMP:
                # Require a second agreeing print before accepting a huge move.
                if self._pending_confirm and abs(price - self._pending_confirm[-1]) / self._pending_confirm[-1] <= MAX_TICK_JUMP:
                    self._pending_confirm.clear()
                    return True
                self._pending_confirm.append(price)
                self.rejected_ticks += 1
                logger.warning(
                    "Rejected suspicious tick for %s: %.4f -> %.4f (%.1f%%)",
                    self.asset.display, self.last_price, price, jump * 100,
                )
                return False
        return True

    # -- event ingestion -----------------------------------------------------
    async def _on_event(self, event: dict) -> None:
        etype = event.get("type")
        if etype == "tick":
            price = event.get("price")
            ts = float(event.get("ts") or time.time())
            if not self._validate_tick(float(price), ts):
                return
            self.last_price = float(price)
            self.last_tick_ts = ts
            self.latency_ms = round((time.time() - ts) * 1000, 1) if ts else None
            updates = self.builder.on_tick(float(price), float(event.get("volume") or 0.0), ts)
            for tf, candle, is_closed in updates:
                if is_closed:
                    self._broadcast(
                        {"type": "candle", "timeframe": tf, "candle": candle, "is_closed": True}
                    )
                    if tf in self.active_timeframes:
                        self._schedule_prediction(tf)
        elif etype == "kline":
            # Provider-native kline: use only for the forming 1m candle value.
            if event.get("is_closed"):
                self._broadcast(
                    {
                        "type": "candle",
                        "timeframe": event.get("interval", "1m"),
                        "candle": {
                            "time": float(event["open_time"]),
                            "open": float(event["open"]),
                            "high": float(event["high"]),
                            "low": float(event["low"]),
                            "close": float(event["close"]),
                            "volume": float(event["volume"]),
                            "is_closed": True,
                        },
                        "is_closed": True,
                    }
                )

    # -- broadcasting --------------------------------------------------------
    def _broadcast(self, message: dict) -> None:
        for queue in list(self.subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                pass

    def _set_mode(self, mode: str, source: Optional[str] = None) -> None:
        if mode != self.mode or (source and source != self.source):
            self.mode = mode
            if source:
                self.source = source
            self._broadcast(self._status_message())

    def _history_message(self, timeframe: str) -> dict:
        candles = self.builder.snapshot(timeframe, limit=500)
        return {
            "type": "history",
            "timeframe": timeframe,
            "symbol": self.asset.display,
            "candles": candles,
            "closed_count": len(self.builder.closed_candles(timeframe)),
        }

    def _status_message(self) -> dict:
        mode = self.mode
        # Offline: history came from a stored dataset and no live tick has
        # arrived, so nothing here is live — say so plainly.
        if self.offline and self.last_tick_ts is None:
            mode = "OFFLINE"
        # Staleness overrides an otherwise "live" feed.
        elif (
            mode in ("LIVE", "DELAYED")
            and is_market_open(self.asset)
            and self.last_tick_ts is not None
            and (time.time() - self.last_tick_ts) > self._stale_threshold
        ):
            mode = "STALE"
        age = None if self.last_tick_ts is None else round(time.time() - self.last_tick_ts, 1)
        return {
            "type": "feed_status",
            "symbol": self.asset.display,
            "asset_class": self.asset.asset_class,
            "mode": mode,
            "source": self.source,
            "market_open": is_market_open(self.asset),
            "last_tick": self.last_tick_ts,
            "last_price": self.last_price,
            "age_seconds": age,
            "latency_ms": self.latency_ms,
            "rejected_ticks": self.rejected_ticks,
            "message": self.last_message,
            "server_time": time.time(),
        }

    async def _flush_loop(self) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(FLUSH_INTERVAL)
            if not self.subscribers:
                continue
            snapshot = {
                "type": "snapshot",
                "price": self.last_price,
                "ts": self.last_tick_ts,
                "forming": {},
                "mode": self.mode,
            }
            for tf in self.active_timeframes:
                forming = self.builder.forming.get(tf)
                if forming:
                    snapshot["forming"][tf] = forming
            self._broadcast(snapshot)
            # Periodic status refresh so the badge "last update: Ns ago" ticks.
            if int(time.time() * 4) % 8 == 0:
                self._broadcast(self._status_message())

    # -- prediction refresh (on candle close) --------------------------------
    def _schedule_prediction(self, timeframe: str) -> None:
        self._prediction_pending.add(timeframe)
        asyncio.create_task(self._prediction_worker())

    async def _prediction_worker(self) -> None:
        if self._prediction_lock.locked():
            return
        async with self._prediction_lock:
            while self._prediction_pending:
                timeframe = self._prediction_pending.pop()
                last = self._last_prediction_ts.get(timeframe, 0)
                if time.time() - last < 3.0:
                    continue
                await self._compute_prediction(timeframe)

    async def _compute_prediction(self, timeframe: str) -> None:
        from services.analysis_service import run_full_analysis

        closed = self.builder.closed_candles(timeframe)
        if len(closed) < 60:
            self._broadcast(
                {
                    "type": "prediction",
                    "timeframe": timeframe,
                    "status": "UNAVAILABLE",
                    "message": f"Only {len(closed)} closed candles available; need at least 60.",
                }
            )
            return
        import pandas as pd

        df = pd.DataFrame(
            [
                {
                    "Timestamp": pd.Timestamp(c["time"], unit="s", tz="UTC"),
                    "Open": c["open"], "High": c["high"], "Low": c["low"],
                    "Close": c["close"], "Volume": c["volume"],
                }
                for c in closed[-1500:]
            ]
        )
        self._last_prediction_ts[timeframe] = time.time()
        try:
            result = await asyncio.to_thread(
                run_full_analysis,
                df,
                {
                    "symbol": self.asset.display,
                    "resolved_symbol": self.asset.yahoo_symbol,
                    "data_source": f"{self.source or 'live feed'} (live closed candles)",
                    "timeframe": timeframe,
                },
                None,
                True,
                self._backtest_cache.get(timeframe),
            )
        except Exception as exc:  # never let a model error kill the feed
            logger.exception("Prediction failed for %s %s", self.asset.display, timeframe)
            result = {"status": "ERROR", "message": f"Prediction failed: {exc}"}
        # Cache a freshly computed walk-forward result so subsequent candle
        # closes reuse it instead of retraining the backtest every minute.
        if result.get("status") == "SUCCESS" and result.get("backtest", {}).get("status") == "SUCCESS":
            self._backtest_cache[timeframe] = result["backtest"]
        result.update(
            {
                "type": "prediction",
                "timeframe": timeframe,
                "interval": timeframe,
                "feed_mode": self.mode,
                "feed_source": self.source,
                "as_of": time.time(),
            }
        )
        self._broadcast(result)


class LiveFeedManager:
    """Process-wide registry of live feeds, shared across all clients."""

    def __init__(self) -> None:
        self._feeds: Dict[str, LiveFeed] = {}
        self._lock = asyncio.Lock()
        self._pruner: Optional[asyncio.Task] = None

    def _key(self, asset: AssetInfo) -> str:
        return f"{asset.asset_class}:{asset.display}"

    async def get_feed(self, asset: AssetInfo) -> LiveFeed:
        async with self._lock:
            key = self._key(asset)
            feed = self._feeds.get(key)
            if feed is None:
                feed = LiveFeed(asset)
                self._feeds[key] = feed
            if self._pruner is None or self._pruner.done():
                self._pruner = asyncio.create_task(self._prune_loop())
            return feed

    def peek(self, asset: AssetInfo) -> Optional[LiveFeed]:
        return self._feeds.get(self._key(asset))

    async def _prune_loop(self) -> None:
        while True:
            await asyncio.sleep(60)
            for key, feed in list(self._feeds.items()):
                if feed.idle:
                    feed.stop()
                    self._feeds.pop(key, None)

    async def shutdown(self) -> None:
        for feed in list(self._feeds.values()):
            feed.stop()
        self._feeds.clear()
        if self._pruner and not self._pruner.done():
            self._pruner.cancel()


manager = LiveFeedManager()
