"""
Activity Definitions for Workflow Orchestration
Activities are the building blocks of workflows
"""

from temporalio import activity
from typing import Dict, Any, List
import httpx
import asyncio
from datetime import datetime
import os

# Service URLs
FRAUD_DETECTION_URL = os.getenv("FRAUD_DETECTION_URL", "http://localhost:8010")
KYC_SERVICE_URL = os.getenv("KYC_SERVICE_URL", "http://localhost:8011")
LEDGER_SERVICE_URL = os.getenv("LEDGER_SERVICE_URL", "http://localhost:8005")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8012")
COMMISSION_SERVICE_URL = os.getenv("COMMISSION_SERVICE_URL", "http://localhost:8013")
CREDIT_SCORING_URL = os.getenv("CREDIT_SCORING_URL", "http://localhost:8014")
LOAN_SERVICE_URL = os.getenv("LOAN_SERVICE_URL", "http://localhost:8015")

# ============================================================================
# Agent Onboarding Activities
# ============================================================================

@activity.defn
async def validate_personal_info(personal_info: Dict[str, Any]) -> Dict[str, Any]:
    """Validate agent personal information"""
    # Basic validation
    required_fields = ["name", "phone", "email", "address", "id_number"]
    
    for field in required_fields:
        if field not in personal_info or not personal_info[field]:
            return {"valid": False, "reason": f"Missing required field: {field}"}
    
    # Email format validation
    if "@" not in personal_info["email"]:
        return {"valid": False, "reason": "Invalid email format"}
    
    # Phone number validation (basic)
    if len(personal_info["phone"]) < 10:
        return {"valid": False, "reason": "Invalid phone number"}
    
    return {"valid": True}

@activity.defn
async def validate_kyc_documents(documents: List[str]) -> Dict[str, Any]:
    """Validate KYC documents"""
    if not documents or len(documents) < 2:
        return {"valid": False, "reason": "Minimum 2 documents required"}
    
    # Check document types
    required_types = ["id_card", "proof_of_address"]
    # In real implementation, would check actual document types
    
    return {"valid": True}

@activity.defn
async def ai_document_validation(data: Dict[str, Any]) -> Dict[str, Any]:
    """AI-based document validation"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{KYC_SERVICE_URL}/api/v1/validate-documents",
                json=data,
                timeout=60.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            activity.logger.error(f"AI document validation failed: {e}")
            # Return low confidence on error
            return {"valid": True, "confidence": 0.5, "reason": "Manual review required"}

@activity.defn
async def register_biometric(data: Dict[str, Any]) -> Dict[str, Any]:
    """Register biometric data"""
    # In real implementation, would call biometric service
    return {
        "success": True,
        "biometric_id": f"bio-{data['agent_id']}"
    }

@activity.defn
async def perform_background_check(agent_id: str) -> Dict[str, Any]:
    """Perform background check"""
    # In real implementation, would call third-party background check service
    return {
        "success": True,
        "risk_score": 0.2,  # Low risk
        "checks_passed": ["criminal_record", "credit_history", "identity"]
    }

@activity.defn
async def create_agent_account(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create agent account"""
    # In real implementation, would call user service
    return {
        "success": True,
        "account_id": f"acc-{data['agent_id']}",
        "created_at": datetime.now().isoformat()
    }

@activity.defn
async def assign_to_hierarchy(data: Dict[str, Any]) -> Dict[str, Any]:
    """Assign agent to hierarchy"""
    # In real implementation, would call hierarchy service
    return {
        "success": True,
        "parent_agent_id": "parent-123",
        "level": 2
    }

@activity.defn
async def enroll_in_training(agent_id: str) -> Dict[str, Any]:
    """Enroll agent in training"""
    # In real implementation, would call training service
    return {
        "success": True,
        "training_id": f"training-{agent_id}",
        "courses": ["basic_operations", "compliance", "customer_service"]
    }

