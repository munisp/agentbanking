import asyncio
import httpx
import logging
from typing import Dict, List, Optional, Tuple

import json
import time
from typing import Dict, List, Optional, Any
import os
import sys
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
# In a real system, this would be dynamically configurable and more extensive
DEX_CONFIG = {
    "ethereum": {
        "uniswap_v3": "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3",
        "sushiswap": "https://api.thegraph.com/subgraphs/name/sushiswap/exchange"
    },
    "polygon": {
        "quickswap": "https://api.thegraph.com/subgraphs/name/quickswap/exchange-v2"
    }
}

# --- GraphQL Queries ---
# These queries are simplified for demonstration
UNISWAP_V3_QUERY = """
query getPools($token0: String!, $token1: String!) {
  pools(where: {token0: $token0, token1: $token1}, orderBy: totalValueLockedUSD, orderDirection: desc) {
    id
    token0Price
    token1Price
    totalValueLockedToken0
    totalValueLockedToken1
  }
}
"""


SUSHISWAP_QUERY = """
query getPairs($token0: String!, $token1: String!) {
  pairs(where: {token0: $token0, token1: $token1}, orderBy: reserveUSD, orderDirection: desc) {
    id
    token0Price
    token1Price
    reserve0
    reserve1
  }
}
"""


class LiquidityAggregator:
    """A service to find the best swap prices across multiple decentralized exchanges (DEXs)."""

    def __init__(self, client: Optional[httpx.AsyncClient] = None) -> None:
        self.client = client or httpx.AsyncClient(timeout=10.0)

    async def _query_dex(self, dex_name: str, endpoint: str, query: str, variables: Dict) -> Optional[Dict]:
        """Generic function to query a DEX's GraphQL endpoint."""
        try:
            response = await self.client.post(endpoint, json={"query": query, "variables": variables})
            response.raise_for_status()
            data = response.json()
            if "errors" in data:
                logging.error(f"GraphQL error from {dex_name}: {data['errors']}")
                return None
            return data["data"]
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error querying {dex_name}: {e}")
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred with {dex_name}: {e}")
            return None

    def _parse_uniswap_v3_response(self, data: Dict, amount_in: float) -> Optional[Tuple[str, float]]:
        """Parses the response from the Uniswap V3 subgraph."""
        if not data or not data.get("pools"):
            return None
        
        best_pool = data["pools"][0] # Simplification: assuming the first (highest TVL) is best
        price = float(best_pool["token1Price"])
        liquidity = float(best_pool["totalValueLockedToken1"])
        
        # Very basic slippage simulation
        if amount_in > liquidity * 0.01: # If trade is >1% of pool liquidity
            logging.warning("High slippage likely on Uniswap V3 for this trade size.")
            price *= 0.99 # Apply a 1% slippage penalty

        return "uniswap_v3", amount_in * price

    def _parse_sushiswap_response(self, data: Dict, amount_in: float) -> Optional[Tuple[str, float]]:
        """Parses the response from the Sushiswap subgraph."""
        if not data or not data.get("pairs"):
            return None

        best_pair = data["pairs"][0]
        price = float(best_pair["token1Price"])
        liquidity = float(best_pair["reserve1"])

        if amount_in > liquidity * 0.01:
            logging.warning("High slippage likely on Sushiswap for this trade size.")
            price *= 0.99

        return "sushiswap", amount_in * price

    async def find_best_swap(self, chain: str, from_token_address: str, to_token_address: str, amount_in: float) -> Optional[Dict]:
        """Finds the best swap rate by querying all configured DEXs on a given chain."""
        if chain not in DEX_CONFIG:
            raise ValueError(f"Chain '{chain}' is not supported.")

        logging.info(f"Finding best swap for {amount_in} of {from_token_address} to {to_token_address} on {chain}...")

        tasks = []
        dex_parsers = {
            "uniswap_v3": (UNISWAP_V3_QUERY, self._parse_uniswap_v3_response),
            "sushiswap": (SUSHISWAP_QUERY, self._parse_sushiswap_response),
            "quickswap": (SUSHISWAP_QUERY, self._parse_sushiswap_response) # QuickSwap is a fork
        }

        for dex_name, endpoint in DEX_CONFIG[chain].items():
            if dex_name in dex_parsers:
                query, _ = dex_parsers[dex_name]
                variables = {"token0": from_token_address.lower(), "token1": to_token_address.lower()}
                tasks.append(self._query_dex(dex_name, endpoint, query, variables))
        
        responses = await asyncio.gather(*tasks)

        best_rate = -1.0
        best_dex = None
        all_quotes = []

        for i, (dex_name, _) in enumerate(DEX_CONFIG[chain].items()):
            response_data = responses[i]
            if response_data:
                _, parser = dex_parsers[dex_name]
                quote = parser(response_data, amount_in)
                if quote:
                    dex, amount_out = quote
                    all_quotes.append({"dex": dex, "amount_out": amount_out})
                    if amount_out > best_rate:
                        best_rate = amount_out
                        best_dex = dex

        if best_dex:
            return {
                "best_dex": best_dex,
                "amount_in": amount_in,
                "amount_out": best_rate,
                "all_quotes": all_quotes
            }
        else:
            logging.warning("Could not find any liquidity for the requested pair.")
            return None

# --- Example Usage ---
async def main() -> None:
    logging.info("--- Initializing Liquidity Aggregator ---")
    aggregator = LiquidityAggregator()

    # --- Example 1: WETH to USDC on Ethereum ---
    # Token addresses must be checksummed or lowercase for TheGraph
    weth_address = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
    usdc_address = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    amount_to_swap = 10.0 # Swapping 10 WETH

    logging.info(f"\n--- Finding best price for {amount_to_swap} WETH to USDC on Ethereum ---")
    best_swap = await aggregator.find_best_swap("ethereum", weth_address, usdc_address, amount_to_swap)

    if best_swap:
        logging.info(f"Best DEX: {best_swap['best_dex']}")
        logging.info(f"Input: {best_swap['amount_in']} WETH")
        logging.info(f"Estimated Output: {best_swap['amount_out']:.2f} USDC")
        logging.info(f"All available quotes: {best_swap['all_quotes']}")
    
    # --- Example 2: No Liquidity ---
    logging.info(f"\n--- Testing a pair with no liquidity ---")
    no_liquidity_swap = await aggregator.find_best_swap("ethereum", weth_address, "0x0000000000000000000000000000000000000000", 1.0)
    if not no_liquidity_swap:
        logging.info("Correctly handled no liquidity case.")

    # --- Example 3: Polygon Swap (WMATIC to USDC) ---
    wmatic_address = "0x0d500b1d8e8ef31e21c99d1db9a6444d3adf1270"
    usdc_poly_address = "0x2791bca1f2de4661ed88a30c99a7a9449aa84174"
    amount_matic = 1000.0

    logging.info(f"\n--- Finding best price for {amount_matic} WMATIC to USDC on Polygon ---")
    poly_swap = await aggregator.find_best_swap("polygon", wmatic_address, usdc_poly_address, amount_matic)
    if poly_swap:
        best_dex = poly_swap['best_dex']
        logging.info(f"Best DEX on Polygon: {best_dex}")
        amount_out = poly_swap['amount_out']
        logging.info(f"Estimated Output: {amount_out:.2f} USDC")

    await aggregator.client.aclose()

if __name__ == "__main__":
    asyncio.run(main())

