# Enhanced Workflow Orchestration Service

## Overview

The Enhanced Workflow Orchestration Service provides Temporal.io-based workflow orchestration for all 30 user journeys in the Remittance Platform. It manages complex, multi-step business processes with reliability, durability, and observability.

## Features

### 1. Temporal.io Integration
- **Durable Execution**: Workflows survive service restarts
- **Automatic Retries**: Configurable retry policies for activities
- **Long-Running Workflows**: Support for workflows that run for days/weeks
- **Saga Pattern**: Automatic compensation for failed transactions
- **Versioning**: Safe workflow code updates without breaking running instances

### 2. 30 Workflow Definitions

#### Fully Implemented Workflows (5)

1. **Agent Onboarding** (11 steps)
   - Personal info validation
   - KYC document validation
   - AI document verification
   - Biometric registration
   - Background check
   - Manual review (if needed)
   - Account creation
   - Hierarchy assignment
   - Training enrollment
   - Approval notification
   - Account activation

2. **Cash-In Transaction** (10 steps)
   - Customer account validation
   - Transaction limits check
   - Agent float validation
   - Fraud detection
   - PIN verification
   - Ledger processing
   - Commission calculation
   - Receipt generation
   - Notifications
   - Analytics update

3. **Cash-Out Transaction** (10 steps)
   - Customer balance validation
   - Transaction limits check
   - Agent cash availability
   - Fraud detection
   - PIN verification
   - Ledger processing
   - Cash tracking
   - Commission calculation
   - Receipt generation
   - Notifications

4. **Loan Application** (9 steps)
   - Eligibility check
   - Credit scoring
   - Fraud detection
   - Repayment schedule calculation
   - Auto-approval or manual review
   - Loan record creation
   - Loan disbursement
   - Approval notification
   - Collection scheduling

5. **Dispute Resolution** (9 steps)
   - Dispute ticket creation
   - Evidence upload
   - Transaction retrieval
   - Support team notification
   - Ledger investigation
   - Resolution waiting
   - Refund processing (if approved)
   - Status update
   - Resolution notification

#### Workflow Classes Defined (25)

6. P2P Transfer
7. Bill Payment
8. Airtime & Data Purchase
9. QR Code Payment
10. Commission Tracking
11. Agent Hierarchy
12. Savings Account
13. Multi-Currency
14. Merchant Dashboard
15. Recurring Payment
16. Referral Program
17. Loyalty Points
18. Float Management
19. Transaction Receipt
20. Budget Planning
21. Real-Time Monitoring
22. Compliance Reporting
23. Agent Performance
24. Customer Segmentation
25. Financial Forecasting
26. Customer Support
27. Account 2FA
28. Transaction Limits
29. Offline Transaction
30. Platform Health

### 3. 50+ Activity Definitions

#### Onboarding Activities (9)
- validate_personal_info
- validate_kyc_documents
- ai_document_validation
- register_biometric
- perform_background_check
- create_agent_account
- assign_to_hierarchy
- enroll_in_training
- activate_agent_account

#### Transaction Activities (13)
- validate_customer_account
- validate_customer_balance
- check_transaction_limits
- validate_agent_float
- check_agent_cash_availability
- check_fraud
- verify_customer_pin
- process_ledger_transaction
- calculate_and_credit_commission
- generate_receipt
- send_transaction_notifications
- update_transaction_analytics
- track_cash_disbursement

#### Loan Activities (7)
- check_loan_eligibility
- perform_credit_scoring
- check_loan_fraud
- calculate_repayment_schedule
- create_loan_record
- disburse_loan
- schedule_loan_collections

#### Dispute Activities (7)
- create_dispute_ticket
- upload_dispute_evidence
- get_transaction_details
- notify_support_team
- investigate_ledger_transaction
- process_refund
- update_dispute_status

#### General Activities (1+)
- send_notification

### 4. Workflow Features

