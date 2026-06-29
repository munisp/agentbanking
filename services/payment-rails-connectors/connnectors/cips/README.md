# CIPS Payment Gateway

## Configuration

Set environment variable:
```
CIPS_API_KEY=your_api_key_here
```

## Usage

```python
from backend.payment_gateways.cips.service import CipsService

service = CipsService()
result = await service.process_transfer({
    "amount": 1000,
    "currency": "NGN",
    "recipient": "account_id"
})
```
