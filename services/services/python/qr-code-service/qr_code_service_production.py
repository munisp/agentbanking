import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Production-Grade QR Code Service
Integrates with E-commerce, Inventory, and Payment systems
Port: 8032

Improvements:
- Rate limiting
- Structured logging
- Input validation limits
- Startup secret validation
- Database error handling
- Metrics export
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("qr-code-service-(production)")
app.include_router(metrics_router)

from pydantic import BaseModel, Field, validator
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
import logging
from logging.handlers import RotatingFileHandler
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from starlette.responses import Response

# ==================== LOGGING SETUP ====================

# Create logs directory
os.makedirs("/var/log/qr-service", exist_ok=True)

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            "/var/log/qr-service/qr_service.log",
            maxBytes=10485760,  # 10MB
            backupCount=5
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# ==================== METRICS SETUP ====================

# Prometheus metrics
qr_generated_total = Counter('qr_generated_total', 'Total QR codes generated', ['qr_type'])
qr_scanned_total = Counter('qr_scanned_total', 'Total QR codes scanned', ['qr_type'])
qr_validation_total = Counter('qr_validation_total', 'Total QR validations', ['status'])
qr_generation_duration = Histogram('qr_generation_duration_seconds', 'QR generation duration')
active_qr_codes = Gauge('active_qr_codes', 'Number of active QR codes', ['qr_type'])

# ==================== APP SETUP ====================

app = FastAPI(title="QR Code Service (Production)", version="2.0.0")

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
s3_client = None

class QRCodeType(str, Enum):
    PRODUCT = "product"
    PAYMENT = "payment"
    SHIPMENT = "shipment"
    INVOICE = "invoice"

# ==================== PYDANTIC MODELS WITH VALIDATION ====================

class ProductQRRequest(BaseModel):
    product_id: str = Field(..., min_length=1, max_length=100)
    sku: str = Field(..., min_length=1, max_length=100)
    store_id: str = Field(..., min_length=1, max_length=100)
    product_name: str = Field(..., min_length=1, max_length=500)
    price: float = Field(..., gt=0, le=10000000)  # Max 10M
    currency: str = Field(default="NGN", regex="^[A-Z]{3}$")

class PaymentQRRequest(BaseModel):
    amount: float = Field(..., gt=0, le=10000000)  # Max 10M
    currency: str = Field(default="NGN", regex="^[A-Z]{3}$")
    merchant_id: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    expires_in_minutes: int = Field(default=15, ge=1, le=60)  # Max 1 hour
    order_id: Optional[str] = Field(None, max_length=100)

class ShipmentQRRequest(BaseModel):
    shipment_id: str = Field(..., min_length=1, max_length=100)
    purchase_order_id: str = Field(..., min_length=1, max_length=100)
    manufacturer_id: str = Field(..., min_length=1, max_length=100)
    agent_id: str = Field(..., min_length=1, max_length=100)
    items: List[Dict[str, Any]] = Field(..., max_items=1000)
    expected_delivery: datetime

    @validator('items')
    def validate_items(cls, v):
        if not v:
            raise ValueError("Items list cannot be empty")
        return v

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
    secret = os.getenv("QR_SIGNATURE_SECRET")
    if not secret:
        logger.error("QR_SIGNATURE_SECRET not set!")
        raise ValueError("QR_SIGNATURE_SECRET must be set")
    
    message = json.dumps(data, sort_keys=True).encode()
    signature = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return signature

def verify_qr_signature(data: Dict[str, Any], signature: str) -> bool:
    """Verify QR code signature"""
    try:
        expected = generate_qr_signature(data)
        return hmac.compare_digest(signature, expected)
    except Exception as e:
        logger.error(f"Signature verification failed: {e}")
        return False

async def generate_qr_image(data: Dict[str, Any]) -> tuple[str, bytes]:
    """Generate QR code image"""
    try:
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
    except Exception as e:
        logger.error(f"QR image generation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate QR image")

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
        logger.info(f"QR code uploaded to S3: {url}")
        return url
    except Exception as e:
        logger.error(f"S3 upload failed: {e}")
        return None

async def save_qr_to_db(qr_id: str, qr_type: str, data: Dict[str, Any], 
                        expires_at: Optional[datetime] = None):
    """Save QR code to database"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO qr_codes (id, qr_type, qr_data, expires_at, created_at)
                VALUES ($1, $2, $3, $4, $5)
            """, qr_id, qr_type, json.dumps(data), expires_at, datetime.utcnow())
        
        logger.info(f"QR code saved to database: {qr_id}")
    except asyncpg.PostgresError as e:
        logger.error(f"Database error saving QR code: {e}")
        raise HTTPException(status_code=500, detail="Failed to save QR code")

async def track_qr_scan(qr_id: str, scanned_by: Optional[str] = None):
    """Track QR code scan"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO qr_scans (qr_id, scanned_by, scanned_at)
                VALUES ($1, $2, $3)
            """, qr_id, scanned_by, datetime.utcnow())
        
        # Update scan count in Redis
        await redis_client.incr(f"qr_scans:{qr_id}")
        
        logger.info(f"QR scan tracked: {qr_id} by {scanned_by}")
    except Exception as e:
        logger.error(f"Failed to track QR scan: {e}")

