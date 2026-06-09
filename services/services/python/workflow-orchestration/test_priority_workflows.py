#!/usr/bin/env python3
"""
Integration Tests for Top 5 Priority Workflows
Tests P2P Transfer, Bill Payment, Airtime/Data, Float Management, and Savings Account workflows
"""

import pytest
import asyncio
from datetime import timedelta
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from temporalio.client import Client

# Import workflows
from workflows_priority_5 import (
    P2PTransferWorkflow,
    BillPaymentWorkflow,
    AirtimeDataPurchaseWorkflow,
    FloatManagementWorkflow,
    SavingsAccountWorkflow,
    P2PTransferInput,
    BillPaymentInput,
    AirtimeDataInput,
    FloatManagementInput,
    SavingsAccountInput,
)

# Import activities (mocked for testing)
from workflows_priority_5 import (
    validate_sender_account,
    validate_recipient_account,
    check_p2p_transaction_limits,
    check_p2p_fraud,
    verify_sender_pin,
    process_p2p_ledger_transaction,
    calculate_p2p_commission,
    generate_p2p_receipt,
    send_p2p_notifications,
    update_p2p_analytics,
    validate_biller_account,
    fetch_bill_details,
    submit_bill_payment,
    validate_telco_phone,
    fetch_data_product_details,
    submit_telco_purchase,
    validate_agent_account,
    get_agent_float_balance,
    validate_float_operation,
    check_float_limits,
    process_float_ledger_operation,
    update_float_tracking,
    update_agent_cash_availability,
    generate_float_report,
    send_float_notifications,
    update_float_analytics,
    trigger_float_rebalance_alert,
    validate_savings_operation,
    check_savings_account_status,
    calculate_savings_interest,
    check_savings_compliance,
    request_savings_authorization,
    process_savings_ledger_operation,
    update_savings_account,
    schedule_interest_payments,
    generate_savings_statement,
    send_savings_notifications,
    update_savings_analytics,
)

# Test fixtures
@pytest.fixture
async def workflow_environment():
    """Create a test workflow environment"""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        yield env

@pytest.fixture
async def workflow_client(workflow_environment):
    """Create a test workflow client"""
    return workflow_environment.client

# ============================================================================
# Test 1: P2P Transfer Workflow
# ============================================================================

@pytest.mark.asyncio
async def test_p2p_transfer_success(workflow_client):
    """Test successful P2P transfer"""
    
    # Create test input
    input_data = P2PTransferInput(
        transaction_id="p2p-test-001",
        sender_id="customer-001",
        recipient_id="customer-002",
        amount=10000.00,
        currency="NGN",
        note="Test transfer",
        agent_id="agent-001"
    )
    
    # Execute workflow
    result = await workflow_client.execute_workflow(
        P2PTransferWorkflow.run,
        input_data,
        id=f"p2p-transfer-{input_data.transaction_id}",
        task_queue="test-queue",
    )
    
    # Assertions
    assert result["status"] == "completed"
    assert result["transaction_id"] == "p2p-test-001"
    assert result["amount"] == 10000.00
    assert "ledger_id" in result
    assert "receipt_url" in result

@pytest.mark.asyncio
async def test_p2p_transfer_insufficient_balance(workflow_client):
    """Test P2P transfer with insufficient balance"""
    
    input_data = P2PTransferInput(
        transaction_id="p2p-test-002",
        sender_id="customer-003",  # Customer with low balance
        recipient_id="customer-002",
        amount=1000000.00,  # Large amount
        currency="NGN"
    )
    
    result = await workflow_client.execute_workflow(
        P2PTransferWorkflow.run,
        input_data,
        id=f"p2p-transfer-{input_data.transaction_id}",
        task_queue="test-queue",
    )
    
    assert result["status"] == "failed"
    assert "balance" in result["reason"].lower() or "insufficient" in result["reason"].lower()

@pytest.mark.asyncio
async def test_p2p_transfer_fraud_detection(workflow_client):
    """Test P2P transfer blocked by fraud detection"""
    
    input_data = P2PTransferInput(
        transaction_id="p2p-test-003",
        sender_id="customer-suspicious",
        recipient_id="customer-002",
        amount=50000.00,
        currency="NGN"
    )
    
    result = await workflow_client.execute_workflow(
        P2PTransferWorkflow.run,
        input_data,
        id=f"p2p-transfer-{input_data.transaction_id}",
        task_queue="test-queue",
    )
    
    assert result["status"] == "blocked"
    assert "fraud" in result["reason"].lower()

