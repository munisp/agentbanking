import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Transaction, NameEnquiry, Bank, TransactionStatus
from schemas import (
    TransactionCreate,
    NameEnquiryRequest,
    NameEnquiryResponse,
    TransactionUpdate,
    BankBase,
)
from config import settings

# --- 1. Custom Exceptions ---

class ServiceException(Exception):
    """Base exception for service layer errors."""
    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class TransactionNotFound(ServiceException):
    """Raised when a transaction is not found."""
    def __init__(self, transaction_ref: str) -> None:
        super().__init__(f"Transaction with reference '{transaction_ref}' not found.", status_code=404)

class BankNotFound(ServiceException):
    """Raised when a bank is not found by code."""
    def __init__(self, bank_code: str) -> None:
        super().__init__(f"Bank with code '{bank_code}' not found.", status_code=404)

class NIBSSAPIError(ServiceException):
    """Raised when the NIBSS API returns an error or is unreachable."""
    def __init__(self, message: str, status_code: int = 503) -> None:
        super().__init__(f"NIBSS API Error: {message}", status_code=status_code)

class NIBSSNotConfigured(NIBSSAPIError):
    """Raised when no real NIBSS provider is configured and simulation mode is off."""
    def __init__(self) -> None:
        super().__init__(
            "NIBSS provider is not configured. Set NIBSS_BASE_URL and NIBSS_API_KEY "
            "for a real NIBSS endpoint, or explicitly set NIBSS_SIMULATION_MODE=true "
            "outside production.",
            status_code=503,
        )

# --- 2. Logging Setup ---

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)

# --- 3. NIBSS Clients ---

class RealNIBSSClient:
    """
    HTTP client for the NIBSS API (NIP name enquiry / funds transfer).

    Calls the NIBSS endpoints configured via NIBSS_BASE_URL using the
    NIBSS_API_KEY/NIBSS_SECRET credentials. Every provider or transport
    failure is raised as NIBSSAPIError; this client never fabricates
    account names, BVNs, session ids, or response codes.
    """
    def __init__(self) -> None:
        self.base_url = settings.NIBSS_BASE_URL.rstrip("/")
        self.timeout = float(os.getenv("NIBSS_TIMEOUT_SECONDS", "15"))
        logger.info(f"Initialized NIBSS HTTP client. Base URL: {self.base_url}")

    def _headers(self) -> Dict[str, str]:
        return {
            "APIKey": settings.NIBSS_API_KEY,
            "Authorization": f"Bearer {settings.NIBSS_SECRET}",
            "Content-Type": "application/json",
        }

    def name_enquiry(self, request: NameEnquiryRequest) -> NameEnquiryResponse:
        """Performs a real NIBSS Name Enquiry call."""
        logger.info(f"NIBSS: Name Enquiry for account {request.account_number} at bank {request.bank_code}")
        url = f"{self.base_url}/name-enquiry"
        payload = {
            "account_number": request.account_number,
            "bank_code": request.bank_code,
        }
        try:
            resp = httpx.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
        except httpx.HTTPError as e:
            raise NIBSSAPIError(f"Name enquiry request failed: {e}", status_code=503)

        if resp.status_code == 404:
            return NameEnquiryResponse(
                account_number=request.account_number,
                bank_code=request.bank_code,
                account_name="",
                bvn=None,
                response_code="404",
                response_message="Account Not Found"
            )
        if resp.status_code != 200:
            raise NIBSSAPIError(f"Name enquiry failed with HTTP {resp.status_code}.", status_code=503)

        try:
            data = resp.json()
        except ValueError as e:
            raise NIBSSAPIError(f"Name enquiry returned a malformed response: {e}", status_code=503)

        return NameEnquiryResponse(
            account_number=request.account_number,
            bank_code=request.bank_code,
            account_name=data.get("account_name", ""),
            bvn=data.get("bvn"),
            response_code=str(data.get("response_code", "")),
            response_message=data.get("response_message", ""),
        )

    def fund_transfer(self, transaction: Transaction) -> Tuple[Optional[str], str, str]:
        """
        Initiates a real NIBSS Instant Payment (NIP) fund transfer.
        Returns: (nibss_session_id, response_code, response_message)
        """
        logger.info(f"NIBSS: Initiating NIP for ref {transaction.transaction_ref} with amount {transaction.amount}")
        url = f"{self.base_url}/fund-transfer"
        payload = {
            "transaction_ref": transaction.transaction_ref,
            "source_account_number": transaction.source_account_number,
            "destination_account_number": transaction.destination_account_number,
            "destination_bank_code": transaction.destination_bank_code,
            "amount": str(transaction.amount),
            "narration": transaction.narration,
        }
        try:
            resp = httpx.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
        except httpx.HTTPError as e:
            raise NIBSSAPIError(f"Fund transfer request failed: {e}", status_code=503)

        if resp.status_code != 200:
            raise NIBSSAPIError(f"Fund transfer failed with HTTP {resp.status_code}.", status_code=503)

        try:
            data = resp.json()
        except ValueError as e:
            raise NIBSSAPIError(f"Fund transfer returned a malformed response: {e}", status_code=503)

        return (
            data.get("session_id") or data.get("nibss_session_id"),
            str(data.get("response_code", "")),
            data.get("response_message", ""),
        )


