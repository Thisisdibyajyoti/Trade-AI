import logging

logger = logging.getLogger("screen_analysis_service")

class ScreenAnalysisService:
    """
    Screen Analysis & Verification Engine (Requirement #19).
    Verifies screen/overlay asset context against live API data feeds.
    Detects price mismatches and pauses predictions if feeds diverge.
    """

    @staticmethod
    def verify_screen_price(screen_symbol: str, screen_price: float, api_price: float, threshold_pct: float = 1.5) -> dict:
        if api_price <= 0 or screen_price <= 0:
            return {
                "valid": False,
                "message": "Invalid price inputs for screen verification."
            }

        diff_pct = abs(screen_price - api_price) / api_price * 100.0

        if diff_pct > threshold_pct:
            return {
                "valid": False,
                "mismatch_detected": True,
                "diff_pct": round(diff_pct, 2),
                "message": f"Displayed price (${screen_price:.2f}) differs from market-data feed (${api_price:.2f}) by {diff_pct:.2f}%. Prediction paused."
            }

        return {
            "valid": True,
            "mismatch_detected": False,
            "diff_pct": round(diff_pct, 2),
            "message": "Screen price synchronized with market-data API feed."
        }
