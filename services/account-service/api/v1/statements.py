"""Account statement generation endpoints."""
import math
import time
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

statements_router = APIRouter()

_ACCOUNTS = [
    {"accountNumber": "0012345678", "accountName": "Fatima Abdullahi", "accountType": "savings", "currency": "NGN", "currentBalance": 8750000.00, "availableBalance": 8250000.00, "lienAmount": 500000, "status": "active", "branchCode": "BR-LOS-001"},
    {"accountNumber": "3034567890", "accountName": "Ibrahim Musa", "accountType": "current", "currency": "NGN", "currentBalance": 15200000.00, "availableBalance": 15200000.00, "lienAmount": 0, "status": "active", "branchCode": "BR-ABJ-001"},
    {"accountNumber": "2098765432", "accountName": "Chioma Okafor", "accountType": "savings", "currency": "NGN", "currentBalance": 2350000.00, "availableBalance": 2350000.00, "lienAmount": 0, "status": "active", "branchCode": "BR-PHC-001"},
]

_TRANSACTIONS = [
    {"id": "TXN-001", "accountNumber": "0012345678", "date": "2026-01-02", "description": "Opening Balance B/F", "reference": "SYS/OB/2026", "debit": 0, "credit": 0, "balance": 5000000, "channel": "system", "category": "system"},
    {"id": "TXN-002", "accountNumber": "0012345678", "date": "2026-01-05", "description": "Salary Credit - Tech Solutions Ltd", "reference": "NIP/SAL/00123", "debit": 0, "credit": 2500000, "balance": 7500000, "channel": "nip", "category": "salary"},
    {"id": "TXN-003", "accountNumber": "0012345678", "date": "2026-01-10", "description": "ATM Withdrawal - Adeola Odeku", "reference": "ATM/LOS/4521", "debit": 200000, "credit": 0, "balance": 7300000, "channel": "atm", "category": "cash"},
    {"id": "TXN-004", "accountNumber": "0012345678", "date": "2026-02-05", "description": "Salary Credit - Tech Solutions Ltd", "reference": "NIP/SAL/00456", "debit": 0, "credit": 2500000, "balance": 8250000, "channel": "nip", "category": "salary"},
    {"id": "TXN-005", "accountNumber": "0012345678", "date": "2026-03-01", "description": "Interest Credit - Feb 2026", "reference": "INT/SAV/0013", "debit": 0, "credit": 56000, "balance": 8750000, "channel": "system", "category": "interest"},
    {"id": "TXN-101", "accountNumber": "3034567890", "date": "2026-01-02", "description": "Opening Balance B/F", "reference": "SYS/OB/2026", "debit": 0, "credit": 0, "balance": 12000000, "channel": "system", "category": "system"},
    {"id": "TXN-102", "accountNumber": "3034567890", "date": "2026-01-15", "description": "Client Payment - Dangote Cement", "reference": "NIP/CLT/9981", "debit": 0, "credit": 4500000, "balance": 16500000, "channel": "nip", "category": "business"},
    {"id": "TXN-103", "accountNumber": "3034567890", "date": "2026-02-01", "description": "Office Rent Payment", "reference": "NIP/RNT/1122", "debit": 1500000, "credit": 0, "balance": 15000000, "channel": "mobile", "category": "rent"},
]


def _filter_txns(account_number: str, start: Optional[str], end: Optional[str]):
    result = [t for t in _TRANSACTIONS if t["accountNumber"] == account_number]
    if start:
        result = [t for t in result if t["date"] >= start]
    if end:
        result = [t for t in result if t["date"] <= end]
    return result


@statements_router.get("/accounts")
def list_accounts():
    return {"items": _ACCOUNTS, "total": len(_ACCOUNTS)}


class GenerateRequest(BaseModel):
    accountNumber: str
    startDate: Optional[str] = None
    endDate: Optional[str] = None


@statements_router.post("/generate")
def generate_statement(req: GenerateRequest):
    acct = next((a for a in _ACCOUNTS if a["accountNumber"] == req.accountNumber), None)
    if not acct:
        raise HTTPException(status_code=404, detail="account not found")
    txns = sorted(_filter_txns(req.accountNumber, req.startDate, req.endDate), key=lambda t: t["date"])
    total_debit = sum(t["debit"] for t in txns)
    total_credit = sum(t["credit"] for t in txns)
    opening_bal = (txns[0]["balance"] + txns[0]["debit"] - txns[0]["credit"]) if txns else 0
    closing_bal = txns[-1]["balance"] if txns else 0
    return {
        "account": acct, "period": {"from": req.startDate, "to": req.endDate},
        "openingBalance": opening_bal, "closingBalance": closing_bal,
        "totalDebit": round(total_debit, 2), "totalCredit": round(total_credit, 2),
        "transactionCount": len(txns), "transactions": txns,
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


@statements_router.get("/transactions")
def list_transactions(accountNumber: Optional[str] = None):
    if not accountNumber:
        return {"items": _TRANSACTIONS, "total": len(_TRANSACTIONS)}
    filtered = [t for t in _TRANSACTIONS if t["accountNumber"] == accountNumber]
    return {"items": filtered, "total": len(filtered)}


@statements_router.get("/summary")
def get_summary(accountNumber: str, startDate: Optional[str] = None, endDate: Optional[str] = None):
    txns = _filter_txns(accountNumber, startDate, endDate)
    total_debit = sum(t["debit"] for t in txns)
    total_credit = sum(t["credit"] for t in txns)
    category_totals: dict = {}
    channel_counts: dict = {}
    for t in txns:
        cat = t["category"]
        if cat not in category_totals:
            category_totals[cat] = {"debit": 0, "credit": 0}
        category_totals[cat]["debit"] += t["debit"]
        category_totals[cat]["credit"] += t["credit"]
        channel_counts[t["channel"]] = channel_counts.get(t["channel"], 0) + 1
    avg_bal = round(sum(t["balance"] for t in txns) / len(txns), 2) if txns else 0
    return {
        "accountNumber": accountNumber, "period": {"from": startDate, "to": endDate},
        "totalDebit": round(total_debit, 2), "totalCredit": round(total_credit, 2),
        "netMovement": round(total_credit - total_debit, 2),
        "transactionCount": len(txns), "averageBalance": avg_bal,
        "categoryBreakdown": category_totals, "channelBreakdown": channel_counts,
    }


class BalanceTrendRequest(BaseModel):
    accountNumber: str


@statements_router.post("/balance-trend")
def get_balance_trend(req: BalanceTrendRequest):
    txns = sorted([t for t in _TRANSACTIONS if t["accountNumber"] == req.accountNumber], key=lambda t: t["date"])
    trend = [{"date": t["date"], "balance": t["balance"]} for t in txns]
    return {"accountNumber": req.accountNumber, "dataPoints": trend, "count": len(trend)}