class MockNIBSSClient:
    """
    Simulated NIBSS client for local development ONLY.

    Only used when NIBSS_SIMULATION_MODE=true is explicitly set AND
    ENVIRONMENT is not production (enforced at import time below).
    Never wired in production.
    """
    def __init__(self) -> None:
        logger.warning("Initialized SIMULATED NIBSS client (NIBSS_SIMULATION_MODE=true).")

    def name_enquiry(self, request: NameEnquiryRequest) -> NameEnquiryResponse:
        """Simulates a Name Enquiry call (clearly marked simulated data)."""
        logger.info(f"Simulated NIBSS: Name Enquiry for account {request.account_number} at bank {request.bank_code}")
        if request.account_number.endswith("404"):
            return NameEnquiryResponse(
                account_number=request.account_number,
                bank_code=request.bank_code,
                account_name="",
                bvn=None,
                response_code="404",
                response_message="Account Not Found"
            )
        return NameEnquiryResponse(
            account_number=request.account_number,
            bank_code=request.bank_code,
            account_name="SIMULATED ACCOUNT HOLDER",
            bvn=None,
            response_code="00",
            response_message="SIMULATED Name Enquiry (NIBSS_SIMULATION_MODE)"
        )

    def fund_transfer(self, transaction: Transaction) -> Tuple[Optional[str], str, str]:
        """Simulates a NIP fund transfer (never in production)."""
        logger.info(f"Simulated NIBSS: NIP for ref {transaction.transaction_ref}")
        if transaction.amount > 1000000:
            return None, "99", "SIMULATED failure: amount exceeds limit."
        return str(uuid.uuid4()), "00", "SIMULATED success (NIBSS_SIMULATION_MODE)"


# --- Client selection / simulation-mode guard ---

_SIMULATION_MODE = os.getenv("NIBSS_SIMULATION_MODE", "false").strip().lower() == "true"
_ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()

if _SIMULATION_MODE and _ENVIRONMENT == "production":
    raise RuntimeError(
        "NIBSS_SIMULATION_MODE=true is forbidden when ENVIRONMENT=production. "
        "Refusing to start with a simulated NIBSS client."
    )


def _nibss_credentials_configured() -> bool:
    return bool(
        settings.NIBSS_API_KEY
        and settings.NIBSS_API_KEY != "your_nibss_api_key"
        and settings.NIBSS_BASE_URL
        and "example.com" not in settings.NIBSS_BASE_URL
    )


def _build_nibss_client():
    """Builds the NIBSS client: simulated only when explicitly gated, else real, else fail closed."""
    if _SIMULATION_MODE:
        return MockNIBSSClient()
    if not _nibss_credentials_configured():
        raise NIBSSNotConfigured()
    return RealNIBSSClient()

# --- 4. Service Layer Implementation ---

