"""
Shared test fixtures & admin-state restore (post SEC-001 env-driven seed).

The database was wiped and re-seeded via the env-driven flow. Only the admin
account exists at session start (email from SEED_ADMIN_EMAIL, password from
SEED_ADMIN_PASSWORD, force_password_change=True). No sample students exist.

At session teardown we restore the seeded admin's password back to the
documented .env value and set force_password_change=true again so subsequent
iterations can continue with the documented credentials.
"""
import os
from pathlib import Path

import bcrypt
import pytest
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path("/app/backend/.env"))
load_dotenv(Path("/app/frontend/.env"))

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

SEED_ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "admin@college.edu")
SEED_ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe#Adm1n2026")


def _restore_admin(db):
    """Restore admin to the documented .env password and force_password_change=True."""
    pw_hash = bcrypt.hashpw(SEED_ADMIN_PASSWORD.encode(), bcrypt.gensalt()).decode()
    db.users.update_one(
        {"email": SEED_ADMIN_EMAIL},
        {"$set": {"password": pw_hash, "force_password_change": True}},
    )


def _cleanup_test_students(db):
    """Delete any TEST_-prefixed students / users created by tests."""
    test_students = list(db.students.find({"$or": [
        {"email": {"$regex": "^test_", "$options": "i"}},
        {"roll_number": {"$regex": "^TEST", "$options": "i"}},
        {"name": {"$regex": "^TEST_", "$options": "i"}},
    ]}, {"id": 1}))
    for s in test_students:
        db.users.delete_one({"id": s["id"]})
        db.attendance.delete_many({"student_id": s["id"]})
    db.students.delete_many({"$or": [
        {"email": {"$regex": "^test_", "$options": "i"}},
        {"roll_number": {"$regex": "^TEST", "$options": "i"}},
        {"name": {"$regex": "^TEST_", "$options": "i"}},
    ]})


@pytest.fixture(scope="session", autouse=True)
def _admin_state_restore_lifecycle():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    yield
    # Teardown: cleanup TEST_ students then restore admin to documented state.
    _cleanup_test_students(db)
    _restore_admin(db)
    client.close()
