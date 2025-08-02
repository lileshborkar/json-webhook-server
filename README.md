# JSON Webhook Server

A simple yet powerful Flask application that provides an intuitive dashboard for creating, managing, and inspecting JSON payloads from webhooks. Instantly generate unique URLs to test and debug your webhook integrations in real-time.

## Features

- Generate unique webhook endpoints.
- Receive and store any JSON payload sent via POST request.
- View a dashboard with statistics and recently active webhooks.
- View a detailed list of all received payloads for each webhook.
- Download all data for a specific webhook as a JSON file.
- Auto-refreshing data view to see new payloads as they arrive.
- Delete webhooks and their associated data.

## Screenshots

**Main Dashboard:** At-a-glance statistics and activity charts.
![Main Dashboard](images/Jason-webhook-server.PNG)

**Generate a Webhook:** After clicking "Generate New Webhook", the new URL and ID are instantly displayed.
![Generating a Webhook](images/generate-new-webhook.PNG)

**View All Webhooks:** A paginated list of all generated webhooks with their stats.
![All Webhooks Page](images/all-webhooks.PNG)

**Inspect Payloads in Real-Time:** The detailed view for a webhook shows all received payloads. New payloads appear at the top automatically without needing a page refresh.

*Initial payload received:*
![Payload View 1](images/testing%201.PNG)

*As more payloads arrive, they are added to the top of the list instantly:*
![Payload View 2](images/testing%202.PNG)

## Prerequisites

- Python 3.x
- `pip` and `venv`

## Technology Stack

-   **Backend:** Flask, Flask-SocketIO
-   **Real-time Communication:** WebSockets (via gevent)
-   **Frontend:** HTML5, Bootstrap 5, Chart.js
-   **Database:** SQLite
-   **Authentication:** HTTP Basic Auth



## Setup and Running the Project

Follow these steps to get the application running on your local machine.

1.  **Create and activate a virtual environment:**

    Open your terminal in the project's root directory and run:

    ```bash
    # Create the virtual environment
    python -m venv venv
    ```

    Activate it:
    -   **On Windows:**
        ```bash
        .\venv\Scripts\activate
        ```
    -   **On macOS & Linux:**
        ```bash
        source venv/bin/activate
        ```

2.  **Install the dependencies:**

    With the virtual environment activated, install the required packages from `requirements.txt`:

    ```bash
    pip install -r requirements.txt
    ```
    > **Note:** For more reproducible builds, it's recommended to pin your dependency versions. You can do this by running `pip freeze > requirements.txt` after installation.

3.  **Run the application:**

    Execute the `app.py` script:

    ```bash
    python app.py
    ```
    
    You should see a message in your terminal indicating that the server has started:
    ```
    --> Starting Flask-SocketIO server on http://127.0.0.1:5000
    ```

4.  **Access the application:**

    Open your web browser and navigate to http://127.0.0.1:5000. The application will create a `webhook_data.db` SQLite database file in the project directory on its first run.

## Authentication

The web interface is protected by Basic Authentication. When you first access the site, you will be prompted for a username and password.

-   **Username:** `admin`
-   **Password:** `supersecret`

> **Security Note:** These default credentials are provided for convenience during local development. For any real-world deployment, you should override them using environment variables (`ADMIN_USER` and `ADMIN_PASSWORD`) for better security.

The webhook receiver endpoint (`/webhook/<id>`) does not require authentication, so services can post data without needing credentials.

## Running Tests

This project uses `pytest` for running automated tests.

1.  **Install Testing Dependencies:**
    Make sure you have activated your virtual environment and installed the main dependencies from `requirements.txt`. You also need to install `pytest`:
    ```bash
    pip install pytest
    ```

2.  **Run the Test Suite:**
    From the root directory of the project, simply run the `pytest` command:
    ```bash
    pytest
    ```
    The tests will run using a separate, temporary database to avoid interfering with your development data.

## How to Use

1.  **Generate a Webhook URL:**
    -   On the main dashboard, click the "Generate New Webhook" button.
    -   A new unique webhook URL and ID will be displayed in an alert box at the top of the dashboard.

2.  **Send Data to the Webhook:**
    -   Copy the full URL of your new webhook.
    -   Send a `POST` request to this URL with a JSON body. You can use any tool like `curl`, Postman, or integrate it into your own applications.

3.  **View Received Data:**
    -   The dashboard statistics will update to reflect new activity.
    -   Click the "Check Received Payloads" button (for a new webhook) or the "View" button (from the "All Webhooks" list) to go to a detailed view.
    -   The detailed view lists all payloads received by that webhook, with timestamps.

4.  **Manage Webhooks:**
    -   **Download:** On the detailed view page, you can download all payloads for a webhook at once, or download each payload individually.
    -   **Delete:** On the "All Webhooks" page, click the "Delete" button to permanently remove a webhook and all its associated data.

## Backing Up Data

The project includes a simple backup script (`backup.sh`) to help you save your data.

The script performs two main actions:
1.  Creates a timestamped copy of the SQLite database (`webhook_data.db`) in the `backups/` directory.
2.  Creates a timestamped zip archive of the entire project, excluding the virtual environment, the backups directory, and other unnecessary files.

To run the backup script:

### On Windows

Use the `backup_project.bat` script. You can either double-click the file in Windows Explorer or run it from the Command Prompt or PowerShell:

```cmd
backup_project.bat
```

### On macOS & Linux

Use the `backup.sh` script.

```bash
# Make the script executable (only needs to be done once)
chmod +x backup.sh

# Run the script
./backup.sh
```

## API Endpoints

### `POST /webhook/<webhook_id>`

This is the primary endpoint for receiving data.

-   **Method:** `POST`
-   **Content-Type:** `application/json`
-   **Body:** Any valid JSON object.
-   **Success Response (200):** `{"status": "received", "timestamp": "..."}`