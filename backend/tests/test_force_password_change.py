"""
SEC-001 backend enforcement — active_user dependency.

Verifies that while a user has force_password_change=true, every protected
endpoint returns HTTP 403 with detail containing 'password change required'
(case-insensitive), EXCEPT /auth/me and /auth/change-password which must
remain reachable so the forced-change flow can complete.

Also verifies /auth/login stays reachable (it is unauthenticated).

Teardown: restores seeded users to admin123/student123 + flag=true.
"""
import os
import random
import uuid
from pathlib import Path

import bcrypt
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path("/app/backend/.env"))
load_dotenv(Path("/app/frontend/.env"))

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

ADMIN_EMAIL = "admin@college.edu"
ADMIN_PW = "admin123"
STUDENT_EMAIL = "aarav@college.edu"
STUDENT_PW = "student123"
OTHER_EMAILS = ["diya@college.edu", "rohan@college.edu"]

NEW_ADMIN_PW = "AdminFPC1new!"
NEW_STUDENT_PW = "StudentFPC1new!"


def _reset(mongo, flag: bool):
    a = bcrypt.hashpw(ADMIN_PW.encode(), bcrypt.gensalt()).decode()
    s = bcrypt.hashpw(STUDENT_PW.encode(), bcrypt.gensalt()).decode()
    mongo.users.update_one({"email": ADMIN_EMAIL},
                           {"$set": {"password": a, "force_password_change": flag}})
    for e in [STUDENT_EMAIL] + OTHER_EMAILS:
        mongo.users.update_one({"email": e},
                               {"$set": {"password": s, "force_password_change": flag}})


@pytest.fixture(scope="session")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="module", autouse=True)
def force_flag_on(mongo):
    """Turn flag ON for this module (overrides session fixture which cleared it),
    then reset to OFF after so downstream modules pass. Final restore to True is
    done by the session-scoped conftest teardown."""
    _reset(mongo, flag=True)
    yield
    _reset(mongo, flag=False)


@pytest.fixture(scope="module")
def http():
    return requests.Session()


def _login(http, email, pw):
    return http.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


def _tok(http, email, pw):
    r = _login(http, email, pw)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


def _assert_403_password_required(resp):
    assert resp.status_code == 403, f"expected 403, got {resp.status_code}: {resp.text}"
    detail = (resp.json().get("detail") or "").lower()
    assert "password change required" in detail, f"detail mismatch: {detail!r}"


# ---------------- Login remains reachable ----------------
class TestLoginReachable:
    def test_admin_can_still_login(self, http):
        r = _login(http, ADMIN_EMAIL, ADMIN_PW)
        assert r.status_code == 200
        assert r.json()["user"].get("force_password_change") is True

    def test_student_can_still_login(self, http):
        r = _login(http, STUDENT_EMAIL, STUDENT_PW)
        assert r.status_code == 200
        assert r.json()["user"].get("force_password_change") is True


# ---------------- Exempted endpoints reachable ----------------
class TestExemptedEndpoints:
    def test_admin_me_reachable(self, http):
        tok = _tok(http, ADMIN_EMAIL, ADMIN_PW)
        r = http.get(f"{API}/auth/me", headers=_hdr(tok), timeout=20)
        assert r.status_code == 200
        assert r.json()["force_password_change"] is True
        assert r.json()["email"] == ADMIN_EMAIL

    def test_student_me_reachable(self, http):
        tok = _tok(http, STUDENT_EMAIL, STUDENT_PW)
        r = http.get(f"{API}/auth/me", headers=_hdr(tok), timeout=20)
        assert r.status_code == 200
        assert r.json()["force_password_change"] is True

    def test_admin_change_password_bad_current(self, http):
        tok = _tok(http, ADMIN_EMAIL, ADMIN_PW)
        r = http.post(f"{API}/auth/change-password",
                      json={"current_password": "wrong", "new_password": "GoodPass1x"},
                      headers=_hdr(tok), timeout=20)
        # Reachable => 400 (not 403); confirms the endpoint is exempt from active_user gate
        assert r.status_code == 400
        assert "current password" in r.json()["detail"].lower()

    def test_student_change_password_weak(self, http):
        tok = _tok(http, STUDENT_EMAIL, STUDENT_PW)
        r = http.post(f"{API}/auth/change-password",
                      json={"current_password": STUDENT_PW, "new_password": "short"},
                      headers=_hdr(tok), timeout=20)
        assert r.status_code == 400


