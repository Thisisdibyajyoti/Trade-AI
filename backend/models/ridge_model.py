import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
import logging

logger = logging.getLogger("ridge_model")


class RidgeModel:
    """
    Model E: Ridge Classifier (L2 Regularization) for market direction prediction.
    Uses L2 penalty to prevent overfitting on correlated technical indicators.
    Predicts 3-class market direction (0: DOWN, 1: SIDEWAYS, 2: UP).

    Key advantages for trading:
    - Handles multicollinearity among technical features (SMA/EMA overlap, RSI/Stoch correlation)
    - Closed-form solution = fast training, suitable for real-time re-fitting
    - L2 regularization shrinks correlated feature coefficients proportionally
    """

    def __init__(self, alpha: float = 1.0, auto_tune: bool = True):
        self.alpha = alpha
        self.auto_tune = auto_tune
        self.clf = RidgeClassifier(alpha=alpha)
        self.scaler = StandardScaler()
        self.trained = False
        self.feature_cols = []
        self.best_alpha = alpha
        self.coef_ = None

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

    def _tune_alpha(self, X: np.ndarray, y: np.ndarray) -> float:
        """Cross-validated alpha selection from candidate grid."""
        alphas = [0.01, 0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0]
        best_alpha = self.alpha
        best_score = -np.inf

        for a in alphas:
            clf = RidgeClassifier(alpha=a)
            try:
                scores = cross_val_score(clf, X, y, cv=min(5, len(X) // 10), scoring='accuracy')
                mean_score = np.mean(scores)
                if mean_score > best_score:
                    best_score = mean_score
                    best_alpha = a
            except Exception:
                continue

        logger.info(f"Ridge alpha tuning: best_alpha={best_alpha}, CV accuracy={best_score:.4f}")
        return best_alpha

    def fit(self, df: pd.DataFrame, feature_cols: list, horizon_candles: int = 1) -> bool:
        df_target = self.prepare_target(df, horizon_candles)
        df_clean = df_target.iloc[:-horizon_candles].dropna(subset=feature_cols + ['target'])

        if len(df_clean) < 50:
            logger.warning("Not enough samples to train Ridge model")
            return False

        self.feature_cols = feature_cols
        X = self.scaler.fit_transform(df_clean[feature_cols].values)
        y = df_clean['target'].values

        # Auto-tune alpha via cross-validation
        if self.auto_tune and len(df_clean) > 100:
            self.best_alpha = self._tune_alpha(X, y)
            self.clf = RidgeClassifier(alpha=self.best_alpha)

        try:
            self.clf.fit(X, y)
            self.trained = True
            self.coef_ = self.clf.coef_
            logger.info(f"Ridge model trained successfully (alpha={self.best_alpha})")
            return True
        except Exception as e:
            logger.error(f"Failed to fit Ridge model: {e}")
            return False

    def predict_proba(self, current_features: pd.DataFrame) -> dict:
        if not self.trained:
            return {"UP": 0.333, "DOWN": 0.333, "SIDEWAYS": 0.334}

        X_latest = self.scaler.transform(current_features[self.feature_cols].iloc[-1:].values)

        # RidgeClassifier uses decision_function -> convert to pseudo-probabilities via softmax
        d_scores = self.clf.decision_function(X_latest)[0]
        if np.ndim(d_scores) == 0 or (hasattr(d_scores, '__len__') and len(d_scores) == 1):
            # Binary fallback
            d_scores = np.array([-float(d_scores), 0.0, float(d_scores)])

        exp_scores = np.exp(d_scores - np.max(d_scores))
        probs = exp_scores / np.sum(exp_scores)

        return {
            "DOWN": float(round(probs[0], 4)),
            "SIDEWAYS": float(round(probs[1], 4)),
            "UP": float(round(probs[2], 4))
        }

    def get_feature_importance(self) -> dict:
        """Returns absolute coefficient magnitudes as feature importance."""
        if not self.trained or self.coef_ is None:
            return {}

        # Average absolute coefficients across classes
        avg_importance = np.mean(np.abs(self.coef_), axis=0)
        importance = {}
        for i, col in enumerate(self.feature_cols):
            if i < len(avg_importance):
                importance[col] = float(round(avg_importance[i], 6))

        # Sort by importance descending
        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
