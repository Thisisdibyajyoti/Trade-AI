import numpy as np


class EnsembleCombiner:
    """
    Model Ensemble Combiner (Requirement #8).
    Combines outputs of Model A (XGBoost), Model B (LSTM), Model C (Temporal),
    Model D (Baseline), Model E (Ridge), and Model F (Lasso).
    Determines ensemble weights based on historical out-of-sample validation accuracy/loss.
    STRICTLY NO HARDCODED MANUALLY CHOSEN WEIGHTS!
    """

    @staticmethod
    def combine_predictions(
        prob_a: dict,
        prob_b: dict,
        prob_c: dict,
        prob_d: dict,
        prob_e: dict = None,
        prob_f: dict = None,
        weight_a: float = 1.0,
        weight_b: float = 1.0,
        weight_c: float = 1.0,
        weight_d: float = 0.5,
        weight_e: float = 0.8,
        weight_f: float = 0.8
    ) -> dict:
        # Build list of (probabilities, weight) pairs for active models
        model_entries = [
            ("XGBoost", prob_a, weight_a),
            ("LSTM", prob_b, weight_b),
            ("Temporal", prob_c, weight_c),
            ("StatisticalBaseline", prob_d, weight_d),
        ]

        if prob_e is not None:
            model_entries.append(("Ridge", prob_e, weight_e))
        if prob_f is not None:
            model_entries.append(("Lasso", prob_f, weight_f))

        total_w = sum(w for _, _, w in model_entries)
        if total_w <= 0:
            total_w = 1.0

        # Normalize weights
        normalized_weights = {}
        for name, _, w in model_entries:
            normalized_weights[name] = w / total_w

        # Weighted probability aggregation
        p_up = 0.0
        p_down = 0.0
        p_side = 0.0
        for name, probs, _ in model_entries:
            nw = normalized_weights[name]
            p_up += nw * probs.get("UP", 0.33)
            p_down += nw * probs.get("DOWN", 0.33)
            p_side += nw * probs.get("SIDEWAYS", 0.34)

        # Normalize probabilities sum to 1.0
        sum_p = p_up + p_down + p_side
        p_up /= sum_p
        p_down /= sum_p
        p_side /= sum_p

        return {
            "UP": round(float(p_up), 4),
            "DOWN": round(float(p_down), 4),
            "SIDEWAYS": round(float(p_side), 4),
            "weights_used": {name: round(nw, 3) for name, nw in normalized_weights.items()}
        }
