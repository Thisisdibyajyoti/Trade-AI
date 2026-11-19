"""
Generate training CSV dataset for TradeAI models.
Fetches real historical OHLCV data from Yahoo Finance and saves it to training/data/.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yfinance as yf
import pandas as pd
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("generate_training_data")

# All assets to fetch training data for
ASSETS = {
    "BTC-USD":       {"name": "Bitcoin",          "category": "Crypto"},
    "ETH-USD":       {"name": "Ethereum",         "category": "Crypto"},
    "AAPL":          {"name": "Apple",            "category": "US Stock"},
    "TSLA":          {"name": "Tesla",            "category": "US Stock"},
    "NVDA":          {"name": "NVIDIA",           "category": "US Stock"},
    "MSFT":          {"name": "Microsoft",        "category": "US Stock"},
    "GOOGL":         {"name": "Alphabet",         "category": "US Stock"},
    "AMZN":          {"name": "Amazon",           "category": "US Stock"},
    "SPY":           {"name": "S&P 500 ETF",      "category": "US ETF"},
    "RELIANCE.NS":   {"name": "Reliance",         "category": "Indian Stock"},
    "TCS.NS":        {"name": "TCS",              "category": "Indian Stock"},
    "^NSEI":         {"name": "Nifty 50",         "category": "Indian Index"},
}

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def fetch_and_save(ticker_symbol: str, meta: dict, period: str = "10y", interval: str = "1d"):
    """Fetch historical data from Yahoo Finance and save as CSV."""
    logger.info(f"Fetching {ticker_symbol} ({meta['name']})...")

    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period=period, interval=interval, auto_adjust=True)

        if df.empty or len(df) < 30:
            logger.warning(f"  ⚠ Insufficient data for {ticker_symbol} ({len(df)} rows), skipping.")
            return None

        df = df.reset_index()

        # Normalize the date column name
        date_col = 'Date' if 'Date' in df.columns else ('Datetime' if 'Datetime' in df.columns else df.columns[0])
        df.rename(columns={date_col: 'Timestamp'}, inplace=True)

        # Keep only OHLCV columns
        df = df[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']].copy()
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])

        # Round prices to reasonable precision
        for col in ['Open', 'High', 'Low', 'Close']:
            df[col] = df[col].round(4)
        df['Volume'] = df['Volume'].astype(int)

        # Save
        safe_name = ticker_symbol.replace("/", "_").replace("^", "IDX_").replace(".", "_")
        csv_path = os.path.join(OUTPUT_DIR, f"{safe_name}_daily.csv")
        df.to_csv(csv_path, index=False)

        min_date = df['Timestamp'].min().strftime('%Y-%m-%d')
        max_date = df['Timestamp'].max().strftime('%Y-%m-%d')
        years = round((df['Timestamp'].max() - df['Timestamp'].min()).days / 365.25, 1)

        logger.info(f"  ✓ {ticker_symbol}: {len(df)} candles | {min_date} → {max_date} ({years} yrs) → {csv_path}")
        return {
            "ticker": ticker_symbol,
            "name": meta["name"],
            "category": meta["category"],
            "candles": len(df),
            "period": f"{min_date} to {max_date}",
            "years": years,
            "file": csv_path
        }

    except Exception as e:
        logger.error(f"  ✗ Failed to fetch {ticker_symbol}: {e}")
        return None


def generate_combined_csv(all_results: list):
    """Also create one combined CSV with a 'Symbol' column for multi-asset training."""
    frames = []
    for res in all_results:
        if res is None:
            continue
        df = pd.read_csv(res["file"])
        df.insert(0, "Symbol", res["ticker"])
        frames.append(df)

    if frames:
        combined = pd.concat(frames, ignore_index=True)
        combined_path = os.path.join(OUTPUT_DIR, "all_assets_daily.csv")
        combined.to_csv(combined_path, index=False)
        logger.info(f"\n✓ Combined dataset: {len(combined)} total rows → {combined_path}")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    logger.info(f"Output directory: {OUTPUT_DIR}")
    logger.info(f"Fetching training data for {len(ASSETS)} assets...\n")

    results = []
    for ticker, meta in ASSETS.items():
        result = fetch_and_save(ticker, meta)
        results.append(result)

    # Generate combined multi-asset CSV
    generate_combined_csv(results)

    # Print summary
    successful = [r for r in results if r is not None]
    logger.info(f"\n{'='*60}")
    logger.info(f"Training data generation complete!")
    logger.info(f"  Assets fetched: {len(successful)}/{len(ASSETS)}")
    logger.info(f"  Output: {OUTPUT_DIR}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    main()
