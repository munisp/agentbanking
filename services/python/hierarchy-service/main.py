
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import List, Optional
import logging

from .config import settings
from .models import Base, engine, SessionLocal, HierarchyNode, HierarchyNodeCreate, HierarchyNodeUpdate

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
    # Business logic to retrieve all hierarchy nodes
    _username = current_user.get("username", "unknown")
    logger.info(f"User {_username} creating node: {node.name}")
    nodes = db.query(HierarchyNode).offset(skip).limit(limit).all()
    return nodes

@app.get("/nodes/{node_id}", response_model=HierarchyNode)
async def read_node(node_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Business logic to retrieve a specific hierarchy node by ID
    _username = current_user.get("username", "unknown")
    logger.info(f"User {_username} creating node: {node.name}")
    node = db.query(HierarchyNode).filter(HierarchyNode.id == node_id).first()
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    return node

@app.put("/nodes/{node_id}", response_model=HierarchyNode)
async def update_node(node_id: int, node: HierarchyNodeUpdate, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
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
    _username = current_user.get("username", "unknown")
    logger.info(f"User {_username} creating node: {node.name}")
    children = db.query(HierarchyNode).filter(HierarchyNode.parent_id == node_id).all()
    return children

@app.get("/nodes/{node_id}/parent", response_model=Optional[HierarchyNode])
async def get_node_parent(node_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
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


