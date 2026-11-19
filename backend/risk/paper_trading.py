import json
import os
from datetime import datetime
import numpy as np

class PaperTradingEngine:
    """
    Paper Trading & Evaluation Feedback System (Requirement #24).
    Logs live predictions, updates them with actual future price outcomes,
    and calculates empirical win rate, profit factor, and prediction error over time.
    """

    def __init__(self, storage_path: str = "paper_trades.json"):
        self.storage_path = storage_path
        self.trades = self._load_trades()

    def _load_trades(self) -> list:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_trades(self):
        try:
            with open(self.storage_path, "w") as f:
                json.dump(self.trades, f, indent=2)
        except Exception as e:
            print(f"Error saving paper trades: {e}")

    def log_prediction_trade(
        self,
        asset: str,
        current_price: float,
        predicted_probs: dict,
        prediction_interval: dict,
        model_version: str = "Ensemble v2.1"
    ) -> dict:
        trade_id = f"PT-{len(self.trades) + 1:04d}"
        pred_direction = max(predicted_probs, key=predicted_probs.get)
        
        trade = {
            "id": trade_id,
            "timestamp": datetime.utcnow().isoformat(),
            "asset": asset,
            "entry_price": current_price,
            "predicted_probs": predicted_probs,
            "predicted_direction": pred_direction,
            "prediction_interval": prediction_interval,
            "model_version": model_version,
            "status": "OPEN", # OPEN or CLOSED
            "exit_price": None,
            "actual_return_pct": None,
            "outcome": None, # WIN, LOSS, NEUTRAL
            "prediction_error_pct": None
        }
        
        self.trades.append(trade)
        self._save_trades()
        return trade

    def update_open_trades(self, asset: str, latest_price: float) -> list:
        updated = []
        for t in self.trades:
            if t["asset"] == asset and t["status"] == "OPEN":
                entry = t["entry_price"]
                ret = (latest_price - entry) / entry
                ret_pct = round(ret * 100, 2)
                
                pred_dir = t["predicted_direction"]
                if pred_dir == "UP":
                    outcome = "WIN" if ret > 0.001 else ("LOSS" if ret < -0.001 else "NEUTRAL")
                elif pred_dir == "DOWN":
                    outcome = "WIN" if ret < -0.001 else ("LOSS" if ret > 0.001 else "NEUTRAL")
                else:
                    outcome = "WIN" if abs(ret) <= 0.003 else "LOSS"

                t["exit_price"] = latest_price
                t["actual_return_pct"] = ret_pct
                t["outcome"] = outcome
                t["status"] = "CLOSED"
                t["prediction_error_pct"] = round(abs(latest_price - (t["prediction_interval"]["interval_50"]["upper"] + t["prediction_interval"]["interval_50"]["lower"])/2) / entry * 100, 2)
                updated.append(t)

        if updated:
            self._save_trades()
        return updated

    def get_performance_summary(self) -> dict:
        closed = [t for t in self.trades if t["status"] == "CLOSED"]
        if not closed:
            return {
                "total_trades": len(self.trades),
                "closed_trades": 0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "avg_prediction_error_pct": 0.0,
                "trades_history": self.trades[-10:]
            }

        wins = sum(1 for t in closed if t["outcome"] == "WIN")
        losses = sum(1 for t in closed if t["outcome"] == "LOSS")
        
        win_rate = (wins / len(closed)) * 100.0
        
        returns = [t["actual_return_pct"] for t in closed if t["actual_return_pct"] is not None]
        gains = [r for r in returns if r > 0]
        loss_vals = [abs(r) for r in returns if r < 0]
        
        profit_factor = (sum(gains) / (sum(loss_vals) + 1e-6)) if loss_vals else (sum(gains) if gains else 1.0)
        avg_err = float(np.mean([t["prediction_error_pct"] for t in closed if t["prediction_error_pct"] is not None])) if closed else 0.0

        return {
            "total_trades": len(self.trades),
            "closed_trades": len(closed),
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(win_rate, 1),
            "profit_factor": round(profit_factor, 2),
            "avg_prediction_error_pct": round(avg_err, 2),
            "trades_history": self.trades[-15:]
        }
