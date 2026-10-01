import logging
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

# --- Configuration and Setup ---

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize the router
router = APIRouter(
    prefix="/transactions",
    tags=["transactions"],
    responses={404: {"description": "Not found"}},
)

# --- Simulated Dependencies (Authentication, Rate Limiting, Service Layer) ---

class User(BaseModel):
    """A simple model for an authenticated user."""
    id: UUID
    email: str
    is_admin: bool = False

def get_current_user() -> User:
    """
    Simulates an authentication dependency.
    In a real application, this would validate a token and fetch user data.
    """
    # Production implementation for a successful authentication
    return User(id=uuid4(), email="user@example.com")

def rate_limit_dependency(user: User = Depends(get_current_user)):
    """
    Simulates a rate limiting dependency.
    In a real application, this would check a cache (e.g., Redis) for rate limits.
    """
    # Simple placeholder logic: allow all requests for now
    logger.debug(f"Rate limit check passed for user {user.id}")
    return True

# --- Pydantic Schemas for Request and Response ---

class EscrowStatus(str):
    """Enum-like class for possible escrow statuses."""
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    REFUNDED = "REFUNDED"
    CANCELLED = "CANCELLED"

class EscrowBase(BaseModel):
    """Base model for escrow data."""
    sender_id: UUID = Field(..., description="The ID of the user creating the escrow.")
    recipient_id: UUID = Field(..., description="The ID of the intended recipient.")
    amount: float = Field(..., gt=0, description="The amount of money in the escrow.")
    currency: str = Field("NGN", max_length=3, description="The currency of the escrow amount.")
    description: Optional[str] = Field(None, max_length=500, description="A brief description of the transaction.")

class EscrowCreate(EscrowBase):
    """Schema for creating a new escrow."""
    pass

class EscrowDetails(EscrowBase):
    """Full details of an escrow transaction."""
    escrow_id: UUID = Field(..., description="Unique identifier for the escrow.")
    status: EscrowStatus = Field(EscrowStatus.PENDING, description="Current status of the escrow.")
    created_at: datetime = Field(..., description="Timestamp of escrow creation.")
    updated_at: datetime = Field(..., description="Timestamp of last update.")

# --- Simulated Service Layer (In-memory storage) ---

# In-memory storage for demonstration

# ── Round-11 persistence fix ───────────────────────────────────────────────
# Process-memory dict replaced by a dict-compatible Postgres-backed store so
# business data survives restarts. Mirrors sibling-service convention:
# {ENV}_DATABASE_URL, pool_pre_ping, auto-created table (python-owned schema).
import os as _r11_os
import json as _r11_json
from datetime import datetime as _r11_dt, timezone as _r11_tz
from sqlalchemy import (
    create_engine as _r11_ce,
    Column as _r11_Col,
    String as _r11_Str,
    DateTime as _r11_DT,
    Text as _r11_Txt,
)
from sqlalchemy.orm import sessionmaker as _r11_sm, declarative_base as _r11_db

_R11Base = _r11_db()


class _R11Row(_R11Base):
    __abstract__ = True
    key = _r11_Col(_r11_Str(128), primary_key=True)
    data = _r11_Col(_r11_Txt, nullable=False)
    updated_at = _r11_Col(
        _r11_DT(timezone=True),
        default=lambda: _r11_dt.now(_r11_tz.utc),
        onupdate=lambda: _r11_dt.now(_r11_tz.utc),
    )


