"""
CIPS (Cross-Border Interbank Payment System) Gateway - Production Implementation.
Handles ISO 20022 pain.001 messages and SWIFT MT103 for Chinese RMB cross-border payments.
"""
import os
import json
import logging
import uuid
import time
import hmac
import hashlib
import ssl
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional
from xml.etree import ElementTree as ET

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

CIPS_API_BASE_URL = os.environ.get("CIPS_API_BASE_URL", "https://api.cips.com.cn/api/v1")
CIPS_PARTICIPANT_ID = os.environ.get("CIPS_PARTICIPANT_ID", "")
CIPS_API_KEY = os.environ.get("CIPS_API_KEY", "")
CIPS_API_SECRET = os.environ.get("CIPS_API_SECRET", "")
CIPS_CERT_PATH = os.environ.get("CIPS_CERT_PATH", "/etc/cips/tls/client.crt")
CIPS_KEY_PATH = os.environ.get("CIPS_KEY_PATH", "/etc/cips/tls/client.key")
CIPS_CA_PATH = os.environ.get("CIPS_CA_PATH", "/etc/cips/tls/ca.crt")


class CIPSAPIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def build_iso20022_pain001(
    message_id: str,
    creation_datetime: str,
    debtor_name: str,
    debtor_account: str,
    debtor_bic: str,
    creditor_name: str,
    creditor_account: str,
    creditor_bic: str,
    amount: Decimal,
    currency: str,
    reference: str,
    purpose: str = "REMITTANCE",
) -> str:
    """
    Build a real ISO 20022 pain.001 CustomerCreditTransferInitiation XML message.
    """
    ns = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.09"
    root = ET.Element("Document", xmlns=ns)
    cstmr_cdt_trf_initn = ET.SubElement(root, "CstmrCdtTrfInitn")

    # Group Header
    grp_hdr = ET.SubElement(cstmr_cdt_trf_initn, "GrpHdr")
    ET.SubElement(grp_hdr, "MsgId").text = message_id
    ET.SubElement(grp_hdr, "CreDtTm").text = creation_datetime
    ET.SubElement(grp_hdr, "NbOfTxs").text = "1"
    ET.SubElement(grp_hdr, "CtrlSum").text = str(amount)
    initg_pty = ET.SubElement(grp_hdr, "InitgPty")
    ET.SubElement(initg_pty, "Nm").text = debtor_name

    # Payment Information
    pmt_inf = ET.SubElement(cstmr_cdt_trf_initn, "PmtInf")
    ET.SubElement(pmt_inf, "PmtInfId").text = f"PMT-{message_id}"
    ET.SubElement(pmt_inf, "PmtMtd").text = "TRF"
    ET.SubElement(pmt_inf, "NbOfTxs").text = "1"
    ET.SubElement(pmt_inf, "CtrlSum").text = str(amount)

    pmt_tp_inf = ET.SubElement(pmt_inf, "PmtTpInf")
    svc_lvl = ET.SubElement(pmt_tp_inf, "SvcLvl")
    ET.SubElement(svc_lvl, "Cd").text = "SEPA"
    lcl_instrm = ET.SubElement(pmt_tp_inf, "LclInstrm")
    ET.SubElement(lcl_instrm, "Cd").text = "CIPS"
    ET.SubElement(pmt_tp_inf, "CtgyPurp").text = purpose

    ET.SubElement(pmt_inf, "ReqdExctnDt").text = datetime.utcnow().strftime("%Y-%m-%d")

    # Debtor
    dbtr = ET.SubElement(pmt_inf, "Dbtr")
    ET.SubElement(dbtr, "Nm").text = debtor_name
    dbtr_acct = ET.SubElement(pmt_inf, "DbtrAcct")
    dbtr_id = ET.SubElement(dbtr_acct, "Id")
    ET.SubElement(dbtr_id, "IBAN").text = debtor_account
    dbtr_agt = ET.SubElement(pmt_inf, "DbtrAgt")
    fin_instn_id = ET.SubElement(dbtr_agt, "FinInstnId")
    ET.SubElement(fin_instn_id, "BICFI").text = debtor_bic

    # Credit Transfer Transaction
    cdt_trf_tx_inf = ET.SubElement(pmt_inf, "CdtTrfTxInf")
    pmt_id = ET.SubElement(cdt_trf_tx_inf, "PmtId")
    ET.SubElement(pmt_id, "InstrId").text = f"INSTR-{message_id}"
    ET.SubElement(pmt_id, "EndToEndId").text = reference

    amt = ET.SubElement(cdt_trf_tx_inf, "Amt")
    instd_amt = ET.SubElement(amt, "InstdAmt", Ccy=currency)
    instd_amt.text = str(amount)

    cdtr_agt = ET.SubElement(cdt_trf_tx_inf, "CdtrAgt")
    cdtr_fin_instn = ET.SubElement(cdtr_agt, "FinInstnId")
    ET.SubElement(cdtr_fin_instn, "BICFI").text = creditor_bic

    cdtr = ET.SubElement(cdt_trf_tx_inf, "Cdtr")
    ET.SubElement(cdtr, "Nm").text = creditor_name
    cdtr_acct = ET.SubElement(cdt_trf_tx_inf, "CdtrAcct")
    cdtr_id = ET.SubElement(cdtr_acct, "Id")
    ET.SubElement(cdtr_id, "IBAN").text = creditor_account

    rmt_inf = ET.SubElement(cdt_trf_tx_inf, "RmtInf")
    ustrd = ET.SubElement(rmt_inf, "Ustrd")
    ustrd.text = reference

    return ET.tostring(root, encoding="unicode", xml_declaration=False)


