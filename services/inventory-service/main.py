from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Depends,
    File,
    UploadFile,
    Header,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Float,
    DateTime,
    ForeignKey,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
import os
import enum
import logging
import httpx
import threading

# Order workflow endpoint

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:password@localhost:5432/remittance_network"
)
# Core-banking document service for storing images in MinIO.
# Override with the internal k8s URL for service-to-service calls:
#   http://document-service.54agent.svc.cluster.local/upload
DOCUMENT_SERVICE_URL = os.getenv(
    "DOCUMENT_SERVICE_URL", "https://54agent.upi.dev/document/upload"
)
DEFAULT_TENANT_ID = os.getenv("TENANT_ID", "54agent")
AUDIT_SVC_URL = os.getenv("AUDIT_SVC_URL", "https://54agent.upi.dev/audit")
engine = create_engine(DATABASE_URL,pool_pre_ping=True, pool_recycle=1800)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Enums
class ItemStatus(str, enum.Enum):
    in_stock = "in_stock"
    low_stock = "low_stock"
    critical = "critical"
    out_of_stock = "out_of_stock"


class ItemCategory(str, enum.Enum):
    hardware = "Hardware"
    accessories = "Accessories"
    consumables = "Consumables"
    software = "Software"


# Database Models
class Store(Base):
    __tablename__ = "stores"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String)
    owner_keycloak_id = Column(String, nullable=False, index=True)
    account_number = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Relationship
    inventory_items = relationship("InventoryItem", back_populates="store")


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    sku = Column(String, unique=True, nullable=False, index=True)
    category = Column(String, nullable=False)
    quantity = Column(Integer, default=0)
    reorder_level = Column(Integer, default=10)
    unit_price = Column(Float, nullable=False)
    supplier = Column(String)
    location = Column(String)
    status = Column(String, default=ItemStatus.in_stock.value)
    barcode = Column(String, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Store relationship
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)
    store = relationship("Store", back_populates="inventory_items")
    # Images relationship
    images = relationship("ItemImage", back_populates="item")


class ItemImage(Base):
    __tablename__ = "item_images"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(
        Integer, ForeignKey("inventory_items.id"), nullable=False, index=True
    )
    url = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    item = relationship("InventoryItem", back_populates="images")


class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True, index=True)
    order_number = Column(String, unique=True, nullable=False, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)
    store_name = Column(String, nullable=False)
    store_location = Column(String)
    agent_keycloak_id = Column(String, nullable=False, index=True)
    agent_account_number = Column(String)
    customer_name = Column(String)
    customer_phone = Column(String)
    customer_email = Column(String)
    payment_method = Column(String, nullable=False)  # cash, transfer, pos
    transaction_id = Column(String)  # For bank transfer and POS payments
    subtotal = Column(Float, nullable=False)
    tax = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    currency = Column(String, default="NGN")
    status = Column(String, default="pending")  # pending, completed, cancelled
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    store = relationship("Store")
    items = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False, index=True)
    inventory_item_id = Column(Integer, nullable=False)
    item_name = Column(String, nullable=False)
    sku = Column(String)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=False)
    category = Column(String)

    # Relationships
    order = relationship("Order", back_populates="items")


class SaleRecord(Base):
    __tablename__ = "sales_records"

    id = Column(String, primary_key=True)
    customer_name = Column(String, nullable=False)
    subtotal = Column(Float, nullable=False)
    tax = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    items = Column(String)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)


# Pydantic Models
class StoreCreate(BaseModel):
    name: str
    description: Optional[str] = None
    owner_keycloak_id: str
    account_number: Optional[str] = None


class StoreResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner_keycloak_id: str
    account_number: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StoreUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    account_number: Optional[str] = None


class InventoryItemCreate(BaseModel):
    name: str
    sku: str
    category: str
    quantity: int = 0
    reorder_level: int = 10
    unit_price: float
    supplier: Optional[str] = None
    location: Optional[str] = None
    barcode: Optional[str] = None
    # store_id removed - it's provided in the URL path


