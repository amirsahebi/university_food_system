#!/bin/bash

# Database Backup Script for University Food System

# Exit on any error
set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | xargs)
fi

# Backup directory
BACKUP_DIR="/var/backups/university_food_system"
mkdir -p "$BACKUP_DIR"

# Timestamp for backup filename
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/db_backup_${TIMESTAMP}.sql.gz"

# Perform backup
pg_dump \
    -h "${DB_HOST:-localhost}" \
    -p "${DB_PORT:-5432}" \
    -U "${DB_USER:-postgres}" \
    -d "${DB_NAME:-university_food_system}" \
    | gzip > "$BACKUP_FILE"

# Rotate backups (keep last 7 daily backups)
find "$BACKUP_DIR" -name "db_backup_*.sql.gz" -mtime +7 -delete

# Optional: Send notification or log backup status
echo "Database backup completed: $BACKUP_FILE"

# Optional: Remote backup to cloud storage
# aws s3 cp "$BACKUP_FILE" s3://your-backup-bucket/database-backups/
