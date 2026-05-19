import torch
import torch.nn.functional as F
from torch_geometric.nn import GCNConv, SAGEConv, GATConv
from torch_geometric.data import Data, DataLoader
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score
import logging
import joblib

import time
import os
# Setup comprehensive logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class GNNFraudDetector(torch.nn.Module):
    """Advanced Graph Neural Network for fraud detection with multiple layer types."""

    def __init__(self, num_node_features, num_classes, hidden_channels=128, model_type='GAT'):
        super().__init__()
        self.model_type = model_type

        if model_type == 'GCN':
            self.conv1 = GCNConv(num_node_features, hidden_channels)
            self.conv2 = GCNConv(hidden_channels, hidden_channels // 2)
            self.conv3 = GCNConv(hidden_channels // 2, num_classes)
        elif model_type == 'SAGE':
            self.conv1 = SAGEConv(num_node_features, hidden_channels)
            self.conv2 = SAGEConv(hidden_channels, hidden_channels // 2)
            self.conv3 = SAGEConv(hidden_channels // 2, num_classes)
        elif model_type == 'GAT':
            self.conv1 = GATConv(num_node_features, hidden_channels, heads=4)
            self.conv2 = GATConv(hidden_channels * 4, hidden_channels // 2, heads=2)
            self.conv3 = GATConv(hidden_channels // 2 * 2, num_classes, heads=1, concat=False)
        else:
            raise ValueError("Unsupported GNN model type")

    def forward(self, data):
        x, edge_index = data.x, data.edge_index
        
        x = self.conv1(x, edge_index)
        x = F.elu(x)
        x = F.dropout(x, p=0.6, training=self.training)
        
        x = self.conv2(x, edge_index)
        x = F.elu(x)
        x = F.dropout(x, p=0.6, training=self.training)

        x = self.conv3(x, edge_index)
        
        return F.log_softmax(x, dim=1)

class FraudGraphBuilder:
    """Builds a sophisticated graph representation from heterogeneous financial data."""

    def __init__(self):
        self.scaler = StandardScaler()
        self.user_encoder = LabelEncoder()
        self.transaction_encoder = LabelEncoder()

    def build_graph(self, transactions_df, user_profiles_df, transaction_networks_df):
        logging.info("Building fraud graph from raw dataframes...")

        # 1. Node Definition (Users and Transactions as separate nodes)
        # This creates a bipartite graph structure which is more expressive
        num_users = len(user_profiles_df)
        num_transactions = len(transactions_df)

        # Encode user and transaction IDs to create a contiguous range of node indices
        user_profiles_df['user_idx'] = self.user_encoder.fit_transform(user_profiles_df['user_id'])
        transactions_df['tx_idx'] = self.transaction_encoder.fit_transform(transactions_df['transaction_id']) + num_users

        # 2. Node Features
        # User Node Features
        user_feature_cols = ['transaction_frequency', 'avg_transaction_amount', 'median_transaction_amount']
        for col in user_feature_cols:
            if col not in user_profiles_df.columns:
                user_profiles_df[col] = 0.0
        user_features = self.scaler.fit_transform(user_profiles_df[user_feature_cols].fillna(0))

        # Transaction Node Features
        tx_feature_cols = ['amount'] # Can add time-based features, etc.
        for col in tx_feature_cols:
            if col not in transactions_df.columns:
                transactions_df[col] = 0.0
        tx_features = self.scaler.fit_transform(transactions_df[tx_feature_cols].fillna(0))

        # To make user and transaction features have the same dimension, we pad them
        max_dim = max(user_features.shape[1], tx_features.shape[1])
        user_features_padded = np.pad(user_features, ((0, 0), (0, max_dim - user_features.shape[1])), 'constant')
        tx_features_padded = np.pad(tx_features, ((0, 0), (0, max_dim - tx_features.shape[1])), 'constant')

        # Combine features into a single tensor
        x = torch.tensor(np.vstack([user_features_padded, tx_features_padded]), dtype=torch.float)

        # 3. Edge Construction (Bipartite: User -> Transaction -> User)
        sender_map = dict(zip(user_profiles_df['user_id'], user_profiles_df['user_idx']))
        receiver_map = dict(zip(user_profiles_df['user_id'], user_profiles_df['user_idx']))
        tx_map = dict(zip(transactions_df['transaction_id'], transactions_df['tx_idx']))

        # Edges from sender to transaction
        sender_edges_src = transactions_df['sender_id'].map(sender_map).values
        sender_edges_dst = transactions_df['tx_idx'].values

        # Edges from transaction to receiver
        receiver_edges_src = transactions_df['tx_idx'].values
        receiver_edges_dst = transactions_df['receiver_id'].map(receiver_map).values
        
        # Combine edges
        edge_src = np.concatenate([sender_edges_src, receiver_edges_src])
        edge_dst = np.concatenate([sender_edges_dst, receiver_edges_dst])

        edge_index = torch.tensor([edge_src, edge_dst], dtype=torch.long)

        # 4. Labels (on transaction nodes)
        # Labels are only for transaction nodes. We'll use a mask for training.
        y = torch.zeros(num_users + num_transactions, dtype=torch.long) - 1 # -1 for nodes without labels (users)
        y[transactions_df['tx_idx']] = torch.tensor(transactions_df['fraud_label'].values, dtype=torch.long)

        data = Data(x=x, edge_index=edge_index, y=y)
        data.tx_mask = torch.zeros(num_users + num_transactions, dtype=torch.bool)
        data.tx_mask[transactions_df['tx_idx']] = True

        logging.info(f"Bipartite graph built with {data.num_nodes} nodes and {data.num_edges} edges.")
        return data

    def save_preprocessors(self, path):
        joblib.dump({'scaler': self.scaler, 'user_encoder': self.user_encoder, 'tx_encoder': self.transaction_encoder}, path)

    def load_preprocessors(self, path):
        preprocessors = joblib.load(path)
        self.scaler = preprocessors['scaler']
        self.user_encoder = preprocessors['user_encoder']
        self.transaction_encoder = preprocessors['tx_encoder']

class GNNService:
    """Production-grade service for GNN-based fraud detection."""

    def __init__(self, model_path=None, preprocessor_path=None, model_type='GAT'):
        self.model = None
        self.model_type = model_type
        self.graph_builder = FraudGraphBuilder()
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logging.info(f"Using device: {self.device}")

        if model_path and preprocessor_path:
            self.load_model(model_path, preprocessor_path)

    def train_model(self, data, epochs=100, lr=0.005, weight_decay=5e-4):
        logging.info(f"Training GNN model ({self.model_type}) on {self.device}...")
        num_classes = len(torch.unique(data.y[data.y != -1]))
        self.model = GNNFraudDetector(data.num_node_features, num_classes, model_type=self.model_type).to(self.device)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr, weight_decay=weight_decay)

        # Create train/test splits on transaction nodes
        tx_indices = torch.where(data.tx_mask)[0]
        train_indices, test_indices = train_test_split(tx_indices, test_size=0.2, random_state=42)
        
        data.train_mask = torch.zeros(data.num_nodes, dtype=torch.bool)
        data.test_mask = torch.zeros(data.num_nodes, dtype=torch.bool)
        data.train_mask[train_indices] = True
        data.test_mask[test_indices] = True

        data = data.to(self.device)

        best_f1 = 0.0
        for epoch in range(epochs):
            self.model.train()
            optimizer.zero_grad()
            out = self.model(data)
            loss = F.nll_loss(out[data.train_mask], data.y[data.train_mask])
            loss.backward()
            optimizer.step()

            if (epoch + 1) % 10 == 0:
                f1, _, _ = self.evaluate_model(data, 'test')
                if f1 > best_f1:
                    best_f1 = f1
                    self.save_model("best_gnn_model.pt", "best_preprocessors.joblib")
                logging.info(f'Epoch: {epoch+1:03d}, Loss: {loss:.4f}, Test F1: {f1:.4f}')
        logging.info(f"GNN model training complete. Best Test F1: {best_f1:.4f}")

    def evaluate_model(self, data, mask_type='test'):
        self.model.eval()
        mask = data.test_mask if mask_type == 'test' else data.train_mask
        with torch.no_grad():
            out = self.model(data.to(self.device))
            pred = out.argmax(dim=1)
            
            y_true = data.y[mask].cpu().numpy()
            y_pred = pred[mask].cpu().numpy()
            y_prob = out[mask].exp()[:, 1].cpu().numpy()

            auc = roc_auc_score(y_true, y_prob)
            ap = average_precision_score(y_true, y_prob)
            f1 = f1_score(y_true, y_pred)

        return f1, auc, ap

    def predict_fraud(self, data):
        logging.info("Making fraud predictions with GNN model...")
        if self.model is None:
            raise ValueError("Model not trained or loaded.")
        self.model.eval()
        with torch.no_grad():
            out = self.model(data.to(self.device))
            probabilities = out.exp()[:, 1].cpu().numpy()
            predictions = out.argmax(dim=1).cpu().numpy()
        return probabilities, predictions

    def save_model(self, model_path, preprocessor_path):
        logging.info(f"Saving GNN model to {model_path} and preprocessors to {preprocessor_path}")
        torch.save(self.model.state_dict(), model_path)
        self.graph_builder.save_preprocessors(preprocessor_path)

    def load_model(self, model_path, preprocessor_path, num_node_features, num_classes):
        logging.info(f"Loading GNN model from {model_path} and preprocessors from {preprocessor_path}")
        self.graph_builder.load_preprocessors(preprocessor_path)
        self.model = GNNFraudDetector(num_node_features, num_classes, model_type=self.model_type).to(self.device)
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.eval()

# Example Usage
if __name__ == '__main__':
    # Dummy Data Generation for demonstration
    num_transactions = 5000
    num_users = 1000
    
    transactions_data = {
        'transaction_id': [f'tx_{i}' for i in range(num_transactions)],
        'sender_id': [f'user_{np.random.randint(0, num_users)}' for _ in range(num_transactions)],
        'receiver_id': [f'user_{np.random.randint(0, num_users)}' for _ in range(num_transactions)],
        'amount': np.random.lognormal(3, 1, num_transactions),
        'fraud_label': (np.random.rand(num_transactions) < 0.05).astype(int) # 5% fraud rate
    }
    transactions_df = pd.DataFrame(transactions_data)

    user_profiles_data = {
        'user_id': [f'user_{i}' for i in range(num_users)],
        'transaction_frequency': np.random.randint(1, 100, num_users),
        'avg_transaction_amount': np.random.lognormal(4, 1, num_users),
        'median_transaction_amount': np.random.lognormal(3.8, 1, num_users),
    }
    user_profiles_df = pd.DataFrame(user_profiles_data)

    # In a real scenario, this would come from the data pipeline
    transaction_networks_df = pd.DataFrame()

    graph_builder = FraudGraphBuilder()
    graph_data = graph_builder.build_graph(transactions_df, user_profiles_df, transaction_networks_df)

    # Initialize and train the GNN service
    gnn_service = GNNService(model_type='GAT')
    gnn_service.train_model(graph_data, epochs=50)
    
    # Evaluate the trained model
    f1, auc, ap = gnn_service.evaluate_model(graph_data, 'test')
    logging.info(f"Final Evaluation - F1: {f1:.4f}, AUC: {auc:.4f}, AP: {ap:.4f}")

    # Make predictions on the whole graph
    probabilities, predictions = gnn_service.predict_fraud(graph_data)
    tx_mask = graph_data.tx_mask.cpu().numpy()
    logging.info(f"Sample predictions on transactions: {predictions[tx_mask][:10]}")
    logging.info(f"Sample probabilities on transactions: {probabilities[tx_mask][:10]}")

    # Save and load model example
    model_save_path = "gnn_fraud_model_prod.pt"
    preprocessor_save_path = "gnn_preprocessors_prod.joblib"
    gnn_service.save_model(model_save_path, preprocessor_save_path)
    
    loaded_gnn_service = GNNService(model_type='GAT')
    # For loading, you need to know the feature dimensions from the training data
    loaded_gnn_service.load_model(model_save_path, preprocessor_save_path, graph_data.num_node_features, len(torch.unique(graph_data.y[graph_data.y != -1])))
    loaded_probabilities, _ = loaded_gnn_service.predict_fraud(graph_data)
    logging.info("Production model loaded and predictions made successfully.")

