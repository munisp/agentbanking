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

_shutdown_handlers = _PgListStore("neural_network_service__shutdown_handlers", "NEURAL_NETWORK_SERVICE_DATABASE_URL")  # round-11 wave-7 persistence

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
Production-Ready Neural Network Service
Multi-purpose deep learning service for Remittance Platform
Supports multiple architectures: CNN, RNN, LSTM, Transformer, BERT
"""
import os
import logging
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware


from pydantic import BaseModel, Field
from transformers import BertTokenizer, BertForSequenceClassification
from transformers import AutoTokenizer, AutoModel
import joblib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Neural Network Service",
    description="Production-ready Multi-purpose Deep Learning Service",
    version="2.0.0"
)

apply_middleware(app)
setup_logging("neural-network-service")
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
    MODEL_PATH = os.getenv("NN_MODEL_PATH", "/models/neural_networks")
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    MODEL_VERSION = "2.0.0"
    MAX_SEQ_LENGTH = 512
    
config = Config()

# Statistics
stats = {
    "total_predictions": 0,
    "models_loaded": 0,
    "start_time": datetime.now()
}

# ==================== Neural Network Models ====================

class LSTMClassifier(nn.Module):
    """LSTM for sequence classification"""
    def __init__(self, input_dim, hidden_dim=128, num_layers=2, num_classes=2, dropout=0.3):
        super(LSTMClassifier, self).__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        
        self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers, 
                           batch_first=True, dropout=dropout, bidirectional=True)
        self.fc = nn.Linear(hidden_dim * 2, num_classes)  # *2 for bidirectional
        self.dropout = nn.Dropout(dropout)
        
    def forward(self, x):
        # x shape: (batch, seq_len, input_dim)
        lstm_out, (h_n, c_n) = self.lstm(x)
        
        # Use last hidden state
        # h_n shape: (num_layers * 2, batch, hidden_dim)
        h_n = h_n.view(self.num_layers, 2, -1, self.hidden_dim)  # Separate directions
        last_hidden = torch.cat([h_n[-1, 0, :, :], h_n[-1, 1, :, :]], dim=1)  # Concat forward and backward
        
        out = self.dropout(last_hidden)
        out = self.fc(out)
        return out

class TransactionCNN(nn.Module):
    """CNN for transaction pattern recognition"""
    def __init__(self, input_dim, num_classes=2):
        super(TransactionCNN, self).__init__()
        self.conv1 = nn.Conv1d(input_dim, 64, kernel_size=3, padding=1)
        self.conv2 = nn.Conv1d(64, 128, kernel_size=3, padding=1)
        self.conv3 = nn.Conv1d(128, 256, kernel_size=3, padding=1)
        self.pool = nn.MaxPool1d(2)
        self.dropout = nn.Dropout(0.5)
        self.fc1 = nn.Linear(256, 128)
        self.fc2 = nn.Linear(128, num_classes)
        
    def forward(self, x):
        # x shape: (batch, seq_len, input_dim)
        x = x.transpose(1, 2)  # (batch, input_dim, seq_len)
        
        x = F.relu(self.conv1(x))
        x = self.pool(x)
        x = F.relu(self.conv2(x))
        x = self.pool(x)
        x = F.relu(self.conv3(x))
        x = F.adaptive_avg_pool1d(x, 1).squeeze(-1)
        
        x = self.dropout(x)
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.fc2(x)
        return x

class TransformerClassifier(nn.Module):
    """Transformer for sequence classification"""
    def __init__(self, input_dim, num_classes=2, d_model=128, nhead=4, num_layers=2):
        super(TransformerClassifier, self).__init__()
        self.embedding = nn.Linear(input_dim, d_model)
        self.pos_encoder = PositionalEncoding(d_model)
        encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead)
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.fc = nn.Linear(d_model, num_classes)
        
    def forward(self, x):
        # x shape: (batch, seq_len, input_dim)
        x = self.embedding(x)
        x = self.pos_encoder(x)
        x = x.transpose(0, 1)  # (seq_len, batch, d_model)
        x = self.transformer(x)
        x = x.mean(dim=0)  # Average over sequence
        x = self.fc(x)
        return x

class PositionalEncoding(nn.Module):
    """Positional encoding for Transformer"""
    def __init__(self, d_model, max_len=5000):
        super(PositionalEncoding, self).__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-np.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)
        self.register_buffer('pe', pe)
        
    def forward(self, x):
        return x + self.pe[:, :x.size(1), :]

# ==================== Model Manager ====================

class NeuralNetworkManager:
    """Manages neural network models"""
    def __init__(self):
        self.device = torch.device(config.DEVICE)
        self.models = {}
        self.tokenizers = {}
        self.load_models()
        
    def load_models(self):
        """Load all neural network models"""
        try:
            model_path = Path(config.MODEL_PATH)
            model_path.mkdir(parents=True, exist_ok=True)
            
            # Load LSTM model
            self.models['lstm'] = LSTMClassifier(input_dim=32).to(self.device)
            self._load_weights('lstm')
            
            # Load CNN model
            self.models['cnn'] = TransactionCNN(input_dim=32).to(self.device)
            self._load_weights('cnn')
            
            # Load Transformer model
            self.models['transformer'] = TransformerClassifier(input_dim=32).to(self.device)
            self._load_weights('transformer')
            
            # Load BERT model for text classification
            try:
                self.tokenizers['bert'] = BertTokenizer.from_pretrained('bert-base-uncased')
                self.models['bert'] = BertForSequenceClassification.from_pretrained(
                    'bert-base-uncased',
                    num_labels=2
                ).to(self.device)
                logger.info("Loaded BERT model")
            except Exception as e:
                logger.warning(f"Could not load BERT: {e}")
            
            # Set all models to eval mode
            for model in self.models.values():
                model.eval()
            
            stats["models_loaded"] = len(self.models)
            logger.info(f"Loaded {len(self.models)} neural network models on {self.device}")
            
        except Exception as e:
            logger.error(f"Error loading models: {e}")
            raise
    
    def _load_weights(self, model_name: str):
        """Load model weights from model registry or local storage"""
        # Try model registry first (S3, MLflow, etc.)
        registry_url = os.getenv("MODEL_REGISTRY_URL", "")
        if registry_url:
            try:
                weight_path = self._download_from_registry(model_name, registry_url)
                if weight_path:
                    self.models[model_name].load_state_dict(
                        torch.load(weight_path, map_location=self.device)
                    )
                    logger.info(f"Loaded {model_name} weights from model registry")
                    return
            except Exception as e:
                logger.warning(f"Failed to load {model_name} from registry: {e}")
        
        # Try local weights
        weight_path = Path(config.MODEL_PATH) / f"{model_name}_weights.pt"
        if weight_path.exists():
            self.models[model_name].load_state_dict(
                torch.load(weight_path, map_location=self.device)
            )
            logger.info(f"Loaded {model_name} weights from local storage")
            return
        
        # Try to download pre-trained weights from HuggingFace or similar
        pretrained_url = os.getenv(f"{model_name.upper()}_PRETRAINED_URL", "")
        if pretrained_url:
            try:
                import urllib.request
                local_path = Path(config.MODEL_PATH) / f"{model_name}_weights.pt"
                urllib.request.urlretrieve(pretrained_url, local_path)
                self.models[model_name].load_state_dict(
                    torch.load(local_path, map_location=self.device)
                )
                logger.info(f"Downloaded and loaded {model_name} pre-trained weights")
                return
            except Exception as e:
                logger.warning(f"Failed to download pre-trained weights for {model_name}: {e}")
        
        # Initialize with Xavier/Kaiming initialization for better convergence
        logger.warning(f"No saved weights for {model_name}, using Xavier/Kaiming initialization")
        self._initialize_weights(self.models[model_name])
    
    def _initialize_weights(self, model: nn.Module):
        """Initialize model weights using Xavier/Kaiming initialization"""
        for name, param in model.named_parameters():
            if 'weight' in name:
                if 'lstm' in name.lower() or 'rnn' in name.lower():
                    nn.init.orthogonal_(param)
                elif len(param.shape) >= 2:
                    nn.init.xavier_uniform_(param)
                else:
                    nn.init.normal_(param, mean=0, std=0.01)
            elif 'bias' in name:
                nn.init.zeros_(param)
    
    def _download_from_registry(self, model_name: str, registry_url: str) -> Optional[Path]:
        """Download model weights from model registry"""
        import urllib.request
        try:
            model_version = os.getenv(f"{model_name.upper()}_VERSION", "latest")
            download_url = f"{registry_url}/models/{model_name}/{model_version}/weights.pt"
            local_path = Path(config.MODEL_PATH) / f"{model_name}_weights.pt"
            urllib.request.urlretrieve(download_url, local_path)
            return local_path
        except Exception as e:
            logger.warning(f"Failed to download from registry: {e}")
            return None
    
    def predict_sequence(self, sequences: np.ndarray, model_name: str = 'lstm') -> Dict[str, Any]:
        """Predict using sequence model (LSTM, CNN, Transformer)"""
        if model_name not in ['lstm', 'cnn', 'transformer']:
            raise ValueError(f"Invalid model: {model_name}")
        
        model = self.models[model_name]
        model.eval()
        
        with torch.no_grad():
            # Convert to tensor
            x = torch.tensor(sequences, dtype=torch.float32).to(self.device)
            
            # Forward pass
            outputs = model(x)
            probs = F.softmax(outputs, dim=1)
            predictions = torch.argmax(probs, dim=1)
            
            return {
                "predictions": predictions.cpu().numpy().tolist(),
                "probabilities": probs.cpu().numpy().tolist(),
                "model": model_name
            }
    
    def predict_text(self, texts: List[str]) -> Dict[str, Any]:
        """Predict using BERT model"""
        if 'bert' not in self.models:
            raise ValueError("BERT model not loaded")
        
        model = self.models['bert']
        tokenizer = self.tokenizers['bert']
        model.eval()
        
        with torch.no_grad():
            # Tokenize
            inputs = tokenizer(
                texts,
                padding=True,
                truncation=True,
                max_length=config.MAX_SEQ_LENGTH,
                return_tensors="pt"
            ).to(self.device)
            
            # Forward pass
            outputs = model(**inputs)
            probs = F.softmax(outputs.logits, dim=1)
            predictions = torch.argmax(probs, dim=1)
            
            return {
                "predictions": predictions.cpu().numpy().tolist(),
                "probabilities": probs.cpu().numpy().tolist(),
                "model": "bert"
            }

# Initialize model manager
model_manager = NeuralNetworkManager()

# ==================== API Models ====================

class SequencePredictionRequest(BaseModel):
    sequences: List[List[List[float]]]  # (batch, seq_len, features)
    model_name: str = Field(default="lstm", description="Model: lstm, cnn, or transformer")

class TextPredictionRequest(BaseModel):
    texts: List[str]

class PredictionResponse(BaseModel):
    predictions: List[int]
    probabilities: List[List[float]]
    model: str

# ==================== API Endpoints ====================

@app.get("/")
async def root():
    return {
        "service": "neural-network-service",
        "version": config.MODEL_VERSION,
        "device": config.DEVICE,
        "models": list(model_manager.models.keys()),
        "status": "ready"
    }

@app.get("/health")
async def health_check():
    uptime = (datetime.now() - stats["start_time"]).total_seconds()
    return {
        "status": "healthy",
        "uptime_seconds": int(uptime),
        "device": config.DEVICE,
        "models_loaded": stats["models_loaded"],
        "total_predictions": stats["total_predictions"]
    }

@app.post("/predict/sequence", response_model=PredictionResponse)
async def predict_sequence(request: SequencePredictionRequest):
    """Predict using sequence models (LSTM, CNN, Transformer)"""
    try:
        stats["total_predictions"] += 1
        
        sequences = np.array(request.sequences)
        result = model_manager.predict_sequence(sequences, request.model_name)
        
        return PredictionResponse(**result)
        
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/predict/text", response_model=PredictionResponse)
async def predict_text(request: TextPredictionRequest):
    """Predict using BERT text classifier"""
    try:
        stats["total_predictions"] += 1
        
        result = model_manager.predict_text(request.texts)
        
        return PredictionResponse(**result)
        
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/models")
async def list_models():
    """List available models"""
    models_info = []
    for name, model in model_manager.models.items():
        params = sum(p.numel() for p in model.parameters())
        models_info.append({
            "name": name,
            "parameters": params,
            "device": str(next(model.parameters()).device)
        })
    
    return {"models": models_info, "device": config.DEVICE}

@app.get("/stats")
async def get_statistics():
    """Get service statistics"""
    uptime = (datetime.now() - stats["start_time"]).total_seconds()
    return {
        "uptime_seconds": int(uptime),
        "total_predictions": stats["total_predictions"],
        "models_loaded": stats["models_loaded"],
        "device": config.DEVICE
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)

