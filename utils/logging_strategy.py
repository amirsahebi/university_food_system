import logging
import os
from logging.handlers import RotatingFileHandler
from django.conf import settings

def get_logger(name):
    """Create and configure a logger with structured logging."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        '{"timestamp": "%(asctime)s", "name": "%(name)s", "severity": "%(levelname)s", "message": "%(message)s", "pathname": "%(pathname)s", "lineno": %(lineno)d, "funcName": "%(funcName)s"}'
    )

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Create file handler if LOGS_DIR is set
    if hasattr(settings, 'LOGS_DIR') and os.path.exists(settings.LOGS_DIR):
        file_handler = RotatingFileHandler(
            os.path.join(settings.LOGS_DIR, f'{name}.log'),
            maxBytes=1024 * 1024 * 10,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

def create_audit_log(user_id, action, details):
    """Create an audit log entry."""
    logger = get_logger('audit')
    logger.info(f"User {user_id} performed {action}: {details}")

def security_log(severity, message, user_id=None):
    """Create a security log entry."""
    logger = get_logger('security')
    if severity == 'info':
        logger.info(message)
    elif severity == 'warning':
        logger.warning(message)
    elif severity == 'error':
        logger.error(message)
    elif severity == 'critical':
        logger.critical(message)
