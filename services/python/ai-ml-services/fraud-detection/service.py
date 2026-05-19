import logging
from typing import List, Optional, Type, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError as DBIntegrityError
from pydantic import BaseModel

from . import models, schemas
from .database import NotFoundError, IntegrityError, DatabaseError
from .config import settings

log = logging.getLogger(__name__)

# --- Custom Exceptions for Service Layer ---

class ServiceException(Exception):
    """Base exception for service-layer errors."""
    pass

class ItemNotFound(ServiceException):
    """Exception raised when a requested item is not found."""
    def __init__(self, model_name: str, item_id: int) -> None:
        self.model_name = model_name
        self.item_id = item_id
        super().__init__(f"{model_name} with ID {item_id} not found.")

class DuplicateItem(ServiceException):
    """Exception raised when attempting to create an item that already exists (e.g., unique constraint violation)."""
    def __init__(self, model_name: str, field: str, value: Any) -> None:
        self.model_name = model_name
        self.field = field
        self.value = value
        super().__init__(f"Duplicate {model_name}: {field} '{value}' already exists.")

# --- Base Service Class ---

class BaseService:
    """Base class for all services to handle common CRUD operations."""
    def __init__(self, db: AsyncSession, model: Type[models.Base], model_name: str) -> None:
        self.db = db
        self.model = model
        self.model_name = model_name

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Type[models.Base]]:
        """Retrieve a list of all items."""
        log.debug(f"Fetching all {self.model_name}s (skip={skip}, limit={limit})")
        result = await self.db.execute(select(self.model).offset(skip).limit(limit))
        return result.scalars().all()

    async def get_by_id(self, item_id: int) -> Type[models.Base]:
        """Retrieve a single item by its ID."""
        log.debug(f"Fetching {self.model_name} with ID {item_id}")
        result = await self.db.execute(select(self.model).filter(self.model.id == item_id))
        item = result.scalar_one_or_none()
        if item is None:
            raise ItemNotFound(self.model_name, item_id)
        return item

    async def create(self, item_data: BaseModel) -> Type[models.Base]:
        """Create a new item."""
        new_item = self.model(**item_data.model_dump())
        self.db.add(new_item)
        try:
            await self.db.commit()
            await self.db.refresh(new_item)
            log.info(f"Created new {self.model_name} with ID {new_item.id}")
            return new_item
        except DBIntegrityError as e:
            await self.db.rollback()
            # A more robust implementation would parse the error message to find the exact duplicate field
            raise DuplicateItem(self.model_name, "unique field", "value") from e
        except Exception as e:
            await self.db.rollback()
            log.error(f"Error creating {self.model_name}: {e}")
            raise DatabaseError(f"Could not create {self.model_name}.") from e

    async def update(self, item_id: int, item_data: BaseModel) -> Type[models.Base]:
        """Update an existing item."""
        item = await self.get_by_id(item_id)
        update_data = item_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(item, key, value)
        
        try:
            await self.db.commit()
            await self.db.refresh(item)
            log.info(f"Updated {self.model_name} with ID {item_id}")
            return item
        except DBIntegrityError as e:
            await self.db.rollback()
            raise DuplicateItem(self.model_name, "unique field", "value") from e
        except Exception as e:
            await self.db.rollback()
            log.error(f"Error updating {self.model_name} with ID {item_id}: {e}")
            raise DatabaseError(f"Could not update {self.model_name}.") from e

    async def delete(self, item_id: int) -> None:
        """Delete an item by its ID."""
        item = await self.get_by_id(item_id)
        await self.db.delete(item)
        await self.db.commit()
        log.info(f"Deleted {self.model_name} with ID {item_id}")

# --- Specific Services ---

class TenantService(BaseService):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, models.Tenant, "Tenant")

class FraudRuleService(BaseService):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, models.FraudRule, "FraudRule")

    async def get_active_rules_by_tenant(self, tenant_id: int) -> List[models.FraudRule]:
        """Retrieve all active fraud rules for a specific tenant."""
        log.debug(f"Fetching active FraudRules for Tenant ID {tenant_id}")
        stmt = select(models.FraudRule).filter(
            models.FraudRule.tenant_id == tenant_id,
            models.FraudRule.status == models.RuleStatus.ACTIVE
        ).order_by(models.FraudRule.severity_score.desc())
        result = await self.db.execute(stmt)
        return result.scalars().all()

class FraudReportService(BaseService):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, models.FraudReport, "FraudReport")

