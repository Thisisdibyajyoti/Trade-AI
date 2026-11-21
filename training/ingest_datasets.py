"""Ingest the bundled offline datasets into canonical OHLCV CSVs.

The three archives the project ships with use different column layouts and
file-naming schemes. This script normalizes all of them into one common shape:

    Timestamp,Open,High,Low,Close,Volume

written to ``backend/data/offline/<SYMBOL>.csv`` plus a ``manifest.json`` that
records, for every file, which archive it came from, its row count and its date
range. The backend's LocalCsvProvider reads exactly this folder, so this script
is the single bridge from raw downloads to a usable offline data source.

Usage:
    python training/ingest_datasets.py
    python training/ingest_datasets.py --raw datasets/raw --out backend/data/offline
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RAW = os.path.join(ROOT, "datasets", "raw")
DEFAULT_OUT = os.path.join(ROOT, "backend", "data", "offline")

COLUMNS = ["Timestamp", "Open", "High", "Low", "Close", "Volume"]

# Quote currencies stripped from a symbol so XRP-USDT and XRP share one file.
# Longer first so USDT/USDC are removed before the bare USD.
QUOTES = ("USDT", "USDC", "BUSD", "FDUSD", "TUSD", "USD", "INR", "EUR", "GBP")

# Archive a0 names its files coin_<FullName>.csv; map those names to tickers.
NAME_TO_TICKER = {
    "BITCOIN": "BTC", "ETHEREUM": "ETH", "SOLANA": "SOL", "XRP": "XRP",
    "CARDANO": "ADA", "CHAINLINK": "LINK", "COSMOS": "ATOM", "DOGECOIN": "DOGE",
    "EOS": "EOS", "IOTA": "IOTA", "LITECOIN": "LTC", "MONERO": "XMR",
    "NEM": "XEM", "POLKADOT": "DOT", "STELLAR": "XLM", "TETHER": "USDT",
    "TRON": "TRX", "USDCOIN": "USDC", "UNISWAP": "UNI", "WRAPPEDBITCOIN": "WBTC",
    "AAVE": "AAVE", "BINANCECOIN": "BNB", "CRYPTOCOMCOIN": "CRO",
}


def _norm(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


def _strip_quote(key: str) -> str:
    for quote in QUOTES:
        if key.endswith(quote) and len(key) > len(quote):
            return key[: -len(quote)]
    return key


def _find_column(columns, *candidates):
    lowered = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand in lowered:
            return lowered[cand]
    return None


def _find_volume_column(columns):
    for c in columns:
        if c.lower().startswith("volume"):
            return c
    return None


def _base_key(path: str, df: pd.DataFrame) -> str:
    """Derive the canonical ticker for a raw dataset file."""
    stem = os.path.splitext(os.path.basename(path))[0]
    if stem.lower().startswith("coin_"):
        name = _norm(stem[5:])
        return NAME_TO_TICKER.get(name, name)

    symbol_col = _find_column(df.columns, "symbol", "ticker")
    if symbol_col is not None:
        for value in df[symbol_col].dropna().astype(str):
            key = _norm(value)
            if key and len(key) <= 8:
                return _strip_quote(key)
    return _norm(stem)


def _to_timestamp(series: pd.Series) -> pd.Series:
    ts = pd.to_datetime(series, errors="coerce")
    if ts.isna().mean() > 0.5:
        ts = pd.to_datetime(series, errors="coerce", dayfirst=True)
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("UTC").dt.tz_localize(None)
    # Every archive is daily; snap to midnight so the same calendar day from two
    # different sources (one stamped 23:59:59, one at 00:00:00) collapses to one
    # candle instead of appearing twice.
    return ts.dt.normalize()


def normalize(path: str):
    """Return (key, canonical_frame) for one raw CSV, or None when unusable."""
    try:
        raw = pd.read_csv(path, low_memory=False)
    except Exception:
        return None
    if raw.empty or len(raw.columns) < 4:
        return None

    ts_col = _find_column(raw.columns, "timestamp", "date", "datetime", "unix")
    o = _find_column(raw.columns, "open")
    h = _find_column(raw.columns, "high")
    low = _find_column(raw.columns, "low")
    c = _find_column(raw.columns, "close")
    if not all((ts_col, o, h, low, c)):
        return None

    vol_col = _find_volume_column(raw.columns)
    frame = pd.DataFrame(
        {
            "Timestamp": _to_timestamp(raw[ts_col]),
            "Open": pd.to_numeric(raw[o], errors="coerce"),
            "High": pd.to_numeric(raw[h], errors="coerce"),
            "Low": pd.to_numeric(raw[low], errors="coerce"),
            "Close": pd.to_numeric(raw[c], errors="coerce"),
            "Volume": pd.to_numeric(raw[vol_col], errors="coerce") if vol_col else 0.0,
        }
    )
    frame["Volume"] = frame["Volume"].fillna(0.0)
    frame = frame.dropna(subset=["Timestamp", "Open", "High", "Low", "Close"])
    if frame.empty:
        return None
    frame = (
        frame.drop_duplicates(subset=["Timestamp"])
        .sort_values("Timestamp")
        .reset_index(drop=True)
    )
    return _base_key(path, raw), frame


def collect(raw_dir: str):
    """Normalize every CSV under raw_dir, grouped by canonical ticker."""
    groups: dict[str, list[tuple[str, pd.DataFrame]]] = {}
    for root, _dirs, files in os.walk(raw_dir):
        for name in sorted(files):
            if not name.lower().endswith(".csv"):
                continue
            path = os.path.join(root, name)
            parsed = normalize(path)
            if parsed is None:
                print(f"  skip (unrecognized): {os.path.relpath(path, raw_dir)}")
                continue
            key, frame = parsed
            groups.setdefault(key, []).append((os.path.relpath(path, raw_dir), frame))
    return groups


def merge_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Union frames, preferring rows that carry real volume data."""
    ordered = sorted(frames, key=lambda f: ((f["Volume"] > 0).any(), len(f)), reverse=True)
    merged = pd.concat(ordered, ignore_index=True).sort_values("Timestamp", kind="mergesort")
    merged = merged.drop_duplicates(subset=["Timestamp"], keep="first")
    return merged.reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize offline datasets for TradeAI")
    parser.add_argument("--raw", default=DEFAULT_RAW, help="Directory of raw extracted datasets")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output directory for canonical CSVs")
    args = parser.parse_args()

    if not os.path.isdir(args.raw):
        print(f"Raw dataset directory not found: {args.raw}")
        return 1

    os.makedirs(args.out, exist_ok=True)
    # Rebuild from scratch so renamed/removed symbols do not leave stale files.
    for stale in os.listdir(args.out):
        if stale.lower().endswith(".csv"):
            os.remove(os.path.join(args.out, stale))
    groups = collect(args.raw)
    print(f"\nFound {len(groups)} distinct symbols across {args.raw}")

    manifest = {}
    written = 0
    for key, entries in sorted(groups.items()):
        frame = merge_frames([f for _src, f in entries])
        if len(frame) < 10:
            continue
        out_path = os.path.join(args.out, f"{key}.csv")
        frame.to_csv(out_path, index=False)
        written += 1
        manifest[key] = {
            "file": f"{key}.csv",
            "rows": int(len(frame)),
            "start": frame["Timestamp"].min().strftime("%Y-%m-%d"),
            "end": frame["Timestamp"].max().strftime("%Y-%m-%d"),
            "has_volume": bool((frame["Volume"] > 0).any()),
            "sources": [src for src, _f in entries],
        }

    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)

    print(f"Wrote {written} canonical CSVs + manifest.json to {args.out}")
    sample = list(sorted(manifest.items()))[:8]
    for key, meta in sample:
        print(f"  {key:8s} {meta['rows']:>6d} rows  {meta['start']}..{meta['end']}  vol={meta['has_volume']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
