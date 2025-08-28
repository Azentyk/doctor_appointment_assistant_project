from datetime import datetime
import logging
from fastapi import Request

# Configure logger
logger = logging.getLogger("session_logger")
logger.setLevel(logging.INFO)

# Optional: File handler (if you want logs in a file)
file_handler = logging.FileHandler("session_logs.log")
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


def create_session_record(request: Request, email: str, session_id: str):
    """Log creation of a new session"""
    try:
        now = datetime.now()
        session_data = {
            "session_id": session_id,
            "user_email": email,
            "ip_address": request.client.host,
            "user_agent": request.headers.get("user-agent", ""),
            "start_time": str(now),
            "status": "active",
        }
        logger.info(f"SESSION CREATED: {session_data}")
    except Exception as e:
        logger.error(f"Error creating session record: {e}")


def update_session_record(session_id: str, event_type: str, event_data: dict = None):
    """Log session event"""
    try:
        now = datetime.now()
        event = {
            "timestamp": str(now),
            "session_id": session_id,
            "event_type": event_type,
            "data": event_data or {},
        }
        logger.info(f"SESSION UPDATED: {event}")
    except Exception as e:
        logger.error(f"Error updating session record: {e}")


def close_session_record(session_id: str):
    """Log session closure"""
    try:
        now = datetime.now()
        session_end = {
            "session_id": session_id,
            "end_time": str(now),
            "status": "closed",
        }
        logger.info(f"SESSION CLOSED: {session_end}")
    except Exception as e:
        logger.error(f"Error closing session record: {e}")
