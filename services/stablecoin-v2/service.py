import json
import logging
import os
import urllib.error
import urllib.request
from typing import List, Optional
from decimal import Decimal, getcontext

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

import models
import schemas

# Set precision for Decimal operations
getcontext().prec = 50

# --- Custom Exceptions ---
class NotFoundException(Exception):
    """Raised when a requested resource is not found (HTTP 404)."""
    def __init__(self, detail: str) -> None:
        self.detail = detail

class ConflictException(Exception):
    """Raised when a resource already exists or a conflict occurs (HTTP 409)."""
    def __init__(self, detail: str) -> None:
        self.detail = detail

class VaultOperationError(Exception):
    """Raised for errors specific to stablecoin/vault operations (HTTP 400/422)."""
    def __init__(self, detail: str) -> None:
        self.detail = detail

# --- Logging Setup ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- Helper Functions ---
def calculate_collateralization_ratio(
    collateral_amount: Decimal,
    stablecoin_debt: Decimal,
    collateral_price_usd: Optional[Decimal] = None
) -> float:
    """Calculates the collateralization ratio.

    A real collateral price is required: silently assuming 1 unit of collateral
    is worth 1 unit of stablecoin fabricates solvency. Callers must pass the
    oracle-derived price (the explicitly gated simulation passes Decimal(1)).
    """
    if stablecoin_debt <= Decimal(0):
        return float('inf')
    if collateral_price_usd is None:
        raise ValueError(
            "collateral_price_usd is required; refusing to assume a 1:1 collateral peg"
        )
    ratio = (collateral_amount * collateral_price_usd) / stablecoin_debt
    return float(ratio)

