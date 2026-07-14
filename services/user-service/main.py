from fastapi import FastAPI
import atexit

from database import Base, engine
from api import health_router, user_router, feedback_router
from utils import get_config
from middlewares import RequiredHeadersMiddleware
from utils.kafka_instance import KafkaClientInstance

config = get_config()

app = FastAPI(title="User service", description="54agent user service.", version="0.0.0")

app.add_middleware(
    RequiredHeadersMiddleware,
    required_headers=["x-tenant-id", "x-keycloak-id"],
    exclude_prefixes=["/health", "/dapr"],
)


# Register shutdown handler
@atexit.register
def shutdown_kafka():
    KafkaClientInstance.close()


Base.metadata.create_all(bind=engine)

app.include_router(health_router, prefix="", tags=["health"])
app.include_router(user_router, prefix="/user", tags=["user"])
app.include_router(feedback_router, prefix="/user/feedback", tags=["feedback"])


# Kafka metrics endpoint
@app.get("/metrics/kafka")
def get_kafka_metrics():
    """Get Kafka publishing metrics"""
    return {
        "status": "connected" if KafkaClientInstance.is_connected() else "disconnected",
        "metrics": KafkaClientInstance.get_metrics(),
    }
