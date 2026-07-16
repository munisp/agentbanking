# NIBSS Payment Gateway

## Configuration

Set environment variable:
```
NIBSS_API_KEY=your_api_key_here
```

## Usage

```python
from backend.payment_gateways.nibss.service import NibssService

service = NibssService()
result = await service.process_transfer({
    "amount": 1000,
    "currency": "NGN",
    "recipient": "account_id"
})
```
