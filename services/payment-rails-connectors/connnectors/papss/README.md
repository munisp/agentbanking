# PAPSS Payment Gateway

## Configuration

Set environment variable:
```
PAPSS_API_KEY=your_api_key_here
```

## Usage

```python
from backend.payment_gateways.papss.service import PapssService

service = PapssService()
result = await service.process_transfer({
    "amount": 1000,
    "currency": "NGN",
    "recipient": "account_id"
})
```
