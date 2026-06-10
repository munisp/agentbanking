"""
Recurring Payments Service
Manages scheduled recurring payments with flexible scheduling

Features:
- Multiple schedule types (daily, weekly, monthly, custom)
- Automatic execution with retry logic
- Payment history tracking
- Failure notifications
- Pause/resume functionality
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
import json

import httpx
from croniter import croniter


class ScheduleType(Enum):
    """Recurring payment schedule types"""
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    BIWEEKLY = "BIWEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    YEARLY = "YEARLY"
    CUSTOM = "CUSTOM"  # Uses cron expression


class PaymentStatus(Enum):
    """Recurring payment status"""
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ExecutionStatus(Enum):
    """Individual execution status"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRYING = "RETRYING"


@dataclass
class RecurringPayment:
    """Recurring payment configuration"""
    payment_id: str
    user_id: str
    recipient_id: str
    amount: Decimal
    currency: str
    schedule_type: str
    cron_expression: Optional[str]
    start_date: datetime
    end_date: Optional[datetime]
    next_execution: datetime
    status: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    metadata: Dict
    created_at: datetime
    updated_at: datetime


@dataclass
class PaymentExecution:
    """Individual payment execution record"""
    execution_id: str
    payment_id: str
    scheduled_at: datetime
    executed_at: Optional[datetime]
    status: str
    transaction_id: Optional[str]
    amount: Decimal
    currency: str
    error_message: Optional[str]
    retry_count: int
    metadata: Dict


