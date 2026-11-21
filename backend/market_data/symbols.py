"""
Asset registry & symbol resolution.

Every data source and the UI agree on one description of an instrument:
its asset class, which providers can serve it, the exchange timezone and
the regular-session hours used to decide LIVE / DELAYED / MARKET CLOSED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Optional
from zoneinfo import ZoneInfo

UTC = ZoneInfo("UTC")
IST = ZoneInfo("Asia/Kolkata")
ET = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class Session:
    """Regular trading session in the exchange's local timezone."""

    timezone: str
    open_time: Optional[time] = None  # None => 24/7 market
    close_time: Optional[time] = None
    # Crypto never closes.
    is_24_7: bool = False


@dataclass(frozen=True)
class AssetInfo:
    """Canonical description of a tradeable instrument."""

    input_symbol: str          # exactly what the user asked for
    display: str               # canonical display label, e.g. "BTC/USDT"
    name: str
    asset_class: str           # crypto | us_stock | in_stock | index
    yahoo_symbol: str          # symbol used by the yfinance fallback
    session: Session
    # Live providers in priority order (first one that works wins).
    live_providers: tuple[str, ...] = ()
    # Symbol used by the primary live provider (e.g. BTCUSDT for Binance).
    provider_symbol: str = ""
    brand_hint: str = "$"      # currency prefix for display

    @property
    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.session.timezone)

    def extra(self) -> dict:
        return {}


# --- Session definitions -----------------------------------------------------
CRYPTO_SESSION = Session(timezone="UTC", is_24_7=True)
NSE_SESSION = Session(timezone="Asia/Kolkata", open_time=time(9, 15), close_time=time(15, 30))
US_SESSION = Session(timezone="America/New_York", open_time=time(9, 30), close_time=time(16, 0))

# --- Crypto registry (Binance is the primary live feed) ----------------------
# name -> (binance pair, yahoo symbol)
_CRYPTO = {
    "BTC": ("BTCUSDT", "BTC-USD", "Bitcoin"),
    "ETH": ("ETHUSDT", "ETH-USD", "Ethereum"),
    "SOL": ("SOLUSDT", "SOL-USD", "Solana"),
    "ADA": ("ADAUSDT", "ADA-USD", "Cardano"),
    "DOGE": ("DOGEUSDT", "DOGE-USD", "Dogecoin"),
    "XRP": ("XRPUSDT", "XRP-USD", "Ripple"),
    "BNB": ("BNBUSDT", "BNB-USD", "BNB"),
    "AVAX": ("AVAXUSDT", "AVAX-USD", "Avalanche"),
    "DOT": ("DOTUSDT", "DOT-USD", "Polkadot"),
    "LINK": ("LINKUSDT", "LINK-USD", "Chainlink"),
    "LTC": ("LTCUSDT", "LTC-USD", "Litecoin"),
    "MATIC": ("MATICUSDT", "MATIC-USD", "Polygon"),
    "POL": ("POLUSDT", "POL-USD", "Polygon (POL)"),
    "TRX": ("TRXUSDT", "TRX-USD", "TRON"),
    "SHIB": ("SHIBUSDT", "SHIB-USD", "Shiba Inu"),
    "UNI": ("UNIUSDT", "UNI-USD", "Uniswap"),
    "ATOM": ("ATOMUSDT", "ATOM-USD", "Cosmos"),
    "ETC": ("ETCUSDT", "ETC-USD", "Ethereum Classic"),
    "FIL": ("FILUSDT", "FIL-USD", "Filecoin"),
    "APT": ("APTUSDT", "APT-USD", "Aptos"),
    "ARB": ("ARBUSDT", "ARB-USD", "Arbitrum"),
    "OP": ("OPUSDT", "OP-USD", "Optimism"),
    "NEAR": ("NEARUSDT", "NEAR-USD", "NEAR Protocol"),
    "INJ": ("INJUSDT", "INJ-USD", "Injective"),
}

