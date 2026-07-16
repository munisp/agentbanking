from fastapi import FastAPI
from router import router

app = FastAPI(title="CBN Comprehensive Compliance Service", version="1.0.0")
app.include_router(router)
