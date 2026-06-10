import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config import Base, engine, get_db
from models import (
    Payout,
    PayoutApproval,
    PayoutApprovalCreate,
    PayoutApprovalRead,
    PayoutBatch,
    PayoutBatchCreate,
    PayoutBatchRead,
    PayoutRead,
    ReconciliationRecord,
    ReconciliationRecordRead,
)

# Initialize the database and logger
Base.metadata.create_all(bind=engine)
router = APIRouter(prefix="/payouts", tags=["payouts"])
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# --- Helper Functions (Business Logic) ---

def _get_batch_or_404(db: Session, batch_id: str) -> PayoutBatch:
    """Fetches a PayoutBatch by ID or raises a 404 error."""
    batch = db.query(PayoutBatch).filter(PayoutBatch.id == batch_id).first()
    if not batch:
        logger.warning(f"PayoutBatch with ID {batch_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PayoutBatch with ID '{batch_id}' not found",
        )
    return batch


def _create_payout_batch(db: Session, batch_data: PayoutBatchCreate) -> PayoutBatch:
    """
    Creates a new PayoutBatch and associated Payouts.
    Calculates total amount and payout count.
    """
    total_amount = sum(p.amount for p in batch_data.payouts)
    payout_count = len(batch_data.payouts)

    if payout_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch must contain at least one payout.",
        )

    # 1. Create the PayoutBatch record
    db_batch = PayoutBatch(
        total_amount=total_amount,
        payout_count=payout_count,
        status="PENDING",
    )
    db.add(db_batch)
    db.flush()  # Flush to get the batch ID

    # 2. Create individual Payout records
    for payout_data in batch_data.payouts:
        db_payout = Payout(
            batch_id=db_batch.id,
            amount=payout_data.amount,
            currency=payout_data.currency,
            recipient_id=payout_data.recipient_id,
            payment_method=payout_data.payment_method,
            external_reference_id=payout_data.external_reference_id,
            status="PENDING",
        )
        db.add(db_payout)

    db.commit()
    db.refresh(db_batch)
    logger.info(f"Created new PayoutBatch {db_batch.id} with {payout_count} payouts.")
    return db_batch


def _approve_batch(
    db: Session, batch: PayoutBatch, approval_data: PayoutApprovalCreate
) -> PayoutApproval:
    """Handles the approval or rejection of a PayoutBatch."""
    if batch.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch is in status '{batch.status}'. Only PENDING batches can be approved/rejected.",
        )

    # 1. Create the PayoutApproval record
    db_approval = PayoutApproval(
        batch_id=batch.id,
        approved_by_id=approval_data.approved_by_id,
        status=approval_data.status,
        rejection_reason=approval_data.rejection_reason
        if approval_data.status == "REJECTED"
        else None,
    )
    db.add(db_approval)

    # 2. Update the PayoutBatch status
    if approval_data.status == "APPROVED":
        batch.status = "APPROVED"
        logger.info(f"PayoutBatch {batch.id} approved by {approval_data.approved_by_id}.")
    elif approval_data.status == "REJECTED":
        batch.status = "FAILED"  # Treat rejection as a final failure state for the batch
        logger.warning(
            f"PayoutBatch {batch.id} rejected by {approval_data.approved_by_id}. Reason: {approval_data.rejection_reason}"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid approval status. Must be 'APPROVED' or 'REJECTED'.",
        )

    db.commit()
    db.refresh(db_approval)
    return db_approval


def _process_batch(db: Session, batch: PayoutBatch) -> PayoutBatch:
    """Processes the processing of an approved PayoutBatch."""
    if batch.status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch is in status '{batch.status}'. Only APPROVED batches can be processed.",
        )

    # 1. Update batch status to PROCESSING
    batch.status = "PROCESSING"
    db.add(batch)
    db.flush()

    # 2. Execute payout via payment gateway and update individual payout statuses
    # In a real system, this would involve an external API call and a webhook/callback
    # to update the status. Here, we process a successful transition.
    successful_payouts = 0
    for payout in batch.payouts:
        # Simple logic: 90% success rate simulation
        if hash(payout.id) % 10 != 0:
            payout.status = "PAID"
            successful_payouts += 1
        else:
            payout.status = "FAILED"
            logger.error(f"Payout {payout.id} failed during processing.")
        db.add(payout)

    # 3. Update batch status to COMPLETED/FAILED based on individual payout results
    if successful_payouts == batch.payout_count:
        batch.status = "COMPLETED"
    elif successful_payouts > 0:
        batch.status = "COMPLETED" # Partial success is still 'completed' for the batch process
    else:
        batch.status = "FAILED"
        
    db.commit()
    db.refresh(batch)
    logger.info(f"PayoutBatch {batch.id} processing finished. Status: {batch.status}.")
    return batch