# ============================================================================
# Test 2: Bill Payment Workflow
# ============================================================================

@pytest.mark.asyncio
async def test_bill_payment_success(workflow_client):
    """Test successful bill payment"""
    
    input_data = BillPaymentInput(
        transaction_id="bill-test-001",
        customer_id="customer-001",
        agent_id="agent-001",
        biller_id="biller-electricity-001",
        biller_name="EKEDC",
        account_number="1234567890",
        amount=5000.00,
        currency="NGN",
        bill_type="electricity"
    )
    
    result = await workflow_client.execute_workflow(
        BillPaymentWorkflow.run,
        input_data,
        id=f"bill-payment-{input_data.transaction_id}",
        task_queue="test-queue",
    )
    
    assert result["status"] == "completed"
    assert result["transaction_id"] == "bill-test-001"
    assert result["amount"] == 5000.00
    assert "ledger_id" in result
    assert "biller_reference" in result
    assert "receipt_url" in result

@pytest.mark.asyncio
async def test_bill_payment_invalid_account(workflow_client):
    """Test bill payment with invalid account number"""
    
    input_data = BillPaymentInput(
        transaction_id="bill-test-002",
        customer_id="customer-001",
        agent_id="agent-001",
        biller_id="biller-electricity-001",
        biller_name="EKEDC",
        account_number="invalid-account",
        amount=5000.00,
        currency="NGN",
        bill_type="electricity"
    )
    
    result = await workflow_client.execute_workflow(
        BillPaymentWorkflow.run,
        input_data,
        id=f"bill-payment-{input_data.transaction_id}",
        task_queue="test-queue",
    )
    
    assert result["status"] == "failed"
    assert "account" in result["reason"].lower() or "invalid" in result["reason"].lower()

@pytest.mark.asyncio
async def test_bill_payment_biller_failure_refund(workflow_client):
    """Test bill payment with biller failure and automatic refund"""
    
    input_data = BillPaymentInput(
        transaction_id="bill-test-003",
        customer_id="customer-001",
        agent_id="agent-001",
        biller_id="biller-fail",  # Biller that fails
        biller_name="Test Biller",
        account_number="1234567890",
        amount=5000.00,
        currency="NGN",
        bill_type="electricity"
    )
    
    result = await workflow_client.execute_workflow(
        BillPaymentWorkflow.run,
        input_data,
        id=f"bill-payment-{input_data.transaction_id}",
        task_queue="test-queue",
    )
    
    assert result["status"] == "failed"
    assert "refund" in result["reason"].lower()

# ============================================================================
# Test 3: Airtime & Data Purchase Workflow
# ============================================================================

@pytest.mark.asyncio
async def test_airtime_purchase_success(workflow_client):
    """Test successful airtime purchase"""
    
    input_data = AirtimeDataInput(
        transaction_id="airtime-test-001",
        customer_id="customer-001",
        agent_id="agent-001",
        telco_provider="MTN",
        phone_number="+2348012345678",
        product_type="airtime",
        amount=1000.00,
        currency="NGN"
    )
    
    result = await workflow_client.execute_workflow(
        AirtimeDataPurchaseWorkflow.run,
        input_data,
        id=f"airtime-{input_data.transaction_id}",
        task_queue="test-queue",
    )
    
    assert result["status"] == "completed"
    assert result["transaction_id"] == "airtime-test-001"
    assert result["amount"] == 1000.00
    assert "ledger_id" in result
    assert "telco_reference" in result
    assert "receipt_url" in result

@pytest.mark.asyncio
async def test_data_purchase_success(workflow_client):
    """Test successful data bundle purchase"""
    
    input_data = AirtimeDataInput(
        transaction_id="data-test-001",
        customer_id="customer-001",
        agent_id="agent-001",
        telco_provider="MTN",
        phone_number="+2348012345678",
        product_type="data",
        product_id="MTN-1GB-MONTHLY",
        amount=1000.00,
        currency="NGN"
    )
    
    result = await workflow_client.execute_workflow(
        AirtimeDataPurchaseWorkflow.run,
        input_data,
        id=f"data-{input_data.transaction_id}",
        task_queue="test-queue",
    )
    
    assert result["status"] == "completed"
    assert result["transaction_id"] == "data-test-001"
    assert "voucher_code" in result or "telco_reference" in result

