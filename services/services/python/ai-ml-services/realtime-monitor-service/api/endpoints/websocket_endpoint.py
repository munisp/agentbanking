"""
WebSocket Endpoint
Nigerian Remittance Platform
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from websocket.connection_manager import manager
from core.auth import get_current_user_from_token
from typing import Optional
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/dashboard")
async def websocket_dashboard_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for real-time dashboard updates
    
    Query Parameters:
    - token: JWT authentication token
    
    Message Types (Server -> Client):
    - heartbeat: Keep-alive ping
    - transaction_update: New or updated transaction
    - metrics_update: Updated dashboard metrics
    - alert: New alert notification
    
    Message Types (Client -> Server):
    - heartbeat: Keep-alive response
    - ping: Latency test
    """
    user_id = None
    
    try:
        # Authenticate user from token
        if not token:
            await websocket.close(code=4001, reason="Authentication required")
            return
        
        try:
            user = await get_current_user_from_token(token)
            user_id = user.get("user_id")
            
            if not user_id:
                await websocket.close(code=4001, reason="Invalid token")
                return
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            await websocket.close(code=4001, reason="Authentication failed")
            return
        
        # Accept connection
        await manager.connect(websocket, user_id)
        
        # Send welcome message
        await manager.send_personal_message({
            "type": "connected",
            "message": "Connected to dashboard WebSocket",
            "user_id": user_id
        }, websocket)
        
        # Listen for messages
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_json()
                
                # Handle client message
                await manager.handle_client_message(websocket, user_id, data)
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected normally: user={user_id}")
                break
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from user {user_id}: {e}")
                await manager.send_personal_message({
                    "type": "error",
                    "message": "Invalid JSON format"
                }, websocket)
            except Exception as e:
                logger.error(f"Error handling message from user {user_id}: {e}")
                break
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    
    finally:
        # Disconnect
        if user_id:
            manager.disconnect(websocket, user_id)


@router.get("/ws/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics"""
    return {
        "status": "success",
        "data": manager.get_stats()
    }
