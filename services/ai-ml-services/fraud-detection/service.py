import ast
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

class RuleEvaluationError(ServiceException):
    """Raised when a fraud rule expression cannot be evaluated truthfully."""
    pass

class MlModelUnavailable(ServiceException):
    """Raised when the external ML scoring endpoint is not configured or fails.

    We NEVER fabricate an ML fraud score — if the model cannot be reached,
    transaction processing fails loud instead of silently approving/declining
    with an invented score.
    """
    pass

# --- Safe fraud-rule expression evaluation ---

_ALLOWED_COMPARE_OPS = (ast.Eq, ast.NotEq, ast.Gt, ast.GtE, ast.Lt, ast.LtE, ast.In, ast.NotIn)


def _eval_rule_node(node: ast.AST, context: dict) -> Any:
    """Recursive descent over a restricted Python-expression AST."""
    if isinstance(node, ast.Expression):
        return _eval_rule_node(node.body, context)
    if isinstance(node, ast.BoolOp):
        values = [_eval_rule_node(v, context) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
        raise RuleEvaluationError(f"unsupported boolean operator: {ast.dump(node.op)}")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval_rule_node(node.operand, context)
    if isinstance(node, ast.Compare):
        left = _eval_rule_node(node.left, context)
        for op, comparator in zip(node.ops, node.comparators):
            if not isinstance(op, _ALLOWED_COMPARE_OPS):
                raise RuleEvaluationError(f"unsupported comparison operator: {ast.dump(op)}")
            right = _eval_rule_node(comparator, context)
            if isinstance(op, ast.Eq):
                ok = left == right
            elif isinstance(op, ast.NotEq):
                ok = left != right
            elif isinstance(op, ast.Gt):
                ok = left > right
            elif isinstance(op, ast.GtE):
                ok = left >= right
            elif isinstance(op, ast.Lt):
                ok = left < right
            elif isinstance(op, ast.LtE):
                ok = left <= right
            elif isinstance(op, ast.In):
                ok = left in right
            else:  # ast.NotIn
                ok = left not in right
            if not ok:
                return False
            left = right
        return True
    if isinstance(node, ast.Name):
        if node.id not in context:
            raise RuleEvaluationError(f"unknown field '{node.id}' in rule expression")
        return context[node.id]
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_eval_rule_node(e, context) for e in node.elts]
    raise RuleEvaluationError(f"unsupported syntax in rule expression: {ast.dump(node)}")


def evaluate_rule_expression(expression: str, context: dict) -> bool:
    """
    Evaluate a fraud rule expression such as
    "amount > 1000 AND currency == 'NGN'" against the transaction context.

    Supported: AND/OR/NOT, parentheses, ==, !=, >, >=, <, <=, in, not in,
    numeric/string/boolean constants, and transaction field names.
    Anything else raises RuleEvaluationError — a rule that cannot be evaluated
    truthfully must fail loud, never silently "match" or "not match".
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise RuleEvaluationError(f"invalid rule expression '{expression}': {exc}") from exc
    return bool(_eval_rule_node(tree, context))


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
        Evaluate a rule's `rule_expression` against the real transaction data
        using the safe AST evaluator (AND/OR/NOT, comparisons, in/not in).
        Rules that cannot be evaluated truthfully raise RuleEvaluationError.
        """
        context = {
            "tenant_id": transaction_data.tenant_id,
            "amount": transaction_data.amount,
            "currency": transaction_data.currency,
            "user_id": transaction_data.user_id,
            "merchant_id": transaction_data.merchant_id,
            "ip_address": transaction_data.ip_address,
        }
        matched = evaluate_rule_expression(rule.rule_expression, context)
        if matched:
            log.info(f"Rule '{rule.name}' (ID: {rule.id}) matched transaction for user {transaction_data.user_id}.")
            return schemas.FraudReportCreate(
                transaction_id=0,  # Will be set after transaction creation
                rule_id=rule.id,
                decision=schemas.FraudDecision.REVIEW,
                score=rule.severity_score,
                reason=f"Rule '{rule.name}' matched: {rule.description}",
                model_version=settings.ML_MODEL_VERSION
            )
        return None

    async def _run_ml_model(self, transaction_data: schemas.TransactionCreate) -> schemas.FraudReportCreate:
        """
        Call the configured external ML scoring endpoint for a fraud score.

        FAIL LOUD: if ML_MODEL_ENDPOINT is not configured, unreachable, times
        out, or returns a response without a numeric 'score', MlModelUnavailable
        is raised. A fabricated score is never returned.
        """
        if not settings.ML_MODEL_ENDPOINT:
            raise MlModelUnavailable(
                "ML_MODEL_ENDPOINT is not configured; refusing to fabricate a fraud score"
            )

        import httpx
        payload = {
            "tenant_id": transaction_data.tenant_id,
            "amount": transaction_data.amount,
            "currency": transaction_data.currency,
            "user_id": transaction_data.user_id,
            "merchant_id": transaction_data.merchant_id,
            "ip_address": transaction_data.ip_address,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(settings.ML_MODEL_ENDPOINT, json=payload)
        except Exception as exc:
            raise MlModelUnavailable(f"ML scoring endpoint unreachable: {exc}") from exc
        if resp.status_code != 200:
            raise MlModelUnavailable(
                f"ML scoring endpoint returned HTTP {resp.status_code}"
            )
        data = resp.json()
        if "score" not in data or not isinstance(data["score"], (int, float)):
            raise MlModelUnavailable("ML scoring endpoint response missing numeric 'score'")

        score = float(data["score"])

        decision_raw = data.get("decision")
        if decision_raw in ("FRAUD", "REVIEW", "SAFE"):
            decision = schemas.FraudDecision(decision_raw)
        elif score > 90:
            decision = schemas.FraudDecision.FRAUD
        elif score > 50:
            decision = schemas.FraudDecision.REVIEW
        else:
            decision = schemas.FraudDecision.SAFE
        reason = f"ML model scored transaction {score:.2f} -> {decision.value}."

        log.info(f"ML model scored transaction for user {transaction_data.user_id}: {score:.2f} ({decision.value}).")

        return schemas.FraudReportCreate(
            transaction_id=0,  # Will be set after transaction creation
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
        await self.db.flush()  # Flush to get the transaction ID

        transaction_id = transaction_model.id
        reports_to_create: List[schemas.FraudReportCreate] = []

        # 2. Run rule-based checks (real expression evaluation; errors fail loud)
        active_rules = await self.rule_service.get_active_rules_by_tenant(transaction_data.tenant_id)
        for rule in active_rules:
            report = await self._evaluate_rule(rule, transaction_data)
            if report:
                reports_to_create.append(report)

        # 3. Run ML-based checks (real endpoint call; errors fail loud)
        ml_report = await self._run_ml_model(transaction_data)
        reports_to_create.append(ml_report)

        # 4. Aggregate reports and determine final transaction status
        final_decision = schemas.FraudDecision.SAFE
        max_score = 0.0

        for report in reports_to_create:
            report.transaction_id = transaction_id  # Set the actual ID
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
