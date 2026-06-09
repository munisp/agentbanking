"""
Router for ollama-service service
Auto-extracted from main.py for unified gateway registration
"""

from fastapi import APIRouter

router = APIRouter(prefix="/ollama-service", tags=["ollama-service"])

@router.get("/health")
async def health_check():
    return {"status": "ok"}

@router.post("/chat")
async def chat(request: ChatRequest):
    return {"status": "ok"}

@router.post("/completions")
async def generate(request: CompletionRequest):
    return {"status": "ok"}

@router.post("/embeddings")
async def embeddings(request: EmbeddingRequest):
    return {"status": "ok"}

@router.get("/models")
async def list_models():
    return {"status": "ok"}

@router.post("/models/pull")
async def pull_model(model_name: str, background_tasks: BackgroundTasks):
    return {"status": "ok"}

@router.post("/banking/assistant")
async def banking_assistant(query: BankingQuery):
    return {"status": "ok"}

@router.post("/banking/fraud-analysis")
async def fraud_analysis(transaction_data: Dict[str, Any]):
    return {"status": "ok"}

@router.post("/banking/classify-query")
async def classify_query(query: str):
    return {"status": "ok"}

