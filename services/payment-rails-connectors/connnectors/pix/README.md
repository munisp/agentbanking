# PIX Payment Gateway

## Configuration

Set environment variable:
```
PIX_API_KEY=your_api_key_here
```

## Usage

```python
from backend.payment_gateways.pix.service import PixService

service = PixService()
result = await service.process_transfer({
    "amount": 1000,
    "currency": "NGN",
    "recipient": "account_id"
})
```