# Alias -> base symbol for crypto
_CRYPTO_ALIASES = {
    "BITCOIN": "BTC",
    "ETHEREUM": "ETH",
    "SOLANA": "SOL",
    "CARDANO": "ADA",
    "DOGECOIN": "DOGE",
    "RIPPLE": "XRP",
    "AVALANCHE": "AVAX",
    "POLKADOT": "DOT",
    "CHAINLINK": "LINK",
    "LITECOIN": "LTC",
    "POLYGON": "MATIC",
    "TRON": "TRX",
    "SHIBA": "SHIB",
    "SHIBA INU": "SHIB",
    "UNISWAP": "UNI",
    "COSMOS": "ATOM",
}

# --- Named equities / indices ------------------------------------------------
# input -> (yahoo symbol, name, asset_class, session)
_NAMED = {
    # Indian equities & indices
    "RELIANCE": ("RELIANCE.NS", "Reliance Industries", "in_stock", NSE_SESSION),
    "TCS": ("TCS.NS", "Tata Consultancy Services", "in_stock", NSE_SESSION),
    "INFY": ("INFY.NS", "Infosys", "in_stock", NSE_SESSION),
    "HDFCBANK": ("HDFCBANK.NS", "HDFC Bank", "in_stock", NSE_SESSION),
    "ICICIBANK": ("ICICIBANK.NS", "ICICI Bank", "in_stock", NSE_SESSION),
    "SBIN": ("SBIN.NS", "State Bank of India", "in_stock", NSE_SESSION),
    "NIFTY 50": ("^NSEI", "Nifty 50 Index", "index", NSE_SESSION),
    "NIFTY": ("^NSEI", "Nifty 50 Index", "index", NSE_SESSION),
    "NIFTY50": ("^NSEI", "Nifty 50 Index", "index", NSE_SESSION),
    "BANK NIFTY": ("^NSEBANK", "Bank Nifty Index", "index", NSE_SESSION),
    "BANKNIFTY": ("^NSEBANK", "Bank Nifty Index", "index", NSE_SESSION),
    # US equities
    "AAPL": ("AAPL", "Apple Inc.", "us_stock", US_SESSION),
    "TSLA": ("TSLA", "Tesla Inc.", "us_stock", US_SESSION),
    "NVDA": ("NVDA", "NVIDIA Corp.", "us_stock", US_SESSION),
    "MSFT": ("MSFT", "Microsoft Corp.", "us_stock", US_SESSION),
    "GOOGL": ("GOOGL", "Alphabet Inc.", "us_stock", US_SESSION),
    "AMZN": ("AMZN", "Amazon.com Inc.", "us_stock", US_SESSION),
    "META": ("META", "Meta Platforms", "us_stock", US_SESSION),
    "SPY": ("SPY", "SPDR S&P 500 ETF", "us_stock", US_SESSION),
    "QQQ": ("QQQ", "Invesco QQQ Trust", "us_stock", US_SESSION),
}


def _clean(raw: str) -> str:
    return (raw or "").strip().upper().replace("  ", " ")


_QUOTES = ("USDT", "USDC", "BUSD", "FDUSD", "USD", "INR", "EUR", "BTC", "ETH")


def _crypto_base(token: str) -> Optional[str]:
    """Map many crypto spellings onto a registry base token (e.g. BTC)."""
    if token in _CRYPTO_ALIASES:
        return _CRYPTO_ALIASES[token]

    t = token
    for sep in ("/", "-", "_", ":"):
        if sep in t:
            t = t.split(sep)[0]
            break

    if t in _CRYPTO:
        return t
    if t in _CRYPTO_ALIASES:
        return _CRYPTO_ALIASES[t]

    # Strip a trailing quote currency, e.g. BTCUSDT -> BTC.
    for quote in _QUOTES:
        if t.endswith(quote) and len(t) > len(quote):
            base = t[: -len(quote)]
            if base in _CRYPTO:
                return base
            if base in _CRYPTO_ALIASES:
                return _CRYPTO_ALIASES[base]
    return None


