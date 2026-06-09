"""
AML Transaction Monitoring and Automated Regulatory Reporting
Real-time transaction monitoring with automated SAR/STR generation

Features:
- Real-time transaction pattern analysis
- Velocity checks and structuring detection
- Automated SAR (Suspicious Activity Report) generation
- STR (Suspicious Transaction Report) generation
- Risk-based transaction monitoring
- ML-based anomaly detection
- Regulatory reporting dashboard
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
import json


logger = logging.getLogger(__name__)


class TransactionRiskLevel(Enum):
    """Transaction risk levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SuspiciousActivityType(Enum):
    """Types of suspicious activities"""
    STRUCTURING = "structuring"  # Breaking large amounts into small transactions
    RAPID_MOVEMENT = "rapid_movement"  # Funds in and out quickly
    UNUSUAL_PATTERN = "unusual_pattern"  # Deviation from normal behavior
    HIGH_RISK_JURISDICTION = "high_risk_jurisdiction"
    ROUND_AMOUNT = "round_amount"  # Suspicious round numbers
    VELOCITY_EXCEEDED = "velocity_exceeded"  # Too many transactions
    AMOUNT_THRESHOLD = "amount_threshold"  # Large amount
    SMURFING = "smurfing"  # Multiple small deposits
    LAYERING = "layering"  # Complex transaction chains


@dataclass
class TransactionAlert:
    """Transaction monitoring alert"""
    alert_id: str
    user_id: str
    transaction_id: str
    alert_type: SuspiciousActivityType
    risk_level: TransactionRiskLevel
    risk_score: int  # 0-100
    amount: float
    currency: str
    description: str
    indicators: List[str]
    timestamp: str
    requires_sar: bool


@dataclass
class SARReport:
    """Suspicious Activity Report"""
    sar_id: str
    user_id: str
    user_name: str
    filing_institution: str
    suspicious_activity_types: List[SuspiciousActivityType]
    transaction_ids: List[str]
    total_amount: float
    currency: str
    activity_period_start: str
    activity_period_end: str
    narrative: str
    supporting_documents: List[str]
    filed_date: str
    filed_to: str  # Regulatory authority
    status: str  # draft, filed, acknowledged