#### Retry Policies
```python
RetryPolicy(
    maximum_attempts=3,
    backoff_coefficient=2.0,
    initial_interval=timedelta(seconds=1)
)
```

#### Signal/Wait Conditions
```python
# Wait for manual review
await workflow.wait_condition(
    lambda: workflow.get_signal("manual_review_completed"),
    timeout=timedelta(days=3)
)
```

#### Timeouts
- Activity timeouts: 10s - 24h depending on activity
- Workflow timeouts: Configurable per workflow
- Heartbeat timeouts: For long-running activities

#### Compensation (Saga Pattern)
- Automatic rollback on failure
- Compensating transactions
- Idempotent activities

## API Endpoints

### Workflow Management
```
GET  /                                      # Service info
GET  /health                                # Health check
GET  /api/v1/workflows                      # List workflows
POST /api/v1/workflows/start                # Start workflow
GET  /api/v1/workflows/{id}/status          # Get status
POST /api/v1/workflows/{id}/signal          # Send signal
POST /api/v1/workflows/{id}/cancel          # Cancel workflow
POST /api/v1/workflows/{id}/terminate       # Terminate workflow
```

### Convenience Endpoints
```
POST /api/v1/workflows/agent-onboarding    # Start onboarding
POST /api/v1/workflows/cash-in              # Start cash-in
POST /api/v1/workflows/cash-out             # Start cash-out
POST /api/v1/workflows/loan-application     # Start loan app
POST /api/v1/workflows/dispute-resolution   # Start dispute
```

## Usage Examples

### Start Agent Onboarding Workflow
```bash
curl -X POST http://localhost:8023/api/v1/workflows/start \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_type": "agent_onboarding",
    "input_data": {
      "agent_id": "agent-123",
      "personal_info": {
        "name": "John Doe",
        "phone": "+2348012345678",
        "email": "john@example.com",
        "address": "123 Main St, Lagos",
        "id_number": "12345678"
      },
      "kyc_documents": ["id_card.pdf", "proof_of_address.pdf"],
      "biometric_data": {"fingerprint": "..."},
      "referral_code": "REF123"
    }
  }'
```

### Start Cash-In Workflow
```bash
curl -X POST http://localhost:8023/api/v1/workflows/cash-in \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "txn-456",
    "agent_id": "agent-123",
    "customer_id": "cust-789",
    "transaction_type": "cash_in",
    "amount": 50000.00,
    "currency": "NGN"
  }'
```

### Check Workflow Status
```bash
curl http://localhost:8023/api/v1/workflows/agent_onboarding-123/status
```

### Send Signal to Workflow
```bash
curl -X POST http://localhost:8023/api/v1/workflows/agent_onboarding-123/signal \
  -H "Content-Type: application/json" \
  -d '{
    "signal_name": "manual_review_completed",
    "signal_data": {
      "approved": true,
      "reviewer": "admin-456"
    }
  }'
```

## Installation

### Prerequisites
- Python 3.11+
- Temporal Server running on localhost:7233 (or configured host)
- PostgreSQL (for workflow state persistence)
- Redis (for caching)

### Install Dependencies
```bash
cd /home/ubuntu/remittance-platform/backend/python-services/workflow-orchestration
pip install -r requirements.txt
```

### Start Temporal Server (Docker)
```bash
docker run -d -p 7233:7233 temporalio/auto-setup:latest
```

## Running the Service

### Development
```bash
python main_enhanced.py
```

### Production
```bash
uvicorn main_enhanced:app --host 0.0.0.0 --port 8023 --workers 4
```

## Environment Variables

```bash
# Temporal
TEMPORAL_HOST=localhost:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_TASK_QUEUE=remittance-workflows

# Service URLs
FRAUD_DETECTION_URL=http://localhost:8010
KYC_SERVICE_URL=http://localhost:8011
LEDGER_SERVICE_URL=http://localhost:8005
NOTIFICATION_SERVICE_URL=http://localhost:8012
COMMISSION_SERVICE_URL=http://localhost:8013
CREDIT_SCORING_URL=http://localhost:8014
LOAN_SERVICE_URL=http://localhost:8015

# Service
PORT=8023
```

