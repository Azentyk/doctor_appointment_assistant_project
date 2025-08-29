# agent.py
from typing import Dict
from patient_bot_conversational import *
from db_utils import get_user_contact_info
from datetime import datetime
import uuid
import logging
from logger import setup_logging

# Initialize logging for Azure (stdout/stderr capture)
setup_logging()
logger = logging.getLogger(__name__)

# In-memory storage for user agents (per session)
user_agents: Dict[str, Dict] = {}

def get_formatted_date() -> str:
    """Return current date in a formatted string."""
    return datetime.now().strftime("%B %d, %Y")

def get_default_config(email: str) -> Dict:
    """
    Generate a config dictionary with patient data and a unique thread ID.
    Works both locally and on Azure.
    """
    contact_info = get_user_contact_info(email)
    if not contact_info:
        logger.warning(f"No contact info found for {email}. Using defaults.")
        contact_info = [{"firstname": "Unknown", "phone": "N/A"}]
    else:
        contact_info = contact_info[0]  # Assuming first record is correct

    current_date = get_formatted_date()
    contact_info['current_date'] = current_date

    logger.info(f"[Azure] Fetched contact info for {email}: {contact_info}")

    patient_data = (
        f"Name: {contact_info.get('firstname', 'Unknown')}, "
        f"Phone Number: {contact_info.get('phone', 'N/A')}, "
        f"Email Id: {email}"
    )
    thread_id = str(uuid.uuid4())

    config = {
        "configurable": {
            "patient_data": patient_data,
            "current_date": current_date,
            "thread_id": thread_id,
        }
    }

    logger.info(f"[Azure] Generated config for {email}: {config}")
    return config

def get_or_create_agent_for_user(email: str, session_id: str) -> Dict:
    """Get existing agent or create a new one for the user (Flask + Azure)."""
    if session_id not in user_agents:
        config = get_default_config(email)
        user_agents[session_id] = config
        logger.info(f"[Azure] Created new agent for session {session_id}: {config}")
    else:
        logger.info(f"[Azure] Retrieved existing agent for session {session_id}")
    return user_agents[session_id]

def remove_agent(session_id: str) -> None:
    """Remove agent from memory (Flask session cleanup)."""
    if session_id in user_agents:
        del user_agents[session_id]
        logger.info(f"[Azure] Removed agent for session {session_id}")
    else:
        logger.warning(f"[Azure] Tried to remove non-existent session {session_id}")