def parse_swift_mt103(mt103_text: str) -> Dict:
    """
    Parse a SWIFT MT103 (Single Customer Credit Transfer) message.
    Returns structured dict with all key fields.
    """
    result = {}
    lines = mt103_text.strip().split("\n")

    for line in lines:
        line = line.strip()
        if line.startswith(":20:"):
            result["transaction_reference"] = line[4:]
        elif line.startswith(":23B:"):
            result["bank_operation_code"] = line[5:]
        elif line.startswith(":32A:"):
            # Format: YYMMDDCCCAMOUNT
            val = line[5:]
            result["value_date"] = val[:6]
            result["currency"] = val[6:9]
            result["amount"] = val[9:].replace(",", ".")
        elif line.startswith(":50K:"):
            result["ordering_customer"] = line[5:]
        elif line.startswith(":52A:"):
            result["ordering_institution_bic"] = line[5:]
        elif line.startswith(":56A:"):
            result["intermediary_institution_bic"] = line[5:]
        elif line.startswith(":57A:"):
            result["account_with_institution_bic"] = line[5:]
        elif line.startswith(":59:"):
            result["beneficiary_customer"] = line[4:]
        elif line.startswith(":70:"):
            result["remittance_information"] = line[4:]
        elif line.startswith(":71A:"):
            result["details_of_charges"] = line[5:]

    return result


def _get_auth_headers(body: str = "") -> Dict[str, str]:
    """Generate CIPS API authentication headers."""
    timestamp = str(int(time.time()))
    nonce = str(uuid.uuid4()).replace("-", "")
    body_hash = hashlib.sha256(body.encode()).hexdigest()
    string_to_sign = f"{timestamp}\n{nonce}\n{body_hash}"
    signature = hmac.new(
        CIPS_API_SECRET.encode(),
        string_to_sign.encode(),
        hashlib.sha256
    ).hexdigest()

    return {
        "X-CIPS-Participant-ID": CIPS_PARTICIPANT_ID,
        "X-CIPS-API-Key": CIPS_API_KEY,
        "X-CIPS-Timestamp": timestamp,
        "X-CIPS-Nonce": nonce,
        "X-CIPS-Signature": signature,
        "Content-Type": "application/xml",
        "Accept": "application/json",
    }


def _build_client() -> httpx.Client:
    """Build httpx client with mTLS for CIPS."""
    cert = None
    verify: object = True
    if os.path.exists(CIPS_CERT_PATH) and os.path.exists(CIPS_KEY_PATH):
        cert = (CIPS_CERT_PATH, CIPS_KEY_PATH)
    if os.path.exists(CIPS_CA_PATH):
        verify = CIPS_CA_PATH
    return httpx.Client(cert=cert, verify=verify, timeout=30.0)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def submit_payment(pain001_xml: str) -> Dict:
    """Submit ISO 20022 pain.001 payment to CIPS."""
    headers = _get_auth_headers(pain001_xml)
    with _build_client() as client:
        resp = client.post(
            f"{CIPS_API_BASE_URL}/payments/submit",
            content=pain001_xml,
            headers=headers,
        )
        if resp.status_code >= 400:
            raise CIPSAPIError(f"CIPS submission error: {resp.status_code} - {resp.text}", resp.status_code)
        return resp.json()


def get_payment_status(transaction_id: str) -> Dict:
    """Query CIPS payment status."""
    headers = _get_auth_headers()
    with _build_client() as client:
        resp = client.get(
            f"{CIPS_API_BASE_URL}/payments/{transaction_id}/status",
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()


def initiate_cips_transfer(
    amount: Decimal,
    currency: str,
    sender_name: str,
    sender_account: str,
    sender_bic: str,
    beneficiary_name: str,
    beneficiary_account: str,
    beneficiary_bic: str,
    reference: str,
) -> Dict:
    """
    Full CIPS transfer initiation: build pain.001, submit to CIPS, return result.
    """
    message_id = f"CIPS-{uuid.uuid4().hex[:16].upper()}"
    creation_dt = datetime.utcnow().isoformat() + "Z"

    pain001_xml = build_iso20022_pain001(
        message_id=message_id,
        creation_datetime=creation_dt,
        debtor_name=sender_name,
        debtor_account=sender_account,
        debtor_bic=sender_bic,
        creditor_name=beneficiary_name,
        creditor_account=beneficiary_account,
        creditor_bic=beneficiary_bic,
        amount=amount,
        currency=currency,
        reference=reference,
    )

    try:
        result = submit_payment(pain001_xml)
        return {
            "success": True,
            "message_id": message_id,
            "cips_transaction_id": result.get("transactionId"),
            "status": result.get("status", "SUBMITTED"),
            "amount": str(amount),
            "currency": currency,
            "submitted_at": creation_dt,
        }
    except CIPSAPIError as e:
        logger.error(f"CIPS transfer failed: {e}")
        return {"success": False, "error": str(e), "message_id": message_id}


def verify_webhook_signature(payload: bytes, headers: Dict[str, str]) -> bool:
    """Verify CIPS webhook HMAC signature."""
    webhook_secret = os.environ.get("CIPS_WEBHOOK_SECRET", "")
    if not webhook_secret:
        return False
    received = headers.get("X-CIPS-Signature", "")
    expected = hmac.new(webhook_secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(received, expected)