class _PgDictStore:
    """Dict-compatible store persisted to Postgres (replaces in-memory dict)."""

    def __init__(self, table, env, model_name=None):
        self._model_name = model_name
        self._Row = type("_R11_%s" % table, (_R11Row,), {"__tablename__": table})
        url = _r11_os.getenv(
            env, "postgresql://postgres:postgres@localhost:5432/platform"
        )
        self._engine = _r11_ce(url, pool_pre_ping=True, pool_size=5, max_overflow=5)
        _R11Base.metadata.create_all(self._engine)
        self._Session = _r11_sm(bind=self._engine, autoflush=False, autocommit=False)

    @staticmethod
    def _ser(v):
        if hasattr(v, "model_dump"):
            v = v.model_dump()
        elif hasattr(v, "dict") and callable(v.dict):
            v = v.dict()
        return _r11_json.dumps(v, default=str)

    def _deser(self, raw):
        d = _r11_json.loads(raw)
        if self._model_name:
            cls = globals().get(self._model_name)
            if cls is not None:
                return cls(**d)
        return d

    def __setitem__(self, k, v):
        s = self._Session()
        try:
            row = s.get(self._Row, str(k))
            payload = self._ser(v)
            if row is None:
                s.add(self._Row(key=str(k), data=payload))
            else:
                row.data = payload
            s.commit()
        finally:
            s.close()

    def __getitem__(self, k):
        s = self._Session()
        try:
            row = s.get(self._Row, str(k))
            if row is None:
                raise KeyError(k)
            return self._deser(row.data)
        finally:
            s.close()

    def get(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            return default

    def __delitem__(self, k):
        s = self._Session()
        try:
            row = s.get(self._Row, str(k))
            if row is None:
                raise KeyError(k)
            s.delete(row)
            s.commit()
        finally:
            s.close()

    def __contains__(self, k):
        s = self._Session()
        try:
            return s.get(self._Row, str(k)) is not None
        finally:
            s.close()

    def _all(self):
        s = self._Session()
        try:
            return s.query(self._Row).all()
        finally:
            s.close()

    def values(self):
        return [self._deser(r.data) for r in self._all()]

    def keys(self):
        return [r.key for r in self._all()]

    def items(self):
        return [(r.key, self._deser(r.data)) for r in self._all()]

    def __len__(self):
        s = self._Session()
        try:
            return s.query(self._Row).count()
        finally:
            s.close()

    def pop(self, k, default=None):
        try:
            v = self[k]
            del self[k]
            return v
        except KeyError:
            return default

    def clear(self):
        s = self._Session()
        try:
            s.query(self._Row).delete()
            s.commit()
        finally:
            s.close()

_escrows = _PgDictStore("cdp_escrows", "CDP_DATABASE_URL", model_name="EscrowDetails")

class EscrowService:
    """Simulated service layer for handling escrow logic."""

    @staticmethod
    def create_escrow(data: EscrowCreate, user: User) -> EscrowDetails:
        """Creates a new escrow transaction."""
        if user.id != data.sender_id:
            logger.warning(f"User {user.id} attempted to create escrow for another user {data.sender_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create an escrow on behalf of another user."
            )

        new_id = uuid4()
        now = datetime.now()
        escrow = EscrowDetails(
            escrow_id=new_id,
            status=EscrowStatus.PENDING,
            created_at=now,
            updated_at=now,
            **data.model_dump()
        )
        _escrows[new_id] = escrow
        logger.info(f"Escrow {new_id} created by user {user.id}")
        return escrow

    @staticmethod
    def get_escrow(escrow_id: UUID, user: User) -> EscrowDetails:
        """Retrieves details for a specific escrow."""
        escrow = _escrows.get(escrow_id)
        if not escrow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Escrow with ID {escrow_id} not found."
            )

        # Authorization check: Only sender, recipient, or admin can view
        if user.id not in [escrow.sender_id, escrow.recipient_id] and not user.is_admin:
            logger.warning(f"Unauthorized access attempt to escrow {escrow_id} by user {user.id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this escrow."
            )

        return escrow

    @staticmethod
    def claim_escrow(escrow_id: UUID, user: User) -> EscrowDetails:
        """Claims an escrow, typically by the recipient."""
        escrow = EscrowService.get_escrow(escrow_id, user) # Uses get_escrow for existence and authorization check

        # Additional authorization: Only the recipient can claim
        if user.id != escrow.recipient_id:
            logger.warning(f"User {user.id} attempted to claim escrow {escrow_id}, but is not the recipient {escrow.recipient_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the recipient can claim this escrow."
            )

        if escrow.status != EscrowStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Escrow is already in status: {escrow.status}. Only PENDING escrows can be claimed."
            )

        # Simulate the actual claim/transfer logic here
        escrow.status = EscrowStatus.CLAIMED
        escrow.updated_at = datetime.now()
        _escrows[escrow_id] = escrow
        logger.info(f"Escrow {escrow_id} claimed by recipient {user.id}")
        return escrow

    @staticmethod
    def refund_escrow(escrow_id: UUID, user: User) -> EscrowDetails:
        """Refunds an escrow, typically by the sender or an admin."""
        escrow = EscrowService.get_escrow(escrow_id, user) # Uses get_escrow for existence and authorization check

        # Additional authorization: Only the sender or admin can refund
        if user.id != escrow.sender_id and not user.is_admin:
            logger.warning(f"User {user.id} attempted to refund escrow {escrow_id}, but is neither sender nor admin.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the sender or an administrator can refund this escrow."
            )

        if escrow.status != EscrowStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Escrow is already in status: {escrow.status}. Only PENDING escrows can be refunded."
            )

        # Simulate the actual refund logic here
        escrow.status = EscrowStatus.REFUNDED
        escrow.updated_at = datetime.now()
        _escrows[escrow_id] = escrow
        logger.info(f"Escrow {escrow_id} refunded by user {user.id}")
        return escrow