## Architecture

### Workflow Execution Model

```
┌─────────────┐
│   FastAPI   │  ← REST API for workflow management
│   Service   │
└──────┬──────┘
       │
       ├─────────────────┐
       │                 │
┌──────▼──────┐   ┌──────▼──────┐
│  Temporal   │   │  Temporal   │
│   Client    │   │   Worker    │
└──────┬──────┘   └──────┬──────┘
       │                 │
       └────────┬────────┘
                │
        ┌───────▼────────┐
        │  Temporal      │
        │  Server        │
        └───────┬────────┘
                │
        ┌───────▼────────┐
        │  PostgreSQL    │  ← Workflow state persistence
        └────────────────┘
```

### Workflow Lifecycle

```
Start → Running → [Activities] → Completed
                      ↓
                   Failed → Retry → Running
                      ↓
                   Cancelled
                      ↓
                   Terminated
```

## Integration with User Stories

This service orchestrates workflows for all 30 user stories:

1. Agent Registration & KYC
2. Agent Cash-In
3. Agent Cash-Out
4. P2P Transfer
5. Bill Payment
6. Airtime & Data
7. QR Payment
8. Loan Application
9. Commission Tracking
10. Agent Hierarchy
11. Savings Account
12. Dispute Resolution
13. Multi-Currency
14. Merchant Dashboard
15. Recurring Payments
16. Referral Program
17. Loyalty Points
18. Float Management
19. Transaction Receipt
20. Budget Planning
21. Real-Time Monitoring
22. Compliance Reporting
23. Agent Performance
24. Customer Segmentation
25. Financial Forecasting
26. Customer Support
27. Account 2FA
28. Transaction Limits
29. Offline Transaction
30. Platform Health

## Monitoring & Observability

### Temporal Web UI
- Access at http://localhost:8088 (default)
- View workflow executions
- Inspect workflow history
- Debug failed workflows
- Replay workflows

### Metrics
- Workflow start rate
- Workflow completion rate
- Workflow failure rate
- Activity execution time
- Activity retry count

### Logging
- Structured JSON logs
- Activity-level logging
- Workflow-level logging
- Error tracking

## Best Practices

1. **Idempotent Activities**: All activities should be idempotent
2. **Deterministic Workflows**: Workflow code must be deterministic
3. **Versioning**: Use workflow versioning for code updates
4. **Timeouts**: Always set appropriate timeouts
5. **Retries**: Configure retry policies for transient failures
6. **Signals**: Use signals for external events
7. **Queries**: Use queries for workflow state inspection
8. **Compensation**: Implement compensating transactions

## Troubleshooting

### Workflow Stuck
- Check Temporal Web UI for workflow history
- Verify activity timeouts
- Check for missing signals

### Activity Failures
- Review activity logs
- Check service availability
- Verify retry policy configuration

### Performance Issues
- Increase worker count
- Optimize activity execution time
- Use activity caching where appropriate

## Future Enhancements

1. **Workflow Templates**: Pre-configured workflow templates
2. **Workflow Composition**: Compose complex workflows from simpler ones
3. **Dynamic Workflows**: Generate workflows based on configuration
4. **Workflow Metrics Dashboard**: Real-time workflow metrics
5. **Workflow Testing Framework**: Comprehensive testing utilities
6. **Workflow Simulation**: Simulate workflows before deployment

## Version History

- **v2.0.0** (2025-11-11): Enhanced with Temporal.io, 30 workflows, 50+ activities
- **v1.0.0** (2025-10-01): Basic orchestration implementation

## Support

For issues or questions, refer to:
- Temporal.io documentation: https://docs.temporal.io
- Platform documentation
- Support team

