"""
FAQ API Endpoints
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api/faq", tags=["faq"])

class FAQ(BaseModel):
    id: int
    question: str
    answer: str
    category: str
    helpful_count: int
    views: int
    related_articles: List[int]

class FAQListResponse(BaseModel):
    faqs: List[FAQ]
    total: int
    categories: List[str]

@router.get("/", response_model=FAQListResponse)
async def get_faqs(category: Optional[str] = None, q: Optional[str] = None):
    """Get FAQs with optional filtering."""
    faqs = [
        {
            "id": 1,
            "question": "What should I do if my transfer failed?",
            "answer": "If your transfer failed, please check your transaction history. If the amount was deducted, file a dispute and we'll investigate within 24 hours.",
            "category": "transfers",
            "helpful_count": 245,
            "views": 1520,
            "related_articles": [2, 5, 8]
        },
        {
            "id": 2,
            "question": "How long does a domestic transfer take?",
            "answer": "Domestic transfers via NIBSS typically complete within 30 seconds. You'll receive a confirmation SMS once completed.",
            "category": "transfers",
            "helpful_count": 189,
            "views": 980,
            "related_articles": [1, 3]
        }
    ]
    
    # Filter by category if provided
    if category:
        faqs = [f for f in faqs if f["category"] == category]
    
    # Filter by search query if provided
    if q:
        q_lower = q.lower()
        faqs = [f for f in faqs if q_lower in f["question"].lower() or q_lower in f["answer"].lower()]
    
    return {
        "faqs": faqs,
        "total": len(faqs),
        "categories": ["transfers", "wallet", "kyc", "savings"]
    }
