"""Billing and invoice management endpoints."""
import uuid
import time
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

billing_router = APIRouter()

_INVOICES = [
    {
        "id": "INV-2026-001", "tenantId": "tenant-001", "accountNumber": "0012345678",
        "customerName": "Fatima Abdullahi", "invoiceType": "service_charge",
        "description": "Monthly account maintenance fee - April 2026",
        "amount": 1000.00, "currency": "NGN", "status": "paid",
        "dueDate": "2026-04-30", "paidDate": "2026-04-28", "paidAmount": 1000.00,
        "items": [{"description": "Account maintenance fee", "quantity": 1, "unitPrice": 1000.00, "total": 1000.00}],
        "createdAt": "2026-04-01T00:00:00Z", "updatedAt": "2026-04-28T10:00:00Z",
    },
    {
        "id": "INV-2026-002", "tenantId": "tenant-001", "accountNumber": "3034567890",
        "customerName": "Ibrahim Musa", "invoiceType": "transaction_fee",
        "description": "Wire transfer fees - April 2026",
        "amount": 5250.00, "currency": "NGN", "status": "pending",
        "dueDate": "2026-05-15", "paidDate": None, "paidAmount": 0.00,
        "items": [
            {"description": "International wire transfer (3 transactions)", "quantity": 3, "unitPrice": 1500.00, "total": 4500.00},
            {"description": "SWIFT messaging fee", "quantity": 3, "unitPrice": 250.00, "total": 750.00},
        ],
        "createdAt": "2026-05-01T00:00:00Z", "updatedAt": "2026-05-01T00:00:00Z",
    },
    {
        "id": "INV-2026-003", "tenantId": "tenant-001", "accountNumber": "2098765432",
        "customerName": "Chioma Okafor", "invoiceType": "loan_repayment",
        "description": "Personal loan installment - May 2026",
        "amount": 125000.00, "currency": "NGN", "status": "overdue",
        "dueDate": "2026-05-10", "paidDate": None, "paidAmount": 0.00,
        "items": [
            {"description": "Loan principal", "quantity": 1, "unitPrice": 100000.00, "total": 100000.00},
            {"description": "Interest", "quantity": 1, "unitPrice": 25000.00, "total": 25000.00},
        ],
        "createdAt": "2026-05-01T00:00:00Z", "updatedAt": "2026-05-11T00:00:00Z",
    },
]


class InvoiceItem(BaseModel):
    description: str
    quantity: float
    unitPrice: float
    total: float


class CreateInvoiceRequest(BaseModel):
    accountNumber: str
    customerName: str
    invoiceType: str  # service_charge | transaction_fee | loan_repayment | penalty | custom
    description: str
    currency: str = "NGN"
    dueDate: str
    items: List[InvoiceItem]


class PayInvoiceRequest(BaseModel):
    paymentReference: Optional[str] = None
    paymentChannel: str = "account_debit"


_BILLING_PLAN = {
    "billing_info": {
        "plan": "premium",
        "billingCycle": "monthly",
        "nextBillingDate": "2026-06-01",
        "status": "active",
    }
}

_TRENDS = [
    {"month": "Jan", "amount": 850000}, {"month": "Feb", "amount": 920000},
    {"month": "Mar", "amount": 780000}, {"month": "Apr", "amount": 1050000},
    {"month": "May", "amount": 1130250},
]


class UpdatePlanRequest(BaseModel):
    plan: str


@billing_router.get("/v1/billing/me")
def get_billing_me():
    return _BILLING_PLAN


@billing_router.put("/v1/billing/plan")
def update_billing_plan(req: UpdatePlanRequest):
    _BILLING_PLAN["billing_info"]["plan"] = req.plan
    return {"status": "updated", "plan": req.plan}


@billing_router.get("/v1/billing/invoices")
def list_billing_invoices(status: Optional[str] = None, page: int = 1, pageSize: int = 20):
    results = list(_INVOICES)
    if status:
        results = [i for i in results if i["status"] == status]
    total = len(results)
    start = (page - 1) * pageSize
    return {"items": results[start: start + pageSize], "total": total, "page": page, "pageSize": pageSize}


