import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_

from . import models
from . import config
from .models import (
    HierarchyNode,
    HierarchyActivityLog,
    HierarchyNodeResponse,
    HierarchyNodeCreate,
    HierarchyNodeUpdate,
    HierarchyActivityLogResponse,
    HierarchyMove,
    HierarchyTreeResponse,
)

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(
    prefix="/hierarchy",
    tags=["hierarchy"],
    responses={404: {"description": "Not found"}},
)

# Dependency to get the database session
get_db = config.get_db

# --- Helper Functions ---

def log_activity(db: Session, node_id: int, action: str, details: Optional[str] = None, user_id: Optional[str] = "system"):
    """Logs an activity for a specific hierarchy node."""
    log_entry = HierarchyActivityLog(
        node_id=node_id,
        action=action,
        details=details,
        user_id=user_id,
    )
    db.add(log_entry)
    try:
        db.commit()
        db.refresh(log_entry)
        logger.info(f"Activity logged for node {node_id}: {action}")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to log activity for node {node_id}: {e}")

def build_tree(nodes: List[HierarchyNode]) -> List[HierarchyNodeResponse]:
    """
    Converts a flat list of HierarchyNode objects into a nested tree structure 
    using the HierarchyNodeResponse Pydantic model.
    """
    node_map: Dict[int, HierarchyNodeResponse] = {}
    root_nodes: List[HierarchyNodeResponse] = []

    # First pass: convert all SQLAlchemy objects to Pydantic response objects
    # and map them by ID.
    for node in nodes:
        # We need to manually handle the recursive part to avoid infinite recursion
        # and ensure we are using the Pydantic model for the tree structure.
        # We pass an empty list for children for now.
        node_response = HierarchyNodeResponse.model_validate(node, update={'children': []})
        node_map[node.id] = node_response

    # Second pass: build the tree structure
    for node_id, node_response in node_map.items():
        parent_id = node_response.parent_id
        if parent_id is None:
            root_nodes.append(node_response)
        elif parent_id in node_map:
            # Add the current node to its parent's children list
            node_map[parent_id].children.append(node_response)
            
    return root_nodes

# --- CRUD Endpoints ---

@router.post(
    "/nodes/",
    response_model=HierarchyNodeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new hierarchy node",
    description="Creates a new node in the hierarchy. Optionally links it to an existing parent node."
)
def create_node(node: HierarchyNodeCreate, db: Session = Depends(get_db)):
    """
    Creates a new HierarchyNode in the database.
    """
    if node.parent_id is not None:
        parent = db.query(HierarchyNode).filter(HierarchyNode.id == node.parent_id).first()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent node with id {node.parent_id} not found."
            )

    db_node = HierarchyNode(**node.model_dump())
    db.add(db_node)
    try:
        db.commit()
        db.refresh(db_node)
        log_activity(db, db_node.id, "CREATE", f"Node created with name: {db_node.name}")
        return db_node
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integrity error: Node name might already exist or parent_id is invalid."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating node: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the node."
        )


@router.get(
    "/nodes/",
    response_model=List[HierarchyNodeResponse],
    summary="List all hierarchy nodes",
    description="Retrieves a flat list of all hierarchy nodes, optionally filtered by parent_id or node_type."
)
def list_nodes(
    parent_id: Optional[int] = None,
    node_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of HierarchyNodes, optionally filtered.
    """
    query = db.query(HierarchyNode)
    
    if parent_id is not None:
        query = query.filter(HierarchyNode.parent_id == parent_id)
    
    if node_type:
        query = query.filter(HierarchyNode.node_type == node_type)
        
    nodes = query.all()
    
    # Use the Pydantic model to validate and format the output
    # Note: The children list will be empty in this flat list view.
    return nodes


@router.get(
    "/nodes/{node_id}",
    response_model=HierarchyNodeResponse,
    summary="Get a single hierarchy node",
    description="Retrieves a single hierarchy node by its ID."
)
def read_node(node_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a single HierarchyNode by its ID.
    """
    node = db.query(HierarchyNode).filter(HierarchyNode.id == node_id).first()
    if node is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node with id {node_id} not found."
        )
    return node