class InventoryItemUpdate(BaseModel):
    name: Optional[str] = None
    quantity: Optional[int] = None
    reorder_level: Optional[int] = None
    unit_price: Optional[float] = None
    supplier: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None
    store_id: Optional[int] = None


class ItemImageCreate(BaseModel):
    url: str


class ItemImageResponse(BaseModel):
    id: int
    item_id: int
    url: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


class InventoryItemResponse(BaseModel):
    id: int
    name: str
    sku: str
    category: str
    quantity: int
    reorder_level: int
    unit_price: float
    supplier: Optional[str]
    location: Optional[str]
    status: str
    barcode: Optional[str]
    created_at: datetime
    updated_at: datetime
    store_id: Optional[int]
    images: Optional[List[ItemImageResponse]] = []

    class Config:
        from_attributes = True


class SaleItem(BaseModel):
    name: str
    sku: str
    quantity: int
    unit_price: float
    total: float


class SaleCreate(BaseModel):
    customer_name: str
    items: List[SaleItem]


class SaleResponse(BaseModel):
    id: str
    customer_name: str
    subtotal: float
    tax: float
    total: float
    items: str
    created_at: datetime

    class Config:
        from_attributes = True


class Item(BaseModel):
    name: str
    store_id: int
    unit_price: float
    quantity: int


class OrderRequestItem(BaseModel):
    order: List[Item]
    account_number: str
    delivery_address: str
    pin: str


# Order Management Schemas
class OrderItemCreate(BaseModel):
    inventory_item_id: int
    item_name: str
    sku: Optional[str] = None
    quantity: int
    unit_price: float
    subtotal: float
    category: Optional[str] = None


class OrderItemResponse(BaseModel):
    id: int
    order_id: str
    inventory_item_id: int
    item_name: str
    sku: Optional[str]
    quantity: int
    unit_price: float
    subtotal: float
    category: Optional[str]

    class Config:
        from_attributes = True


class OrderCreate(BaseModel):
    store_id: int
    store_name: Optional[str] = None
    store_location: Optional[str] = None
    agent_keycloak_id: str
    agent_account_number: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    payment_method: str
    transaction_id: Optional[str] = None
    items: List[OrderItemCreate]
    subtotal: float
    tax: float
    total: float
    currency: Optional[str] = "NGN"
    status: Optional[str] = "completed"
    created_by: Optional[str] = None


class OrderUpdate(BaseModel):
    status: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None


class OrderResponse(BaseModel):
    id: str
    order_number: str
    store_id: int
    store_name: str
    store_location: Optional[str]
    agent_keycloak_id: str
    agent_account_number: Optional[str]
    customer_name: Optional[str]
    customer_phone: Optional[str]
    customer_email: Optional[str]
    payment_method: str
    transaction_id: Optional[str]
    subtotal: float
    tax: float
    total: float
    currency: str
    status: str
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse] = []

    class Config:
        from_attributes = True


class OrderStatsResponse(BaseModel):
    total_orders: int
    total_revenue: float
    pending_orders: int
    completed_orders: int
    cancelled_orders: int
    average_order_value: float


# Create tables
Base.metadata.create_all(bind=engine)

# Run incremental schema migrations for columns added after initial deploy
with engine.connect() as _conn:
    _conn.execute(
        __import__("sqlalchemy").text(
            "ALTER TABLE stores ADD COLUMN IF NOT EXISTS account_number VARCHAR"
        )
    )
    _conn.execute(
        __import__("sqlalchemy").text(
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS transaction_id VARCHAR"
        )
    )
    _conn.commit()

