import pytest
import importlib
from flask import g
from _pytest.monkeypatch import MonkeyPatch
import os
os.environ.setdefault("FLASK_DEBUG", "false")
import uuid
TEST_OWNER_ID = "00000000-0000-0000-0000-000000000000"
# ------------------------------------------------------------------------------
# Patch before Flask imports routes
# ------------------------------------------------------------------------------
mp = MonkeyPatch()

# Import modules directly
import middleware.auth as auth
import middleware.notify as notify_module

# --- Fake decorators ----------------------------------------------------------
def fake_login_required(*args, **kwargs):
    """
    Mock @login_required decorator.
    Accepts arbitrary args/kwargs so tests don't break when real decorator
    includes options like verify_with_supabase=True.
    """
    role = kwargs.get("role", "salon_owner")

    def decorator(fn):
        def wrapper(*fn_args, **fn_kwargs):
            g.user = {
                "sub": TEST_OWNER_ID  if role == "salon_owner" else str(uuid.uuid4()) ,
                "email": "mock@test.com",
                "role": role,
            }
            return fn(*fn_args, **fn_kwargs)
        wrapper.__name__ = fn.__name__
        return wrapper
    return decorator


def fake_role_required(roles=None, **kwargs):
    """
    Mock @role_required decorator.
    Accepts arbitrary kwargs for compatibility.
    """
    role = roles[0] if roles else "salon_owner"

    def decorator(fn):
        def wrapper(*args, **kwargs):
            g.user = {
                "sub": TEST_OWNER_ID if role == "salon_owner" else "admin-uuid",
                "email": "mock@test.com",
                "role": role,
            }
            return fn(*args, **kwargs)
        wrapper.__name__ = fn.__name__
        return wrapper
    return decorator


def fake_notify(*args, **kwargs):
    """No-op @notify decorator."""
    def decorator(func):
        return func
    return decorator


# --- Patch middleware modules -------------------------------------------------
mp.setattr(auth, "login_required", fake_login_required)
mp.setattr(auth, "role_required", fake_role_required)
notify_module.notify = fake_notify  # replace with no-op


# ------------------------------------------------------------------------------
# Import Flask app AFTER patching decorators
# ------------------------------------------------------------------------------
try:
    from app import app
    import routes.salon as salon_routes
    importlib.reload(salon_routes)  # reload so Flask registers with fakes
except ImportError as e:
    # If app can't be imported (missing dependencies), create a minimal mock app
    from flask import Flask
    app = Flask(__name__)
    app.config["TESTING"] = True


# ------------------------------------------------------------------------------
# Flask test client fixture
# ------------------------------------------------------------------------------
@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


# ------------------------------------------------------------------------------
# Mock Supabase interactions
# ------------------------------------------------------------------------------
@pytest.fixture
def mock_supabase(monkeypatch):
    from services import salon_service, notification_service
    import config
    from unittest.mock import Mock

    TEST_OWNER_ID = "00000000-0000-0000-0000-000000000000"
    ADMIN_ID = "admin-uuid"

    db = {
        "users": [{"id": TEST_OWNER_ID, "email": "owner@test.com"}],
        "salons": [],
        "notifications": [],
        "user_profiles": [{"user_id": ADMIN_ID, "role": "admin"}],
        "user_details": [
            {"id": TEST_OWNER_ID, "email": "owner@test.com", "role": "salon_owner"},
            {"id": ADMIN_ID, "email": "admin@test.com", "role": "admin"}
        ],
    }

    # Mock requests.post to prevent actual HTTP calls in _send_email
    mock_requests_post = Mock(return_value=Mock(status_code=200))
    monkeypatch.setattr("services.notification_service.requests.post", mock_requests_post)

    class MockTable:
        def __init__(self, name):
            self.name = name
            self._single = False
            self._filters = {}
            self._select_fields = None

        def insert(self, data):
            if isinstance(data, list):
                data = data[0]
            data = dict(data)
            if self.name == "salons":
                if "id" not in data:
                    data["id"] = f"salon-{len(db['salons'])+1}"
                db["salons"].append(data)
            elif self.name == "notifications":
                if "id" not in data:
                    data["id"] = str(uuid.uuid4())
                db["notifications"].append(data)
            elif self.name == "users":
                db["users"].append(data)

            # Simulate Supabase returning an object with .execute()
            class Result:
                def __init__(self, d): self.data = [d]
                def execute(self): return self

            return Result(data)

        def update(self, data):
            # Simulate update by replacing fields on last record
            if self.name == "salons" and db["salons"]:
                db["salons"][-1].update(data)
            return self

        def select(self, *args, **kwargs):
            # Store select fields if provided (e.g., "email", "owner_id, name")
            if args:
                self._select_fields = args[0] if isinstance(args[0], str) else None
            return self

        def eq(self, key, value):
            self._filters[key] = value
            return self

        def single(self):
            self._single = True
            return self

        def maybe_single(self):
            self._single = True
            return self

        def execute(self):
            # Handle table queries
            if self.name not in db:
                # Return empty result for unknown tables
                result_data = None if self._single else []
                return type("R", (), {"data": result_data, "error": None})()
            
            table_data = list(db[self.name])  # Copy to avoid modifying original
            
            # Apply filters if any
            if self._filters:
                filtered = []
                for item in table_data:
                    match = True
                    for key, value in self._filters.items():
                        if item.get(key) != value:
                            match = False
                            break
                    if match:
                        filtered.append(item)
                table_data = filtered
            
            if self._single:
                # Return single item (first filtered or None)
                data = table_data[0] if table_data else None
                # Reset state for next call
                self._single = False
                self._filters = {}
                return type("R", (), {"data": data, "error": None})()
            else:
                # Return list
                result_data = table_data
                # Reset state for next call
                self._filters = {}
                return type("R", (), {"data": result_data, "error": None})()

        def order(self, *args, **kwargs):
            return self

        def ilike(self, *args, **kwargs):
            return self

        def in_(self, *args, **kwargs):
            return self

        def lte(self, *args, **kwargs):
            return self

    # Redirect supabase.table calls to our mock
    monkeypatch.setattr(salon_service.supabase, "table", MockTable)
    monkeypatch.setattr(notification_service.supabase, "table", MockTable)
    monkeypatch.setattr(config.supabase, "table", MockTable)

    return db
