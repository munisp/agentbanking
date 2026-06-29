from fastapi import FastAPI

from routes import health_router, transfers_router
from utils import get_config

config = get_config()

app = FastAPI(
    title="Payment rails connectors service",
    description="54agent payment rails connectors service.",
    version="0.0.0",
    root_path=config.ROOT_PATH,
)

app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(transfers_router, prefix="/outbound", tags=["transfers"])
