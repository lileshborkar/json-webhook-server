#!/bin/bash

# --- Configuration ---
BACKUP_DIR="backups" # Directory to store all backups
DB_FILE="webhook_data.db" # The database file to back up
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S") # Consistent timestamp for this backup run
DB_BACKUP_NAME="db_backup_${TIMESTAMP}.db" # Name for the database backup file
PROJECT_BACKUP_NAME="project_archive_${TIMESTAMP}.zip" # Name for the project zip file

# --- Main Script ---

# Check for dependencies first
if ! command -v zip &> /dev/null; then
    echo "Error: 'zip' command is not installed or not in your PATH. Please install it and try again."
    exit 1
fi

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"
echo "Backup directory ensured at: $BACKUP_DIR"

# 1. Backup the database
if [ -f "$DB_FILE" ]; then
    cp "$DB_FILE" "$BACKUP_DIR/$DB_BACKUP_NAME"
    echo "Database backed up to: $BACKUP_DIR/$DB_BACKUP_NAME"
else
    echo "Warning: Database file '$DB_FILE' not found. Skipping database backup."
fi

# 2. Backup the project files (excluding venv, backups, and git)
echo "Creating project archive..."
if zip -r "$BACKUP_DIR/$PROJECT_BACKUP_NAME" . -x "venv/*" -x "$BACKUP_DIR/*" -x "*.zip" -x ".git/*" -x "__pycache__/*" > /dev/null; then
    echo "Project files archived to: $BACKUP_DIR/$PROJECT_BACKUP_NAME"
    echo "Backup process complete."
else
    echo "Error: Failed to create project archive. Please check permissions and ensure 'zip' is installed."
    exit 1
fi