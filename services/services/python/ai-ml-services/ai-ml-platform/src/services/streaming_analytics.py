import pandas as pd
import numpy as np
from collections import deque
import time
import threading
import logging

import sys
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RealtimeAnalyticsEngine:
    """A sophisticated engine for real-time streaming analytics on financial transactions."""


    def __init__(self, window_size_seconds=3600, user_history_limit=100):
        self.window_size_seconds = window_size_seconds
        self.user_history_limit = user_history_limit
        
        # Use deques for efficient time-windowed operations
        self.transaction_window = deque()
        
        # Store user-specific aggregates and history
        self.user_aggregates = {}
        self.user_transaction_history = {}

        # For monitoring and performance tracking
        self.processed_count = 0
        self.start_time = time.time()

        # Lock for thread-safe operations
        self.lock = threading.Lock()

    def _cleanup_window(self):
        """Removes transactions that are older than the defined window size."""

        now = time.time()
        while self.transaction_window and self.transaction_window[0]["timestamp"] < now - self.window_size_seconds:
            self.transaction_window.popleft()

    def process_transaction_stream(self, new_transaction):
        """Processes a new transaction, updates aggregates, and returns real-time features."""
        with self.lock:
            now = time.time()
            new_transaction["timestamp"] = now
            
            self.transaction_window.append(new_transaction)
            self._cleanup_window()

            sender_id = new_transaction["sender_id"]
            receiver_id = new_transaction["receiver_id"]
            amount = new_transaction["amount"]

            # Update aggregates for sender and receiver
            self._update_user_aggregates(sender_id, amount, "send")
            self._update_user_aggregates(receiver_id, amount, "receive")

            # Generate real-time features
            realtime_features = self._generate_realtime_features(new_transaction)

            self.processed_count += 1
            return realtime_features

    def _update_user_aggregates(self, user_id, amount, direction):
        """Updates the aggregates for a specific user."""
        if user_id not in self.user_aggregates:
            self.user_aggregates[user_id] = self._initialize_user_aggregates()
            self.user_transaction_history[user_id] = deque(maxlen=self.user_history_limit)

        # Update transaction history
        self.user_transaction_history[user_id].append(amount)
        history = list(self.user_transaction_history[user_id])

        # Update aggregates
        agg = self.user_aggregates[user_id]
        if direction == "send":
            agg["send_count"] += 1
            agg["send_total_amount"] += amount
        else: # receive
            agg["receive_count"] += 1
            agg["receive_total_amount"] += amount
        
        agg["avg_amount"] = np.mean(history)
        agg["median_amount"] = np.median(history)
        agg["std_dev_amount"] = np.std(history)
        agg["max_amount"] = np.max(history)
        agg["min_amount"] = np.min(history)

    def _initialize_user_aggregates(self):
        return {
            "send_count": 0,
            "receive_count": 0,
            "send_total_amount": 0.0,
            "receive_total_amount": 0.0,
            "avg_amount": 0.0,
            "median_amount": 0.0,
            "std_dev_amount": 0.0,
            "max_amount": 0.0,
            "min_amount": 0.0
        }

    def _generate_realtime_features(self, transaction):
        """Generates features based on the current state of the engine."""

        sender_id = transaction["sender_id"]
        receiver_id = transaction["receiver_id"]
        amount = transaction["amount"]

        sender_agg = self.user_aggregates.get(sender_id, self._initialize_user_aggregates())
        receiver_agg = self.user_aggregates.get(receiver_id, self._initialize_user_aggregates())

        # Time-based features within the global window
        window_df = pd.DataFrame(list(self.transaction_window))
        sender_window_tx = window_df[window_df["sender_id"] == sender_id]
        receiver_window_tx = window_df[window_df["receiver_id"] == receiver_id]

        features = {
            # Transaction-level features
            "amount": amount,
            
            # Sender-based features
            "sender_tx_count_in_window": len(sender_window_tx),
            "sender_avg_amount_history": sender_agg["avg_amount"],
            "amount_vs_sender_avg": amount / (sender_agg["avg_amount"] + 1e-6),
            "amount_vs_sender_max": amount / (sender_agg["max_amount"] + 1e-6),
            
            # Receiver-based features
            "receiver_tx_count_in_window": len(receiver_window_tx),
            "receiver_avg_amount_history": receiver_agg["avg_amount"],
            "amount_vs_receiver_avg": amount / (receiver_agg["avg_amount"] + 1e-6),

            # Global window features
            "avg_tx_amount_in_window": window_df["amount"]
.mean(),
            "total_tx_in_window": len(self.transaction_window)
        }
        return features

    def get_user_summary(self, user_id):
        with self.lock:
            if user_id in self.user_aggregates:
                return self.user_aggregates[user_id]
            return None

    def get_system_throughput(self):
        with self.lock:
            elapsed_time = time.time() - self.start_time
            if elapsed_time > 0:
                return self.processed_count / elapsed_time
            return 0

    def get_system_status(self):
        with self.lock:
            return {
                "processed_transactions": self.processed_count,
                "transactions_in_window": len(self.transaction_window),
                "unique_users_tracked": len(self.user_aggregates),
                "throughput_tps": self.get_system_throughput(),
                "uptime_seconds": time.time() - self.start_time
            }

# Example Usage with a simulated real-time stream
def simulate_stream(engine, num_transactions=1000, max_users=50):
    logging.info(f"--- Simulating a stream of {num_transactions} transactions ---")
    for i in range(num_transactions):
        transaction = {
            "transaction_id": f"tx_{i}",
            "sender_id": f"user_{np.random.randint(0, max_users)}",
            "receiver_id": f"user_{np.random.randint(0, max_users)}",
            "amount": np.random.lognormal(3, 1)
        }
        
        realtime_features = engine.process_transaction_stream(transaction)
        
        if (i + 1) % 100 == 0:
            logging.info(f"Processed transaction {i+1}. Throughput: {engine.get_system_throughput():.2f} TPS")
            # logging.info(f"Real-time features for tx_{i}: {realtime_features}")
        
        time.sleep(0.01) # Simulate time between transactions

if __name__ == "__main__":
    # Initialize the engine with a 1-hour window
    analytics_engine = RealtimeAnalyticsEngine(window_size_seconds=3600)

    # Run the simulation in a separate thread to not block other operations
    simulation_thread = threading.Thread(target=simulate_stream, args=(analytics_engine, 2000, 100))
    simulation_thread.start()

    # While the simulation runs, we can query the system status
    for _ in range(5):
        time.sleep(4) # Wait for some transactions to be processed
        if simulation_thread.is_alive():
            status = analytics_engine.get_system_status()
            logging.info(f"SYSTEM STATUS: {status}")
            
            # Get a summary for a specific user
            user_summary = analytics_engine.get_user_summary("user_10")
            if user_summary:
                logging.info(f"SUMMARY for user_10: {user_summary}")

    # Wait for the simulation to finish
    simulation_thread.join()
    logging.info("Simulation finished.")
    final_status = analytics_engine.get_system_status()
    logging.info(f"FINAL SYSTEM STATUS: {final_status}")

