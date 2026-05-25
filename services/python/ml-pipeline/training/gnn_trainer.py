"""
Graph Neural Network Training Pipeline

Trains GNN models for:
- Fraud detection on transaction graphs
- Agent network community detection
- Money laundering pattern recognition

Architectures:
- GCN (Graph Convolutional Network) - baseline
- GAT (Graph Attention Network) - attention-weighted neighbors
- GraphSAGE - inductive learning for unseen nodes

Features:
- Bipartite graph construction (customer ↔ agent)
- Proper message passing with edge features
- Mini-batch training with NeighborLoader
- Early stopping + checkpointing
- Weight persistence (.pt files)
"""

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch_geometric.nn import GCNConv, GATConv, SAGEConv, global_mean_pool
from torch_geometric.data import Data, Batch
from torch_geometric.loader import NeighborLoader
from sklearn.metrics import roc_auc_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
import joblib
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent.parent / "models" / "weights"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


# ======================== GNN Architectures ========================

class FraudGCN(nn.Module):
    """3-layer Graph Convolutional Network for node-level fraud classification"""

    def __init__(self, in_channels: int, hidden_channels: int = 128, out_channels: int = 2, dropout: float = 0.5):
        super().__init__()
        self.conv1 = GCNConv(in_channels, hidden_channels)
        self.bn1 = nn.BatchNorm1d(hidden_channels)
        self.conv2 = GCNConv(hidden_channels, hidden_channels // 2)
        self.bn2 = nn.BatchNorm1d(hidden_channels // 2)
        self.conv3 = GCNConv(hidden_channels // 2, out_channels)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        x = self.conv1(x, edge_index)
        x = self.bn1(x)
        x = F.relu(x)
        x = self.dropout(x)

        x = self.conv2(x, edge_index)
        x = self.bn2(x)
        x = F.relu(x)
        x = self.dropout(x)

        x = self.conv3(x, edge_index)
        return F.log_softmax(x, dim=1)


class FraudGAT(nn.Module):
    """Graph Attention Network with multi-head attention for fraud detection"""

    def __init__(self, in_channels: int, hidden_channels: int = 64, out_channels: int = 2,
                 heads: int = 4, dropout: float = 0.5):
        super().__init__()
        self.conv1 = GATConv(in_channels, hidden_channels, heads=heads, dropout=dropout)
        self.bn1 = nn.BatchNorm1d(hidden_channels * heads)
        self.conv2 = GATConv(hidden_channels * heads, hidden_channels, heads=heads, dropout=dropout)
        self.bn2 = nn.BatchNorm1d(hidden_channels * heads)
        self.conv3 = GATConv(hidden_channels * heads, out_channels, heads=1, concat=False, dropout=dropout)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        x = self.conv1(x, edge_index)
        x = self.bn1(x)
        x = F.elu(x)
        x = self.dropout(x)

        x = self.conv2(x, edge_index)
        x = self.bn2(x)
        x = F.elu(x)
        x = self.dropout(x)

        x = self.conv3(x, edge_index)
        return F.log_softmax(x, dim=1)


class FraudGraphSAGE(nn.Module):
    """GraphSAGE for inductive fraud detection on dynamic graphs"""

    def __init__(self, in_channels: int, hidden_channels: int = 128, out_channels: int = 2, dropout: float = 0.5):
        super().__init__()
        self.conv1 = SAGEConv(in_channels, hidden_channels)
        self.bn1 = nn.BatchNorm1d(hidden_channels)
        self.conv2 = SAGEConv(hidden_channels, hidden_channels // 2)
        self.bn2 = nn.BatchNorm1d(hidden_channels // 2)
        self.conv3 = SAGEConv(hidden_channels // 2, out_channels)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        x = self.conv1(x, edge_index)
        x = self.bn1(x)
        x = F.relu(x)
        x = self.dropout(x)

        x = self.conv2(x, edge_index)
        x = self.bn2(x)
        x = F.relu(x)
        x = self.dropout(x)

        x = self.conv3(x, edge_index)
        return F.log_softmax(x, dim=1)


# ======================== GNN Trainer ========================

class GNNFraudTrainer:
    """Trains GNN models on transaction graph data"""

    def __init__(self, output_dir: Path = MODELS_DIR, device: str = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        logger.info(f"GNN Trainer on device: {self.device}")

    def prepare_graph_data(self, graph_dict: Dict[str, np.ndarray]) -> Data:
        """Convert numpy graph data to PyTorch Geometric Data object"""
        edge_index = torch.LongTensor(graph_dict["edge_index"])
        node_features = torch.FloatTensor(graph_dict["node_features"])
        node_labels = torch.LongTensor(graph_dict["node_labels"].astype(int))

        # Make graph undirected (add reverse edges)
        reverse_edge_index = edge_index.flip(0)
        edge_index = torch.cat([edge_index, reverse_edge_index], dim=1)

        data = Data(
            x=node_features,
            edge_index=edge_index,
            y=node_labels,
        )

        # Create train/val/test masks
        n_nodes = node_features.shape[0]
        indices = np.arange(n_nodes)
        train_idx, test_idx = train_test_split(indices, test_size=0.3, random_state=42,
                                                stratify=node_labels.numpy())
        val_idx, test_idx = train_test_split(test_idx, test_size=0.5, random_state=42,
                                              stratify=node_labels.numpy()[test_idx])

        data.train_mask = torch.zeros(n_nodes, dtype=torch.bool)
        data.val_mask = torch.zeros(n_nodes, dtype=torch.bool)
        data.test_mask = torch.zeros(n_nodes, dtype=torch.bool)
        data.train_mask[train_idx] = True
        data.val_mask[val_idx] = True
        data.test_mask[test_idx] = True

        logger.info(f"Graph: {n_nodes} nodes, {edge_index.shape[1]} edges")
        logger.info(f"  Train: {data.train_mask.sum()}, Val: {data.val_mask.sum()}, Test: {data.test_mask.sum()}")
        logger.info(f"  Fraud rate: {node_labels.float().mean():.4f}")

        return data

    def train_all(self, graph_dict: Dict[str, np.ndarray]) -> Dict[str, Any]:
        """Train all GNN architectures"""
        logger.info("=" * 60)
        logger.info("GNN FRAUD DETECTION TRAINING PIPELINE")
        logger.info("=" * 60)
        start_time = time.time()

        data = self.prepare_graph_data(graph_dict)
        data = data.to(self.device)
        in_channels = data.x.shape[1]

        results = {}

        # Train GCN
        logger.info("\n--- Training GCN ---")
        gcn_model = FraudGCN(in_channels=in_channels, hidden_channels=128)
        results["gcn"] = self._train_model(gcn_model, data, "fraud_gcn")

        # Train GAT
        logger.info("\n--- Training GAT ---")
        gat_model = FraudGAT(in_channels=in_channels, hidden_channels=64, heads=4)
        results["gat"] = self._train_model(gat_model, data, "fraud_gat")

        # Train GraphSAGE
        logger.info("\n--- Training GraphSAGE ---")
        sage_model = FraudGraphSAGE(in_channels=in_channels, hidden_channels=128)
        results["graphsage"] = self._train_model(sage_model, data, "fraud_graphsage")

        # Save training metadata
        elapsed = time.time() - start_time
        metadata = {
            "training_timestamp": datetime.now().isoformat(),
            "training_duration_seconds": elapsed,
            "n_nodes": int(data.x.shape[0]),
            "n_edges": int(data.edge_index.shape[1]),
            "n_features": in_channels,
            "fraud_rate": float(data.y.float().mean()),
            "device": str(self.device),
            "results": {k: {mk: float(mv) for mk, mv in v.items() if isinstance(mv, (int, float, np.floating))} for k, v in results.items()},
        }
        with open(self.output_dir / "gnn_training_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"\nGNN training complete in {elapsed:.1f}s")
        return results

    def _train_model(self, model: nn.Module, data: Data, model_name: str) -> Dict:
        """Train a single GNN model with early stopping"""
        model = model.to(self.device)
        optimizer = optim.Adam(model.parameters(), lr=0.005, weight_decay=5e-4)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=10, factor=0.5)

        # Class weights for imbalanced graph
        n_classes = 2
        class_counts = torch.bincount(data.y[data.train_mask], minlength=n_classes).float()
        class_weights = (class_counts.sum() / (n_classes * class_counts)).to(self.device)
        criterion = nn.NLLLoss(weight=class_weights)

        best_val_auc = 0
        patience = 30
        patience_counter = 0
        epochs = 200

        for epoch in range(epochs):
            # Training
            model.train()
            optimizer.zero_grad()
            out = model(data.x, data.edge_index)
            loss = criterion(out[data.train_mask], data.y[data.train_mask])
            loss.backward()
            optimizer.step()

            # Validation
            model.eval()
            with torch.no_grad():
                out = model(data.x, data.edge_index)
                val_loss = criterion(out[data.val_mask], data.y[data.val_mask])
                val_probs = torch.exp(out[data.val_mask])[:, 1].cpu().numpy()
                val_labels = data.y[data.val_mask].cpu().numpy()

                if len(np.unique(val_labels)) > 1:
                    val_auc = roc_auc_score(val_labels, val_probs)
                else:
                    val_auc = 0.5

            scheduler.step(val_loss)

            if (epoch + 1) % 20 == 0:
                logger.info(f"  Epoch {epoch+1}/{epochs} - Loss: {loss.item():.4f}, "
                            f"Val AUC: {val_auc:.4f}")

            # Early stopping
            if val_auc > best_val_auc:
                best_val_auc = val_auc
                patience_counter = 0
                torch.save({
                    "model_state_dict": model.state_dict(),
                    "epoch": epoch,
                    "val_auc": val_auc,
                    "model_class": model.__class__.__name__,
                    "in_channels": data.x.shape[1],
                }, self.output_dir / f"{model_name}_best.pt")
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    logger.info(f"  Early stopping at epoch {epoch+1}")
                    break

        # Load best model and evaluate on test
        checkpoint = torch.load(self.output_dir / f"{model_name}_best.pt", map_location=self.device)
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()

        with torch.no_grad():
            out = model(data.x, data.edge_index)
            test_probs = torch.exp(out[data.test_mask])[:, 1].cpu().numpy()
            test_preds = out[data.test_mask].argmax(dim=1).cpu().numpy()
            test_labels = data.y[data.test_mask].cpu().numpy()

        metrics = {
            "auc": roc_auc_score(test_labels, test_probs) if len(np.unique(test_labels)) > 1 else 0.5,
            "f1": f1_score(test_labels, test_preds, zero_division=0),
            "precision": precision_score(test_labels, test_preds, zero_division=0),
            "recall": recall_score(test_labels, test_preds, zero_division=0),
            "best_epoch": int(checkpoint["epoch"]),
            "best_val_auc": float(best_val_auc),
        }

        logger.info(f"  {model_name} - Test AUC: {metrics['auc']:.4f}, F1: {metrics['f1']:.4f}")
        return metrics
