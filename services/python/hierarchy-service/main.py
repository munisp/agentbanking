import os

from fastapi import FastAPI, Depends, HTTPException, status
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.security import OAuth2PasswordBearer
from typing import List, Optional
import logging

from .config import settings
from .models import Base, engine, SessionLocal, HierarchyNode, HierarchyNodeCreate, HierarchyNodeUpdate

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

# --- PostgreSQL Persistence ---
import asyncpg
from typing import Optional

_pg_pool: Optional[asyncpg.Pool] = None

async def get_pg_pool() -> Optional[asyncpg.Pool]:
    global _pg_pool
    if _pg_pool is None:
        try:
            _pg_pool = await asyncpg.create_pool(
                dsn=os.environ.get("DATABASE_URL", "postgresql://localhost:5432/agentbanking"),
                min_size=2, max_size=10, command_timeout=10
            )
            await _pg_pool.execute("""
                CREATE TABLE IF NOT EXISTS service_state (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL DEFAULT '{}',
                    service TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        except Exception:
            _pg_pool = None
    return _pg_pool

async def pg_get(key: str, service: str):
    pool = await get_pg_pool()
    if pool:
        row = await pool.fetchrow(
            "SELECT value FROM service_state WHERE key = $1 AND service = $2", key, service
        )
        return row["value"] if row else None
    return None

async def pg_set(key: str, value, service: str):
    pool = await get_pg_pool()
    if pool:
        import json
        await pool.execute(
            "INSERT INTO service_state (key, value, service, updated_at) VALUES ($1, $2::jsonb, $3, NOW()) "
            "ON CONFLICT (key) DO UPDATE SET value = $2::jsonb, updated_at = NOW()",
            key, json.dumps(value) if not isinstance(value, str) else value, service
        )
# --- End PostgreSQL Persistence ---


_shutdown_handlers = []

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logging.info(f"[shutdown] Received {sig_name}, shutting down gracefully...")
    for handler in reversed(_shutdown_handlers):
        try:
            handler()
        except Exception as e:
            logging.warning(f"[shutdown] Handler error: {e}")
    logging.info("[shutdown] Cleanup complete, exiting")
    sys.exit(0)

signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)
atexit.register(lambda: logging.info("[shutdown] atexit handler called"))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Hierarchy Service API",
    description="API for managing hierarchical structures within the Remittance Platform.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)
apply_middleware(app, enable_auth=True)

# OAuth2PasswordBearer for token-based authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Authentication/authorization logic
def get_current_user(token: str = Depends(oauth2_scheme)):
    # In a real application, this would validate the token and return a user object
    # For now, we'll just assume a valid token means an authenticated user
    logger.info(f"Authenticating user with token: {token[:10]}...")
    if not token: # Simple check, replace with actual token validation
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    from fastapi import HTTPException
    raise HTTPException(status_code=401, detail="Authentication required")

@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up Hierarchy Service...")
    # Create database tables if they don't exist
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables checked/created.")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Hierarchy Service...")

@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    return {"status": "healthy", "service": "hierarchy-service", "version": app.version}

# --- Hierarchy Node Endpoints ---

@app.post("/nodes/", response_model=HierarchyNode, status_code=status.HTTP_201_CREATED)
async def create_node(node: HierarchyNodeCreate, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("create_node_" + str(int(_time.time() * 1000)), _json.dumps({"action": "create_node", "timestamp": _time.time()}), "hierarchy-service")

    # Business logic to create a new hierarchy node
    _username = current_user.get("username", "unknown")
    logger.info(f"User {_username} creating node: {node.name}")
    db_node = HierarchyNode(**node.dict())
    db.add(db_node)
    db.commit()
    db.refresh(db_node)
    return db_node

@app.get("/nodes/", response_model=List[HierarchyNode])
async def read_nodes(skip: int = 0, limit: int = 100, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("read_nodes", "hierarchy-service")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    # Business logic to retrieve all hierarchy nodes
    _username = current_user.get("username", "unknown")
    logger.info(f"User {_username} creating node: {node.name}")
    nodes = db.query(HierarchyNode).offset(skip).limit(limit).all()
    return nodes

@app.get("/nodes/{node_id}", response_model=HierarchyNode)
async def read_node(node_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("read_node", "hierarchy-service")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    # Business logic to retrieve a specific hierarchy node by ID
    _username = current_user.get("username", "unknown")
    logger.info(f"User {_username} creating node: {node.name}")
    node = db.query(HierarchyNode).filter(HierarchyNode.id == node_id).first()
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    return node

@app.put("/nodes/{node_id}", response_model=HierarchyNode)
async def update_node(node_id: int, node: HierarchyNodeUpdate, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("update_node_" + str(int(_time.time() * 1000)), _json.dumps({"action": "update_node", "timestamp": _time.time()}), "hierarchy-service")

    # Business logic to update an existing hierarchy node
    _username = current_user.get("username", "unknown")
    logger.info(f"User {_username} creating node: {node.name}")
    db_node = db.query(HierarchyNode).filter(HierarchyNode.id == node_id).first()
    if db_node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    for key, value in node.dict(exclude_unset=True).items():
        setattr(db_node, key, value)
    db.commit()
    db.refresh(db_node)
    return db_node

@app.delete("/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node(node_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("delete_node_" + str(int(_time.time() * 1000)), _json.dumps({"action": "delete_node", "timestamp": _time.time()}), "hierarchy-service")

    # Business logic to delete a hierarchy node
    _username = current_user.get("username", "unknown")
    logger.info(f"User {_username} creating node: {node.name}")
    db_node = db.query(HierarchyNode).filter(HierarchyNode.id == node_id).first()
    if db_node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    db.delete(db_node)
    db.commit()
    return

@app.get("/nodes/{node_id}/children", response_model=List[HierarchyNode])
async def get_node_children(node_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("get_node_children", "hierarchy-service")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    _username = current_user.get("username", "unknown")
    logger.info(f"User {_username} creating node: {node.name}")
    children = db.query(HierarchyNode).filter(HierarchyNode.parent_id == node_id).all()
    return children

@app.get("/nodes/{node_id}/parent", response_model=Optional[HierarchyNode])
async def get_node_parent(node_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("get_node_parent", "hierarchy-service")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    _username = current_user.get("username", "unknown")
    logger.info(f"User {_username} creating node: {node.name}")
    node = db.query(HierarchyNode).filter(HierarchyNode.id == node_id).first()
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    if node.parent_id is None:
        return None
    parent = db.query(HierarchyNode).filter(HierarchyNode.id == node.parent_id).first()
    return parent

@app.post("/nodes/{node_id}/assign_parent/{parent_id}", response_model=HierarchyNode)
async def assign_parent(node_id: int, parent_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("assign_parent_" + str(int(_time.time() * 1000)), _json.dumps({"action": "assign_parent", "timestamp": _time.time()}), "hierarchy-service")

    _username = current_user.get("username", "unknown")
    logger.info(f"User {_username} creating node: {node.name}")
    node = db.query(HierarchyNode).filter(HierarchyNode.id == node_id).first()
    parent = db.query(HierarchyNode).filter(HierarchyNode.id == parent_id).first()

    if node is None or parent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node or Parent not found")
    
    if node_id == parent_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A node cannot be its own parent")

    # Prevent circular dependencies (simple check for direct parent-child)
    if parent.parent_id == node_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Circular dependency detected")

    node.parent_id = parent_id
    db.commit()
    db.refresh(node)
    return node

@app.post("/nodes/{node_id}/remove_parent", response_model=HierarchyNode)
async def remove_parent(node_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("remove_parent_" + str(int(_time.time() * 1000)), _json.dumps({"action": "remove_parent", "timestamp": _time.time()}), "hierarchy-service")

    _username = current_user.get("username", "unknown")
    logger.info(f"User {_username} creating node: {node.name}")
    node = db.query(HierarchyNode).filter(HierarchyNode.id == node_id).first()
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    node.parent_id = None
    db.commit()
    db.refresh(node)
    return node

# Error handling example (can be expanded)
from starlette.responses import JSONResponse

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
    )

from sqlalchemy.exc import SQLAlchemyError

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request, exc: SQLAlchemyError):
    logger.error(f"Database error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": "An internal database error occurred."},
    )

