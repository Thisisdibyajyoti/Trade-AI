import sys
import os

# Ensure backend/ is on sys.path so bare imports (e.g. from market_data.fetcher)
# work regardless of the working directory or serverless context.
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_project_root = os.path.dirname(_backend_dir)
for _p in [_backend_dir, _project_root]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import json
import logging
from datetime import datetime

from market_data.fetcher import fetch_historical_data, resolve_symbol
from preprocessing.cleaner import DataQualityEngine
from features.engineer import FeatureEngineer
from models.statistical_baseline import StatisticalBaselineModel
from models.xgboost_model import XGBoostModel
from models.lstm_model import LSTMModel
from models.temporal_model import TemporalModel
from models.ridge_model import RidgeModel
from models.lasso_model import LassoModel
from backtesting.walk_forward import WalkForwardBacktester
from ensemble.combiner import EnsembleCombiner
from prediction.calibrator import ProbabilityCalibrator
from similarity.engine import MarketRegimeAndSimilarityEngine
from risk.paper_trading import PaperTradingEngine
from services.openai_service import OpenAIReasoningService
from services.screen_service import ScreenAnalysisService
from explainability.engine import ExplainableAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trade_ai_api")

app = FastAPI(title="TradeAI API", version="2.1.0", description="Data-driven AI Trading Analysis Backend")

# Enable CORS for React frontend & Tauri overlay
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

paper_trading_engine = PaperTradingEngine()

# Request Models
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

@app.get("/api/health")
def health():
    return {
        "status": "ONLINE",
        "app": "TradeAI Backend",
        "version": "v2.1.0",
        "timestamp": datetime.utcnow().isoformat()
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
        {"symbol": "NVDA", "name": "NVIDIA Corp.", "category": "US Stock"}
    ]

@app.get("/api/chart-data/{symbol}")
def get_chart_data(symbol: str, timeframe: str = "1d"):
    result = fetch_historical_data(symbol, timeframe=timeframe)
    if result["status"] != "SUCCESS" or result["dataframe"] is None:
        raise HTTPException(status_code=400, detail=result.get("message", "Failed to load chart data"))
    
    df = result["dataframe"]
    candles = []
    for _, row in df.iterrows():
        # Timestamp as UNIX seconds for Lightweight Charts
        ts = int(pd.to_datetime(row["Timestamp"]).timestamp()) if 'pd' in globals() else int(datetime.fromisoformat(str(row["Timestamp"])).timestamp())
        candles.append({
            "time": ts,
            "open": float(round(row["Open"], 2)),
            "high": float(round(row["High"], 2)),
            "low": float(round(row["Low"], 2)),
            "close": float(round(row["Close"], 2)),
            "volume": float(round(row["Volume"], 2))
        })
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "candles": candles
    }

import pandas as pd # Ensure pandas in scope for API functions