class TransactionService(BaseService):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, models.Transaction, "Transaction")
        self.rule_service = FraudRuleService(db)
        self.report_service = FraudReportService(db)

    async def _evaluate_rule(self, rule: models.FraudRule, transaction_data: schemas.TransactionCreate) -> Optional[schemas.FraudReportCreate]:
        """
        Simulates the evaluation of a single rule expression against transaction data.
        In a real system, this would use an expression engine (e.g., Drools, PyKnow).
        For this implementation, we will simulate a match based on a simple check.
        """
        # NOTE: This is a SIMULATION of rule evaluation.
        # A production system would use a dedicated rule engine.
        
        # Simple simulation: if the rule name contains "HighValue" and amount > 500, it matches.
        if "HighValue" in rule.name and transaction_data.amount > 500:
            log.info(f"Rule '{rule.name}' (ID: {rule.id}) matched transaction {transaction_data.user_id}.")
            return schemas.FraudReportCreate(
                transaction_id=0, # Will be set after transaction creation
                rule_id=rule.id,
                decision=schemas.FraudDecision.REVIEW,
                score=rule.severity_score,
                reason=f"Rule '{rule.name}' matched: {rule.description}",
                model_version=settings.ML_MODEL_VERSION
            )
        return None

    async def _run_ml_model(self, transaction_data: schemas.TransactionCreate) -> schemas.FraudReportCreate:
        """
        Simulates calling an external ML model for a fraud score.
        """
        # NOTE: This is a SIMULATION of an ML model call.
        # A production system would use requests to call the endpoint in settings.ML_MODEL_ENDPOINT.
        
        # Simple simulation: score based on amount and IP address length
        score = min(100.0, transaction_data.amount / 10.0 + len(transaction_data.ip_address))
        
        if score > 90:
            decision = schemas.FraudDecision.FRAUD
            reason = "ML Model predicted high fraud risk."
        elif score > 50:
            decision = schemas.FraudDecision.REVIEW
            reason = "ML Model predicted moderate fraud risk."
        else:
            decision = schemas.FraudDecision.SAFE
            reason = "ML Model predicted low fraud risk."

        log.info(f"ML Model scored transaction {transaction_data.user_id} with score {score:.2f} and decision {decision.value}.")

        return schemas.FraudReportCreate(
            transaction_id=0, # Will be set after transaction creation
            rule_id=None,
            decision=decision,
            score=score,
            reason=reason,
            model_version=settings.ML_MODEL_VERSION
        )

    async def process_transaction(self, transaction_data: schemas.TransactionCreate) -> models.Transaction:
        """
        The core business logic:
        1. Create the transaction record.
        2. Run rule-based checks.
        3. Run ML-based checks.
        4. Aggregate reports and determine final transaction status.
        5. Create fraud reports.
        """
        # 1. Create the transaction record (initially PENDING)
        transaction_model = models.Transaction(**transaction_data.model_dump(), status=models.TransactionStatus.PENDING)
        self.db.add(transaction_model)
        await self.db.flush() # Flush to get the transaction ID

        transaction_id = transaction_model.id
        reports_to_create: List[schemas.FraudReportCreate] = []
        
        # 2. Run rule-based checks
        active_rules = await self.rule_service.get_active_rules_by_tenant(transaction_data.tenant_id)
        for rule in active_rules:
            report = await self._evaluate_rule(rule, transaction_data)
            if report:
                reports_to_create.append(report)

        # 3. Run ML-based checks
        ml_report = await self._run_ml_model(transaction_data)
        reports_to_create.append(ml_report)

        # 4. Aggregate reports and determine final transaction status
        final_decision = schemas.FraudDecision.SAFE
        max_score = 0.0
        
        for report in reports_to_create:
            report.transaction_id = transaction_id # Set the actual ID
            max_score = max(max_score, report.score)
            
            # Decision hierarchy: FRAUD > REVIEW > SAFE
            if report.decision == schemas.FraudDecision.FRAUD:
                final_decision = schemas.FraudDecision.FRAUD
            elif report.decision == schemas.FraudDecision.REVIEW and final_decision != schemas.FraudDecision.FRAUD:
                final_decision = schemas.FraudDecision.REVIEW

        # Set final transaction status
        if final_decision == schemas.FraudDecision.FRAUD:
            transaction_model.status = models.TransactionStatus.DECLINED
        elif final_decision == schemas.FraudDecision.REVIEW:
            # For REVIEW, we keep it PENDING for manual review
            transaction_model.status = models.TransactionStatus.PENDING
        else:
            transaction_model.status = models.TransactionStatus.APPROVED

        # 5. Create fraud reports
        for report_data in reports_to_create:
            report_model = models.FraudReport(**report_data.model_dump())
            self.db.add(report_model)

        try:
            await self.db.commit()
            await self.db.refresh(transaction_model)
            log.info(f"Processed transaction {transaction_id}. Final status: {transaction_model.status.name}")
            return transaction_model
        except Exception as e:
            await self.db.rollback()
            log.error(f"Transaction processing failed for tenant {transaction_data.tenant_id}: {e}")
            raise DatabaseError("Transaction processing failed due to a database error.") from e

# --- Dependency Injection Function ---

def get_tenant_service(db: AsyncSession) -> TenantService:
    return TenantService(db)

def get_transaction_service(db: AsyncSession) -> TransactionService:
    return TransactionService(db)

def get_fraud_rule_service(db: AsyncSession) -> FraudRuleService:
    return FraudRuleService(db)

def get_fraud_report_service(db: AsyncSession) -> FraudReportService:
    return FraudReportService(db)