class RecurringPaymentsService:
    """
    Recurring Payments Service
    
    Manages scheduled recurring payments with:
    - Flexible scheduling (daily, weekly, monthly, custom cron)
    - Automatic execution with retry logic
    - Payment history and audit trail
    - Pause/resume functionality
    - Failure notifications
    - End date support
    """
    
    def __init__(
        self,
        payment_api_url: str,
        notification_api_url: str,
        max_retries: int = 3,
        retry_delay_minutes: int = 30
    ):
        """
        Initialize recurring payments service
        
        Args:
            payment_api_url: Payment processing API URL
            notification_api_url: Notification service URL
            max_retries: Maximum retry attempts for failed payments
            retry_delay_minutes: Delay between retries in minutes
        """
        self.payment_api_url = payment_api_url
        self.notification_api_url = notification_api_url
        self.max_retries = max_retries
        self.retry_delay_minutes = retry_delay_minutes
        
        # HTTP client
        self.client: Optional[httpx.AsyncClient] = None
        
        # In-memory storage (would use database in production)
        self._payments: Dict[str, RecurringPayment] = {}
        self._executions: Dict[str, List[PaymentExecution]] = {}
        
        # Execution queue
        self._execution_queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.client = httpx.AsyncClient(timeout=30)
        # Start background worker
        self._worker_task = asyncio.create_task(self._execution_worker())
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        # Stop worker
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        if self.client:
            await self.client.aclose()
    
    async def create_recurring_payment(
        self,
        user_id: str,
        recipient_id: str,
        amount: Decimal,
        currency: str,
        schedule_type: ScheduleType,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        cron_expression: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> RecurringPayment:
        """
        Create a new recurring payment
        
        Args:
            user_id: User identifier
            recipient_id: Recipient identifier
            amount: Payment amount
            currency: Currency code
            schedule_type: Schedule type
            start_date: Start date for payments
            end_date: Optional end date
            cron_expression: Custom cron expression (for CUSTOM schedule)
            metadata: Optional metadata
            
        Returns:
            RecurringPayment object
        """
        if amount <= 0:
            raise ValueError("Payment amount must be positive")
        
        if schedule_type == ScheduleType.CUSTOM and not cron_expression:
            raise ValueError("Cron expression required for CUSTOM schedule")
        
        if end_date and end_date <= start_date:
            raise ValueError("End date must be after start date")
        
        payment_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        # Generate cron expression if not custom
        if schedule_type != ScheduleType.CUSTOM:
            cron_expression = self._generate_cron_expression(schedule_type, start_date)
        
        # Calculate next execution
        next_execution = self._calculate_next_execution(
            cron_expression,
            start_date
        )
        
        payment = RecurringPayment(
            payment_id=payment_id,
            user_id=user_id,
            recipient_id=recipient_id,
            amount=amount,
            currency=currency,
            schedule_type=schedule_type.value,
            cron_expression=cron_expression,
            start_date=start_date,
            end_date=end_date,
            next_execution=next_execution,
            status=PaymentStatus.ACTIVE.value,
            total_executions=0,
            successful_executions=0,
            failed_executions=0,
            metadata=metadata or {},
            created_at=now,
            updated_at=now
        )
        
        self._payments[payment_id] = payment
        self._executions[payment_id] = []
        
        return payment
    
    def _generate_cron_expression(
        self,
        schedule_type: ScheduleType,
        start_date: datetime
    ) -> str:
        """Generate cron expression for schedule type"""
        minute = start_date.minute
        hour = start_date.hour
        day = start_date.day
        
        if schedule_type == ScheduleType.DAILY:
            return f"{minute} {hour} * * *"
        elif schedule_type == ScheduleType.WEEKLY:
            weekday = start_date.weekday()
            return f"{minute} {hour} * * {weekday}"
        elif schedule_type == ScheduleType.BIWEEKLY:
            # Every 2 weeks on same day
            weekday = start_date.weekday()
            return f"{minute} {hour} * * {weekday}"  # Would need additional logic
        elif schedule_type == ScheduleType.MONTHLY:
            return f"{minute} {hour} {day} * *"
        elif schedule_type == ScheduleType.QUARTERLY:
            # Every 3 months on same day
            month = start_date.month
            return f"{minute} {hour} {day} {month}/3 *"
        elif schedule_type == ScheduleType.YEARLY:
            month = start_date.month
            return f"{minute} {hour} {day} {month} *"
        else:
            raise ValueError(f"Unsupported schedule type: {schedule_type}")
    
    def _calculate_next_execution(
        self,
        cron_expression: str,
        base_time: datetime
    ) -> datetime:
        """Calculate next execution time from cron expression"""
        cron = croniter(cron_expression, base_time)
        return cron.get_next(datetime)
    
    async def get_recurring_payment(self, payment_id: str) -> RecurringPayment:
        """Get recurring payment by ID"""
        if payment_id not in self._payments:
            raise ValueError(f"Payment not found: {payment_id}")
        return self._payments[payment_id]
    
    async def list_recurring_payments(
        self,
        user_id: str,
        status: Optional[PaymentStatus] = None
    ) -> List[RecurringPayment]:
        """List recurring payments for a user"""
        payments = [
            p for p in self._payments.values()
            if p.user_id == user_id
        ]
        
        if status:
            payments = [p for p in payments if p.status == status.value]
        
        return payments
    
    async def pause_recurring_payment(self, payment_id: str) -> RecurringPayment:
        """Pause a recurring payment"""
        payment = await self.get_recurring_payment(payment_id)
        
        if payment.status != PaymentStatus.ACTIVE.value:
            raise ValueError(f"Cannot pause payment in status: {payment.status}")
        
        payment.status = PaymentStatus.PAUSED.value
        payment.updated_at = datetime.now(timezone.utc)
        
        return payment
    
    async def resume_recurring_payment(self, payment_id: str) -> RecurringPayment:
        """Resume a paused recurring payment"""
        payment = await self.get_recurring_payment(payment_id)
        
        if payment.status != PaymentStatus.PAUSED.value:
            raise ValueError(f"Cannot resume payment in status: {payment.status}")
        
        payment.status = PaymentStatus.ACTIVE.value
        payment.updated_at = datetime.now(timezone.utc)
        
        # Recalculate next execution
        payment.next_execution = self._calculate_next_execution(
            payment.cron_expression,
            datetime.now(timezone.utc)
        )
        
        return payment
    
    async def cancel_recurring_payment(self, payment_id: str) -> RecurringPayment:
        """Cancel a recurring payment"""
        payment = await self.get_recurring_payment(payment_id)
        
        if payment.status == PaymentStatus.CANCELLED.value:
            raise ValueError("Payment already cancelled")
        
        payment.status = PaymentStatus.CANCELLED.value
        payment.updated_at = datetime.now(timezone.utc)
        
        return payment
    
    async def update_recurring_payment(
        self,
        payment_id: str,
        amount: Optional[Decimal] = None,
        schedule_type: Optional[ScheduleType] = None,
        cron_expression: Optional[str] = None,
        end_date: Optional[datetime] = None
    ) -> RecurringPayment:
        """Update recurring payment configuration"""
        payment = await self.get_recurring_payment(payment_id)
        
        if payment.status not in [PaymentStatus.ACTIVE.value, PaymentStatus.PAUSED.value]:
            raise ValueError(f"Cannot update payment in status: {payment.status}")
        
        if amount is not None:
            if amount <= 0:
                raise ValueError("Amount must be positive")
            payment.amount = amount
        
        if schedule_type is not None:
            payment.schedule_type = schedule_type.value
            if schedule_type != ScheduleType.CUSTOM:
                payment.cron_expression = self._generate_cron_expression(
                    schedule_type,
                    payment.start_date
                )
        
        if cron_expression is not None:
            payment.cron_expression = cron_expression
        
        if end_date is not None:
            if end_date <= payment.start_date:
                raise ValueError("End date must be after start date")
            payment.end_date = end_date
        
        # Recalculate next execution
        payment.next_execution = self._calculate_next_execution(
            payment.cron_expression,
            datetime.now(timezone.utc)
        )
        
        payment.updated_at = datetime.now(timezone.utc)
        
        return payment
    
    async def get_payment_history(
        self,
        payment_id: str,
        limit: int = 100
    ) -> List[PaymentExecution]:
        """Get execution history for a recurring payment"""
        if payment_id not in self._executions:
            return []
        
        executions = self._executions[payment_id]
        return sorted(
            executions,
            key=lambda e: e.scheduled_at,
            reverse=True
        )[:limit]
    
    async def check_and_schedule_payments(self):
        """Check for payments due and schedule them"""
        now = datetime.now(timezone.utc)
        
        for payment in self._payments.values():
            if payment.status != PaymentStatus.ACTIVE.value:
                continue
            
            # Check if end date passed
            if payment.end_date and now > payment.end_date:
                payment.status = PaymentStatus.COMPLETED.value
                payment.updated_at = now
                continue
            
            # Check if payment is due
            if now >= payment.next_execution:
                await self._schedule_execution(payment)
                
                # Calculate next execution
                payment.next_execution = self._calculate_next_execution(
                    payment.cron_expression,
                    now
                )
                payment.updated_at = now
    
    async def _schedule_execution(self, payment: RecurringPayment):
        """Schedule a payment execution"""
        execution_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        execution = PaymentExecution(
            execution_id=execution_id,
            payment_id=payment.payment_id,
            scheduled_at=now,
            executed_at=None,
            status=ExecutionStatus.PENDING.value,
            transaction_id=None,
            amount=payment.amount,
            currency=payment.currency,
            error_message=None,
            retry_count=0,
            metadata={}
        )
        
        self._executions[payment.payment_id].append(execution)
        payment.total_executions += 1
        
        # Add to execution queue
        await self._execution_queue.put((payment, execution))
    
    async def _execution_worker(self):
        """Background worker for executing payments"""
        while True:
            try:
                payment, execution = await self._execution_queue.get()
                await self._execute_payment(payment, execution)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Execution worker error: {e}")
    
    async def _execute_payment(
        self,
        payment: RecurringPayment,
        execution: PaymentExecution
    ):
        """Execute a single payment"""
        if not self.client:
            return
        
        execution.status = ExecutionStatus.PROCESSING.value
        
        try:
            # Call payment API
            response = await self.client.post(
                f"{self.payment_api_url}/transactions/initiate",
                json={
                    "user_id": payment.user_id,
                    "recipient_id": payment.recipient_id,
                    "amount": float(payment.amount),
                    "currency": payment.currency,
                    "metadata": {
                        "recurring_payment_id": payment.payment_id,
                        "execution_id": execution.execution_id
                    }
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                execution.status = ExecutionStatus.SUCCESS.value
                execution.transaction_id = data.get("transaction_id")
                execution.executed_at = datetime.now(timezone.utc)
                payment.successful_executions += 1
            else:
                raise Exception(f"Payment API error: {response.status_code}")
                
        except Exception as e:
            execution.error_message = str(e)
            execution.retry_count += 1
            
            if execution.retry_count < self.max_retries:
                execution.status = ExecutionStatus.RETRYING.value
                # Schedule retry
                await asyncio.sleep(self.retry_delay_minutes * 60)
                await self._execution_queue.put((payment, execution))
            else:
                execution.status = ExecutionStatus.FAILED.value
                payment.failed_executions += 1
                
                # Send failure notification
                await self._send_failure_notification(payment, execution)
    
    async def _send_failure_notification(
        self,
        payment: RecurringPayment,
        execution: PaymentExecution
    ):
        """Send notification for failed payment"""
        if not self.client:
            return
        
        try:
            await self.client.post(
                f"{self.notification_api_url}/notifications",
                json={
                    "user_id": payment.user_id,
                    "type": "recurring_payment_failed",
                    "title": "Recurring Payment Failed",
                    "message": f"Payment of {payment.amount} {payment.currency} failed after {execution.retry_count} attempts",
                    "data": {
                        "payment_id": payment.payment_id,
                        "execution_id": execution.execution_id,
                        "error": execution.error_message
                    }
                }
            )
        except Exception as e:
            print(f"Failed to send notification: {e}")
