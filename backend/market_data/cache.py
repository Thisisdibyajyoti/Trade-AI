"""Disk cache for historical OHLCV bars.

Avoids refetching years of data every time an asset is reopened. Keyed by
provider + symbol + timeframe, stored as pickle under backend/.cache.
"""

from __future__ import annotations

import hashlib
import logging
import pickle
import time
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger("history_cache")

_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _key(provider: str, symbol: str, timeframe: str) -> Path:
    digest = hashlib.sha1(f"{provider}|{symbol}|{timeframe}".encode()).hexdigest()[:16]
    return _CACHE_DIR / f"{provider}_{symbol.replace('/', '_')}_{timeframe}_{digest}.pkl"


def load(provider: str, symbol: str, timeframe: str, ttl_seconds: float) -> Optional[pd.DataFrame]:
    path = _key(provider, symbol, timeframe)
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > ttl_seconds:
        return None
    try:
        with path.open("rb") as fh:
            return pickle.load(fh)
    except Exception as exc:  # corrupt cache should never break the app
        logger.warning("Cache read failed for %s: %s", path.name, exc)
        return None


def save(provider: str, symbol: str, timeframe: str, df: pd.DataFrame) -> None:
    if df is None or df.empty:
        return
    path = _key(provider, symbol, timeframe)
    try:
        with path.open("wb") as fh:
            pickle.dump(df, fh)
    except Exception as exc:
        logger.warning("Cache write failed for %s: %s", path.name, exc)