# ==================== PRODUCT QR CODE ENDPOINTS ====================

@app.post("/qr/product", response_model=QRCodeResponse)
@limiter.limit("20/minute")
async def generate_product_qr(request: Request, data: ProductQRRequest):
    """Generate QR code for a product (Rate limited: 20/min)"""
    with qr_generation_duration.time():
        qr_id = str(uuid.uuid4())
        
        # Create QR data
        qr_data = {
            "type": QRCodeType.PRODUCT,
            "qr_id": qr_id,
            "product_id": data.product_id,
            "sku": data.sku,
            "store_id": data.store_id,
            "product_name": data.product_name,
            "price": data.price,
            "currency": data.currency,
            "timestamp": datetime.utcnow().isoformat(),
            "api_endpoint": f"http://localhost:8020/products/{data.product_id}"
        }
        
        # Add signature
        qr_data["signature"] = generate_qr_signature(qr_data)
        
        # Generate QR image
        img_base64, img_bytes = await generate_qr_image(qr_data)
        
        # Upload to S3
        img_url = await upload_qr_to_s3(qr_id, img_bytes)
        
        # Save to database
        await save_qr_to_db(qr_id, QRCodeType.PRODUCT, qr_data)
        
        # Update metrics
        qr_generated_total.labels(qr_type='product').inc()
        active_qr_codes.labels(qr_type='product').inc()
        
        # Update product with QR code URL
        try:
            async with httpx.AsyncClient() as client:
                await client.patch(
                    f"http://localhost:8020/products/{data.product_id}",
                    json={"qr_code_url": img_url, "qr_code_id": qr_id},
                    timeout=5.0
                )
        except Exception as e:
            logger.warning(f"Failed to update product with QR: {e}")
        
        logger.info(f"Product QR generated: {qr_id} for product {data.product_id}")
        
        return QRCodeResponse(
            qr_id=qr_id,
            qr_type=QRCodeType.PRODUCT,
            qr_data=qr_data,
            qr_image_base64=img_base64,
            qr_image_url=img_url
        )

# ==================== PAYMENT QR CODE ENDPOINTS ====================

@app.post("/qr/payment", response_model=QRCodeResponse)
@limiter.limit("10/minute")
async def generate_payment_qr(request: Request, data: PaymentQRRequest):
    """Generate dynamic QR code for payment (Rate limited: 10/min)"""
    with qr_generation_duration.time():
        qr_id = str(uuid.uuid4())
        payment_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(minutes=data.expires_in_minutes)
        
        # Create QR data
        qr_data = {
            "type": QRCodeType.PAYMENT,
            "qr_id": qr_id,
            "payment_id": payment_id,
            "amount": data.amount,
            "currency": data.currency,
            "merchant_id": data.merchant_id,
            "description": data.description,
            "order_id": data.order_id,
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
        try:
            await redis_client.setex(
                f"payment_qr:{payment_id}",
                data.expires_in_minutes * 60,
                json.dumps(qr_data)
            )
        except Exception as e:
            logger.error(f"Redis cache failed: {e}")
        
        # Update metrics
        qr_generated_total.labels(qr_type='payment').inc()
        active_qr_codes.labels(qr_type='payment').inc()
        
        logger.info(f"Payment QR generated: {qr_id} for amount {data.amount} {data.currency}")
        
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
@limiter.limit("20/minute")
async def generate_shipment_qr(request: Request, data: ShipmentQRRequest):
    """Generate QR code for shipment tracking (Rate limited: 20/min)"""
    with qr_generation_duration.time():
        qr_id = str(uuid.uuid4())
        
        # Create QR data
        qr_data = {
            "type": QRCodeType.SHIPMENT,
            "qr_id": qr_id,
            "shipment_id": data.shipment_id,
            "purchase_order_id": data.purchase_order_id,
            "manufacturer_id": data.manufacturer_id,
            "agent_id": data.agent_id,
            "items": data.items,
            "expected_delivery": data.expected_delivery.isoformat(),
            "timestamp": datetime.utcnow().isoformat(),
            "tracking_endpoint": f"http://localhost:8027/shipments/{data.shipment_id}"
        }
        
        # Add signature
        qr_data["signature"] = generate_qr_signature(qr_data)
        
        # Generate QR image
        img_base64, img_bytes = await generate_qr_image(qr_data)
        
        # Upload to S3
        img_url = await upload_qr_to_s3(qr_id, img_bytes)
        
        # Save to database
        await save_qr_to_db(qr_id, QRCodeType.SHIPMENT, qr_data)
        
        # Update metrics
        qr_generated_total.labels(qr_type='shipment').inc()
        active_qr_codes.labels(qr_type='shipment').inc()
        
        # Update shipment with QR code
        try:
            async with httpx.AsyncClient() as client:
                await client.patch(
                    f"http://localhost:8027/shipments/{data.shipment_id}",
                    json={"qr_code_url": img_url, "qr_code_id": qr_id},
                    timeout=5.0
                )
        except Exception as e:
            logger.warning(f"Failed to update shipment with QR: {e}")
        
        logger.info(f"Shipment QR generated: {qr_id} for shipment {data.shipment_id}")
        
        return QRCodeResponse(
            qr_id=qr_id,
            qr_type=QRCodeType.SHIPMENT,
            qr_data=qr_data,
            qr_image_base64=img_base64,
            qr_image_url=img_url
        )

# ==================== QR CODE VALIDATION ENDPOINTS ====================

@app.post("/qr/validate")
@limiter.limit("30/minute")
async def validate_qr_code(request: Request, qr_data: Dict[str, Any]):
    """Validate and decode QR code (Rate limited: 30/min)"""
    try:
        # Extract signature
        signature = qr_data.get("signature")
        if not signature:
            qr_validation_total.labels(status='missing_signature').inc()
            raise HTTPException(status_code=400, detail="Missing signature")
        
        # Verify signature
        data_without_sig = {k: v for k, v in qr_data.items() if k != "signature"}
        if not verify_qr_signature(data_without_sig, signature):
            qr_validation_total.labels(status='invalid_signature').inc()
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Check expiry for payment QR codes
        if qr_data.get("type") == QRCodeType.PAYMENT:
            expires_at = datetime.fromisoformat(qr_data["expires_at"])
            if datetime.utcnow() > expires_at:
                qr_validation_total.labels(status='expired').inc()
                raise HTTPException(status_code=410, detail="QR code expired")
        
        # Track scan
        await track_qr_scan(qr_data["qr_id"])
        qr_scanned_total.labels(qr_type=qr_data.get("type", "unknown")).inc()
        qr_validation_total.labels(status='valid').inc()
        
        # Route to appropriate handler
        qr_type = qr_data["type"]
        
        if qr_type == QRCodeType.PRODUCT:
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
                logger.warning(f"Product API unavailable: {e}")
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
                logger.warning(f"Shipment API unavailable: {e}")
                return {
                    "valid": True,
                    "type": "shipment",
                    "data": qr_data,
                    "qr_id": qr_data["qr_id"],
                    "note": "Shipment API unavailable, using QR data"
                }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"QR validation error: {e}")
        qr_validation_total.labels(status='error').inc()
        raise HTTPException(status_code=500, detail="Validation failed")

