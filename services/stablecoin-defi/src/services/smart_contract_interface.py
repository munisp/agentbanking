import json
import logging
from typing import Any, Dict, List, Optional
from web3 import Web3
from web3.contract import Contract
from web3.exceptions import ContractLogicError

from blockchain_connectors import BlockchainConnectorManager # Assuming the manager is in this file

import time
from typing import Dict, List, Optional, Any
import os
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ContractInteractionError(Exception):
    """Custom exception for smart contract interaction errors."""

    
    def __init__(self, message: str, contract_address: str = None, transaction_hash: str = None) -> None:
        self.message = message
        self.contract_address = contract_address
        self.transaction_hash = transaction_hash
        super().__init__(self.message)
    
    def __str__(self):
        error_details = [self.message]
        if self.contract_address:
            error_details.append(f"Contract: {self.contract_address}")
        if self.transaction_hash:
            error_details.append(f"Transaction: {self.transaction_hash}")
        return " | ".join(error_details)

class SmartContractInterface:
    """A generic, robust interface for interacting with any smart contract."""


    def __init__(self, chain_name: str, contract_address: str, contract_abi: List[Dict[str, Any]], connector_manager: BlockchainConnectorManager) -> None:
        self.chain_name = chain_name
        self.contract_address = Web3.to_checksum_address(contract_address)
        self.abi = contract_abi
        self.connector_manager = connector_manager
        
        self.w3: Optional[Web3] = self.connector_manager.get_connection(self.chain_name)
        if not self.w3:
            raise ConnectionError(f"Could not establish connection to {self.chain_name}")
            
        self.contract: Contract = self.w3.eth.contract(address=self.contract_address, abi=self.abi)
        logging.info(f"Initialized interface for contract at {self.contract_address} on {self.chain_name}")

    def _get_tx_options(self, from_address: str, gas_limit: Optional[int] = None, gas_price_priority: str = 'medium') -> Dict[str, Any]:
        """Constructs a dictionary of transaction options."""
        if not self.w3:
            raise ConnectionError("No active web3 connection.")

        return {
            'from': Web3.to_checksum_address(from_address),
            'chainId': self.w3.eth.chain_id,
            'gas': gas_limit, # Will be estimated if None
            'gasPrice': self.connector_manager.get_gas_price(self.chain_name, priority=gas_price_priority),
            'nonce': self.w3.eth.get_transaction_count(Web3.to_checksum_address(from_address))
        }

    def call_function(self, function_name: str, *args: Any, **kwargs: Any) -> Any:
        """Calls a read-only (view/pure) function on the smart contract."""

        logging.info(f"Calling function [32m{function_name}[0m on {self.contract_address} with args: {args}")
        try:
            func = self.contract.functions[function_name](*args)
            result = func.call(**kwargs)
            logging.info(f"Result from {function_name}: {result}")
            return result
        except Exception as e:
            logging.error(f"Error calling function {function_name}: {e}")
            raise ContractInteractionError(f"Failed to call {function_name}") from e

    def transact_function(
        self,
        function_name: str,
        from_address: str,
        private_key: str,
        *args: Any,
        gas_limit: Optional[int] = None,
        gas_price_priority: str = 'medium',
        wait_for_receipt: bool = True
    ) -> Dict[str, Any]:
        """Executes a transactional (state-changing) function on the smart contract."""
        if not self.w3:
            raise ConnectionError("No active web3 connection.")

        logging.info(f"Executing transaction [33m{function_name}[0m on {self.contract_address} from {from_address}")
        try:
            tx_options = self._get_tx_options(from_address, gas_limit, gas_price_priority)
            
            # Build the transaction
            func = self.contract.functions[function_name](*args)
            
            # Estimate gas if not provided
            if tx_options["gas"] is None:
                try:
                    estimated_gas = func.estimate_gas({"from": tx_options["from"]})
                    tx_options["gas"] = int(estimated_gas * 1.2) # Add a 20% buffer
                    logging.info(f"Estimated gas: {estimated_gas}, using: {tx_options['gas']}")
                except ContractLogicError as e:
                    logging.error(f"Gas estimation failed: {e}. The transaction will likely fail.")
                    raise ContractInteractionError("Gas estimation failed") from e

            unsigned_txn = func.build_transaction(tx_options)

            # Sign the transaction
            signed_txn = self.w3.eth.account.sign_transaction(unsigned_txn, private_key=private_key)

            # Send the transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            hex_tx_hash = tx_hash.hex()
            logging.info(f"Transaction sent with hash: {hex_tx_hash}")

            if wait_for_receipt:
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
                logging.info(f"Transaction confirmed in block: {receipt.blockNumber}")
                if receipt["status"] == 0:
                    logging.error("Transaction failed! Check transaction hash on a block explorer.")
                    raise ContractInteractionError(f"Transaction {hex_tx_hash} failed.")
                return {"tx_hash": hex_tx_hash, "receipt": dict(receipt)}
            else:
                return {"tx_hash": hex_tx_hash}

        except ContractLogicError as e:
            logging.error(f"Contract logic error for {function_name}: {e}")
            raise ContractInteractionError(f"Contract execution reverted for {function_name}") from e
        except Exception as e:
            logging.error(f"Error executing transaction {function_name}: {e}")
            raise ContractInteractionError(f"Failed to execute transaction {function_name}") from e

    def get_event_logs(self, event_name: str, from_block: int, to_block: Optional[int] = 'latest') -> List[Dict[str, Any]]:
        """Retrieves logs for a specific event within a block range."""

        logging.info(f"Fetching [34m{event_name}[0m events from block {from_block} to {to_block}")
        try:
            event_filter = self.contract.events[event_name].create_filter(fromBlock=from_block, toBlock=to_block)
            logs = event_filter.get_all_entries()
            return [dict(log) for log in logs]
        except Exception as e:
            logging.error(f"Error fetching events for {event_name}: {e}")
            raise ContractInteractionError(f"Failed to fetch events for {event_name}") from e