# FastAPI app
app = FastAPI(
    title="54agent Inventory Service",
    description="Inventory and POS management for agent banking platform",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def emit_audit_event(request: Request, status_code: int):
    event_type_map = {
        "POST": "CREATE",
        "PUT": "UPDATE",
        "PATCH": "UPDATE",
        "DELETE": "DELETE",
    }
    event_type = event_type_map.get(request.method)
    if not event_type:
        return

    tenant_id = request.headers.get("x-tenant-id") or DEFAULT_TENANT_ID
    actor_id = request.headers.get("x-keycloak-id") or "system"

    payload = {
        "actor_id": actor_id,
        "tenant_id": tenant_id,
        "event_type": event_type,
        "event_data": {
            "service": "inventory-service",
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "query": str(request.url.query),
        },
        "timestamp": datetime.utcnow().isoformat(),
    }

    def _send():
        try:
            with httpx.Client(timeout=5.0) as client:
                client.post(
                    f"{AUDIT_SVC_URL}/audits",
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "x-tenant-id": tenant_id,
                        "x-keycloak-id": actor_id,
                    },
                )
        except Exception:
            logger.warning("Failed to emit audit event")

    threading.Thread(target=_send, daemon=True).start()


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    response = await call_next(request)
    if (
        request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and response.status_code < 500
        and not request.url.path.startswith(("/docs", "/openapi", "/redoc"))
    ):
        emit_audit_event(request, response.status_code)
    return response


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Helper function to update item status
def update_item_status(item: InventoryItem):
    if item.quantity == 0:
        item.status = ItemStatus.out_of_stock.value
    elif item.quantity < item.reorder_level * 0.5:
        item.status = ItemStatus.critical.value
    elif item.quantity < item.reorder_level:
        item.status = ItemStatus.low_stock.value
    else:
        item.status = ItemStatus.in_stock.value


# Routes
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "inventory-service",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# Store Endpoints
@app.post("/stores", response_model=StoreResponse)
async def create_store(store: StoreCreate, db: Session = Depends(get_db)):
    """Create a new store"""
    db_store = Store(
        name=store.name,
        description=store.description,
        owner_keycloak_id=store.owner_keycloak_id,
        account_number=store.account_number,
    )
    db.add(db_store)
    db.commit()
    db.refresh(db_store)
    logger.info(
        f"Created store: {db_store.name} for owner {db_store.owner_keycloak_id}"
    )
    return db_store


@app.get("/stores", response_model=List[StoreResponse])
async def list_stores(
    owner_keycloak_id: Optional[str] = None, db: Session = Depends(get_db)
):
    """List all stores, optionally filter by owner_keycloak_id"""
    query = db.query(Store)
    if owner_keycloak_id:
        query = query.filter(Store.owner_keycloak_id == owner_keycloak_id)
    stores = query.order_by(Store.created_at.desc()).all()
    return stores


@app.get("/stores/{store_id}", response_model=StoreResponse)
async def get_store(store_id: int, db: Session = Depends(get_db)):
    """Get a specific store by ID"""
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@app.put("/stores/{store_id}", response_model=StoreResponse)
async def update_store(
    store_id: int, store_data: StoreUpdate, db: Session = Depends(get_db)
):
    """Update a store's name, description, or account_number"""
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    if store_data.name is not None:
        store.name = store_data.name
    if store_data.description is not None:
        store.description = store_data.description
    if store_data.account_number is not None:
        store.account_number = store_data.account_number
    store.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(store)
    return store


@app.delete("/stores/{store_id}")
async def delete_store(store_id: int, db: Session = Depends(get_db)):
    """Delete a store and all its inventory items"""
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    # Remove all inventory items first (FK constraint)
    db.query(InventoryItem).filter(InventoryItem.store_id == store_id).delete()
    db.delete(store)
    db.commit()
    logger.info(f"Deleted store {store_id}")
    return {"message": "Store deleted successfully"}


