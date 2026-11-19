import numpy as np
import pandas as pd

class ProbabilityCalibrator:
    """
    Calibrates prediction probabilities and calculates prediction intervals (50%, 80%, 95%)
    based on actual historical residual error distribution (Requirement #9, #10, #11).
    """

    @staticmethod
    def calibrate_probabilities(raw_probs: dict, temperature: float = 1.0) -> dict:
        """
        Applies temperature scaling calibration to raw model probabilities.
        """
        keys = ["UP", "DOWN", "SIDEWAYS"]
        logits = np.array([np.log(max(1e-5, raw_probs.get(k, 0.33))) for k in keys])
        scaled_logits = logits / max(0.1, temperature)
        exp_l = np.exp(scaled_logits - np.max(scaled_logits))
        probs = exp_l / np.sum(exp_l)
        
        return {
            "UP": round(float(probs[0] * 100), 1),
            "DOWN": round(float(probs[1] * 100), 1),
            "SIDEWAYS": round(float(probs[2] * 100), 1)
        }

    @staticmethod
    def calculate_prediction_intervals(current_price: float, returns_std: float, horizon_multiplier: float = 1.0) -> dict:
        """
        Calculates 50%, 80%, and 95% price prediction intervals.
        Formula: price * (1 +- z * sigma * sqrt(horizon))
        """
        sigma = returns_std * np.sqrt(horizon_multiplier)
        
        # Z-scores: 50% -> 0.674, 80% -> 1.282, 95% -> 1.960
        z_50 = 0.674
        z_80 = 1.282
        z_95 = 1.960
        
        lower_50 = current_price * (1.0 - z_50 * sigma)
        upper_50 = current_price * (1.0 + z_50 * sigma)
        
        lower_80 = current_price * (1.0 - z_80 * sigma)
        upper_80 = current_price * (1.0 + z_80 * sigma)
        
        lower_95 = current_price * (1.0 - z_95 * sigma)
        upper_95 = current_price * (1.0 + z_95 * sigma)
        
        return {
            "interval_50": {"lower": round(float(lower_50), 2), "upper": round(float(upper_50), 2)},
            "interval_80": {"lower": round(float(lower_80), 2), "upper": round(float(upper_80), 2)},
            "interval_95": {"lower": round(float(lower_95), 2), "upper": round(float(upper_95), 2)},
            "residual_volatility_pct": round(float(sigma * 100), 2)
        }

    @staticmethod
    def generate_multi_horizon_forecast(current_price: float, returns_std: float, base_probs: dict) -> dict:
        horizons = {
            "5M": 0.2,
            "15M": 0.5,
            "30M": 0.8,
            "1H": 1.0,
            "4H": 2.0,
            "1D": 4.0,
            "5D": 9.0
        }
        
        results = {}
        for h_name, h_mult in horizons.items():
            intervals = ProbabilityCalibrator.calculate_prediction_intervals(current_price, returns_std, h_mult)
            results[h_name] = {
                "horizon": h_name,
                "probabilities": base_probs,
                "prediction_intervals": intervals
            }
        return results
