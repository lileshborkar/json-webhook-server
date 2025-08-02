import sqlite3
import json
from typing import Any, Optional, Tuple
from datetime import datetime, timezone
import uuid
import math

class DbManager:
    """A class to manage all database interactions."""

    def __init__(self, connection: sqlite3.Connection):
        """Initializes the DbManager with a database connection."""
        self.db = connection

    def get_total_webhook_count(self) -> int:
        """Returns the total number of webhooks."""
        return self.db.execute('SELECT COUNT(id) FROM webhooks').fetchone()[0]

    def get_stats_today(self, table: str) -> int:
        """Returns the count of entries from the last 24 hours for a given table."""
        query = f"SELECT COUNT(id) FROM {table} WHERE timestamp >= datetime('now', '-24 hours')"
        return self.db.execute(query).fetchone()[0]

    def get_daily_counts(self, table: str, date_column: str, date_alias: str = 'event_date', days: int = 7) -> list[dict[str, Any]]:
        """Fetches daily event counts from a table for the last N days."""
        query = f"""
            SELECT date({date_column}) as {date_alias}, COUNT(id) as count
            FROM {table}
            WHERE date({date_column}) >= date('now', '-{days} days')
            GROUP BY {date_alias}
            ORDER BY {date_alias} ASC
        """
        rows = self.db.execute(query).fetchall()
        return [dict(row) for row in rows]

    def get_all_webhooks_paginated(self, page: int, per_page: int) -> dict[str, Any]:
        """Retrieves a paginated list of all webhooks."""
        count_result = self.db.execute('SELECT COUNT(id) FROM webhooks').fetchone()
        total_webhooks = count_result[0]
        
        total_pages = math.ceil(total_webhooks / per_page)
        offset = (page - 1) * per_page

        webhooks_list = self.db.execute(
            'SELECT * FROM webhooks ORDER BY created_at DESC LIMIT ? OFFSET ?',
            (per_page, offset)
        ).fetchall()
        
        return {
            'webhooks': webhooks_list,
            'total_pages': total_pages,
            'current_page': page
        }

    def create_webhook(self, host_url: str) -> Tuple[str, str]:
        """Creates a new webhook and returns its ID and full URL."""
        webhook_id = str(uuid.uuid4())
        full_url = host_url.rstrip('/') + '/webhook/' + webhook_id
        created_at = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            'INSERT INTO webhooks (id, url, created_at) VALUES (?, ?, ?)',
            (webhook_id, full_url, created_at)
        )
        self.db.commit()
        return webhook_id, full_url

    def get_webhook(self, webhook_id: str) -> Optional[sqlite3.Row]:
        """Retrieves a single webhook by its ID."""
        return self.db.execute('SELECT * FROM webhooks WHERE id = ?', (webhook_id,)).fetchone()

    def record_successful_payload(self, webhook_id: str, data: dict) -> Tuple[int, str]:
        """Records a successful payload, updates stats, and returns the new payload ID and timestamp."""
        timestamp = datetime.now(timezone.utc).isoformat()
        cursor = self.db.cursor()
        cursor.execute(
            'INSERT INTO webhook_payloads (webhook_id, timestamp, payload) VALUES (?, ?, ?)',
            (webhook_id, timestamp, json.dumps(data))
        )
        new_payload_id = cursor.lastrowid
        self.db.execute(
            'UPDATE webhooks SET success_count = success_count + 1, last_payload_at = ? WHERE id = ?',
            (timestamp, webhook_id)
        )
        self.db.commit()
        return new_payload_id, timestamp

    def record_failed_payload(self, webhook_id: str) -> None:
        """Records a failed payload reception and updates stats."""
        timestamp = datetime.now(timezone.utc).isoformat()
        self.db.execute('UPDATE webhooks SET failure_count = failure_count + 1 WHERE id = ?', (webhook_id,))
        self.db.execute('INSERT INTO webhook_failures (webhook_id, timestamp) VALUES (?, ?)', (webhook_id, timestamp))
        self.db.commit()

    def get_payloads_for_webhook_paginated(self, webhook_id: str, page: int, per_page: int) -> dict[str, Any]:
        """Retrieves a paginated list of payloads for a specific webhook."""
        count_result = self.db.execute('SELECT COUNT(id) FROM webhook_payloads WHERE webhook_id = ?', (webhook_id,)).fetchone()
        total_payloads = count_result[0]
        
        total_pages = math.ceil(total_payloads / per_page)
        offset = (page - 1) * per_page

        payloads_data = self.db.execute(
            'SELECT id, timestamp, payload FROM webhook_payloads WHERE webhook_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?',
            (webhook_id, per_page, offset)
        ).fetchall()
        
        return {
            'payloads': payloads_data,
            'total_pages': total_pages,
            'current_page': page
        }

    def get_all_payloads_for_webhook(self, webhook_id: str) -> list[sqlite3.Row]:
        """Retrieves all payloads for a specific webhook (for download)."""
        return self.db.execute(
            'SELECT timestamp, payload FROM webhook_payloads WHERE webhook_id = ? ORDER BY timestamp DESC',
            (webhook_id,)
        ).fetchall()

    def delete_webhook(self, webhook_id: str) -> None:
        """Deletes a webhook and its associated data."""
        self.db.execute('DELETE FROM webhooks WHERE id = ?', (webhook_id,))
        self.db.commit()

    def get_single_payload(self, payload_id: int) -> Optional[sqlite3.Row]:
        """Retrieves a single payload by its ID."""
        return self.db.execute('SELECT payload FROM webhook_payloads WHERE id = ?', (payload_id,)).fetchone()