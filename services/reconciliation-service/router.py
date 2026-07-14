from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os, json, time, logging
from datetime import datetime, timedelta
from decimal import Decimal
from models import ReconciliationReport, ReconciliationStatus, Base

logger = logging.getLogger(__name__)
router = APIRouter()

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "service": "reconciliation-service", "database": "connected"}
    except Exception as e:
        raise HTTPException(503, detail={"status": "unhealthy", "error": str(e)})


@router.post("/reconcile/float-vs-ledger")
def reconcile_float_vs_ledger(db=Depends(get_db)):
    start = time.time()
    try:
        # Get all active float accounts
        accounts = db.execute(text(
            "SELECT account_id, balance FROM float_accounts WHERE status = 'active'"
        )).fetchall()

        discrepancies = []
        matched = 0

        for account in accounts:
            account_id, stored_balance = account.account_id, Decimal(str(account.balance))

            # Compute balance from transaction history
            result = db.execute(text("""
                SELECT
                    COALESCE(SUM(CASE WHEN transaction_type IN ('CREDIT','TOPUP','INTEREST') THEN amount ELSE 0 END), 0) -
                    COALESCE(SUM(CASE WHEN transaction_type IN ('DEBIT','FEE','RESERVE') THEN amount ELSE 0 END), 0) AS computed_balance
                FROM float_transactions WHERE account_id = :account_id
            """), {"account_id": account_id}).fetchone()

            computed_balance = Decimal(str(result.computed_balance)) if result and result.computed_balance is not None else Decimal("0")
            diff = abs(stored_balance - computed_balance)

            if diff > Decimal("0.01"):
                discrepancies.append({
                    "account_id": account_id,
                    "stored_balance": float(stored_balance),
                    "computed_balance": float(computed_balance),
                    "discrepancy": float(diff)
                })
            else:
                matched += 1

        status = ReconciliationStatus.DISCREPANCY if discrepancies else ReconciliationStatus.BALANCED
        total_discrepancy = sum(d["discrepancy"] for d in discrepancies)

        report = ReconciliationReport(
            run_type="float_vs_ledger",
            status=status,
            total_checked=len(accounts),
            matched_count=matched,
            discrepancy_count=len(discrepancies),
            discrepancy_amount=Decimal(str(round(total_discrepancy, 2))),
            details=json.dumps(discrepancies[:100]),  # cap at 100 for storage
            duration_ms=int((time.time() - start) * 1000)
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        return {
            "report_id": report.id,
            "status": status,
            "total_checked": len(accounts),
            "matched": matched,
            "discrepancies": len(discrepancies),
            "total_discrepancy_amount": round(total_discrepancy, 2),
            "discrepancy_details": discrepancies[:10],  # first 10 in response
            "run_at": report.run_at.isoformat(),
            "duration_ms": report.duration_ms,
        }
    except Exception as e:
        logger.error(f"Float reconciliation failed: {e}")
        raise HTTPException(500, detail=str(e))


@router.post("/reconcile/settlement-vs-commission")
def reconcile_settlement_vs_commission(
    days: int = Query(30, ge=1, le=365),
    db=Depends(get_db)
):
    start = time.time()
    since = datetime.utcnow() - timedelta(days=days)
    try:
        # Total settled amount
        settlement_result = db.execute(text("""
            SELECT COALESCE(SUM(amount), 0) as total_settled,
                   COUNT(*) as settlement_count
            FROM settlements
            WHERE status = 'completed' AND settlement_date >= :since
        """), {"since": since}).fetchone()

        total_settled = Decimal(str(settlement_result.total_settled))
        settlement_count = settlement_result.settlement_count

        # Total commissions earned in same period
        commission_result = db.execute(text("""
            SELECT COALESCE(SUM(commission_amount), 0) as total_commission,
                   COUNT(*) as transaction_count
            FROM commission_transactions
            WHERE created_at >= :since
        """), {"since": since}).fetchone()

        total_commission = Decimal(str(commission_result.total_commission))

        diff = abs(total_settled - total_commission)
        threshold = total_commission * Decimal("0.01")  # 1% tolerance
        status = ReconciliationStatus.DISCREPANCY if diff > threshold and total_commission > 0 else ReconciliationStatus.BALANCED

        report = ReconciliationReport(
            run_type="settlement_vs_commission",
            status=status,
            total_checked=settlement_count,
            matched_count=settlement_count if status == ReconciliationStatus.BALANCED else 0,
            discrepancy_count=1 if status == ReconciliationStatus.DISCREPANCY else 0,
            discrepancy_amount=diff,
            details=json.dumps({
                "period_days": days,
                "total_settled": float(total_settled),
                "total_commission": float(total_commission),
                "difference": float(diff),
                "threshold_1pct": float(threshold),
            }),
            duration_ms=int((time.time() - start) * 1000)
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        return {
            "report_id": report.id,
            "status": status,
            "period_days": days,
            "total_settled": float(total_settled),
            "total_commission": float(total_commission),
            "difference": float(diff),
            "balanced": status == ReconciliationStatus.BALANCED,
            "run_at": report.run_at.isoformat(),
        }
    except Exception as e:
        logger.error(f"Settlement/commission reconciliation failed: {e}")
        raise HTTPException(500, detail=str(e))


@router.get("/reconcile/reports")
def list_reports(
    run_type: str = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db)
):
    q = db.query(ReconciliationReport)
    if run_type:
        q = q.filter(ReconciliationReport.run_type == run_type)
    reports = q.order_by(ReconciliationReport.run_at.desc()).limit(limit).all()
    return {
        "reports": [
            {
                "id": r.id,
                "run_type": r.run_type,
                "status": r.status,
                "total_checked": r.total_checked,
                "discrepancy_count": r.discrepancy_count,
                "discrepancy_amount": float(r.discrepancy_amount or 0),
                "run_at": r.run_at.isoformat(),
                "duration_ms": r.duration_ms,
            }
            for r in reports
        ]
    }


@router.get("/reconcile/reports/{report_id}")
def get_report(report_id: int, db=Depends(get_db)):
    report = db.query(ReconciliationReport).filter(ReconciliationReport.id == report_id).first()
    if not report:
        raise HTTPException(404, detail=f"Report {report_id} not found")
    details = None
    if report.details:
        try:
            details = json.loads(report.details)
        except Exception:
            details = report.details
    return {
        "id": report.id,
        "run_type": report.run_type,
        "status": report.status,
        "total_checked": report.total_checked,
        "matched_count": report.matched_count,
        "discrepancy_count": report.discrepancy_count,
        "discrepancy_amount": float(report.discrepancy_amount or 0),
        "details": details,
        "run_at": report.run_at.isoformat(),
        "duration_ms": report.duration_ms,
    }