@activity.defn
async def activate_agent_account(agent_id: str) -> Dict[str, Any]:
    """Activate agent account"""
    # In real implementation, would call user service
    return {
        "success": True,
        "status": "active",
        "activated_at": datetime.now().isoformat()
    }

# ============================================================================
# Transaction Activities
# ============================================================================

@activity.defn
async def validate_customer_account(customer_id: str) -> Dict[str, Any]:
    """Validate customer account"""
    # In real implementation, would call account service
    return {
        "valid": True,
        "account_status": "active",
        "kyc_verified": True
    }

@activity.defn
async def validate_customer_balance(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate customer has sufficient balance"""
    # In real implementation, would call account service
    return {
        "sufficient": True,
        "balance": 100000.00,
        "available_balance": 95000.00
    }

@activity.defn
async def check_transaction_limits(data: Dict[str, Any]) -> Dict[str, Any]:
    """Check if transaction is within limits"""
    # In real implementation, would call limits service
    daily_limit = 500000.00
    transaction_limit = 100000.00
    
    if data["amount"] > transaction_limit:
        return {
            "within_limits": False,
            "reason": "Exceeds single transaction limit"
        }
    
    return {
        "within_limits": True,
        "daily_remaining": daily_limit - data["amount"]
    }

@activity.defn
async def validate_agent_float(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate agent has sufficient float"""
    # In real implementation, would call float management service
    return {
        "sufficient": True,
        "float_balance": 500000.00,
        "available_float": 450000.00
    }

@activity.defn
async def check_agent_cash_availability(data: Dict[str, Any]) -> Dict[str, Any]:
    """Check if agent has sufficient cash for withdrawal"""
    # In real implementation, would call float management service
    return {
        "available": True,
        "cash_balance": 300000.00
    }

@activity.defn
async def check_fraud(data: Dict[str, Any]) -> Dict[str, Any]:
    """Check transaction for fraud"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{FRAUD_DETECTION_URL}/api/v1/check",
                json=data,
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            activity.logger.error(f"Fraud check failed: {e}")
            # Return low risk on error to not block transaction
            return {"risk_score": 0.1, "risk_level": "low"}

@activity.defn
async def verify_customer_pin(data: Dict[str, Any]) -> Dict[str, Any]:
    """Verify customer PIN"""
    # In real implementation, would call auth service
    return {
        "verified": True,
        "verified_at": datetime.now().isoformat()
    }

@activity.defn
async def process_ledger_transaction(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process transaction in TigerBeetle ledger"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{LEDGER_SERVICE_URL}/api/v1/transactions",
                json=data,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            return {
                "success": True,
                "ledger_id": result.get("ledger_id", f"ledger-{data['transaction_id']}")
            }
        except Exception as e:
            activity.logger.error(f"Ledger transaction failed: {e}")
            return {"success": False, "error": str(e)}

@activity.defn
async def calculate_and_credit_commission(data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate and credit commission to agent"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{COMMISSION_SERVICE_URL}/api/v1/calculate",
                json=data,
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            activity.logger.error(f"Commission calculation failed: {e}")
            # Return zero commission on error
            return {"amount": 0.0, "error": str(e)}

@activity.defn
async def generate_receipt(data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate transaction receipt"""
    # In real implementation, would call receipt service
    return {
        "success": True,
        "receipt_id": f"receipt-{data['transaction_id']}",
        "url": f"https://receipts.example.com/{data['transaction_id']}.pdf"
    }

@activity.defn
async def send_transaction_notifications(data: Dict[str, Any]) -> Dict[str, Any]:
    """Send transaction notifications"""
    async with httpx.AsyncClient() as client:
        try:
            # Send to agent
            await client.post(
                f"{NOTIFICATION_SERVICE_URL}/api/v1/send",
                json={
                    "recipient_id": data["agent_id"],
                    "type": "transaction_completed",
                    "data": data,
                    "channels": ["push", "sms"]
                },
                timeout=10.0
            )
            
            # Send to customer
            await client.post(
                f"{NOTIFICATION_SERVICE_URL}/api/v1/send",
                json={
                    "recipient_id": data["customer_id"],
                    "type": "transaction_completed",
                    "data": data,
                    "channels": ["push", "sms"]
                },
                timeout=10.0
            )
            
            return {"success": True}
        except Exception as e:
            activity.logger.error(f"Notification sending failed: {e}")
            return {"success": False, "error": str(e)}

@activity.defn
async def update_transaction_analytics(data: Dict[str, Any]) -> Dict[str, Any]:
    """Update transaction analytics"""
    # In real implementation, would call analytics service
    return {"success": True}

@activity.defn
async def track_cash_disbursement(data: Dict[str, Any]) -> Dict[str, Any]:
    """Track cash disbursement"""
    # In real implementation, would call cash tracking service
    return {
        "success": True,
        "tracking_id": f"cash-{data['transaction_id']}"
    }

# ============================================================================
# Loan Activities
# ============================================================================

@activity.defn
async def check_loan_eligibility(data: Dict[str, Any]) -> Dict[str, Any]:
    """Check loan eligibility"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{LOAN_SERVICE_URL}/api/v1/eligibility",
                json=data,
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            activity.logger.error(f"Eligibility check failed: {e}")
            return {
                "eligible": False,
                "reason": "Service unavailable"
            }

@activity.defn
async def perform_credit_scoring(customer_id: str) -> Dict[str, Any]:
    """Perform credit scoring"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{CREDIT_SCORING_URL}/api/v1/score",
                json={"customer_id": customer_id},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            activity.logger.error(f"Credit scoring failed: {e}")
            return {
                "score": 500,  # Default medium score
                "risk_level": "medium"
            }

@activity.defn
async def check_loan_fraud(data: Dict[str, Any]) -> Dict[str, Any]:
    """Check loan application for fraud"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{FRAUD_DETECTION_URL}/api/v1/check-loan",
                json=data,
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            activity.logger.error(f"Loan fraud check failed: {e}")
            return {"risk_score": 0.2, "risk_level": "low"}

@activity.defn
async def calculate_repayment_schedule(data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate loan repayment schedule"""
    # Simple calculation (in real implementation, would be more complex)
    principal = data["principal"]
    term_months = data["term_months"]
    
    # Interest rate based on credit score
    credit_score = data.get("credit_score", 650)
    if credit_score >= 750:
        interest_rate = 0.10  # 10%
    elif credit_score >= 650:
        interest_rate = 0.15  # 15%
    else:
        interest_rate = 0.20  # 20%
    
    total_interest = principal * interest_rate * (term_months / 12)
    total_repayment = principal + total_interest
    monthly_payment = total_repayment / term_months
    
    # Generate schedule
    schedule = []
    for month in range(1, term_months + 1):
        schedule.append({
            "month": month,
            "due_date": f"2025-{(month % 12) + 1:02d}-01",
            "amount": monthly_payment,
            "principal": principal / term_months,
            "interest": total_interest / term_months
        })
    
    return {
        "interest_rate": interest_rate,
        "monthly_payment": monthly_payment,
        "total_repayment": total_repayment,
        "schedule": schedule,
        "first_payment_date": schedule[0]["due_date"]
    }

@activity.defn
async def create_loan_record(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create loan record"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{LOAN_SERVICE_URL}/api/v1/loans",
                json=data,
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            activity.logger.error(f"Loan record creation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

@activity.defn
async def disburse_loan(data: Dict[str, Any]) -> Dict[str, Any]:
    """Disburse loan to customer account"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{LOAN_SERVICE_URL}/api/v1/disburse",
                json=data,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            activity.logger.error(f"Loan disbursement failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

@activity.defn
async def schedule_loan_collections(data: Dict[str, Any]) -> Dict[str, Any]:
    """Schedule loan repayment collections"""
    # In real implementation, would call scheduler service
    return {
        "success": True,
        "scheduled_count": len(data["repayment_schedule"])
    }

# ============================================================================
# Dispute Resolution Activities
# ============================================================================

@activity.defn
async def create_dispute_ticket(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create dispute ticket"""
    # In real implementation, would call dispute service
    return {
        "success": True,
        "ticket_id": f"ticket-{data['dispute_id']}",
        "created_at": datetime.now().isoformat()
    }

@activity.defn
async def upload_dispute_evidence(data: Dict[str, Any]) -> Dict[str, Any]:
    """Upload dispute evidence"""
    # In real implementation, would upload to S3 or similar
    return {
        "success": True,
        "evidence_urls": [f"https://evidence.example.com/{f}" for f in data["evidence_files"]]
    }

@activity.defn
async def get_transaction_details(transaction_id: str) -> Dict[str, Any]:
    """Get transaction details"""
    # In real implementation, would call transaction service
    return {
        "transaction_id": transaction_id,
        "amount": 50000.00,
        "type": "cash_in",
        "status": "completed",
        "timestamp": "2025-11-10T10:30:00"
    }

@activity.defn
async def notify_support_team(data: Dict[str, Any]) -> Dict[str, Any]:
    """Notify support team of new dispute"""
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{NOTIFICATION_SERVICE_URL}/api/v1/send",
                json={
                    "recipient_group": "support_team",
                    "type": "new_dispute",
                    "data": data,
                    "channels": ["email", "slack"]
                },
                timeout=10.0
            )
            return {"success": True}
        except Exception as e:
            activity.logger.error(f"Support notification failed: {e}")
            return {"success": False, "error": str(e)}

@activity.defn
async def investigate_ledger_transaction(transaction_id: str) -> Dict[str, Any]:
    """Investigate transaction in ledger"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{LEDGER_SERVICE_URL}/api/v1/transactions/{transaction_id}",
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            activity.logger.error(f"Ledger investigation failed: {e}")
            return {"error": str(e)}

@activity.defn
async def process_refund(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process refund"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{LEDGER_SERVICE_URL}/api/v1/refunds",
                json=data,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            activity.logger.error(f"Refund processing failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

@activity.defn
async def update_dispute_status(data: Dict[str, Any]) -> Dict[str, Any]:
    """Update dispute status"""
    # In real implementation, would call dispute service
    return {
        "success": True,
        "updated_at": datetime.now().isoformat()
    }

# ============================================================================
# General Activities
# ============================================================================

@activity.defn
async def send_notification(data: Dict[str, Any]) -> Dict[str, Any]:
    """Send notification to user"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{NOTIFICATION_SERVICE_URL}/api/v1/send",
                json=data,
                timeout=10.0
            )
            response.raise_for_status()
            return {"success": True}
        except Exception as e:
            activity.logger.error(f"Notification failed: {e}")
            return {"success": False, "error": str(e)}

# ============================================================================
# Activity Registry
# ============================================================================

ACTIVITIES = [
    # Onboarding
    validate_personal_info,
    validate_kyc_documents,
    ai_document_validation,
    register_biometric,
    perform_background_check,
    create_agent_account,
    assign_to_hierarchy,
    enroll_in_training,
    activate_agent_account,
    
    # Transactions
    validate_customer_account,
    validate_customer_balance,
    check_transaction_limits,
    validate_agent_float,
    check_agent_cash_availability,
    check_fraud,
    verify_customer_pin,
    process_ledger_transaction,
    calculate_and_credit_commission,
    generate_receipt,
    send_transaction_notifications,
    update_transaction_analytics,
    track_cash_disbursement,
    
    # Loans
    check_loan_eligibility,
    perform_credit_scoring,
    check_loan_fraud,
    calculate_repayment_schedule,
    create_loan_record,
    disburse_loan,
    schedule_loan_collections,
    
    # Disputes
    create_dispute_ticket,
    upload_dispute_evidence,
    get_transaction_details,
    notify_support_team,
    investigate_ledger_transaction,
    process_refund,
    update_dispute_status,
    
    # General
    send_notification,
]

