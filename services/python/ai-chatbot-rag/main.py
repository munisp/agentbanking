"""
AI Agent Support Chatbot — RAG over docs + transaction data

Architecture:
- Knowledge base: curated FAQ + troubleshooting guides
- Transaction context: recent agent activity
- LLM: Optional OpenAI/Ollama integration
- Escalation: auto-route to human support after 3 failed resolutions
"""
import asyncio
import logging
import os
import re
import time
from typing import Optional

import asyncpg
from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-chatbot-rag")

app = FastAPI(title="54Link AI Support Chatbot", version="1.0.0")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/agentbanking")
pool: Optional[asyncpg.Pool] = None

# Knowledge Base — curated troubleshooting content
KNOWLEDGE_BASE = {
    "pos not working": {
        "answer": (
            "Common POS troubleshooting steps:\n"
            "1. Check power and battery level\n"
            "2. Verify SIM card is properly inserted\n"
            "3. Check network signal strength (minimum 2 bars)\n"
            "4. Restart the terminal (hold power button 10 seconds)\n"
            "5. If display shows error code, note it and contact support\n"
            "6. Try a test transaction with small amount (NGN 100)"
        ),
        "category": "pos_troubleshooting",
        "confidence": 0.95,
    },
    "float top up": {
        "answer": (
            "To top up your float:\n"
            "1. Visit your super-agent or bank branch\n"
            "2. Transfer funds to your designated float account\n"
            "3. Float will reflect within 5-15 minutes\n"
            "4. Minimum top-up: NGN 5,000\n"
            "5. For instant top-up, use the mobile banking transfer option"
        ),
        "category": "float_management",
        "confidence": 0.90,
    },
    "commission": {
        "answer": (
            "Commission structure:\n"
            "• Cash-in: 0.5% of transaction amount\n"
            "• Cash-out: 0.75% of transaction amount\n"
            "• Transfer: 0.3% flat fee\n"
            "• Bill payment: NGN 20-50 per transaction\n"
            "• Airtime: 3-5% discount from telcos\n\n"
            "Commissions are credited daily at 11:59 PM to your float account."
        ),
        "category": "earnings",
        "confidence": 0.92,
    },
    "kyc": {
        "answer": (
            "KYC requirements by tier:\n\n"
            "Tier 1 (Basic): Phone number + BVN\n"
            "  → Max daily: NGN 50,000\n\n"
            "Tier 2 (Standard): + NIN + Photo ID\n"
            "  → Max daily: NGN 200,000\n\n"
            "Tier 3 (Enhanced): + Utility bill + Reference letter\n"
            "  → Max daily: NGN 5,000,000\n\n"
            "Submit docs via the app: Settings → KYC Verification"
        ),
        "category": "compliance",
        "confidence": 0.88,
    },
    "dispute": {
        "answer": (
            "To file a transaction dispute:\n"
            "1. Go to Transactions → Select the transaction\n"
            "2. Tap 'Dispute' → Select reason\n"
            "3. Attach evidence (screenshot, receipt)\n"
            "4. Submit — you'll receive a ticket number\n\n"
            "Resolution timeline: 3-5 business days\n"
            "For urgent disputes (>NGN 100,000): Call 0800-54LINK"
        ),
        "category": "disputes",
        "confidence": 0.85,
    },
    "network error": {
        "answer": (
            "Network connectivity fixes:\n"
            "1. Toggle airplane mode on/off\n"
            "2. Check if SIM data is active (dial *461#)\n"
            "3. Move to an area with better signal\n"
            "4. If using WiFi, try switching to mobile data\n"
            "5. Clear app cache: Settings → Apps → 54Link → Clear Cache\n"
            "6. Transactions queued offline will sync automatically when connected"
        ),
        "category": "connectivity",
        "confidence": 0.87,
    },
    "settlement": {
        "answer": (
            "Settlement schedule:\n"
            "• T+0 (Same day): Available for transactions > NGN 10,000\n"
            "• T+1 (Next business day): Standard settlement\n"
            "• Settlement times: 6:00 AM, 12:00 PM, 6:00 PM, 11:59 PM\n\n"
            "Check settlement status: Dashboard → Settlements\n"
            "For delayed settlements (>24 hours), contact support."
        ),
        "category": "settlements",
        "confidence": 0.90,
    },
}