# ---------------- Admin blocked on all protected endpoints ----------------
class TestAdminBlocked:
    @pytest.fixture(scope="class")
    def tok(self, http):
        return _tok(http, ADMIN_EMAIL, ADMIN_PW)

    def test_list_students_blocked(self, http, tok):
        _assert_403_password_required(http.get(f"{API}/students", headers=_hdr(tok), timeout=20))

    def test_create_student_blocked(self, http, tok):
        payload = {"name": "X", "roll_number": f"BLK{uuid.uuid4().hex[:5]}",
                   "email": f"blk_{uuid.uuid4().hex[:5]}@x.edu", "course": "BCA",
                   "phone": "9000000000"}
        _assert_403_password_required(
            http.post(f"{API}/students", json=payload, headers=_hdr(tok), timeout=20))

    def test_update_student_blocked(self, http, tok):
        _assert_403_password_required(
            http.put(f"{API}/students/any-id", json={"course": "MCA"}, headers=_hdr(tok), timeout=20))

    def test_delete_student_blocked(self, http, tok):
        _assert_403_password_required(
            http.delete(f"{API}/students/any-id", headers=_hdr(tok), timeout=20))

    def test_enroll_face_blocked(self, http, tok):
        _assert_403_password_required(
            http.post(f"{API}/students/any-id/face",
                      json={"descriptor": [0.1] * 128}, headers=_hdr(tok), timeout=20))

    def test_face_recognize_blocked(self, http, tok):
        _assert_403_password_required(
            http.post(f"{API}/face/recognize",
                      json={"descriptor": [0.1] * 128}, headers=_hdr(tok), timeout=20))

    def test_attendance_list_blocked(self, http, tok):
        _assert_403_password_required(
            http.get(f"{API}/attendance", headers=_hdr(tok), timeout=20))

    def test_attendance_stats_blocked(self, http, tok):
        _assert_403_password_required(
            http.get(f"{API}/attendance/stats", headers=_hdr(tok), timeout=20))

    def test_attendance_export_blocked(self, http, tok):
        _assert_403_password_required(
            http.get(f"{API}/attendance/export", headers=_hdr(tok), timeout=20))


# ---------------- Student blocked on all protected endpoints ----------------
class TestStudentBlocked:
    @pytest.fixture(scope="class")
    def tok_and_id(self, http):
        r = _login(http, STUDENT_EMAIL, STUDENT_PW)
        assert r.status_code == 200
        return r.json()["access_token"], r.json()["user"]["id"]

    def test_attendance_list_blocked(self, http, tok_and_id):
        tok, _ = tok_and_id
        _assert_403_password_required(
            http.get(f"{API}/attendance", headers=_hdr(tok), timeout=20))

    def test_me_stats_blocked(self, http, tok_and_id):
        tok, _ = tok_and_id
        _assert_403_password_required(
            http.get(f"{API}/attendance/me/stats", headers=_hdr(tok), timeout=20))

    def test_get_own_profile_blocked(self, http, tok_and_id):
        tok, sid = tok_and_id
        _assert_403_password_required(
            http.get(f"{API}/students/{sid}", headers=_hdr(tok), timeout=20))

    def test_mark_self_blocked(self, http, tok_and_id):
        tok, _ = tok_and_id
        _assert_403_password_required(
            http.post(f"{API}/face/mark-self",
                      json={"descriptor": [0.1] * 128}, headers=_hdr(tok), timeout=20))


# ---------------- After change-password, same token unlocks protected endpoints ----------------
class TestPostChangeUnlocks:
    def test_admin_can_access_after_change(self, http, mongo):
        _reset(mongo, flag=True)  # ensure starting state
        tok = _tok(http, ADMIN_EMAIL, ADMIN_PW)
        # Before change: blocked
        _assert_403_password_required(http.get(f"{API}/students", headers=_hdr(tok), timeout=20))
        # Change
        r = http.post(f"{API}/auth/change-password",
                      json={"current_password": ADMIN_PW, "new_password": NEW_ADMIN_PW},
                      headers=_hdr(tok), timeout=20)
        assert r.status_code == 200, r.text
        # Same token now unlocked
        r2 = http.get(f"{API}/students", headers=_hdr(tok), timeout=20)
        assert r2.status_code == 200, r2.text
        assert isinstance(r2.json(), list)

    def test_student_can_access_after_change(self, http, mongo):
        _reset(mongo, flag=True)
        tok = _tok(http, STUDENT_EMAIL, STUDENT_PW)
        _assert_403_password_required(
            http.get(f"{API}/attendance/me/stats", headers=_hdr(tok), timeout=20))
        r = http.post(f"{API}/auth/change-password",
                      json={"current_password": STUDENT_PW, "new_password": NEW_STUDENT_PW},
                      headers=_hdr(tok), timeout=20)
        assert r.status_code == 200, r.text
        r2 = http.get(f"{API}/attendance/me/stats", headers=_hdr(tok), timeout=20)
        assert r2.status_code == 200, r2.text
        assert "attendance_percentage" in r2.json()
