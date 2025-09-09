import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pymongo import MongoClient


def setup_logging():
    """Configure logging with rotating file, console, and a resilient MongoDB handler.

    Environment variables:
      - LOG_DIR: directory to write rotated logs (default: ./logs)
      - LOG_LEVEL: logging level name (default: INFO)
      - MONGO_URI: MongoDB connection URI (default: mongodb://localhost:27017/)
      - MONGO_DB: MongoDB database name for logs (default: patient_db)
      - MONGO_COLLECTION: MongoDB collection name for logs (default: app_logs)
    """
    # Read configuration from environment with sensible defaults
    log_dir = os.getenv("LOG_DIR", os.path.join(os.getcwd(), "logs"))
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    mongo_db = os.getenv("MONGO_DB", "patient_db")
    mongo_collection = os.getenv("MONGO_COLLECTION", "app_logs")

    # Ensure log directory exists
    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception:
        # If we can't create the directory, fallback to current working directory
        log_dir = os.getcwd()

    log_file = os.path.join(log_dir, "app.txt")

    # Determine numeric log level
    level = getattr(logging, log_level_name, logging.INFO)

    # Rotating text log file (app.txt, app.txt.1, ...)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(level)

    # Console output
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    # Configure root logger
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[file_handler, console_handler],
    )

    # Define a resilient MongoDB handler
    class MongoDBHandler(logging.Handler):
        def __init__(self, uri: str, db_name: str, collection_name: str):
            super().__init__()
            self._uri = uri
            self._db_name = db_name
            self._collection_name = collection_name
            self._client = None
            self._collection = None

            # Try to create a client but don't raise on failure
            try:
                # short timeout so the app doesn't hang on startup if Mongo is unreachable
                self._client = MongoClient(self._uri, serverSelectionTimeoutMS=5000)
                # Attempt a server selection to validate connection
                self._client.admin.command('ping')
                self._collection = self._client[self._db_name][self._collection_name]
            except Exception as e:
                # Keep the handler alive even if Mongo is not available
                self._client = None
                self._collection = None
                # Use fallback: write a debug message to standard error
                try:
                    import sys
                    sys.stderr.write(f"[logger] Could not connect to MongoDB: {e}\n")
                except Exception:
                    pass

        def emit(self, record: logging.LogRecord) -> None:
            try:
                if not self._collection:
                    # If MongoDB isn't available, skip writing to DB
                    return

                # Build a structured log entry
                now = datetime.utcnow().isoformat() + "Z"
                log_entry = {
                    "timestamp": now,
                    "level": record.levelname,
                    "message": record.getMessage(),
                    "logger_name": record.name,
                    "module": record.module,
                    "funcName": record.funcName,
                    "lineno": record.lineno,
                }

                # Include exception info if present
                if record.exc_info:
                    try:
                        import traceback
                        log_entry["exception"] = "\n".join(traceback.format_exception(*record.exc_info))
                    except Exception:
                        pass

                # Insert into MongoDB
                self._collection.insert_one(log_entry)
            except Exception:
                # Never let logging failures crash the app
                try:
                    import sys
                    sys.stderr.write("[logger] Failed to emit log to MongoDB\n")
                except Exception:
                    pass

    # Attach MongoDB handler
    try:
        mongo_handler = MongoDBHandler(mongo_uri, mongo_db, mongo_collection)
        mongo_handler.setLevel(level)
        logging.getLogger().addHandler(mongo_handler)
    except Exception:
        # If handler construction fails for any reason, don't block the app
        logging.getLogger().exception("Failed to initialize MongoDB logging handler")

    logging.getLogger().info("Logging is set up successfully.")
