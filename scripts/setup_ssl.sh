#!/bin/bash

# SSL Certificate Setup Script for University Food System

# Exit on any error
set -e

# Domain name
DOMAIN="food.university.example.com"

# Email for Let's Encrypt registration
EMAIL="admin@university.example.com"

# Install Certbot
sudo apt-get update
sudo apt-get install -y certbot python3-certbot-nginx

# Obtain SSL Certificate
sudo certbot certonly \
    --nginx \
    -d "$DOMAIN" \
    -m "$EMAIL" \
    --agree-tos \
    --no-eff-email

# Setup automatic renewal
(crontab -l 2>/dev/null; echo "0 0,12 * * * python3 -c 'import random; import time; time.sleep(random.random() * 3600)' && sudo certbot renew --quiet && sudo systemctl reload nginx") | crontab -

echo "SSL Certificate setup completed for $DOMAIN"
