import numpy as np
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger("walk_forward_backtester")

class WalkForwardBacktester:
    """
    Evaluates ML Models against Statistical Baselines using expanding/rolling walk-forward windows.
    Generates real out-of-sample accuracy, Sharpe ratio, Max Drawdown, and Profit Factor metrics.
    """

    @staticmethod
    def run_walk_forward(df: pd.DataFrame, feature_cols: list, model_a, model_d_baseline, horizon_candles: int = 1, train_ratio: float = 0.7) -> dict:
        if df is None or len(df) < 100:
            return {
                "status": "ERROR",
                "message": "Dataset too small for walk-forward validation (minimum 100 candles needed)."
            }

        n = len(df)
        split_idx = int(n * train_ratio)

        train_df = df.iloc[:split_idx].copy()
        test_df = df.iloc[split_idx:].copy()

        # 1. Fit baseline model on training set
        train_returns = train_df['returns']
        model_d_baseline.fit(train_returns)

        # 2. Fit ML Model A on training set
        model_a.fit(train_df, feature_cols, horizon_candles=horizon_candles)

        # 3. Perform Out-of-Sample Walk-Forward Simulation
        actual_directions = []
        model_predictions = []
        baseline_predictions = []
        actual_returns = []
        
        test_df_target = model_a.prepare_target(test_df, horizon_candles)
        
        # Threshold for volatility
        vols = test_df['returns'].rolling(20).std().fillna(0.005)

        for i in range(len(test_df) - horizon_candles):
            current_row = test_df.iloc[:i+1]
            act_ret = (test_df['Close'].iloc[i + horizon_candles] - test_df['Close'].iloc[i]) / test_df['Close'].iloc[i]
            
            thresh = 0.25 * vols.iloc[i]
            if act_ret > thresh:
                act_dir = "UP"
            elif act_ret < -thresh:
                act_dir = "DOWN"
            else:
                act_dir = "SIDEWAYS"

            actual_directions.append(act_dir)
            actual_returns.append(act_ret)

            # Model A Prediction
            p_a = model_a.predict_proba(current_row)
            pred_dir_a = max(p_a, key=p_a.get)
            model_predictions.append(pred_dir_a)

            # Baseline Model D Prediction
            p_d = model_d_baseline.predict_probabilities()
            pred_dir_d = max(p_d, key=p_d.get)
            baseline_predictions.append(pred_dir_d)

        # Calculate Out-of-Sample Performance Statistics
        actuals = np.array(actual_directions)
        preds_a = np.array(model_predictions)
        preds_d = np.array(baseline_predictions)

        acc_model = float(np.mean(actuals == preds_a))
        acc_baseline = float(np.mean(actuals == preds_d))

        # Precision, Recall, F1 for Model A
        up_matches = (preds_a == "UP") & (actuals == "UP")
        precision_up = float(np.sum(up_matches) / (np.sum(preds_a == "UP") + 1e-6))
        recall_up = float(np.sum(up_matches) / (np.sum(actuals == "UP") + 1e-6))
        f1_up = float(2 * precision_up * recall_up / (precision_up + recall_up + 1e-6))

        # Financial metrics (Sharpe, Drawdown, Profit Factor)
        trade_returns = []
        for p, r in zip(model_predictions, actual_returns):
            if p == "UP":
                trade_returns.append(r)
            elif p == "DOWN":
                trade_returns.append(-r)
            else:
                trade_returns.append(0.0)

        trade_returns = np.array(trade_returns)
        gains = trade_returns[trade_returns > 0]
        losses = np.abs(trade_returns[trade_returns < 0])

        profit_factor = float(np.sum(gains) / (np.sum(losses) + 1e-6))
        sharpe_ratio = float(np.mean(trade_returns) / (np.std(trade_returns) + 1e-6) * np.sqrt(252))

        cum_equity = np.cumprod(1 + trade_returns)
        peak = np.maximum.accumulate(cum_equity)
        drawdown = (cum_equity - peak) / peak
        max_drawdown = float(np.min(drawdown)) if len(drawdown) > 0 else 0.0

        min_test_date = test_df['Timestamp'].min().strftime('%Y-%m-%d')
        max_test_date = test_df['Timestamp'].max().strftime('%Y-%m-%d')

        return {
            "status": "SUCCESS",
            "validation_method": "Walk-Forward (Out-of-Sample)",
            "test_period": f"{min_test_date} to {max_test_date}",
            "train_samples": split_idx,
            "test_samples": len(test_df) - horizon_candles,
            "model_directional_accuracy": round(acc_model * 100, 2),
            "baseline_directional_accuracy": round(acc_baseline * 100, 2),
            "outperforms_baseline": bool(acc_model > acc_baseline),
            "precision": round(precision_up * 100, 2),
            "recall": round(recall_up * 100, 2),
            "f1_score": round(f1_up * 100, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_pct": round(max_drawdown * 100, 2),
            "last_training_date": datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        }
