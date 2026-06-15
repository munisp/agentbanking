import sys as _sys, os as _os

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

_shutdown_handlers = []

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

apply_middleware(app, enable_auth=True)
setup_logging("neural-network-service")
app.include_router(metrics_router)

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


# ── OpenTelemetry Tracing ────────────────────────────────────────────────────
_otel_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
if _otel_endpoint:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        _resource = Resource.create({
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "neural-network-service"),
            "service.version": os.environ.get("OTEL_SERVICE_VERSION", "1.0.0"),
            "deployment.environment": os.environ.get("ENVIRONMENT", "production"),
        })
        _provider = TracerProvider(resource=_resource)
        _exporter = OTLPSpanExporter(endpoint=f"{_otel_endpoint}/v1/traces")
        _provider.add_span_processor(BatchSpanProcessor(_exporter))
        trace.set_tracer_provider(_provider)
        logging.getLogger(__name__).info(f"[OTel] Tracing enabled → {_otel_endpoint}")
    except ImportError:
        logging.getLogger(__name__).warning("[OTel] opentelemetry packages not installed — tracing disabled")

app = FastAPI(
# Instrument FastAPI with OpenTelemetry
if _otel_endpoint:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except (ImportError, Exception):
        pass


import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/neural_network_service")

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id SERIAL PRIMARY KEY,
        action TEXT, entity_id TEXT, data TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS state_store (
        key TEXT PRIMARY KEY, value TEXT,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.commit()
    conn.close()

init_db()

def log_audit(action: str, entity_id: str, data: str = ""):
    try:
        conn = get_db()
        conn.execute("INSERT INTO audit_log (action, entity_id, data) VALUES (%s, %s, %s)", (action, entity_id, data))
        conn.commit()
        conn.close()
    except Exception:
        pass
    title="Neural Network Service",
    description="Production-ready Multi-purpose Deep Learning Service",
    version="2.0.0"
)

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

