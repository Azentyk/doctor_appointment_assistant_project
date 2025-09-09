from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import uuid
import logging
from datetime import datetime

from db_utils import (
    authenticate_user,
    register_user,
    load_users_df,
    get_user_contact_info
)
from logger import setup_logging
from session import create_session_record, update_session_record  # added session record utilities

# Initialize logger
setup_logging()
logger = logging.getLogger(__name__)

# Flask Blueprint (replaces FastAPI APIRouter)
auth_bp = Blueprint("auth", __name__, template_folder="templates")


@auth_bp.route("/")
def home_page():
    logger.info("Home page accessed")
    return render_template("home.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register_page():
    if request.method == "GET":
        logger.info("Register page accessed")
        return render_template("register.html")

    # POST logic
    firstname = request.form.get("firstname")
    email = request.form.get("email")
    phone = request.form.get("phone")
    country = request.form.get("country")
    state = request.form.get("state")
    location = request.form.get("location")
    city = request.form.get("city")
    password = request.form.get("password")

    error = register_user(firstname, email, phone, country, state, location, city, password)

    if error is None:
        # Log and update session record for registration success
        logger.info(
            f"Registration successful for {email} from IP {request.remote_addr} "
            f"User-Agent: {request.headers.get('User-Agent', '')}"
        )
        try:
            update_session_record(None, "registration_success", {
                'email': email,
                'ip': request.remote_addr,
                'user_agent': request.headers.get('User-Agent', ''),
            })
        except Exception as e:
            logger.exception(f"Failed to update session record for registration_success: {e}")

        return redirect(url_for("auth.login_page"))

    # Registration failed: update session record and log
    logger.warning(
        f"Registration failed for {email}. Reason: {error}. "
        f"IP: {request.remote_addr}, User-Agent: {request.headers.get('User-Agent', '')}"
    )
    try:
        update_session_record(None, "registration_failed", {
            'email': email,
            'reason': error,
            'ip': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', ''),
        })
    except Exception as e:
        logger.exception(f"Failed to update session record for registration_failed: {e}")

    return render_template("register.html", message=error)


@auth_bp.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "GET":
        logger.info("Login page accessed")
        return render_template("login.html")

    # POST logic
    email = request.form.get("email")
    password = request.form.get("password")

    if authenticate_user(email, password):
        session_id = str(uuid.uuid4())
        session["user"] = email
        session["session_id"] = session_id

        # Create and update session records (wrapped in try/except to avoid breaking auth flow)
        try:
            create_session_record(request, email, session_id)
            update_session_record(session_id, "login_success")
        except Exception as e:
            logger.exception(f"Failed to create/update session record after login: {e}")

        logger.info(
            f"User {email} logged in successfully with session ID {session_id} "
            f"from IP {request.remote_addr}, User-Agent: {request.headers.get('User-Agent', '')}"
        )
        return redirect(url_for("chat.chat_page", session_id=session_id))

    # Login failed: update session record and log
    try:
        update_session_record(None, "login_failed", {
            'email': email,
            'ip': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', ''),
        })
    except Exception as e:
        logger.exception(f"Failed to update session record for login_failed: {e}")

    logger.warning(
        f"Failed login attempt for {email} "
        f"from IP {request.remote_addr}, User-Agent: {request.headers.get('User-Agent', '')}"
    )

    flash("Invalid email or password", "error")
    return render_template("login.html", message="Invalid email or password")


@auth_bp.route("/google-login", methods=["POST"])
def google_login():
    """
    Accepts form POST with 'email' (e.g., from a Google OAuth callback or client-side form).
    If the user doesn't exist, auto-register them (using parts of their email as firstname).
    Creates a session and returns session_id JSON.
    """
    email = request.form.get("email")
    logger.info(f"Google login attempt for {email}")

    # Check if user exists in backend
    existing_user = get_user_contact_info(email)

    if not existing_user:
        logger.info(f"User {email} not found in backend. Registering now...")
        try:
            register_user(
                firstname=email.split("@")[0],
                email=email,
                phone="-",
                country="-",
                state="-",
                location="-",
                city="-",
                password="google_oauth",
            )
        except Exception as e:
            logger.exception(f"Auto-registration during google-login failed for {email}: {e}")
            try:
                update_session_record(None, "google_login_failed", {
                    'email': email,
                    'reason': str(e),
                    'ip': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent', ''),
                })
            except Exception:
                pass
            return jsonify({"error": "Google login failed"}), 500

    # create session
    session_id = str(uuid.uuid4())
    session["user"] = email
    session["session_id"] = session_id

    try:
        create_session_record(request, email, session_id)
        update_session_record(session_id, "google_login_success")
    except Exception as e:
        logger.exception(f"Failed to create/update session record after google login: {e}")

    logger.info(f"Google login: Created session for {email} with session ID {session_id}")

    # Return session ID in JSON response
    return jsonify({"session_id": session_id}), 200


@auth_bp.route("/logout")
def logout():
    session_id = session.get("session_id")
    user_email = session.get("user")

    if session_id:
        try:
            update_session_record(session_id, "logout")
        except Exception as e:
            logger.exception(f"Failed to update session record for logout: {e}")
        logger.info(f"User {user_email} logged out from session {session_id}")
    else:
        logger.warning("Logout attempted without active session")

    session.clear()
    return redirect(url_for("auth.home_page"))
