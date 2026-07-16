import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Device Manager Service
Manages POS devices, connections, and health monitoring
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel
import redis.asyncio as redis
from device_drivers import DeviceManager, DeviceInfo, DeviceStatus, DeviceProtocol

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Device Manager Service",
    description="POS Device Management and Monitoring",
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

apply_middleware(app)
setup_logging("device-manager-service")
app.include_router(metrics_router)

# Pydantic models
class DeviceRegistrationRequest(BaseModel):
    device_id: str
    device_type: str
    protocol: DeviceProtocol
    connection_params: Dict[str, Any]
    capabilities: List[str]

class DeviceCommandRequest(BaseModel):
    device_id: str
    command: str
    parameters: Optional[Dict[str, Any]] = None

class DeviceResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

class DeviceHealthResponse(BaseModel):
    device_id: str
    status: DeviceStatus
    last_seen: datetime
    connection_quality: float
    error_count: int
    uptime_percentage: float

# Global device manager
device_manager = DeviceManager()
redis_client: Optional[redis.Redis] = None

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global redis_client
    
    try:
        # Initialize Redis connection
        redis_client = redis.from_url("redis://redis:6379", decode_responses=True)
        await redis_client.ping()
        logger.info("Connected to Redis")
        
        # Start device discovery
        asyncio.create_task(device_discovery_task())
        
        # Start health monitoring
        asyncio.create_task(device_health_monitoring_task())
        
        logger.info("Device Manager Service started successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize Device Manager Service: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global redis_client
    
    if redis_client:
        await redis_client.close()
    
    # Disconnect all devices
    await device_manager.disconnect_all_devices()
    
    logger.info("Device Manager Service shut down")

@app.get("/devices/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check Redis connection
        redis_status = "connected" if redis_client and await redis_client.ping() else "disconnected"
        
        # Get device statistics
        device_stats = await get_device_statistics()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "redis_status": redis_status,
            "device_statistics": device_stats,
            "version": "1.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

@app.get("/devices", response_model=List[DeviceInfo])
async def list_devices():
    """List all registered devices"""
    try:
        devices = await device_manager.list_devices()
        return devices
    except Exception as e:
        logger.error(f"Failed to list devices: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve devices")

@app.post("/devices/register", response_model=DeviceResponse)
async def register_device(request: DeviceRegistrationRequest):
    """Register a new device"""
    try:
        device_info = DeviceInfo(
            device_id=request.device_id,
            device_type=request.device_type,
            protocol=request.protocol,
            connection_params=request.connection_params,
            capabilities=request.capabilities,
            status=DeviceStatus.DISCONNECTED,
            last_seen=datetime.utcnow()
        )
        
        success = await device_manager.register_device(device_info)
        
        if success:
            # Cache device info in Redis
            if redis_client:
                await redis_client.hset(
                    f"device:{request.device_id}",
                    mapping={
                        "device_type": request.device_type,
                        "protocol": request.protocol.value,
                        "status": DeviceStatus.DISCONNECTED.value,
                        "registered_at": datetime.utcnow().isoformat()
                    }
                )
            
            return DeviceResponse(
                success=True,
                message=f"Device {request.device_id} registered successfully",
                data={"device_id": request.device_id}
            )
        else:
            raise HTTPException(status_code=400, detail="Failed to register device")
            
    except Exception as e:
        logger.error(f"Device registration failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/devices/{device_id}/connect", response_model=DeviceResponse)
async def connect_device(device_id: str):
    """Connect to a device"""
    try:
        success = await device_manager.connect_device(device_id)
        
        if success:
            # Update status in Redis
            if redis_client:
                await redis_client.hset(
                    f"device:{device_id}",
                    mapping={
                        "status": DeviceStatus.CONNECTED.value,
                        "connected_at": datetime.utcnow().isoformat()
                    }
                )
            
            return DeviceResponse(
                success=True,
                message=f"Connected to device {device_id}",
                data={"device_id": device_id, "status": "connected"}
            )
        else:
            raise HTTPException(status_code=400, detail="Failed to connect to device")
            
    except Exception as e:
        logger.error(f"Device connection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/devices/{device_id}/disconnect", response_model=DeviceResponse)
async def disconnect_device(device_id: str):
    """Disconnect from a device"""
    try:
        success = await device_manager.disconnect_device(device_id)
        
        if success:
            # Update status in Redis
            if redis_client:
                await redis_client.hset(
                    f"device:{device_id}",
                    mapping={
                        "status": DeviceStatus.DISCONNECTED.value,
                        "disconnected_at": datetime.utcnow().isoformat()
                    }
                )
            
            return DeviceResponse(
                success=True,
                message=f"Disconnected from device {device_id}",
                data={"device_id": device_id, "status": "disconnected"}
            )
        else:
            raise HTTPException(status_code=400, detail="Failed to disconnect from device")
            
    except Exception as e:
        logger.error(f"Device disconnection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/devices/{device_id}/command", response_model=DeviceResponse)
async def send_device_command(device_id: str, request: DeviceCommandRequest):
    """Send command to a device"""
    try:
        result = await device_manager.send_command(
            device_id=device_id,
            command=request.command,
            parameters=request.parameters or {}
        )
        
        return DeviceResponse(
            success=True,
            message=f"Command {request.command} sent to device {device_id}",
            data=result
        )
        
    except Exception as e:
        logger.error(f"Device command failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/devices/{device_id}/health", response_model=DeviceHealthResponse)
async def get_device_health(device_id: str):
    """Get device health information"""
    try:
        device_info = await device_manager.get_device_info(device_id)
        
        if not device_info:
            raise HTTPException(status_code=404, detail="Device not found")
        
        # Get health metrics from Redis
        health_data = {}
        if redis_client:
            health_data = await redis_client.hgetall(f"device_health:{device_id}")
        
        return DeviceHealthResponse(
            device_id=device_id,
            status=device_info.status,
            last_seen=device_info.last_seen,
            connection_quality=float(health_data.get("connection_quality", 1.0)),
            error_count=int(health_data.get("error_count", 0)),
            uptime_percentage=float(health_data.get("uptime_percentage", 100.0))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get device health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/devices/discover")
async def discover_devices(background_tasks: BackgroundTasks):
    """Trigger device discovery"""
    try:
        background_tasks.add_task(run_device_discovery)
        
        return DeviceResponse(
            success=True,
            message="Device discovery started",
            data={"status": "discovery_started"}
        )
        
    except Exception as e:
        logger.error(f"Device discovery failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/devices/statistics")
async def get_device_statistics():
    """Get device statistics"""
    try:
        devices = await device_manager.list_devices()
        
        stats = {
            "total_devices": len(devices),
            "connected_devices": len([d for d in devices if d.status == DeviceStatus.CONNECTED]),
            "disconnected_devices": len([d for d in devices if d.status == DeviceStatus.DISCONNECTED]),
            "error_devices": len([d for d in devices if d.status == DeviceStatus.ERROR]),
            "device_types": {},
            "protocols": {}
        }
        
        # Count by device type and protocol
        for device in devices:
            stats["device_types"][device.device_type] = stats["device_types"].get(device.device_type, 0) + 1
            stats["protocols"][device.protocol.value] = stats["protocols"].get(device.protocol.value, 0) + 1
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get device statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background tasks
async def device_discovery_task():
    """Background task for periodic device discovery"""
    while True:
        try:
            await run_device_discovery()
            await asyncio.sleep(300)  # Run every 5 minutes
        except Exception as e:
            logger.error(f"Device discovery task error: {e}")
            await asyncio.sleep(60)  # Retry after 1 minute on error

async def run_device_discovery():
    """Run device discovery"""
    try:
        logger.info("Starting device discovery...")
        
        # Discover serial devices
        serial_devices = await device_manager.discover_serial_devices()
        logger.info(f"Discovered {len(serial_devices)} serial devices")
        
        # Discover USB devices
        usb_devices = await device_manager.discover_usb_devices()
        logger.info(f"Discovered {len(usb_devices)} USB devices")
        
        # Discover Bluetooth devices
        bluetooth_devices = await device_manager.discover_bluetooth_devices()
        logger.info(f"Discovered {len(bluetooth_devices)} Bluetooth devices")
        
        # Auto-register discovered devices
        all_devices = serial_devices + usb_devices + bluetooth_devices
        for device_info in all_devices:
            try:
                await device_manager.register_device(device_info)
                logger.info(f"Auto-registered device: {device_info.device_id}")
            except Exception as e:
                logger.warning(f"Failed to auto-register device {device_info.device_id}: {e}")
        
        logger.info("Device discovery completed")
        
    except Exception as e:
        logger.error(f"Device discovery error: {e}")

async def device_health_monitoring_task():
    """Background task for device health monitoring"""
    while True:
        try:
            await monitor_device_health()
            await asyncio.sleep(30)  # Monitor every 30 seconds
        except Exception as e:
            logger.error(f"Device health monitoring error: {e}")
            await asyncio.sleep(60)  # Retry after 1 minute on error

async def monitor_device_health():
    """Monitor health of all devices"""
    try:
        devices = await device_manager.list_devices()
        
        for device in devices:
            try:
                # Check device connectivity
                is_healthy = await device_manager.check_device_health(device.device_id)
                
                # Update health metrics in Redis
                if redis_client:
                    health_key = f"device_health:{device.device_id}"
                    current_time = datetime.utcnow()
                    
                    # Get previous health data
                    prev_data = await redis_client.hgetall(health_key)
                    error_count = int(prev_data.get("error_count", 0))
                    
                    if not is_healthy:
                        error_count += 1
                    
                    # Calculate uptime percentage (simplified)
                    uptime_percentage = max(0, 100 - (error_count * 2))  # Each error reduces uptime by 2%
                    
                    # Update health data
                    await redis_client.hset(
                        health_key,
                        mapping={
                            "last_check": current_time.isoformat(),
                            "is_healthy": str(is_healthy),
                            "error_count": str(error_count),
                            "uptime_percentage": str(uptime_percentage),
                            "connection_quality": "1.0" if is_healthy else "0.0"
                        }
                    )
                    
                    # Set expiration for health data (1 hour)
                    await redis_client.expire(health_key, 3600)
                
            except Exception as e:
                logger.warning(f"Health check failed for device {device.device_id}: {e}")
        
    except Exception as e:
        logger.error(f"Device health monitoring error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8073)
