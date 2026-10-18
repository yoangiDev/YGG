# Tests package
import os

# The tests run in test mode, as in CI, whatever the local .env says (ENVIRONMENT=development). In test mode the
# database engine has no pool (app/db/session.py): each test runs in its own event loop, and an asyncpg connection
# opened in an earlier test's blows up with "Event loop is closed". It goes here and not in conftest.py because
# pytest loads this package first, and the engine is created when the app is imported.
os.environ["ENVIRONMENT"] = "test"
