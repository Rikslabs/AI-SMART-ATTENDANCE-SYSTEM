"""
Shared test fixtures & seed-state management.

Because SEC-001 seeded users have force_password_change=true by default,
most protected endpoints return 403 until the flag is cleared. Old tests
(backend_test.py, test_security.py, test_security_audit2.py, test_mark_self.py)
assume the flag is false so they can hit /students, /attendance, etc.

Strategy:
* Session-scoped autouse fixture clears the flag for all 4 seeded users at
  session start and resets it back to True at session end.
* test_change_password.py and test_force_password_change.py override this
  by setting the flag back to True inside their own module-scoped fixture
  before their tests run.
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

ADMIN_EMAIL = "admin@college.edu"
ADMIN_PW = "admin123"
STUDENT_PW = "student123"
SEED_EMAILS = [
    ("admin@college.edu", ADMIN_PW),
    ("aarav@college.edu", STUDENT_PW),
    ("diya@college.edu", STUDENT_PW),
    ("rohan@college.edu", STUDENT_PW),
]


def _reset_seed(db, flag: bool):
    for email, pw in SEED_EMAILS:
        pw_hash = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
        db.users.update_one(
            {"email": email},
            {"$set": {"password": pw_hash, "force_password_change": flag}},
        )


@pytest.fixture(scope="session", autouse=True)
def _seed_flag_lifecycle():
    """Clear force_password_change for all seeded users so legacy tests pass,
    then restore flag=True + original password at session end."""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    _reset_seed(db, flag=False)
    yield
    _reset_seed(db, flag=True)
    client.close()
