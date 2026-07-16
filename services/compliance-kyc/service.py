from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from typing import List, Optional
from models import KYCRecord, KYCDocument, KYCCheck, KYCStatus, CheckStatus
from schemas import (
    KYCRecordCreate, KYCRecordUpdate, 
    KYCDocumentCreate, KYCDocumentUpdate, 
    KYCCheckCreate, KYCCheckUpdate
)
from main import KYCServiceException
from config import logger
from fastapi import status

# --- Custom Exceptions ---
class RecordNotFoundException(KYCServiceException):
    def __init__(self, record_id: int) -> None:
        super().__init__(
            name="RecordNotFound",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"KYC Record with ID {record_id} not found."
        )

class DocumentNotFoundException(KYCServiceException):
    def __init__(self, document_id: int) -> None:
        super().__init__(
            name="DocumentNotFound",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"KYC Document with ID {document_id} not found."
        )

class CheckNotFoundException(KYCServiceException):
    def __init__(self, check_id: int) -> None:
        super().__init__(
            name="CheckNotFound",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"KYC Check with ID {check_id} not found."
        )

class DuplicateCustomerException(KYCServiceException):
    def __init__(self, customer_id: str) -> None:
        super().__init__(
            name="DuplicateCustomer",
            status_code=status.HTTP_409_CONFLICT,
            detail=f"KYC Record already exists for customer ID {customer_id}."
        )

# --- Service Layer ---
class KYCService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # --- KYC Record Operations ---
    async def create_record(self, record_in: KYCRecordCreate) -> KYCRecord:
        """Creates a new KYC record."""
        logger.info(f"Attempting to create KYC record for customer: {record_in.customer_id}")
        
        # Check for duplicate customer_id
        existing_record = await self.get_record_by_customer_id(record_in.customer_id)
        if existing_record:
            raise DuplicateCustomerException(record_in.customer_id)

        new_record = KYCRecord(**record_in.model_dump())
        self.db.add(new_record)
        
        try:
            await self.db.commit()
            await self.db.refresh(new_record)
            logger.info(f"KYC record created with ID: {new_record.id}")
            return new_record
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating KYC record: {e}")
            raise KYCServiceException(name="DatabaseError", detail="Could not create KYC record.")

    async def get_record(self, record_id: int) -> KYCRecord:
        """Retrieves a single KYC record by ID, including related documents and checks."""
        stmt = (
            select(KYCRecord)
            .where(KYCRecord.id == record_id)
            .options(selectinload(KYCRecord.documents), selectinload(KYCRecord.checks))
        )
        result = await self.db.execute(stmt)
        record = result.scalars().first()
        
        if not record:
            raise RecordNotFoundException(record_id)
        
        return record

    async def get_record_by_customer_id(self, customer_id: str) -> Optional[KYCRecord]:
        """Retrieves a single KYC record by customer ID."""
        stmt = select(KYCRecord).where(KYCRecord.customer_id == customer_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def list_records(self, skip: int = 0, limit: int = 100) -> List[KYCRecord]:
        """Lists all KYC records with pagination."""
        stmt = select(KYCRecord).offset(skip).limit(limit).order_by(KYCRecord.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_record(self, record_id: int, record_in: KYCRecordUpdate) -> KYCRecord:
        """Updates an existing KYC record."""
        record = await self.get_record(record_id) # get_record handles not found exception
        
        update_data = record_in.model_dump(exclude_unset=True)
        
        for key, value in update_data.items():
            setattr(record, key, value)
        
        try:
            await self.db.commit()
            await self.db.refresh(record)
            logger.info(f"KYC record {record_id} updated.")
            return record
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating KYC record {record_id}: {e}")
            raise KYCServiceException(name="DatabaseError", detail="Could not update KYC record.")

    async def delete_record(self, record_id: int) -> None:
        """Deletes a KYC record."""
        record = await self.get_record(record_id) # get_record handles not found exception
        
        await self.db.delete(record)
        
        try:
            await self.db.commit()
            logger.info(f"KYC record {record_id} deleted.")
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting KYC record {record_id}: {e}")
            raise KYCServiceException(name="DatabaseError", detail="Could not delete KYC record.")

    # --- Document Operations ---
    async def add_document(self, record_id: int, document_in: KYCDocumentCreate) -> KYCDocument:
        """Adds a new document to a KYC record."""
        record = await self.get_record(record_id) # Check if record exists
        
        new_document = KYCDocument(kyc_record_id=record_id, **document_in.model_dump())
        self.db.add(new_document)
        
        try:
            await self.db.commit()
            await self.db.refresh(new_document)
            logger.info(f"Document {new_document.id} added to record {record_id}.")
            return new_document
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error adding document to record {record_id}: {e}")
            raise KYCServiceException(name="DatabaseError", detail="Could not add document.")

    async def update_document_status(self, document_id: int, document_in: KYCDocumentUpdate) -> KYCDocument:
        """Updates the verification status of a document."""
        stmt = select(KYCDocument).where(KYCDocument.id == document_id)
        result = await self.db.execute(stmt)
        document = result.scalars().first()
        
        if not document:
            raise DocumentNotFoundException(document_id)
        
        document.verification_status = document_in.verification_status
        
        try:
            await self.db.commit()
            await self.db.refresh(document)
            logger.info(f"Document {document_id} status updated to {document.verification_status}.")
            return document
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating document {document_id} status: {e}")
            raise KYCServiceException(name="DatabaseError", detail="Could not update document status.")

    # --- Check Operations ---
    async def add_check(self, record_id: int, check_in: KYCCheckCreate) -> KYCCheck:
        """Adds a new check to a KYC record."""
        record = await self.get_record(record_id) # Check if record exists
        
        new_check = KYCCheck(kyc_record_id=record_id, **check_in.model_dump())
        self.db.add(new_check)
        
        try:
            await self.db.commit()
            await self.db.refresh(new_check)
            logger.info(f"Check {new_check.id} ({new_check.check_type}) added to record {record_id}.")
            return new_check
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error adding check to record {record_id}: {e}")
            raise KYCServiceException(name="DatabaseError", detail="Could not add check.")

    async def update_check_status(self, check_id: int, check_in: KYCCheckUpdate) -> KYCCheck:
        """Updates the status and response of a check."""
        stmt = select(KYCCheck).where(KYCCheck.id == check_id)
        result = await self.db.execute(stmt)
        check = result.scalars().first()
        
        if not check:
            raise CheckNotFoundException(check_id)
        
        update_data = check_in.model_dump(exclude_unset=True)
        
        for key, value in update_data.items():
            setattr(check, key, value)
        
        try:
            await self.db.commit()
            await self.db.refresh(check)
            logger.info(f"Check {check_id} status updated to {check.check_status}.")
            return check
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating check {check_id} status: {e}")
            raise KYCServiceException(name="DatabaseError", detail="Could not update check status.")

# Dependency to get the service instance
async def get_kyc_service(db: AsyncSession) -> KYCService:
    return KYCService(db)