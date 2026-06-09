import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Comprehensive QR Code Service
Integrates with E-commerce, Inventory, and Payment systems
Port: 8032
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("qr-code-service")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import qrcode
import qrcode.image.svg
import io
import base64
import hashlib
import hmac
import json
import uuid
import asyncpg
import redis.asyncio as redis
import boto3
import httpx
import os

app = FastAPI(title="QR Code Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database and cache
db_pool = None
redis_client = None
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION", "us-east-1")
)

class QRCodeType(str, Enum):
    PRODUCT = "product"
    PAYMENT = "payment"
    SHIPMENT = "shipment"
    INVOICE = "invoice"

class ProductQRRequest(BaseModel):
    product_id: str
    sku: str
    store_id: str
    product_name: str
    price: float
    currency: str = "NGN"

class PaymentQRRequest(BaseModel):
    amount: float
    currency: str = "NGN"
    merchant_id: str
    description: Optional[str] = None
    expires_in_minutes: int = 15
    order_id: Optional[str] = None

class ShipmentQRRequest(BaseModel):
    shipment_id: str
    purchase_order_id: str
    manufacturer_id: str
    agent_id: str
    items: List[Dict[str, Any]]
    expected_delivery: datetime

class QRCodeResponse(BaseModel):
    qr_id: str
    qr_type: str
    qr_data: Dict[str, Any]
    qr_image_base64: str
    qr_image_url: Optional[str] = None
    expires_at: Optional[datetime] = None

# ==================== HELPER FUNCTIONS ====================

def generate_qr_signature(data: Dict[str, Any]) -> str:
    """Generate HMAC signature for QR code security"""
    secret = os.getenv("QR_SIGNATURE_SECRET", "default_qr_secret_key_change_in_production")
    message = json.dumps(data, sort_keys=True).encode()
    signature = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return signature

def verify_qr_signature(data: Dict[str, Any], signature: str) -> bool:
    """Verify QR code signature"""
    expected = generate_qr_signature(data)
    return hmac.compare_digest(signature, expected)

async def generate_qr_image(data: Dict[str, Any]) -> tuple[str, bytes]:
    """Generate QR code image"""
    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(json.dumps(data))
    qr.make(fit=True)
    
    # Generate image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to bytes
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_bytes = img_buffer.getvalue()
    
    # Convert to base64
    img_base64 = base64.b64encode(img_bytes).decode()
    
    return img_base64, img_bytes

async def upload_qr_to_s3(qr_id: str, img_bytes: bytes) -> str:
    """Upload QR code image to S3"""
    try:
        bucket = os.getenv("S3_BUCKET_NAME", "remittance-qrcodes")
        key = f"qrcodes/{qr_id}.png"
        
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=img_bytes,
            ContentType='image/png',
            ACL='public-read'
        )
        
        url = f"https://{bucket}.s3.amazonaws.com/{key}"
        return url
    except Exception as e:
        print(f"S3 upload failed: {e}")
        return None

async def save_qr_to_db(qr_id: str, qr_type: str, data: Dict[str, Any], 
                        expires_at: Optional[datetime] = None):
    """Save QR code to database"""
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO qr_codes (id, qr_type, qr_data, expires_at, created_at)
            VALUES ($1, $2, $3, $4, $5)
        """, qr_id, qr_type, json.dumps(data), expires_at, datetime.utcnow())

async def track_qr_scan(qr_id: str, scanned_by: Optional[str] = None):
    """Track QR code scan"""
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO qr_scans (qr_id, scanned_by, scanned_at)
            VALUES ($1, $2, $3)
        """, qr_id, scanned_by, datetime.utcnow())
    
    # Update scan count in Redis
    await redis_client.incr(f"qr_scans:{qr_id}")

# ==================== PRODUCT QR CODE ENDPOINTS ====================

@app.post("/qr/product", response_model=QRCodeResponse)
async def generate_product_qr(request: ProductQRRequest):
    """Generate QR code for a product"""
    qr_id = str(uuid.uuid4())
    
    # Create QR data
    qr_data = {
        "type": QRCodeType.PRODUCT,
        "qr_id": qr_id,
        "product_id": request.product_id,
        "sku": request.sku,
        "store_id": request.store_id,
        "product_name": request.product_name,
        "price": request.price,
        "currency": request.currency,
        "timestamp": datetime.utcnow().isoformat(),
        "api_endpoint": f"http://localhost:8020/products/{request.product_id}"
    }
    
    # Add signature
    qr_data["signature"] = generate_qr_signature(qr_data)
    
    # Generate QR image
    img_base64, img_bytes = await generate_qr_image(qr_data)
    
    # Upload to S3
    img_url = await upload_qr_to_s3(qr_id, img_bytes)
    
    # Save to database
    await save_qr_to_db(qr_id, QRCodeType.PRODUCT, qr_data)
    
    # Update product with QR code URL (call e-commerce API)
    try:
        async with httpx.AsyncClient() as client:
            await client.patch(
                f"http://localhost:8020/products/{request.product_id}",
                json={"qr_code_url": img_url, "qr_code_id": qr_id},
                timeout=5.0
            )
    except Exception as e:
        print(f"Failed to update product with QR: {e}")
    
    return QRCodeResponse(
        qr_id=qr_id,
        qr_type=QRCodeType.PRODUCT,
        qr_data=qr_data,
        qr_image_base64=img_base64,
        qr_image_url=img_url
    )

