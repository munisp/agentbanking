import sys as _sys, os as _os

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

# ── Round-11 persistence fix (wave-6: asyncpg) ────────────────────────────
# Process-memory containers replaced by Postgres-backed stores so business
# data survives restarts. Wave-6 upgrade: all DB I/O now runs on asyncpg via
# a dedicated background event loop, so async FastAPI handlers no longer
# block the main loop on sync SQLAlchemy calls. Same dict/list-compatible
# public API; {ENV}_DATABASE_URL convention unchanged.
import os as _r11_os
import json as _r11_json
import asyncio as _r11_asyncio
import threading as _r11_threading
import asyncpg as _r11_apg

_r11_loop = _r11_asyncio.new_event_loop()


def _r11_loop_main(loop):
    _r11_asyncio.set_event_loop(loop)
    loop.run_forever()


_r11_threading.Thread(
    target=_r11_loop_main, args=(_r11_loop,), daemon=True, name="r11-pg-io"
).start()


def _r11_sync(coro):
    """Run an asyncpg coroutine on the dedicated loop and wait for it."""
    return _r11_asyncio.run_coroutine_threadsafe(coro, _r11_loop).result()


class _PgDictStore:
    """Dict-compatible store persisted to Postgres (replaces in-memory dict)."""

    def __init__(self, table, env, model_name=None):
        if not table.replace("_", "").isalnum():
            raise ValueError("unsafe table name: %r" % table)
        self._model_name = model_name
        self._table = table
        url = _r11_os.getenv(
            env, "postgresql://postgres:postgres@localhost:5432/platform"
        )
        self._pool = _r11_sync(_r11_apg.create_pool(url, min_size=1, max_size=10))
        _r11_sync(self._ensure())

    async def _ensure(self):
        async with self._pool.acquire() as c:
            await c.execute(
                'CREATE TABLE IF NOT EXISTS "%s" ('
                "key VARCHAR(128) PRIMARY KEY, "
                "data TEXT NOT NULL, "
                "updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
                ")" % self._table
            )

    @staticmethod
    def _ser(v):
        def _cv(x):
            if hasattr(x, "model_dump"):
                return x.model_dump()
            if hasattr(x, "dict") and callable(x.dict):
                return x.dict()
            return x
        if isinstance(v, list):
            v = [_cv(x) for x in v]
        else:
            v = _cv(v)
        return _r11_json.dumps(v, default=str)

    def _deser(self, raw):
        d = _r11_json.loads(raw)
        if self._model_name:
            cls = globals().get(self._model_name)
            if cls is not None:
                if isinstance(d, list):
                    return [cls(**x) if isinstance(x, dict) else x for x in d]
                return cls(**d)
        return d

    async def _aset(self, k, payload):
        async with self._pool.acquire() as c:
            await c.execute(
                'INSERT INTO "%s" (key, data) VALUES ($1, $2) '
                "ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data, "
                "updated_at = now()" % self._table,
                str(k), payload,
            )

    def __setitem__(self, k, v):
        _r11_sync(self._aset(k, self._ser(v)))

    async def _aget(self, k):
        async with self._pool.acquire() as c:
            return await c.fetchval(
                'SELECT data FROM "%s" WHERE key = $1' % self._table, str(k)
            )

    def __getitem__(self, k):
        raw = _r11_sync(self._aget(k))
        if raw is None:
            raise KeyError(k)
        return self._deser(raw)

    def get(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            return default

    async def _adel(self, k):
        async with self._pool.acquire() as c:
            return await c.execute(
                'DELETE FROM "%s" WHERE key = $1' % self._table, str(k)
            )

    def __delitem__(self, k):
        res = _r11_sync(self._adel(k))
        if res == "DELETE 0":
            raise KeyError(k)

    def __contains__(self, k):
        return _r11_sync(self._aget(k)) is not None

    def setdefault(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            self[k] = default
            return default

    async def _aall(self):
        async with self._pool.acquire() as c:
            return await c.fetch('SELECT key, data FROM "%s"' % self._table)

    def _all(self):
        return _r11_sync(self._aall())

    def values(self):
        return [self._deser(r["data"]) for r in self._all()]

    def keys(self):
        return [r["key"] for r in self._all()]

    def items(self):
        return [(r["key"], self._deser(r["data"])) for r in self._all()]

    def __len__(self):
        async def _n():
            async with self._pool.acquire() as c:
                return await c.fetchval('SELECT COUNT(*) FROM "%s"' % self._table)
        return _r11_sync(_n())

    def pop(self, k, default=None):
        try:
            v = self[k]
            del self[k]
            return v
        except KeyError:
            return default

    def clear(self):
        async def _c():
            async with self._pool.acquire() as c:
                await c.execute('DELETE FROM "%s"' % self._table)
        _r11_sync(_c())


class _PgListStore:
    """List-compatible store persisted to Postgres (replaces in-memory list)."""

    def __init__(self, table, env):
        if not table.replace("_", "").isalnum():
            raise ValueError("unsafe table name: %r" % table)
        self._table = table
        url = _r11_os.getenv(
            env, "postgresql://postgres:postgres@localhost:5432/platform"
        )
        self._pool = _r11_sync(_r11_apg.create_pool(url, min_size=1, max_size=10))
        _r11_sync(self._ensure())

    async def _ensure(self):
        async with self._pool.acquire() as c:
            await c.execute(
                'CREATE TABLE IF NOT EXISTS "%s" ('
                "id SERIAL PRIMARY KEY, "
                "data TEXT NOT NULL, "
                "created_at TIMESTAMPTZ NOT NULL DEFAULT now()"
                ")" % self._table
            )

    @staticmethod
    def _ser(v):
        def _cv(x):
            if hasattr(x, "model_dump"):
                return x.model_dump()
            if hasattr(x, "dict") and callable(x.dict):
                return x.dict()
            return x
        return _r11_json.dumps(_cv(v), default=str)

    @staticmethod
    def _deser(raw):
        return _r11_json.loads(raw)

    def append(self, v):
        async def _a():
            async with self._pool.acquire() as c:
                await c.execute(
                    'INSERT INTO "%s" (data) VALUES ($1)' % self._table,
                    self._ser(v),
                )
        _r11_sync(_a())

    async def _arows(self):
        async with self._pool.acquire() as c:
            return await c.fetch(
                'SELECT id, data FROM "%s" ORDER BY id' % self._table
            )

    def _rows(self):
        return _r11_sync(self._arows())

    def __iter__(self):
        return iter([self._deser(r["data"]) for r in self._rows()])

    def __len__(self):
        async def _n():
            async with self._pool.acquire() as c:
                return await c.fetchval('SELECT COUNT(*) FROM "%s"' % self._table)
        return _r11_sync(_n())

    def __getitem__(self, idx):
        vals = [self._deser(r["data"]) for r in self._rows()]
        return vals[idx]

    def __delitem__(self, idx):
        rows = self._rows()
        targets = rows[idx] if isinstance(idx, slice) else [rows[idx]]
        ids = [r["id"] for r in targets]
        if not ids:
            return
        async def _d():
            async with self._pool.acquire() as c:
                await c.execute(
                    'DELETE FROM "%s" WHERE id = ANY($1::int[])' % self._table, ids
                )
        _r11_sync(_d())

    def clear(self):
        async def _c():
            async with self._pool.acquire() as c:
                await c.execute('DELETE FROM "%s"' % self._table)
        _r11_sync(_c())

_shutdown_handlers = []  # function registry — must stay in-process (wave-8 revert of wave-7 overreach)  # round-11 wave-7 persistence

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


from pydantic import BaseModel
from typing import List, Dict, Optional, Set
from datetime import datetime
import logging
import json
import asyncio
import uuid
import os

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

apply_middleware(app)
setup_logging("websocket-service")
app.include_router(metrics_router)

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