@app.get("/inventory/items", response_model=List[InventoryItemResponse])
async def get_inventory_items(
    search: Optional[str] = None,
    category: Optional[str] = None,
    location: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get all inventory items with optional filters"""
    query = db.query(InventoryItem)

    if search:
        query = query.filter(
            (InventoryItem.name.ilike(f"%{search}%"))
            | (InventoryItem.sku.ilike(f"%{search}%"))
        )

    if category and category != "all":
        query = query.filter(InventoryItem.category == category)

    if location and location != "all":
        query = query.filter(InventoryItem.location == location)

    if status and status != "all":
        query = query.filter(InventoryItem.status == status)

    items = query.all()
    return items


@app.get("/inventory/items/{item_id}", response_model=InventoryItemResponse)
async def get_inventory_item(item_id: int, db: Session = Depends(get_db)):
    """Get a specific inventory item"""
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


# Create inventory item under a store
@app.post("/stores/{store_id}/items", response_model=InventoryItemResponse)
async def create_store_inventory_item(
    store_id: int, item: InventoryItemCreate, db: Session = Depends(get_db)
):
    """Create a new inventory item for a store"""
    # Check if store exists
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    # Check if SKU already exists
    existing = db.query(InventoryItem).filter(InventoryItem.sku == item.sku).first()
    if existing:
        raise HTTPException(status_code=400, detail="SKU already exists")

    # Create item with store_id from URL path
    item_data = item.dict()
    item_data["store_id"] = store_id
    db_item = InventoryItem(**item_data)
    update_item_status(db_item)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    logger.info(f"Created inventory item: {db_item.sku} for store {store_id}")
    return db_item


# List items for a store
@app.get("/stores/{store_id}/items", response_model=List[InventoryItemResponse])
async def list_store_inventory_items(
    store_id: int,
    search: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all inventory items for a store with optional filters"""
    query = db.query(InventoryItem).filter(InventoryItem.store_id == store_id)

    if search:
        query = query.filter(
            (InventoryItem.name.ilike(f"%{search}%"))
            | (InventoryItem.sku.ilike(f"%{search}%"))
        )

    if category and category != "all":
        query = query.filter(InventoryItem.category == category)

    if status and status != "all":
        query = query.filter(InventoryItem.status == status)

    items = query.all()
    return items


# Get all items from all stores (for customer portal)
@app.get("/items", response_model=List[InventoryItemResponse])
async def list_all_items(
    search: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """List all inventory items from all stores (customer marketplace view)"""
    query = db.query(InventoryItem)

    if search:
        query = query.filter(
            (InventoryItem.name.ilike(f"%{search}%"))
            | (InventoryItem.sku.ilike(f"%{search}%"))
        )

    if category and category != "all":
        query = query.filter(InventoryItem.category == category)

    if status and status != "all":
        query = query.filter(InventoryItem.status == status)

    items = query.limit(limit).all()
    return items


@app.put("/inventory/items/{item_id}", response_model=InventoryItemResponse)
async def update_inventory_item(
    item_id: int, item_update: InventoryItemUpdate, db: Session = Depends(get_db)
):
    """Update an inventory item"""
    db_item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")

    update_data = item_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_item, field, value)

    update_item_status(db_item)
    db_item.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(db_item)

    logger.info(f"Updated inventory item: {db_item.sku}")
    return db_item


@app.delete("/inventory/items/{item_id}")
async def delete_inventory_item(item_id: int, db: Session = Depends(get_db)):
    """Delete an inventory item"""
    db_item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")

    db.delete(db_item)
    db.commit()

    logger.info(f"Deleted inventory item: {db_item.sku}")
    return {"message": "Item deleted successfully"}


@app.get("/inventory/alerts")
async def get_stock_alerts(db: Session = Depends(get_db)):
    """Get items with low stock, critical stock, or out of stock"""
    alerts = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.status.in_(
                [
                    ItemStatus.low_stock.value,
                    ItemStatus.critical.value,
                    ItemStatus.out_of_stock.value,
                ]
            )
        )
        .all()
    )

    return alerts


