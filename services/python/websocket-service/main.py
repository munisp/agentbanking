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
WebSocket Service
Real-time bidirectional communication service for Remittance Platform
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("websocket-service")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import List, Dict, Optional, Set
from datetime import datetime
import logging
import json
import asyncio
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="WebSocket Service",
    description="Real-time bidirectional communication service",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connection Manager
class ConnectionManager:
    def __init__(self):
        # Store active connections by agent_id
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Store connection metadata
        self.connection_metadata: Dict[WebSocket, Dict] = {}
        # Store rooms for group messaging
        self.rooms: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, agent_id: str, metadata: Dict = None):
        """Connect a new WebSocket client"""
        await websocket.accept()
        
        if agent_id not in self.active_connections:
            self.active_connections[agent_id] = set()
        
        self.active_connections[agent_id].add(websocket)
        self.connection_metadata[websocket] = {
            "agent_id": agent_id,
            "connected_at": datetime.utcnow(),
            "metadata": metadata or {}
        }
        
        logger.info(f"Client connected: agent_id={agent_id}, total_connections={len(self.active_connections[agent_id])}")
    
    def disconnect(self, websocket: WebSocket):
        """Disconnect a WebSocket client"""
        if websocket in self.connection_metadata:
            metadata = self.connection_metadata[websocket]
            agent_id = metadata["agent_id"]
            
            if agent_id in self.active_connections:
                self.active_connections[agent_id].discard(websocket)
                if not self.active_connections[agent_id]:
                    del self.active_connections[agent_id]
            
            # Remove from all rooms
            for room_connections in self.rooms.values():
                room_connections.discard(websocket)
            
            del self.connection_metadata[websocket]
            
            logger.info(f"Client disconnected: agent_id={agent_id}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific WebSocket connection"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {str(e)}")
    
    async def send_to_agent(self, message: str, agent_id: str):
        """Send a message to all connections of a specific agent"""
        if agent_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[agent_id]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Error sending to agent {agent_id}: {str(e)}")
                    disconnected.add(connection)
            
            # Clean up disconnected connections
            for connection in disconnected:
                self.disconnect(connection)
    
    async def broadcast(self, message: str, exclude: Optional[WebSocket] = None):
        """Broadcast a message to all connected clients"""
        disconnected = set()
        for agent_connections in self.active_connections.values():
            for connection in agent_connections:
                if connection != exclude:
                    try:
                        await connection.send_text(message)
                    except Exception as e:
                        logger.error(f"Error broadcasting: {str(e)}")
                        disconnected.add(connection)
        
        # Clean up disconnected connections
        for connection in disconnected:
            self.disconnect(connection)
    
    async def join_room(self, websocket: WebSocket, room_id: str):
        """Add a WebSocket connection to a room"""
        if room_id not in self.rooms:
            self.rooms[room_id] = set()
        self.rooms[room_id].add(websocket)
        logger.info(f"Client joined room: room_id={room_id}")
    
    async def leave_room(self, websocket: WebSocket, room_id: str):
        """Remove a WebSocket connection from a room"""
        if room_id in self.rooms:
            self.rooms[room_id].discard(websocket)
            if not self.rooms[room_id]:
                del self.rooms[room_id]
            logger.info(f"Client left room: room_id={room_id}")
    
    async def send_to_room(self, message: str, room_id: str, exclude: Optional[WebSocket] = None):
        """Send a message to all connections in a room"""
        if room_id in self.rooms:
            disconnected = set()
            for connection in self.rooms[room_id]:
                if connection != exclude:
                    try:
                        await connection.send_text(message)
                    except Exception as e:
                        logger.error(f"Error sending to room {room_id}: {str(e)}")
                        disconnected.add(connection)
            
            # Clean up disconnected connections
            for connection in disconnected:
                self.disconnect(connection)
    
    def get_active_connections_count(self) -> int:
        """Get total number of active connections"""
        return sum(len(connections) for connections in self.active_connections.values())
    
    def get_agent_connections_count(self, agent_id: str) -> int:
        """Get number of connections for a specific agent"""
        return len(self.active_connections.get(agent_id, set()))

manager = ConnectionManager()

# Models
class Message(BaseModel):
    type: str  # personal, broadcast, room
    content: str
    agent_id: Optional[str] = None
    room_id: Optional[str] = None
    timestamp: Optional[datetime] = None

class ConnectionInfo(BaseModel):
    agent_id: str
    connection_count: int
    connected_at: datetime

# API Endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "websocket-service",
        "timestamp": datetime.utcnow().isoformat(),
        "active_connections": manager.get_active_connections_count(),
        "active_agents": len(manager.active_connections),
        "active_rooms": len(manager.rooms)
    }

@app.get("/connections")
async def list_connections():
    """List all active connections"""
    connections = []
    for agent_id, agent_connections in manager.active_connections.items():
        for connection in agent_connections:
            if connection in manager.connection_metadata:
                metadata = manager.connection_metadata[connection]
                connections.append({
                    "agent_id": agent_id,
                    "connected_at": metadata["connected_at"].isoformat(),
                    "metadata": metadata["metadata"]
                })
    return {"connections": connections, "total": len(connections)}

@app.get("/connections/{agent_id}")
async def get_agent_connections(agent_id: str):
    """Get connections for a specific agent"""
    count = manager.get_agent_connections_count(agent_id)
    return {
        "agent_id": agent_id,
        "connection_count": count,
        "is_online": count > 0
    }

