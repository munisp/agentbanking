from fastapi import FastAPI, Depends

from database import Base, engine
from api import health_router, transaction_router
from utils import get_config
from utils.coa_client import CoAClient
from middlewares import swagger_keycloak_id_auth, get_request_auth_headers
from dapr.ext.fastapi import DaprApp  # type: ignore
from events import subscribe

# Setup config
config = get_config()

# Initialize CoA Client
coa_client = CoAClient()

app = FastAPI(
    title="Transaction ledger",
    description="54agent transaction ledger.",
    version="0.0.0"
)

dapr_app = DaprApp(app)

app.middleware("http")(get_request_auth_headers)

Base.metadata.create_all(bind=engine)

app.include_router(health_router, prefix="", tags=["health"])
app.include_router(transaction_router, prefix="/txn", tags=["transactions"])

subscribe(dapr_app)