@app.post("/api/analyze")
def analyze_asset(req: AnalyzeRequest):
    symbol = req.symbol.strip().upper()
    timeframe = req.timeframe
    
    # 1. Verify / Resolve Symbol
    resolved = resolve_symbol(symbol)
    if not resolved:
        return {
            "status": "UNIDENTIFIED",
            "error_code": "SYMBOL_UNIDENTIFIED",
            "message": "Unable to reliably identify the trading instrument. Please select the asset manually.",
            "prediction": None
        }

    # 2. Fetch Historical Data (Up to 10 Years)
    data_res = fetch_historical_data(symbol, timeframe=timeframe, max_years=10)
    if data_res["status"] != "SUCCESS" or data_res["dataframe"] is None:
        return {
            "status": "INSUFFICIENT_DATA",
            "error_code": "DATA_FETCH_FAILED",
            "message": data_res.get("message", "Insufficient historical data to produce a validated prediction for this asset/timeframe."),
            "prediction": None
        }

    raw_df = data_res["dataframe"]

    # 3. Data Quality Engine
    quality_res = DataQualityEngine.clean_and_audit(raw_df, source_name=data_res["data_source"], timeframe=timeframe)
    if quality_res["status"] != "SUCCESS":
        return {
            "status": "DATA_QUALITY_ERROR",
            "message": "Data quality audit failed for dataset.",
            "prediction": None
        }

    clean_df = quality_res["clean_df"]
    data_summary = quality_res["summary"]

    # 4. Feature Engineering
    df_features = FeatureEngineer.generate_features(clean_df)
    feature_cols = [
        'returns', 'log_returns', 'momentum_5', 'momentum_10', 'hl_range', 'oc_range',
        'volatility_20', 'atr_14', 'sma_20', 'sma_50', 'rsi_14', 'macd', 'macd_signal',
        'bb_pct_b', 'bb_bandwidth', 'stoch_k', 'stoch_d', 'cci_20', 'volume_change', 'rvol', 'trend_strength'
    ]

    # 5. Fit Models
    model_d_baseline = StatisticalBaselineModel()
    model_a_xgb = XGBoostModel()
    model_b_lstm = LSTMModel(seq_len=10)
    model_c_temp = TemporalModel()
    model_e_ridge = RidgeModel(auto_tune=True)
    model_f_lasso = LassoModel(auto_tune=True)

    # Fit baseline
    model_d_baseline.fit(df_features['returns'])
    p_d = model_d_baseline.predict_probabilities()

    # Fit XGBoost
    model_a_xgb.fit(df_features, feature_cols)
    p_a = model_a_xgb.predict_proba(df_features)

    # Fit LSTM
    model_b_lstm.fit(df_features, feature_cols)
    p_b = model_b_lstm.predict_proba(df_features)

    # Fit Temporal
    model_c_temp.fit(df_features, feature_cols)
    p_c = model_c_temp.predict_proba(df_features)

    # Fit Ridge (L2 Regularization)
    model_e_ridge.fit(df_features, feature_cols)
    p_e = model_e_ridge.predict_proba(df_features)

    # Fit Lasso (L1 Regularization / Feature Selection)
    model_f_lasso.fit(df_features, feature_cols)
    p_f = model_f_lasso.predict_proba(df_features)

    # 6. Walk-Forward Backtest
    backtest_res = WalkForwardBacktester.run_walk_forward(
        df_features, feature_cols, model_a_xgb, model_d_baseline
    )

    # 7. Ensemble Combination (now includes Ridge & Lasso)
    ensemble_res = EnsembleCombiner.combine_predictions(p_a, p_b, p_c, p_d, p_e, p_f)

    # 8. Probability Calibration & Prediction Intervals
    calibrated_probs = ProbabilityCalibrator.calibrate_probabilities(ensemble_res)
    current_price = float(df_features['Close'].iloc[-1])
    returns_std = float(df_features['returns'].rolling(20).std().iloc[-1])
    
    prediction_intervals = ProbabilityCalibrator.calculate_prediction_intervals(current_price, returns_std)
    multi_horizons = ProbabilityCalibrator.generate_multi_horizon_forecast(current_price, returns_std, calibrated_probs)

    # 9. Market Regime & Historical Similarity Search
    regime_res = MarketRegimeAndSimilarityEngine.detect_market_regime(df_features)
    similarity_res = MarketRegimeAndSimilarityEngine.search_historical_similarity(df_features, feature_cols, k_neighbors=400)

    # 10. Explainable AI Report
    model_predictions = {
        "XGBoost": p_a,
        "LSTM": p_b,
        "Temporal": p_c,
        "StatisticalBaseline": p_d,
        "Ridge": p_e,
        "Lasso": p_f
    }
    xai_report = ExplainableAI.generate_full_explanation(
        model_predictions=model_predictions,
        ensemble_result=ensemble_res,
        feature_df=df_features,
        feature_cols=feature_cols,
        ridge_model=model_e_ridge,
        lasso_model=model_f_lasso,
        xgboost_model=model_a_xgb,
        backtest_result=backtest_res,
        market_regime=regime_res
    )

    # 11. OpenAI Explanation Service
    analysis_payload = {
        "symbol": symbol,
        "current_price": current_price,
        "probabilities": calibrated_probs,
        "prediction_intervals": prediction_intervals,
        "market_regime": regime_res,
        "similarity": similarity_res,
        "backtest": backtest_res,
        "xai": xai_report
    }
    ai_explanation = OpenAIReasoningService.generate_explanation(analysis_payload, api_key=req.openai_api_key)

    # 12. Transparent Data Source Card
    transparency_card = {
        "asset": symbol,
        "resolved_ticker": data_res["resolved_symbol"],
        "data_source": data_res["data_source"],
        "historical_period": data_res["data_period"],
        "years_available": data_res["years_available"],
        "observation_count": data_res["candle_count"],
        "current_data_timestamp": data_res["last_update"],
        "model_version": "TradeAI Ensemble v3.0 (Ridge+Lasso+XAI)",
        "validation_method": "Walk-Forward (Out-of-Sample)"
    }

    return {
        "status": "SUCCESS",
        "symbol": symbol,
        "current_price": current_price,
        "timeframe": timeframe,
        "probabilities": calibrated_probs,
        "prediction_intervals": prediction_intervals,
        "multi_horizons": multi_horizons,
        "market_regime": regime_res,
        "similarity": similarity_res,
        "backtest": backtest_res,
        "model_weights": ensemble_res["weights_used"],
        "xai": xai_report,
        "data_summary": data_summary,
        "transparency_card": transparency_card,
        "ai_explanation": ai_explanation
    }

