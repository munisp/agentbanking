"""
Lending Service
Loan origination, disbursement, and repayment
"""

from typing import Dict
from datetime import datetime, timedelta


class LendingService:
    """Lending and loan management"""
    
    def __init__(self):
        self.loans = {}
    
    async def create_loan(self, user_id: str, amount: float, term_months: int, interest_rate: float) -> Dict:
        """Create new loan"""
        try:
            loan_id = f"LOAN-{len(self.loans) + 1:06d}"
            
            monthly_payment = amount * (interest_rate / 12 / 100) / (1 - (1 + interest_rate / 12 / 100) ** -term_months)
            total_repayment = monthly_payment * term_months
            
            loan = {
                "loan_id": loan_id,
                "user_id": user_id,
                "amount": amount,
                "interest_rate": interest_rate,
                "term_months": term_months,
                "monthly_payment": round(monthly_payment, 2),
                "total_repayment": round(total_repayment, 2),
                "status": "pending_approval",
                "created_at": datetime.now().isoformat(),
                "disbursed_at": None,
                "outstanding_balance": amount
            }
            
            self.loans[loan_id] = loan
            
            return {"status": "success", "loan": loan}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    async def approve_loan(self, loan_id: str) -> Dict:
        """Approve loan"""
        try:
            if loan_id not in self.loans:
                return {"status": "failed", "error": "Loan not found"}
            
            self.loans[loan_id]["status"] = "approved"
            self.loans[loan_id]["approved_at"] = datetime.now().isoformat()
            
            return {"status": "success", "loan": self.loans[loan_id]}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    async def disburse_loan(self, loan_id: str) -> Dict:
        """Disburse loan funds"""
        try:
            if loan_id not in self.loans:
                return {"status": "failed", "error": "Loan not found"}
            
            if self.loans[loan_id]["status"] != "approved":
                return {"status": "failed", "error": "Loan not approved"}
            
            self.loans[loan_id]["status"] = "active"
            self.loans[loan_id]["disbursed_at"] = datetime.now().isoformat()
            
            return {"status": "success", "loan": self.loans[loan_id]}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    async def make_payment(self, loan_id: str, amount: float) -> Dict:
        """Make loan payment"""
        try:
            if loan_id not in self.loans:
                return {"status": "failed", "error": "Loan not found"}
            
            loan = self.loans[loan_id]
            loan["outstanding_balance"] -= amount
            
            if loan["outstanding_balance"] <= 0:
                loan["status"] = "paid_off"
                loan["paid_off_at"] = datetime.now().isoformat()
            
            return {"status": "success", "loan": loan, "payment_amount": amount}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