# ==================== PAYMENT QR CODE ENDPOINTS ====================

@app.post("/qr/payment", response_model=QRCodeResponse)
async def generate_payment_qr(request: PaymentQRRequest):
    """Generate dynamic QR code for payment"""
    qr_id = str(uuid.uuid4())
    payment_id = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(minutes=request.expires_in_minutes)
    
    # Create QR data
    qr_data = {
        "type": QRCodeType.PAYMENT,
        "qr_id": qr_id,
        "payment_id": payment_id,
        "amount": request.amount,
        "currency": request.currency,
        "merchant_id": request.merchant_id,
        "description": request.description,
        "order_id": request.order_id,
        "expires_at": expires_at.isoformat(),
        "timestamp": datetime.utcnow().isoformat(),
        "payment_endpoint": "http://localhost:8021/payments"
    }
    
    # Add signature
    qr_data["signature"] = generate_qr_signature(qr_data)
    
    # Generate QR image
    img_base64, img_bytes = await generate_qr_image(qr_data)
    
    # Upload to S3
    img_url = await upload_qr_to_s3(qr_id, img_bytes)
    
    # Save to database
    await save_qr_to_db(qr_id, QRCodeType.PAYMENT, qr_data, expires_at)
    
    # Cache in Redis with expiry
    await redis_client.setex(
        f"payment_qr:{payment_id}",
        request.expires_in_minutes * 60,
        json.dumps(qr_data)
    )
    
    return QRCodeResponse(
        qr_id=qr_id,
        qr_type=QRCodeType.PAYMENT,
        qr_data=qr_data,
        qr_image_base64=img_base64,
        qr_image_url=img_url,
        expires_at=expires_at
    )

# ==================== SHIPMENT QR CODE ENDPOINTS ====================

@app.post("/qr/shipment", response_model=QRCodeResponse)
async def generate_shipment_qr(request: ShipmentQRRequest):
    """Generate QR code for shipment tracking"""
    qr_id = str(uuid.uuid4())
    
    # Create QR data
    qr_data = {
        "type": QRCodeType.SHIPMENT,
        "qr_id": qr_id,
        "shipment_id": request.shipment_id,
        "purchase_order_id": request.purchase_order_id,
        "manufacturer_id": request.manufacturer_id,
        "agent_id": request.agent_id,
        "items": request.items,
        "expected_delivery": request.expected_delivery.isoformat(),
        "timestamp": datetime.utcnow().isoformat(),
        "tracking_endpoint": f"http://localhost:8027/shipments/{request.shipment_id}"
    }
    
    # Add signature
    qr_data["signature"] = generate_qr_signature(qr_data)
    
    # Generate QR image
    img_base64, img_bytes = await generate_qr_image(qr_data)
    
    # Upload to S3
    img_url = await upload_qr_to_s3(qr_id, img_bytes)
    
    # Save to database
    await save_qr_to_db(qr_id, QRCodeType.SHIPMENT, qr_data)
    
    # Update shipment with QR code (call inventory API)
    try:
        async with httpx.AsyncClient() as client:
            await client.patch(
                f"http://localhost:8027/shipments/{request.shipment_id}",
                json={"qr_code_url": img_url, "qr_code_id": qr_id},
                timeout=5.0
            )
    except Exception as e:
        print(f"Failed to update shipment with QR: {e}")
    
    return QRCodeResponse(
        qr_id=qr_id,
        qr_type=QRCodeType.SHIPMENT,
        qr_data=qr_data,
        qr_image_base64=img_base64,
        qr_image_url=img_url
    )

# ==================== QR CODE VALIDATION ENDPOINTS ====================

