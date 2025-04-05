#!/bin/bash

# Set user and group IDs to match host system
if [ -n "$DJANGO_UID" ] && [ -n "$DJANGO_GID" ]; then
    # Check if the user already exists
    if id djangouser &>/dev/null; then
        # Modify existing user
        usermod -u "$DJANGO_UID" djangouser
        groupmod -g "$DJANGO_GID" djangouser
    else
        # Create user with specified UID/GID
        groupadd -g "$DJANGO_GID" djangouser
        useradd -u "$DJANGO_UID" -g djangouser -m djangouser
    fi

    # Ensure media and static directories exist and have correct permissions
    mkdir -p /app/media /app/staticfiles
    chmod 777 /app/media /app/staticfiles
fi

# Apply database migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Start Gunicorn
exec gunicorn \
    --config gunicorn_config.py \
    university_food_system.wsgi:application