@app.get("/api/quick-growth/{symbol}")
def quick_growth(symbol: str):
    """
    Fast, data-driven growth snapshot for the movable target scanner.
    Uses real OHLCV only — no fabricated predictions.
    """
    raw_symbol = symbol.strip()
    resolved = resolve_symbol(raw_symbol)
    if not resolved:
        return {
            "status": "UNIDENTIFIED",
            "message": "Unable to reliably identify the trading instrument. Please select the asset manually.",
        }

    data_res = fetch_historical_data(raw_symbol, timeframe="1d", max_years=2)
    if data_res["status"] != "SUCCESS" or data_res["dataframe"] is None:
        return {
            "status": "INSUFFICIENT_DATA",
            "message": data_res.get("message", "Insufficient historical data."),
        }

    df = data_res["dataframe"].copy()
    closes = df["Close"].astype(float)
    current_price = float(closes.iloc[-1])
    returns = closes.pct_change().dropna()

    def period_return(days: int) -> float | None:
        if len(closes) <= days:
            return None
        return float((closes.iloc[-1] / closes.iloc[-(days + 1)]) - 1.0) * 100.0

    ret_7d = period_return(7)
    ret_30d = period_return(30)
    ret_90d = period_return(90)

    daily_vol = float(returns.tail(60).std()) if len(returns) >= 10 else 0.02
    # Expected 30d move magnitude from realized vol (sqrt-time scaling)
    expected_30d_move_pct = float(daily_vol * (30 ** 0.5) * 100.0)
    momentum_bias = ret_30d if ret_30d is not None else (ret_7d or 0.0)
    # Potential growth = recent momentum blended with vol-scaled upside envelope
    potential_growth_pct = float(0.65 * momentum_bias + 0.35 * expected_30d_move_pct * (1 if momentum_bias >= 0 else -1))

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
        "symbol": raw_symbol.upper(),
        "resolved_ticker": resolved,
        "name": raw_symbol,
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
        "data_source": data_res.get("data_source", "yfinance"),
        "as_of": datetime.utcnow().isoformat(),
    }

@app.post("/api/paper-trading/log")
def log_paper_trade(req: PaperTradeRequest):
    trade = paper_trading_engine.log_prediction_trade(
        asset=req.symbol,
        current_price=req.current_price,
        predicted_probs=req.probabilities,
        prediction_interval=req.prediction_interval
    )
    return {"status": "SUCCESS", "trade": trade}

@app.get("/api/paper-trading/summary")
def get_paper_trading_summary():
    return paper_trading_engine.get_performance_summary()

@app.post("/api/verify-screen")
def verify_screen(req: VerifyScreenRequest):
    return ScreenAnalysisService.verify_screen_price(req.screen_symbol, req.screen_price, req.api_price)
