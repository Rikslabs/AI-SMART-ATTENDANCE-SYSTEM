"""
SEC-001 close-out — POST /api/auth/change-password
- Verifies auth, validation, blocklist, blank/short/no-digit, no-user_id param.
- Verifies /login and /auth/me expose force_password_change flag.
- End-to-end change: old password stops working, new password works, flag flips to false.
- Regression: after student pw change, key flows (students CRUD admin, mark-self, attendance
  list/stats/export, face/recognize admin-only, no face_image leak) still work.
- TEARDOWN: restores seeded users (admin@, aarav@, diya@, rohan@) to password + flag=true
  via direct Mongo write with bcrypt.
"""
import os
import random
import uuid
import pytest
import requests
import bcrypt
from pymongo import MongoClient
from dotenv import load_dotenv
from pathlib import Path

# Load backend/.env so MONGO_URL/DB_NAME match the running server exactly
load_dotenv(Path("/app/backend/.env"))
load_dotenv(Path("/app/frontend/.env"))

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

ADMIN_EMAIL = "admin@college.edu"
ADMIN_PW = "admin123"
STUDENT_EMAIL = "aarav@college.edu"   # gets its password rotated during tests
STUDENT_PW = "student123"
OTHER_EMAILS = ["diya@college.edu", "rohan@college.edu"]

NEW_ADMIN_PW = "AdminNewPass9!"
NEW_STUDENT_PW = "StudentNewPass9!"


# ---------------- Fixtures ----------------
@pytest.fixture(scope="session")
def http():
    return requests.Session()


@pytest.fixture(scope="session")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


def _login(http, email, pw):
    return http.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)


