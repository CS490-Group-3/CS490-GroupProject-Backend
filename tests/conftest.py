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
from app import app
import routes.salon as salon_routes
importlib.reload(salon_routes)  # reload so Flask registers with fakes


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

    TEST_OWNER_ID = "00000000-0000-0000-0000-000000000000"

    db = {
        "users": [{"id": TEST_OWNER_ID, "email": "owner@test.com"}],
        "salons": [],
        "notifications": [],
        "user_profiles": [{"user_id": "admin-uuid", "role": "admin"}],
    }

    class MockTable:
        def __init__(self, name):
            self.name = name

        def insert(self, data):
            if isinstance(data, list):
                data = data[0]
            data = dict(data)
            if self.name == "salons":
                data["id"] = f"salon-{len(db['salons'])+1}"
                db["salons"].append(data)
            elif self.name == "notifications":
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
            return self

        def eq(self, *args, **kwargs):
            return self

        def single(self):
            self._single = True
            return self
        def execute(self):
            if getattr(self, "_single", False):
                data = db[self.name][-1] if db[self.name] else {}
                return type("R", (), {"data": data})()
            return type("R", (), {"data": db[self.name]})()

        def order(self, *args, **kwargs):
            return self



    # Redirect supabase.table calls to our mock
    monkeypatch.setattr(salon_service.supabase, "table", MockTable)
    monkeypatch.setattr(notification_service.supabase, "table", MockTable)

    return db