# --- Router Endpoints ---

@router.post(
    "/escrow",
    response_model=EscrowDetails,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new escrow transaction",
    dependencies=[Depends(rate_limit_dependency)]
)
def create_escrow_endpoint(
    escrow_data: EscrowCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new escrow transaction between a sender and a recipient.

    - **sender_id**: The ID of the user creating the escrow (must match authenticated user).
    - **recipient_id**: The ID of the intended recipient.
    - **amount**: The amount to be held in escrow.
    - **currency**: The currency (defaults to NGN).
    - **description**: Optional description of the transaction.
    """
    logger.info(f"Received request to create escrow for recipient {escrow_data.recipient_id} by user {current_user.id}")
    try:
        return EscrowService.create_escrow(escrow_data, current_user)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"An unexpected error occurred during escrow creation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the request."
        )

@router.get(
    "/escrow/{escrow_id}",
    response_model=EscrowDetails,
    summary="Get details of a specific escrow transaction",
    dependencies=[Depends(rate_limit_dependency)]
)
def get_escrow_details_endpoint(
    escrow_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves the full details of an escrow transaction by its ID.

    - **escrow_id**: The unique identifier of the escrow.
    - **Requires Authorization**: Only the sender, recipient, or an administrator can view the details.
    """
    logger.info(f"Received request to get details for escrow {escrow_id} by user {current_user.id}")
    try:
        return EscrowService.get_escrow(escrow_id, current_user)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching escrow {escrow_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the request."
        )

@router.post(
    "/escrow/{escrow_id}/claim",
    response_model=EscrowDetails,
    summary="Claim an escrow transaction",
    dependencies=[Depends(rate_limit_dependency)]
)
def claim_escrow_endpoint(
    escrow_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """
    Allows the recipient to claim a PENDING escrow, transferring the funds.

    - **escrow_id**: The unique identifier of the escrow to claim.
    - **Requires Authorization**: Only the intended recipient can claim.
    - **Error Handling**: Fails if the escrow is not PENDING.
    """
    logger.info(f"Received request to claim escrow {escrow_id} by user {current_user.id}")
    try:
        return EscrowService.claim_escrow(escrow_id, current_user)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"An unexpected error occurred while claiming escrow {escrow_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the request."
        )

@router.post(
    "/escrow/{escrow_id}/refund",
    response_model=EscrowDetails,
    summary="Refund an escrow transaction",
    dependencies=[Depends(rate_limit_dependency)]
)
def refund_escrow_endpoint(
    escrow_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """
    Allows the sender or an administrator to refund a PENDING escrow, returning the funds to the sender.

    - **escrow_id**: The unique identifier of the escrow to refund.
    - **Requires Authorization**: Only the sender or an administrator can refund.
    - **Error Handling**: Fails if the escrow is not PENDING.
    """
    logger.info(f"Received request to refund escrow {escrow_id} by user {current_user.id}")
    try:
        return EscrowService.refund_escrow(escrow_id, current_user)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"An unexpected error occurred while refunding escrow {escrow_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the request."
        )

# Example usage (if this file were run directly):
# if __name__ == "__main__":
#     import uvicorn
#     from fastapi import FastAPI
#
#     app = FastAPI()
#     app.include_router(router)
#
#     # To run: uvicorn transactions_router:app --reload
#     # This is commented out as the agent should not run the server.
#     # uvicorn.run(app, host="0.0.0.0", port=8000)