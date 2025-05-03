from functools import wraps
from utils.logging_strategy import get_logger

logger = get_logger('tasks')

def task_with_logging(task_func=None, *, task_name=None):
    """Decorator to add logging to Celery tasks."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                logger.info(f"Starting task {task_name or func.__name__} with args: {args}, kwargs: {kwargs}")
                result = func(*args, **kwargs)
                logger.info(f"Completed task {task_name or func.__name__} successfully")
                return result
            except Exception as e:
                logger.error(f"Task {task_name or func.__name__} failed: {str(e)}", exc_info=True)
                raise
        return wrapper
    
    if task_func:
        return decorator(task_func)
    return decorator