def _auth_header(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module", autouse=True)
def restore_seed_after_all(mongo):
    """Guarantee seed reset regardless of pass/fail."""
    yield
    reset_hash_admin = bcrypt.hashpw(ADMIN_PW.encode(), bcrypt.gensalt()).decode()
    reset_hash_stu = bcrypt.hashpw(STUDENT_PW.encode(), bcrypt.gensalt()).decode()
    mongo.users.update_one(
        {"email": ADMIN_EMAIL},
        {"$set": {"password": reset_hash_admin, "force_password_change": True}},
    )
    for e in [STUDENT_EMAIL] + OTHER_EMAILS:
        mongo.users.update_one(
            {"email": e},
            {"$set": {"password": reset_hash_stu, "force_password_change": True}},
        )


# ---------------- Login exposes force_password_change ----------------
class TestLoginFlag:
    def test_admin_login_has_flag_true(self, http):
        r = _login(http, ADMIN_EMAIL, ADMIN_PW)
        assert r.status_code == 200, r.text
        u = r.json()["user"]
        assert u["email"] == ADMIN_EMAIL
        assert u.get("force_password_change") is True

    def test_student_login_has_flag_true(self, http):
        r = _login(http, STUDENT_EMAIL, STUDENT_PW)
        assert r.status_code == 200, r.text
        u = r.json()["user"]
        assert u.get("force_password_change") is True

    def test_me_has_flag_true(self, http):
        tok = _login(http, ADMIN_EMAIL, ADMIN_PW).json()["access_token"]
        r = http.get(f"{API}/auth/me", headers=_auth_header(tok), timeout=20)
        assert r.status_code == 200
        assert r.json().get("force_password_change") is True


# ---------------- Change-password validation (uses admin token) ----------------
class TestChangePwValidation:
    @pytest.fixture(scope="class")
    def admin_tok(self, http):
        return _login(http, ADMIN_EMAIL, ADMIN_PW).json()["access_token"]

    def test_no_token(self, http):
        r = http.post(f"{API}/auth/change-password",
                      json={"current_password": "x", "new_password": "y"}, timeout=20)
        assert r.status_code == 401

    def test_wrong_current(self, http, admin_tok):
        r = http.post(f"{API}/auth/change-password",
                      json={"current_password": "wrongwrong", "new_password": "Whatever1abc"},
                      headers=_auth_header(admin_tok), timeout=20)
        assert r.status_code == 400
        assert "current password" in r.json().get("detail", "").lower()

    def test_short(self, http, admin_tok):
        r = http.post(f"{API}/auth/change-password",
                      json={"current_password": ADMIN_PW, "new_password": "Ab1"},
                      headers=_auth_header(admin_tok), timeout=20)
        assert r.status_code == 400
        assert "8 characters" in r.json()["detail"]

    def test_no_digit(self, http, admin_tok):
        r = http.post(f"{API}/auth/change-password",
                      json={"current_password": ADMIN_PW, "new_password": "AllLettersOnly"},
                      headers=_auth_header(admin_tok), timeout=20)
        assert r.status_code == 400
        assert "letter and one digit" in r.json()["detail"]

    def test_no_letter(self, http, admin_tok):
        r = http.post(f"{API}/auth/change-password",
                      json={"current_password": ADMIN_PW, "new_password": "12345678901"},
                      headers=_auth_header(admin_tok), timeout=20)
        assert r.status_code == 400
        assert "letter and one digit" in r.json()["detail"]

    @pytest.mark.parametrize("pw", ["admin123", "student123", "password", "12345678"])
    def test_blocklist(self, http, admin_tok, pw):
        r = http.post(f"{API}/auth/change-password",
                      json={"current_password": ADMIN_PW, "new_password": pw},
                      headers=_auth_header(admin_tok), timeout=20)
        assert r.status_code == 400

    def test_same_as_current(self, http, admin_tok):
        r = http.post(f"{API}/auth/change-password",
                      json={"current_password": ADMIN_PW, "new_password": ADMIN_PW},
                      headers=_auth_header(admin_tok), timeout=20)
        assert r.status_code == 400
        assert "different" in r.json()["detail"].lower()

    def test_empty_new(self, http, admin_tok):
        r = http.post(f"{API}/auth/change-password",
                      json={"current_password": ADMIN_PW, "new_password": ""},
                      headers=_auth_header(admin_tok), timeout=20)
        assert r.status_code == 400

    def test_no_user_id_param_supported(self, http, admin_tok):
        # Endpoint operates only on caller's own id — no /change-password/{id}
        r = http.post(f"{API}/auth/change-password/some-other-id",
                      json={"current_password": ADMIN_PW, "new_password": "Whatever1abc"},
                      headers=_auth_header(admin_tok), timeout=20)
        assert r.status_code in (404, 405)


# ---------------- End-to-end: admin change ----------------
class TestAdminChangeFlow:
    def test_admin_change_success_then_old_fails_new_works(self, http):
        tok = _login(http, ADMIN_EMAIL, ADMIN_PW).json()["access_token"]
        r = http.post(f"{API}/auth/change-password",
                      json={"current_password": ADMIN_PW, "new_password": NEW_ADMIN_PW},
                      headers=_auth_header(tok), timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert "message" in body

        # old fails
        r2 = _login(http, ADMIN_EMAIL, ADMIN_PW)
        assert r2.status_code == 401

        # new works & flag flipped
        r3 = _login(http, ADMIN_EMAIL, NEW_ADMIN_PW)
        assert r3.status_code == 200
        u = r3.json()["user"]
        assert u.get("force_password_change") is False

        # /auth/me also shows false
        tok2 = r3.json()["access_token"]
        me = http.get(f"{API}/auth/me", headers=_auth_header(tok2), timeout=20).json()
        assert me.get("force_password_change") is False

        # restore admin pw so remaining tests (which use ADMIN_PW) still work
        r4 = http.post(f"{API}/auth/change-password",
                       json={"current_password": NEW_ADMIN_PW, "new_password": "TempAdmin1xyz"},
                       headers=_auth_header(tok2), timeout=20)
        assert r4.status_code == 200
        # NOTE: cannot rotate to admin123 (blocklisted). Session-scope teardown does that via Mongo.


# ---------------- End-to-end: student change + regression ----------------
class TestStudentChangeAndRegression:
    def test_student_change_and_regression_bundle(self, http):
        # 1. student changes own password
        stu_tok = _login(http, STUDENT_EMAIL, STUDENT_PW).json()["access_token"]
        r = http.post(f"{API}/auth/change-password",
                      json={"current_password": STUDENT_PW, "new_password": NEW_STUDENT_PW},
                      headers=_auth_header(stu_tok), timeout=20)
        assert r.status_code == 200, r.text

        # old blocked, new logs in with flag=false
        assert _login(http, STUDENT_EMAIL, STUDENT_PW).status_code == 401
        newlogin = _login(http, STUDENT_EMAIL, NEW_STUDENT_PW)
        assert newlogin.status_code == 200
        stu_tok = newlogin.json()["access_token"]
        assert newlogin.json()["user"].get("force_password_change") is False

        # 2. admin token from teardown-safe temp pw
        admin_tok = _login(http, ADMIN_EMAIL, "TempAdmin1xyz").json()["access_token"]
        ah = _auth_header(admin_tok)
        sh = _auth_header(stu_tok)

        # 3. Admin students CRUD regression
        payload = {
            "name": "TEST_CP Student",
            "roll_number": f"TEST_CP{uuid.uuid4().hex[:6]}",
            "email": f"test_cp_{uuid.uuid4().hex[:6]}@college.edu",
            "course": "BCA", "phone": "9000000099", "password": "Init1pass",
        }
        cr = http.post(f"{API}/students", json=payload, headers=ah, timeout=20)
        assert cr.status_code == 200, cr.text
        new_sid = cr.json()["id"]

        # New student's login must include force_password_change=true
        new_login = _login(http, payload["email"], "Init1pass")
        assert new_login.status_code == 200
        assert new_login.json()["user"].get("force_password_change") is True

        # face_image / face_descriptor never leaked in list or profile
        lst = http.get(f"{API}/students", headers=ah, timeout=20).json()
        for row in lst:
            assert "face_image" not in row
            assert "face_descriptor" not in row
        prof = http.get(f"{API}/students/{new_sid}", headers=ah, timeout=20).json()
        assert "face_image" not in prof and "face_descriptor" not in prof

        # delete the throwaway student
        dr = http.delete(f"{API}/students/{new_sid}", headers=ah, timeout=20)
        assert dr.status_code == 200

        # 4. mark-self with freshly rotated student token — enroll first as admin on aarav
        aarav = [x for x in lst if x["roll_number"] == "BCA2101"][0]
        rnd = random.Random(7)
        desc = [rnd.uniform(-1, 1) for _ in range(128)]
        er = http.post(f"{API}/students/{aarav['id']}/face",
                       json={"descriptor": desc}, headers=ah, timeout=20)
        assert er.status_code == 200
        ms = http.post(f"{API}/face/mark-self",
                       json={"descriptor": desc}, headers=sh, timeout=20)
        assert ms.status_code == 200
        assert ms.json()["matched"] is True
        # no face_image in response
        assert "face_image" not in ms.json().get("student", {})

        # 5. attendance list/stats/export
        assert http.get(f"{API}/attendance", headers=ah, timeout=20).status_code == 200
        assert http.get(f"{API}/attendance/stats", headers=ah, timeout=20).status_code == 200
        exp = http.get(f"{API}/attendance/export", headers=ah, timeout=30)
        assert exp.status_code == 200
        assert "text/csv" in exp.headers.get("content-type", "").lower()

        # 6. /face/recognize admin-only
        assert http.post(f"{API}/face/recognize", json={"descriptor": desc},
                        headers=sh, timeout=20).status_code == 403
        assert http.post(f"{API}/face/recognize", json={"descriptor": desc},
                        headers=ah, timeout=20).status_code == 200
