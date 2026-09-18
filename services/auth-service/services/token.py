import os
import time
import jwt
import requests
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from sqlalchemy.orm import Session
from schemas.v1 import GenerateToken, Context
from adapters import KeycloakAdapter
from utils import ApiError, get_config
from services import AuthService
from utils.errors import raise_http_exception_handler

config = get_config()


class TokenService:
    """Token service."""

    def __init__(self):
        pass

    def generate_token(self, payload: GenerateToken, db: Session, context: Context):
        auth_service = AuthService(db)

        auth = auth_service.get_auth_by_api_key(payload.key, payload.secret, context)

        if not auth:
            raise_http_exception_handler(
                status_code=401,
                message="Invalid credentials.",
                code="AUTH-AUTH-INT-4002",
            )

        keycloak_adapter = KeycloakAdapter(realm=context.keycloak_realm)

        keycloak_user = keycloak_adapter.get_user(auth.api_key)

        if keycloak_user is None:
            raise ApiError(
                message="Invalid user.",
                status_code=500,
                code="AUTH-AUTH-INT-5001",
            )

        return keycloak_adapter.request_user_token(payload.key, payload.secret)

    def jwk_to_pem(self, jwk):
        n = int.from_bytes(base64.urlsafe_b64decode(jwk["n"] + "=="), "big")
        e = int.from_bytes(base64.urlsafe_b64decode(jwk["e"] + "=="), "big")
        pub_key = rsa.RSAPublicNumbers(e, n).public_key(default_backend())
        return pub_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    # F10: process-local JWKS cache (realm URL -> (fetched_at_epoch, jwks_dict))
    _jwks_cache = {}
    _JWKS_CACHE_TTL_SECONDS = int(os.getenv("JWKS_CACHE_TTL_SECONDS", "3600"))
    _JWKS_FETCH_TIMEOUT_SECONDS = float(os.getenv("JWKS_FETCH_TIMEOUT_SECONDS", "5"))

    def _fetch_jwks(self, jwks_url: str) -> dict:
        """Fetch JWKS with a bounded timeout and a TTL cache.

        Fails closed: a fetch error with no cached keys raises, rather than
        silently accepting tokens.
        """
        cached = self._jwks_cache.get(jwks_url)
        now = time.time()
        if cached and (now - cached[0]) < self._JWKS_CACHE_TTL_SECONDS:
            return cached[1]
        resp = requests.get(jwks_url, timeout=self._JWKS_FETCH_TIMEOUT_SECONDS)
        resp.raise_for_status()
        jwks = resp.json()
        self._jwks_cache[jwks_url] = (now, jwks)
        return jwks

    def validate_token(self, token: str, context: Context):
        keycloak_base_url = os.getenv(
            "KEYCLOAK_SERVER_URL", "https://keycloak.servers.upi.dev"
        ).rstrip("/")
        realm = context.keycloak_realm
        jwks_url = (
            f"{keycloak_base_url}/realms/{realm}/protocol/openid-connect/certs"
        )
        jwks = self._fetch_jwks(jwks_url)

        headers = jwt.get_unverified_header(token)
        kid = headers["kid"]

        key_data = next(k for k in jwks["keys"] if k["kid"] == kid)
        pem_key = self.jwk_to_pem(key_data)

        # F10: verify issuer and (when configured) audience, not just expiry.
        expected_issuer = f"{keycloak_base_url}/realms/{realm}"
        expected_audience = os.getenv("KEYCLOAK_CLIENT_ID", "")
        decode_options = {"verify_exp": True, "verify_iss": True}
        decode_kwargs = {"issuer": expected_issuer}
        if expected_audience:
            decode_options["verify_aud"] = True
            decode_kwargs["audience"] = expected_audience
        else:
            decode_options["verify_aud"] = False

        decoded_token = jwt.decode(
            token,
            key=pem_key,
            algorithms=["RS256"],
            options=decode_options,
            **decode_kwargs,
        )
        return decoded_token

    def refresh_token(self, token: str, context: Context) -> dict:
        return KeycloakAdapter(realm=context.keycloak_realm).refresh_user_token(
            refresh_token=token
        )


token_service = TokenService()
