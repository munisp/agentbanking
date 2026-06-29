from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RequiredHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        required_headers: list[str],
        exclude_paths: list[str] | None = None,
        exclude_prefixes: list[str] | None = None,
    ):
        super().__init__(app)
        self.required_headers = [h.lower() for h in required_headers]
        self.exclude_paths = exclude_paths or []
        self.exclude_prefixes = exclude_prefixes or []

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in self.exclude_paths:
            return await call_next(request)

        for prefix in self.exclude_prefixes:
            if path.startswith(prefix):
                return await call_next(request)

        missing_headers = [
            header for header in self.required_headers if header not in request.headers
        ]

        if missing_headers:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Missing required headers",
                    "missing": missing_headers,
                },
            )

        return await call_next(request)