@app.post("/inventory/sales", response_model=SaleResponse)
async def create_sale(sale: SaleCreate, db: Session = Depends(get_db)):
    """Process a sale and update inventory"""
    import json

    # Calculate totals
    subtotal = sum(item.total for item in sale.items)
    tax = subtotal * 0.075  # 7.5% VAT
    total = subtotal + tax

    # Update inventory quantities
    for sale_item in sale.items:
        db_item = (
            db.query(InventoryItem).filter(InventoryItem.sku == sale_item.sku).first()
        )
        if not db_item:
            raise HTTPException(
                status_code=404, detail=f"Item {sale_item.sku} not found"
            )

        if db_item.quantity < sale_item.quantity:
            raise HTTPException(
                status_code=400, detail=f"Insufficient stock for {sale_item.name}"
            )

        db_item.quantity -= sale_item.quantity
        update_item_status(db_item)

    # Create sale record
    sale_id = f"RCP-{int(datetime.utcnow().timestamp() * 1000)}"
    db_sale = SaleRecord(
        id=sale_id,
        customer_name=sale.customer_name,
        subtotal=subtotal,
        tax=tax,
        total=total,
        items=json.dumps([item.dict() for item in sale.items]),
    )

    db.add(db_sale)
    db.commit()
    db.refresh(db_sale)

    logger.info(f"Created sale: {sale_id} for {sale.customer_name}")
    return db_sale


@app.get("/inventory/sales", response_model=List[SaleResponse])
async def get_sales(
    limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)
):
    """Get sales history"""
    sales = (
        db.query(SaleRecord).order_by(SaleRecord.created_at.desc()).limit(limit).all()
    )
    return sales


@app.get("/inventory/metrics")
async def get_inventory_metrics(db: Session = Depends(get_db)):
    """Get inventory metrics"""
    items = db.query(InventoryItem).all()

    total_items = sum(item.quantity for item in items)
    total_value = sum(item.quantity * item.unit_price for item in items)
    low_stock = len(
        [
            i
            for i in items
            if i.status in [ItemStatus.low_stock.value, ItemStatus.critical.value]
        ]
    )
    out_of_stock = len([i for i in items if i.status == ItemStatus.out_of_stock.value])

    return {
        "total_items": total_items,
        "total_value": total_value,
        "low_stock": low_stock,
        "out_of_stock": out_of_stock,
        "unique_items": len(items),
    }


class TransferOrderResponse(BaseModel):
    order_id: str
    status: str
    message: str
    transfer_status: str
    transfer_response: Optional[dict] = None
    created_at: datetime


@app.post("/orders/transfer", response_model=TransferOrderResponse)
async def create_transfer_order(
    order_request: OrderRequestItem, db: Session = Depends(get_db)
):
    """Create an order: transfer funds, then record order."""
    total_amount = sum(
        item.unit_price * item.quantity for item in order_request.order
    )

    store_id = order_request.order[0].store_id if order_request.order else None
    store = (
        db.query(Store).filter(Store.id == store_id).first() if store_id else None
    )
    if not store or not store.account_number:
        raise HTTPException(
            status_code=400, detail="Store account number not found"
        )

    transfer_payload = {
        "payer": order_request.account_number,
        "payee": store.account_number,
        "amount": total_amount,
        "note": f"Order payment for store {store_id}",
        "pin": order_request.pin,
    }

    transfer_url = "https://54agent.upi.dev/payment-processing/payment/transfer"
    transfer_status = "pending"
    transfer_response = None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(transfer_url, json=transfer_payload)
        transfer_response = resp.json()
        if resp.status_code == 200:
            transfer_status = "success"
        else:
            transfer_status = "failed"
            raise HTTPException(
                status_code=502, detail=f"Transfer failed: {transfer_response}"
            )
    except HTTPException:
        raise
    except Exception as exc:
        transfer_status = "failed"
        raise HTTPException(status_code=502, detail=f"Transfer error: {exc}")

    order_id = f"ORD-{int(datetime.utcnow().timestamp() * 1000)}"
    order_record = {
        "order_id": order_id,
        "items": [item.dict() for item in order_request.order],
        "account_number": order_request.account_number,
        "delivery_address": order_request.delivery_address,
        "total_amount": total_amount,
        "created_at": datetime.utcnow().isoformat(),
    }
    import json
    logger.info(f"Order recorded: {json.dumps(order_record)}")

    return TransferOrderResponse(
        order_id=order_id,
        status="created",
        message="Order placed and transfer successful",
        transfer_status=transfer_status,
        transfer_response=transfer_response,
        created_at=datetime.utcnow(),
    )


