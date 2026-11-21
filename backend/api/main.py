import sys
import os

# Ensure backend/ is on sys.path so bare imports (e.g. from market_data.fetcher)
# work regardless of the working directory or serverless context.
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_project_root = os.path.dirname(_backend_dir)
for _p in [_backend_dir, _project_root]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from contextlib import asynccontextmanager
from datetime import datetime

import pandas as pd
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import asyncio
import json
import logging

from market_data.symbols import resolve_asset, is_market_open
from market_data.live_feed import manager, fetch_history, provider_chain, is_offline_source
from market_data.providers.coingecko import fetch_crypto_market_list
from market_data.candle_builder import TIMEFRAME_SECONDS
from services.analysis_service import run_full_analysis
from risk.paper_trading import PaperTradingEngine
from services.screen_service import ScreenAnalysisService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trade_ai_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("TradeAI backend starting")
    yield
    await manager.shutdown()
    logger.info("TradeAI backend stopped")


app = FastAPI(
    title="TradeAI API",
    version="3.0.0",
    description="Data-driven AI Trading Analysis Backend with live market data",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

paper_trading_engine = PaperTradingEngine()

DISCLAIMER = (
    "For education and research only. Not financial advice. "
    "Predictions are probabilistic and can be wrong."
)


# --- Request models ----------------------------------------------------------
class AnalyzeRequest(BaseModel):
    symbol: str
    timeframe: str = "1d"
    openai_api_key: str | None = None


class PaperTradeRequest(BaseModel):
    symbol: str
    current_price: float
    probabilities: dict
    prediction_interval: dict


class VerifyScreenRequest(BaseModel):
    screen_symbol: str
    screen_price: float
    api_price: float


# --- Helpers -----------------------------------------------------------------
def candles_from_df(df: pd.DataFrame) -> list[dict]:
    candles = []
    for _, row in df.iterrows():
        ts = pd.Timestamp(row["Timestamp"])
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        candles.append(
            {
                "time": int(ts.timestamp()),
                "open": float(round(row["Open"], 6)),
                "high": float(round(row["High"], 6)),
                "low": float(round(row["Low"], 6)),
                "close": float(round(row["Close"], 6)),
                "volume": float(round(row.get("Volume", 0.0) or 0.0, 4)),
            }
        )
    return candles


def static_feed_status(asset, offline: bool = False) -> dict:
    """Feed status when no live feed object exists yet (REST snapshot)."""
    if offline:
        return {
            "symbol": asset.display,
            "asset_class": asset.asset_class,
            "mode": "OFFLINE",
            "source": "offline dataset",
            "market_open": is_market_open(asset),
            "last_tick": None,
            "last_price": None,
            "age_seconds": None,
            "message": "No live feed available — showing the stored offline dataset (static snapshot, not live).",
            "server_time": datetime.utcnow().timestamp(),
        }
    live_providers = provider_chain(asset)
    primary = live_providers[0].name if live_providers else "none"
    freshness = live_providers[0].freshness if live_providers else "DELAYED"
    if not is_market_open(asset):
        mode = "CLOSED"
    else:
        mode = freshness
    return {
        "symbol": asset.display,
        "asset_class": asset.asset_class,
        "mode": mode,
        "source": primary,
        "market_open": is_market_open(asset),
        "last_tick": None,
        "last_price": None,
        "age_seconds": None,
        "message": (
            f"Streaming via {primary}." if mode in ("LIVE", "DELAYED")
            else "Market is closed — showing last close."
        ),
        "server_time": datetime.utcnow().timestamp(),
    }


# --- Basic endpoints ---------------------------------------------------------
@app.get("/api/health")
def health():
    return {
        "status": "ONLINE",
        "app": "TradeAI Backend",
        "version": "v3.0.0",
        "disclaimer": DISCLAIMER,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/watchlist")
def get_watchlist():
    return [
        {"symbol": "BTC/USDT", "name": "Bitcoin", "category": "Crypto"},
        {"symbol": "ETH/USDT", "name": "Ethereum", "category": "Crypto"},
        {"symbol": "SOL", "name": "Solana", "category": "Crypto"},
        {"symbol": "ADA", "name": "Cardano", "category": "Crypto"},
        {"symbol": "DOGE", "name": "Dogecoin", "category": "Crypto"},
        {"symbol": "XRP", "name": "Ripple", "category": "Crypto"},
        {"symbol": "RELIANCE", "name": "Reliance Industries", "category": "Indian Stock"},
        {"symbol": "TCS", "name": "Tata Consultancy Services", "category": "Indian Stock"},
        {"symbol": "NIFTY 50", "name": "Nifty 50 Index", "category": "Index"},
        {"symbol": "BANK NIFTY", "name": "Bank Nifty Index", "category": "Index"},
        {"symbol": "AAPL", "name": "Apple Inc.", "category": "US Stock"},
        {"symbol": "TSLA", "name": "Tesla Inc.", "category": "US Stock"},
        {"symbol": "NVDA", "name": "NVIDIA Corp.", "category": "US Stock"},
    ]


@app.get("/api/crypto-list")
async def crypto_list(limit: int = 60):
    """Real, live crypto list for the Target Scanner search surface (CoinGecko)."""
    coins = await fetch_crypto_market_list(limit=limit)
    return {"status": "SUCCESS" if coins else "UNAVAILABLE", "count": len(coins), "coins": coins}


# --- History / chart ---------------------------------------------------------
@app.get("/api/chart-data/{symbol:path}")
async def get_chart_data(symbol: str, timeframe: str = "1d"):
    asset = resolve_asset(symbol)
    if not asset:
        raise HTTPException(
            status_code=400,
            detail="Unable to reliably identify the trading instrument. Please select the asset manually.",
        )
    result = await fetch_history(asset, timeframe)
    if result.status != "SUCCESS" or result.dataframe is None:
        raise HTTPException(status_code=400, detail=result.message or "Failed to load chart data")

    df = result.dataframe
    last_price = float(df["Close"].iloc[-1])
    return {
        "symbol": asset.display,
        "resolved_ticker": asset.yahoo_symbol,
        "timeframe": result.timeframe,
        "data_source": result.source,
        "candle_count": int(len(df)),
        "last_price": last_price,
        "feed_status": static_feed_status(asset, offline=is_offline_source(result.source)),
        "candles": candles_from_df(df),
    }


# --- Feed status -------------------------------------------------------------
@app.get("/api/feed-status/{symbol:path}")
async def feed_status(symbol: str):
    asset = resolve_asset(symbol)
    if not asset:
        return {
            "status": "UNIDENTIFIED",
            "message": "Unable to reliably identify the trading instrument. Please select the asset manually.",
        }
    feed = manager.peek(asset)
    if feed is not None:
        status = feed._status_message()
        status["status"] = "SUCCESS"
        return status
    status = static_feed_status(asset)
    status["status"] = "SUCCESS"
    return status


# --- Full analysis -----------------------------------------------------------
@app.post("/api/analyze")
async def analyze_asset(req: AnalyzeRequest):
    asset = resolve_asset(req.symbol)
    if not asset:
        return {
            "status": "UNIDENTIFIED",
            "error_code": "SYMBOL_UNIDENTIFIED",
            "message": "Unable to reliably identify the trading instrument. Please select the asset manually.",
            "prediction": None,
        }

    result = await fetch_history(asset, req.timeframe)
    if result.status != "SUCCESS" or result.dataframe is None:
        return {
            "status": "INSUFFICIENT_DATA",
            "error_code": "DATA_FETCH_FAILED",
            "message": result.message
            or "Insufficient historical data to produce a validated prediction for this asset/timeframe.",
            "prediction": None,
        }

    df = result.dataframe
    min_ts = pd.Timestamp(df["Timestamp"].min())
    max_ts = pd.Timestamp(df["Timestamp"].max())
    meta = {
        "symbol": asset.display,
        "resolved_symbol": asset.yahoo_symbol,
        "data_source": result.source,
        "timeframe": result.timeframe,
        "data_period": f"{min_ts.strftime('%Y-%m-%d')} to {max_ts.strftime('%Y-%m-%d')}",
        "years_available": round((max_ts - min_ts).days / 365.25, 1),
        "candle_count": int(len(df)),
        "last_update": max_ts.isoformat(),
    }
    analysis = await asyncio.to_thread(run_full_analysis, df, meta, req.openai_api_key)
    analysis["feed_status"] = static_feed_status(asset, offline=is_offline_source(result.source))
    analysis["disclaimer"] = DISCLAIMER
    return analysis


# --- Quick growth (Target Scanner) ------------------------------------------
async def _quick_growth(asset) -> dict:
    result = await fetch_history(asset, "1d", days=400)
    if result.status != "SUCCESS" or result.dataframe is None:
        return {"status": "INSUFFICIENT_DATA", "message": result.message or "Insufficient historical data."}

    closes = result.dataframe["Close"].astype(float)
    current_price = float(closes.iloc[-1])
    returns = closes.pct_change().dropna()

    def period_return(days: int):
        if len(closes) <= days:
            return None
        return float((closes.iloc[-1] / closes.iloc[-(days + 1)]) - 1.0) * 100.0

    ret_7d, ret_30d, ret_90d = period_return(7), period_return(30), period_return(90)
    daily_vol = float(returns.tail(60).std()) if len(returns) >= 10 else 0.02
    expected_30d_move_pct = float(daily_vol * (30 ** 0.5) * 100.0)
    momentum_bias = ret_30d if ret_30d is not None else (ret_7d or 0.0)
    potential_growth_pct = float(
        0.65 * momentum_bias + 0.35 * expected_30d_move_pct * (1 if momentum_bias >= 0 else -1)
    )

    if potential_growth_pct > 2:
        bias = "BULLISH"
    elif potential_growth_pct < -2:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    up_prob = max(5.0, min(95.0, 50.0 + potential_growth_pct * 1.2))
    down_prob = max(5.0, min(95.0, 100.0 - up_prob - 10.0))
    side_prob = max(5.0, 100.0 - up_prob - down_prob)

    return {
        "status": "SUCCESS",
        "symbol": asset.display,
        "resolved_ticker": asset.yahoo_symbol,
        "name": asset.name,
        "current_price": round(current_price, 6),
        "potential_growth_pct": round(potential_growth_pct, 2),
        "bias": bias,
        "returns": {
            "7d_pct": None if ret_7d is None else round(ret_7d, 2),
            "30d_pct": None if ret_30d is None else round(ret_30d, 2),
            "90d_pct": None if ret_90d is None else round(ret_90d, 2),
        },
        "expected_30d_move_pct": round(expected_30d_move_pct, 2),
        "probabilities": {
            "UP": round(up_prob, 1),
            "DOWN": round(down_prob, 1),
            "SIDEWAYS": round(side_prob, 1),
        },
        "data_source": result.source,
        "as_of": datetime.utcnow().isoformat(),
    }


@app.get("/api/quick-growth")
async def quick_growth_query(symbol: str):
    asset = resolve_asset(symbol)
    if not asset:
        return {
            "status": "UNIDENTIFIED",
            "message": "Unable to reliably identify the trading instrument. Please select the asset manually.",
        }
    return await _quick_growth(asset)


@app.get("/api/quick-growth/{symbol:path}")
async def quick_growth_path(symbol: str):
    asset = resolve_asset(symbol)
    if not asset:
        return {
            "status": "UNIDENTIFIED",
            "message": "Unable to reliably identify the trading instrument. Please select the asset manually.",
        }
    return await _quick_growth(asset)


# --- Paper trading -----------------------------------------------------------
@app.post("/api/paper-trading/log")
def log_paper_trade(req: PaperTradeRequest):
    trade = paper_trading_engine.log_prediction_trade(
        asset=req.symbol,
        current_price=req.current_price,
        predicted_probs=req.probabilities,
        prediction_interval=req.prediction_interval,
    )
    return {"status": "SUCCESS", "trade": trade}


@app.get("/api/paper-trading/summary")
def get_paper_trading_summary():
    return paper_trading_engine.get_performance_summary()


@app.post("/api/verify-screen")
def verify_screen(req: VerifyScreenRequest):
    return ScreenAnalysisService.verify_screen_price(req.screen_symbol, req.screen_price, req.api_price)


# --- Live WebSocket ----------------------------------------------------------
@app.websocket("/ws/live/{symbol:path}")
async def ws_live(websocket: WebSocket, symbol: str, timeframe: str = "1d"):
    await websocket.accept()

    asset = resolve_asset(symbol)
    if not asset:
        await websocket.send_json(
            {
                "type": "error",
                "code": "SYMBOL_UNIDENTIFIED",
                "message": "Unable to reliably identify the trading instrument. Please select the asset manually.",
            }
        )
        await websocket.close()
        return

    if timeframe not in TIMEFRAME_SECONDS:
        timeframe = "1d"

    feed = await manager.get_feed(asset)
    queue = await feed.subscribe(timeframe)

    async def pump() -> None:
        while True:
            message = await queue.get()
            await websocket.send_json(message)

    pump_task = asyncio.create_task(pump())
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except Exception:
                continue
            action = data.get("action")
            if action == "set_timeframe" and data.get("timeframe"):
                await feed.change_timeframe(queue, data["timeframe"])
            elif action == "ping":
                await websocket.send_json({"type": "pong", "server_time": datetime.utcnow().timestamp()})
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("WS error for %s: %s", symbol, exc)
    finally:
        pump_task.cancel()
        feed.unsubscribe(queue)
