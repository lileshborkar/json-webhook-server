from flask import Flask, request, jsonify, render_template, redirect, url_for, Response, g, abort, flash
from flask_cors import CORS # type: ignore
from flask_socketio import SocketIO, join_room
from flask_httpauth import HTTPBasicAuth
from datetime import datetime, timezone
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
import json
from typing import Any, Tuple
import sqlite3
import os
import click
from db_manager import DbManager

app = Flask(__name__)
app.secret_key = os.urandom(24) # Required for flash messages
socketio = SocketIO(app, async_mode='gevent')
CORS(app)
auth = HTTPBasicAuth()

# For simplicity, credentials are in-memory.
# In a real app, use environment variables. This implementation falls back to
# the original credentials if environment variables are not set. The password
# is now hashed for better security.
users = {
    os.environ.get("ADMIN_USER", "admin"): generate_password_hash(os.environ.get("ADMIN_PASSWORD", "supersecret"))
}

@auth.verify_password
def verify_password(username: str, password: str) -> str | None:
    """Verify user credentials against the stored hashed password."""
    if username in users and check_password_hash(users.get(username), password):
        return username
    return None

# ---------- DATABASE SETUP ----------
app.config.setdefault('DATABASE', 'webhook_data.db')
app.config.setdefault('DATABASE_URI', False) # Support for in-memory DB URIs for testing
app.config.setdefault('PAYLOADS_PER_PAGE', 20)

def get_db() -> sqlite3.Connection:
    """
    Connect to the application's configured database.
    The connection is unique for each request and will be reused if this is called again.
    """
    if 'db' not in g:
        g.db = sqlite3.connect(
            app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES,
            uri=app.config.get('DATABASE_URI', False)
        )
        g.db.row_factory = sqlite3.Row  # Allows accessing columns by name
        g.db.execute('PRAGMA foreign_keys = ON') # Enable foreign key support
    return g.db

