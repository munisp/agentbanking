"""
Agent Hierarchy Management - FastAPI microservice
Manages multi-level agent hierarchies, territory assignments, and upline/downline relationships
"""
import os
import sys
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Agent Hierarchy Management",
    description="Manages multi-level agent hierarchies, territory assignments, and upline/downline relationships",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Service health check endpoint."""
    return {"status": "healthy", "service": "agent-hierarchy-service", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/v1/hierarchy/{agent_id}")
async def get_hierarchy(agent_id: str):
    """Get agent's position in the hierarchy tree."""
    return {
        "agent_id": agent_id,
        "level": "agent",
        "upline": None,
        "downline_count": 0,
        "territory": None,
        "region": None,
        "commission_tier": "standard",
    }

@app.get("/api/v1/hierarchy/{agent_id}/downline")
async def get_downline(agent_id: str, depth: int = 1):
    """Get agent's downline tree up to specified depth."""
    if depth > 5:
        raise HTTPException(status_code=400, detail="Maximum depth is 5 levels")
    return {
        "agent_id": agent_id,
        "depth": depth,
        "downline": [],
        "total_agents": 0,
    }

@app.post("/api/v1/hierarchy/assign")
async def assign_territory(agent_id: str, territory_id: str, effective_date: str = None):
    """Assign agent to a territory."""
    return {
        "agent_id": agent_id,
        "territory_id": territory_id,
        "effective_date": effective_date or __import__('datetime').date.today().isoformat(),
        "status": "assigned",
    }

@app.post("/api/v1/hierarchy/promote")
async def promote_agent(agent_id: str, new_level: str, reason: str = ""):
    """Promote agent to a higher level in the hierarchy."""
    valid_levels = ["agent", "super_agent", "master_agent", "distributor", "regional_manager"]
    if new_level not in valid_levels:
        raise HTTPException(status_code=400, detail=f"Invalid level. Must be one of: {valid_levels}")
    return {
        "agent_id": agent_id,
        "previous_level": "agent",
        "new_level": new_level,
        "reason": reason,
        "effective_date": __import__('datetime').date.today().isoformat(),
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
