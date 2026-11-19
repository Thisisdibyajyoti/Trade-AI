import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("market_data_fetcher")

SYMBOL_MAP = {
    # Indian Equities & Indices
    "RELIANCE": "RELIANCE.NS",
    "RELIANCE.NS": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "TCS.NS": "TCS.NS",
    "NIFTY 50": "^NSEI",
    "NIFTY": "^NSEI",
    "^NSEI": "^NSEI",
    "BANK NIFTY": "^NSEBANK",
    "BANKNIFTY": "^NSEBANK",
    "^NSEBANK": "^NSEBANK",
    
    # Crypto (tickers + common search names)
    "BTC/USDT": "BTC-USD",
    "BTCUSDT": "BTC-USD",
    "BTC-USD": "BTC-USD",
    "BTC": "BTC-USD",
    "BITCOIN": "BTC-USD",
    "ETH/USDT": "ETH-USD",
    "ETHUSDT": "ETH-USD",
    "ETH-USD": "ETH-USD",
    "ETH": "ETH-USD",
    "ETHEREUM": "ETH-USD",
    "SOL": "SOL-USD",
    "SOL-USD": "SOL-USD",
    "SOLANA": "SOL-USD",
    "ADA": "ADA-USD",
    "ADA-USD": "ADA-USD",
    "CARDANO": "ADA-USD",
    "DOGE": "DOGE-USD",
    "DOGE-USD": "DOGE-USD",
    "DOGECOIN": "DOGE-USD",
    "XRP": "XRP-USD",
    "XRP-USD": "XRP-USD",
    "RIPPLE": "XRP-USD",
    "BNB": "BNB-USD",
    "BNB-USD": "BNB-USD",
    "AVAX": "AVAX-USD",
    "AVAX-USD": "AVAX-USD",
    "AVALANCHE": "AVAX-USD",
    "DOT": "DOT-USD",
    "DOT-USD": "DOT-USD",
    "POLKADOT": "DOT-USD",
    "LINK": "LINK-USD",
    "LINK-USD": "LINK-USD",
    "CHAINLINK": "LINK-USD",
    "LTC": "LTC-USD",
    "LTC-USD": "LTC-USD",
    "LITECOIN": "LTC-USD",
    "MATIC": "MATIC-USD",
    "MATIC-USD": "MATIC-USD",
    "POLYGON": "MATIC-USD",
    
    # US Equities
    "AAPL": "AAPL",
    "TSLA": "TSLA",
    "NVDA": "NVDA",
    "MSFT": "MSFT",
    "GOOGL": "GOOGL",
    "AMZN": "AMZN",
    "SPY": "SPY",
    "QQQ": "QQQ"
}

def resolve_symbol(ticker_input: str) -> str | None:
    """
    Verifies and maps input trading symbol to legitimate data feed symbol.
    """
    if not ticker_input:
        return None
    
    clean = ticker_input.strip().upper()
    if clean in SYMBOL_MAP:
        return SYMBOL_MAP[clean]
    
    # Check if directly valid yfinance symbol
    if clean.endswith(".NS") or clean.endswith(".BO") or clean.startswith("^"):
        return clean
        
    # Standard 1-5 letter US ticker fallback test
    if len(clean) <= 6 and clean.isalpha():
        return clean
        
    return None

def fetch_historical_data(symbol_input: str, timeframe: str = "1d", max_years: int = 10) -> dict:
    """
    Fetches up to `max_years` of historical market data from official data feeds.
    Strictly reports actual available period and candle counts.
    """
    resolved_symbol = resolve_symbol(symbol_input)
    if not resolved_symbol:
        return {
            "status": "UNIDENTIFIED",
            "message": "Unable to reliably identify the trading instrument. Please select the asset manually.",
            "data": None
        }
    
    logger.info(f"Fetching data for {resolved_symbol} with timeframe {timeframe}...")
    
    # Map timeframe to yfinance interval and period
    tf_map = {
        "1m": ("1m", "7d"),      # Max intraday 1m available on yfinance is 7d
        "5m": ("5m", "60d"),     # Max 5m is 60d
        "15m": ("15m", "60d"),   # Max 15m is 60d
        "30m": ("30m", "60d"),   # Max 30m is 60d
        "1h": ("60m", "730d"),   # Max 1h is 730d (2 years)
        "4h": ("60m", "730d"),   # Will resample 1h to 4h
        "1d": ("1d", "10y"),     # Up to 10 years for daily
        "1w": ("1wk", "10y")     # Up to 10 years for weekly
    }
    
    interval, period = tf_map.get(timeframe, ("1d", "10y"))
    
    try:
        ticker = yf.Ticker(resolved_symbol)
        df = ticker.history(period=period, interval=interval, auto_adjust=True)
        
        if df.empty or len(df) < 30:
            # Try fetching standard 1d daily fallback if intraday returned empty
            if timeframe not in ["1d", "1w"]:
                logger.warning(f"Intraday data empty for {resolved_symbol}, trying 1d fallback")
                df = ticker.history(period="10y", interval="1d", auto_adjust=True)
                timeframe = "1d"
        
        if df.empty or len(df) < 30:
            return {
                "status": "INSUFFICIENT_DATA",
                "message": f"Insufficient historical data available for asset '{symbol_input}'. Minimum 30 candles required.",
                "data": None
            }
            
        # Standardize columns
        df = df.reset_index()
        # Handle index column names ('Date' or 'Datetime')
        date_col = 'Date' if 'Date' in df.columns else ('Datetime' if 'Datetime' in df.columns else df.columns[0])
        df.rename(columns={date_col: 'Timestamp', 'Open': 'Open', 'High': 'High', 'Low': 'Low', 'Close': 'Close', 'Volume': 'Volume'}, inplace=True)
        
        # Format timestamps to ISO string
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        
        # Resample to 4h if 4h requested
        if timeframe == "4h":
            df.set_index('Timestamp', inplace=True)
            resampled = df.resample('4h').agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }).dropna().reset_index()
            df = resampled

        # Calculate exact coverage years
        min_date = df['Timestamp'].min()
        max_date = df['Timestamp'].max()
        days_span = (max_date - min_date).days
        years_span = round(days_span / 365.25, 1)
        
        # Fast ticker info metadata
        info = ticker.info if hasattr(ticker, 'info') and isinstance(ticker.info, dict) else {}
        last_price = float(df['Close'].iloc[-1])
        
        return {
            "status": "SUCCESS",
            "symbol": symbol_input,
            "resolved_symbol": resolved_symbol,
            "timeframe": timeframe,
            "data_source": "Yahoo Finance Feed",
            "data_period": f"{min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}",
            "years_available": years_span,
            "candle_count": len(df),
            "last_update": max_date.isoformat(),
            "last_price": last_price,
            "dataframe": df
        }
        
    except Exception as e:
        logger.error(f"Error fetching market data for {symbol_input}: {str(e)}")
        return {
            "status": "ERROR",
            "message": f"Failed to fetch market data: {str(e)}",
            "data": None
        }
