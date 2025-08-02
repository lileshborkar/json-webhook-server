import base64
from app import app
import json

def test_unauthorized_access(client):
    """
    GIVEN a test client
    WHEN the '/' page is requested without credentials
    THEN check that a 401 'Unauthorized' response is returned
    """
    response = client.get('/')
    assert response.status_code == 401

def test_dashboard_access_with_auth(client, auth_headers):
    """
    GIVEN a test client
    WHEN the '/' page is requested with correct credentials
    THEN check that a 200 'OK' response is returned and the page contains 'Dashboard'
    """
    response = client.get('/', headers=auth_headers)
    assert response.status_code == 200
    assert b"Dashboard" in response.data

def test_generate_webhook(client, auth_headers):
    """
    GIVEN an authenticated client
    WHEN a POST request is sent to /generate
    THEN check that the response is a redirect and a new webhook is created in the DB
    """
    # Use the app context to interact with the database directly and get the initial state
    with app.app_context():
        from app import get_db
        db = get_db()
        initial_count = db.execute('SELECT COUNT(id) FROM webhooks').fetchone()[0]

    # Make the request to generate a new webhook
    response = client.post('/generate', headers=auth_headers)

    # Assert that the request was successful and redirected to the home page
    assert response.status_code == 302
    assert response.headers['Location'] == '/'

    # Assert that a new webhook was added to the database
    with app.app_context():
        from app import get_db
        db = get_db()
        final_count = db.execute('SELECT COUNT(id) FROM webhooks').fetchone()[0]
        assert final_count == initial_count + 1

def test_receive_payload(client):
    """
    GIVEN a client and an existing webhook
    WHEN a POST request with a JSON payload is sent to the webhook URL
    THEN check the response is OK and the payload is stored in the database
    """
    # Setup: Create a webhook directly in the database for this test
    webhook_id = "test-webhook-id-123"
    with app.app_context():
        from app import get_db
        db = get_db()
        db.execute(
            'INSERT INTO webhooks (id, url, created_at) VALUES (?, ?, ?)',
            (webhook_id, f'/webhook/{webhook_id}', '2024-01-01T00:00:00Z')
        )
        db.commit()

    # Action: Send a POST request to the webhook endpoint
    payload = {"key": "value", "test": True}
    response = client.post(f'/webhook/{webhook_id}', json=payload)

    # Assertions
    assert response.status_code == 200
    assert response.json['status'] == 'received'

    # Verify the data was stored correctly in the database
    with app.app_context():
        from app import get_db
        db = get_db()
        stored_payload = db.execute('SELECT payload FROM webhook_payloads WHERE webhook_id = ?', (webhook_id,)).fetchone()
        assert stored_payload is not None
        assert json.loads(stored_payload['payload']) == payload

        webhook_stats = db.execute('SELECT success_count FROM webhooks WHERE id = ?', (webhook_id,)).fetchone()
        assert webhook_stats['success_count'] == 1

def test_receive_bad_payload(client):
    """
    GIVEN a client and an existing webhook
    WHEN a POST request with a non-JSON payload is sent
    THEN check the response is 400 and the failure count is incremented
    """
    # Setup
    webhook_id = "test-webhook-id-456"
    with app.app_context():
        from app import get_db
        db = get_db()
        db.execute('INSERT INTO webhooks (id, url, created_at) VALUES (?, ?, ?)', (webhook_id, f'/webhook/{webhook_id}', '2024-01-01T00:00:00Z'))
        db.commit()

    # Action: Send a POST request with invalid data
    response = client.post(f'/webhook/{webhook_id}', data="this is not json")

    # Assertions
    assert response.status_code == 400
    with app.app_context():
        from app import get_db
        db = get_db()
        webhook_stats = db.execute('SELECT success_count, failure_count FROM webhooks WHERE id = ?', (webhook_id,)).fetchone()
        assert webhook_stats['success_count'] == 0
        assert webhook_stats['failure_count'] == 1

def test_delete_webhook(client, auth_headers):
    """
    GIVEN an authenticated client and an existing webhook with payloads
    WHEN a POST request is sent to /delete/<webhook_id>
    THEN check the webhook and its associated payloads are deleted from the database
    """
    # Setup: Create a webhook and some payloads for it
    webhook_id = "test-webhook-to-delete"
    with app.app_context():
        from app import get_db
        db = get_db()
        db.execute('INSERT INTO webhooks (id, url, created_at) VALUES (?, ?, ?)',
                   (webhook_id, f'/webhook/{webhook_id}', '2024-01-01T00:00:00Z'))
        db.execute('INSERT INTO webhook_payloads (webhook_id, timestamp, payload) VALUES (?, ?, ?)',
                   (webhook_id, '2024-01-01T01:00:00Z', '{}'))
        db.execute('INSERT INTO webhook_payloads (webhook_id, timestamp, payload) VALUES (?, ?, ?)',
                   (webhook_id, '2024-01-01T02:00:00Z', '{}'))
        db.commit()

        # Verify setup
        assert db.execute('SELECT COUNT(id) FROM webhooks WHERE id = ?', (webhook_id,)).fetchone()[0] == 1
        assert db.execute('SELECT COUNT(id) FROM webhook_payloads WHERE webhook_id = ?', (webhook_id,)).fetchone()[0] == 2

    # Action: Send the delete request
    response = client.post(f'/delete/{webhook_id}', headers=auth_headers)

    # Assertions
    assert response.status_code == 302 # Should redirect after delete
    assert response.headers['Location'] == '/'

    # Verify deletion from the database
    with app.app_context():
        from app import get_db
        db = get_db()
        webhook_count = db.execute('SELECT COUNT(id) FROM webhooks WHERE id = ?', (webhook_id,)).fetchone()[0]
        payload_count = db.execute('SELECT COUNT(id) FROM webhook_payloads WHERE webhook_id = ?', (webhook_id,)).fetchone()[0]
        assert webhook_count == 0
        assert payload_count == 0