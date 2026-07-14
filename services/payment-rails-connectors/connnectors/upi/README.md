# UPI Payment Gateway

## Configuration

Set environment variable:
```
UPI_API_KEY=your_api_key_here
```

## Usage

```python
from backend.payment_gateways.upi.service import UpiService

service = UpiService()
result = await service.process_transfer({
    "amount": 1000,
    "currency": "NGN",
    "recipient": "account_id"
})
```