@billing_router.get("/v1/stats")
def get_billing_stats():
    paid = sum(i["paidAmount"] for i in _INVOICES)
    outstanding = sum(i["amount"] - i["paidAmount"] for i in _INVOICES if i["status"] != "paid")
    return {
        "totalCollected": round(paid, 2),
        "totalOutstanding": round(outstanding, 2),
        "invoiceCount": len(_INVOICES),
        "overdueCount": sum(1 for i in _INVOICES if i["status"] == "overdue"),
        "currency": "NGN",
    }


@billing_router.get("/v1/billing/trends")
def get_billing_trends():
    return {"trends": _TRENDS, "currency": "NGN"}


@billing_router.get("/v1/invoices")
def list_invoices_v1(
    status: Optional[str] = None,
    invoiceType: Optional[str] = None,
    accountNumber: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
):
    return list_invoices(status=status, invoiceType=invoiceType, accountNumber=accountNumber, page=page, pageSize=pageSize)


@billing_router.get("/invoices")
def list_invoices(
    status: Optional[str] = None,
    invoiceType: Optional[str] = None,
    accountNumber: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
):
    results = list(_INVOICES)
    if status:
        results = [i for i in results if i["status"] == status]
    if invoiceType:
        results = [i for i in results if i["invoiceType"] == invoiceType]
    if accountNumber:
        results = [i for i in results if i["accountNumber"] == accountNumber]
    total = len(results)
    start = (page - 1) * pageSize
    return {"items": results[start: start + pageSize], "total": total, "page": page, "pageSize": pageSize}


@billing_router.get("/invoices/summary")
def invoice_summary():
    total = len(_INVOICES)
    paid = sum(1 for i in _INVOICES if i["status"] == "paid")
    pending = sum(1 for i in _INVOICES if i["status"] == "pending")
    overdue = sum(1 for i in _INVOICES if i["status"] == "overdue")
    total_outstanding = sum(i["amount"] - i["paidAmount"] for i in _INVOICES if i["status"] != "paid")
    total_collected = sum(i["paidAmount"] for i in _INVOICES)
    return {
        "total": total, "paid": paid, "pending": pending, "overdue": overdue,
        "totalOutstanding": round(total_outstanding, 2),
        "totalCollected": round(total_collected, 2),
    }


@billing_router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: str):
    inv = next((i for i in _INVOICES if i["id"] == invoice_id), None)
    if not inv:
        raise HTTPException(status_code=404, detail="invoice not found")
    return inv


@billing_router.post("/invoices")
def create_invoice(req: CreateInvoiceRequest):
    total_amount = sum(item.total for item in req.items)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    inv = {
        "id": f"INV-{uuid.uuid4().hex[:8].upper()}",
        "tenantId": "",
        "accountNumber": req.accountNumber,
        "customerName": req.customerName,
        "invoiceType": req.invoiceType,
        "description": req.description,
        "amount": round(total_amount, 2),
        "currency": req.currency,
        "status": "pending",
        "dueDate": req.dueDate,
        "paidDate": None,
        "paidAmount": 0.00,
        "items": [item.dict() for item in req.items],
        "createdAt": now,
        "updatedAt": now,
    }
    _INVOICES.append(inv)
    return inv


@billing_router.post("/invoices/{invoice_id}/pay")
def pay_invoice(invoice_id: str, req: PayInvoiceRequest):
    inv = next((i for i in _INVOICES if i["id"] == invoice_id), None)
    if not inv:
        raise HTTPException(status_code=404, detail="invoice not found")
    if inv["status"] == "paid":
        raise HTTPException(status_code=400, detail="invoice already paid")

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    inv["status"] = "paid"
    inv["paidDate"] = now
    inv["paidAmount"] = inv["amount"]
    inv["updatedAt"] = now
    if req.paymentReference:
        inv["paymentReference"] = req.paymentReference
    inv["paymentChannel"] = req.paymentChannel
    return {"status": "paid", "invoiceId": invoice_id, "amountPaid": inv["amount"], "paidAt": now}


@billing_router.post("/invoices/{invoice_id}/cancel")
def cancel_invoice(invoice_id: str):
    inv = next((i for i in _INVOICES if i["id"] == invoice_id), None)
    if not inv:
        raise HTTPException(status_code=404, detail="invoice not found")
    if inv["status"] == "paid":
        raise HTTPException(status_code=400, detail="cannot cancel a paid invoice")

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    inv["status"] = "cancelled"
    inv["updatedAt"] = now
    return {"status": "cancelled", "invoiceId": invoice_id}