@app.post("/send/agent/{agent_id}")
async def send_to_agent(agent_id: str, message: Message):
    """Send a message to a specific agent"""
    try:
        message.timestamp = datetime.utcnow()
        message_json = json.dumps({
            "type": "personal",
            "content": message.content,
            "timestamp": message.timestamp.isoformat()
        })
        
        await manager.send_to_agent(message_json, agent_id)
        
        return {
            "status": "sent",
            "agent_id": agent_id,
            "timestamp": message.timestamp.isoformat()
        }
    except Exception as e:
        logger.error(f"Error sending to agent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/send/broadcast")
async def broadcast_message(message: Message):
    """Broadcast a message to all connected clients"""
    try:
        message.timestamp = datetime.utcnow()
        message_json = json.dumps({
            "type": "broadcast",
            "content": message.content,
            "timestamp": message.timestamp.isoformat()
        })
        
        await manager.broadcast(message_json)
        
        return {
            "status": "broadcasted",
            "recipients": manager.get_active_connections_count(),
            "timestamp": message.timestamp.isoformat()
        }
    except Exception as e:
        logger.error(f"Error broadcasting: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/send/room/{room_id}")
async def send_to_room(room_id: str, message: Message):
    """Send a message to all clients in a room"""
    try:
        message.timestamp = datetime.utcnow()
        message_json = json.dumps({
            "type": "room",
            "room_id": room_id,
            "content": message.content,
            "timestamp": message.timestamp.isoformat()
        })
        
        await manager.send_to_room(message_json, room_id)
        
        return {
            "status": "sent",
            "room_id": room_id,
            "recipients": len(manager.rooms.get(room_id, set())),
            "timestamp": message.timestamp.isoformat()
        }
    except Exception as e:
        logger.error(f"Error sending to room: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# WebSocket Endpoints

@app.websocket("/ws/{agent_id}")
async def websocket_endpoint(websocket: WebSocket, agent_id: str):
    """Main WebSocket endpoint"""
    await manager.connect(websocket, agent_id)
    
    try:
        # Send welcome message
        await manager.send_personal_message(
            json.dumps({
                "type": "system",
                "content": "Connected to Remittance Platform WebSocket Service",
                "timestamp": datetime.utcnow().isoformat()
            }),
            websocket
        )
        
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                message_type = message.get("type", "echo")
                
                if message_type == "ping":
                    # Respond to ping
                    await manager.send_personal_message(
                        json.dumps({"type": "pong", "timestamp": datetime.utcnow().isoformat()}),
                        websocket
                    )
                
                elif message_type == "join_room":
                    # Join a room
                    room_id = message.get("room_id")
                    if room_id:
                        await manager.join_room(websocket, room_id)
                        await manager.send_personal_message(
                            json.dumps({
                                "type": "system",
                                "content": f"Joined room: {room_id}",
                                "timestamp": datetime.utcnow().isoformat()
                            }),
                            websocket
                        )
                
                elif message_type == "leave_room":
                    # Leave a room
                    room_id = message.get("room_id")
                    if room_id:
                        await manager.leave_room(websocket, room_id)
                        await manager.send_personal_message(
                            json.dumps({
                                "type": "system",
                                "content": f"Left room: {room_id}",
                                "timestamp": datetime.utcnow().isoformat()
                            }),
                            websocket
                        )
                
                elif message_type == "room_message":
                    # Send message to room
                    room_id = message.get("room_id")
                    content = message.get("content")
                    if room_id and content:
                        await manager.send_to_room(
                            json.dumps({
                                "type": "room_message",
                                "room_id": room_id,
                                "agent_id": agent_id,
                                "content": content,
                                "timestamp": datetime.utcnow().isoformat()
                            }),
                            room_id,
                            exclude=websocket
                        )
                
                else:
                    # Echo message back
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "echo",
                            "content": message.get("content", ""),
                            "timestamp": datetime.utcnow().isoformat()
                        }),
                        websocket
                    )
            
            except json.JSONDecodeError:
                # If not JSON, echo as plain text
                await manager.send_personal_message(
                    json.dumps({
                        "type": "echo",
                        "content": data,
                        "timestamp": datetime.utcnow().isoformat()
                    }),
                    websocket
                )
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"Client disconnected: agent_id={agent_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        manager.disconnect(websocket)

@app.websocket("/ws/room/{room_id}")
async def room_websocket_endpoint(websocket: WebSocket, room_id: str, agent_id: str):
    """WebSocket endpoint for room-based communication"""
    await manager.connect(websocket, agent_id)
    await manager.join_room(websocket, room_id)
    
    try:
        # Send welcome message
        await manager.send_to_room(
            json.dumps({
                "type": "system",
                "content": f"Agent {agent_id} joined the room",
                "timestamp": datetime.utcnow().isoformat()
            }),
            room_id
        )
        
        while True:
            data = await websocket.receive_text()
            
            # Broadcast to room
            await manager.send_to_room(
                json.dumps({
                    "type": "message",
                    "agent_id": agent_id,
                    "content": data,
                    "timestamp": datetime.utcnow().isoformat()
                }),
                room_id,
                exclude=websocket
            )
    
    except WebSocketDisconnect:
        await manager.leave_room(websocket, room_id)
        manager.disconnect(websocket)
        
        # Notify room
        await manager.send_to_room(
            json.dumps({
                "type": "system",
                "content": f"Agent {agent_id} left the room",
                "timestamp": datetime.utcnow().isoformat()
            }),
            room_id
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8085)

