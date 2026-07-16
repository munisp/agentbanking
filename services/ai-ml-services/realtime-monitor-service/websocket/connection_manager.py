"""
WebSocket Connection Manager
Nigerian Remittance Platform
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set, Optional
import json
import asyncio
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage WebSocket connections"""

    def __init__(self):
        # Active connections: {user_id: Set[WebSocket]}
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Connection metadata: {websocket_id: metadata}
        self.connection_metadata: Dict[int, Dict] = {}
        # Heartbeat tasks
        self.heartbeat_tasks: Dict[int, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept new WebSocket connection"""
        await websocket.accept()
        
        # Add to active connections
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        
        # Store metadata
        ws_id = id(websocket)
        self.connection_metadata[ws_id] = {
            "user_id": user_id,
            "connected_at": datetime.utcnow(),
            "last_heartbeat": datetime.utcnow()
        }
        
        # Start heartbeat task
        self.heartbeat_tasks[ws_id] = asyncio.create_task(
            self._heartbeat_loop(websocket, ws_id)
        )
        
        logger.info(f"WebSocket connected: user={user_id}, total_connections={self.get_connection_count()}")

    def disconnect(self, websocket: WebSocket, user_id: str):
        """Remove WebSocket connection"""
        ws_id = id(websocket)
        
        # Cancel heartbeat task
        if ws_id in self.heartbeat_tasks:
            self.heartbeat_tasks[ws_id].cancel()
            del self.heartbeat_tasks[ws_id]
        
        # Remove from active connections
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        # Remove metadata
        if ws_id in self.connection_metadata:
            del self.connection_metadata[ws_id]
        
        logger.info(f"WebSocket disconnected: user={user_id}, total_connections={self.get_connection_count()}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to specific WebSocket"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")

    async def send_to_user(self, message: dict, user_id: str):
        """Send message to all connections of a specific user"""
        if user_id in self.active_connections:
            disconnected = set()
            for websocket in self.active_connections[user_id]:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send to user {user_id}: {e}")
                    disconnected.add(websocket)
            
            # Clean up disconnected websockets
            for ws in disconnected:
                self.disconnect(ws, user_id)

    async def broadcast(self, message: dict, exclude_user: Optional[str] = None):
        """Broadcast message to all connected clients"""
        disconnected = []
        
        for user_id, websockets in self.active_connections.items():
            if exclude_user and user_id == exclude_user:
                continue
            
            for websocket in websockets:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to broadcast to {user_id}: {e}")
                    disconnected.append((websocket, user_id))
        
        # Clean up disconnected websockets
        for ws, user_id in disconnected:
            self.disconnect(ws, user_id)

    async def broadcast_to_dashboard(self, message_type: str, data: any):
        """Broadcast dashboard update to all connections"""
        message = {
            "type": message_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast(message)
        logger.debug(f"Broadcasted {message_type} to {self.get_connection_count()} connections")

    def get_connection_count(self) -> int:
        """Get total number of active connections"""
        return sum(len(connections) for connections in self.active_connections.values())

    def get_user_count(self) -> int:
        """Get number of unique connected users"""
        return len(self.active_connections)

    def is_user_connected(self, user_id: str) -> bool:
        """Check if user has any active connections"""
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0

    async def _heartbeat_loop(self, websocket: WebSocket, ws_id: int):
        """Send periodic heartbeat to keep connection alive"""
        try:
            while True:
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                
                try:
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                    # Update last heartbeat time
                    if ws_id in self.connection_metadata:
                        self.connection_metadata[ws_id]["last_heartbeat"] = datetime.utcnow()
                    
                except Exception as e:
                    logger.error(f"Heartbeat failed for ws_id={ws_id}: {e}")
                    break
        except asyncio.CancelledError:
            logger.debug(f"Heartbeat task cancelled for ws_id={ws_id}")

    async def handle_client_message(self, websocket: WebSocket, user_id: str, data: dict):
        """Handle messages from client"""
        message_type = data.get("type")
        
        if message_type == "heartbeat":
            # Client heartbeat - update last heartbeat time
            ws_id = id(websocket)
            if ws_id in self.connection_metadata:
                self.connection_metadata[ws_id]["last_heartbeat"] = datetime.utcnow()
            
            # Send heartbeat response
            await self.send_personal_message({
                "type": "heartbeat",
                "timestamp": datetime.utcnow().isoformat()
            }, websocket)
        
        elif message_type == "ping":
            # Ping-pong for latency testing
            await self.send_personal_message({
                "type": "pong",
                "timestamp": datetime.utcnow().isoformat()
            }, websocket)
        
        else:
            logger.warning(f"Unknown message type from user {user_id}: {message_type}")

    def get_stats(self) -> dict:
        """Get connection statistics"""
        return {
            "total_connections": self.get_connection_count(),
            "unique_users": self.get_user_count(),
            "connections_by_user": {
                user_id: len(connections) 
                for user_id, connections in self.active_connections.items()
            }
        }


# Global connection manager instance
manager = ConnectionManager()
