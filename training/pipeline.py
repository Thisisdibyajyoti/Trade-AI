import os
import sys
import pandas as pd
import numpy as np
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.market_data.fetcher import fetch_historical_data
from backend.preprocessing.cleaner import DataQualityEngine
from backend.features.engineer import FeatureEngineer
from backend.models.xgboost_model import XGBoostModel
from backend.models.statistical_baseline import StatisticalBaselineModel
from backend.models.ridge_model import RidgeModel
from backend.models.lasso_model import LassoModel
from backend.backtesting.walk_forward import WalkForwardBacktester
from backend.explainability.engine import ExplainableAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("offline_training_pipeline")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# Mapping from user-facing symbols to CSV filenames
SYMBOL_TO_CSV = {
    "BTC/USDT": "BTC-USD_daily.csv",
    "ETH/USDT": "ETH-USD_daily.csv",
    "AAPL": "AAPL_daily.csv",
    "TSLA": "TSLA_daily.csv",
    "NVDA": "NVDA_daily.csv",
    "MSFT": "MSFT_daily.csv",
    "GOOGL": "GOOGL_daily.csv",
    "AMZN": "AMZN_daily.csv",
    "SPY": "SPY_daily.csv",
    "RELIANCE": "RELIANCE_NS_daily.csv",
    "TCS": "TCS_NS_daily.csv",
    "NIFTY 50": "IDX_NSEI_daily.csv",
}


def load_from_csv(symbol: str) -> dict | None:
    """Load historical data from local CSV file instead of hitting the API."""
    csv_name = SYMBOL_TO_CSV.get(symbol.upper())
    if csv_name is None:
        return None

    csv_path = os.path.join(DATA_DIR, csv_name)
    if not os.path.exists(csv_path):
        logger.warning(f"CSV file not found: {csv_path}")
        logger.info("Run 'python training/generate_training_data.py' first to generate training CSVs.")
        return None

    df = pd.read_csv(csv_path)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])

    min_date = df['Timestamp'].min()
    max_date = df['Timestamp'].max()
    years = round((max_date - min_date).days / 365.25, 1)

    logger.info(f"Loaded {len(df)} candles from CSV: {csv_path}")
    return {
        "status": "SUCCESS",
        "symbol": symbol,
        "resolved_symbol": csv_name.replace("_daily.csv", ""),
        "timeframe": "1d",
        "data_source": f"Local CSV ({csv_name})",
        "data_period": f"{min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}",
        "years_available": years,
        "candle_count": len(df),
        "last_update": max_date.isoformat(),
        "last_price": float(df['Close'].iloc[-1]),
        "dataframe": df
    }


def train_offline_pipeline(symbol: str = "BTC/USDT", timeframe: str = "1d", use_csv: bool = True):
    logger.info(f"--- Starting Offline Training Pipeline for {symbol} ---")
    
    # 1. Load data — prefer local CSV, fall back to live API fetch
    raw = None
    if use_csv:
        raw = load_from_csv(symbol)
        if raw:
            logger.info(f"Using local CSV data for {symbol}")

    if raw is None:
        logger.info(f"Fetching live data for {symbol} from Yahoo Finance...")
        raw = fetch_historical_data(symbol, timeframe=timeframe, max_years=10)

    if raw["status"] != "SUCCESS":
        logger.error(f"Data fetch failed: {raw.get('message')}")
        return
        
    df_raw = raw["dataframe"]
    
    # 2. Data Quality
    clean_res = DataQualityEngine.clean_and_audit(df_raw, raw["data_source"], timeframe)
    df_clean = clean_res["clean_df"]
    
    # 3. Features
    df_feat = FeatureEngineer.generate_features(df_clean)
    feature_cols = [
        'returns', 'log_returns', 'momentum_5', 'momentum_10', 'hl_range', 'oc_range',
        'volatility_20', 'atr_14', 'sma_20', 'sma_50', 'rsi_14', 'macd', 'macd_signal',
        'bb_pct_b', 'bb_bandwidth', 'stoch_k', 'stoch_d', 'cci_20', 'volume_change', 'rvol', 'trend_strength'
    ]
    
    # 4. Fit All Models
    b_model = StatisticalBaselineModel()
    xgb_model = XGBoostModel()
    ridge_model = RidgeModel(auto_tune=True)
    lasso_model = LassoModel(auto_tune=True)

    b_model.fit(df_feat['returns'])
    xgb_model.fit(df_feat, feature_cols)
    ridge_model.fit(df_feat, feature_cols)
    lasso_model.fit(df_feat, feature_cols)
    
    # 5. Out-of-Sample Walk-Forward Backtest
    backtest = WalkForwardBacktester.run_walk_forward(df_feat, feature_cols, xgb_model, b_model)
    
    logger.info("--- Walk-Forward Out-of-Sample Validation Results ---")
    logger.info(f"Test Period: {backtest.get('test_period')}")
    logger.info(f"Model Directional Accuracy: {backtest.get('model_directional_accuracy')}%")
    logger.info(f"Baseline Benchmark Accuracy: {backtest.get('baseline_directional_accuracy')}%")
    logger.info(f"Sharpe Ratio: {backtest.get('sharpe_ratio')}")
    logger.info(f"Profit Factor: {backtest.get('profit_factor')}")
    logger.info(f"Max Drawdown: {backtest.get('max_drawdown_pct')}%")

    # 6. Explainable AI Report
    model_predictions = {
        "XGBoost": xgb_model.predict_proba(df_feat),
        "StatisticalBaseline": b_model.predict_probabilities(),
        "Ridge": ridge_model.predict_proba(df_feat),
        "Lasso": lasso_model.predict_proba(df_feat),
    }
    xai_report = ExplainableAI.generate_full_explanation(
        model_predictions=model_predictions,
        ensemble_result=model_predictions["XGBoost"],  # Primary model as proxy
        feature_df=df_feat,
        feature_cols=feature_cols,
        ridge_model=ridge_model,
        lasso_model=lasso_model,
        xgboost_model=xgb_model,
        backtest_result=backtest
    )

    logger.info("--- Explainable AI Report ---")
    logger.info(f"Top Feature Drivers: {xai_report.get('feature_importance', {}).get('top_5', [])}")
    logger.info(f"Model Agreement: {xai_report.get('model_agreement', {}).get('agreement_pct', 0)}%")
    logger.info(f"Confidence Tier: {xai_report.get('confidence_assessment', {}).get('tier', 'N/A')}")

    # 7. Lasso Feature Selection Report
    lasso_report = lasso_model.get_selected_features_report()
    logger.info(f"--- Lasso Feature Selection ---")
    logger.info(f"Selected {lasso_report.get('selected_count', 0)}/{lasso_report.get('total_features', 0)} features")
    logger.info(f"Selected: {lasso_report.get('selected', [])}")
    logger.info(f"Eliminated: {lasso_report.get('eliminated', [])}")
    logger.info(f"Sparsity Ratio: {lasso_report.get('sparsity_ratio', 0)}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TradeAI Offline Training Pipeline")
    parser.add_argument("--symbol", default="BTC/USDT", help="Asset symbol (e.g. BTC/USDT, AAPL, NVDA)")
    parser.add_argument("--timeframe", default="1d", help="Timeframe (default: 1d)")
    parser.add_argument("--live", action="store_true", help="Force live API fetch instead of local CSV")
    args = parser.parse_args()

    train_offline_pipeline(args.symbol, args.timeframe, use_csv=not args.live)
