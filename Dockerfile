FROM python:3.11.11-slim-bullseye

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV APP_HOME=/app

# Create app directory and set working directory
RUN mkdir -p ${APP_HOME}/staticfiles ${APP_HOME}/media \
    && chmod 777 ${APP_HOME}/staticfiles ${APP_HOME}/media

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
COPY requirements.txt ${APP_HOME}/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . ${APP_HOME}/

# Collect static files
RUN python manage.py collectstatic --noinput

# Set up entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port for the app
EXPOSE 8000

# Set the default command
CMD ["/bin/bash", "/entrypoint.sh"]
