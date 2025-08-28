from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
import uuid
import logging

from db_utils import (
    authenticate_user,
    register_user,
    load_users_df,
    get_user_contact_info
)
from logger import setup_logging

# Initialize logger
setup_logging()
logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/")
async def home_page(request: Request):
    logger.info("Home page accessed")
    return templates.TemplateResponse("home.html", {"request": request})

@router.get("/register")
async def register_page(request: Request):
    logger.info("Register page accessed")
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
async def register_user_endpoint(
    request: Request,
    firstname: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    country: str = Form(...),
    state: str = Form(...),
    location: str = Form(...),
    city: str = Form(...),
    password: str = Form(...)
):
    error = register_user(firstname, email, phone, country, state, location, city, password)
    
    if error is None:
        logger.info(f"Registration successful for {email} from IP {request.client.host} "
                    f"User-Agent: {request.headers.get('user-agent', '')}")
        return RedirectResponse(url="/login", status_code=303)
    
    logger.warning(f"Registration failed for {email}. Reason: {error}. "
                   f"IP: {request.client.host}, User-Agent: {request.headers.get('user-agent', '')}")
    
    return templates.TemplateResponse("register.html", {
        "request": request,
        "message": error
    })

@router.get("/login")
async def login_page(request: Request):
    logger.info("Login page accessed")
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    if authenticate_user(email, password):
        session_id = str(uuid.uuid4())
        request.session["user"] = email
        request.session["session_id"] = session_id
        
        logger.info(f"User {email} logged in successfully with session ID {session_id} "
                    f"from IP {request.client.host}, User-Agent: {request.headers.get('user-agent', '')}")
        return RedirectResponse(url=f"/chat/{session_id}", status_code=303)
    
    logger.warning(f"Failed login attempt for {email} "
                   f"from IP {request.client.host}, User-Agent: {request.headers.get('user-agent', '')}")
    
    return templates.TemplateResponse("login.html", {
        "request": request,
        "message": "Invalid email or password"
    })

@router.get("/logout")
async def logout(request: Request):
    session_id = request.session.get("session_id")
    user_email = request.session.get("user")
    
    if session_id:
        logger.info(f"User {user_email} logged out from session {session_id}")
    else:
        logger.warning("Logout attempted without active session")
    
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)
