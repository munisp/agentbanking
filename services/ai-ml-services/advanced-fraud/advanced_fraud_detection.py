"""
Advanced Fraud Detection — deterministic heuristic scorer

This is a transparent feature-averaging heuristic over the transaction's own
attributes (amount, hour, international flag, account age). It is NOT a neural
network and no random noise is injected into the score: the same transaction
always yields the same fraud score.
"""

from typing import Dict


class AdvancedFraudDetection:
    """Deterministic heuristic fraud scoring (no learned weights, no RNG)."""

    async def analyze_transaction(self, transaction: Dict) -> Dict:
        """Analyze transaction for fraud"""
        try:
            features = [
                transaction.get("amount", 0) / 10000,
                transaction.get("hour", 12) / 24,
                1 if transaction.get("is_international", False) else 0,
                transaction.get("user_age_days", 30) / 365
            ]

            # Deterministic heuristic score — no random jitter.
            fraud_score = min(1.0, sum(features) / len(features))

            if fraud_score > 0.8:
                risk_level = "high"
                action = "block"
            elif fraud_score > 0.5:
                risk_level = "medium"
                action = "review"
            else:
                risk_level = "low"
                action = "approve"

            return {
                "status": "success",
                "fraud_score": round(fraud_score, 3),
                "risk_level": risk_level,
                "recommended_action": action,
                "scoring_method": "deterministic_heuristic",
                "factors": {
                    "amount_risk": features[0],
                    "time_risk": features[1],
                    "location_risk": features[2],
                    "account_age_risk": features[3]
                }
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}