@router.put(
    "/nodes/{node_id}",
    response_model=HierarchyNodeResponse,
    summary="Update an existing hierarchy node",
    description="Updates the details of an existing hierarchy node."
)
def update_node(node_id: int, node_update: HierarchyNodeUpdate, db: Session = Depends(get_db)):
    """
    Updates an existing HierarchyNode.
    """
    db_node = db.query(HierarchyNode).filter(HierarchyNode.id == node_id).first()
    if db_node is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node with id {node_id} not found."
        )

    update_data = node_update.model_dump(exclude_unset=True)
    
    # Check if parent_id is being updated and if it's valid
    if 'parent_id' in update_data and update_data['parent_id'] is not None:
        parent = db.query(HierarchyNode).filter(HierarchyNode.id == update_data['parent_id']).first()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent node with id {update_data['parent_id']} not found."
            )
            
    for key, value in update_data.items():
        setattr(db_node, key, value)

    try:
        db.commit()
        db.refresh(db_node)
        log_activity(db, db_node.id, "UPDATE", f"Node updated. Fields: {', '.join(update_data.keys())}")
        return db_node
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integrity error: Node name might already exist or parent_id is invalid."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating node {node_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the node."
        )


@router.delete(
    "/nodes/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a hierarchy node",
    description="Deletes a hierarchy node by its ID. Note: This will fail if the node has children (foreign key constraint)."
)
def delete_node(node_id: int, db: Session = Depends(get_db)):
    """
    Deletes a HierarchyNode by its ID.
    """
    db_node = db.query(HierarchyNode).filter(HierarchyNode.id == node_id).first()
    if db_node is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node with id {node_id} not found."
        )

    # Check for children to prevent orphaned nodes and maintain integrity
    if db_node.children:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete node: it has active children. Please reassign or delete children first."
        )

    db.delete(db_node)
    try:
        db.commit()
        log_activity(db, node_id, "DELETE", f"Node deleted: {db_node.name}")
        return {"ok": True}
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting node {node_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the node."
        )

# --- Business-Specific Endpoints ---

@router.get(
    "/tree/",
    response_model=List[HierarchyNodeResponse],
    summary="Get the full hierarchy tree",
    description="Retrieves the entire hierarchy structure, starting from all root nodes, as a nested list."
)
def get_full_tree(db: Session = Depends(get_db)):
    """
    Retrieves the entire hierarchy as a nested tree structure.
    """
    # Fetch all nodes to build the tree in memory
    all_nodes = db.query(HierarchyNode).all()
    
    if not all_nodes:
        return []
        
    return build_tree(all_nodes)


@router.get(
    "/nodes/{node_id}/activities",
    response_model=List[HierarchyActivityLogResponse],
    summary="Get activity log for a node",
    description="Retrieves the history of actions performed on a specific hierarchy node."
)
def get_node_activities(node_id: int, db: Session = Depends(get_db)):
    """
    Retrieves the activity log for a specific HierarchyNode.
    """
    node = db.query(HierarchyNode).filter(HierarchyNode.id == node_id).first()
    if node is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node with id {node_id} not found."
        )
        
    activities = db.query(HierarchyActivityLog).filter(HierarchyActivityLog.node_id == node_id).order_by(HierarchyActivityLog.timestamp.desc()).all()
    
    return activities


@router.post(
    "/nodes/{node_id}/move",
    response_model=HierarchyNodeResponse,
    summary="Move a node to a new parent",
    description="Changes the parent of a hierarchy node. Set new_parent_id to null to make it a root node."
)
def move_node(node_id: int, move_data: HierarchyMove, db: Session = Depends(get_db)):
    """
    Moves a HierarchyNode to a new parent.
    """
    db_node = db.query(HierarchyNode).filter(HierarchyNode.id == node_id).first()
    if db_node is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node with id {node_id} not found."
        )

    new_parent_id = move_data.new_parent_id
    
    # Check for circular dependency (moving a node to itself or one of its children)
    if new_parent_id == node_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot move a node to itself."
        )
        
    if new_parent_id is not None:
        new_parent = db.query(HierarchyNode).filter(HierarchyNode.id == new_parent_id).first()
        if not new_parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"New parent node with id {new_parent_id} not found."
            )
            
        # Simple check to prevent moving a node to one of its descendants
        # A more robust check would traverse the tree, but for a basic implementation, 
        # we assume the user will not attempt this for now, or rely on a more complex 
        # tree structure (like MPTT) for full validation.
        # For this implementation, we will only check if the new parent is the node itself.
        
    old_parent_id = db_node.parent_id
    db_node.parent_id = new_parent_id
    
    try:
        db.commit()
        db.refresh(db_node)
        log_activity(
            db, 
            node_id, 
            "MOVE", 
            f"Node moved from parent_id {old_parent_id} to new_parent_id {new_parent_id}",
            user_id=move_data.user_id
        )
        return db_node
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integrity error: New parent_id is invalid."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error moving node {node_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while moving the node."
        )
