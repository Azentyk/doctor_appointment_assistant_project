# main.py
import os
import sys
import pysqlite3

# Override default sqlite3 with pysqlite3 (needed in some Azure environments)
sys.modules["sqlite3"] = pysqlite3

from flask import Flask, render_template, session
from flask_session import Session
from logger import setup_logging
from db_utils import init_db
from chat_routes import chat_bp
from authentication import auth_bp


def create_app():
    """Flask application factory for Azure/Gunicorn deployment."""
    # Initialize logging first
    setup_logging()

    # Initialize database (ensures collections/indexes exist)
    init_db()

    # Create Flask app
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Secret key (override in production with env var)
    app.secret_key = os.getenv("SECRET_KEY", "your_secret_key")

    # Session configuration (server-side storage with filesystem)
    app.config["SESSION_TYPE"] = "filesystem"
    app.config["SESSION_FILE_DIR"] = os.path.join(os.getcwd(), "flask_session")
    app.config["SESSION_PERMANENT"] = False
    app.config["SESSION_USE_SIGNER"] = True  # add signing for extra safety
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("FLASK_ENV") == "production"

    Session(app)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)

    # Default route
    @app.route("/")
    def index():
        # ensure a session exists
        if "session_id" not in session:
            session["session_id"] = os.urandom(16).hex()
        return render_template("index.html", session_id=session["session_id"])

    return app


# Expose app for Gunicorn / Azure
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
