"""
Nigerian Financial Synthetic Data Generator

Generates realistic synthetic datasets for:
- Transaction fraud detection (agent POS, transfers, mobile money)
- Credit scoring (informal sector, agent lending)
- Agent behavior analysis (float management, commission patterns)
- Network/graph features (transaction networks, agent clusters)

Data reflects Nigerian fintech reality:
- Naira denominations and typical transaction sizes
- Nigerian bank codes (CBN-registered banks)
- Agent network patterns (rural vs urban, float cycles)
- Fraud typologies common in West Africa (SIM swap, agent collusion, identity fraud)
- Time patterns (salary days, market days, religious calendar effects)
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Tuple, Dict, List, Optional
from dataclasses import dataclass
import hashlib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Nigerian-specific constants
NIGERIAN_BANKS = [
    "ACCESS", "GTB", "ZENITH", "UBA", "FIRST_BANK", "FCMB", "STANBIC",
    "FIDELITY", "UNION", "STERLING", "POLARIS", "WEMA", "KEYSTONE",
    "ECOBANK", "HERITAGE", "JAIZ", "OPAY", "PALMPAY", "MONIEPOINT", "KUDA"
]

NIGERIAN_STATES = [
    "Lagos", "Kano", "Rivers", "Oyo", "Abuja", "Kaduna", "Ogun",
    "Anambra", "Delta", "Enugu", "Imo", "Borno", "Bauchi",
    "Plateau", "Kwara", "Niger", "Osun", "Ondo", "Ekiti",
    "Cross River", "Edo", "Abia", "Benue", "Nasarawa", "Kogi",
    "Taraba", "Adamawa", "Sokoto", "Zamfara", "Kebbi", "Jigawa",
    "Yobe", "Gombe", "Bayelsa", "Ebonyi", "Akwa Ibom"
]

TRANSACTION_TYPES = [
    "cash_in", "cash_out", "transfer", "bill_payment", "airtime",
    "merchant_payment", "loan_disbursement", "loan_repayment",
    "float_top_up", "commission_withdrawal", "savings_deposit",
    "qr_payment", "pos_purchase", "agent_to_agent"
]

MERCHANT_CATEGORIES = [
    "grocery", "fuel_station", "pharmacy", "restaurant", "electronics",
    "clothing", "transport", "school_fees", "hospital", "market_stall",
    "betting", "religious", "rent", "utilities", "agriculture"
]

FRAUD_TYPES = [
    "sim_swap", "agent_collusion", "identity_theft", "float_manipulation",
    "transaction_splitting", "ghost_agent", "money_laundering",
    "card_cloning", "social_engineering", "account_takeover",
    "synthetic_identity", "commission_fraud"
]


@dataclass
class DataConfig:
    """Configuration for synthetic data generation"""
    n_customers: int = 100_000
    n_agents: int = 5_000
    n_transactions: int = 1_000_000
    n_days: int = 365
    fraud_rate: float = 0.025  # 2.5% fraud rate (realistic for Nigerian fintech)
    start_date: str = "2023-01-01"
    seed: int = 42


class NigerianTransactionGenerator:
    """Generates realistic Nigerian financial transaction data"""

    def __init__(self, config: DataConfig = None):
        self.config = config or DataConfig()
        np.random.seed(self.config.seed)
        self.start_date = datetime.strptime(self.config.start_date, "%Y-%m-%d")

    def generate_customers(self) -> pd.DataFrame:
        """Generate customer profiles with Nigerian demographics"""
        n = self.config.n_customers
        logger.info(f"Generating {n} customer profiles...")

        # Age distribution skewed young (Nigeria median age ~18)
        ages = np.random.lognormal(mean=3.3, sigma=0.4, size=n).clip(18, 75).astype(int)

        # Income distribution (NGN) - heavy right tail
        # Minimum wage ~30K NGN, median ~80K, high earners 500K+
        incomes = np.random.lognormal(mean=11.2, sigma=0.9, size=n).clip(30_000, 5_000_000)

        # KYC levels (most users are basic KYC in Nigeria)
        kyc_levels = np.random.choice(
            ["none", "basic", "enhanced", "full"],
            size=n, p=[0.05, 0.55, 0.30, 0.10]
        )

        # Account age (days) - exponential, most accounts are new
        account_ages = np.random.exponential(scale=180, size=n).clip(1, 1095).astype(int)

        # Urban vs rural
        is_urban = np.random.binomial(1, 0.52, n)  # 52% urbanization rate

        # State distribution (weighted by population)
        state_weights = np.random.dirichlet(np.ones(len(NIGERIAN_STATES)) * 2)
        # Boost Lagos, Kano, Rivers
        state_weights[0] *= 3  # Lagos
        state_weights[1] *= 2  # Kano
        state_weights[2] *= 1.5  # Rivers
        state_weights /= state_weights.sum()
        states = np.random.choice(NIGERIAN_STATES, size=n, p=state_weights)

        # Device types
        devices = np.random.choice(
            ["android_low", "android_mid", "android_high", "ios", "feature_phone", "ussd"],
            size=n, p=[0.30, 0.25, 0.10, 0.08, 0.15, 0.12]
        )

        # BVN verification status
        has_bvn = np.random.binomial(1, 0.75, n)

        # NIN verification status
        has_nin = np.random.binomial(1, 0.60, n)

        # Transaction frequency per month
        tx_frequency = np.random.lognormal(mean=2.0, sigma=1.0, size=n).clip(1, 200).astype(int)

        customers = pd.DataFrame({
            "customer_id": [f"CUST_{i:06d}" for i in range(n)],
            "age": ages,
            "monthly_income_ngn": incomes.astype(int),
            "kyc_level": kyc_levels,
            "account_age_days": account_ages,
            "is_urban": is_urban,
            "state": states,
            "device_type": devices,
            "has_bvn": has_bvn,
            "has_nin": has_nin,
            "monthly_tx_frequency": tx_frequency,
            "primary_bank": np.random.choice(NIGERIAN_BANKS, size=n),
            "has_savings_goal": np.random.binomial(1, 0.35, n),
            "has_loan": np.random.binomial(1, 0.15, n),
            "risk_tier": np.random.choice(["low", "medium", "high"], size=n, p=[0.70, 0.22, 0.08]),
        })

        logger.info(f"Generated {n} customers across {len(NIGERIAN_STATES)} states")
        return customers

    def generate_agents(self) -> pd.DataFrame:
        """Generate agent profiles with realistic Nigerian agent network data"""
        n = self.config.n_agents
        logger.info(f"Generating {n} agent profiles...")

        # Agent tiers
        tiers = np.random.choice(
            ["basic", "standard", "premium", "super_agent"],
            size=n, p=[0.40, 0.35, 0.20, 0.05]
        )

        # Daily transaction volume based on tier
        daily_volumes = np.where(
            tiers == "basic", np.random.lognormal(3.0, 0.5, n),
            np.where(tiers == "standard", np.random.lognormal(3.5, 0.5, n),
            np.where(tiers == "premium", np.random.lognormal(4.0, 0.5, n),
                     np.random.lognormal(4.5, 0.5, n)))
        ).clip(5, 500).astype(int)

        # Float balance (NGN)
        float_balances = np.where(
            tiers == "basic", np.random.lognormal(11, 0.5, n),
            np.where(tiers == "standard", np.random.lognormal(12, 0.5, n),
            np.where(tiers == "premium", np.random.lognormal(13, 0.5, n),
                     np.random.lognormal(14, 0.5, n)))
        ).clip(10_000, 50_000_000).astype(int)

        # Commission rate
        commission_rates = np.where(
            tiers == "basic", np.random.uniform(0.003, 0.005, n),
            np.where(tiers == "standard", np.random.uniform(0.004, 0.007, n),
            np.where(tiers == "premium", np.random.uniform(0.005, 0.008, n),
                     np.random.uniform(0.006, 0.010, n)))
        )

        agents = pd.DataFrame({
            "agent_id": [f"AGT_{i:05d}" for i in range(n)],
            "tier": tiers,
            "state": np.random.choice(NIGERIAN_STATES, size=n),
            "is_urban": np.random.binomial(1, 0.65, n),
            "daily_tx_volume": daily_volumes,
            "float_balance_ngn": float_balances,
            "commission_rate": commission_rates,
            "months_active": np.random.exponential(scale=12, size=n).clip(1, 60).astype(int),
            "pos_terminal": np.random.binomial(1, 0.70, n),
            "has_storefront": np.random.binomial(1, 0.25, n),
            "network_provider": np.random.choice(["MTN", "GLO", "AIRTEL", "9MOBILE"], size=n, p=[0.45, 0.20, 0.25, 0.10]),
            "float_top_up_frequency_daily": np.random.poisson(lam=2, size=n).clip(0, 10),
            "dispute_rate": np.random.beta(1, 50, n),
            "churn_risk": np.random.beta(2, 10, n),
        })

        logger.info(f"Generated {n} agents")
        return agents

    def generate_transactions(self, customers: pd.DataFrame, agents: pd.DataFrame) -> pd.DataFrame:
        """Generate realistic transaction data with Nigerian patterns"""
        n = self.config.n_transactions
        logger.info(f"Generating {n} transactions...")

        # Time distribution - peaks at salary days (25-28th), market days, morning/evening
        days_offset = np.random.exponential(scale=self.config.n_days / 3, size=n).clip(0, self.config.n_days - 1).astype(int)
        hours = self._generate_time_distribution(n)
        timestamps = [
            self.start_date + timedelta(days=int(d), hours=int(h), minutes=np.random.randint(0, 60))
            for d, h in zip(days_offset, hours)
        ]

        # Transaction types (weighted by Nigerian usage patterns)
        tx_types = np.random.choice(TRANSACTION_TYPES, size=n, p=[
            0.18,  # cash_in
            0.20,  # cash_out (most common)
            0.15,  # transfer
            0.12,  # bill_payment
            0.10,  # airtime
            0.08,  # merchant_payment
            0.03,  # loan_disbursement
            0.03,  # loan_repayment
            0.04,  # float_top_up
            0.02,  # commission_withdrawal
            0.02,  # savings_deposit
            0.01,  # qr_payment
            0.01,  # pos_purchase
            0.01,  # agent_to_agent
        ])

        # Amounts based on transaction type (NGN)
        amounts = self._generate_amounts(tx_types, n)

        # Assign customers and agents
        customer_ids = np.random.choice(customers["customer_id"].values, size=n)
        agent_ids = np.random.choice(agents["agent_id"].values, size=n)

        # Channel
        channels = np.random.choice(
            ["pos", "mobile_app", "ussd", "web", "agent_app"],
            size=n, p=[0.30, 0.35, 0.15, 0.10, 0.10]
        )

        # Status
        statuses = np.random.choice(
            ["successful", "failed", "pending", "reversed"],
            size=n, p=[0.92, 0.05, 0.02, 0.01]
        )

        # Generate fraud labels
        is_fraud, fraud_types = self._generate_fraud_labels(
            n, tx_types, amounts, customer_ids, customers, agents, agent_ids
        )

        transactions = pd.DataFrame({
            "transaction_id": [f"TXN_{i:08d}" for i in range(n)],
            "timestamp": timestamps,
            "customer_id": customer_ids,
            "agent_id": agent_ids,
            "transaction_type": tx_types,
            "amount_ngn": amounts.astype(int),
            "channel": channels,
            "status": statuses,
            "is_fraud": is_fraud,
            "fraud_type": fraud_types,
            "merchant_category": np.random.choice(MERCHANT_CATEGORIES, size=n),
            "destination_bank": np.random.choice(NIGERIAN_BANKS, size=n),
            "source_bank": np.random.choice(NIGERIAN_BANKS, size=n),
            "fee_ngn": (amounts * np.random.uniform(0.005, 0.015, n)).astype(int),
            "device_fingerprint": [hashlib.md5(f"dev_{i}".encode()).hexdigest()[:16] for i in np.random.randint(0, 50000, n)],
            "ip_risk_score": np.random.beta(2, 10, n),
            "session_duration_sec": np.random.exponential(scale=120, size=n).clip(5, 1800).astype(int),
            "is_first_transaction": np.random.binomial(1, 0.03, n),
            "distance_from_usual_km": np.random.exponential(scale=5, size=n).clip(0, 500),
        })

        logger.info(f"Generated {n} transactions, fraud rate: {is_fraud.mean():.4f}")
        return transactions

    def _generate_time_distribution(self, n: int) -> np.ndarray:
        """Nigerian transaction time patterns - peaks at 8-10am, 12-2pm, 5-7pm"""
        # Mixture of gaussians for Nigerian business hours
        component = np.random.choice([0, 1, 2, 3], size=n, p=[0.25, 0.30, 0.30, 0.15])
        hours = np.where(
            component == 0, np.random.normal(9, 1.5, n),    # Morning peak
            np.where(component == 1, np.random.normal(13, 1.5, n),  # Afternoon
            np.where(component == 2, np.random.normal(17, 1.5, n),  # Evening peak
                     np.random.normal(21, 2, n)))                   # Night
        ).clip(0, 23).astype(int)
        return hours

    def _generate_amounts(self, tx_types: np.ndarray, n: int) -> np.ndarray:
        """Generate realistic Naira amounts per transaction type"""
        amounts = np.zeros(n)

        type_params = {
            "cash_in": (10.5, 1.0),      # median ~36K NGN
            "cash_out": (10.2, 1.2),     # median ~27K NGN
            "transfer": (10.0, 1.5),     # median ~22K NGN
            "bill_payment": (9.5, 0.8),  # median ~13K NGN
            "airtime": (7.5, 1.0),       # median ~1.8K NGN
            "merchant_payment": (9.0, 1.2),  # median ~8K NGN
            "loan_disbursement": (11.5, 0.8),  # median ~100K NGN
            "loan_repayment": (10.0, 0.6),   # median ~22K NGN
            "float_top_up": (12.0, 1.0),    # median ~160K NGN
            "commission_withdrawal": (9.0, 0.8),  # median ~8K NGN
            "savings_deposit": (9.5, 1.0),  # median ~13K NGN
            "qr_payment": (8.5, 1.0),     # median ~5K NGN
            "pos_purchase": (9.0, 1.0),   # median ~8K NGN
            "agent_to_agent": (12.5, 0.8),  # median ~270K NGN
        }

        for tx_type, (mu, sigma) in type_params.items():
            mask = tx_types == tx_type
            count = mask.sum()
            if count > 0:
                amounts[mask] = np.random.lognormal(mean=mu, sigma=sigma, size=count)

        # Clip to CBN limits
        amounts = amounts.clip(50, 10_000_000)  # Min 50 NGN, max 10M NGN
        return amounts

    def _generate_fraud_labels(
        self, n: int, tx_types: np.ndarray, amounts: np.ndarray,
        customer_ids: np.ndarray, customers: pd.DataFrame,
        agents: pd.DataFrame, agent_ids: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Generate realistic fraud labels based on Nigerian fraud patterns"""
        is_fraud = np.zeros(n, dtype=int)
        fraud_types = np.array(["none"] * n, dtype=object)

        # Base fraud probability per transaction
        fraud_prob = np.full(n, self.config.fraud_rate)

        # Higher fraud risk factors:
        # 1. Large amounts (>500K NGN)
        fraud_prob[amounts > 500_000] *= 3.0
        # 2. Night transactions (unusual hours)
        # Already encoded in time patterns
        # 3. New accounts (first 30 days)
        customer_df = customers.set_index("customer_id")
        for i, cid in enumerate(customer_ids):
            if cid in customer_df.index:
                row = customer_df.loc[cid]
                if row["account_age_days"] < 30:
                    fraud_prob[i] *= 2.5
                if row["kyc_level"] == "none":
                    fraud_prob[i] *= 4.0
                if row["risk_tier"] == "high":
                    fraud_prob[i] *= 3.0
            if i >= 10000:  # Only check first 10K for performance
                break

        # 4. Agent-to-agent transfers (money laundering risk)
        fraud_prob[tx_types == "agent_to_agent"] *= 5.0
        # 5. Cash-out immediately after cash-in (structuring)
        fraud_prob[tx_types == "cash_out"] *= 1.5

        # Cap probability
        fraud_prob = fraud_prob.clip(0, 0.15)

        # Generate fraud labels
        is_fraud = np.random.binomial(1, fraud_prob)

        # Assign fraud types to fraudulent transactions
        fraud_mask = is_fraud == 1
        n_fraud = fraud_mask.sum()
        if n_fraud > 0:
            fraud_types[fraud_mask] = np.random.choice(
                FRAUD_TYPES, size=n_fraud, p=[
                    0.12,  # sim_swap
                    0.15,  # agent_collusion
                    0.12,  # identity_theft
                    0.10,  # float_manipulation
                    0.10,  # transaction_splitting
                    0.08,  # ghost_agent
                    0.10,  # money_laundering
                    0.05,  # card_cloning
                    0.08,  # social_engineering
                    0.05,  # account_takeover
                    0.03,  # synthetic_identity
                    0.02,  # commission_fraud
                ]
            )

        logger.info(f"Fraud distribution: {n_fraud}/{n} = {n_fraud/n:.4f}")
        return is_fraud, fraud_types

    def generate_credit_data(self, customers: pd.DataFrame, transactions: pd.DataFrame) -> pd.DataFrame:
        """Generate credit scoring features from customer and transaction data"""
        n = len(customers)
        logger.info(f"Generating credit features for {n} customers...")

        # Aggregate transaction features per customer
        tx_agg = transactions.groupby("customer_id").agg(
            total_transactions=("transaction_id", "count"),
            total_amount=("amount_ngn", "sum"),
            avg_amount=("amount_ngn", "mean"),
            max_amount=("amount_ngn", "max"),
            fraud_count=("is_fraud", "sum"),
            unique_agents=("agent_id", "nunique"),
            unique_types=("transaction_type", "nunique"),
        ).reset_index()

        credit_df = customers.merge(tx_agg, on="customer_id", how="left").fillna(0)

        # Generate credit scores (300-850) based on features
        base_score = 500 + np.zeros(n)

        # Positive factors
        base_score += credit_df["account_age_days"].values * 0.1  # Longer history = better
        base_score += np.where(credit_df["has_bvn"].values == 1, 50, 0)
        base_score += np.where(credit_df["has_nin"].values == 1, 30, 0)
        base_score += np.where(credit_df["kyc_level"].values == "full", 40, 0)
        base_score += np.log1p(credit_df["total_transactions"].values) * 10
        base_score += np.where(credit_df["is_urban"].values == 1, 10, 0)

        # Negative factors
        base_score -= credit_df["fraud_count"].values * 100
        base_score -= np.where(credit_df["risk_tier"].values == "high", 80, 0)
        base_score -= np.where(credit_df["kyc_level"].values == "none", 60, 0)

        # Add noise
        base_score += np.random.normal(0, 30, n)

        # Clip to valid range
        credit_scores = base_score.clip(300, 850).astype(int)

        # Default probability (inversely correlated with score)
        default_prob = 1.0 / (1.0 + np.exp((credit_scores - 550) / 80))
        default_prob += np.random.normal(0, 0.05, n)
        default_prob = default_prob.clip(0.01, 0.95)

        # Is defaulted (binary label)
        is_defaulted = np.random.binomial(1, default_prob)

        credit_df["credit_score"] = credit_scores
        credit_df["default_probability"] = default_prob
        credit_df["is_defaulted"] = is_defaulted
        credit_df["debt_to_income"] = np.random.beta(2, 5, n)
        credit_df["num_active_loans"] = np.random.poisson(0.5, n).clip(0, 5)
        credit_df["months_since_last_default"] = np.random.exponential(24, n).clip(0, 120).astype(int)
        credit_df["credit_utilization"] = np.random.beta(2, 5, n)
        credit_df["payment_history_score"] = np.random.beta(5, 2, n)

        logger.info(f"Generated credit data, default rate: {is_defaulted.mean():.4f}")
        return credit_df

    def generate_graph_data(self, transactions: pd.DataFrame) -> Dict[str, np.ndarray]:
        """Generate graph structure for GNN training (transaction network)"""
        logger.info("Generating graph data for GNN training...")

        # Build edges: customer → agent relationships
        edges_df = transactions[["customer_id", "agent_id"]].drop_duplicates()

        # Encode nodes
        all_customers = transactions["customer_id"].unique()
        all_agents = transactions["agent_id"].unique()

        customer_map = {c: i for i, c in enumerate(all_customers)}
        agent_map = {a: i + len(all_customers) for i, a in enumerate(all_agents)}

        # Edge index (COO format for PyTorch Geometric)
        src_nodes = []
        dst_nodes = []
        for _, row in edges_df.iterrows():
            if row["customer_id"] in customer_map and row["agent_id"] in agent_map:
                src_nodes.append(customer_map[row["customer_id"]])
                dst_nodes.append(agent_map[row["agent_id"]])

        edge_index = np.array([src_nodes, dst_nodes])

        # Node features
        n_nodes = len(all_customers) + len(all_agents)

        # Customer node features
        customer_features = np.random.randn(len(all_customers), 16)
        # Agent node features
        agent_features = np.random.randn(len(all_agents), 16)
        # Combine
        node_features = np.vstack([customer_features, agent_features])

        # Node labels (fraud indicator for customers)
        customer_fraud = transactions.groupby("customer_id")["is_fraud"].max()
        node_labels = np.zeros(n_nodes)
        for cust, idx in customer_map.items():
            if cust in customer_fraud.index:
                node_labels[idx] = customer_fraud[cust]

        logger.info(f"Graph: {n_nodes} nodes, {len(src_nodes)} edges")
        return {
            "edge_index": edge_index,
            "node_features": node_features,
            "node_labels": node_labels,
            "n_customers": len(all_customers),
            "n_agents": len(all_agents),
            "customer_map": customer_map,
            "agent_map": agent_map,
        }

    def generate_all(self) -> Dict[str, pd.DataFrame]:
        """Generate complete synthetic dataset"""
        logger.info("=" * 60)
        logger.info("Starting full Nigerian synthetic data generation")
        logger.info("=" * 60)

        customers = self.generate_customers()
        agents = self.generate_agents()
        transactions = self.generate_transactions(customers, agents)
        credit_data = self.generate_credit_data(customers, transactions)
        graph_data = self.generate_graph_data(transactions)

        logger.info("=" * 60)
        logger.info("Data generation complete!")
        logger.info(f"  Customers: {len(customers)}")
        logger.info(f"  Agents: {len(agents)}")
        logger.info(f"  Transactions: {len(transactions)}")
        logger.info(f"  Credit records: {len(credit_data)}")
        logger.info(f"  Graph nodes: {graph_data['node_features'].shape[0]}")
        logger.info(f"  Graph edges: {graph_data['edge_index'].shape[1]}")
        logger.info("=" * 60)

        return {
            "customers": customers,
            "agents": agents,
            "transactions": transactions,
            "credit_data": credit_data,
            "graph_data": graph_data,
        }


def generate_training_dataset(
    n_transactions: int = 200_000,
    n_customers: int = 20_000,
    n_agents: int = 1_000,
    seed: int = 42
) -> Dict[str, pd.DataFrame]:
    """Convenience function to generate a training-sized dataset"""
    config = DataConfig(
        n_customers=n_customers,
        n_agents=n_agents,
        n_transactions=n_transactions,
        seed=seed,
    )
    generator = NigerianTransactionGenerator(config)
    return generator.generate_all()


if __name__ == "__main__":
    data = generate_training_dataset(n_transactions=50_000, n_customers=5_000, n_agents=500)
    print(f"\nDataset shapes:")
    for key, value in data.items():
        if isinstance(value, pd.DataFrame):
            print(f"  {key}: {value.shape}")
        elif isinstance(value, dict):
            print(f"  {key}: {value['node_features'].shape[0]} nodes, {value['edge_index'].shape[1]} edges")
