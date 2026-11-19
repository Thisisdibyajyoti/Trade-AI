import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
import logging

logger = logging.getLogger("lasso_model")


class LassoModel:
    """
    Model F: Lasso-Regularized Logistic Regression (L1 Regularization) for market direction.
    Uses L1 penalty to perform automatic feature selection — zeros out irrelevant features.
    Predicts 3-class market direction (0: DOWN, 1: SIDEWAYS, 2: UP).

    Key advantages for trading:
    - Automatic feature selection: drives irrelevant indicator coefficients to exactly zero
    - Reveals which technical indicators actually matter for prediction
    - Reduces overfitting by eliminating noise features (e.g., redundant oscillators)
    - Sparse coefficient vector = interpretable model that shows what drives predictions
    """

    def __init__(self, C: float = 1.0, auto_tune: bool = True):
        # C = inverse of regularization strength (smaller C = stronger L1 penalty)
        self.C = C
        self.auto_tune = auto_tune
        self.clf = LogisticRegression(
            penalty='l1', C=C, solver='saga', multi_class='multinomial',
            max_iter=2000, random_state=42
        )
        self.scaler = StandardScaler()
        self.trained = False
        self.feature_cols = []
        self.best_C = C
        self.coef_ = None
        self.selected_features = []

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

    def _tune_C(self, X: np.ndarray, y: np.ndarray) -> float:
        """Cross-validated inverse-regularization strength selection."""
        C_candidates = [0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0]
        best_C = self.C
        best_score = -np.inf

        for c in C_candidates:
            clf = LogisticRegression(
                penalty='l1', C=c, solver='saga', multi_class='multinomial',
                max_iter=2000, random_state=42
            )
            try:
                scores = cross_val_score(clf, X, y, cv=min(5, len(X) // 10), scoring='accuracy')
                mean_score = np.mean(scores)
                if mean_score > best_score:
                    best_score = mean_score
                    best_C = c
            except Exception:
                continue

        logger.info(f"Lasso C tuning: best_C={best_C}, CV accuracy={best_score:.4f}")
        return best_C

    def fit(self, df: pd.DataFrame, feature_cols: list, horizon_candles: int = 1) -> bool:
        df_target = self.prepare_target(df, horizon_candles)
        df_clean = df_target.iloc[:-horizon_candles].dropna(subset=feature_cols + ['target'])

        if len(df_clean) < 50:
            logger.warning("Not enough samples to train Lasso model")
            return False

        self.feature_cols = feature_cols
        X = self.scaler.fit_transform(df_clean[feature_cols].values)
        y = df_clean['target'].values

        # Auto-tune C via cross-validation
        if self.auto_tune and len(df_clean) > 100:
            self.best_C = self._tune_C(X, y)
            self.clf = LogisticRegression(
                penalty='l1', C=self.best_C, solver='saga', multi_class='multinomial',
                max_iter=2000, random_state=42
            )

        try:
            self.clf.fit(X, y)
            self.trained = True
            self.coef_ = self.clf.coef_
            self._identify_selected_features()
            logger.info(
                f"Lasso model trained successfully (C={self.best_C}), "
                f"{len(self.selected_features)}/{len(feature_cols)} features selected"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to fit Lasso model: {e}")
            return False

    def _identify_selected_features(self):
        """Identifies which features have non-zero coefficients (L1 selection)."""
        if self.coef_ is None:
            self.selected_features = []
            return

        # A feature is "selected" if any class has a non-zero coefficient for it
        non_zero_mask = np.any(np.abs(self.coef_) > 1e-8, axis=0)
        self.selected_features = [
            self.feature_cols[i] for i in range(len(self.feature_cols))
            if i < len(non_zero_mask) and non_zero_mask[i]
        ]

    def predict_proba(self, current_features: pd.DataFrame) -> dict:
        if not self.trained:
            return {"UP": 0.333, "DOWN": 0.333, "SIDEWAYS": 0.334}

        X_latest = self.scaler.transform(current_features[self.feature_cols].iloc[-1:].values)
        probs = self.clf.predict_proba(X_latest)[0]

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

        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

    def get_selected_features_report(self) -> dict:
        """Returns L1 feature selection report: which features survived, which were zeroed out."""
        if not self.trained:
            return {"selected": [], "eliminated": [], "sparsity_ratio": 0.0}

        eliminated = [f for f in self.feature_cols if f not in self.selected_features]
        sparsity_ratio = len(eliminated) / max(1, len(self.feature_cols))

        return {
            "selected": self.selected_features,
            "eliminated": eliminated,
            "total_features": len(self.feature_cols),
            "selected_count": len(self.selected_features),
            "eliminated_count": len(eliminated),
            "sparsity_ratio": round(sparsity_ratio, 4)
        }
