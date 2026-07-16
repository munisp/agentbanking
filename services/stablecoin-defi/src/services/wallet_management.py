from typing import Any, Dict, List, Optional, Union, Tuple

import os
import json
import logging
import sqlite3
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes
from web3 import Web3
from cryptography.fernet import Fernet
from flask import Flask, request, jsonify

import time
# Assuming blockchain_connectors.py is in the same directory
from blockchain_connectors import BlockchainConnectorManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
DB_PATH = 'wallets.db'
# In production, this key MUST be loaded securely (e.g., from AWS KMS, HashiCorp Vault)
ENCRYPTION_KEY = os.environ.get('WALLET_ENCRYPTION_KEY', Fernet.generate_key().decode())

class KeyManagementService:
        """A mock KMS for encrypting and decrypting sensitive data like private keys."""

        def __init__(self, key) -> None:
            self.cipher_suite = Fernet(key.encode())

        def encrypt(self, data: str) -> str:
            return self.cipher_suite.encrypt(data.encode()).decode()

        def decrypt(self, encrypted_data: str) -> str:
            return self.cipher_suite.decrypt(encrypted_data.encode()).decode()

class WalletStorage:
        """Manages the persistent storage of wallet information in a local database."""

        def __init__(self, db_path) -> None:
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self._create_table()

        def _create_table(self) -> None:
            cursor = self.conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS wallets (
                    user_id TEXT PRIMARY KEY,
                    address TEXT NOT NULL,
                    encrypted_pk TEXT NOT NULL,
                    hd_path TEXT NOT NULL
                )
            ''')
            self.conn.commit()

        def save_wallet(self, user_id, address, encrypted_pk, hd_path) -> bool:
            try:
                cursor = self.conn.cursor()
                cursor.execute("INSERT INTO wallets (user_id, address, encrypted_pk, hd_path) VALUES (?, ?, ?, ?)",
                               (user_id, address, encrypted_pk, hd_path))
                self.conn.commit()
                logging.info(f"Saved wallet for user: {user_id}")
                return True
            except sqlite3.IntegrityError:
                logging.error(f"Wallet for user {user_id} already exists.")
                return False

        def get_wallet(self, user_id) -> None:
            cursor = self.conn.cursor()
            cursor.execute("SELECT address, encrypted_pk, hd_path FROM wallets WHERE user_id = ?", (user_id,))
            return cursor.fetchone()

class WalletManager:
        """A comprehensive Hierarchical Deterministic (HD) wallet management service."""


        def __init__(self, storage: WalletStorage, kms: KeyManagementService) -> None:
            self.storage = storage
            self.kms = kms

        def create_master_seed(self, strength_bits: int = 256) -> str:
            """Generates a new BIP39 mnemonic phrase."""
            return Bip39SeedGenerator.FromWordsNumber(strength_bits // 32 * 3).Generate()

        def create_user_wallet(self, user_id: str, master_seed_mnemonic: str, account_index: int = 0) -> Dict[str, str]:
            """Creates a new blockchain wallet for a user from a master seed."""
            if self.storage.get_wallet(user_id):
                raise ValueError(f"User {user_id} already has a wallet.")

            # Generate seed from mnemonic
            seed_bytes = Bip39SeedGenerator(master_seed_mnemonic).Generate()

            # Create an HD wallet structure (BIP44 for Ethereum)
            # m/44'/60'/0'/0/account_index
            bip44_mst = Bip44.FromSeed(seed_bytes, Bip44Coins.ETHEREUM)
            bip44_acc = bip44_mst.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(account_index)
            address = bip44_acc.PublicKey().ToAddress()
            private_key = bip44_acc.PrivateKey().Raw().ToHex()

            # Encrypt the private key before storage
            encrypted_pk = self.kms.encrypt(private_key)
            hd_path = str(bip44_acc.ToPath())

            # Save to database
            self.storage.save_wallet(user_id, address, encrypted_pk, hd_path)

            return {
                "user_id": user_id,
                "address": address,
                "hd_path": hd_path
                # IMPORTANT: Private key is NOT returned, only the encrypted version is stored.
            }

        def get_wallet_details(self, user_id: str) -> Optional[Dict[str, str]]:
            wallet_data = self.storage.get_wallet(user_id)
            if wallet_data:
                address, _, hd_path = wallet_data
                return {"user_id": user_id, "address": address, "hd_path": hd_path}
            return None

        def get_decrypted_private_key(self, user_id: str) -> Optional[str]:
            """Securely retrieves and decrypts a user's private key."""

            wallet_data = self.storage.get_wallet(user_id)
            if wallet_data:
                _, encrypted_pk, _ = wallet_data
                return self.kms.decrypt(encrypted_pk)
            return None

        def get_multi_chain_balances(self, user_id: str, connector_manager: BlockchainConnectorManager) -> Dict[str, Any]:
            """Gets the native asset (e.g., ETH, MATIC) balance for a user across all connected chains."""

            wallet_info = self.get_wallet_details(user_id)
            if not wallet_info:
                raise ValueError(f"No wallet found for user {user_id}")

            address = wallet_info['address']
            balances = {}
            active_connections = connector_manager.get_all_connections()

            for chain_name, w3 in active_connections.items():
                try:
                    balance_wei = w3.eth.get_balance(Web3.to_checksum_address(address))
                    balance_ether = w3.from_wei(balance_wei, 'ether')
                    balances[chain_name] = {'balance': float(balance_ether)}
                except Exception as e:
                    logging.error(f"Could not fetch balance for {address} on {chain_name}: {e}")
                    balances[chain_name] = {'error': str(e)}
            
            return {"user_id": user_id, "address": address, "balances": balances}

# --- API Wrapper ---
app = Flask(__name__)
# ─── Security Hardening (CVE-2024-34069, CVE-2026-27205) ─────────────────────
import os as _os
_flask_env = _os.getenv("FLASK_ENV", _os.getenv("APP_ENV", "production")).lower()
if _flask_env != "development":
    app.config["DEBUG"] = False
    app.config["TESTING"] = False
    _os.environ["WERKZEUG_DEBUG_PIN"] = "off"
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SECRET_KEY"] = _os.getenv("FLASK_SECRET_KEY", _os.urandom(32).hex())

@app.after_request
def _add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers.pop("Server", None)
    return response
# ─────────────────────────────────────────────────────────────────────────────


# Initialize components
kms = KeyManagementService(ENCRYPTION_KEY)
wallet_storage = WalletStorage(DB_PATH)
wallet_manager = WalletManager(wallet_storage, kms)
connector_manager = BlockchainConnectorManager()

# In a real application, you would securely generate and store this once.
MASTER_SEED = wallet_manager.create_master_seed()
logging.warning(f"Generated new MASTER SEED for this session. In production, this must be securely stored and reused: {MASTER_SEED}")

@app.route('/wallet', methods=['POST'])
def create_wallet_api() -> Tuple:
        data = request.json
        if not data or 'user_id' not in data or 'account_index' not in data:
            return jsonify({'error': 'user_id and account_index are required'}), 400
        
        try:
            wallet_info = wallet_manager.create_user_wallet(data['user_id'], MASTER_SEED, data['account_index'])
            return jsonify(wallet_info), 201
        except ValueError as e:
            return jsonify({'error': str(e)}), 409 # Conflict
        except Exception as e:
            logging.error(f"Wallet creation failed: {e}")
            return jsonify({'error': 'Internal server error'}), 500

@app.route('/wallet/<user_id>', methods=['GET'])
def get_wallet_api(user_id) -> Tuple:
        wallet_info = wallet_manager.get_wallet_details(user_id)
        if wallet_info:
            return jsonify(wallet_info)
        else:
            return jsonify({'error': 'Wallet not found'}), 404

@app.route('/wallet/<user_id>/balances', methods=['GET'])
def get_balances_api(user_id) -> Tuple:
        try:
            balances = wallet_manager.get_multi_chain_balances(user_id, connector_manager)
            return jsonify(balances)
        except ValueError as e:
            return jsonify({'error': str(e)}), 404
        except Exception as e:
            logging.error(f"Balance retrieval failed: {e}")
            return jsonify({'error': 'Internal server error'}), 500

# --- Example Usage ---
if __name__ == '__main__':
        logging.info("--- Initializing Wallet Management Service ---")
        
        # 1. Create a couple of user wallets
        try:
            user1_wallet = wallet_manager.create_user_wallet("user_001", MASTER_SEED, 0)
            logging.info(f"Created Wallet 1: {user1_wallet}")
            user2_wallet = wallet_manager.create_user_wallet("user_002", MASTER_SEED, 1)
            logging.info(f"Created Wallet 2: {user2_wallet}")
        except ValueError as e:
            logging.warning(f"Wallets already exist: {e}")

        # 2. Retrieve a decrypted private key (for internal use only)
        pk = wallet_manager.get_decrypted_private_key("user_001")
        if pk:
            logging.info(f"Retrieved and decrypted PK for user_001 (first 10 chars): {pk[:10]}...")

        # 3. Get multi-chain balances for a user
        logging.info("\n--- Fetching Multi-Chain Balances for user_001 ---")
        # Note: This requires the connector manager to be connected, which it does on init.
        # For real balances, INFURA_ID/ALCHEMY_ID env vars must be set.
        balances_user1 = wallet_manager.get_multi_chain_balances("user_001", connector_manager)
        logging.info(json.dumps(balances_user1, indent=2))

        # 4. Start the API server
        logging.info("\n--- Starting Wallet Management API Server ---")
        # To test:
        # curl -X POST -H "Content-Type: application/json" -d '{"user_id": "api_user_123", "account_index": 10}' http://127.0.0.1:5004/wallet
        # curl http://127.0.0.1:5004/wallet/api_user_123
        # curl http://127.0.0.1:5004/wallet/api_user_123/balances
        app.run(host='0.0.0.0', port=5004)

