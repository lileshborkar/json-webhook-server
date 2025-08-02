import pytest
import base64

# We need to import the app and the init_db function from your main application file.
# To make this work, pytest needs to see the root directory. You can run pytest
# from the root directory of your project.
from app import app, init_db

@pytest.fixture
def client():
    """A test client for the app."""
    # Use a shared in-memory database for tests. This is faster and avoids
    # all filesystem locking issues, especially on Windows.
    # The 'cache=shared' is crucial to ensure all connections in the test
    # see the same database.
    db_path = "file:memdb_for_test?mode=memory&cache=shared"

    # Update the app's configuration for testing
    app.config.update({
        "TESTING": True,
        "DATABASE": db_path,
        "DATABASE_URI": True, # Tell the app to connect using URI mode
        "WTF_CSRF_ENABLED": False, # Disable CSRF for simpler testing if you use forms
        "SECRET_KEY": "test-secret-key" # Use a consistent secret key for tests
    })

    # Initialize the database with our schema
    with app.app_context():
        init_db()

    # Yield the test client to the test functions
    yield app.test_client()

@pytest.fixture
def auth_headers():
    """A pytest fixture that provides authorization headers for tests."""
    credentials = base64.b64encode(b"admin:supersecret").decode("utf-8")
    return {'Authorization': f'Basic {credentials}'}