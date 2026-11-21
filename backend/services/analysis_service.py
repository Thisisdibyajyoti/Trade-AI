"""Shared analysis pipeline.

Both the REST `/api/analyze` endpoint and the live WebSocket reuse this so a
prediction computed from backfilled history and one computed on a candle close
come from exactly the same code path.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import pandas as pd

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
from services.openai_service import OpenAIReasoningService
from explainability.engine import ExplainableAI

logger = logging.getLogger("analysis_service")

FEATURE_COLS = [
    "returns", "log_returns", "momentum_5", "momentum_10", "hl_range", "oc_range",
    "volatility_20", "atr_14", "sma_20", "sma_50", "rsi_14", "macd", "macd_signal",
    "bb_pct_b", "bb_bandwidth", "stoch_k", "stoch_d", "cci_20", "volume_change",
    "rvol", "trend_strength",
]

MODEL_VERSION = "TradeAI Ensemble v3.1 (Live)"


def run_full_analysis(
    raw_df: pd.DataFrame,
    meta: dict,
    openai_api_key: Optional[str] = None,
    live: bool = False,
    cached_backtest: Optional[dict] = None,
) -> dict:
    """
    Run the full quantitative pipeline on a raw OHLCV dataframe.

    `meta` should provide: symbol, resolved_symbol, data_source, timeframe and
    optionally data_period / years_available / candle_count / last_update.

    When `live` is True the expensive out-of-sample walk-forward backtest is not
    recomputed on every candle close; the previously computed result is reused
    (pass it via `cached_backtest`). Everything else — features, models,
    probabilities, intervals, regime, similarity — is recomputed fresh.
    """
    symbol = meta.get("symbol", "")
    timeframe = meta.get("timeframe", "1d")
    source = meta.get("data_source", "market feed")

    if raw_df is None or raw_df.empty:
        return {
            "status": "INSUFFICIENT_DATA",
            "error_code": "NO_DATA",
            "message": "No historical data available to produce a validated prediction.",
            "prediction": None,
        }

    # 1. Data quality audit
    quality = DataQualityEngine.clean_and_audit(raw_df, source_name=source, timeframe=timeframe)
    if quality.get("status") != "SUCCESS":
        return {
            "status": "DATA_QUALITY_ERROR",
            "message": "Data quality audit failed for dataset.",
            "prediction": None,
        }
    clean_df = quality["clean_df"]
    data_summary = quality["summary"]

    if len(clean_df) < 60:
        return {
            "status": "INSUFFICIENT_DATA",
            "error_code": "DATA_TOO_SHORT",
            "message": (
                f"Only {len(clean_df)} candles were available; at least 60 are required "
                "for a validated prediction."
            ),
            "prediction": None,
        }

    # 2. Feature engineering (past-only)
    df_features = FeatureEngineer.generate_features(clean_df)

    # 3. Fit models
    model_d_baseline = StatisticalBaselineModel()
    model_a_xgb = XGBoostModel()
    model_b_lstm = LSTMModel(seq_len=10)
    model_c_temp = TemporalModel()
    # Live refresh runs on every candle close, so it must be cheap: skip the
    # cross-validated hyper-parameter search and use the fixed defaults. The
    # full search still runs for the on-demand `/api/analyze` path.
    model_e_ridge = RidgeModel(auto_tune=not live)
    model_f_lasso = LassoModel(auto_tune=not live)

    model_d_baseline.fit(df_features["returns"])
    p_d = model_d_baseline.predict_probabilities()

    model_a_xgb.fit(df_features, FEATURE_COLS)
    p_a = model_a_xgb.predict_proba(df_features)

    model_b_lstm.fit(df_features, FEATURE_COLS)
    p_b = model_b_lstm.predict_proba(df_features)

    model_c_temp.fit(df_features, FEATURE_COLS)
    p_c = model_c_temp.predict_proba(df_features)

    model_e_ridge.fit(df_features, FEATURE_COLS)
    p_e = model_e_ridge.predict_proba(df_features)

    model_f_lasso.fit(df_features, FEATURE_COLS)
    p_f = model_f_lasso.predict_proba(df_features)

    # 4. Walk-forward out-of-sample backtest
    if live and cached_backtest:
        backtest_res = cached_backtest
    else:
        backtest_res = WalkForwardBacktester.run_walk_forward(
            df_features, FEATURE_COLS, model_a_xgb, model_d_baseline
        )

    # 5. Ensemble
    ensemble_res = EnsembleCombiner.combine_predictions(p_a, p_b, p_c, p_d, p_e, p_f)

    # 6. Calibration & intervals (anchored on the latest price)
    calibrated_probs = ProbabilityCalibrator.calibrate_probabilities(ensemble_res)
    current_price = float(df_features["Close"].iloc[-1])
    returns_std = float(df_features["returns"].rolling(20).std().iloc[-1])
    if not (returns_std > 0):
        returns_std = float(df_features["returns"].std() or 0.01)

    prediction_intervals = ProbabilityCalibrator.calculate_prediction_intervals(current_price, returns_std)
    multi_horizons = ProbabilityCalibrator.generate_multi_horizon_forecast(
        current_price, returns_std, calibrated_probs
    )

    # 7. Regime & similarity
    regime_res = MarketRegimeAndSimilarityEngine.detect_market_regime(df_features)
    similarity_res = MarketRegimeAndSimilarityEngine.search_historical_similarity(
        df_features, FEATURE_COLS, k_neighbors=400
    )

    # 8. Explainable AI
    model_predictions = {
        "XGBoost": p_a, "LSTM": p_b, "Temporal": p_c,
        "StatisticalBaseline": p_d, "Ridge": p_e, "Lasso": p_f,
    }
    xai_report = ExplainableAI.generate_full_explanation(
        model_predictions=model_predictions,
        ensemble_result=ensemble_res,
        feature_df=df_features,
        feature_cols=FEATURE_COLS,
        ridge_model=model_e_ridge,
        lasso_model=model_f_lasso,
        xgboost_model=model_a_xgb,
        backtest_result=backtest_res,
        market_regime=regime_res,
    )

    # 9. OpenAI explanation (may be template fallback)
    analysis_payload = {
        "symbol": symbol,
        "current_price": current_price,
        "probabilities": calibrated_probs,
        "prediction_intervals": prediction_intervals,
        "market_regime": regime_res,
        "similarity": similarity_res,
        "backtest": backtest_res,
        "xai": xai_report,
    }
    ai_explanation = OpenAIReasoningService.generate_explanation(analysis_payload, api_key=openai_api_key)

    # 10. Transparency card from the *real* data span
    if meta.get("data_period"):
        data_period = meta["data_period"]
        years_available = meta.get("years_available")
    else:
        min_ts = clean_df["Timestamp"].min()
        max_ts = clean_df["Timestamp"].max()
        data_period = f"{min_ts.strftime('%Y-%m-%d')} to {max_ts.strftime('%Y-%m-%d')}"
        years_available = round((max_ts - min_ts).days / 365.25, 1)

    transparency_card = {
        "asset": symbol,
        "resolved_ticker": meta.get("resolved_symbol", symbol),
        "data_source": source,
        "historical_period": data_period,
        "years_available": years_available,
        "observation_count": int(meta.get("candle_count") or len(clean_df)),
        "current_data_timestamp": meta.get("last_update") or datetime.utcnow().isoformat(),
        "model_version": MODEL_VERSION,
        "validation_method": "Walk-Forward (Out-of-Sample)",
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
        "model_weights": ensemble_res.get("weights_used", {}),
        "xai": xai_report,
        "data_summary": data_summary,
        "transparency_card": transparency_card,
        "ai_explanation": ai_explanation,
    }
