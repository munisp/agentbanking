from fastapi import Request, Header, HTTPException
from utils import create_logger

logger = create_logger(__name__)

async def get_request_auth_headers(request: Request, call_next):
    keycloak_id = request.headers.get("x-keycloak-id")

    # Attach to request.state if needed downstream
    request.state.keycloak_id = keycloak_id

    # Proceed to the route handler
    response = await call_next(request)
    return response

def swagger_keycloak_id_auth(x_keycloak_id: str = Header(..., description="Keycloak user ID")):
    if not x_keycloak_id:
        raise HTTPException(status_code=401, detail="Missing x-keycloak-id header")
    return x_keycloak_id