"""
Service module - delegates to main application entry point.
Import and run via main.py for the full FastAPI application.
"""
from main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
