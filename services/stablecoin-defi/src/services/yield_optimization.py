import asyncio
import httpx
import logging
from typing import Dict, List, Optional

import json
import time
from typing import Dict, List, Optional, Any
import os
import sys
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
# In a real system, this would be more extensive and dynamically updated
YIELD_SOURCES_CONFIG = {
    "aave_v3": {
        "ethereum": "https://api.thegraph.com/subgraphs/name/aave/protocol-v3",
        "polygon": "https://api.thegraph.com/subgraphs/name/aave/protocol-v3-polygon"
    },
    "compound_v2": {
        "ethereum": "https://api.thegraph.com/subgraphs/name/graphprotocol/compound-v2"
    }
}

# --- GraphQL Queries ---
AAVE_V3_QUERY = """
query getReserves($pool: String) {
  reserves(where: {pool: $pool}, orderBy: totalATokenSupply, orderDirection: desc) {
    symbol
    liquidityRate # This is the supply APY in Ray (1e27)
    variableBorrowRate
    stableBorrowRate
    totalLiquidity
    totalATokenSupply
  }
}
"""


COMPOUND_V2_QUERY = """
query getMarkets {
  markets(orderBy: totalSupply, orderDirection: desc) {
    symbol
    supplyRate # Annual supply rate per block
    borrowRate
    totalBorrows
    totalSupply
  }
}
"""

# Constants for APY calculation
SECONDS_PER_YEAR = 31536000
ETH_BLOCKS_PER_YEAR = 2102400 # Approximation

class YieldOptimizer:
    """
A service to find the best yield opportunities for stablecoins across DeFi protocols."""

    def __init__(self, client: Optional[httpx.AsyncClient] = None) -> None:
        self.client = client or httpx.AsyncClient(timeout=15.0)

    async def _query_protocol(self, protocol_name: str, endpoint: str, query: str, variables: Dict) -> Optional[Dict]:
        """
Generic function to query a protocol's GraphQL endpoint."""
        try:
            response = await self.client.post(endpoint, json={"query": query, "variables": variables})
            response.raise_for_status()
            data = response.json()
            if "errors" in data:
                logging.error(f"GraphQL error from {protocol_name}: {data['errors']}")
                return None
            return data["data"]
        except Exception as e:
            logging.error(f"An unexpected error occurred with {protocol_name}: {e}")
            return None

    def _parse_aave_v3_response(self, data: Dict, stablecoins: List[str]) -> List[Dict]:
        """Parses the response from the Aave V3 subgraph and calculates APY."""

        opportunities = []
        if not data or not data.get("reserves"):
            return opportunities

        for reserve in data["reserves"]:
            symbol = reserve["symbol"]
            if symbol in stablecoins:
                try:
                    # liquidityRate is in Ray (1e27), convert to percentage APY
                    supply_apy = (float(reserve["liquidityRate"]) / 1e27) * 100
                    opportunities.append({
                        "protocol": "Aave V3",
                        "asset": symbol,
                        "supply_apy": supply_apy,
                        "total_supply_usd": float(reserve["totalATokenSupply"]) # Approximation
                    })
                except Exception as e:
                    logging.warning(f"Could not parse Aave V3 reserve for {symbol}: {e}")
        return opportunities

    def _parse_compound_v2_response(self, data: Dict, stablecoins: List[str]) -> List[Dict]:
        """Parses the response from the Compound V2 subgraph and calculates APY."""

        opportunities = []
        if not data or not data.get("markets"):
            return opportunities

        for market in data["markets"]:
            symbol = market["symbol"].replace("c", "") # cUSDC -> USDC
            if symbol in stablecoins:
                try:
                    # supplyRate is per block, convert to annual percentage APY
                    supply_apy = float(market["supplyRate"]) * ETH_BLOCKS_PER_YEAR * 100
                    opportunities.append({
                        "protocol": "Compound V2",
                        "asset": symbol,
                        "supply_apy": supply_apy,
                        "total_supply_usd": float(market["totalSupply"]) # Approximation
                    })
                except Exception as e:
                    logging.warning(f"Could not parse Compound V2 market for {symbol}: {e}")
        return opportunities

    async def find_best_yields(self, chain: str, stablecoins: List[str] = ["USDC", "USDT", "DAI"]) -> List[Dict]:
        """Finds the best yield opportunities by querying all configured protocols."""
        if chain not in ["ethereum", "polygon"]:
            raise ValueError(f"Yield farming on chain '{chain}' is not currently supported.")

        logging.info(f"Finding best yields for {stablecoins} on {chain}...\n")

        tasks = []
        protocol_parsers = {
            "aave_v3": (AAVE_V3_QUERY, self._parse_aave_v3_response),
            "compound_v2": (COMPOUND_V2_QUERY, self._parse_compound_v2_response)
        }

        for protocol_name, config in YIELD_SOURCES_CONFIG.items():
            if chain in config:
                endpoint = config[chain]
                query, _ = protocol_parsers[protocol_name]
                # Aave V3 needs the pool address, which is chain-specific. This is a simplification.
                variables = {"pool": "0x87870Bca3F3fD603653167FC5d316aa9c113eB11"} if protocol_name == "aave_v3" else {}
                tasks.append(self._query_protocol(protocol_name, endpoint, query, variables))
        
        responses = await asyncio.gather(*tasks)

        all_opportunities = []
        for i, (protocol_name, _) in enumerate(YIELD_SOURCES_CONFIG.items()):
            if chain in YIELD_SOURCES_CONFIG[protocol_name]:
                response_data = responses.pop(0)
                if response_data:
                    _, parser = protocol_parsers[protocol_name]
                    opportunities = parser(response_data, stablecoins)
                    all_opportunities.extend(opportunities)

        # Sort by highest APY
        sorted_opportunities = sorted(all_opportunities, key=lambda x: x["supply_apy"], reverse=True)
        return sorted_opportunities

# --- Example Usage ---
async def main() -> None:
    logging.info("--- Initializing Yield Optimizer ---")
    optimizer = YieldOptimizer()

    # --- Example 1: Find best yields on Ethereum ---
    logging.info("--- Finding best yields on Ethereum ---")
    ethereum_yields = await optimizer.find_best_yields("ethereum")

    if ethereum_yields:
        logging.info("Top 5 Yield Opportunities on Ethereum:")
        for opp in ethereum_yields[:5]:
            logging.info(
                f"  Protocol: {opp['protocol'].ljust(12)} | "
                f"Asset: {opp['asset'].ljust(5)} | "
                f"Supply APY: {opp['supply_apy']:.2f}% | "
                f"Total Supplied: ${opp['total_supply_usd'] / 1e6:,.0f}M"
            )
    else:
        logging.warning("Could not retrieve any yield opportunities on Ethereum.")

    # --- Example 2: Find best yields on Polygon ---
    logging.info("\n--- Finding best yields on Polygon ---")
    polygon_yields = await optimizer.find_best_yields("polygon")

    if polygon_yields:
        logging.info("Top 5 Yield Opportunities on Polygon:")
        for opp in polygon_yields[:5]:
            logging.info(
                f"  Protocol: {opp['protocol'].ljust(12)} | "
                f"Asset: {opp['asset'].ljust(5)} | "
                f"Supply APY: {opp['supply_apy']:.2f}% | "
                f"Total Supplied: ${opp['total_supply_usd'] / 1e6:,.0f}M"
            )
    else:
        logging.warning("Could not retrieve any yield opportunities on Polygon.")

    await optimizer.client.aclose()

if __name__ == "__main__":
    asyncio.run(main())