# Image upload endpoints
@app.post("/inventory/items/{item_id}/images", response_model=ItemImageResponse)
async def upload_item_image(
    item_id: int,
    file: UploadFile = File(...),
    x_tenant_id: Optional[str] = Header(None, alias="x-tenant-id"),
    db: Session = Depends(get_db),
):
    """Upload an image for an inventory item via the core-banking document service (MinIO)."""
    db_item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")

    contents = await file.read()
    tenant_id = x_tenant_id or DEFAULT_TENANT_ID

    # Forward the file to the document service — returns { url, id, filename, content_type }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                DOCUMENT_SERVICE_URL,
                files={
                    "file": (file.filename, contents, file.content_type or "image/jpeg")
                },
                data={"document_type": "product_image"},
                headers={"x-tenant-id": tenant_id},
            )
        if resp.status_code not in (200, 201):
            logger.error(f"Document service error {resp.status_code}: {resp.text}")
            raise HTTPException(
                status_code=502,
                detail=f"Document service returned {resp.status_code}: {resp.text}",
            )
        image_url = resp.json().get("url")
        if not image_url:
            raise HTTPException(
                status_code=502, detail="Document service did not return a URL"
            )
    except httpx.RequestError as exc:
        logger.error(f"Document service unreachable: {exc}")
        raise HTTPException(
            status_code=502, detail=f"Document service unreachable: {exc}"
        )

    db_image = ItemImage(item_id=item_id, url=image_url)
    db.add(db_image)
    db.commit()
    db.refresh(db_image)

    logger.info(f"Uploaded image for item {item_id} -> {image_url}")
    return db_image


@app.post("/inventory/items/{item_id}/images/url", response_model=ItemImageResponse)
async def add_item_image_url(
    item_id: int, image: ItemImageCreate, db: Session = Depends(get_db)
):
    """Add an image URL for an inventory item"""
    # Check if item exists
    db_item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Create image record
    db_image = ItemImage(item_id=item_id, url=image.url)
    db.add(db_image)
    db.commit()
    db.refresh(db_image)

    logger.info(f"Added image URL for item {item_id}")
    return db_image


@app.get("/inventory/items/{item_id}/images", response_model=List[ItemImageResponse])
async def get_item_images(item_id: int, db: Session = Depends(get_db)):
    """Get all images for an inventory item"""
    db_item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")

    return db_item.images


@app.delete("/inventory/items/{item_id}/images/{image_id}")
async def delete_item_image(item_id: int, image_id: int, db: Session = Depends(get_db)):
    """Delete an image for an inventory item"""
    db_image = (
        db.query(ItemImage)
        .filter(ItemImage.id == image_id, ItemImage.item_id == item_id)
        .first()
    )
    if not db_image:
        raise HTTPException(status_code=404, detail="Image not found")

    db.delete(db_image)
    db.commit()

    logger.info(f"Deleted image {image_id} for item {item_id}")
    return {"message": "Image deleted successfully"}


# Order Management Endpoints
@app.post("/inventory/orders", response_model=OrderResponse)
async def create_order(order: OrderCreate, db: Session = Depends(get_db)):
    """Create a new order"""
    import uuid

    # Generate unique order ID and number
    order_id = str(uuid.uuid4())
    order_number = f"ORD-{datetime.utcnow().strftime('%Y%m%d')}-{order_id[:8].upper()}"

    # Get store information if not provided
    if not order.store_name:
        store = db.query(Store).filter(Store.id == order.store_id).first()
        if store:
            order.store_name = store.name
            order.store_location = store.description

    # Create order
    db_order = Order(
        id=order_id,
        order_number=order_number,
        store_id=order.store_id,
        store_name=order.store_name or "Unknown Store",
        store_location=order.store_location,
        agent_keycloak_id=order.agent_keycloak_id,
        agent_account_number=order.agent_account_number,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        customer_email=order.customer_email,
        payment_method=order.payment_method,
        transaction_id=order.transaction_id,
        subtotal=order.subtotal,
        tax=order.tax,
        total=order.total,
        currency=order.currency,
        status=order.status,
        created_by=order.created_by,
    )
    db.add(db_order)

    # Create order items
    for item in order.items:
        db_order_item = OrderItem(
            order_id=order_id,
            inventory_item_id=item.inventory_item_id,
            item_name=item.item_name,
            sku=item.sku,
            quantity=item.quantity,
            unit_price=item.unit_price,
            subtotal=item.subtotal,
            category=item.category,
        )
        db.add(db_order_item)

    db.commit()
    db.refresh(db_order)

    logger.info(f"Created order {order_number} for agent {order.agent_keycloak_id}")
    return db_order


