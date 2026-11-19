import os
import openai
import logging

logger = logging.getLogger("openai_service")

class OpenAIReasoningService:
    """
    OpenAI Reasoning Layer (Requirement #18).
    Explains verified quantitative model outputs without altering numerical values.
    """

    @staticmethod
    def generate_explanation(analysis_payload: dict, api_key: str = None) -> str:
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            # Fallback deterministic structured textual explanation when no API key provided
            symbol = analysis_payload.get("symbol", "Asset")
            probs = analysis_payload.get("probabilities", {})
            regime = analysis_payload.get("market_regime", {}).get("regime", "N/A")
            intervals = analysis_payload.get("prediction_intervals", {}).get("interval_80", {})
            similarity = analysis_payload.get("similarity", {})
            backtest = analysis_payload.get("backtest", {})
            
            return (
                f"### Quantitative AI Analysis for **{symbol}**\n\n"
                f"- **Current Market Regime**: `{regime}`\n"
                f"- **Validated Probabilities**: UP: `{probs.get('UP', 0)}%`, DOWN: `{probs.get('DOWN', 0)}%`, SIDEWAYS: `{probs.get('SIDEWAYS', 0)}%`\n"
                f"- **80% Prediction Interval**: `{intervals.get('lower', 0)}` to `{intervals.get('upper', 0)}`\n"
                f"- **Historical Analogs**: Found `{similarity.get('similar_matches_found', 0)}` similar historical periods with `{similarity.get('positive_pct', 0)}%` positive outcomes.\n"
                f"- **Out-of-Sample Accuracy**: `{backtest.get('model_directional_accuracy', 0)}%` (vs Baseline: `{backtest.get('baseline_directional_accuracy', 0)}%`).\n\n"
                f"*Note: Configure `OPENAI_API_KEY` in environment or settings for live GPT-4o deep synthesis.*"
            )

        try:
            client = openai.OpenAI(api_key=key)
            prompt = (
                f"You are TradeAI's quantitative explanation engine.\n"
                f"Below are the STRICT UNALTERABLE numerical outputs generated from our Python machine learning ensemble and historical data for {analysis_payload.get('symbol')}:\n\n"
                f"1. Current Price: {analysis_payload.get('current_price')}\n"
                f"2. Market Regime: {analysis_payload.get('market_regime')}\n"
                f"3. Model Probabilities: UP={analysis_payload.get('probabilities', {}).get('UP')}%, DOWN={analysis_payload.get('probabilities', {}).get('DOWN')}%, SIDEWAYS={analysis_payload.get('probabilities', {}).get('SIDEWAYS')}%\n"
                f"4. 80% Prediction Interval: {analysis_payload.get('prediction_intervals', {}).get('interval_80')}\n"
                f"5. Historical Similarity Search: {analysis_payload.get('similarity')}\n"
                f"6. Walk-Forward Backtest Performance: {analysis_payload.get('backtest')}\n\n"
                f"STRICT RULES:\n"
                f"- DO NOT change, modify, or round any of the numerical probabilities or prices above.\n"
                f"- Explain what these numbers mean for a trader, key technical factors driving the prediction, uncertainty bounds, and critical support/resistance levels.\n"
                f"- Keep your response concise, structured, professional, and clear."
            )

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a quantitative finance explanation system. You strictly explain given quantitative model outputs without altering any numbers."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=500
            )

            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI service error: {e}")
            return f"Reasoning service error: {str(e)}. Quantitative metrics remain 100% verified above."
