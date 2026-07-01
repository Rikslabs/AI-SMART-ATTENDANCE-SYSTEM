"""
Security-hardening tests for AI Smart Attendance System.
Covers SEC-002 (auth on /api/face/recognize), SEC-003 (admin-only GET /api/students),
SEC-004 (JWT_SECRET from env), SEC-005 (regex-escape user input to $regex queries).
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://smartcheck-ai-2.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@college.edu"
ADMIN_PASSWORD = "admin123"
STUDENT_EMAIL = "aarav@college.edu"
STUDENT_PASSWORD = "student123"


# ---------- Session-scoped fixtures ----------
@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module")
def admin_token(s):
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    d = r.json()
    assert "access_token" in d and d["role"] == "admin"
    return d["access_token"]


@pytest.fixture(scope="module")
def student_token(s):
    r = s.post(f"{API}/auth/login", json={"email": STUDENT_EMAIL, "password": STUDENT_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Student login failed: {r.status_code} {r.text}"
    d = r.json()
    assert d["role"] == "student"
    return d["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def student_headers(student_token):
    return {"Authorization": f"Bearer {student_token}"}


@pytest.fixture(scope="module")
def student_user(s, student_headers):
    r = s.get(f"{API}/auth/me", headers=student_headers, timeout=20)
    assert r.status_code == 200
    return r.json()


# fixed descriptor for SEC-002 end-to-end recognize flow
def _desc_seq(n=128):
    # generates [0.01, 0.02, ..., 1.28]
    return [round((i + 1) / 100.0, 4) for i in range(n)]


# ------------------------------------------------------------------------
# SEC-002: /api/face/recognize now requires auth
# ------------------------------------------------------------------------
class TestSEC002_FaceRecognizeAuth:
    def test_recognize_no_token_401(self, s):
        r = s.post(f"{API}/face/recognize",
                   json={"descriptor": _desc_seq()}, timeout=20)
        assert r.status_code == 401, r.text

    def test_recognize_invalid_token_401(self, s):
        r = s.post(f"{API}/face/recognize",
                   json={"descriptor": _desc_seq()},
                   headers={"Authorization": "Bearer bogus.jwt.token"}, timeout=20)
        assert r.status_code == 401

    def test_recognize_with_student_token_and_enrolled_descriptor(self, s, admin_headers, student_headers, student_user):
        # 1) Admin creates a fresh test student
        roll = f"TESTSEC{uuid.uuid4().hex[:6].upper()}"
        email = f"testsec_{uuid.uuid4().hex[:6]}@college.edu"
        create = s.post(f"{API}/students",
                        json={"name": "TEST_SEC Student", "roll_number": roll,
                              "email": email, "course": "BCA", "phone": "9000000010",
                              "password": "student123"},
                        headers=admin_headers, timeout=20)
        assert create.status_code == 200, create.text
        sid = create.json()["id"]

        # 2) Admin enrolls a fixed 128-D descriptor
        desc = _desc_seq()
        er = s.post(f"{API}/students/{sid}/face",
                    json={"descriptor": desc}, headers=admin_headers, timeout=20)
        assert er.status_code == 200
        assert er.json()["face_enrolled"] is True

        try:
            # 3) Student token -> recognize with same descriptor: matched:true
            r1 = s.post(f"{API}/face/recognize",
                        json={"descriptor": desc},
                        headers=student_headers, timeout=30)
            assert r1.status_code == 200, r1.text
            b1 = r1.json()
            assert b1["matched"] is True
            assert b1["student"]["id"] == sid

            # 4) Second call same day -> already_marked:true
            r2 = s.post(f"{API}/face/recognize",
                        json={"descriptor": desc},
                        headers=student_headers, timeout=30)
            assert r2.status_code == 200
            b2 = r2.json()
            assert b2["matched"] is True
            assert b2["already_marked"] is True

            # 5) Admin token also works
            r3 = s.post(f"{API}/face/recognize",
                        json={"descriptor": desc},
                        headers=admin_headers, timeout=30)
            assert r3.status_code == 200
            assert r3.json()["matched"] is True
        finally:
            # Cleanup: delete test student (and their attendance rows)
            s.delete(f"{API}/students/{sid}", headers=admin_headers, timeout=20)


# ------------------------------------------------------------------------
# SEC-003: GET /api/students admin-only; students keep own access
# ------------------------------------------------------------------------
class TestSEC003_StudentsAdminOnly:
    def test_list_students_no_token_401(self, s):
        r = s.get(f"{API}/students", timeout=20)
        assert r.status_code == 401

    def test_list_students_student_token_403(self, s, student_headers):
        r = s.get(f"{API}/students", headers=student_headers, timeout=20)
        assert r.status_code == 403

    def test_list_students_admin_token_200(self, s, admin_headers):
        r = s.get(f"{API}/students", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) >= 3

    def test_student_can_get_own_profile(self, s, student_headers, student_user):
        sid = student_user["id"]
        r = s.get(f"{API}/students/{sid}", headers=student_headers, timeout=20)
        assert r.status_code == 200
        assert r.json()["id"] == sid

    def test_student_me_stats_ok(self, s, student_headers):
        r = s.get(f"{API}/attendance/me/stats", headers=student_headers, timeout=20)
        assert r.status_code == 200
        d = r.json()
        for k in ("present_days", "working_days", "attendance_percentage", "recent"):
            assert k in d

    def test_student_attendance_only_own(self, s, student_headers, student_user):
        r = s.get(f"{API}/attendance", headers=student_headers, timeout=20)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        for row in rows:
            assert row["student_id"] == student_user["id"], f"leaked other student row: {row}"

    def test_attendance_no_token_401(self, s):
        r = s.get(f"{API}/attendance", timeout=20)
        assert r.status_code == 401


# ------------------------------------------------------------------------
# SEC-004: JWT_SECRET loaded from env; login+auth end-to-end
# ------------------------------------------------------------------------
class TestSEC004_JWTFromEnv:
    def test_admin_login_returns_jwt(self, s):
        r = s.post(f"{API}/auth/login",
                   json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
        assert r.status_code == 200
        tok = r.json()["access_token"]
        # JWT has 3 dot-separated segments
        assert tok.count(".") == 2 and len(tok) > 40

        # And that token is usable
        me = s.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=20)
        assert me.status_code == 200
        assert me.json()["email"] == ADMIN_EMAIL

    def test_student_login_returns_jwt(self, s):
        r = s.post(f"{API}/auth/login",
                   json={"email": STUDENT_EMAIL, "password": STUDENT_PASSWORD}, timeout=20)
        assert r.status_code == 200
        tok = r.json()["access_token"]
        assert tok.count(".") == 2
        me = s.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=20)
        assert me.status_code == 200
        assert me.json()["role"] == "student"

    def test_tampered_token_rejected(self, s, admin_token):
        # flip last char
        bad = admin_token[:-1] + ("A" if admin_token[-1] != "A" else "B")
        r = s.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {bad}"}, timeout=20)
        assert r.status_code == 401


# ------------------------------------------------------------------------
# SEC-005: regex-escape user-controlled $regex inputs
# ------------------------------------------------------------------------
class TestSEC005_RegexEscape:
    def test_search_with_regex_metachars_is_safe(self, s, admin_headers):
        # ".*" should NOT act as wildcard; only literal ".*" matches -> empty list expected
        r = s.get(f"{API}/attendance", headers=admin_headers,
                  params={"search": ".*"}, timeout=20)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        for row in rows:
            assert ".*" in row.get("student_name", "") or ".*" in row.get("roll_number", ""), \
                f"regex metachar leaked as wildcard, row={row}"

    def test_search_with_where_operator_is_safe(self, s, admin_headers):
        r = s.get(f"{API}/attendance", headers=admin_headers,
                  params={"search": "$where"}, timeout=20)
        assert r.status_code == 200
        # returns list (empty or literal), never 500
        rows = r.json()
        assert isinstance(rows, list)
        for row in rows:
            assert "$where" in row.get("student_name", "") or "$where" in row.get("roll_number", "")

    def test_search_with_pipe_alternation_is_literal(self, s, admin_headers):
        r = s.get(f"{API}/attendance", headers=admin_headers,
                  params={"search": "BCA2101|BCA2102"}, timeout=20)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        # Should NOT return records matching either roll separately (alternation must be escaped)
        for row in rows:
            hay = f"{row.get('student_name','')} {row.get('roll_number','')}"
            assert "BCA2101|BCA2102" in hay

    def test_month_with_regex_metachars_is_safe(self, s, admin_headers):
        r = s.get(f"{API}/attendance", headers=admin_headers,
                  params={"month": ".*"}, timeout=20)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        # No date starts with the literal ".*", so must be empty
        assert rows == []

    def test_month_regex_metachars_export_safe(self, s, admin_headers):
        r = s.get(f"{API}/attendance/export", headers=admin_headers,
                  params={"month": ".*"}, timeout=30)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "").lower()
        # Body should have header row only (no rows leak via wildcard)
        lines = [ln for ln in r.text.splitlines() if ln.strip()]
        assert lines[0].startswith("Date,Time,Roll Number,Name,Course,Status")
        assert len(lines) == 1, f"regex metachar leaked into month filter, got {len(lines)-1} rows"


# ------------------------------------------------------------------------
# Regression: unauthorized access confirmations
# ------------------------------------------------------------------------
class TestUnauthorized:
    def test_face_recognize_no_token(self, s):
        r = s.post(f"{API}/face/recognize", json={"descriptor": [0.0] * 128}, timeout=20)
        assert r.status_code == 401

    def test_students_no_token(self, s):
        r = s.get(f"{API}/students", timeout=20)
        assert r.status_code == 401

    def test_attendance_no_token(self, s):
        r = s.get(f"{API}/attendance", timeout=20)
        assert r.status_code == 401

    def test_export_no_token(self, s):
        r = s.get(f"{API}/attendance/export", timeout=20)
        assert r.status_code == 401

    def test_export_student_forbidden(self, s, student_headers):
        r = s.get(f"{API}/attendance/export", headers=student_headers, timeout=20)
        assert r.status_code == 403