@app.get("/inventory/orders", response_model=List[OrderResponse])
async def get_orders(
    agent_keycloak_id: Optional[str] = None,
    store_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get orders with optional filters"""
    query = db.query(Order)

    if agent_keycloak_id:
        query = query.filter(Order.agent_keycloak_id == agent_keycloak_id)

    if store_id:
        query = query.filter(Order.store_id == store_id)

    if status:
        query = query.filter(Order.status == status)

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(Order.created_at >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(Order.created_at <= end_dt)
        except ValueError:
            pass

    # Apply pagination
    offset = (page - 1) * limit
    orders = query.order_by(Order.created_at.desc()).offset(offset).limit(limit).all()

    return orders


@app.get("/inventory/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str, db: Session = Depends(get_db)):
    """Get a specific order by ID"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.put("/inventory/orders/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: str, order_data: OrderUpdate, db: Session = Depends(get_db)
):
    """Update an order"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order_data.status is not None:
        order.status = order_data.status
    if order_data.customer_name is not None:
        order.customer_name = order_data.customer_name
    if order_data.customer_phone is not None:
        order.customer_phone = order_data.customer_phone
    if order_data.customer_email is not None:
        order.customer_email = order_data.customer_email

    order.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(order)

    logger.info(f"Updated order {order_id}")
    return order


@app.put("/inventory/orders/{order_id}/status")
async def update_order_status(
    order_id: str, status: str = Query(...), db: Session = Depends(get_db)
):
    """Update order status"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.status = status
    order.updated_at = datetime.utcnow()
    db.commit()

    logger.info(f"Updated order {order_id} status to {status}")
    return {"message": "Order status updated", "status": status}


@app.delete("/inventory/orders/{order_id}")
async def delete_order(order_id: str, db: Session = Depends(get_db)):
    """Delete an order"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    db.delete(order)
    db.commit()

    logger.info(f"Deleted order {order_id}")
    return {"message": "Order deleted successfully"}


@app.get("/inventory/stores/{store_id}/orders", response_model=List[OrderResponse])
async def get_store_orders(
    store_id: int,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get all orders for a specific store"""
    query = db.query(Order).filter(Order.store_id == store_id)

    if status:
        query = query.filter(Order.status == status)

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(Order.created_at >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(Order.created_at <= end_dt)
        except ValueError:
            pass

    offset = (page - 1) * limit
    orders = query.order_by(Order.created_at.desc()).offset(offset).limit(limit).all()

    return orders


@app.get("/inventory/stores/{store_id}/orders/stats", response_model=OrderStatsResponse)
async def get_store_order_stats(
    store_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get order statistics for a store"""
    query = db.query(Order).filter(Order.store_id == store_id)

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(Order.created_at >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(Order.created_at <= end_dt)
        except ValueError:
            pass

    orders = query.all()

    total_orders = len(orders)
    total_revenue = sum(order.total for order in orders)
    pending_orders = sum(1 for order in orders if order.status == "pending")
    completed_orders = sum(1 for order in orders if order.status == "completed")
    cancelled_orders = sum(1 for order in orders if order.status == "cancelled")
    average_order_value = total_revenue / total_orders if total_orders > 0 else 0

    return OrderStatsResponse(
        total_orders=total_orders,
        total_revenue=total_revenue,
        pending_orders=pending_orders,
        completed_orders=completed_orders,
        cancelled_orders=cancelled_orders,
        average_order_value=average_order_value,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8096")))
