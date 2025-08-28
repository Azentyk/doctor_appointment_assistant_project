import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logging():
    """Configure logging with rotating .txt file handler"""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Rotating text log file (app.log, app.log.1, app.log.2, etc.)
    file_handler = RotatingFileHandler(
        f'{log_dir}/app.txt',
        maxBytes=1024*1024*5,  # 5 MB
        backupCount=5,         # keep last 5 rotated files
        encoding="utf-8"
    )

    # Console output for debugging
    console_handler = logging.StreamHandler()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[file_handler, console_handler]
    )
