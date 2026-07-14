import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Transaction, NameEnquiry, Bank, TransactionStatus
from schemas import (
    TransactionCreate,
    NameEnquiryRequest,
    NameEnquiryResponse,
    TransactionUpdate,
    BankBase,
    TransactionListResponse,
)
from fastapi import Depends
from database import get_db
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
    """Raised when the mock NIBSS API returns an error."""
    def __init__(self, message: str, status_code: int = 503) -> None:
        super().__init__(f"NIBSS API Error: {message}", status_code=status_code)

# --- 2. Logging Setup ---

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)

# --- 3. Mock NIBSS Client (Simulating External API) ---

class MockNIBSSClient:
    """
    A mock client to simulate interaction with the external NIBSS API.
    In a real application, this would use 'requests' to call the actual NIBSS endpoints.
    """
    def __init__(self) -> None:
        logger.info(f"Initialized Mock NIBSS Client. Base URL: {settings.NIBSS_BASE_URL}")

    def name_enquiry(self, request: NameEnquiryRequest) -> NameEnquiryResponse:
        """Simulates a Name Enquiry call."""
        logger.info(f"Mock NIBSS: Performing Name Enquiry for account {request.account_number} at bank {request.bank_code}")
        
        # Simple mock logic
        if request.account_number.endswith("000"):
            # Simulate a successful response
            return NameEnquiryResponse(
                account_number=request.account_number,
                bank_code=request.bank_code,
                account_name="JOHN DOE",
                bvn="12345678901",
                response_code="00",
                response_message="Successful Name Enquiry"
            )
        elif request.account_number.endswith("404"):
            # Simulate account not found
            return NameEnquiryResponse(
                account_number=request.account_number,
                bank_code=request.bank_code,
                account_name="",
                bvn=None,
                response_code="404",
                response_message="Account Not Found"
            )
        else:
            # Simulate a general NIBSS error
            raise NIBSSAPIError("General NIBSS Name Enquiry failure.", status_code=503)

    def fund_transfer(self, transaction: Transaction) -> Tuple[Optional[str], str, str]:
        """
        Simulates a NIBSS Instant Payment (NIP) fund transfer.
        Returns: (nibss_session_id, response_code, response_message)
        """
        logger.info(f"Mock NIBSS: Initiating NIP for ref {transaction.transaction_ref} with amount {transaction.amount}")
        
        # Simple mock logic based on amount
        if transaction.amount > 1000000:
            # Simulate a failure due to limit
            return None, "99", "Transaction amount exceeds limit."
        elif transaction.amount == 100:
            # Simulate a successful transaction
            return str(uuid.uuid4()), "00", "Transaction successful."
        else:
            # Simulate a pending/timeout scenario
            return None, "90", "Transaction is pending or timed out."

# --- 4. Service Layer Implementation ---

class NIBSSService:
    """
    Business logic layer for NIBSS integration.
    Handles database operations and interaction with the NIBSS client.
    """
    def __init__(self, db: Session) -> None:
        self.db = db
        self.nibss_client = MockNIBSSClient()

    # --- Bank Operations ---

    def get_bank_by_code(self, bank_code: str) -> Bank:
        """Retrieves a bank by its NIBSS code."""
        bank = self.db.query(Bank).filter(Bank.bank_code == bank_code).first()
        if not bank:
            raise BankNotFound(bank_code)
        return bank

    def get_all_banks(self) -> List[Bank]:
        """Retrieves all active banks."""
        banks = self.db.query(Bank).filter(Bank.is_active == True).all()
        return [Bank.from_orm(bank) for bank in banks]

    # --- Name Enquiry Operations ---

    def perform_name_enquiry(self, request: NameEnquiryRequest) -> NameEnquiryResponse:
        """
        Performs a name enquiry via the NIBSS client and saves the result.
        """
        # 1. Validate bank code exists locally
        self.get_bank_by_code(request.bank_code)
        
        # 2. Call mock NIBSS API
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
                # Keep PENDING for a real-world async process, but for this sync mock, we'll mark it TIMEOUT
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
        return Transaction.from_orm(transaction)

    def list_transactions(self, skip: int = 0, limit: int = 100) -> TransactionListResponse:
        """Retrieves a paginated list of transactions."""
        query = self.db.query(Transaction).order_by(Transaction.created_at.desc())
        total = query.count()
        transactions = query.offset(skip).limit(limit).all()
        return TransactionListResponse(
            total=total,
            page=skip // limit + 1,
            size=len(transactions),
            items=[Transaction.from_orm(tx) for tx in transactions]
        )

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

def get_nibss_service(db: Session = Depends(get_db)) -> NIBSSService:
    """
    Returns an instance of the NIBSSService with a database session.
    """
    return NIBSSService(db)
