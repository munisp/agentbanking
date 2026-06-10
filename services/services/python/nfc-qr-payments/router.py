"""API Router for NFC/QR Self-Service Payments."""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models import (StaticQRRequest, DynamicQRRequest, QRScanRequest,
                     NFCTokenRequest, NFCValidateRequest, QRCodeResponse, TransactionResponse)
from service import NFCQRPaymentsService
from config import get_db

router = APIRouter(prefix="/api/v1/nfc-qr", tags=["NFC/QR Self-Service Payments"])


def get_svc(db: Session = Depends(get_db)) -> NFCQRPaymentsService:
    return NFCQRPaymentsService(db)


@router.post("/qr/static", response_model=QRCodeResponse, summary="Generate static agent QR code")
def generate_static_qr(payload: StaticQRRequest, svc: NFCQRPaymentsService = Depends(get_svc)):
    return svc.generate_static_agent_qr(
        agent_id=payload.agent_id, agent_name=payload.agent_name,
        agent_code=payload.agent_code, bank_code=payload.bank_code,
        account_number=payload.account_number,
    )


@router.post("/qr/dynamic", response_model=QRCodeResponse, summary="Generate dynamic payment QR code")
def generate_dynamic_qr(payload: DynamicQRRequest, svc: NFCQRPaymentsService = Depends(get_svc)):
    try:
        return svc.generate_dynamic_payment_qr(
            agent_id=payload.agent_id, amount=payload.amount,
            transaction_type=payload.transaction_type,
            description=payload.description, customer_phone=payload.customer_phone,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/qr/scan", response_model=TransactionResponse, summary="Scan QR and initiate payment")
def scan_qr(payload: QRScanRequest, svc: NFCQRPaymentsService = Depends(get_svc)):
    try:
        return svc.scan_and_initiate(
            qr_data=payload.qr_data, customer_phone=payload.customer_phone,
            customer_bvn=payload.customer_bvn, override_amount=payload.override_amount,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/nfc/token", summary="Issue NFC token for tap-to-pay")
def issue_nfc_token(payload: NFCTokenRequest, svc: NFCQRPaymentsService = Depends(get_svc)):
    return svc.issue_nfc_token(
        agent_id=payload.agent_id, amount=payload.amount,
        transaction_type=payload.transaction_type, customer_phone=payload.customer_phone,
    )


@router.post("/nfc/validate", response_model=TransactionResponse, summary="Validate NFC tap and initiate transaction")
def validate_nfc(payload: NFCValidateRequest, svc: NFCQRPaymentsService = Depends(get_svc)):
    try:
        return svc.validate_nfc_token(token_value=payload.token_value, agent_id=payload.agent_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/agents/{agent_id}/qr-codes", response_model=List[QRCodeResponse])
def get_agent_qr_codes(agent_id: UUID, svc: NFCQRPaymentsService = Depends(get_svc)):
    return svc.get_agent_qr_codes(agent_id)


@router.get("/agents/{agent_id}/transactions", response_model=List[TransactionResponse])
def get_agent_transactions(agent_id: UUID, limit: int = 50, svc: NFCQRPaymentsService = Depends(get_svc)):
    return svc.get_agent_transactions(agent_id, limit=limit)


@router.get("/health")
def health():
    return {"status": "healthy", "service": "nfc-qr-payments"}
