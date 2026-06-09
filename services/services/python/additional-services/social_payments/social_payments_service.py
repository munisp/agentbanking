"""
Social Payments Service

Enables social payment features like group payments, split bills, and payment requests

Features:
- Group payments (multiple people paying one recipient)
- Split bills (one payer, multiple recipients)
- Payment requests
- Payment pools
- Social feed
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

import httpx


class PaymentRequestStatus(Enum):
    """Payment request status"""
    PENDING = "PENDING"
    PAID = "PAID"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class GroupPaymentStatus(Enum):
    """Group payment status"""
    COLLECTING = "COLLECTING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class SplitBillStatus(Enum):
    """Split bill status"""
    PENDING = "PENDING"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    FULLY_PAID = "FULLY_PAID"
    CANCELLED = "CANCELLED"


class SocialPaymentsService:
    """
    Social Payments Service
    
    Enables social payment features
    
    Features:
    - Group payments (crowdfunding style)
    - Split bills (expense sharing)
    - Payment requests (request money)
    - Payment pools (shared savings)
    - Activity feed
    """
    
    def __init__(
        self,
        payment_service_url: str,
        notification_service_url: str,
        api_key: str
    ):
        """
        Initialize social payments service
        
        Args:
            payment_service_url: Payment service endpoint
            notification_service_url: Notification service endpoint
            api_key: API key
        """
        self.payment_service_url = payment_service_url
        self.notification_service_url = notification_service_url
        self.api_key = api_key
        
        self.client: Optional[httpx.AsyncClient] = None
        
        # In-memory storage (would use database in production)
        self._payment_requests: Dict[str, Dict] = {}
        self._group_payments: Dict[str, Dict] = {}
        self._split_bills: Dict[str, Dict] = {}
        self._payment_pools: Dict[str, Dict] = {}
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=30)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def create_payment_request(
        self,
        request_id: str,
        requester_id: str,
        requester_name: str,
        payer_id: str,
        payer_name: str,
        amount: Decimal,
        currency: str,
        description: str,
        due_date: Optional[str] = None
    ) -> Dict:
        """
        Create payment request
        
        Args:
            request_id: Unique request ID
            requester_id: Requester user ID
            requester_name: Requester name
            payer_id: Payer user ID
            payer_name: Payer name
            amount: Requested amount
            currency: Currency code
            description: Request description
            due_date: Optional due date (ISO format)
            
        Returns:
            Payment request result
        """
        # Set default due date (7 days)
        if not due_date:
            due_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        
        request = {
            "request_id": request_id,
            "requester_id": requester_id,
            "requester_name": requester_name,
            "payer_id": payer_id,
            "payer_name": payer_name,
            "amount": float(amount),
            "currency": currency,
            "description": description,
            "status": PaymentRequestStatus.PENDING.value,
            "due_date": due_date,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "paid_at": None
        }
        
        self._payment_requests[request_id] = request
        
        # Send notification to payer
        await self._send_notification(
            user_id=payer_id,
            title="Payment Request",
            message=f"{requester_name} is requesting {currency} {amount} for {description}",
            action_url=f"/payments/requests/{request_id}"
        )
        
        return {
            "status": "SUCCESS",
            "request_id": request_id,
            "payment_url": f"/payments/requests/{request_id}"
        }
    
    async def pay_request(
        self,
        request_id: str,
        transaction_id: str
    ) -> Dict:
        """Pay a payment request"""
        if request_id not in self._payment_requests:
            return {"status": "NOT_FOUND"}
        
        request = self._payment_requests[request_id]
        
        if request["status"] != PaymentRequestStatus.PENDING.value:
            return {
                "status": "REJECTED",
                "reason": f"Request is {request['status']}"
            }
        
        # Process payment via payment service
        payment_result = await self._process_payment(
            from_user_id=request["payer_id"],
            to_user_id=request["requester_id"],
            amount=Decimal(str(request["amount"])),
            currency=request["currency"],
            description=f"Payment for: {request['description']}"
        )
        
        if payment_result["status"] != "SUCCESS":
            return payment_result
        
        # Update request
        request["status"] = PaymentRequestStatus.PAID.value
        request["paid_at"] = datetime.now(timezone.utc).isoformat()
        request["transaction_id"] = transaction_id
        
        # Notify requester
        await self._send_notification(
            user_id=request["requester_id"],
            title="Payment Received",
            message=f"{request['payer_name']} paid your request of {request['currency']} {request['amount']}",
            action_url=f"/transactions/{transaction_id}"
        )
        
        return {
            "status": "SUCCESS",
            "request_id": request_id,
            "transaction_id": transaction_id
        }
    
    async def create_group_payment(
        self,
        group_id: str,
        organizer_id: str,
        organizer_name: str,
        recipient_id: str,
        recipient_name: str,
        target_amount: Decimal,
        currency: str,
        title: str,
        description: str,
        contributors: List[Dict],  # [{"user_id": "...", "name": "...", "amount": 100}]
        deadline: Optional[str] = None
    ) -> Dict:
        """
        Create group payment (crowdfunding style)
        
        Multiple people contribute to pay one recipient
        
        Args:
            group_id: Unique group payment ID
            organizer_id: Organizer user ID
            organizer_name: Organizer name
            recipient_id: Recipient user ID
            recipient_name: Recipient name
            target_amount: Target amount to collect
            currency: Currency code
            title: Payment title
            description: Payment description
            contributors: List of contributors with amounts
            deadline: Optional deadline (ISO format)
            
        Returns:
            Group payment result
        """
        if not deadline:
            deadline = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
        
        group_payment = {
            "group_id": group_id,
            "organizer_id": organizer_id,
            "organizer_name": organizer_name,
            "recipient_id": recipient_id,
            "recipient_name": recipient_name,
            "target_amount": float(target_amount),
            "collected_amount": 0.0,
            "currency": currency,
            "title": title,
            "description": description,
            "status": GroupPaymentStatus.COLLECTING.value,
            "contributors": {},  # user_id -> {"name": "...", "amount": 0, "paid": False}
            "deadline": deadline,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None
        }
        
        # Initialize contributors
        for contributor in contributors:
            group_payment["contributors"][contributor["user_id"]] = {
                "name": contributor["name"],
                "expected_amount": float(contributor["amount"]),
                "paid_amount": 0.0,
                "paid": False,
                "transaction_id": None
            }
        
        self._group_payments[group_id] = group_payment
        
        # Notify all contributors
        for contributor in contributors:
            await self._send_notification(
                user_id=contributor["user_id"],
                title=f"Group Payment: {title}",
                message=f"{organizer_name} is collecting {currency} {target_amount} for {recipient_name}. Your share: {currency} {contributor['amount']}",
                action_url=f"/payments/groups/{group_id}"
            )
        
        return {
            "status": "SUCCESS",
            "group_id": group_id,
            "payment_url": f"/payments/groups/{group_id}"
        }
    
    async def contribute_to_group(
        self,
        group_id: str,
        contributor_id: str,
        amount: Decimal,
        transaction_id: str
    ) -> Dict:
        """Contribute to group payment"""
        if group_id not in self._group_payments:
            return {"status": "NOT_FOUND"}
        
        group = self._group_payments[group_id]
        
        if group["status"] != GroupPaymentStatus.COLLECTING.value:
            return {
                "status": "REJECTED",
                "reason": f"Group payment is {group['status']}"
            }
        
        if contributor_id not in group["contributors"]:
            return {
                "status": "REJECTED",
                "reason": "Not a contributor"
            }
        
        contributor = group["contributors"][contributor_id]
        
        if contributor["paid"]:
            return {
                "status": "REJECTED",
                "reason": "Already paid"
            }
        
        # Process payment
        payment_result = await self._process_payment(
            from_user_id=contributor_id,
            to_user_id=group["organizer_id"],  # Organizer holds funds
            amount=amount,
            currency=group["currency"],
            description=f"Contribution to: {group['title']}"
        )
        
        if payment_result["status"] != "SUCCESS":
            return payment_result
        
        # Update contributor
        contributor["paid_amount"] = float(amount)
        contributor["paid"] = True
        contributor["transaction_id"] = transaction_id
        contributor["paid_at"] = datetime.now(timezone.utc).isoformat()
        
        # Update collected amount
        group["collected_amount"] += float(amount)
        
        # Check if target reached
        if group["collected_amount"] >= group["target_amount"]:
            await self._complete_group_payment(group_id)
        
        return {
            "status": "SUCCESS",
            "group_id": group_id,
            "collected_amount": group["collected_amount"],
            "target_amount": group["target_amount"],
            "progress_percentage": (group["collected_amount"] / group["target_amount"]) * 100
        }
    
    async def create_split_bill(
        self,
        bill_id: str,
        payer_id: str,
        payer_name: str,
        total_amount: Decimal,
        currency: str,
        description: str,
        splits: List[Dict]  # [{"user_id": "...", "name": "...", "amount": 50}]
    ) -> Dict:
        """
        Create split bill
        
        One person paid, others owe their share
        
        Args:
            bill_id: Unique bill ID
            payer_id: Person who paid
            payer_name: Payer name
            total_amount: Total bill amount
            currency: Currency code
            description: Bill description
            splits: List of people who owe money
            
        Returns:
            Split bill result
        """
        # Validate splits sum to total
        splits_sum = sum(Decimal(str(split["amount"])) for split in splits)
        if splits_sum != total_amount:
            return {
                "status": "REJECTED",
                "reason": f"Splits sum ({splits_sum}) doesn't match total ({total_amount})"
            }
        
        split_bill = {
            "bill_id": bill_id,
            "payer_id": payer_id,
            "payer_name": payer_name,
            "total_amount": float(total_amount),
            "paid_amount": 0.0,
            "currency": currency,
            "description": description,
            "status": SplitBillStatus.PENDING.value,
            "splits": {},  # user_id -> {"name": "...", "amount": 50, "paid": False}
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Initialize splits
        for split in splits:
            split_bill["splits"][split["user_id"]] = {
                "name": split["name"],
                "owed_amount": float(split["amount"]),
                "paid": False,
                "transaction_id": None
            }
        
        self._split_bills[bill_id] = split_bill
        
        # Notify all who owe money
        for split in splits:
            await self._send_notification(
                user_id=split["user_id"],
                title="Split Bill",
                message=f"{payer_name} paid {currency} {total_amount} for {description}. You owe: {currency} {split['amount']}",
                action_url=f"/payments/splits/{bill_id}"
            )
        
        return {
            "status": "SUCCESS",
            "bill_id": bill_id,
            "payment_url": f"/payments/splits/{bill_id}"
        }
    
    async def pay_split(
        self,
        bill_id: str,
        payer_id: str,
        transaction_id: str
    ) -> Dict:
        """Pay your share of split bill"""
        if bill_id not in self._split_bills:
            return {"status": "NOT_FOUND"}
        
        bill = self._split_bills[bill_id]
        
        if payer_id not in bill["splits"]:
            return {
                "status": "REJECTED",
                "reason": "Not part of this split"
            }
        
        split = bill["splits"][payer_id]
        
        if split["paid"]:
            return {
                "status": "REJECTED",
                "reason": "Already paid"
            }
        
        # Process payment
        payment_result = await self._process_payment(
            from_user_id=payer_id,
            to_user_id=bill["payer_id"],
            amount=Decimal(str(split["owed_amount"])),
            currency=bill["currency"],
            description=f"Split payment for: {bill['description']}"
        )
        
        if payment_result["status"] != "SUCCESS":
            return payment_result
        
        # Update split
        split["paid"] = True
        split["transaction_id"] = transaction_id
        split["paid_at"] = datetime.now(timezone.utc).isoformat()
        
        # Update paid amount
        bill["paid_amount"] += split["owed_amount"]
        
        # Update status
        if bill["paid_amount"] >= bill["total_amount"]:
            bill["status"] = SplitBillStatus.FULLY_PAID.value
        else:
            bill["status"] = SplitBillStatus.PARTIALLY_PAID.value
        
        # Notify original payer
        await self._send_notification(
            user_id=bill["payer_id"],
            title="Split Payment Received",
            message=f"{split['name']} paid their share of {bill['currency']} {split['owed_amount']}",
            action_url=f"/transactions/{transaction_id}"
        )
        
        return {
            "status": "SUCCESS",
            "bill_id": bill_id,
            "paid_amount": bill["paid_amount"],
            "total_amount": bill["total_amount"],
            "remaining": bill["total_amount"] - bill["paid_amount"]
        }
    
    async def get_payment_request(self, request_id: str) -> Optional[Dict]:
        """Get payment request details"""
        return self._payment_requests.get(request_id)
    
    async def get_group_payment(self, group_id: str) -> Optional[Dict]:
        """Get group payment details"""
        return self._group_payments.get(group_id)
    
    async def get_split_bill(self, bill_id: str) -> Optional[Dict]:
        """Get split bill details"""
        return self._split_bills.get(bill_id)
    
    async def get_user_activity(
        self,
        user_id: str,
        limit: int = 50
    ) -> Dict:
        """Get user's social payment activity"""
        activity = []
        
        # Payment requests
        for request in self._payment_requests.values():
            if request["requester_id"] == user_id or request["payer_id"] == user_id:
                activity.append({
                    "type": "payment_request",
                    "data": request,
                    "timestamp": request["created_at"]
                })
        
        # Group payments
        for group in self._group_payments.values():
            if group["organizer_id"] == user_id or user_id in group["contributors"]:
                activity.append({
                    "type": "group_payment",
                    "data": group,
                    "timestamp": group["created_at"]
                })
        
        # Split bills
        for bill in self._split_bills.values():
            if bill["payer_id"] == user_id or user_id in bill["splits"]:
                activity.append({
                    "type": "split_bill",
                    "data": bill,
                    "timestamp": bill["created_at"]
                })
        
        # Sort by timestamp (newest first)
        activity.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return {
            "user_id": user_id,
            "activity": activity[:limit],
            "total_count": len(activity)
        }
    
    async def _complete_group_payment(self, group_id: str):
        """Complete group payment and transfer to recipient"""
        group = self._group_payments[group_id]
        
        # Transfer collected amount to recipient
        await self._process_payment(
            from_user_id=group["organizer_id"],
            to_user_id=group["recipient_id"],
            amount=Decimal(str(group["collected_amount"])),
            currency=group["currency"],
            description=f"Group payment: {group['title']}"
        )
        
        group["status"] = GroupPaymentStatus.COMPLETED.value
        group["completed_at"] = datetime.now(timezone.utc).isoformat()
        
        # Notify recipient
        await self._send_notification(
            user_id=group["recipient_id"],
            title="Group Payment Completed",
            message=f"You received {group['currency']} {group['collected_amount']} from {group['title']}",
            action_url=f"/payments/groups/{group_id}"
        )
    
    async def _process_payment(
        self,
        from_user_id: str,
        to_user_id: str,
        amount: Decimal,
        currency: str,
        description: str
    ) -> Dict:
        """Process payment via payment service"""
        if not self.client:
            # Simplified - return success
            return {"status": "SUCCESS"}
        
        try:
            response = await self.client.post(
                f"{self.payment_service_url}/payments",
                json={
                    "from_user_id": from_user_id,
                    "to_user_id": to_user_id,
                    "amount": float(amount),
                    "currency": currency,
                    "description": description
                },
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            
            response.raise_for_status()
            return {"status": "SUCCESS"}
            
        except:
            return {"status": "FAILED", "error": "Payment processing failed"}
    
    async def _send_notification(
        self,
        user_id: str,
        title: str,
        message: str,
        action_url: str
    ):
        """Send notification to user"""
        if not self.client:
            return
        
        try:
            await self.client.post(
                f"{self.notification_service_url}/notifications",
                json={
                    "user_id": user_id,
                    "title": title,
                    "message": message,
                    "action_url": action_url
                },
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
        except:
            pass  # Notification failure shouldn't block payment
