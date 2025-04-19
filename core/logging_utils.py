"""
Centralized logging configuration for the university food system.
Provides standard logging utilities to be used across the application.
"""
import logging
import os
from pythonjsonlogger import jsonlogger
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

# Configure logging integration with Sentry
sentry_logging = LoggingIntegration(
    level=logging.INFO,        # Minimum level to send to Sentry
    event_level=logging.ERROR  # Minimum level to send as events to Sentry
)

def get_logger(name):
    """
    Get a logger configured with the standard format and settings.
    
    Args:
        name: Usually __name__ of the calling module
        
    Returns:
        A configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Only configure handlers if they haven't been added yet
    if not logger.handlers:
        # Set the log level based on environment or default to INFO
        log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
        logger.setLevel(getattr(logging, log_level))
        
        # Create a console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level))
        
        # Create JSON formatter for structured logging
        formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d %(funcName)s',
            rename_fields={'levelname': 'severity', 'asctime': 'timestamp'}
        )
        console_handler.setFormatter(formatter)
        
        # Add the handler to the logger
        logger.addHandler(console_handler)
    
    return logger