# ==================== SHIPMENT SCANNING ENDPOINTS ====================

@app.post("/qr/shipment/{shipment_id}/scan")
@limiter.limit("20/minute")
async def scan_shipment_qr(
    request: Request,
    shipment_id: str,
    scan_type: str,
    scanned_by: str,
    location: Optional[str] = None
):
    """Scan shipment QR code and update status (Rate limited: 20/min)"""
    try:
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
                    
                    logger.info(f"Shipment delivered and inventory updated: {shipment_id}")
        except Exception as e:
            logger.error(f"Failed to update shipment status: {e}")
            raise HTTPException(status_code=500, detail="Failed to update shipment")
        
        return {
            "success": True,
            "shipment_id": shipment_id,
            "status": scan_type,
            "message": f"Shipment {scan_type} scan recorded successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Shipment scan error: {e}")
        raise HTTPException(status_code=500, detail="Scan failed")

# ==================== ANALYTICS ENDPOINTS ====================

@app.get("/qr/analytics/{qr_id}")
async def get_qr_analytics(qr_id: str):
    """Get analytics for a QR code"""
    try:
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
    except Exception as e:
        logger.error(f"Analytics retrieval error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve analytics")

# ==================== METRICS ENDPOINT ====================

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type="text/plain")

# ==================== HEALTH CHECK ====================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        
        # Check Redis
        await redis_client.ping()
        
        return {
            "status": "healthy",
            "service": "QR Code Service (Production)",
            "version": "2.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected",
            "redis": "connected"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# ==================== STARTUP ====================

@app.on_event("startup")
async def startup():
    global db_pool, redis_client, s3_client
    
    logger.info("Starting QR Code Service (Production)...")
    
    # Validate required environment variables
    required_vars = ["QR_SIGNATURE_SECRET", "DATABASE_URL", "REDIS_URL"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Validate secret is not default
    secret = os.getenv("QR_SIGNATURE_SECRET")
    if secret == "default_qr_secret_key_change_in_production":
        error_msg = "QR_SIGNATURE_SECRET must be changed from default value"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    logger.info("Environment variables validated")
    
    # Initialize database
    try:
        db_pool = await asyncpg.create_pool(
            os.getenv("DATABASE_URL"),
            min_size=5,
            max_size=20
        )
        logger.info("Database connection pool created")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise
    
    # Initialize Redis
    try:
        redis_client = await redis.from_url(os.getenv("REDIS_URL"))
        await redis_client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        raise
    
    # Initialize S3
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION", "us-east-1")
        )
        logger.info("S3 client initialized")
    except Exception as e:
        logger.warning(f"S3 client initialization failed: {e}")
    
    # Create tables
    try:
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
        
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error(f"Table creation failed: {e}")
        raise
    
    logger.info("QR Code Service (Production) started successfully")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8032)