def _reconcile_batch(db: Session, batch: PayoutBatch) -> ReconciliationRecord:
    """Processes the reconciliation process for a completed PayoutBatch."""
    if batch.status not in ["COMPLETED", "FAILED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch is in status '{batch.status}'. Only COMPLETED or FAILED batches can be reconciled.",
        )

    # Check if reconciliation already exists (idempotency)
    existing_reco = db.query(ReconciliationRecord).filter(ReconciliationRecord.batch_id == batch.id).first()
    if existing_reco:
        return existing_reco

    # 1. Gather data for reconciliation
    paid_payouts = db.query(Payout).filter(Payout.batch_id == batch.id, Payout.status == "PAID").all()
    failed_payouts = db.query(Payout).filter(Payout.batch_id == batch.id, Payout.status == "FAILED").all()
    
    total_paid_amount = sum(p.amount for p in paid_payouts)
    total_batch_amount = batch.total_amount
    
    # 2. Determine reconciliation status
    reco_status = "PENDING"
    details = {
        "paid_count": len(paid_payouts),
        "failed_count": len(failed_payouts),
        "total_paid_amount": float(total_paid_amount),
        "total_batch_amount": float(total_batch_amount),
        "mismatch_amount": float(total_batch_amount - total_paid_amount),
    }

    if total_paid_amount == total_batch_amount and len(paid_payouts) == batch.payout_count:
        reco_status = "MATCHED"
    elif total_paid_amount != total_batch_amount or len(paid_payouts) + len(failed_payouts) != batch.payout_count:
        reco_status = "MISMATCH"
    else:
        reco_status = "MANUAL_REVIEW" # e.g., if there are failures, but the total paid amount matches a subset

    # 3. Create the ReconciliationRecord
    db_reco = ReconciliationRecord(
        batch_id=batch.id,
        status=reco_status,
        details=details,
    )
    db.add(db_reco)
    db.commit()
    db.refresh(db_reco)
    logger.info(f"PayoutBatch {batch.id} reconciled. Status: {reco_status}.")
    return db_reco


# --- API Endpoints ---

@router.post(
    "/batches",
    response_model=PayoutBatchRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Payout Batch",
    description="Creates a new batch of payouts and calculates the total amount and count.",
)
def create_payout_batch(
    batch_data: PayoutBatchCreate, db: Session = Depends(get_db)
):
    """
    Endpoint to create a new PayoutBatch.
    """
    return _create_payout_batch(db, batch_data)


@router.get(
    "/batches/{batch_id}",
    response_model=PayoutBatchRead,
    summary="Get Payout Batch details",
    description="Retrieves the details of a specific payout batch, including related approval and reconciliation records.",
)
def get_payout_batch(batch_id: str, db: Session = Depends(get_db)):
    """
    Endpoint to retrieve a PayoutBatch by ID.
    """
    return _get_batch_or_404(db, batch_id)


@router.get(
    "/batches/{batch_id}/payouts",
    response_model=List[PayoutRead],
    summary="Get all Payouts in a Batch",
    description="Retrieves a list of all individual payouts belonging to a specific batch.",
)
def get_payouts_in_batch(batch_id: str, db: Session = Depends(get_db)):
    """
    Endpoint to retrieve all Payouts for a given Batch ID.
    """
    batch = _get_batch_or_404(db, batch_id)
    return batch.payouts


@router.post(
    "/batches/{batch_id}/approve",
    response_model=PayoutApprovalRead,
    summary="Approve or Reject a Payout Batch",
    description="Approves or rejects a PENDING payout batch, updating the batch status accordingly.",
)
def approve_payout_batch(
    batch_id: str,
    approval_data: PayoutApprovalCreate,
    db: Session = Depends(get_db),
):
    """
    Endpoint to approve or reject a PayoutBatch.
    """
    batch = _get_batch_or_404(db, batch_id)
    return _approve_batch(db, batch, approval_data)


@router.post(
    "/batches/{batch_id}/process",
    response_model=PayoutBatchRead,
    summary="Process an Approved Payout Batch (Simulation)",
    description="Processes the external processing of an APPROVED payout batch, updating individual payout statuses and the final batch status.",
)
def process_payout_batch(batch_id: str, db: Session = Depends(get_db)):
    """
    Endpoint to process an APPROVED PayoutBatch.
    """
    batch = _get_batch_or_404(db, batch_id)
    return _process_batch(db, batch)


@router.post(
    "/batches/{batch_id}/reconcile",
    response_model=ReconciliationRecordRead,
    summary="Reconcile a Completed Payout Batch (Simulation)",
    description="Processes the reconciliation process for a COMPLETED or FAILED batch, comparing expected vs. actual paid amounts and creating a reconciliation record.",
)
def reconcile_payout_batch(batch_id: str, db: Session = Depends(get_db)):
    """
    Endpoint to reconcile a COMPLETED PayoutBatch.
    """
    batch = _get_batch_or_404(db, batch_id)
    return _reconcile_batch(db, batch)