def resolve_asset(raw_symbol: str) -> Optional[AssetInfo]:
    """
    Resolve user input into a fully-described instrument, or None when the
    symbol cannot be identified with confidence.
    """
    if not raw_symbol:
        return None
    clean = _clean(raw_symbol)
    if not clean:
        return None

    # 1) Crypto (explicit pair form, ticker, or plain name)
    base = _crypto_base(clean)
    if base and base in _CRYPTO:
        pair, yahoo, name = _CRYPTO[base]
        return AssetInfo(
            input_symbol=raw_symbol,
            display=f"{base}/USDT",
            name=name,
            asset_class="crypto",
            yahoo_symbol=yahoo,
            session=CRYPTO_SESSION,
            live_providers=("binance", "coingecko"),
            provider_symbol=pair,
            brand_hint="$",
        )

    # 2) Named Indian / US equities & indices
    if clean in _NAMED:
        yahoo, name, klass, session = _NAMED[clean]
        return AssetInfo(
            input_symbol=raw_symbol,
            display=clean,
            name=name,
            asset_class=klass,
            yahoo_symbol=yahoo,
            session=session,
            live_providers=("finnhub", "yfinance") if klass == "us_stock" else ("yfinance",),
            provider_symbol=yahoo,
            brand_hint="₹" if klass in ("in_stock", "index") and session is NSE_SESSION else "$",
        )

    # 3) Explicit exchange suffixes (RELIANCE.NS / X.BO)
    if clean.endswith(".NS") or clean.endswith(".BO"):
        session = NSE_SESSION
        return AssetInfo(
            input_symbol=raw_symbol,
            display=clean,
            name=clean.replace(".NS", "").replace(".BO", ""),
            asset_class="in_stock",
            yahoo_symbol=clean,
            session=session,
            live_providers=("yfinance",),
            provider_symbol=clean,
            brand_hint="₹",
        )

    # 4) Yahoo index prefix
    if clean.startswith("^"):
        return AssetInfo(
            input_symbol=raw_symbol,
            display=clean,
            name=clean,
            asset_class="index",
            yahoo_symbol=clean,
            session=US_SESSION,
            live_providers=("yfinance",),
            provider_symbol=clean,
            brand_hint="$",
        )

    # 5) Plausible US ticker: 1-5 letters. We accept it but mark it as a
    #    best-effort guess; the data fetch will confirm existence.
    if 1 <= len(clean) <= 5 and clean.isalpha():
        return AssetInfo(
            input_symbol=raw_symbol,
            display=clean,
            name=clean,
            asset_class="us_stock",
            yahoo_symbol=clean,
            session=US_SESSION,
            live_providers=("finnhub", "yfinance"),
            provider_symbol=clean,
            brand_hint="$",
        )

    return None


# --- Market-hours helpers ----------------------------------------------------
def is_market_open(asset: AssetInfo, now_utc=None) -> bool:
    """True when the regular session is open right now."""
    from datetime import datetime

    now_utc = now_utc or datetime.now(tz=UTC)
    if asset.session.is_24_7:
        return True
    local = now_utc.astimezone(asset.tzinfo)
    if local.weekday() >= 5:  # Sat/Sun
        return False
    if asset.session.open_time is None or asset.session.close_time is None:
        return False
    return asset.session.open_time <= local.time() <= asset.session.close_time


def session_bounds(asset: AssetInfo, now_utc=None):
    """Return (open_dt, close_dt) datetimes in the exchange timezone for today."""
    from datetime import datetime, timedelta

    now_utc = now_utc or datetime.now(tz=UTC)
    local = now_utc.astimezone(asset.tzinfo)
    if asset.session.is_24_7:
        return local - timedelta(days=1), local + timedelta(days=1)
    o = local.replace(
        hour=asset.session.open_time.hour,
        minute=asset.session.open_time.minute,
        second=0,
        microsecond=0,
    )
    c = local.replace(
        hour=asset.session.close_time.hour,
        minute=asset.session.close_time.minute,
        second=0,
        microsecond=0,
    )
    return o, c
