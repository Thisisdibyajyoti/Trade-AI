import numpy as np
import pandas as pd
import logging
from typing import Optional

logger = logging.getLogger("explainability")


class ExplainableAI:
    """
    Explainable AI (XAI) Engine for the TradeAI ensemble prediction system.

    Provides multi-level model interpretability:
    1. Feature Importance - Which indicators drive predictions (aggregated across models)
    2. Feature Selection Report - Which features L1/Lasso kept vs eliminated
    3. Model Agreement Analysis - How aligned are individual models on the prediction
    4. Prediction Decomposition - Per-model contribution breakdown
    5. Decision Rationale - Human-readable reasoning for the ensemble output
    6. Confidence Assessment - Risk-adjusted reliability score

    All explanations are grounded in actual model internals (coefficients, probabilities,
    decision boundaries) — never fabricated or hallucinated post-hoc.
    """

    @staticmethod
    def generate_full_explanation(
        model_predictions: dict,
        ensemble_result: dict,
        feature_df: pd.DataFrame,
        feature_cols: list,
        ridge_model=None,
        lasso_model=None,
        xgboost_model=None,
        backtest_result: dict = None,
        market_regime: dict = None
    ) -> dict:
        """
        Generates a comprehensive XAI report combining all explanation dimensions.

        Args:
            model_predictions: Dict of model_name -> probability dict (e.g. {"XGBoost": {"UP": 0.4, ...}})
            ensemble_result: Combined ensemble prediction output
            feature_df: DataFrame with features for the latest prediction
            feature_cols: List of feature column names
            ridge_model: Trained RidgeModel instance (optional)
            lasso_model: Trained LassoModel instance (optional)
            xgboost_model: Trained XGBoostModel instance (optional)
            backtest_result: Walk-forward backtest results dict
            market_regime: Market regime detection result dict
        """
        xai_report = {
            "status": "SUCCESS",
            "feature_importance": ExplainableAI._aggregate_feature_importance(
                ridge_model, lasso_model, xgboost_model, feature_cols
            ),
            "feature_selection": ExplainableAI._get_feature_selection_report(lasso_model),
            "model_agreement": ExplainableAI._analyze_model_agreement(model_predictions),
            "prediction_decomposition": ExplainableAI._decompose_prediction(
                model_predictions, ensemble_result
            ),
            "confidence_assessment": ExplainableAI._assess_confidence(
                model_predictions, ensemble_result, backtest_result
            ),
            "decision_rationale": ExplainableAI._generate_rationale(
                ensemble_result, model_predictions, market_regime, backtest_result
            ),
            "top_drivers": ExplainableAI._identify_top_drivers(
                feature_df, feature_cols, ridge_model, lasso_model, xgboost_model
            )
        }

        return xai_report

    @staticmethod
    def _aggregate_feature_importance(
        ridge_model=None, lasso_model=None, xgboost_model=None, feature_cols: list = None
    ) -> dict:
        """Aggregates feature importance across all models that expose coefficients/importances."""
        importances = {}

        # Ridge coefficients
        ridge_imp = {}
        if ridge_model and hasattr(ridge_model, 'get_feature_importance'):
            ridge_imp = ridge_model.get_feature_importance()
            for feat, val in ridge_imp.items():
                importances.setdefault(feat, []).append(val)

        # Lasso coefficients
        lasso_imp = {}
        if lasso_model and hasattr(lasso_model, 'get_feature_importance'):
            lasso_imp = lasso_model.get_feature_importance()
            for feat, val in lasso_imp.items():
                importances.setdefault(feat, []).append(val)

        # XGBoost feature importances
        xgb_imp = {}
        if xgboost_model and hasattr(xgboost_model, 'clf') and xgboost_model.trained:
            try:
                raw_imp = xgboost_model.clf.feature_importances_
                for i, col in enumerate(feature_cols or []):
                    if i < len(raw_imp):
                        xgb_imp[col] = float(raw_imp[i])
                        importances.setdefault(col, []).append(float(raw_imp[i]))
            except Exception:
                pass

        # Average across models
        aggregated = {}
        for feat, values in importances.items():
            aggregated[feat] = float(round(np.mean(values), 6))

        # Sort descending
        sorted_imp = dict(sorted(aggregated.items(), key=lambda x: x[1], reverse=True))

        # Normalize to percentages
        total = sum(sorted_imp.values()) + 1e-9
        normalized = {k: round(v / total * 100, 2) for k, v in sorted_imp.items()}

        return {
            "aggregated": normalized,
            "per_model": {
                "Ridge": ridge_imp if ridge_imp else None,
                "Lasso": lasso_imp if lasso_imp else None,
                "XGBoost": xgb_imp if xgb_imp else None
            },
            "top_5": list(normalized.keys())[:5]
        }

    @staticmethod
    def _get_feature_selection_report(lasso_model=None) -> dict:
        """Uses Lasso's L1 sparsity to report which features survived selection."""
        if lasso_model and hasattr(lasso_model, 'get_selected_features_report'):
            return lasso_model.get_selected_features_report()
        return {
            "selected": [],
            "eliminated": [],
            "sparsity_ratio": 0.0,
            "note": "Lasso model not available for feature selection analysis"
        }

    @staticmethod
    def _analyze_model_agreement(model_predictions: dict) -> dict:
        """Measures how much individual models agree on the predicted direction."""
        if not model_predictions:
            return {"agreement_score": 0.0, "unanimous": False, "majority_direction": "UNKNOWN"}

        directions = []
        for model_name, probs in model_predictions.items():
            if isinstance(probs, dict) and any(k in probs for k in ["UP", "DOWN", "SIDEWAYS"]):
                best_dir = max(probs, key=probs.get)
                directions.append(best_dir)

        if not directions:
            return {"agreement_score": 0.0, "unanimous": False, "majority_direction": "UNKNOWN"}

        # Count votes
        from collections import Counter
        vote_counts = Counter(directions)
        majority_dir = vote_counts.most_common(1)[0][0]
        majority_count = vote_counts.most_common(1)[0][1]
        total_models = len(directions)

        agreement_score = round(majority_count / total_models, 4)
        unanimous = majority_count == total_models

        # Dissenting models
        dissenters = [
            model_name for model_name, probs in model_predictions.items()
            if isinstance(probs, dict) and max(probs, key=probs.get) != majority_dir
        ]

        return {
            "agreement_score": agreement_score,
            "agreement_pct": round(agreement_score * 100, 1),
            "unanimous": unanimous,
            "majority_direction": majority_dir,
            "vote_distribution": dict(vote_counts),
            "total_models": total_models,
            "dissenting_models": dissenters
        }

    @staticmethod
    def _decompose_prediction(model_predictions: dict, ensemble_result: dict) -> dict:
        """Shows how each model contributes to the final ensemble probability."""
        decomposition = {}

        weights_used = ensemble_result.get("weights_used", {})

        for model_name, probs in model_predictions.items():
            if not isinstance(probs, dict):
                continue
            weight = weights_used.get(model_name, 0.0)
            predicted_dir = max(probs, key=probs.get) if probs else "UNKNOWN"
            decomposition[model_name] = {
                "probabilities": probs,
                "predicted_direction": predicted_dir,
                "ensemble_weight": weight,
                "weighted_contribution": {
                    k: round(v * weight, 4) for k, v in probs.items()
                }
            }

        return decomposition

    @staticmethod
    def _assess_confidence(
        model_predictions: dict, ensemble_result: dict, backtest_result: dict = None
    ) -> dict:
        """Risk-adjusted confidence score combining model agreement, probability margin, and historical accuracy."""
        # 1. Probability margin (how decisive is the ensemble?)
        probs = {k: v for k, v in ensemble_result.items() if k in ["UP", "DOWN", "SIDEWAYS"]}
        if probs:
            sorted_probs = sorted(probs.values(), reverse=True)
            margin = sorted_probs[0] - (sorted_probs[1] if len(sorted_probs) > 1 else 0)
        else:
            margin = 0.0

        # 2. Model agreement score
        agreement = ExplainableAI._analyze_model_agreement(model_predictions)
        agreement_score = agreement.get("agreement_score", 0.5)

        # 3. Historical accuracy factor
        hist_accuracy = 0.5
        if backtest_result and isinstance(backtest_result, dict):
            hist_accuracy = backtest_result.get("model_directional_accuracy", 50) / 100.0

        # Combined confidence (weighted)
        raw_confidence = (
            0.35 * min(margin * 3, 1.0) +     # Probability margin (0-1)
            0.35 * agreement_score +            # Model agreement (0-1)
            0.30 * hist_accuracy                # Historical accuracy (0-1)
        )

        confidence = round(min(max(raw_confidence, 0.0), 1.0), 4)

        # Confidence tier
        if confidence >= 0.75:
            tier = "HIGH"
            tier_description = "Strong model consensus with decisive probability margin."
        elif confidence >= 0.50:
            tier = "MODERATE"
            tier_description = "Reasonable model alignment, but some divergence exists."
        elif confidence >= 0.30:
            tier = "LOW"
            tier_description = "Significant model disagreement. Exercise caution."
        else:
            tier = "VERY_LOW"
            tier_description = "Models strongly disagree. Prediction is unreliable."

        return {
            "confidence_score": confidence,
            "confidence_pct": round(confidence * 100, 1),
            "tier": tier,
            "tier_description": tier_description,
            "components": {
                "probability_margin": round(margin, 4),
                "model_agreement": round(agreement_score, 4),
                "historical_accuracy": round(hist_accuracy, 4)
            }
        }

    @staticmethod
    def _generate_rationale(
        ensemble_result: dict,
        model_predictions: dict,
        market_regime: dict = None,
        backtest_result: dict = None
    ) -> str:
        """Generates human-readable decision rationale grounded in model internals."""
        parts = []

        # Ensemble direction
        probs = {k: v for k, v in ensemble_result.items() if k in ["UP", "DOWN", "SIDEWAYS"]}
        if probs:
            direction = max(probs, key=probs.get)
            prob_val = probs[direction]
            parts.append(
                f"The ensemble of {len(model_predictions)} models predicts {direction} "
                f"with {prob_val:.1f}% calibrated probability."
            )

        # Model agreement
        agreement = ExplainableAI._analyze_model_agreement(model_predictions)
        if agreement.get("unanimous"):
            parts.append(
                f"All {agreement['total_models']} models unanimously agree on {agreement['majority_direction']}."
            )
        else:
            parts.append(
                f"{agreement.get('agreement_pct', 0)}% model agreement "
                f"({agreement.get('majority_direction', 'N/A')} majority). "
                f"Dissenting: {', '.join(agreement.get('dissenting_models', []))}."
            )

        # Market regime context
        if market_regime and isinstance(market_regime, dict):
            regime = market_regime.get("regime", "Unknown")
            trend = market_regime.get("trend_status", "")
            parts.append(f"Current market regime: {regime} ({trend}).")

        # Backtest context
        if backtest_result and isinstance(backtest_result, dict):
            acc = backtest_result.get("model_directional_accuracy", 0)
            sharpe = backtest_result.get("sharpe_ratio", 0)
            outperforms = backtest_result.get("outperforms_baseline", False)
            parts.append(
                f"Walk-forward accuracy: {acc}% (Sharpe: {sharpe}). "
                f"{'Outperforms' if outperforms else 'Does NOT outperform'} statistical baseline."
            )

        return " ".join(parts)

    @staticmethod
    def _identify_top_drivers(
        feature_df: pd.DataFrame,
        feature_cols: list,
        ridge_model=None,
        lasso_model=None,
        xgboost_model=None,
        top_n: int = 5
    ) -> list:
        """
        Identifies the top N features driving the current prediction,
        combining importance with the current feature values.
        """
        importance = ExplainableAI._aggregate_feature_importance(
            ridge_model, lasso_model, xgboost_model, feature_cols
        )
        top_features = importance.get("top_5", [])[:top_n]

        drivers = []
        for feat in top_features:
            current_val = None
            if feat in feature_df.columns and len(feature_df) > 0:
                current_val = float(feature_df[feat].iloc[-1])

            agg_imp = importance.get("aggregated", {}).get(feat, 0.0)

            signal = "NEUTRAL"
            if current_val is not None:
                if feat in ['rsi_14']:
                    if current_val > 70:
                        signal = "OVERBOUGHT"
                    elif current_val < 30:
                        signal = "OVERSOLD"
                elif feat in ['macd', 'macd_signal']:
                    signal = "BULLISH" if current_val > 0 else "BEARISH"
                elif feat in ['momentum_5', 'momentum_10', 'returns']:
                    signal = "BULLISH" if current_val > 0 else "BEARISH"
                elif feat in ['trend_strength']:
                    if current_val > 1:
                        signal = "STRONG_UPTREND"
                    elif current_val < -1:
                        signal = "STRONG_DOWNTREND"
                    else:
                        signal = "RANGE_BOUND"
                elif feat in ['bb_pct_b']:
                    if current_val > 0.8:
                        signal = "NEAR_UPPER_BAND"
                    elif current_val < 0.2:
                        signal = "NEAR_LOWER_BAND"
                elif feat in ['volatility_20', 'atr_14', 'bb_bandwidth']:
                    signal = "HIGH_VOLATILITY" if current_val > feature_df[feat].quantile(0.75) else "NORMAL"

            drivers.append({
                "feature": feat,
                "importance_pct": agg_imp,
                "current_value": round(current_val, 6) if current_val is not None else None,
                "signal": signal
            })

        return drivers
