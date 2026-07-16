# SWIFT Payment Gateway

## Configuration

Set environment variable:
```
SWIFT_API_KEY=your_api_key_here
```

## Usage

```python
from backend.payment_gateways.swift.service import SwiftService

service = SwiftService()
result = await service.process_transfer({
    "amount": 1000,
    "currency": "NGN",
    "recipient": "account_id"
})
```
