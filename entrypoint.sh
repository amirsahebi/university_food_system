#!/bin/bash
set -e

# Run database migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Start Gunicorn
exec gunicorn \
    --config gunicorn_config.py \
    university_food_system.wsgi:application