@app.teardown_appcontext
def close_db(e: Exception | None = None) -> None:
    """If this request connected to the database, close the connection."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db() -> None:
    """
    Initialize the database by connecting and creating tables if they don't exist.
    """
    conn = sqlite3.connect(
        app.config['DATABASE'],
        uri=app.config.get('DATABASE_URI', False)
    )
    with conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS webhooks (
                id TEXT PRIMARY KEY,
                url TEXT,
                created_at TEXT,
                success_count INTEGER NOT NULL DEFAULT 0,
                failure_count INTEGER NOT NULL DEFAULT 0,
                last_payload_at TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS webhook_payloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                webhook_id TEXT,
                timestamp TEXT,
                payload TEXT,
                FOREIGN KEY(webhook_id) REFERENCES webhooks(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS webhook_failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                webhook_id TEXT,
                timestamp TEXT,
                FOREIGN KEY(webhook_id) REFERENCES webhooks(id) ON DELETE CASCADE
            )
        ''')
        conn.commit()

@app.cli.command('init-db')
def init_db_command() -> None:
    """Clears the existing data and creates new tables."""
    init_db()
    click.echo('Initialized the database.')

# ---------- HELPERS ----------

def get_webhook_or_404(webhook_id: str) -> sqlite3.Row:
    """Get a webhook by ID, aborting with 404 if not found."""
    db_manager = DbManager(get_db())
    webhook = db_manager.get_webhook(webhook_id)
    if webhook is None:
        abort(404, description=f"Webhook ID {webhook_id} not found.")
    return webhook

@app.template_filter('pretty_json')
def pretty_json_filter(value: str) -> str:
    """Parse a JSON string and pretty-print it."""
    try:
        return json.dumps(json.loads(value), indent=2)
    except (json.JSONDecodeError, TypeError):
        return value # Return original value if it's not valid JSON

# ---------- ROUTES ----------
@app.route('/')
@auth.login_required
def index() -> str:
    """Renders the main dashboard page with statistics and charts."""
    db_manager = DbManager(get_db())
    
    # --- Stat Card Data ---
    total_webhooks = db_manager.get_total_webhook_count()
    success_today = db_manager.get_stats_today('webhook_payloads')
    failures_today = db_manager.get_stats_today('webhook_failures')
    
    # --- Chart Data (Last 7 Days) ---
    chart_creation_data = db_manager.get_daily_counts('webhooks', 'created_at', date_alias='creation_date')
    chart_success_data = db_manager.get_daily_counts('webhook_payloads', 'timestamp')
    chart_failure_data = db_manager.get_daily_counts('webhook_failures', 'timestamp')
    
    # --- Daily Activity Table Data (Last 7 Days) ---
    # Combine all stats into a single structure keyed by date
    all_dates = sorted(list(set([d['creation_date'] for d in chart_creation_data] + [d['event_date'] for d in chart_success_data] + [d['event_date'] for d in chart_failure_data])))
    daily_stats = []
    for date in all_dates:
        daily_stats.append({
            'date': date,
            'created': next((item['count'] for item in chart_creation_data if item['creation_date'] == date), 0),
            'succeeded': next((item['count'] for item in chart_success_data if item['event_date'] == date), 0),
            'failed': next((item['count'] for item in chart_failure_data if item['event_date'] == date), 0)
        })
    
    return render_template('index.html',
                           total_webhooks=total_webhooks,
                           success_today=success_today,
                           failures_today=failures_today,
                           daily_stats=daily_stats,
                           chart_creation_data=chart_creation_data, chart_success_data=chart_success_data, chart_failure_data=chart_failure_data)

@app.route('/webhooks')
@auth.login_required
def list_all_webhooks() -> str:
    """Displays a paginated list of all created webhooks."""
    page = request.args.get('page', 1, type=int)
    per_page = app.config['PAYLOADS_PER_PAGE']
    db_manager = DbManager(get_db())
    
    pagination_data = db_manager.get_all_webhooks_paginated(page, per_page)

    return render_template('webhooks_list.html', webhooks=pagination_data['webhooks'],
                           current_page=pagination_data['current_page'], total_pages=pagination_data['total_pages'])

@app.route('/generate', methods=['POST'])
@auth.login_required
def generate_webhook() -> Response:
    """Generates a new webhook, stores it in the DB, and redirects to the dashboard."""
    db_manager = DbManager(get_db())
    webhook_id, full_url = db_manager.create_webhook(request.host_url)

    # Flash the new webhook details to show on the redirected page
    flash(f"{webhook_id}|{full_url}", 'new_webhook')
    return redirect(url_for('index'))

@app.route('/webhook/<webhook_id>', methods=['POST'])
def webhook(webhook_id: str) -> Response:
    """The public endpoint to receive JSON payloads for a specific webhook."""
    db_manager = DbManager(get_db())
    if not db_manager.get_webhook(webhook_id):
        abort(404, description=f"Webhook ID {webhook_id} not found.")

    try:
        data = request.get_json(force=True)
        new_payload_id, timestamp = db_manager.record_successful_payload(webhook_id, data)

        # Emit a real-time event to clients viewing this webhook's page
        payload_data = {'id': new_payload_id, 'timestamp': timestamp, 'payload': json.dumps(data)}
        socketio.emit('new_payload', payload_data, room=webhook_id)

        return jsonify({"status": "received", "timestamp": timestamp}), 200
    except Exception as e:
        app.logger.error(f"Error processing payload for webhook {webhook_id}: {e}", exc_info=True)
        db_manager.record_failed_payload(webhook_id)
        return jsonify({"error": f"Failed to process request: {e}"}), 400

@app.route('/data/<webhook_id>', methods=['GET'])
@auth.login_required
def show_webhook_data(webhook_id: str) -> str:
    """Displays the details and paginated payloads for a specific webhook."""
    webhook = get_webhook_or_404(webhook_id)
    page = request.args.get('page', 1, type=int)
    per_page = app.config['PAYLOADS_PER_PAGE']
    db_manager = DbManager(get_db())

    pagination_data = db_manager.get_payloads_for_webhook_paginated(webhook_id, page, per_page)

    return render_template('webhook_data.html', webhook=webhook, payloads=pagination_data['payloads'],
                           current_page=pagination_data['current_page'], total_pages=pagination_data['total_pages'])

@app.route('/download/<webhook_id>', methods=['GET'])
@auth.login_required
def download_webhook_data(webhook_id: str) -> Response:
    """Downloads all payloads for a specific webhook as a single JSON file."""
    get_webhook_or_404(webhook_id)
    db_manager = DbManager(get_db())
    payloads = db_manager.get_all_payloads_for_webhook(webhook_id)

    parsed_data = [{"timestamp": row['timestamp'], "payload": json.loads(row['payload'])} for row in payloads]
    json_data = json.dumps(parsed_data, indent=2)

    return Response(
        json_data,
        mimetype='application/json',
        headers={"Content-Disposition": f"attachment;filename=webhook_{webhook_id}.json"}
    )

@app.route('/delete/<webhook_id>', methods=['POST'])
@auth.login_required
def delete_webhook(webhook_id: str) -> Response:
    """Deletes a webhook and all its associated data."""
    get_webhook_or_404(webhook_id)
    db_manager = DbManager(get_db())
    db_manager.delete_webhook(webhook_id)
    return redirect(url_for('index'))

@app.route('/download/payload/<int:payload_id>', methods=['GET'])
@auth.login_required
def download_single_payload(payload_id: int) -> Response:
    """Downloads a single payload as a JSON file."""
    db_manager = DbManager(get_db())
    payload = db_manager.get_single_payload(payload_id)
    if payload is None:
        abort(404, "Payload not found.")
    
    # Pretty-format the JSON for readability
    pretty_payload = json.dumps(json.loads(payload['payload']), indent=2)
    
    return Response(
        pretty_payload,
        mimetype='application/json',
        headers={"Content-Disposition": f"attachment;filename=payload_{payload_id}.json"}
    )

@app.route('/help')
@auth.login_required
def help_page() -> str:
    """Renders the help page."""
    return render_template('help.html')

@socketio.on('join')
def on_join(data: dict) -> None:
    """A client joins a room for a specific webhook."""
    webhook_id = data.get('webhook_id')
    if webhook_id:
        join_room(webhook_id)

if __name__ == '__main__':
    print("--> Starting Flask-SocketIO server on http://127.0.0.1:5000")
    socketio.run(app, debug=True)