class NIBSSService:
    """
    Business logic layer for NIBSS integration.
    Handles database operations and interaction with the NIBSS client.
    """
    def __init__(self, db: Session) -> None:
        self.db = db
        self._nibss_client = None

    @property
    def nibss_client(self):
        """Lazily builds the NIBSS client so read-only operations fail closed
        only when a NIBSS call is actually required."""
        if self._nibss_client is None:
            self._nibss_client = _build_nibss_client()
        return self._nibss_client

    # --- Bank Operations ---

    def get_bank_by_code(self, bank_code: str) -> Bank:
        """Retrieves a bank by its NIBSS code."""
        bank = self.db.query(Bank).filter(Bank.bank_code == bank_code).first()
        if not bank:
            raise BankNotFound(bank_code)
        return bank

    def get_all_banks(self) -> List[Bank]:
        """Retrieves all active banks."""
        return self.db.query(Bank).filter(Bank.is_active == True).all()

    # --- Name Enquiry Operations ---

    def perform_name_enquiry(self, request: NameEnquiryRequest) -> NameEnquiryResponse:
        """
        Performs a name enquiry via the NIBSS client and saves the result.
        """
        # 1. Validate bank code exists locally
        self.get_bank_by_code(request.bank_code)
        
        # 2. Call NIBSS API (real client, or gated simulator)
        response = self.nibss_client.name_enquiry(request)
        
        # 3. Save enquiry result to database
        enquiry_record = NameEnquiry(
            account_number=request.account_number,
            bank_code=request.bank_code,
            account_name=response.account_name,
            bvn=response.bvn,
            response_code=response.response_code,
            response_message=response.response_message,
            created_at=datetime.utcnow()
        )
        self.db.add(enquiry_record)
        self.db.commit()
        self.db.refresh(enquiry_record)
        
        return response

    # --- Transaction Operations (CRUD) ---

    def create_transaction(self, transaction_data: TransactionCreate) -> Transaction:
        """
        Creates a new transaction record and initiates the NIP transfer.
        """
        # 1. Validate destination bank
        self.get_bank_by_code(transaction_data.destination_bank_code)
        
        # 2. Create local transaction record (PENDING)
        transaction_ref = str(uuid.uuid4())
        new_transaction = Transaction(
            transaction_ref=transaction_ref,
            status=TransactionStatus.PENDING,
            **transaction_data.dict(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.db.add(new_transaction)
        self.db.commit()
        self.db.refresh(new_transaction)
        
        logger.info(f"Transaction {transaction_ref} created. Initiating NIP transfer.")
        
        # 3. Initiate NIP transfer via NIBSS client
        try:
            session_id, response_code, response_message = self.nibss_client.fund_transfer(new_transaction)
            
            # 4. Update transaction status based on NIBSS response
            new_transaction.nibss_session_id = session_id
            new_transaction.response_code = response_code
            new_transaction.response_message = response_message
            
            if response_code == "00":
                new_transaction.status = TransactionStatus.SUCCESS
            elif response_code == "90":
                # NIBSS timeout/pending: keep as TIMEOUT for async requery
                new_transaction.status = TransactionStatus.TIMEOUT
            else:
                new_transaction.status = TransactionStatus.FAILED
                
            self.db.commit()
            self.db.refresh(new_transaction)
            
        except NIBSSAPIError as e:
            # Handle API communication failure
            new_transaction.status = TransactionStatus.FAILED
            new_transaction.response_code = "99"
            new_transaction.response_message = f"API Communication Error: {e.message}"
            self.db.commit()
            self.db.refresh(new_transaction)
            raise ServiceException(f"Failed to communicate with NIBSS API: {e.message}", status_code=503)
            
        return new_transaction

    def get_transaction_by_ref(self, transaction_ref: str) -> Transaction:
        """Retrieves a transaction by its unique reference."""
        transaction = self.db.query(Transaction).filter(Transaction.transaction_ref == transaction_ref).first()
        if not transaction:
            raise TransactionNotFound(transaction_ref)
        return transaction

    def list_transactions(self, skip: int = 0, limit: int = 100) -> Tuple[List[Transaction], int]:
        """Retrieves a paginated list of transactions."""
        query = self.db.query(Transaction).order_by(Transaction.created_at.desc())
        total = query.count()
        transactions = query.offset(skip).limit(limit).all()
        return transactions, total

    def update_transaction_status(self, transaction_ref: str, update_data: TransactionUpdate) -> Transaction:
        """
        Updates the status of a transaction (e.g., via a webhook or background job).
        """
        transaction = self.get_transaction_by_ref(transaction_ref)
        
        # Update fields
        transaction.status = update_data.status
        transaction.response_code = update_data.response_code
        transaction.response_message = update_data.response_message
        transaction.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(transaction)
        logger.info(f"Transaction {transaction_ref} status updated to {transaction.status.value}")
        return transaction

    def delete_transaction(self, transaction_ref: str) -> Dict[str, Any]:
        """
        Deletes a transaction record. (Caution: Not typical for financial data).
        """
        transaction = self.get_transaction_by_ref(transaction_ref)
        self.db.delete(transaction)
        self.db.commit()
        logger.warning(f"Transaction {transaction_ref} deleted.")
        return {"message": f"Transaction {transaction_ref} deleted successfully."}

# --- Dependency Injection Helper ---

def get_nibss_service(db: Session) -> NIBSSService:
    """
    Returns an instance of the NIBSSService with a database session.
    """
    return NIBSSService(db)