# --- Example Usage ---
if __name__ == "__main__":
    # This example requires a deployed contract and a private key with funds on a testnet.
    # We will use a public, verified contract on a testnet (e.g., Goerli) for demonstration.
    
    # Dummy ERC20 contract on Goerli testnet (replace with a real one if available)
    DUMMY_ERC20_ADDRESS = "0x07865c6E87B9F70255377e024ace6630C1Eaa37F" # USDC on Goerli
    with open("erc20_abi.json", "r") as f: # Assuming erc20_abi.json exists from stablecoin_gateway.py
        DUMMY_ERC20_ABI = json.load(f)

    # Set up environment for demonstration
    # You must set your own Infura ID and a private key for a Goerli account with test ETH
    os.environ["INFURA_ID"] = "YOUR_INFURA_ID" # Replace with your Infura ID
    os.environ["TEST_PRIVATE_KEY"] = "0x..." # Replace with your Goerli private key
    os.environ["TEST_ADDRESS"] = "0x..." # Replace with your Goerli address

    if os.environ.get("INFURA_ID") == "YOUR_INFURA_ID":
        logging.error("Please set your INFURA_ID environment variable to run the example.")
    else:
        # 1. Initialize the connector manager and the contract interface
        logging.info("\n--- Initializing Interface ---")
        connector = BlockchainConnectorManager({
            "goerli": [f"https://goerli.infura.io/v3/{os.environ.get('INFURA_ID')}"]
        })
        
        try:
            contract_interface = SmartContractInterface(
                chain_name="goerli",
                contract_address=DUMMY_ERC20_ADDRESS,
                contract_abi=DUMMY_ERC20_ABI,
                connector_manager=connector
            )

            # 2. Call a read-only function
            logging.info("\n--- Calling a View Function (balanceOf) ---")
            vitalik_address = "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B"
            balance_wei = contract_interface.call_function("balanceOf", vitalik_address)
            decimals = contract_interface.call_function("decimals")
            logging.info(f"Balance of {vitalik_address}: {balance_wei / (10**decimals):.6f} USDC")

            # 3. Execute a transaction (commented out unless private key is set)
            # logging.info("\n--- Executing a Transaction (transfer) ---")
            # if os.environ.get("TEST_PRIVATE_KEY") != "0x...":
            #     tx_result = contract_interface.transact_function(
            #         "transfer",
            #         from_address=os.environ["TEST_ADDRESS"],
            #         private_key=os.environ["TEST_PRIVATE_KEY"],
            #         args=["0x000000000000000000000000000000000000dEaD", 10000] # Send 0.01 USDC to dead address
            #     )
            #     logging.info(f"Transaction successful: {tx_result[\'tx_hash\']}")
            # else:
            #     logging.warning("Skipping transaction example. Please set TEST_PRIVATE_KEY.")

            # 4. Fetch event logs
            logging.info("\n--- Fetching Event Logs (Transfer) ---")
            latest_block = connector.get_connection("goerli").eth.block_number
            transfer_events = contract_interface.get_event_logs("Transfer", from_block=latest_block - 100, to_block=latest_block)
            logging.info(f"Found {len(transfer_events)} Transfer events in the last 100 blocks.")
            if transfer_events:
                logging.info(f"Example event: {transfer_events[0]}")

        except Exception as e:
            logging.error(f"An error occurred during the example run: {e}")


