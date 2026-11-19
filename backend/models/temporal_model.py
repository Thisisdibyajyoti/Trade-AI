import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeClassifier
from sklearn.preprocessing import StandardScaler
import logging

logger = logging.getLogger("temporal_model")

class TemporalModel:
    """
    Model C: Temporal Feature Network (Linear/Ridge Attention proxy).
    Evaluates temporal cross-feature dependencies with L2 regularization.
    """

    def __init__(self):
        self.clf = RidgeClassifier(alpha=1.0)
        self.scaler = StandardScaler()
        self.trained = False
        self.feature_cols = []

    def fit(self, df: pd.DataFrame, feature_cols: list, horizon_candles: int = 1):
        target_df = df.copy()
        future_return = target_df['Close'].shift(-horizon_candles) / target_df['Close'] - 1.0
        threshold = 0.25 * target_df['returns'].rolling(20).std().shift(-horizon_candles).fillna(0.005)
        
        target_df['target'] = 1 # SIDEWAYS
        target_df.loc[future_return > threshold, 'target'] = 2 # UP
        target_df.loc[future_return < -threshold, 'target'] = 0 # DOWN
        
        df_clean = target_df.dropna(subset=feature_cols + ['target'])
        if len(df_clean) < 30:
            return False

        self.feature_cols = feature_cols
        X = self.scaler.fit_transform(df_clean[feature_cols].values)
        y = df_clean['target'].values
        
        try:
            self.clf.fit(X, y)
            self.trained = True
            return True
        except Exception as e:
            logger.error(f"Temporal Model fit error: {e}")
            return False

    def predict_proba(self, current_features: pd.DataFrame) -> dict:
        if not self.trained:
            return {"UP": 0.333, "DOWN": 0.333, "SIDEWAYS": 0.334}

        X_latest = self.scaler.transform(current_features[self.feature_cols].iloc[-1:].values)
        
        # RidgeClassifier decision function to softmax approximation
        d_scores = self.clf.decision_function(X_latest)[0]
        if d_scores.ndim == 0 or len(d_scores) == 1:
            # Binary fallback
            d_scores = np.array([-d_scores[0], 0.0, d_scores[0]])
            
        exp_scores = np.exp(d_scores - np.max(d_scores))
        probs = exp_scores / np.sum(exp_scores)

        return {
            "DOWN": float(round(probs[0], 4)),
            "SIDEWAYS": float(round(probs[1], 4)),
            "UP": float(round(probs[2], 4))
        }
