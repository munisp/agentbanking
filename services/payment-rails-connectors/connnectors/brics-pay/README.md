# BRICS-PAY Payment Gateway

## Configuration

Set environment variable:
```
BRICS-PAY_API_KEY=your_api_key_here
```

## Usage

```python
from backend.payment_gateways.brics-pay.service import BricsPayService

service = BricsPayService()
result = await service.process_transfer({
    "amount": 1000,
    "currency": "NGN",
    "recipient": "account_id"
})
```
