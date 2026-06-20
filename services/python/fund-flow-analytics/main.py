"""
Fund Flow Analytics Engine (Python)

Microservice for:
- BNPL portfolio analytics and risk scoring
- FX rate forecasting using moving averages
- Fraud detection on reversals and refunds
- Fund flow anomaly detection
- Settlement reconciliation reporting

Endpoints:
    POST /api/bnpl/analytics         — BNPL portfolio analytics
    POST /api/bnpl/risk-score        — Credit risk scoring for BNPL
    POST /api/fx/forecast            — FX rate forecast
    POST /api/fraud/check-reversal   — Fraud check on reversals
    POST /api/anomaly/detect         — Anomaly detection on fund flows
    POST /api/reconciliation/report  — Generate reconciliation report
    GET  /health                     — Health check
"""

import os
import time
import math
import hashlib
import statistics
from datetime import datetime, timedelta
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

PORT = int(os.environ.get("FUND_FLOW_ANALYTICS_PORT", "8252"))


# ── BNPL Analytics ───────────────────────────────────────────────────────────

def calculate_bnpl_portfolio_analytics(data: dict) -> dict:
    """Analyze BNPL portfolio health."""
    applications = data.get("applications", [])
    total = len(applications)
    if total == 0:
        return {
            "totalApplications": 0,
            "activeLoans": 0,
            "overdueRate": 0.0,
            "defaultRate": 0.0,
            "totalDisbursed": 0.0,
            "totalRepaid": 0.0,
            "portfolioAtRisk": 0.0,
        }

    active = sum(1 for a in applications if a.get("status") == "active")
    overdue = sum(1 for a in applications if a.get("status") == "overdue")
    defaulted = sum(1 for a in applications if a.get("status") == "defaulted")
    total_disbursed = sum(float(a.get("amount", 0)) for a in applications)
    total_repaid = sum(float(a.get("paidAmount", 0)) for a in applications)
    outstanding = total_disbursed - total_repaid

    overdue_amount = sum(
        float(a.get("amount", 0)) - float(a.get("paidAmount", 0))
        for a in applications
        if a.get("status") in ("overdue", "defaulted")
    )

    par = (overdue_amount / outstanding * 100) if outstanding > 0 else 0

    return {
        "totalApplications": total,
        "activeLoans": active,
        "overdueLoans": overdue,
        "defaultedLoans": defaulted,
        "overdueRate": round(overdue / total * 100, 2) if total > 0 else 0,
        "defaultRate": round(defaulted / total * 100, 2) if total > 0 else 0,
        "totalDisbursed": round(total_disbursed, 2),
        "totalRepaid": round(total_repaid, 2),
        "outstandingBalance": round(outstanding, 2),
        "portfolioAtRisk": round(par, 2),
        "collectionRate": round(total_repaid / total_disbursed * 100, 2) if total_disbursed > 0 else 0,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def calculate_credit_risk_score(data: dict) -> dict:
    """Score BNPL applicant credit risk (0-1000)."""
    score = 500  # base score
    factors = []

    # Payment history
    on_time_payments = data.get("onTimePayments", 0)
    late_payments = data.get("latePayments", 0)
    total_payments = on_time_payments + late_payments
    if total_payments > 0:
        payment_ratio = on_time_payments / total_payments
        score += int(payment_ratio * 200 - 100)
        factors.append(f"Payment history: {payment_ratio:.0%} on-time")

    # Existing debt
    existing_debt = data.get("existingDebt", 0)
    monthly_income = data.get("monthlyIncome", 1)
    dti = existing_debt / monthly_income if monthly_income > 0 else 1
    if dti < 0.3:
        score += 100
        factors.append(f"Low DTI: {dti:.0%}")
    elif dti > 0.6:
        score -= 150
        factors.append(f"High DTI: {dti:.0%}")

    # Account age
    account_age_months = data.get("accountAgeMonths", 0)
    if account_age_months > 24:
        score += 50
        factors.append("Established account (>24 months)")
    elif account_age_months < 3:
        score -= 50
        factors.append("New account (<3 months)")

    # Transaction volume
    avg_monthly_volume = data.get("avgMonthlyVolume", 0)
    if avg_monthly_volume > 500000:
        score += 75
        factors.append("High transaction volume")

    score = max(0, min(1000, score))
    risk_level = (
        "low" if score >= 700 else
        "medium" if score >= 400 else
        "high"
    )

    return {
        "score": score,
        "riskLevel": risk_level,
        "maxApprovedAmount": score * 1000 if risk_level != "high" else 0,
        "factors": factors,
        "recommendation": "approve" if score >= 500 else "review" if score >= 300 else "decline",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ── FX Forecasting ──────────────────────────────────────────────────────────

def forecast_fx_rate(data: dict) -> dict:
    """Simple moving average FX rate forecast."""
    historical_rates = data.get("historicalRates", [])
    corridor = data.get("corridor", "NGN-USD")
    periods = data.get("forecastPeriods", 7)

    if len(historical_rates) < 3:
        return {"error": "Need at least 3 historical data points"}

    rates = [float(r) for r in historical_rates]
    current = rates[-1]

    # Simple Moving Average (SMA)
    sma_5 = statistics.mean(rates[-5:]) if len(rates) >= 5 else statistics.mean(rates)
    sma_10 = statistics.mean(rates[-10:]) if len(rates) >= 10 else statistics.mean(rates)

    # Exponential Moving Average (EMA)
    alpha = 2 / (min(len(rates), 10) + 1)
    ema = rates[0]
    for r in rates[1:]:
        ema = alpha * r + (1 - alpha) * ema

    # Volatility
    if len(rates) >= 2:
        returns = [(rates[i] - rates[i - 1]) / rates[i - 1] for i in range(1, len(rates))]
        volatility = statistics.stdev(returns) if len(returns) >= 2 else 0
    else:
        volatility = 0

    # Trend
    trend = "up" if sma_5 > sma_10 else "down" if sma_5 < sma_10 else "flat"

    # Forecast (simple linear extrapolation from EMA)
    daily_change = (ema - sma_10) / max(len(rates), 1)
    forecast = [
        round(ema + daily_change * (i + 1), 6)
        for i in range(periods)
    ]

    return {
        "corridor": corridor,
        "currentRate": current,
        "sma5": round(sma_5, 6),
        "sma10": round(sma_10, 6),
        "ema": round(ema, 6),
        "volatility": round(volatility, 6),
        "trend": trend,
        "forecast": forecast,
        "confidence": "low" if volatility > 0.02 else "medium" if volatility > 0.005 else "high",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ── Fraud Detection ─────────────────────────────────────────────────────────

def check_reversal_fraud(data: dict) -> dict:
    """Detect suspicious patterns in transaction reversals."""
    agent_id = data.get("agentId", 0)
    reversal_amount = float(data.get("amount", 0))
    reversal_count_today = data.get("reversalCountToday", 0)
    reversal_amount_today = float(data.get("reversalAmountToday", 0))
    avg_transaction_amount = float(data.get("avgTransactionAmount", 1))
    account_age_days = data.get("accountAgeDays", 365)

    risk_score = 0
    flags = []

    # Velocity check: too many reversals in a day
    if reversal_count_today > 5:
        risk_score += 30
        flags.append(f"High reversal velocity: {reversal_count_today} today")
    elif reversal_count_today > 3:
        risk_score += 15
        flags.append(f"Elevated reversal count: {reversal_count_today} today")

    # Amount anomaly: reversal much larger than average
    if avg_transaction_amount > 0 and reversal_amount > avg_transaction_amount * 5:
        risk_score += 25
        flags.append(f"Amount anomaly: {reversal_amount:.0f} vs avg {avg_transaction_amount:.0f}")

    # Daily reversal volume
    if reversal_amount_today > 500000:
        risk_score += 20
        flags.append(f"High daily reversal volume: {reversal_amount_today:.0f}")

    # New account risk
    if account_age_days < 30:
        risk_score += 15
        flags.append("New account (<30 days)")

    # Round amount suspicion
    if reversal_amount > 10000 and reversal_amount % 10000 == 0:
        risk_score += 10
        flags.append("Suspiciously round reversal amount")

    risk_score = min(100, risk_score)
    decision = (
        "block" if risk_score >= 70 else
        "review" if risk_score >= 40 else
        "allow"
    )

    return {
        "agentId": agent_id,
        "reversalAmount": reversal_amount,
        "riskScore": risk_score,
        "decision": decision,
        "flags": flags,
        "requiresManualReview": risk_score >= 40,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ── Anomaly Detection ───────────────────────────────────────────────────────

def detect_fund_flow_anomaly(data: dict) -> dict:
    """Detect anomalies in fund flow patterns."""
    transactions = data.get("transactions", [])
    if len(transactions) < 5:
        return {"anomalies": [], "message": "Insufficient data for anomaly detection"}

    amounts = [float(t.get("amount", 0)) for t in transactions]
    mean_amount = statistics.mean(amounts)
    std_amount = statistics.stdev(amounts) if len(amounts) >= 2 else 0

    anomalies = []
    for i, tx in enumerate(transactions):
        amount = float(tx.get("amount", 0))
        z_score = (amount - mean_amount) / std_amount if std_amount > 0 else 0

        if abs(z_score) > 3:
            anomalies.append({
                "index": i,
                "ref": tx.get("ref", f"TX-{i}"),
                "amount": amount,
                "zScore": round(z_score, 2),
                "severity": "critical" if abs(z_score) > 5 else "high",
                "type": "unusually_large" if z_score > 0 else "unusually_small",
            })
        elif abs(z_score) > 2:
            anomalies.append({
                "index": i,
                "ref": tx.get("ref", f"TX-{i}"),
                "amount": amount,
                "zScore": round(z_score, 2),
                "severity": "medium",
                "type": "elevated" if z_score > 0 else "depressed",
            })

    return {
        "totalTransactions": len(transactions),
        "meanAmount": round(mean_amount, 2),
        "stdDeviation": round(std_amount, 2),
        "anomalyCount": len(anomalies),
        "anomalies": anomalies[:20],
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ── Reconciliation Report ───────────────────────────────────────────────────

def generate_reconciliation_report(data: dict) -> dict:
    """Generate a fund flow reconciliation report."""
    agents = data.get("agents", [])
    report_items = []
    total_discrepancy = 0
    reconciled_count = 0

    for agent in agents:
        float_bal = float(agent.get("floatBalance", 0))
        gl_credits = float(agent.get("glCredits", 0))
        gl_debits = float(agent.get("glDebits", 0))
        gl_net = gl_credits - gl_debits
        discrepancy = abs(float_bal - gl_net)
        is_reconciled = discrepancy < 0.01

        if is_reconciled:
            reconciled_count += 1
        total_discrepancy += discrepancy

        report_items.append({
            "agentId": agent.get("agentId"),
            "floatBalance": float_bal,
            "glNetBalance": round(gl_net, 2),
            "discrepancy": round(discrepancy, 2),
            "isReconciled": is_reconciled,
            "status": "reconciled" if is_reconciled else "needs_attention",
        })

    return {
        "reportId": f"RECON-{int(time.time())}",
        "totalAgents": len(agents),
        "reconciledAgents": reconciled_count,
        "unreconciledAgents": len(agents) - reconciled_count,
        "totalDiscrepancy": round(total_discrepancy, 2),
        "reconciliationRate": round(reconciled_count / len(agents) * 100, 2) if agents else 0,
        "items": report_items[:100],
        "generatedAt": datetime.utcnow().isoformat() + "Z",
    }


# ── HTTP Server ──────────────────────────────────────────────────────────────

class FundFlowHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress default logging

    def _send_json(self, status: int, data: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"
        return json.loads(body)

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {
                "status": "healthy",
                "service": "fund-flow-analytics",
                "version": "1.0.0",
                "timestamp": datetime.utcnow().isoformat() + "Z",
            })
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        try:
            data = self._read_json()

            if self.path == "/api/bnpl/analytics":
                result = calculate_bnpl_portfolio_analytics(data)
            elif self.path == "/api/bnpl/risk-score":
                result = calculate_credit_risk_score(data)
            elif self.path == "/api/fx/forecast":
                result = forecast_fx_rate(data)
            elif self.path == "/api/fraud/check-reversal":
                result = check_reversal_fraud(data)
            elif self.path == "/api/anomaly/detect":
                result = detect_fund_flow_anomaly(data)
            elif self.path == "/api/reconciliation/report":
                result = generate_reconciliation_report(data)
            else:
                self._send_json(404, {"error": "Not found"})
                return

            self._send_json(200, result)
        except Exception as e:
            self._send_json(500, {"error": str(e)})


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), FundFlowHandler)
    print(f"Fund Flow Analytics Engine starting on :{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