@app.post("/qr/validate")
async def validate_qr_code(qr_data: Dict[str, Any]):
    """Validate and decode QR code"""
    # Extract signature
    signature = qr_data.get("signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")
    
    # Verify signature
    data_without_sig = {k: v for k, v in qr_data.items() if k != "signature"}
    if not verify_qr_signature(data_without_sig, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Check expiry for payment QR codes
    if qr_data.get("type") == QRCodeType.PAYMENT:
        expires_at = datetime.fromisoformat(qr_data["expires_at"])
        if datetime.utcnow() > expires_at:
            raise HTTPException(status_code=410, detail="QR code expired")
    
    # Track scan
    await track_qr_scan(qr_data["qr_id"])
    
    # Route to appropriate handler
    qr_type = qr_data["type"]
    
    if qr_type == QRCodeType.PRODUCT:
        # Fetch product details from e-commerce
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://localhost:8020/products/{qr_data['product_id']}",
                    timeout=5.0
                )
                product = response.json()
            
            return {
                "valid": True,
                "type": "product",
                "data": product,
                "qr_id": qr_data["qr_id"]
            }
        except Exception as e:
            return {
                "valid": True,
                "type": "product",
                "data": qr_data,
                "qr_id": qr_data["qr_id"],
                "note": "Product API unavailable, using QR data"
            }
    
    elif qr_type == QRCodeType.PAYMENT:
        return {
            "valid": True,
            "type": "payment",
            "payment_id": qr_data["payment_id"],
            "amount": qr_data["amount"],
            "currency": qr_data["currency"],
            "merchant_id": qr_data["merchant_id"],
            "qr_id": qr_data["qr_id"]
        }
    
    elif qr_type == QRCodeType.SHIPMENT:
        # Fetch shipment details from inventory
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://localhost:8027/shipments/{qr_data['shipment_id']}",
                    timeout=5.0
                )
                shipment = response.json()
            
            return {
                "valid": True,
                "type": "shipment",
                "data": shipment,
                "qr_id": qr_data["qr_id"]
            }
        except Exception as e:
            return {
                "valid": True,
                "type": "shipment",
                "data": qr_data,
                "qr_id": qr_data["qr_id"],
                "note": "Shipment API unavailable, using QR data"
            }

# ==================== SHIPMENT SCANNING ENDPOINTS ====================

@app.post("/qr/shipment/{shipment_id}/scan")
async def scan_shipment_qr(
    shipment_id: str,
    scan_type: str,  # "pickup", "in_transit", "delivered"
    scanned_by: str,
    location: Optional[str] = None
):
    """Scan shipment QR code and update status"""
    # Track scan
    await track_qr_scan(shipment_id, scanned_by)
    
    # Update shipment status in inventory management
    try:
        async with httpx.AsyncClient() as client:
            # Update shipment status
            await client.patch(
                f"http://localhost:8027/shipments/{shipment_id}",
                json={
                    "status": scan_type,
                    "scanned_by": scanned_by,
                    "scanned_at": datetime.utcnow().isoformat(),
                    "location": location
                },
                timeout=10.0
            )
            
            # If delivered, update e-commerce inventory
            if scan_type == "delivered":
                shipment_response = await client.get(
                    f"http://localhost:8027/shipments/{shipment_id}",
                    timeout=5.0
                )
                shipment = shipment_response.json()
                
                # Update inventory for each item
                for item in shipment.get("items", []):
                    await client.post(
                        f"http://localhost:8020/products/{item['product_id']}/inventory/adjust",
                        json={
                            "quantity_change": item["quantity"],
                            "reason": f"shipment_delivered:{shipment_id}"
                        },
                        timeout=5.0
                    )
    except Exception as e:
        print(f"Failed to update shipment status: {e}")
    
    return {
        "success": True,
        "shipment_id": shipment_id,
        "status": scan_type,
        "message": f"Shipment {scan_type} scan recorded successfully"
    }

# ==================== ANALYTICS ENDPOINTS ====================

@app.get("/qr/analytics/{qr_id}")
async def get_qr_analytics(qr_id: str):
    """Get analytics for a QR code"""
    # Get scan count from Redis
    scan_count = await redis_client.get(f"qr_scans:{qr_id}")
    
    # Get scan history from database
    async with db_pool.acquire() as conn:
        scans = await conn.fetch("""
            SELECT scanned_by, scanned_at
            FROM qr_scans
            WHERE qr_id = $1
            ORDER BY scanned_at DESC
            LIMIT 100
        """, qr_id)
    
    return {
        "qr_id": qr_id,
        "total_scans": int(scan_count) if scan_count else 0,
        "recent_scans": [
            {
                "scanned_by": scan["scanned_by"],
                "scanned_at": scan["scanned_at"].isoformat()
            }
            for scan in scans
        ]
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "QR Code Service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

# ==================== STARTUP ====================

@app.on_event("startup")
async def startup():
    global db_pool, redis_client
    
    # Initialize database
    db_pool = await asyncpg.create_pool(
        os.getenv("DATABASE_URL", "postgresql://agent_user:agent_password@localhost/remittance_db"),
        min_size=5,
        max_size=20
    )
    
    # Initialize Redis
    redis_client = await redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379")
    )
    
    # Create tables
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS qr_codes (
                id VARCHAR(36) PRIMARY KEY,
                qr_type VARCHAR(20) NOT NULL,
                qr_data JSONB NOT NULL,
                expires_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL
            )
        """)
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS qr_scans (
                id SERIAL PRIMARY KEY,
                qr_id VARCHAR(36) NOT NULL,
                scanned_by VARCHAR(100),
                scanned_at TIMESTAMP NOT NULL
            )
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_qr_scans_qr_id ON qr_scans(qr_id)
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_qr_scans_scanned_at ON qr_scans(scanned_at)
        """)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8032)

