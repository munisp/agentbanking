"""
Router for epr-kgqa-service service
Auto-extracted from main.py for unified gateway registration
"""

from fastapi import APIRouter

router = APIRouter(prefix="/epr-kgqa-service", tags=["epr-kgqa-service"])

@router.get("/health")
async def health_check():
    return {"status": "ok"}

@router.post("/ask")
async def ask_question(question: Question):
    return {"status": "ok"}

@router.post("/entities/extract")
async def extract_entities(text: str):
    return {"status": "ok"}

@router.post("/relations/extract")
async def extract_relations(text: str):
    return {"status": "ok"}

@router.get("/entities/{entity_id}/neighbors")
async def get_neighbors(entity_id: str, depth: int = 2):
    return {"status": "ok"}

@router.post("/explain")
async def explain_reasoning(question: str, answer: str):
    return {"status": "ok"}

@router.get("/stats")
async def get_stats():
    return {"status": "ok"}

@router.post("/classify")
async def classify_question(text: str):
    return {"status": "ok"}

