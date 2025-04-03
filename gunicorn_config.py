import multiprocessing

# Basic Gunicorn Configuration for Local Development
bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
threads = 4
timeout = 120
keepalive = 5

# Logging Configuration
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stdout
loglevel = "info"

# Worker Class
worker_class = "gthread"
