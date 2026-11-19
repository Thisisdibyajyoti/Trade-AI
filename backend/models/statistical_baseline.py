import numpy as np
import pandas as pd
from scipy.stats import norm

class StatisticalBaselineModel:
    """
    Model D: Simple statistical baseline (Historical Return Distribution + Volatility Drift Model).
    Used as benchmark to ensure complex models are only trusted if they outperform baseline.
    """

    def __init__(self):
        self.mean_return = 0.0
        self.std_return = 0.01
        self.up_prob = 0.5
        self.down_prob = 0.5
        self.sideways_prob = 0.0
        self.trained = False

    def fit(self, train_returns: pd.Series):
        clean_returns = train_returns.dropna().values
        if len(clean_returns) == 0:
            return
            
        self.mean_return = float(np.mean(clean_returns))
        self.std_return = float(np.std(clean_returns) + 1e-6)
        
        # Threshold for sideways move (e.g. within 0.2 * std)
        threshold = 0.2 * self.std_return
        
        up_count = np.sum(clean_returns > threshold)
        down_count = np.sum(clean_returns < -threshold)
        sideways_count = np.sum((clean_returns >= -threshold) & (clean_returns <= threshold))
        total = len(clean_returns)
        
        self.up_prob = float(up_count / total)
        self.down_prob = float(down_count / total)
        self.sideways_prob = float(sideways_count / total)
        self.trained = True

    def predict_probabilities(self, current_return: float = 0.0) -> dict:
        """
        Returns statistical probabilities based on historical distribution.
        """
        if not self.trained:
            return {"UP": 0.333, "DOWN": 0.333, "SIDEWAYS": 0.334}
            
        return {
            "UP": round(self.up_prob, 4),
            "DOWN": round(self.down_prob, 4),
            "SIDEWAYS": round(self.sideways_prob, 4)
        }

    def predict_price_range(self, last_price: float, z_score: float = 1.96) -> tuple[float, float]:
        """
        Calculates price interval based on parametric normal distribution of returns.
        """
        lower = last_price * (1 + self.mean_return - z_score * self.std_return)
        upper = last_price * (1 + self.mean_return + z_score * self.std_return)
        return (round(lower, 2), round(upper, 2))
