import logging
from adapters.permify import load_schema

from fastapi import FastAPI

from database import Base, engine
from api.v1 import health_router, auth_router, token_router, system_router, permissions_router
from utils import get_config
from middlewares import RequiredHeadersMiddleware, AuditMiddleware

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup config
config = get_config()

app = FastAPI(
    title="Auth service", description="54agent authentication service.", version="0.0.0"
)

app.add_middleware(
    RequiredHeadersMiddleware,
    required_headers=["x-tenant-id", "x-keycloak-realm", "x-keycloak-pub-key"],
    exclude_prefixes=["/health", "/dapr", "/system"],
)
app.add_middleware(AuditMiddleware)

Base.metadata.create_all(bind=engine)

app.include_router(health_router, prefix="", tags=["health"])
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(token_router, prefix="/token", tags=["token"])
app.include_router(system_router, prefix="/system", tags=["system"])
app.include_router(permissions_router, prefix="/permissions", tags=["permissions"])


@app.on_event("startup")
async def startup_event():
    load_schema()
    logger.info("Auth Service is running..")
