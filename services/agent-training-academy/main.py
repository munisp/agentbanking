from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from router import router
from models import Base
from config import engine

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Agent Training Academy LMS", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
