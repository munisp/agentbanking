"""
White-Label Multi-Tenant Platform Service

Enables partners to launch branded remittance platforms

Features:
- Multi-tenancy with data isolation
- Custom branding (logo, colors, domain)
- Revenue sharing models
- Partner portal
- API access
- Compliance management
"""

import asyncio
import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

import httpx


class TenantStatus(Enum):
    """Tenant status"""
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    TERMINATED = "TERMINATED"


class RevenueModel(Enum):
    """Revenue sharing model"""
    PERCENTAGE = "PERCENTAGE"  # % of transaction fees
    FIXED_PER_TXN = "FIXED_PER_TXN"  # Fixed amount per transaction
    SUBSCRIPTION = "SUBSCRIPTION"  # Monthly subscription
    HYBRID = "HYBRID"  # Combination


class WhiteLabelService:
    """
    White-Label Multi-Tenant Platform Service
    
    Enables partners to launch branded remittance platforms
    
    Features:
    - Tenant management
    - Custom branding
    - Revenue sharing
    - API key management
    - Usage analytics
    - Compliance configuration
    """
    
    def __init__(
        self,
        database_url: str,
        storage_url: str,
        platform_domain: str
    ):
        """
        Initialize white-label service
        
        Args:
            database_url: Database connection URL
            storage_url: Object storage URL (for logos, etc.)
            platform_domain: Platform base domain
        """
        self.database_url = database_url
        self.storage_url = storage_url
        self.platform_domain = platform_domain
        
        self.client: Optional[httpx.AsyncClient] = None
        
        # In-memory storage (would use database in production)
        self._tenants: Dict[str, Dict] = {}
        self._api_keys: Dict[str, str] = {}  # api_key -> tenant_id
        self._transactions: Dict[str, List[Dict]] = {}  # tenant_id -> transactions
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=30)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def create_tenant(
        self,
        tenant_id: str,
        company_name: str,
        contact_email: str,
        contact_name: str,
        subdomain: str,
        revenue_model: RevenueModel,
        revenue_share_percentage: Optional[Decimal] = None,
        fixed_fee_per_transaction: Optional[Decimal] = None,
        monthly_subscription_fee: Optional[Decimal] = None
    ) -> Dict:
        """
        Create new tenant
        
        Args:
            tenant_id: Unique tenant ID
            company_name: Company name
            contact_email: Contact email
            contact_name: Contact person name
            subdomain: Subdomain (e.g., "acme" -> acme.platform.com)
            revenue_model: Revenue sharing model
            revenue_share_percentage: Revenue share % (if applicable)
            fixed_fee_per_transaction: Fixed fee per txn (if applicable)
            monthly_subscription_fee: Monthly subscription (if applicable)
            
        Returns:
            Tenant creation result
        """
        # Validate subdomain
        if not self._validate_subdomain(subdomain):
            return {
                "status": "REJECTED",
                "reason": "Invalid subdomain format"
            }
        
        # Check subdomain availability
        if self._subdomain_exists(subdomain):
            return {
                "status": "REJECTED",
                "reason": "Subdomain already taken"
            }
        
        # Generate API keys
        api_key = self._generate_api_key()
        api_secret = self._generate_api_secret()
        
        # Create tenant
        tenant = {
            "tenant_id": tenant_id,
            "company_name": company_name,
            "contact_email": contact_email,
            "contact_name": contact_name,
            "subdomain": subdomain,
            "custom_domain": None,  # Can be set later
            "status": TenantStatus.PENDING.value,
            "revenue_model": revenue_model.value,
            "revenue_share_percentage": float(revenue_share_percentage) if revenue_share_percentage else None,
            "fixed_fee_per_transaction": float(fixed_fee_per_transaction) if fixed_fee_per_transaction else None,
            "monthly_subscription_fee": float(monthly_subscription_fee) if monthly_subscription_fee else None,
            "api_key": api_key,
            "api_secret_hash": hashlib.sha256(api_secret.encode()).hexdigest(),
            "branding": {
                "logo_url": None,
                "primary_color": "#000000",
                "secondary_color": "#FFFFFF",
                "company_name": company_name
            },
            "enabled_gateways": [],  # Will be configured
            "compliance": {
                "kyc_required": True,
                "kyc_level": "BASIC",
                "aml_enabled": True,
                "transaction_limit_daily": 10000,
                "transaction_limit_monthly": 100000
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
            "activated_at": None
        }
        
        self._tenants[tenant_id] = tenant
        self._api_keys[api_key] = tenant_id
        self._transactions[tenant_id] = []
        
        return {
            "status": "SUCCESS",
            "tenant_id": tenant_id,
            "api_key": api_key,
            "api_secret": api_secret,  # Only returned once
            "subdomain": f"{subdomain}.{self.platform_domain}",
            "portal_url": f"https://{subdomain}.{self.platform_domain}/portal",
            "message": "Tenant created. Please complete setup in portal."
        }
    
    async def activate_tenant(
        self,
        tenant_id: str
    ) -> Dict:
        """Activate tenant after setup completion"""
        if tenant_id not in self._tenants:
            return {"status": "NOT_FOUND"}
        
        tenant = self._tenants[tenant_id]
        
        # Validate tenant is ready
        if not tenant["branding"]["logo_url"]:
            return {
                "status": "REJECTED",
                "reason": "Logo not uploaded"
            }
        
        if not tenant["enabled_gateways"]:
            return {
                "status": "REJECTED",
                "reason": "No payment gateways configured"
            }
        
        tenant["status"] = TenantStatus.ACTIVE.value
        tenant["activated_at"] = datetime.now(timezone.utc).isoformat()
        
        return {
            "status": "SUCCESS",
            "tenant_id": tenant_id,
            "message": "Tenant activated",
            "platform_url": f"https://{tenant['subdomain']}.{self.platform_domain}"
        }
    
    async def update_branding(
        self,
        tenant_id: str,
        logo_url: Optional[str] = None,
        primary_color: Optional[str] = None,
        secondary_color: Optional[str] = None,
        company_name: Optional[str] = None
    ) -> Dict:
        """Update tenant branding"""
        if tenant_id not in self._tenants:
            return {"status": "NOT_FOUND"}
        
        tenant = self._tenants[tenant_id]
        branding = tenant["branding"]
        
        if logo_url:
            branding["logo_url"] = logo_url
        if primary_color:
            branding["primary_color"] = primary_color
        if secondary_color:
            branding["secondary_color"] = secondary_color
        if company_name:
            branding["company_name"] = company_name
        
        return {
            "status": "SUCCESS",
            "branding": branding
        }
    
    async def configure_gateways(
        self,
        tenant_id: str,
        gateways: List[str]
    ) -> Dict:
        """Configure enabled payment gateways"""
        if tenant_id not in self._tenants:
            return {"status": "NOT_FOUND"}
        
        tenant = self._tenants[tenant_id]
        tenant["enabled_gateways"] = gateways
        
        return {
            "status": "SUCCESS",
            "enabled_gateways": gateways
        }
    
    async def set_custom_domain(
        self,
        tenant_id: str,
        custom_domain: str
    ) -> Dict:
        """Set custom domain for tenant"""
        if tenant_id not in self._tenants:
            return {"status": "NOT_FOUND"}
        
        tenant = self._tenants[tenant_id]
        tenant["custom_domain"] = custom_domain
        
        return {
            "status": "SUCCESS",
            "custom_domain": custom_domain,
            "message": "Please configure DNS CNAME record",
            "cname_target": f"{tenant['subdomain']}.{self.platform_domain}"
        }
    
    async def record_transaction(
        self,
        tenant_id: str,
        transaction_id: str,
        amount: Decimal,
        currency: str,
        gateway: str,
        fee: Decimal
    ) -> Dict:
        """Record transaction for revenue sharing"""
        if tenant_id not in self._tenants:
            return {"status": "NOT_FOUND"}
        
        tenant = self._tenants[tenant_id]
        
        # Calculate revenue share
        revenue_share = self._calculate_revenue_share(
            tenant=tenant,
            amount=amount,
            fee=fee
        )
        
        transaction = {
            "transaction_id": transaction_id,
            "amount": float(amount),
            "currency": currency,
            "gateway": gateway,
            "fee": float(fee),
            "platform_revenue": float(revenue_share["platform_revenue"]),
            "partner_revenue": float(revenue_share["partner_revenue"]),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self._transactions[tenant_id].append(transaction)
        
        return {
            "status": "SUCCESS",
            "revenue_share": revenue_share
        }
    
    async def get_tenant_analytics(
        self,
        tenant_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict:
        """Get tenant analytics"""
        if tenant_id not in self._tenants:
            return {"status": "NOT_FOUND"}
        
        transactions = self._transactions.get(tenant_id, [])
        
        # Filter by date if provided
        if start_date or end_date:
            filtered = []
            for txn in transactions:
                txn_date = txn["timestamp"]
                if start_date and txn_date < start_date:
                    continue
                if end_date and txn_date > end_date:
                    continue
                filtered.append(txn)
            transactions = filtered
        
        # Calculate metrics
        total_transactions = len(transactions)
        total_volume = sum(txn["amount"] for txn in transactions)
        total_fees = sum(txn["fee"] for txn in transactions)
        partner_revenue = sum(txn["partner_revenue"] for txn in transactions)
        platform_revenue = sum(txn["platform_revenue"] for txn in transactions)
        
        # Gateway breakdown
        gateway_stats = {}
        for txn in transactions:
            gateway = txn["gateway"]
            if gateway not in gateway_stats:
                gateway_stats[gateway] = {
                    "count": 0,
                    "volume": 0
                }
            gateway_stats[gateway]["count"] += 1
            gateway_stats[gateway]["volume"] += txn["amount"]
        
        return {
            "tenant_id": tenant_id,
            "period": {
                "start": start_date,
                "end": end_date
            },
            "metrics": {
                "total_transactions": total_transactions,
                "total_volume": total_volume,
                "total_fees": total_fees,
                "partner_revenue": partner_revenue,
                "platform_revenue": platform_revenue
            },
            "gateway_breakdown": gateway_stats
        }
    
    async def get_tenant_by_api_key(
        self,
        api_key: str
    ) -> Optional[Dict]:
        """Get tenant by API key"""
        tenant_id = self._api_keys.get(api_key)
        if not tenant_id:
            return None
        return self._tenants.get(tenant_id)
    
    async def suspend_tenant(
        self,
        tenant_id: str,
        reason: str
    ) -> Dict:
        """Suspend tenant"""
        if tenant_id not in self._tenants:
            return {"status": "NOT_FOUND"}
        
        tenant = self._tenants[tenant_id]
        tenant["status"] = TenantStatus.SUSPENDED.value
        tenant["suspension_reason"] = reason
        tenant["suspended_at"] = datetime.now(timezone.utc).isoformat()
        
        return {
            "status": "SUCCESS",
            "message": "Tenant suspended"
        }
    
    async def reactivate_tenant(
        self,
        tenant_id: str
    ) -> Dict:
        """Reactivate suspended tenant"""
        if tenant_id not in self._tenants:
            return {"status": "NOT_FOUND"}
        
        tenant = self._tenants[tenant_id]
        
        if tenant["status"] != TenantStatus.SUSPENDED.value:
            return {
                "status": "REJECTED",
                "reason": "Tenant is not suspended"
            }
        
        tenant["status"] = TenantStatus.ACTIVE.value
        tenant["reactivated_at"] = datetime.now(timezone.utc).isoformat()
        
        return {
            "status": "SUCCESS",
            "message": "Tenant reactivated"
        }
    
    def _validate_subdomain(self, subdomain: str) -> bool:
        """Validate subdomain format"""
        import re
        pattern = r'^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$'
        return bool(re.match(pattern, subdomain))
    
    def _subdomain_exists(self, subdomain: str) -> bool:
        """Check if subdomain exists"""
        for tenant in self._tenants.values():
            if tenant["subdomain"] == subdomain:
                return True
        return False
    
    def _generate_api_key(self) -> str:
        """Generate API key"""
        return f"wl_{secrets.token_urlsafe(32)}"
    
    def _generate_api_secret(self) -> str:
        """Generate API secret"""
        return secrets.token_urlsafe(48)
    
    def _calculate_revenue_share(
        self,
        tenant: Dict,
        amount: Decimal,
        fee: Decimal
    ) -> Dict:
        """Calculate revenue share"""
        model = tenant["revenue_model"]
        
        if model == RevenueModel.PERCENTAGE.value:
            # Split fee by percentage
            partner_percentage = Decimal(str(tenant["revenue_share_percentage"])) / 100
            partner_revenue = fee * partner_percentage
            platform_revenue = fee - partner_revenue
            
        elif model == RevenueModel.FIXED_PER_TXN.value:
            # Fixed amount per transaction
            partner_revenue = Decimal(str(tenant["fixed_fee_per_transaction"]))
            platform_revenue = fee - partner_revenue
            
        elif model == RevenueModel.SUBSCRIPTION.value:
            # All fees go to platform (subscription paid separately)
            partner_revenue = Decimal("0")
            platform_revenue = fee
            
        else:  # HYBRID
            # Combination of percentage and fixed
            fixed = Decimal(str(tenant.get("fixed_fee_per_transaction", 0)))
            percentage = Decimal(str(tenant.get("revenue_share_percentage", 0))) / 100
            partner_revenue = fixed + (fee * percentage)
            platform_revenue = fee - partner_revenue
        
        return {
            "partner_revenue": partner_revenue,
            "platform_revenue": platform_revenue,
            "revenue_model": model
        }
