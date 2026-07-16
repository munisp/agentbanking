import os
import time
import logging
import random
import threading
from web3 import Web3
from web3.middleware import geth_poa_middleware
from web3.providers.base import BaseProvider
from typing import List, Dict, Any, Optional

import json
from typing import Dict, List, Optional, Any
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
DEFAULT_PROVIDERS = {
    "ethereum": [
        f"https://mainnet.infura.io/v3/{os.environ.get('INFURA_ID')}",
        f"https://eth-mainnet.g.alchemy.com/v2/{os.environ.get('ALCHEMY_ETH_ID')}",
        "https://rpc.ankr.com/eth"
    ],
    "polygon": [
        "https://polygon-rpc.com",
        f"https://polygon-mainnet.g.alchemy.com/v2/{os.environ.get('ALCHEMY_POLYGON_ID')}",
        "https://rpc.ankr.com/polygon"
    ],
    "bsc": [
        "https://bsc-dataseed.binance.org/",
        "https://bsc-dataseed1.defibit.io/",
        "https://bsc-dataseed1.ninicoin.io/"
    ],
    "arbitrum": [
        "https://arb1.arbitrum.io/rpc",
        f"https://arb-mainnet.g.alchemy.com/v2/{os.environ.get('ALCHEMY_ARBITRUM_ID')}"
    ]
}

class FallbackProvider(BaseProvider):
    """A custom Web3 provider that falls back to other providers if one fails."""

    def __init__(self, providers: List[BaseProvider]) -> None:
        super().__init__()
        self.providers = providers
        self.current_provider_index = 0

    def make_request(self, method: str, params: Any) -> Dict[str, Any]:
        for i in range(len(self.providers)):
            provider_index = (self.current_provider_index + i) % len(self.providers)
            provider = self.providers[provider_index]
            try:
                response = provider.make_request(method, params)
                self.current_provider_index = provider_index
                return response
            except Exception as e:
                logging.warning(f"Provider {provider_index} failed for method {method}: {e}. Falling back...")
        raise ConnectionError("All providers failed to handle the request.")

class BlockchainConnectorManager:
    """Manages robust, fault-tolerant connections to multiple blockchains."""


    def __init__(self, provider_config: Optional[Dict[str, List[str]]] = None) -> None:
        self.provider_config = provider_config or DEFAULT_PROVIDERS
        self.connections: Dict[str, Web3] = {}
        self.connection_status: Dict[str, bool] = {}
        self._initialize_connections()

    def _initialize_connections(self) -> None:
        for chain_name in self.provider_config.keys():
            self.get_connection(chain_name)

    def get_connection(self, chain_name: str) -> Optional[Web3]:
        if chain_name in self.connections and self.is_connected(chain_name):
            return self.connections[chain_name]

        if chain_name not in self.provider_config:
            logging.error(f"Unsupported chain: {chain_name}")
            return None

        provider_urls = self.provider_config[chain_name]
        http_providers = [Web3.HTTPProvider(url) for url in provider_urls]
        fallback_provider = FallbackProvider(http_providers)

        w3 = Web3(fallback_provider)
        
        if chain_name in ["polygon", "bsc"]:
            w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        try:
            if w3.is_connected():
                self.connections[chain_name] = w3
                self.connection_status[chain_name] = True
                logging.info(f"Successfully established connection to {chain_name}.")
                return w3
            else:
                self.connection_status[chain_name] = False
                logging.error(f"Failed to establish connection to {chain_name}. All providers failed.")
                return None
        except Exception as e:
            self.connection_status[chain_name] = False
            logging.error(f"An exception occurred while connecting to {chain_name}: {e}")
            return None

    def is_connected(self, chain_name: str) -> bool:
        if chain_name not in self.connections:
            return False
        try:
            block_number = self.connections[chain_name].eth.block_number
            self.connection_status[chain_name] = True
            logging.debug(f"{chain_name} is connected. Current block: {block_number}")
            return True
        except Exception as e:
            logging.warning(f"Connection check failed for {chain_name}: {e}")
            self.connection_status[chain_name] = False
            return False

    def get_all_connections(self) -> Dict[str, Web3]:
        return {chain: conn for chain, conn in self.connections.items() if self.is_connected(chain)}

    def get_status_report(self) -> Dict[str, Any]:
        report = {}
        for chain_name in self.provider_config.keys():
            is_conn = self.is_connected(chain_name)
            report[chain_name] = {
                "status": "Connected" if is_conn else "Disconnected",
                "block_number": self.connections[chain_name].eth.block_number if is_conn else None,
                "gas_price_gwei": self.connections[chain_name].eth.gas_price / 1e9 if is_conn else None
            }
        return report

    def get_gas_price(self, chain_name: str, priority: str = "medium") -> Optional[int]:
        w3 = self.get_connection(chain_name)
        if not w3:
            return None
        
        try:
            base_price = w3.eth.gas_price
            if priority == "fast":
                return int(base_price * 1.2)
            elif priority == "slow":
                return int(base_price * 0.8)
            else: # medium
                return base_price
        except Exception as e:
            logging.error(f"Could not fetch gas price for {chain_name}: {e}")
            return None

def run_health_checks(manager: BlockchainConnectorManager, interval_seconds: int = 60) -> None:
    while True:
        logging.info("--- Running Periodic Health Checks ---")
        report = manager.get_status_report()
        logging.info(json.dumps(report, indent=2))
        time.sleep(interval_seconds)

if __name__ == '__main__':
    logging.info("--- Initializing Blockchain Connector Manager ---")
    connector_manager = BlockchainConnectorManager()

    health_check_thread = threading.Thread(target=run_health_checks, args=(connector_manager, 30), daemon=True)
    health_check_thread.start()

    time.sleep(2)

    logging.info("\n--- Getting Polygon Connection ---")
    polygon_conn = connector_manager.get_connection("polygon")
    if polygon_conn:
        logging.info(f"Polygon Block Number: {polygon_conn.eth.block_number}")

    logging.info("\n--- Fetching Gas Prices ---")
    eth_gas_fast = connector_manager.get_gas_price("ethereum", priority="fast")
    if eth_gas_fast:
        logging.info(f"Fast Ethereum Gas Price: {eth_gas_fast / 1e9:.2f} Gwei")

    logging.info("\n--- Testing Fallback Mechanism ---")
    faulty_config = {
        "ethereum": [
            "https://bad.url.that.does.not.exist",
            DEFAULT_PROVIDERS["ethereum"][0]
        ]
    }
    faulty_manager = BlockchainConnectorManager(provider_config=faulty_config)
    eth_conn_faulty = faulty_manager.get_connection("ethereum")
    if eth_conn_faulty and eth_conn_faulty.is_connected():
        logging.info("Fallback successful! Connected to Ethereum despite faulty provider.")
        logging.info(f"Current Block (via fallback): {eth_conn_faulty.eth.block_number}")

    logging.info("\n--- Final Status Report ---")
    final_report = connector_manager.get_status_report()
    logging.info(json.dumps(final_report, indent=2))

    logging.info("\nDemonstration complete. Health checks will continue in the background.")
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        logging.info("Exiting.")

