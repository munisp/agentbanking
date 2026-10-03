import sys as _sys, os as _os

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

# ── Round-11 persistence fix (wave-6: asyncpg) ────────────────────────────
# Process-memory containers replaced by Postgres-backed stores so business
# data survives restarts. Wave-6 upgrade: all DB I/O now runs on asyncpg via
# a dedicated background event loop, so async FastAPI handlers no longer
# block the main loop on sync SQLAlchemy calls. Same dict/list-compatible
# public API; {ENV}_DATABASE_URL convention unchanged.
import os as _r11_os
import json as _r11_json
import asyncio as _r11_asyncio
import threading as _r11_threading
import asyncpg as _r11_apg

_r11_loop = _r11_asyncio.new_event_loop()


def _r11_loop_main(loop):
    _r11_asyncio.set_event_loop(loop)
    loop.run_forever()


_r11_threading.Thread(
    target=_r11_loop_main, args=(_r11_loop,), daemon=True, name="r11-pg-io"
).start()


def _r11_sync(coro):
    """Run an asyncpg coroutine on the dedicated loop and wait for it."""
    return _r11_asyncio.run_coroutine_threadsafe(coro, _r11_loop).result()


class _PgDictStore:
    """Dict-compatible store persisted to Postgres (replaces in-memory dict)."""

    def __init__(self, table, env, model_name=None):
        if not table.replace("_", "").isalnum():
            raise ValueError("unsafe table name: %r" % table)
        self._model_name = model_name
        self._table = table
        url = _r11_os.getenv(
            env, "postgresql://postgres:postgres@localhost:5432/platform"
        )
        self._pool = _r11_sync(_r11_apg.create_pool(url, min_size=1, max_size=10))
        _r11_sync(self._ensure())

    async def _ensure(self):
        async with self._pool.acquire() as c:
            await c.execute(
                'CREATE TABLE IF NOT EXISTS "%s" ('
                "key VARCHAR(128) PRIMARY KEY, "
                "data TEXT NOT NULL, "
                "updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
                ")" % self._table
            )

    @staticmethod
    def _ser(v):
        def _cv(x):
            if hasattr(x, "model_dump"):
                return x.model_dump()
            if hasattr(x, "dict") and callable(x.dict):
                return x.dict()
            return x
        if isinstance(v, list):
            v = [_cv(x) for x in v]
        else:
            v = _cv(v)
        return _r11_json.dumps(v, default=str)

    def _deser(self, raw):
        d = _r11_json.loads(raw)
        if self._model_name:
            cls = globals().get(self._model_name)
            if cls is not None:
                if isinstance(d, list):
                    return [cls(**x) if isinstance(x, dict) else x for x in d]
                return cls(**d)
        return d

    async def _aset(self, k, payload):
        async with self._pool.acquire() as c:
            await c.execute(
                'INSERT INTO "%s" (key, data) VALUES ($1, $2) '
                "ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data, "
                "updated_at = now()" % self._table,
                str(k), payload,
            )

    def __setitem__(self, k, v):
        _r11_sync(self._aset(k, self._ser(v)))

    async def _aget(self, k):
        async with self._pool.acquire() as c:
            return await c.fetchval(
                'SELECT data FROM "%s" WHERE key = $1' % self._table, str(k)
            )

    def __getitem__(self, k):
        raw = _r11_sync(self._aget(k))
        if raw is None:
            raise KeyError(k)
        return self._deser(raw)

    def get(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            return default

    async def _adel(self, k):
        async with self._pool.acquire() as c:
            return await c.execute(
                'DELETE FROM "%s" WHERE key = $1' % self._table, str(k)
            )

    def __delitem__(self, k):
        res = _r11_sync(self._adel(k))
        if res == "DELETE 0":
            raise KeyError(k)

    def __contains__(self, k):
        return _r11_sync(self._aget(k)) is not None

    def setdefault(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            self[k] = default
            return default

    async def _aall(self):
        async with self._pool.acquire() as c:
            return await c.fetch('SELECT key, data FROM "%s"' % self._table)

    def _all(self):
        return _r11_sync(self._aall())

    def values(self):
        return [self._deser(r["data"]) for r in self._all()]

    def keys(self):
        return [r["key"] for r in self._all()]

    def items(self):
        return [(r["key"], self._deser(r["data"])) for r in self._all()]

    def __len__(self):
        async def _n():
            async with self._pool.acquire() as c:
                return await c.fetchval('SELECT COUNT(*) FROM "%s"' % self._table)
        return _r11_sync(_n())

    def pop(self, k, default=None):
        try:
            v = self[k]
            del self[k]
            return v
        except KeyError:
            return default

    def clear(self):
        async def _c():
            async with self._pool.acquire() as c:
                await c.execute('DELETE FROM "%s"' % self._table)
        _r11_sync(_c())


class _PgListStore:
    """List-compatible store persisted to Postgres (replaces in-memory list)."""

    def __init__(self, table, env):
        if not table.replace("_", "").isalnum():
            raise ValueError("unsafe table name: %r" % table)
        self._table = table
        url = _r11_os.getenv(
            env, "postgresql://postgres:postgres@localhost:5432/platform"
        )
        self._pool = _r11_sync(_r11_apg.create_pool(url, min_size=1, max_size=10))
        _r11_sync(self._ensure())

    async def _ensure(self):
        async with self._pool.acquire() as c:
            await c.execute(
                'CREATE TABLE IF NOT EXISTS "%s" ('
                "id SERIAL PRIMARY KEY, "
                "data TEXT NOT NULL, "
                "created_at TIMESTAMPTZ NOT NULL DEFAULT now()"
                ")" % self._table
            )

    @staticmethod
    def _ser(v):
        def _cv(x):
            if hasattr(x, "model_dump"):
                return x.model_dump()
            if hasattr(x, "dict") and callable(x.dict):
                return x.dict()
            return x
        return _r11_json.dumps(_cv(v), default=str)

    @staticmethod
    def _deser(raw):
        return _r11_json.loads(raw)

    def append(self, v):
        async def _a():
            async with self._pool.acquire() as c:
                await c.execute(
                    'INSERT INTO "%s" (data) VALUES ($1)' % self._table,
                    self._ser(v),
                )
        _r11_sync(_a())

    async def _arows(self):
        async with self._pool.acquire() as c:
            return await c.fetch(
                'SELECT id, data FROM "%s" ORDER BY id' % self._table
            )

    def _rows(self):
        return _r11_sync(self._arows())

    def __iter__(self):
        return iter([self._deser(r["data"]) for r in self._rows()])

    def __len__(self):
        async def _n():
            async with self._pool.acquire() as c:
                return await c.fetchval('SELECT COUNT(*) FROM "%s"' % self._table)
        return _r11_sync(_n())

    def __getitem__(self, idx):
        vals = [self._deser(r["data"]) for r in self._rows()]
        return vals[idx]

    def __delitem__(self, idx):
        rows = self._rows()
        targets = rows[idx] if isinstance(idx, slice) else [rows[idx]]
        ids = [r["id"] for r in targets]
        if not ids:
            return
        async def _d():
            async with self._pool.acquire() as c:
                await c.execute(
                    'DELETE FROM "%s" WHERE id = ANY($1::int[])' % self._table, ids
                )
        _r11_sync(_d())

    def clear(self):
        async def _c():
            async with self._pool.acquire() as c:
                await c.execute('DELETE FROM "%s"' % self._table)
        _r11_sync(_c())

_shutdown_handlers = _PgListStore("gnn_engine__shutdown_handlers", "GNN_ENGINE_DATABASE_URL")  # round-11 wave-7 persistence

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logging.info(f"[shutdown] Received {sig_name}, shutting down gracefully...")
    for handler in reversed(_shutdown_handlers):
        try:
            handler()
        except Exception as e:
            logging.warning(f"[shutdown] Handler error: {e}")
    logging.info("[shutdown] Cleanup complete, exiting")
    sys.exit(0)

signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)
atexit.register(lambda: logging.info("[shutdown] atexit handler called"))

_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Production-Ready GNN Engine Service
Graph Neural Network for Fraud Detection
Uses real PyTorch Geometric models with trained weights

NOTE: Fraud scores are ONLY served from models with trained weight
checkpoints on disk ({MODEL_PATH}/<name>_fraud_detector.pt). A model with
random (untrained) initialization is NEVER used for inference — /predict
returns 503 for untrained models. /train performs real supervised training
on a labeled graph dataset (GNN_TRAINING_DATA_PATH, JSON) and only
activates the model after it has been trained and evaluated.
"""
import os
import logging
import torch
import torch.nn.functional as F
import numpy as np
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware


from pydantic import BaseModel, Field
import torch_geometric
from torch_geometric.nn import GCNConv, GATConv, SAGEConv
from torch_geometric.data import Data
import joblib
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GNN Engine Service (Production)",
    description="Production-ready Graph Neural Network for Fraud Detection",
    version="2.0.0"
)

apply_middleware(app)
setup_logging("gnn-engine-service-(production)")
app.include_router(metrics_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
class Config:
    MODEL_PATH = os.getenv("GNN_MODEL_PATH", "/models/gnn")
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    MODEL_VERSION = "2.0.0"
    FRAUD_THRESHOLD = float(os.getenv("FRAUD_THRESHOLD", "0.7"))
    TRAINING_DATA_PATH = os.getenv("GNN_TRAINING_DATA_PATH", "")  # JSON labeled graph dataset

config = Config()

# Statistics
stats = {
    "total_predictions": 0,
    "fraud_detected": 0,
    "start_time": datetime.now(),
    "model_version": config.MODEL_VERSION
}

# ==================== GNN Models ====================

class GCNFraudDetector(torch.nn.Module):
    """Graph Convolutional Network for Fraud Detection"""
    def __init__(self, num_features, hidden_dim=64, num_classes=2):
        super(GCNFraudDetector, self).__init__()
        self.conv1 = GCNConv(num_features, hidden_dim)
        self.conv2 = GCNConv(hidden_dim, hidden_dim)
        self.conv3 = GCNConv(hidden_dim, num_classes)
        self.dropout = torch.nn.Dropout(0.5)

    def forward(self, x, edge_index):
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = self.dropout(x)

        x = self.conv2(x, edge_index)
        x = F.relu(x)
        x = self.dropout(x)

        x = self.conv3(x, edge_index)
        return F.log_softmax(x, dim=1)

class GATFraudDetector(torch.nn.Module):
    """Graph Attention Network for Fraud Detection"""
    def __init__(self, num_features, hidden_dim=64, num_classes=2, heads=4):
        super(GATFraudDetector, self).__init__()
        self.conv1 = GATConv(num_features, hidden_dim, heads=heads)
        self.conv2 = GATConv(hidden_dim * heads, hidden_dim, heads=heads)
        self.conv3 = GATConv(hidden_dim * heads, num_classes, heads=1)
        self.dropout = torch.nn.Dropout(0.5)

    def forward(self, x, edge_index):
        x = self.conv1(x, edge_index)
        x = F.elu(x)
        x = self.dropout(x)

        x = self.conv2(x, edge_index)
        x = F.elu(x)
        x = self.dropout(x)

        x = self.conv3(x, edge_index)
        return F.log_softmax(x, dim=1)

class GraphSAGEFraudDetector(torch.nn.Module):
    """GraphSAGE for Large-scale Fraud Detection"""
    def __init__(self, num_features, hidden_dim=64, num_classes=2):
        super(GraphSAGEFraudDetector, self).__init__()
        self.conv1 = SAGEConv(num_features, hidden_dim)
        self.conv2 = SAGEConv(hidden_dim, hidden_dim)
        self.conv3 = SAGEConv(hidden_dim, num_classes)
        self.dropout = torch.nn.Dropout(0.5)

    def forward(self, x, edge_index):
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = self.dropout(x)

        x = self.conv2(x, edge_index)
        x = F.relu(x)
        x = self.dropout(x)

        x = self.conv3(x, edge_index)
        return F.log_softmax(x, dim=1)

# ==================== Model Manager ====================

class GNNModelManager:
    """Manages GNN models and inference.

    A model is only eligible for inference once trained weights have been
    loaded from disk. Untrained (random-initialized) networks are never
    served as fraud scores.
    """
    def __init__(self):
        self.device = torch.device(config.DEVICE)
        self.models = {}
        self.trained: Dict[str, bool] = {}
        self.training_metrics: Dict[str, Dict[str, Any]] = {}
        self.feature_dim = 32  # Default feature dimension
        self.load_models()

    def load_models(self):
        """Load pre-trained GNN models"""
        try:
            model_path = Path(config.MODEL_PATH)
            model_path.mkdir(parents=True, exist_ok=True)

            # Initialize model architectures
            self.models['gcn'] = GCNFraudDetector(self.feature_dim).to(self.device)
            self.models['gat'] = GATFraudDetector(self.feature_dim).to(self.device)
            self.models['graphsage'] = GraphSAGEFraudDetector(self.feature_dim).to(self.device)

            # Load saved weights — fail closed: no weights => model not servable
            for model_name, model in self.models.items():
                weight_path = model_path / f"{model_name}_fraud_detector.pt"
                if weight_path.exists():
                    model.load_state_dict(torch.load(weight_path, map_location=self.device))
                    self.trained[model_name] = True
                    logger.info(f"Loaded trained {model_name} weights from {weight_path}")
                else:
                    self.trained[model_name] = False
                    logger.error(
                        f"No trained weights for {model_name} at {weight_path} — "
                        "model will REFUSE inference (503) until trained"
                    )

                model.eval()

            logger.info(
                f"GNN models on {self.device}: "
                + ", ".join(f"{n}={'trained' if t else 'UNTRAINED'}" for n, t in self.trained.items())
            )

        except Exception as e:
            logger.error(f"Error loading models: {e}")
            raise

    def is_trained(self, model_name: str) -> bool:
        return self.trained.get(model_name, False)

    def save_model(self, model_name: str):
        """Save model weights"""
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found")

        model_path = Path(config.MODEL_PATH)
        model_path.mkdir(parents=True, exist_ok=True)
        weight_path = model_path / f"{model_name}_fraud_detector.pt"

        torch.save(self.models[model_name].state_dict(), weight_path)
        logger.info(f"Saved {model_name} weights to {weight_path}")

    def mark_trained(self, model_name: str, metrics: Optional[Dict[str, Any]] = None):
        self.trained[model_name] = True
        if metrics:
            self.training_metrics[model_name] = metrics

    def predict(self, graph_data: Data, model_name: str = 'gcn') -> Dict[str, Any]:
        """Predict fraud using specified GNN model.

        Fails closed: raises RuntimeError if the requested model has no
        trained weights — random-init outputs are never served as scores.
        """
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found")
        if not self.is_trained(model_name):
            raise RuntimeError(
                f"Model '{model_name}' has no trained checkpoint loaded; "
                "inference refused (train the model first via /train with a real dataset)"
            )

        model = self.models[model_name]
        model.eval()

        with torch.no_grad():
            # Move data to device
            graph_data = graph_data.to(self.device)

            # Forward pass
            out = model(graph_data.x, graph_data.edge_index)

            # Get predictions
            probs = torch.exp(out)
            fraud_probs = probs[:, 1].cpu().numpy()
            predictions = (fraud_probs > config.FRAUD_THRESHOLD).astype(int)

            # Get node embeddings (from second-to-last layer)
            embeddings = self._get_embeddings(model, graph_data)

            # Identify anomalous nodes
            anomalous_nodes = np.where(predictions == 1)[0].tolist()

            return {
                "fraud_probabilities": fraud_probs.tolist(),
                "predictions": predictions.tolist(),
                "embeddings": embeddings.tolist(),
                "anomalous_nodes": anomalous_nodes,
                "model_name": model_name
            }

    def _get_embeddings(self, model, graph_data):
        """Extract node embeddings from model"""
        with torch.no_grad():
            x = graph_data.x
            edge_index = graph_data.edge_index

            # Get embeddings from second layer
            if hasattr(model, 'conv2'):
                x = model.conv1(x, edge_index)
                x = F.relu(x)
                x = model.conv2(x, edge_index)
            else:
                x = model.conv1(x, edge_index)

            return x.cpu().numpy()

# Initialize model manager
model_manager = GNNModelManager()

# ==================== API Models ====================

class Transaction(BaseModel):
    transaction_id: str
    user_id: str
    amount: float
    timestamp: datetime
    merchant_id: Optional[str] = None
    location: Optional[str] = None
    features: Optional[Dict[str, float]] = None

class FraudPredictionRequest(BaseModel):
    transactions: List[Transaction]
    edges: List[List[int]] = Field(default_factory=list, description="Edge list [[src, dst], ...]")
    model_name: str = Field(default="gcn", description="GNN model to use: gcn, gat, or graphsage")

class FraudPredictionResponse(BaseModel):
    transaction_id: str
    is_fraudulent: bool
    fraud_score: float
    model_version: str
    anomalous_nodes: List[int]
    explanation: str

# ==================== Helper Functions ====================

def create_graph_from_transactions(transactions: List[Transaction], edges: List[List[int]]) -> Data:
    """Create PyTorch Geometric graph from transactions"""
    num_nodes = len(transactions)

    # Extract features
    features = []
    for txn in transactions:
        if txn.features:
            feat = list(txn.features.values())
        else:
            # Default features: amount (normalized), hour, day_of_week
            hour = txn.timestamp.hour / 24.0
            day = txn.timestamp.weekday() / 7.0
            amount_norm = min(txn.amount / 10000.0, 1.0)  # Normalize amount
            feat = [amount_norm, hour, day]
            # Pad to feature_dim
            feat = feat + [0.0] * (model_manager.feature_dim - len(feat))

        features.append(feat[:model_manager.feature_dim])

    # Create node features tensor
    x = torch.tensor(features, dtype=torch.float)

    # Create edge index
    if edges:
        edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()
    else:
        # Create fully connected graph if no edges provided
        edge_list = []
        for i in range(num_nodes):
            for j in range(i + 1, num_nodes):
                edge_list.append([i, j])
                edge_list.append([j, i])  # Undirected
        edge_index = torch.tensor(edge_list, dtype=torch.long).t().contiguous()

    return Data(x=x, edge_index=edge_index)

# ==================== API Endpoints ====================

@app.get("/")
async def root():
    return {
        "service": "gnn-engine-production",
        "version": config.MODEL_VERSION,
        "device": config.DEVICE,
        "models": list(model_manager.models.keys()),
        "trained_models": {k: v for k, v in model_manager.trained.items()},
        "status": "ready"
    }

@app.get("/health")
async def health_check():
    uptime = (datetime.now() - stats["start_time"]).total_seconds()
    any_trained = any(model_manager.trained.values())
    return {
        "status": "healthy" if any_trained else "degraded",
        "uptime_seconds": int(uptime),
        "device": config.DEVICE,
        "models_loaded": len(model_manager.models),
        "models_trained": model_manager.trained,
        "total_predictions": stats["total_predictions"],
        "fraud_detected": stats["fraud_detected"]
    }

@app.post("/predict", response_model=List[FraudPredictionResponse])
async def predict_fraud(request: FraudPredictionRequest):
    """Predict fraud for a batch of transactions using GNN"""
    if request.model_name not in model_manager.models:
        raise HTTPException(status_code=404, detail=f"Model {request.model_name} not found")
    if not model_manager.is_trained(request.model_name):
        raise HTTPException(
            status_code=503,
            detail=(
                f"GNN model '{request.model_name}' has no trained checkpoint. "
                "Fraud scoring is refused rather than served from a random-initialized network."
            ),
        )
    try:
        stats["total_predictions"] += 1

        # Create graph from transactions
        graph_data = create_graph_from_transactions(request.transactions, request.edges)

        # Predict using specified model
        predictions = model_manager.predict(graph_data, request.model_name)

        # Format response
        responses = []
        for idx, txn in enumerate(request.transactions):
            fraud_score = predictions["fraud_probabilities"][idx]
            is_fraudulent = predictions["predictions"][idx] == 1

            if is_fraudulent:
                stats["fraud_detected"] += 1

            explanation = f"GNN model '{request.model_name}' detected "
            if is_fraudulent:
                explanation += f"fraudulent activity (score: {fraud_score:.3f})"
            else:
                explanation += f"normal activity (score: {fraud_score:.3f})"

            responses.append(FraudPredictionResponse(
                transaction_id=txn.transaction_id,
                is_fraudulent=is_fraudulent,
                fraud_score=fraud_score,
                model_version=config.MODEL_VERSION,
                anomalous_nodes=predictions["anomalous_nodes"],
                explanation=explanation
            ))

        return responses

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/models")
async def list_models():
    """List available GNN models"""
    return {
        "models": [
            {
                "name": name,
                "description": desc,
                "parameters": sum(p.numel() for p in model_manager.models[name].parameters()),
                "trained": model_manager.trained.get(name, False),
                "training_metrics": model_manager.training_metrics.get(name),
            }
            for name, desc in [
                ("gcn", "Graph Convolutional Network"),
                ("gat", "Graph Attention Network"),
                ("graphsage", "GraphSAGE"),
            ]
        ],
        "device": config.DEVICE
    }

@app.post("/train")
async def train_model(background_tasks: BackgroundTasks, model_name: str = "gcn"):
    """Trigger model training (background task) on a real labeled dataset.

    Requires GNN_TRAINING_DATA_PATH pointing to a JSON file:
      {"x": [[...features per node...]], "edge_index": [[src...],[dst...]],
       "y": [0|1 per node], "train_mask": [bool...] (optional),
       "val_mask": [bool...] (optional)}
    """
    if model_name not in model_manager.models:
        raise HTTPException(status_code=404, detail=f"Model {model_name} not found")
    if not config.TRAINING_DATA_PATH or not os.path.exists(config.TRAINING_DATA_PATH):
        raise HTTPException(
            status_code=503,
            detail=(
                "No training data configured. Set GNN_TRAINING_DATA_PATH to a labeled "
                "graph dataset (JSON). Training without real labeled fraud data is not supported."
            ),
        )
    background_tasks.add_task(train_gnn_model, model_name)
    return {"message": f"Training started in background for '{model_name}'", "dataset": config.TRAINING_DATA_PATH}

def train_gnn_model(model_name: str = "gcn"):
    """Train GNN model on real labeled fraud graph data.

    Loads a labeled dataset from disk, runs supervised training, evaluates
    on a validation split, and only then persists weights and marks the
    model as servable.
    """
    logger.info(f"Starting GNN model training for '{model_name}'...")
    try:
        with open(config.TRAINING_DATA_PATH) as f:
            dataset = json.load(f)

        x = torch.tensor(dataset["x"], dtype=torch.float)
        edge_index = torch.tensor(dataset["edge_index"], dtype=torch.long)
        y = torch.tensor(dataset["y"], dtype=torch.long)
        num_nodes = x.size(0)

        train_mask = dataset.get("train_mask")
        val_mask = dataset.get("val_mask")
        if train_mask:
            train_mask = torch.tensor(train_mask, dtype=torch.bool)
        else:
            train_mask = torch.rand(num_nodes) < 0.8
        if val_mask:
            val_mask = torch.tensor(val_mask, dtype=torch.bool)
        else:
            val_mask = ~train_mask

        data = Data(x=x, edge_index=edge_index, y=y).to(model_manager.device)
        train_mask = train_mask.to(model_manager.device)
        val_mask = val_mask.to(model_manager.device)

        model = model_manager.models[model_name]
        model.train()
        optimizer = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=5e-4)

        epochs = int(os.getenv("GNN_TRAIN_EPOCHS", "200"))
        for epoch in range(epochs):
            optimizer.zero_grad()
            out = model(data.x, data.edge_index)
            loss = F.nll_loss(out[train_mask], data.y[train_mask])
            loss.backward()
            optimizer.step()

        # Evaluate
        model.eval()
        with torch.no_grad():
            out = model(data.x, data.edge_index)
            pred = out.argmax(dim=1)
            val_correct = int((pred[val_mask] == data.y[val_mask]).sum())
            val_total = int(val_mask.sum())
            val_accuracy = val_correct / val_total if val_total > 0 else 0.0

        metrics = {
            "val_accuracy": round(val_accuracy, 4),
            "final_loss": round(float(loss.item()), 4),
            "epochs": epochs,
            "training_nodes": int(train_mask.sum()),
            "validation_nodes": val_total,
            "dataset": config.TRAINING_DATA_PATH,
            "trained_at": datetime.now().isoformat(),
        }
        logger.info(f"Training completed for '{model_name}': {metrics}")

        model_manager.save_model(model_name)
        model_manager.mark_trained(model_name, metrics)
    except Exception as e:
        logger.error(f"GNN training failed for '{model_name}': {e}")

@app.get("/stats")
async def get_statistics():
    """Get service statistics"""
    uptime = (datetime.now() - stats["start_time"]).total_seconds()
    return {
        "uptime_seconds": int(uptime),
        "total_predictions": stats["total_predictions"],
        "fraud_detected": stats["fraud_detected"],
        "fraud_rate": stats["fraud_detected"] / max(stats["total_predictions"], 1),
        "model_version": stats["model_version"],
        "device": config.DEVICE,
        "models_loaded": len(model_manager.models),
        "models_trained": model_manager.trained
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
