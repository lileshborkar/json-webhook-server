@echo off
SETLOCAL

REM --- Configuration ---
SET "BACKUP_DIR=backups"
SET "DB_FILE=webhook_data.db"

REM Create a reliable, filesystem-safe timestamp (YYYY-MM-DD_HH-MM-SS)
SET "TIMESTAMP=%date:~-4,4%-%date:~-10,2%-%date:~-7,2%_%time:~0,2%-%time:~3,2%-%time:~6,2%"
SET "TIMESTAMP=%TIMESTAMP: =0%"
SET "DB_BACKUP_NAME=db_backup_%TIMESTAMP%.db"
SET "PROJECT_BACKUP_NAME=project_archive_%TIMESTAMP%.zip"

REM --- Main Script ---

REM Check for dependencies first
where 7z >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: '7z.exe' command not found.
    echo Please install 7-Zip and add it to your system's PATH.
    goto:eof
)

REM Create backup directory if it doesn't exist
IF NOT EXIST "%BACKUP_DIR%" (
    mkdir "%BACKUP_DIR%"
    echo Backup directory created at: %BACKUP_DIR%
)

REM 1. Backup the database
IF EXIST "%DB_FILE%" (
    copy "%DB_FILE%" "%BACKUP_DIR%\%DB_BACKUP_NAME%" > nul
    echo Database backed up to: %BACKUP_DIR%\%DB_BACKUP_NAME%
) ELSE (
    echo Warning: Database file '%DB_FILE%' not found. Skipping database backup.
)

REM 2. Backup the project files (excluding venv, backups, and git)
echo Creating project archive...
REM Use 7-Zip to create a zip archive. The -x flag excludes files/directories.
7z a -tzip "%BACKUP_DIR%\%PROJECT_BACKUP_NAME%" -r -x!venv -x!backups -x!*.zip -x!.git -x!__pycache__ > nul
if %errorlevel% equ 0 (
    echo Project files archived to: %BACKUP_DIR%\%PROJECT_BACKUP_NAME%
    echo Backup process complete.
) else (
    echo Error: Failed to create project archive. Please check permissions.
)

ENDLOCAL