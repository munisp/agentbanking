from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from decimal import Decimal

import schemas
import service
from database import get_db

# --- Custom Exceptions to HTTP Status Codes Mapping ---
def handle_service_exceptions(func) -> None:
    """Decorator to map service exceptions to HTTP exceptions."""
    def wrapper(*args, **kwargs) -> None:
        try:
            return func(*args, **kwargs)
        except service.NotFoundException as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.detail)
        except service.ConflictException as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.detail)
        except service.VaultOperationError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.detail)
        except Exception as e:
            # Catch all other unexpected errors
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {e}")
    return wrapper

router = APIRouter(
    prefix="/v1",
    tags=["stablecoin-v2"],
)

# Dependency to get the service instance
def get_service(db: Session = Depends(get_db)) -> service.StablecoinV2Service:
    return service.StablecoinV2Service(db)

# --- User Endpoints ---
@router.post("/users", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED, summary="Create a new user")
@handle_service_exceptions
def create_user(user: schemas.UserCreate, svc: service.StablecoinV2Service = Depends(get_service)) -> None:
    return svc.create_user(user)

@router.get("/users", response_model=List[schemas.UserResponse], summary="List all users")
@handle_service_exceptions
def list_users(skip: int = 0, limit: int = 100, svc: service.StablecoinV2Service = Depends(get_service)) -> None:
    return svc.get_users(skip=skip, limit=limit)

@router.get("/users/{user_id}", response_model=schemas.UserResponse, summary="Get a user by ID")
@handle_service_exceptions
def get_user(user_id: int, svc: service.StablecoinV2Service = Depends(get_service)) -> None:
    return svc.get_user(user_id)

@router.patch("/users/{user_id}", response_model=schemas.UserResponse, summary="Update user details")
@handle_service_exceptions
def update_user(user_id: int, user_data: schemas.UserUpdate, svc: service.StablecoinV2Service = Depends(get_service)) -> None:
    return svc.update_user(user_id, user_data)

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a user")
@handle_service_exceptions
def delete_user(user_id: int, svc: service.StablecoinV2Service = Depends(get_service)) -> None:
    svc.delete_user(user_id)
    return

# --- Vault Endpoints ---
@router.post("/vaults", response_model=schemas.VaultResponse, status_code=status.HTTP_201_CREATED, summary="Create a new collateral vault")
@handle_service_exceptions
def create_vault(vault: schemas.VaultCreate, svc: service.StablecoinV2Service = Depends(get_service)) -> None:
    return svc.create_vault(vault)

@router.get("/vaults", response_model=List[schemas.VaultResponse], summary="List all vaults")
@handle_service_exceptions
def list_vaults(skip: int = 0, limit: int = 100, svc: service.StablecoinV2Service = Depends(get_service)) -> None:
    return svc.get_vaults(skip=skip, limit=limit)

@router.get("/vaults/{vault_id}", response_model=schemas.VaultResponse, summary="Get a vault by ID")
@handle_service_exceptions
def get_vault(vault_id: int, svc: service.StablecoinV2Service = Depends(get_service)) -> None:
    return svc.get_vault(vault_id)

@router.patch("/vaults/{vault_id}", response_model=schemas.VaultResponse, summary="Update vault status (e.g., close)")
@handle_service_exceptions
def update_vault(vault_id: int, vault_data: schemas.VaultUpdate, svc: service.StablecoinV2Service = Depends(get_service)) -> None:
    return svc.update_vault(vault_id, vault_data)

@router.delete("/vaults/{vault_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a vault (must have zero debt)")
@handle_service_exceptions
def delete_vault(vault_id: int, svc: service.StablecoinV2Service = Depends(get_service)) -> None:
    svc.delete_vault(vault_id)
    return

# --- Vault Operations Endpoints ---
class VaultOperation(schemas.BaseModel):
    amount: Decimal = schemas.Field(..., gt=Decimal(0), description="The amount of asset to operate with.")

@router.post("/vaults/{vault_id}/deposit", response_model=schemas.VaultResponse, summary="Deposit collateral into a vault")
@handle_service_exceptions
def deposit_collateral(vault_id: int, operation: VaultOperation, svc: service.StablecoinV2Service = Depends(get_service)) -> None:
    return svc.deposit_collateral(vault_id, operation.amount)

@router.post("/vaults/{vault_id}/withdraw", response_model=schemas.VaultResponse, summary="Withdraw collateral from a vault")
@handle_service_exceptions
def withdraw_collateral(vault_id: int, operation: VaultOperation, svc: service.StablecoinV2Service = Depends(get_service)) -> None:
    return svc.withdraw_collateral(vault_id, operation.amount)

@router.post("/vaults/{vault_id}/mint", response_model=schemas.VaultResponse, summary="Mint stablecoin from a vault")
@handle_service_exceptions
def mint_stablecoin(vault_id: int, operation: VaultOperation, svc: service.StablecoinV2Service = Depends(get_service)) -> None:
    return svc.mint_stablecoin(vault_id, operation.amount)

@router.post("/vaults/{vault_id}/burn", response_model=schemas.VaultResponse, summary="Burn stablecoin to repay debt")
@handle_service_exceptions
def burn_stablecoin(vault_id: int, operation: VaultOperation, svc: service.StablecoinV2Service = Depends(get_service)) -> None:
    return svc.burn_stablecoin(vault_id, operation.amount)

# --- Transaction Endpoints ---
@router.get("/transactions", response_model=List[schemas.TransactionResponse], summary="List all transactions")
@handle_service_exceptions
def list_transactions(skip: int = 0, limit: int = 100, svc: service.StablecoinV2Service = Depends(get_service)) -> None:
    return svc.get_transactions(skip=skip, limit=limit)

@router.get("/transactions/{transaction_id}", response_model=schemas.TransactionResponse, summary="Get a transaction by ID")
@handle_service_exceptions
def get_transaction(transaction_id: int, svc: service.StablecoinV2Service = Depends(get_service)) -> None:
    return svc.get_transaction(transaction_id)

# --- Global State Endpoint ---
@router.get("/state", response_model=schemas.GlobalStateResponse, summary="Get the global stablecoin state")
@handle_service_exceptions
def get_global_state(svc: service.StablecoinV2Service = Depends(get_service)) -> None:
    return svc.get_global_state()