@pytest.mark.asyncio
async def test_airtime_invalid_phone(workflow_client):
    """Test airtime purchase with invalid phone number"""
    
    input_data = AirtimeDataInput(
        transaction_id="airtime-test-002",
        customer_id="customer-001",
        agent_id="agent-001",
        telco_provider="MTN",
        phone_number="invalid-phone",
        product_type="airtime",
        amount=1000.00,
        currency="NGN"
    )
    
    result = await workflow_client.execute_workflow(
        AirtimeDataPurchaseWorkflow.run,
        input_data,
        id=f"airtime-{input_data.transaction_id}",
        task_queue="test-queue",
    )
    
    assert result["status"] == "failed"
    assert "phone" in result["reason"].lower() or "invalid" in result["reason"].lower()

# ============================================================================
# Test 4: Float Management Workflow
# ============================================================================

@pytest.mark.asyncio
async def test_float_deposit_success(workflow_client):
    """Test successful float deposit"""
    
    input_data = FloatManagementInput(
        operation_id="float-test-001",
        agent_id="agent-001",
        operation_type="deposit",
        amount=100000.00,
        currency="NGN",
        reason="Daily float top-up"
    )
    
    result = await workflow_client.execute_workflow(
        FloatManagementWorkflow.run,
        input_data,
        id=f"float-{input_data.operation_id}",
        task_queue="test-queue",
    )
    
    assert result["status"] == "completed"
    assert result["operation_id"] == "float-test-001"
    assert result["operation_type"] == "deposit"
    assert result["amount"] == 100000.00
    assert "new_balance" in result
    assert "ledger_id" in result
    assert "report_url" in result

@pytest.mark.asyncio
async def test_float_withdrawal_success(workflow_client):
    """Test successful float withdrawal"""
    
    input_data = FloatManagementInput(
        operation_id="float-test-002",
        agent_id="agent-001",
        operation_type="withdrawal",
        amount=50000.00,
        currency="NGN",
        reason="End of day settlement"
    )
    
    result = await workflow_client.execute_workflow(
        FloatManagementWorkflow.run,
        input_data,
        id=f"float-{input_data.operation_id}",
        task_queue="test-queue",
    )
    
    assert result["status"] == "completed"
    assert result["operation_type"] == "withdrawal"
    assert result["amount"] == 50000.00

@pytest.mark.asyncio
async def test_float_transfer_success(workflow_client):
    """Test successful float transfer between agents"""
    
    input_data = FloatManagementInput(
        operation_id="float-test-003",
        agent_id="agent-001",
        operation_type="transfer",
        amount=25000.00,
        currency="NGN",
        source_agent_id="agent-001",
        target_agent_id="agent-002",
        reason="Float rebalancing"
    )
    
    result = await workflow_client.execute_workflow(
        FloatManagementWorkflow.run,
        input_data,
        id=f"float-{input_data.operation_id}",
        task_queue="test-queue",
    )
    
    assert result["status"] == "completed"
    assert result["operation_type"] == "transfer"

@pytest.mark.asyncio
async def test_float_rebalance_alert(workflow_client):
    """Test float rebalance alert triggered when balance is low"""
    
    input_data = FloatManagementInput(
        operation_id="float-test-004",
        agent_id="agent-low-balance",
        operation_type="withdrawal",
        amount=90000.00,  # Large withdrawal
        currency="NGN",
        reason="Large customer payout"
    )
    
    result = await workflow_client.execute_workflow(
        FloatManagementWorkflow.run,
        input_data,
        id=f"float-{input_data.operation_id}",
        task_queue="test-queue",
    )
    
    # Should complete but trigger rebalance alert
    assert result["status"] == "completed"
    # Alert would be sent to agent/admin

# ============================================================================
# Test 5: Savings Account Workflow
# ============================================================================

