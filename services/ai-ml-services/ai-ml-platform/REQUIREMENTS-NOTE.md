# REQUIREMENTS NOTE — services/ai-ml-services/ai-ml-platform

`service.py` now uses real bcrypt password hashing via passlib:

```python
from passlib.context import CryptContext
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
```

The service directory (`services/ai-ml-services/ai-ml-platform/`) has **no
requirements file of its own** (no requirements.txt / pyproject.toml / Dockerfile
in that directory at commit 68cc0eea5f02a354a67ef2b71d684a5e9df7426f), so the
dependency could not be added to a service-local requirements file.

Action required for deployment: ensure the service's environment installs

```
passlib[bcrypt]>=1.7.4
```

(i.e. `passlib` plus the `bcrypt` backend). Without it, import of `service.py`
will fail fast with `ModuleNotFoundError: No module named 'passlib'` — this is
intentional fail-loud behavior rather than silently falling back to the old
`hashed_<password>` placeholder.

Note: `register` (`UserService.create_user`) and `login`
(`AuthService.authenticate_user`) already routed through
`get_password_hash`/`verify_password`, so replacing those two helpers fixes both
paths. Token issuance (`create_access_token`) still returns HTTP 501 by design —
Keycloak-issued RS256 tokens are the supported path.
