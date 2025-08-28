from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from logger import setup_logging
from db_utils import init_db
from chat_routes import router as chat_router
from authentication import router as auth_router

# Initialize logging
setup_logging()

# Initialize database
init_db()

# Create FastAPI app
app = FastAPI()

# Add middleware and routes
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(auth_router)
app.include_router(chat_router)