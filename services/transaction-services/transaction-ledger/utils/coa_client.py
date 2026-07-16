"""
Chart of Accounts Service Client

This module provides a client for interacting with the Chart of Accounts service
to create accounts and journal entries for double-entry bookkeeping.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)


class CoAClient:
    """Client for Chart of Accounts service"""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or os.getenv(
            "COA_SERVICE_URL", "http://chart-of-accounts-service:8080"
        )
        self.timeout = 30.0

    def _get_headers(
        self, tenant_id: str, user_id: str, user_role: str
    ) -> Dict[str, str]:
        """Build headers for CoA service requests"""
        return {
            "Content-Type": "application/json",
            "X-Tenant-ID": tenant_id,
            "X-User-ID": user_id,
            "X-User-Role": user_role,
        }

    async def create_account(
        self,
        tenant_id: str,
        user_id: str,
        user_role: str,
        code: str,
        name: str,
        account_type: str,
        currency: str = "NGN",
        parent_id: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new account in the Chart of Accounts

        Args:
            tenant_id: Tenant identifier
            user_id: User making the request
            user_role: User role (e.g., bank_admin, finance_admin)
            code: Account code (e.g., "1400")
            name: Account name (e.g., "Loans Receivable")
            account_type: Account type (asset, liability, equity, revenue, expense)
            currency: Currency code (default: NGN)
            parent_id: Parent account ID for hierarchical accounts
            description: Optional account description

        Returns:
            Created account data
        """
        account_data = {
            "code": code,
            "name": name,
            "type": account_type,
            "currency": currency,
            "is_active": True,
            "is_system_account": True,
        }

        if parent_id:
            account_data["parent_id"] = parent_id
        if description:
            account_data["description"] = description

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/accounts",
                    json=account_data,
                    headers=self._get_headers(tenant_id, user_id, user_role),
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Failed to create CoA account: {e}")
                raise

    async def create_journal_entry(
        self,
        tenant_id: str,
        user_id: str,
        user_role: str,
        description: str,
        lines: List[Dict[str, Any]],
        reference: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new journal entry"""
        entry_data = {
            "date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "description": description,
            "posted_by": user_id,
            "lines": lines,
        }

        if reference:
            entry_data["reference"] = reference
        if metadata:
            entry_data["metadata"] = metadata

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/journal-entries",
                    json=entry_data,
                    headers=self._get_headers(tenant_id, user_id, user_role),
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                # Capture HTTP error details
                error_detail = {
                    "status_code": e.response.status_code,
                    "response_body": e.response.text,
                    "request_data": entry_data,
                }
                logger.error(f"Failed to create journal entry: {error_detail}")
                raise Exception(
                    f"CoA service error [{e.response.status_code}]: {e.response.text}"
                )
            except httpx.RequestError as e:
                # Capture connection/network errors
                logger.error(f"Failed to connect to CoA service: {e}")
                logger.error(f"CoA service URL: {self.base_url}")
                raise Exception(f"CoA service connection failed: {e}")
            except Exception as e:
                logger.error(f"Unexpected error creating journal entry: {e}")
                raise

    async def get_accounts(
        self,
        tenant_id: str,
        user_id: str,
        user_role: str,
    ) -> List[Dict[str, Any]]:
        """Get all accounts for a tenant"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/accounts",
                    headers=self._get_headers(tenant_id, user_id, user_role),
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Failed to get accounts: {e}")
                raise

    # ===== Payment Processing Specific Methods =====

    async def record_payment(
        self,
        tenant_id: str,
        user_id: str,
        user_role: str,
        payment_id: str,
        amount: int,  # Amount in kobo (smallest currency unit)
        from_account: str,
        to_account: str,
        description: str,
    ) -> Dict[str, Any]:
        """
        Record a payment transaction

        Debit: Receiver account
        Credit: Sender account
        """
        lines = [
            {
                "account_id": to_account,
                "description": f"Payment received - {description}",
                "debit_amount": amount,
                "credit_amount": 0,
            },
            {
                "account_id": from_account,
                "description": f"Payment sent - {description}",
                "debit_amount": 0,
                "credit_amount": amount,
            },
        ]

        return await self.create_journal_entry(
            tenant_id=tenant_id,
            user_id=user_id,
            user_role=user_role,
            description=f"Payment: {description}",
            lines=lines,
            reference=payment_id,
            metadata={
                "payment_id": payment_id,
                "source": "payment-processing-service",
                "event_type": "payment",
            },
        )

    async def record_escrow_deposit(
        self,
        tenant_id: str,
        user_id: str,
        user_role: str,
        escrow_id: str,
        amount: int,
        customer_account: str,
    ) -> Dict[str, Any]:
        """
        Record escrow deposit

        Debit: Escrow account (2300)
        Credit: Customer account
        """
        lines = [
            {
                "account_id": "2300",  # Escrow Liabilities
                "description": f"Escrow deposit for {escrow_id}",
                "debit_amount": amount,
                "credit_amount": 0,
            },
            {
                "account_id": customer_account,
                "description": "Escrow deposit from customer",
                "debit_amount": 0,
                "credit_amount": amount,
            },
        ]

        return await self.create_journal_entry(
            tenant_id=tenant_id,
            user_id=user_id,
            user_role=user_role,
            description=f"Escrow deposit: {escrow_id}",
            lines=lines,
            reference=escrow_id,
            metadata={
                "escrow_id": escrow_id,
                "source": "escrow-service",
                "event_type": "deposit",
            },
        )

    async def record_escrow_release(
        self,
        tenant_id: str,
        user_id: str,
        user_role: str,
        escrow_id: str,
        amount: int,
        beneficiary_account: str,
    ) -> Dict[str, Any]:
        """
        Record escrow release

        Debit: Beneficiary account
        Credit: Escrow account (2300)
        """
        lines = [
            {
                "account_id": beneficiary_account,
                "description": "Escrow release to beneficiary",
                "debit_amount": amount,
                "credit_amount": 0,
            },
            {
                "account_id": "2300",  # Escrow Liabilities
                "description": f"Escrow release for {escrow_id}",
                "debit_amount": 0,
                "credit_amount": amount,
            },
        ]

        return await self.create_journal_entry(
            tenant_id=tenant_id,
            user_id=user_id,
            user_role=user_role,
            description=f"Escrow release: {escrow_id}",
            lines=lines,
            reference=escrow_id,
            metadata={
                "escrow_id": escrow_id,
                "source": "escrow-service",
                "event_type": "release",
            },
        )

    async def record_card_transaction(
        self,
        tenant_id: str,
        user_id: str,
        user_role: str,
        transaction_id: str,
        amount: int,
        card_account: str,
        merchant_account: str,
        transaction_type: str,  # "purchase", "withdrawal", "refund"
    ) -> Dict[str, Any]:
        """
        Record card transaction

        For purchases:
          Debit: Merchant account
          Credit: Card account
        """
        if transaction_type == "purchase":
            lines = [
                {
                    "account_id": merchant_account,
                    "description": f"Card purchase - {transaction_id}",
                    "debit_amount": amount,
                    "credit_amount": 0,
                },
                {
                    "account_id": card_account,
                    "description": "Card payment",
                    "debit_amount": 0,
                    "credit_amount": amount,
                },
            ]
        elif transaction_type == "refund":
            lines = [
                {
                    "account_id": card_account,
                    "description": "Card refund",
                    "debit_amount": amount,
                    "credit_amount": 0,
                },
                {
                    "account_id": merchant_account,
                    "description": f"Refund to customer - {transaction_id}",
                    "debit_amount": 0,
                    "credit_amount": amount,
                },
            ]
        else:
            raise ValueError(f"Unsupported transaction type: {transaction_type}")

        return await self.create_journal_entry(
            tenant_id=tenant_id,
            user_id=user_id,
            user_role=user_role,
            description=f"Card {transaction_type}: {transaction_id}",
            lines=lines,
            reference=transaction_id,
            metadata={
                "transaction_id": transaction_id,
                "source": "card-service",
                "event_type": transaction_type,
            },
        )

    async def record_savings_deposit(
        self,
        tenant_id: str,
        user_id: str,
        user_role: str,
        account_id: str,
        amount: int,
        customer_account: str,
    ) -> Dict[str, Any]:
        """
        Record savings deposit

        Debit: Savings account (2200)
        Credit: Customer source account
        """
        lines = [
            {
                "account_id": "2200",  # Savings Deposits
                "description": f"Savings deposit to account {account_id}",
                "debit_amount": amount,
                "credit_amount": 0,
            },
            {
                "account_id": customer_account,
                "description": "Transfer to savings",
                "debit_amount": 0,
                "credit_amount": amount,
            },
        ]

        return await self.create_journal_entry(
            tenant_id=tenant_id,
            user_id=user_id,
            user_role=user_role,
            description=f"Savings deposit: {account_id}",
            lines=lines,
            reference=account_id,
            metadata={
                "account_id": account_id,
                "source": "savings-service",
                "event_type": "deposit",
            },
        )

    async def record_savings_withdrawal(
        self,
        tenant_id: str,
        user_id: str,
        user_role: str,
        account_id: str,
        amount: int,
        customer_account: str,
    ) -> Dict[str, Any]:
        """
        Record savings withdrawal

        Debit: Customer destination account
        Credit: Savings account (2200)
        """
        lines = [
            {
                "account_id": customer_account,
                "description": "Savings withdrawal",
                "debit_amount": amount,
                "credit_amount": 0,
            },
            {
                "account_id": "2200",  # Savings Deposits
                "description": f"Withdrawal from account {account_id}",
                "debit_amount": 0,
                "credit_amount": amount,
            },
        ]

        return await self.create_journal_entry(
            tenant_id=tenant_id,
            user_id=user_id,
            user_role=user_role,
            description=f"Savings withdrawal: {account_id}",
            lines=lines,
            reference=account_id,
            metadata={
                "account_id": account_id,
                "source": "savings-service",
                "event_type": "withdrawal",
            },
        )
