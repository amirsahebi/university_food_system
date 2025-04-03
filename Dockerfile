FROM python:3.11.11-slim-bullseye

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV APP_HOME=/app
ENV APP_USER=djangouser

# Create app directory and set working directory
RUN mkdir -p ${APP_HOME} \
    && groupadd -r ${APP_USER} \
    && useradd -r -g ${APP_USER} -d ${APP_HOME} ${APP_USER}

# Set working directory
WORKDIR ${APP_HOME}

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    netcat \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY --chown=${APP_USER}:${APP_USER} requirements.txt ${APP_HOME}/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY --chown=${APP_USER}:${APP_USER} . ${APP_HOME}/

# Ensure correct permissions for the entire app directory
RUN chown -R ${APP_USER}:${APP_USER} ${APP_HOME}

# Collect static files
RUN python manage.py collectstatic --noinput

# Set up entrypoint
COPY --chown=${APP_USER}:${APP_USER} entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Switch to non-root user
USER ${APP_USER}

# Expose port for the app
EXPOSE 8000

# Set the default command
CMD ["/bin/bash", "/entrypoint.sh"]