# --- Service Class ---
class StablecoinV2Service:
    def __init__(self, db: Session) -> None:
        self.db = db
        # Simulation of the CDP engine is only allowed when explicitly enabled
        # AND outside production. Production requires a price oracle and a
        # chain settlement gateway.
        self.simulation_mode = os.getenv("STABLECOIN_V2_SIMULATION_MODE", "false").lower() == "true"
        self.environment = os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "production")).lower()
        self.price_oracle_url = os.getenv("STABLECOIN_V2_PRICE_ORACLE_URL", "").strip() or None
        self.chain_gateway_url = os.getenv("STABLECOIN_V2_CHAIN_GATEWAY_URL", "").strip() or None
        if self.simulation_mode and self.environment == "production":
            raise RuntimeError(
                "STABLECOIN_V2_SIMULATION_MODE=true is forbidden in production: "
                "simulated mint/burn must never run against live funds"
            )

    def _get_collateral_price_usd(self, collateral_asset: str) -> Decimal:
        """Fetch the collateral price from the configured price oracle.

        Expects a CoinGecko-compatible simple/price endpoint. Raises loudly
        when no oracle is configured or the price cannot be retrieved — a 1:1
        peg is never silently assumed outside gated simulation.
        """
        if self.simulation_mode:
            # Explicitly gated, non-production test mode only.
            return Decimal(1)
        if not self.price_oracle_url:
            raise VaultOperationError(
                "No price oracle configured (STABLECOIN_V2_PRICE_ORACLE_URL is unset); "
                "refusing to assume a 1:1 collateral peg"
            )
        asset_id = collateral_asset.lower()
        url = f"{self.price_oracle_url}?ids={asset_id}&vs_currencies=usd"
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                data = json.loads(response.read().decode())
            return Decimal(str(data[asset_id]["usd"]))
        except (urllib.error.URLError, TimeoutError, KeyError, TypeError, json.JSONDecodeError) as e:
            logger.error(f"Price oracle lookup failed for {collateral_asset}: {e}")
            raise VaultOperationError(
                f"Unable to fetch collateral price for {collateral_asset} from oracle: {e}"
            )

    def _settle_onchain(self, action: str, vault_id: Optional[int], amount: Decimal, asset: str) -> Optional[str]:
        """Execute a vault action on-chain via the configured chain gateway.

        Returns the on-chain transaction hash. Raises loudly when settlement
        is unavailable — vault state is never advanced from database writes
        alone.
        """
        if self.simulation_mode:
            # Explicitly gated, non-production test mode only.
            return None
        if not self.chain_gateway_url:
            raise VaultOperationError(
                "No on-chain settlement gateway configured "
                "(STABLECOIN_V2_CHAIN_GATEWAY_URL is unset); refusing to simulate "
                f"{action} from database state alone"
            )
        payload = {
            "action": action,
            "vault_id": vault_id,
            "amount": str(amount),
            "asset": asset,
        }
        request = urllib.request.Request(
            f"{self.chain_gateway_url.rstrip('/')}/vault-operations",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            logger.error(f"Chain gateway call failed for {action} on vault {vault_id}: {e}")
            raise VaultOperationError(f"On-chain settlement failed for {action}: {e}")
        tx_hash = data.get("tx_hash")
        if not tx_hash:
            raise VaultOperationError(
                f"On-chain settlement for {action} did not return a transaction hash"
            )
        return tx_hash

    # --- User Operations ---
    def create_user(self, user_data: schemas.UserCreate) -> models.User:
        logger.info(f"Attempting to create user with address: {user_data.public_address}")
        db_user = self.db.query(models.User).filter(
            (models.User.public_address == user_data.public_address) |
            (models.User.email == user_data.email)
        ).first()
        if db_user:
            raise ConflictException(f"User with address {user_data.public_address} or email {user_data.email} already exists.")

        db_user = models.User(
            public_address=user_data.public_address,
            email=user_data.email,
            is_active=True
        )
        self.db.add(db_user)
        try:
            self.db.commit()
            self.db.refresh(db_user)
            logger.info(f"User created successfully with ID: {db_user.id}")
            return db_user
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error during user creation: {e}")
            raise ConflictException("Database integrity error during user creation.")

    def get_user(self, user_id: int) -> models.User:
        db_user = self.db.query(models.User).filter(models.User.id == user_id).first()
        if not db_user:
            raise NotFoundException(f"User with ID {user_id} not found.")
        return db_user

    def get_users(self, skip: int = 0, limit: int = 100) -> List[models.User]:
        return self.db.query(models.User).offset(skip).limit(limit).all()

    def update_user(self, user_id: int, user_data: schemas.UserUpdate) -> models.User:
        db_user = self.get_user(user_id)
        update_data = user_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_user, key, value)

        self.db.commit()
        self.db.refresh(db_user)
        logger.info(f"User with ID {user_id} updated.")
        return db_user

    def delete_user(self, user_id: int) -> None:
        db_user = self.get_user(user_id)
        self.db.delete(db_user)
        self.db.commit()
        logger.info(f"User with ID {user_id} deleted.")

    # --- Vault Operations ---
    def create_vault(self, vault_data: schemas.VaultCreate) -> models.Vault:
        logger.info(f"Attempting to create vault for user ID: {vault_data.owner_id}")
        self.get_user(vault_data.owner_id) # Check if user exists

        collateral_amount = vault_data.collateral_amount
        stablecoin_debt = vault_data.stablecoin_debt

        if collateral_amount <= Decimal(0):
            raise VaultOperationError("Collateral amount must be greater than zero.")

        # Minimum collateralization ratio (e.g., 150% or 1.5)
        MIN_RATIO = 1.5
        collateral_price = self._get_collateral_price_usd(vault_data.collateral_asset)
        ratio = calculate_collateralization_ratio(collateral_amount, stablecoin_debt, collateral_price)

        if ratio < MIN_RATIO:
            raise VaultOperationError(f"Initial collateralization ratio ({ratio:.2f}) is below the minimum required ({MIN_RATIO:.2f}).")

        # Mint on-chain first when opening with debt; never advance vault debt
        # from a database write alone.
        mint_tx_hash = None
        if stablecoin_debt > Decimal(0):
            mint_tx_hash = self._settle_onchain("MINT", None, stablecoin_debt, vault_data.collateral_asset)

        db_vault = models.Vault(
            owner_id=vault_data.owner_id,
            collateral_asset=vault_data.collateral_asset,
            collateral_amount=collateral_amount,
            stablecoin_debt=stablecoin_debt,
            collateralization_ratio=ratio,
            status=models.VaultStatus.OPEN
        )
        self.db.add(db_vault)
        self.db.commit()
        self.db.refresh(db_vault)
        logger.info(f"Vault created successfully with ID: {db_vault.id}")

        # If debt > 0, record the MINT transaction with its real tx hash
        if stablecoin_debt > Decimal(0):
            self._record_transaction(
                user_id=vault_data.owner_id,
                vault_id=db_vault.id,
                transaction_type=models.TransactionType.MINT,
                stablecoin_amount=stablecoin_debt,
                collateral_change=None,
                tx_hash=mint_tx_hash
            )
            self.db.commit()

        return db_vault

    def get_vault(self, vault_id: int) -> models.Vault:
        db_vault = self.db.query(models.Vault).filter(models.Vault.id == vault_id).first()
        if not db_vault:
            raise NotFoundException(f"Vault with ID {vault_id} not found.")
        return db_vault

    def get_vaults(self, skip: int = 0, limit: int = 100) -> List[models.Vault]:
        return self.db.query(models.Vault).offset(skip).limit(limit).all()

    def update_vault(self, vault_id: int, vault_data: schemas.VaultUpdate) -> models.Vault:
        db_vault = self.get_vault(vault_id)
        update_data = vault_data.model_dump(exclude_unset=True)

        # Only status can be updated directly without affecting collateral/debt
        if 'status' in update_data:
            db_vault.status = update_data['status']
            self.db.commit()
            self.db.refresh(db_vault)
            logger.info(f"Vault with ID {vault_id} status updated to {db_vault.status.value}.")
            return db_vault
        else:
            raise VaultOperationError("Only vault status can be updated directly via this endpoint. Use specific endpoints for collateral/debt changes.")

    def delete_vault(self, vault_id: int) -> None:
        db_vault = self.get_vault(vault_id)
        if db_vault.stablecoin_debt > Decimal(0):
            raise VaultOperationError("Cannot delete vault with outstanding debt. Must be closed first.")
        self.db.delete(db_vault)
        self.db.commit()
        logger.info(f"Vault with ID {vault_id} deleted.")

    def deposit_collateral(self, vault_id: int, amount: Decimal) -> models.Vault:
        db_vault = self.get_vault(vault_id)
        if db_vault.status != models.VaultStatus.OPEN:
            raise VaultOperationError(f"Cannot deposit collateral to a vault with status: {db_vault.status.value}")
        if amount <= Decimal(0):
            raise VaultOperationError("Deposit amount must be positive.")

        collateral_price = self._get_collateral_price_usd(db_vault.collateral_asset)

        # Lock collateral on-chain before advancing DB state.
        tx_hash = self._settle_onchain("DEPOSIT_COLLATERAL", db_vault.id, amount, db_vault.collateral_asset)

        db_vault.collateral_amount += amount
        db_vault.collateralization_ratio = calculate_collateralization_ratio(
            db_vault.collateral_amount, db_vault.stablecoin_debt, collateral_price
        )

        self.db.commit()
        self.db.refresh(db_vault)
        logger.info(f"Deposited {amount} collateral to vault ID {vault_id}.")

        self._record_transaction(
            user_id=db_vault.owner_id,
            vault_id=db_vault.id,
            transaction_type=models.TransactionType.COLLATERAL_DEPOSIT,
            stablecoin_amount=Decimal(0),
            collateral_change=amount,
            tx_hash=tx_hash
        )
        self.db.commit()
        return db_vault

    def withdraw_collateral(self, vault_id: int, amount: Decimal) -> models.Vault:
        db_vault = self.get_vault(vault_id)
        if db_vault.status != models.VaultStatus.OPEN:
            raise VaultOperationError(f"Cannot withdraw collateral from a vault with status: {db_vault.status.value}")
        if amount <= Decimal(0):
            raise VaultOperationError("Withdrawal amount must be positive.")
        if db_vault.collateral_amount < amount:
            raise VaultOperationError("Insufficient collateral in vault.")

        collateral_price = self._get_collateral_price_usd(db_vault.collateral_asset)

        new_collateral_amount = db_vault.collateral_amount - amount
        new_ratio = calculate_collateralization_ratio(new_collateral_amount, db_vault.stablecoin_debt, collateral_price)

        MIN_RATIO = 1.5
        if new_ratio < MIN_RATIO:
            raise VaultOperationError(f"Withdrawal would drop ratio to {new_ratio:.2f}, below minimum required ({MIN_RATIO:.2f}).")

        # Release collateral on-chain before advancing DB state.
        tx_hash = self._settle_onchain("WITHDRAW_COLLATERAL", db_vault.id, amount, db_vault.collateral_asset)

        db_vault.collateral_amount = new_collateral_amount
        db_vault.collateralization_ratio = new_ratio

        self.db.commit()
        self.db.refresh(db_vault)
        logger.info(f"Withdrew {amount} collateral from vault ID {vault_id}.")

        self._record_transaction(
            user_id=db_vault.owner_id,
            vault_id=db_vault.id,
            transaction_type=models.TransactionType.COLLATERAL_WITHDRAWAL,
            stablecoin_amount=Decimal(0),
            collateral_change=-amount,
            tx_hash=tx_hash
        )
        self.db.commit()
        return db_vault

    def mint_stablecoin(self, vault_id: int, amount: Decimal) -> models.Vault:
        db_vault = self.get_vault(vault_id)
        if db_vault.status != models.VaultStatus.OPEN:
            raise VaultOperationError(f"Cannot mint stablecoin from a vault with status: {db_vault.status.value}")
        if amount <= Decimal(0):
            raise VaultOperationError("Mint amount must be positive.")

        collateral_price = self._get_collateral_price_usd(db_vault.collateral_asset)

        new_debt = db_vault.stablecoin_debt + amount
        new_ratio = calculate_collateralization_ratio(db_vault.collateral_amount, new_debt, collateral_price)

        MIN_RATIO = 1.5
        if new_ratio < MIN_RATIO:
            raise VaultOperationError(f"Minting would drop ratio to {new_ratio:.2f}, below minimum required ({MIN_RATIO:.2f}).")

        # Mint on-chain before advancing DB debt.
        tx_hash = self._settle_onchain("MINT", db_vault.id, amount, db_vault.collateral_asset)

        db_vault.stablecoin_debt = new_debt
        db_vault.collateralization_ratio = new_ratio

        self.db.commit()
        self.db.refresh(db_vault)
        logger.info(f"Minted {amount} stablecoin from vault ID {vault_id}.")

        self._record_transaction(
            user_id=db_vault.owner_id,
            vault_id=db_vault.id,
            transaction_type=models.TransactionType.MINT,
            stablecoin_amount=amount,
            collateral_change=None,
            tx_hash=tx_hash
        )
        self.db.commit()
        return db_vault

    def burn_stablecoin(self, vault_id: int, amount: Decimal) -> models.Vault:
        db_vault = self.get_vault(vault_id)
        if db_vault.status != models.VaultStatus.OPEN:
            raise VaultOperationError(f"Cannot burn stablecoin to a vault with status: {db_vault.status.value}")
        if amount <= Decimal(0):
            raise VaultOperationError("Burn amount must be positive.")
        if db_vault.stablecoin_debt < amount:
            raise VaultOperationError("Burn amount exceeds outstanding debt.")

        collateral_price = self._get_collateral_price_usd(db_vault.collateral_asset)

        # Burn on-chain before reducing DB debt.
        tx_hash = self._settle_onchain("BURN", db_vault.id, amount, db_vault.collateral_asset)

        db_vault.stablecoin_debt -= amount
        db_vault.collateralization_ratio = calculate_collateralization_ratio(
            db_vault.collateral_amount, db_vault.stablecoin_debt, collateral_price
        )

        self.db.commit()
        self.db.refresh(db_vault)
        logger.info(f"Burned {amount} stablecoin to vault ID {vault_id}.")

        self._record_transaction(
            user_id=db_vault.owner_id,
            vault_id=db_vault.id,
            transaction_type=models.TransactionType.BURN,
            stablecoin_amount=-amount, # Negative for debt reduction
            collateral_change=None,
            tx_hash=tx_hash
        )
        self.db.commit()
        return db_vault

    # --- Transaction Operations ---
    def _record_transaction(self, user_id: int, transaction_type: models.TransactionType, stablecoin_amount: Decimal, vault_id: Optional[int] = None, collateral_change: Optional[Decimal] = None, tx_hash: Optional[str] = None) -> models.Transaction:
        """Internal method to record a transaction."""
        db_transaction = models.Transaction(
            user_id=user_id,
            vault_id=vault_id,
            transaction_type=transaction_type,
            stablecoin_amount=stablecoin_amount,
            collateral_change=collateral_change,
            tx_hash=tx_hash
        )
        self.db.add(db_transaction)
        # Note: commit is handled by the calling function (e.g., create_vault, deposit_collateral)
        # to ensure atomicity of the main operation and the transaction record.
        self.db.flush()
        self.db.refresh(db_transaction)
        return db_transaction

    def get_transaction(self, transaction_id: int) -> models.Transaction:
        db_transaction = self.db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
        if not db_transaction:
            raise NotFoundException(f"Transaction with ID {transaction_id} not found.")
        return db_transaction

    def get_transactions(self, skip: int = 0, limit: int = 100) -> List[models.Transaction]:
        return self.db.query(models.Transaction).offset(skip).limit(limit).all()

    # --- Global State Operations ---
    def get_global_state(self) -> models.GlobalState:
        db_state = self.db.query(models.GlobalState).filter(models.GlobalState.id == 1).first()
        if not db_state:
            # Initialize if it doesn't exist
            db_state = models.GlobalState(id=1)
            self.db.add(db_state)
            self.db.commit()
            self.db.refresh(db_state)
        return db_state

    def update_global_state(self, total_supply_change: Decimal, total_collateral_change: Decimal) -> None:
        """Updates the global state atomically."""
        db_state = self.get_global_state()
        db_state.total_stablecoin_supply += total_supply_change
        db_state.total_collateral_value += total_collateral_change
        self.db.commit()
        self.db.refresh(db_state)
        logger.info("Global state updated.")
        return db_state