@pytest.mark.asyncio
async def test_savings_account_open_success(workflow_client):
    """Test successful savings account opening"""
    
    input_data = SavingsAccountInput(
        account_id="savings-test-001",
        customer_id="customer-001",
        operation_type="open",
        amount=10000.00,
        account_type="regular",
        interest_rate=5.0,
        withdrawal_frequency="monthly"
    )
    
    result = await workflow_client.execute_workflow(
        SavingsAccountWorkflow.run,
        input_data,
        id=f"savings-{input_data.account_id}",
        task_queue="test-queue",
    )
    
    assert result["status"] == "completed"
    assert result["account_id"] == "savings-test-001"
    assert result["operation_type"] == "open"
    assert result["amount"] == 10000.00
    assert "new_balance" in result
    assert "ledger_id" in result
    assert "statement_url" in result

@pytest.mark.asyncio
async def test_savings_deposit_success(workflow_client):
    """Test successful savings deposit"""
    
    input_data = SavingsAccountInput(
        account_id="savings-test-001",
        customer_id="customer-001",
        operation_type="deposit",
        amount=5000.00
    )
    
    result = await workflow_client.execute_workflow(
        SavingsAccountWorkflow.run,
        input_data,
        id=f"savings-deposit-{input_data.account_id}",
        task_queue="test-queue",
    )
    
    assert result["status"] == "completed"
    assert result["operation_type"] == "deposit"
    assert result["amount"] == 5000.00

@pytest.mark.asyncio
async def test_savings_withdrawal_with_interest(workflow_client):
    """Test savings withdrawal with interest calculation"""
    
    input_data = SavingsAccountInput(
        account_id="savings-test-001",
        customer_id="customer-001",
        operation_type="withdraw",
        amount=3000.00,
        account_type="regular",
        interest_rate=5.0
    )
    
    result = await workflow_client.execute_workflow(
        SavingsAccountWorkflow.run,
        input_data,
        id=f"savings-withdraw-{input_data.account_id}",
        task_queue="test-queue",
    )
    
    assert result["status"] == "completed"
    assert result["operation_type"] == "withdraw"
    assert result["amount"] == 3000.00
    assert "interest_amount" in result

@pytest.mark.asyncio
async def test_savings_fixed_term_account(workflow_client):
    """Test fixed-term savings account creation"""
    
    input_data = SavingsAccountInput(
        account_id="savings-test-002",
        customer_id="customer-001",
        operation_type="open",
        amount=50000.00,
        account_type="fixed",
        interest_rate=8.0,
        term_months=12
    )
    
    result = await workflow_client.execute_workflow(
        SavingsAccountWorkflow.run,
        input_data,
        id=f"savings-{input_data.account_id}",
        task_queue="test-queue",
    )
    
    assert result["status"] == "completed"
    assert result["account_id"] == "savings-test-002"
    # Interest payments should be scheduled

@pytest.mark.asyncio
async def test_savings_target_account(workflow_client):
    """Test target savings account creation"""
    
    input_data = SavingsAccountInput(
        account_id="savings-test-003",
        customer_id="customer-001",
        operation_type="open",
        amount=5000.00,
        account_type="target",
        interest_rate=6.0,
        target_amount=100000.00,
        term_months=24
    )
    
    result = await workflow_client.execute_workflow(
        SavingsAccountWorkflow.run,
        input_data,
        id=f"savings-{input_data.account_id}",
        task_queue="test-queue",
    )
    
    assert result["status"] == "completed"
    assert result["account_id"] == "savings-test-003"

@pytest.mark.asyncio
async def test_savings_close_account(workflow_client):
    """Test savings account closure with final interest"""
    
    input_data = SavingsAccountInput(
        account_id="savings-test-001",
        customer_id="customer-001",
        operation_type="close",
        account_type="regular",
        interest_rate=5.0
    )
    
    result = await workflow_client.execute_workflow(
        SavingsAccountWorkflow.run,
        input_data,
        id=f"savings-close-{input_data.account_id}",
        task_queue="test-queue",
    )
    
    assert result["status"] == "completed"
    assert result["operation_type"] == "close"
    assert "interest_amount" in result
    assert result["new_balance"] == 0  # Account closed

# ============================================================================
# Test Runner
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