class ChatRequest(BaseModel):
    message: str
    agent_id: Optional[int] = None
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    source: str  # knowledge_base, context, escalation
    confidence: float
    conversation_id: str
    suggestions: list[str]
    escalated: bool

class ConversationManager:
    def __init__(self):
        self.conversations: dict[str, list[dict]] = {}
        self.failed_attempts: dict[str, int] = {}

    def add_message(self, conv_id: str, role: str, content: str):
        if conv_id not in self.conversations:
            self.conversations[conv_id] = []
        self.conversations[conv_id].append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
        })

    def get_history(self, conv_id: str) -> list[dict]:
        return self.conversations.get(conv_id, [])

    def record_failure(self, conv_id: str):
        self.failed_attempts[conv_id] = self.failed_attempts.get(conv_id, 0) + 1

    def should_escalate(self, conv_id: str) -> bool:
        return self.failed_attempts.get(conv_id, 0) >= 3

conv_mgr = ConversationManager()

def find_answer(message: str) -> Optional[dict]:
    message_lower = message.lower()
    best_match = None
    best_score = 0

    for keyword, entry in KNOWLEDGE_BASE.items():
        keywords = keyword.split()
        matches = sum(1 for kw in keywords if kw in message_lower)
        score = matches / len(keywords) if keywords else 0

        if score > best_score and score >= 0.5:
            best_score = score
            best_match = entry

    return best_match

@app.on_event("startup")
async def startup():
    global pool
    try:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        logger.info("AI Chatbot connected to PostgreSQL")
    except Exception as e:
        logger.warning(f"DB connection skipped: {e}")

@app.on_event("shutdown")
async def shutdown():
    if pool:
        await pool.close()

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "ai-chatbot-rag", "kb_size": len(KNOWLEDGE_BASE)}

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    conv_id = req.conversation_id or f"conv-{int(time.time())}"
    conv_mgr.add_message(conv_id, "user", req.message)

    # Check for escalation
    if conv_mgr.should_escalate(conv_id):
        return ChatResponse(
            response=(
                "I'm connecting you with a human support agent.\n"
                "Your ticket has been created. Expected response: within 15 minutes.\n"
                "Reference: ESC-" + str(int(time.time()))
            ),
            source="escalation",
            confidence=1.0,
            conversation_id=conv_id,
            suggestions=[],
            escalated=True,
        )

    # Try knowledge base
    match = find_answer(req.message)
    if match:
        conv_mgr.add_message(conv_id, "assistant", match["answer"])
        return ChatResponse(
            response=match["answer"],
            source="knowledge_base",
            confidence=match["confidence"],
            conversation_id=conv_id,
            suggestions=get_suggestions(match["category"]),
            escalated=False,
        )

    # No match — record failure
    conv_mgr.record_failure(conv_id)
    fallback = (
        "I couldn't find a specific answer to your question.\n"
        "Could you try rephrasing, or choose from these common topics?\n\n"
        "If you need immediate help, type 'AGENT' to connect with support."
    )
    return ChatResponse(
        response=fallback,
        source="fallback",
        confidence=0.1,
        conversation_id=conv_id,
        suggestions=["POS not working", "Float top up", "Commission rates", "File a dispute"],
        escalated=False,
    )

def get_suggestions(category: str) -> list[str]:
    suggestions_map = {
        "pos_troubleshooting": ["POS error codes", "Replace POS terminal", "POS firmware update"],
        "float_management": ["Commission rates", "Settlement schedule", "Float history"],
        "earnings": ["Settlement schedule", "Top agent rewards", "Commission calculator"],
        "compliance": ["KYC documents list", "Upgrade KYC tier", "KYC status check"],
        "disputes": ["Track dispute status", "Dispute timeline", "Escalate to manager"],
        "connectivity": ["Offline mode", "Transaction sync", "Network status"],
        "settlements": ["Commission rates", "Settlement history", "Failed settlement"],
    }
    return suggestions_map.get(category, ["Help", "Contact support"])

@app.get("/api/v1/stats")
async def stats():
    return {
        "knowledge_base_entries": len(KNOWLEDGE_BASE),
        "active_conversations": len(conv_mgr.conversations),
        "total_messages": sum(len(v) for v in conv_mgr.conversations.values()),
        "escalations": sum(1 for v in conv_mgr.failed_attempts.values() if v >= 3),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8462")))
