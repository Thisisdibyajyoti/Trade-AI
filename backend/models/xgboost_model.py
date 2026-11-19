import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
import xgboost as xgb
import logging

logger = logging.getLogger("xgboost_model")

class XGBoostModel:
    """
    Model A: XGBoost / GradientBoosting for structured market features.
    Predicts 3-class market direction (0: DOWN, 1: SIDEWAYS, 2: UP).
    """

    def __init__(self):
        self.clf = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.05,
            objective='multi:softprob',
            num_class=3,
            random_state=42
        )
        self.trained = False
        self.feature_cols = []

    def prepare_target(self, df: pd.DataFrame, horizon_candles: int = 1) -> pd.DataFrame:
        target_df = df.copy()
        future_return = target_df['Close'].shift(-horizon_candles) / target_df['Close'] - 1.0
        
        # Volatility-adjusted threshold
        vol = target_df['returns'].rolling(20).std().shift(-horizon_candles).fillna(0.005)
        threshold = 0.25 * vol
        
        # 0: DOWN, 1: SIDEWAYS, 2: UP
        conditions = [
            (future_return < -threshold),
            (future_return >= -threshold) & (future_return <= threshold),
            (future_return > threshold)
        ]
        target_df['target'] = np.select(conditions, [0, 1, 2], default=1)
        return target_df

    def fit(self, df: pd.DataFrame, feature_cols: list, horizon_candles: int = 1):
        df_target = self.prepare_target(df, horizon_candles)
        # Drop last N candles where target is unknown
        df_clean = df_target.iloc[:-horizon_candles].dropna(subset=feature_cols + ['target'])
        
        if len(df_clean) < 50:
            logger.warning("Not enough samples to train XGBoost model")
            return False

        X = df_clean[feature_cols].values
        y = df_clean['target'].values
        
        self.feature_cols = feature_cols
        try:
            self.clf.fit(X, y)
            self.trained = True
            logger.info("XGBoost model trained successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to fit XGBoost: {e}")
            # Fallback to sklearn GradientBoosting
            fallback_clf = GradientBoostingClassifier(n_estimators=50, max_depth=3)
            fallback_clf.fit(X, y)
            self.clf = fallback_clf
            self.trained = True
            return True

    def predict_proba(self, current_features: pd.DataFrame) -> dict:
        if not self.trained:
            return {"UP": 0.333, "DOWN": 0.333, "SIDEWAYS": 0.334}

        X_latest = current_features[self.feature_cols].iloc[-1:].values
        probs = self.clf.predict_proba(X_latest)[0]
        
        # Order: 0 -> DOWN, 1 -> SIDEWAYS, 2 -> UP
        return {
            "DOWN": float(round(probs[0], 4)),
            "SIDEWAYS": float(round(probs[1], 4)),
            "UP": float(round(probs[2], 4))
        }