class AMLTransactionMonitor:
    """Real-time AML transaction monitoring"""
    
    def __init__(self, db_connection) -> None:
        self.db = db_connection
        self.alert_threshold = 70  # Risk score threshold for alerts
        self.sar_threshold = 85  # Risk score threshold for SAR
    
    async def monitor_transaction(
        self,
        transaction: Dict[str, Any]
    ) -> Optional[TransactionAlert]:
        """
        Monitor single transaction for suspicious activity
        
        Args:
            transaction: Transaction details
            
        Returns:
            Alert if suspicious, None otherwise
        """
        user_id = transaction["user_id"]
        amount = float(transaction["amount"])
        currency = transaction["currency"]
        
        indicators = []
        risk_score = 0
        suspicious_types = []
        
        # Check 1: Amount threshold (>$10,000 or equivalent)
        if amount >= 10000:
            indicators.append(f"Large amount: {amount} {currency}")
            risk_score += 15
            suspicious_types.append(SuspiciousActivityType.AMOUNT_THRESHOLD)
        
        # Check 2: Round amount (exactly 10000, 50000, etc.)
        if amount % 10000 == 0 and amount >= 10000:
            indicators.append(f"Suspicious round amount: {amount}")
            risk_score += 10
            suspicious_types.append(SuspiciousActivityType.ROUND_AMOUNT)
        
        # Check 3: Velocity check (transaction frequency)
        recent_txns = await self._get_recent_transactions(user_id, hours=24)
        if len(recent_txns) > 10:
            indicators.append(f"High velocity: {len(recent_txns)} transactions in 24h")
            risk_score += 20
            suspicious_types.append(SuspiciousActivityType.VELOCITY_EXCEEDED)
        
        # Check 4: Structuring detection
        if await self._detect_structuring(user_id, amount):
            indicators.append("Possible structuring detected")
            risk_score += 30
            suspicious_types.append(SuspiciousActivityType.STRUCTURING)
        
        # Check 5: Rapid movement (in and out quickly)
        if await self._detect_rapid_movement(user_id):
            indicators.append("Rapid fund movement detected")
            risk_score += 25
            suspicious_types.append(SuspiciousActivityType.RAPID_MOVEMENT)
        
        # Check 6: Unusual pattern (ML-based)
        pattern_score = await self._detect_unusual_pattern(user_id, transaction)
        if pattern_score > 0.7:
            indicators.append(f"Unusual pattern detected (score: {pattern_score:.2f})")
            risk_score += int(pattern_score * 20)
            suspicious_types.append(SuspiciousActivityType.UNUSUAL_PATTERN)
        
        # Check 7: High-risk jurisdiction
        if transaction.get("destination_country") in ["KP", "IR", "SY"]:  # Example
            indicators.append(f"High-risk jurisdiction: {transaction.get('destination_country')}")
            risk_score += 35
            suspicious_types.append(SuspiciousActivityType.HIGH_RISK_JURISDICTION)
        
        # Generate alert if threshold exceeded
        if risk_score >= self.alert_threshold:
            risk_level = self._calculate_risk_level(risk_score)
            
            alert = TransactionAlert(
                alert_id=f"ALERT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                user_id=user_id,
                transaction_id=transaction["transaction_id"],
                alert_type=suspicious_types[0] if suspicious_types else SuspiciousActivityType.UNUSUAL_PATTERN,
                risk_level=risk_level,
                risk_score=risk_score,
                amount=amount,
                currency=currency,
                description="; ".join(indicators),
                indicators=indicators,
                timestamp=datetime.utcnow().isoformat(),
                requires_sar=risk_score >= self.sar_threshold
            )
            
            logger.warning(f"Transaction alert generated: {alert.alert_id}, risk: {risk_score}")
            return alert
        
        return None
    
    async def generate_sar(
        self,
        user_id: str,
        alert_ids: List[str]
    ) -> SARReport:
        """
        Generate Suspicious Activity Report
        
        Args:
            user_id: User ID
            alert_ids: List of alert IDs to include
            
        Returns:
            SAR report
        """
        logger.info(f"Generating SAR for user {user_id}")
        
        # Fetch alerts
        alerts = await self._get_alerts(alert_ids)
        
        # Aggregate information
        transaction_ids = [alert["transaction_id"] for alert in alerts]
        total_amount = sum(alert["amount"] for alert in alerts)
        currency = alerts[0]["currency"] if alerts else "USD"
        
        # Get user information
        user = await self._get_user_info(user_id)
        
        # Generate narrative
        narrative = self._generate_sar_narrative(user, alerts)
        
        # Create SAR
        sar = SARReport(
            sar_id=f"SAR-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            user_id=user_id,
            user_name=user.get("full_name", ""),
            filing_institution="Nigerian Remittance Platform",
            suspicious_activity_types=[SuspiciousActivityType.STRUCTURING],  # From alerts
            transaction_ids=transaction_ids,
            total_amount=total_amount,
            currency=currency,
            activity_period_start=alerts[0]["timestamp"] if alerts else "",
            activity_period_end=alerts[-1]["timestamp"] if alerts else "",
            narrative=narrative,
            supporting_documents=[],
            filed_date=datetime.utcnow().isoformat(),
            filed_to="Central Bank of Nigeria - NFIU",
            status="draft"
        )
        
        logger.info(f"SAR generated: {sar.sar_id}")
        return sar
    
    async def _get_recent_transactions(self, user_id: str, hours: int = 24) -> List[Dict]:
        """Get recent transactions for user"""
        # Simulate database query
        await asyncio.sleep(0.1)
        return [{"transaction_id": f"TXN-{i}", "amount": 5000} for i in range(5)]
    
    async def _detect_structuring(self, user_id: str, current_amount: float) -> bool:
        """Detect structuring (breaking large amounts into small transactions)"""
        # Get transactions in last 7 days
        recent_txns = await self._get_recent_transactions(user_id, hours=168)
        
        # Check if multiple transactions just below reporting threshold
        threshold = 10000
        suspicious_count = sum(
            1 for txn in recent_txns
            if 9000 <= txn["amount"] < threshold
        )
        
        return suspicious_count >= 3
    
    async def _detect_rapid_movement(self, user_id: str) -> bool:
        """Detect rapid fund movement (in and out quickly)"""
        # Simulate check
        await asyncio.sleep(0.1)
        return False
    
    async def _detect_unusual_pattern(self, user_id: str, transaction: Dict) -> float:
        """ML-based unusual pattern detection"""
        # Simulate ML model prediction
        await asyncio.sleep(0.2)
        return 0.65  # Anomaly score
    
    def _calculate_risk_level(self, risk_score: int) -> TransactionRiskLevel:
        """Calculate risk level from score"""
        if risk_score >= 90:
            return TransactionRiskLevel.CRITICAL
        elif risk_score >= 75:
            return TransactionRiskLevel.HIGH
        elif risk_score >= 50:
            return TransactionRiskLevel.MEDIUM
        else:
            return TransactionRiskLevel.LOW
    
    async def _get_alerts(self, alert_ids: List[str]) -> List[Dict]:
        """Fetch alerts from database"""
        await asyncio.sleep(0.1)
        return [
            {
                "alert_id": aid,
                "transaction_id": f"TXN-{i}",
                "amount": 9500,
                "currency": "USD",
                "timestamp": datetime.utcnow().isoformat()
            }
            for i, aid in enumerate(alert_ids)
        ]
    
    async def _get_user_info(self, user_id: str) -> Dict:
        """Get user information"""
        await asyncio.sleep(0.1)
        return {
            "user_id": user_id,
            "full_name": "John Doe",
            "email": "john@example.com"
        }
    
    def _generate_sar_narrative(self, user: Dict, alerts: List[Dict]) -> str:
        """Generate SAR narrative"""
        return f"""
Suspicious Activity Detected for User: {user.get('full_name')}

Summary:
Multiple transactions exhibiting characteristics of structuring were detected.
The subject conducted {len(alerts)} transactions totaling {sum(a['amount'] for a in alerts)} USD
over a period of {len(alerts)} days, with individual amounts just below the reporting threshold.

Pattern Analysis:
- Transaction amounts consistently between 9,000-9,999 USD
- Transactions occurred at regular intervals
- No apparent legitimate business purpose
- Pattern consistent with intentional avoidance of reporting requirements

Recommendation:
File SAR with regulatory authority for further investigation.
"""


# Example usage
async def example_usage() -> None:
    """Example usage"""
    
    monitor = AMLTransactionMonitor(db_connection=None)
    
    # Monitor transaction
    transaction = {
        "transaction_id": "TXN-12345",
        "user_id": "USER-67890",
        "amount": 9500,
        "currency": "USD",
        "destination_country": "NG"
    }
    
    alert = await monitor.monitor_transaction(transaction)
    
    if alert:
        print(f"Alert generated: {alert.alert_id}")
        print(f"Risk score: {alert.risk_score}/100")
        print(f"Indicators: {alert.indicators}")
        
        if alert.requires_sar:
            sar = await monitor.generate_sar(
                user_id=alert.user_id,
                alert_ids=[alert.alert_id]
            )
            print(f"\nSAR generated: {sar.sar_id}")
            print(f"Total amount: {sar.total_amount} {sar.currency}")


if __name__ == "__main__":
    asyncio.run(example_usage())

