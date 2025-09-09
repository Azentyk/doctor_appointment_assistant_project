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
    This version defensively normalizes contact_info to a dict no matter what
    the data source returns (None, dict, list, nested list, etc).
    """
    raw_contact = get_user_contact_info(email)

    # Defensive normalization ------------------------------------------------
    contact_info = None

    # If caller returned a dict directly, use it.
    if isinstance(raw_contact, dict):
        contact_info = raw_contact

    # If it's a list, try to extract a dict from it (first candidate that is a dict).
    elif isinstance(raw_contact, list):
        # Find first dict element inside list (handles list-of-lists too)
        found = None
        for item in raw_contact:
            if isinstance(item, dict):
                found = item
                break
            # if item is a single-element list containing a dict, try that
            if isinstance(item, list) and len(item) > 0 and isinstance(item[0], dict):
                found = item[0]
                break
        if found is not None:
            contact_info = found
        else:
            # no dict found — log and fall through to defaults
            logger.warning(
                "[Azure] get_user_contact_info returned a list, but no dict found "
                f"for {email}. Raw preview: {str(raw_contact)[:300]}"
            )

    # Anything else (None, str, etc) — log and fallback
    else:
        if raw_contact is not None:
            logger.warning(
                "[Azure] get_user_contact_info returned unexpected type "
                f"{type(raw_contact).__name__} for {email}. Preview: {str(raw_contact)[:300]}"
            )

    # If still no usable contact_info, use default values
    if not isinstance(contact_info, dict):
        logger.info(f"[Azure] No usable contact info for {email}; using default values.")
        contact_info = {"firstname": "Unknown", "phone": "N/A"}

    # Now safe to use contact_info as a dict
    try:
        current_date = get_formatted_date()
        contact_info['current_date'] = current_date
    except Exception as e:
        logger.exception(f"[Azure] Error setting current_date for contact_info of {email}: {e}")
        # ensure contact_info has the key even if exception occurred
        contact_info.setdefault('current_date', get_formatted_date())

    logger.info(f"[Azure] Normalized contact info for {email}: {contact_info}")

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
