"""Recurring Payments Service - Production Implementation"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import uuid, os, logging, httpx

logger = logging.getLogger(__name__)
PAYMENT_API = os.getenv("PAYMENT_SERVICE_URL", "http://localhost:8000/api/v1/payment")
NOTIFICATION_API = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8000/api/v1/notification-service")
schedules_db: Dict[str, Dict] = {}

async def create(data: Dict[str, Any]) -> Dict[str, Any]:
    sid = str(uuid.uuid4())
    schedules_db[sid] = {**data, "id": sid, "status": "active", "created_at": datetime.utcnow().isoformat()}
    return schedules_db[sid]

async def get_by_id(item_id: str) -> Optional[Dict[str, Any]]:
    return schedules_db.get(item_id)

async def get_all() -> List[Dict[str, Any]]:
    return list(schedules_db.values())

async def update(item_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if item_id in schedules_db:
        schedules_db[item_id].update(data)
        return schedules_db[item_id]
    return None

async def delete(item_id: str) -> bool:
    return schedules_db.pop(item_id, None) is not None

async def create_schedule(user_id: str, amount: float, currency: str, recipient: str, frequency: str, start_date: str) -> Dict:
    schedule = {"id": str(uuid.uuid4()), "user_id": user_id, "amount": amount, "currency": currency, "recipient": recipient, "frequency": frequency, "start_date": start_date, "status": "active", "next_execution": start_date, "created_at": datetime.utcnow().isoformat(), "execution_count": 0, "last_executed": None}
    schedules_db[schedule["id"]] = schedule
    return schedule

async def execute_scheduled_payment(schedule_id: str) -> Dict:
    schedule = schedules_db.get(schedule_id)
    if not schedule or schedule["status"] != "active":
        return {"success": False, "error": "Schedule not found or inactive"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(PAYMENT_API, json={"amount": schedule["amount"], "currency": schedule["currency"], "recipient": schedule["recipient"], "idempotency_key": f"{schedule_id}-{schedule['execution_count']+1}"})
            result = resp.json()
        schedule["execution_count"] += 1
        schedule["last_executed"] = datetime.utcnow().isoformat()
        freq_map = {"daily": 1, "weekly": 7, "biweekly": 14, "monthly": 30}
        days = freq_map.get(schedule["frequency"], 30)
        schedule["next_execution"] = (datetime.utcnow() + timedelta(days=days)).isoformat()
        return {"success": True, "payment": result, "next_execution": schedule["next_execution"]}
    except Exception as e:
        logger.error(f"Payment execution failed for {schedule_id}: {e}")
        return {"success": False, "error": str(e)}

async def pause_schedule(schedule_id: str) -> Dict:
    if schedule_id in schedules_db:
        schedules_db[schedule_id]["status"] = "paused"
        return {"success": True, "status": "paused"}
    return {"success": False, "error": "Not found"}

async def resume_schedule(schedule_id: str) -> Dict:
    if schedule_id in schedules_db and schedules_db[schedule_id]["status"] == "paused":
        schedules_db[schedule_id]["status"] = "active"
        return {"success": True, "status": "active"}
    return {"success": False, "error": "Not found or not paused"}

async def cancel_schedule(schedule_id: str) -> Dict:
    if schedule_id in schedules_db:
        schedules_db[schedule_id]["status"] = "cancelled"
        return {"success": True, "status": "cancelled"}
    return {"success": False, "error": "Not found"}

async def edit_schedule(schedule_id: str, updates: Dict[str, Any]) -> Dict:
    if schedule_id in schedules_db:
        for k, v in updates.items():
            if k in {"amount", "currency", "recipient", "frequency"}:
                schedules_db[schedule_id][k] = v
        return {"success": True, "schedule": schedules_db[schedule_id]}
    return {"success": False, "error": "Not found"}
