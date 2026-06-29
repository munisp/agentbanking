# FEDNOW Payment Gateway

## Configuration

Set environment variable:
```
FEDNOW_API_KEY=your_api_key_here
```

## Usage

```python
from backend.payment_gateways.fednow.service import FednowService

service = FednowService()
result = await service.process_transfer({
    "amount": 1000,
    "currency": "NGN",
    "recipient": "account_id"
})
```
