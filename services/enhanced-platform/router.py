from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from service import (
    user_service, party_service, land_asset_service, agreement_service,
    NotFoundException, DuplicateEntryException, AuthenticationException
)
from schemas import (
    UserCreate, UserUpdate, UserInDB, PartyCreate, PartyUpdate, Party,
    LandAssetCreate, LandAssetUpdate, LandAsset, AgreementCreate,
    AgreementUpdate, Agreement, Token, Message
)
from auth import create_access_token, get_current_user, get_current_superuser
from models import User

# --- Authentication Router ---

auth_router = APIRouter(tags=["Authentication"])

@auth_router.post("/token", response_model=Token, summary="Authenticate and get JWT token")
async def login_for_access_token(
    email: str, password: str, db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Authenticate a user with email and password and return an access token.
    """
    user = await user_service.authenticate_user(db, email, password)
    if not user:
        raise AuthenticationException(detail="Incorrect email or password")
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@auth_router.post("/users/", response_model=UserInDB, status_code=status.HTTP_201_CREATED, summary="Create a new user")
async def create_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)) -> None:
    """
    Register a new user.
    """
    try:
        return await user_service.create_user(db, user_in)
    except DuplicateEntryException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.detail)

@auth_router.get("/users/me", response_model=UserInDB, summary="Get current user details")
async def read_users_me(current_user: User = Depends(get_current_user)) -> None:
    """
    Get the details of the currently authenticated user.
    """
    return current_user

# --- CRUD Routers ---

# Base function to handle CRUD operations and exceptions
def crud_router(service, create_schema, update_schema, response_schema, prefix: str, tags: List[str]) -> Dict[str, Any]:
    router = APIRouter(prefix=prefix, tags=tags)
    
    @router.post("/", response_model=response_schema, status_code=status.HTTP_201_CREATED, summary=f"Create a new {tags[0]}")
    async def create_item(
        item_in: create_schema,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user) # Requires authentication
    ) -> None:
        try:
            return await service.create(db, item_in)
        except (NotFoundException, DuplicateEntryException) as e:
            raise HTTPException(status_code=e.status_code, detail=e.detail)

    @router.get("/", response_model=List[response_schema], summary=f"Retrieve a list of {tags[0]}")
    async def read_items(
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ) -> None:
        return await service.get_multi(db, skip=skip, limit=limit)

    @router.get("/{item_id}", response_model=response_schema, summary=f"Retrieve a single {tags[0]} by ID")
    async def read_item(
        item_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ) -> None:
        try:
            return await service.get(db, item_id)
        except NotFoundException as e:
            raise HTTPException(status_code=e.status_code, detail=e.detail)

    @router.put("/{item_id}", response_model=response_schema, summary=f"Update an existing {tags[0]}")
    async def update_item(
        item_id: int,
        item_in: update_schema,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ) -> None:
        try:
            db_item = await service.get(db, item_id)
            return await service.update(db, db_item, item_in)
        except (NotFoundException, DuplicateEntryException) as e:
            raise HTTPException(status_code=e.status_code, detail=e.detail)

    @router.delete("/{item_id}", response_model=Message, summary=f"Delete a {tags[0]}")
    async def delete_item(
        item_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ) -> Dict[str, Any]:
        try:
            await service.remove(db, item_id)
            return {"message": f"{tags[0]} with ID {item_id} deleted successfully"}
        except NotFoundException as e:
            raise HTTPException(status_code=e.status_code, detail=e.detail)
    
    return router

# Instantiate CRUD Routers
party_router = crud_router(party_service, PartyCreate, PartyUpdate, Party, "/parties", ["Parties"])
land_asset_router = crud_router(land_asset_service, LandAssetCreate, LandAssetUpdate, LandAsset, "/land-assets", ["Land Assets"])
agreement_router = crud_router(agreement_service, AgreementCreate, AgreementUpdate, Agreement, "/agreements", ["Agreements"])

# --- Main API Router ---

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(party_router)
api_router.include_router(land_asset_router)
api_router.include_router(agreement_router)
