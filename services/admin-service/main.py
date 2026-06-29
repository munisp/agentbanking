import logging
import atexit
from fastapi import FastAPI
from sqlalchemy import text

from database import Base, engine
from api.v1 import health_router, admin_router
from utils import get_config
from middlewares import RequiredHeadersMiddleware
from utils.kafka_instance import KafkaClientInstance

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup config
config = get_config()

app = FastAPI(
    title="Admin service", description="54agent admin service.", version="0.0.0"
)

app.add_middleware(
    RequiredHeadersMiddleware,
    required_headers=[
        "x-tenant-id",
    ],
    exclude_prefixes=["/health", "/dapr", "/metrics", "/metrics/kafka"],
)


# Register shutdown handler
@atexit.register
def shutdown_kafka():
    KafkaClientInstance.close()


Base.metadata.create_all(bind=engine)

app.include_router(health_router, prefix="", tags=["health"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])


# Kafka metrics endpoint
@app.get("/metrics/kafka")
def get_kafka_metrics():
    """Get Kafka publishing metrics"""
    return {
        "status": "connected" if KafkaClientInstance.is_connected() else "disconnected",
        "metrics": KafkaClientInstance.get_metrics(),
    }


def run_migrations():
    """
    Migrate DB column from legacy Postgres enum type to VARCHAR.
    Safe to run multiple times — checks column type first.
    """
    try:
        with engine.connect() as conn:
            # Check current column data type
            result = conn.execute(
                text(
                    "SELECT data_type FROM information_schema.columns "
                    "WHERE table_name='admin' AND column_name='access_level'"
                )
            )
            row = result.fetchone()
            if row and row[0].lower() != "character varying":
                conn.execute(
                    text(
                        "ALTER TABLE admin ALTER COLUMN access_level TYPE VARCHAR(100) "
                        "USING access_level::text"
                    )
                )
                conn.execute(text("DROP TYPE IF EXISTS accesslevel"))
                conn.commit()
                logger.info("✅ Migrated admin.access_level to VARCHAR(100)")
    except Exception as e:
        logger.warning(f"Migration check skipped or already applied: {e}")


@app.on_event("startup")
async def startup_event():
    run_migrations()
    logger.info("🚀 Admin Service is running..")
