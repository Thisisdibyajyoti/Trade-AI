import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
import logging

logger = logging.getLogger("historical_similarity_engine")

class MarketRegimeAndSimilarityEngine:
    """
    Market Regime Classifier & Historical Similarity Engine (Requirement #12 & #13).
    Performs vector similarity search (k-NN) to locate historical periods matching current features.
    """

    @staticmethod
    def detect_market_regime(df: pd.DataFrame) -> dict:
        if df is None or len(df) < 20:
            return {"regime": "Unknown", "description": "Insufficient data for regime classification"}

        last_row = df.iloc[-1]
        close = last_row['Close']
        sma_20 = last_row.get('sma_20', close)
        sma_50 = last_row.get('sma_50', close)
        rsi = last_row.get('rsi_14', 50)
        volatility = last_row.get('volatility_20', 0.01)
        adx = last_row.get('adx_14', 20)

        hist_vol_median = df['volatility_20'].median() if 'volatility_20' in df.columns else 0.01

        # Volatility status
        vol_status = "High Volatility" if volatility > 1.3 * hist_vol_median else ("Low Volatility" if volatility < 0.7 * hist_vol_median else "Normal Volatility")

        # Trend status
        if close > sma_20 and sma_20 > sma_50 and rsi > 55:
            trend_status = "Strong Uptrend"
        elif close > sma_50:
            trend_status = "Weak Uptrend"
        elif close < sma_20 and sma_20 < sma_50 and rsi < 45:
            trend_status = "Strong Downtrend"
        elif close < sma_50:
            trend_status = "Weak Downtrend"
        else:
            trend_status = "Sideways Consolidation"

        full_regime = f"{vol_status} {trend_status}".strip()

        return {
            "regime": full_regime,
            "trend_status": trend_status,
            "volatility_status": vol_status,
            "rsi": round(float(rsi), 1),
            "trend_strength_adx": round(float(adx), 1),
            "volatility_ratio": round(float(volatility / (hist_vol_median + 1e-6)), 2)
        }

    @staticmethod
    def search_historical_similarity(df: pd.DataFrame, feature_cols: list, k_neighbors: int = 400, horizon_candles: int = 5) -> dict:
        """
        Extracts current feature vector, searches historical dataset using K-Nearest Neighbors,
        evaluates what happened after those similar historical periods.
        """
        df_clean = df.dropna(subset=feature_cols).reset_index(drop=True)
        if len(df_clean) < 100:
            return {
                "status": "INSUFFICIENT_DATA",
                "similar_matches_found": 0,
                "positive_outcomes": 0,
                "negative_outcomes": 0,
                "neutral_outcomes": 0,
                "win_rate_pct": 0.0
            }

        # Features matrix (exclude last N candles as potential targets)
        X_hist = df_clean[feature_cols].iloc[:-horizon_candles].values
        current_vector = df_clean[feature_cols].iloc[-1:].values

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_hist)
        current_scaled = scaler.transform(current_vector)

        n_samples = len(X_scaled)
        actual_k = min(k_neighbors, max(10, int(n_samples * 0.2)))

        nbrs = NearestNeighbors(n_neighbors=actual_k, metric='cosine')
        nbrs.fit(X_scaled)

        distances, indices = nbrs.kneighbors(current_scaled)
        matched_indices = indices[0]

        # Examine historical outcome after each matched index
        pos_count = 0
        neg_count = 0
        neu_count = 0
        post_returns = []

        returns_vol = df_clean['returns'].rolling(20).std().median()
        thresh = 0.25 * returns_vol if returns_vol > 0 else 0.002

        for idx in matched_indices:
            if idx + horizon_candles < len(df_clean):
                p_initial = df_clean['Close'].iloc[idx]
                p_future = df_clean['Close'].iloc[idx + horizon_candles]
                fut_ret = (p_future - p_initial) / p_initial
                post_returns.append(fut_ret)

                if fut_ret > thresh:
                    pos_count += 1
                elif fut_ret < -thresh:
                    neg_count += 1
                else:
                    neu_count += 1

        total_matches = len(post_returns)
        win_rate = (pos_count / total_matches * 100) if total_matches > 0 else 0.0

        return {
            "status": "SUCCESS",
            "similar_matches_found": total_matches,
            "positive_outcomes": pos_count,
            "negative_outcomes": neg_count,
            "neutral_outcomes": neu_count,
            "positive_pct": round((pos_count / total_matches * 100), 1) if total_matches > 0 else 0.0,
            "negative_pct": round((neg_count / total_matches * 100), 1) if total_matches > 0 else 0.0,
            "neutral_pct": round((neu_count / total_matches * 100), 1) if total_matches > 0 else 0.0,
            "avg_historical_return_pct": round(float(np.mean(post_returns) * 100), 2) if post_returns else 0.0
        }
