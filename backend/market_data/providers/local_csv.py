"""Offline dataset source.

Serves historical OHLCV from the locally stored CSV snapshots that ship with
the project. It is used only when every online provider fails — no internet, an
API outage, or a symbol a vendor does not cover — so the app can still show real
recorded prices and produce real predictions offline.

This source is deliberately NOT part of the live streaming chain: it never
emits ticks, so a stored close is never presented as a live price. Everything it
returns is labelled as a static OFFLINE snapshot, with the file it came from.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from .base import HistoryResult, MarketDataProvider

logger = logging.getLogger("provider.local")

# backend/market_data/providers/local_csv.py -> backend/data/offline
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "offline"

_QUOTES = ("USDT", "USDC", "BUSD", "FDUSD", "TUSD", "USD", "INR", "EUR", "GBP", "BTC", "ETH")
_COLUMNS = ["Timestamp", "Open", "High", "Low", "Close", "Volume"]
# Timeframes that can be rebuilt from daily bars.
_RESAMPLE_RULE = {"1w": "W-MON"}


def _norm(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


def _candidate_keys(*names: str) -> set:
    """Every spelling of a symbol that could name an offline CSV file."""
    keys = set()
    for name in names:
        n = _norm(name)
        if not n:
            continue
        keys.add(n)
        for quote in _QUOTES:
            if n.endswith(quote) and len(n) > len(quote):
                keys.add(n[: -len(quote)])
    return keys


class LocalCsvProvider(MarketDataProvider):
    """Read-only provider backed by the bundled offline datasets."""

    name = "offline-dataset"
    freshness = "OFFLINE"
    supports_stream = False

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self._index: Optional[Dict[str, Path]] = None
        self._cache: Dict[str, pd.DataFrame] = {}
        self.manifest: Dict[str, dict] = {}

    # -- index ---------------------------------------------------------------
    def available(self) -> bool:
        return bool(self._build_index())

    def _build_index(self) -> Dict[str, Path]:
        if self._index is not None:
            return self._index
        index: Dict[str, Path] = {}
        if self.data_dir.is_dir():
            for path in sorted(self.data_dir.glob("*.csv")):
                index.setdefault(_norm(path.stem), path)
            manifest_path = self.data_dir / "manifest.json"
            if manifest_path.exists():
                try:
                    loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        self.manifest = loaded
                except Exception as exc:  # pragma: no cover - non-fatal
                    logger.warning("Could not read offline manifest: %s", exc)
        self._index = index
        return index

    def _resolve(self, asset) -> Optional[Path]:
        index = self._build_index()
        if not index:
            return None
        keys = _candidate_keys(
            getattr(asset, "display", "") or "",
            getattr(asset, "yahoo_symbol", "") or "",
            getattr(asset, "input_symbol", "") or "",
        )
        for key in keys:
            if key in index:
                return index[key]
        return None

    # -- loading -------------------------------------------------------------
    def _load(self, path: Path) -> Optional[pd.DataFrame]:
        cache_key = str(path)
        if cache_key in self._cache:
            return self._cache[cache_key]
        try:
            df = pd.read_csv(path)
        except Exception as exc:
            logger.warning("Failed reading offline dataset %s: %s", path, exc)
            return None
        if "Timestamp" not in df.columns:
            logger.warning("Offline dataset %s has no Timestamp column.", path)
            return None
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], utc=True, errors="coerce")
        for col in ("Open", "High", "Low", "Close"):
            df[col] = pd.to_numeric(df.get(col), errors="coerce")
        df["Volume"] = pd.to_numeric(df.get("Volume", 0.0), errors="coerce").fillna(0.0)
        df = df[_COLUMNS].dropna(subset=["Timestamp", "Open", "High", "Low", "Close"])
        df = df.drop_duplicates(subset=["Timestamp"]).sort_values("Timestamp").reset_index(drop=True)
        self._cache[cache_key] = df
        return df

    @staticmethod
    def _resample(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        rule = _RESAMPLE_RULE[timeframe]
        return (
            df.set_index("Timestamp")
            .resample(rule)
            .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
            .dropna()
            .reset_index()
        )

    # -- MarketDataProvider --------------------------------------------------
    async def get_history(self, asset, timeframe: str, lookback_days: int) -> HistoryResult:
        path = self._resolve(asset)
        if path is None:
            return HistoryResult(
                status="ERROR",
                source=self.name,
                message=f"No offline dataset available for {getattr(asset, 'display', '')}.",
                timeframe=timeframe,
            )
        df = await asyncio.to_thread(self._load, path)
        if df is None or df.empty:
            return HistoryResult(
                status="ERROR",
                source=self.name,
                message=f"Offline dataset {path.name} could not be read.",
                timeframe=timeframe,
            )
        if timeframe in _RESAMPLE_RULE:
            df = await asyncio.to_thread(self._resample, df, timeframe)
        elif timeframe != "1d":
            return HistoryResult(
                status="ERROR",
                source=self.name,
                message=f"Offline dataset holds daily bars and cannot serve {timeframe}.",
                timeframe=timeframe,
            )
        if lookback_days:
            cutoff = df["Timestamp"].max() - pd.Timedelta(days=int(lookback_days))
            df = df[df["Timestamp"] >= cutoff].reset_index(drop=True)
        if len(df) < 2:
            return HistoryResult(
                status="INSUFFICIENT_DATA",
                source=self.name,
                message=f"Offline dataset for {getattr(asset, 'display', '')} has too few candles.",
                timeframe=timeframe,
            )
        return HistoryResult(
            status="SUCCESS",
            dataframe=df,
            source=f"Offline dataset ({path.name})",
            timeframe=timeframe,
        )

    async def get_latest_price(self, asset) -> Optional[float]:
        # Never present a stored close as a live price.
        return None
