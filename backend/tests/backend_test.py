"""
AI Smart Attendance System - Backend API tests
Covers: auth, students CRUD, face enroll/recognize, attendance stats/list/export
"""
import os
import random
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://smartcheck-ai-2.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@college.edu"
ADMIN_PASSWORD = "admin123"
STUDENT_EMAIL = "aarav@college.edu"
STUDENT_PASSWORD = "student123"


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def s():
    return requests.Session()


@pytest.fixture(scope="session")
def admin_token(s):
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    assert data["role"] == "admin"
    assert data["user"]["email"] == ADMIN_EMAIL
    return data["access_token"]


@pytest.fixture(scope="session")
def student_token(s):
    r = s.post(f"{API}/auth/login", json={"email": STUDENT_EMAIL, "password": STUDENT_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Student login failed: {r.status_code} {r.text}"
    data = r.json()
    assert data["role"] == "student"
    return data["access_token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def student_headers(student_token):
    return {"Authorization": f"Bearer {student_token}"}


# ---------- AUTH ----------
class TestAuth:
    def test_admin_login(self, admin_token):
        assert isinstance(admin_token, str) and len(admin_token) > 20

    def test_student_login(self, student_token):
        assert isinstance(student_token, str) and len(student_token) > 20

    def test_invalid_login(self, s):
        r = s.post(f"{API}/auth/login", json={"email": "nope@college.edu", "password": "wrong"}, timeout=20)
        assert r.status_code == 401

    def test_me_admin(self, s, admin_headers):
        r = s.get(f"{API}/auth/me", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL
        assert r.json()["role"] == "admin"

    def test_me_student(self, s, student_headers):
        r = s.get(f"{API}/auth/me", headers=student_headers, timeout=20)
        assert r.status_code == 200
        assert r.json()["role"] == "student"

    def test_me_no_token(self, s):
        r = s.get(f"{API}/auth/me", timeout=20)
        assert r.status_code == 401


# ---------- STUDENTS CRUD ----------
class TestStudents:
    created_id = None

    def test_list_students_has_seeded(self, s, admin_headers):
        r = s.get(f"{API}/students", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        students = r.json()
        assert isinstance(students, list)
        rolls = {st["roll_number"] for st in students}
        assert {"BCA2101", "BCA2102", "BCA2103"}.issubset(rolls)

    def test_list_students_requires_auth(self, s):
        r = s.get(f"{API}/students", timeout=20)
        assert r.status_code == 401

    def test_student_cannot_create(self, s, student_headers):
        payload = {
            "name": "TEST_Blocked", "roll_number": "TEST_BLK1",
            "email": "test_blocked@college.edu", "course": "BCA", "phone": "9999999999",
        }
        r = s.post(f"{API}/students", json=payload, headers=student_headers, timeout=20)
        assert r.status_code == 403

    def test_admin_create_student(self, s, admin_headers):
        payload = {
            "name": "TEST_Student One", "roll_number": "TESTROLL001",
            "email": "test_student1@college.edu", "course": "BCA",
            "phone": "9000000001", "password": "student123",
        }
        r = s.post(f"{API}/students", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["roll_number"] == "TESTROLL001"
        assert data["email"] == "test_student1@college.edu"
        assert data["face_enrolled"] is False
        assert "id" in data
        TestStudents.created_id = data["id"]

        # GET verify persisted
        g = s.get(f"{API}/students/{data['id']}", headers=admin_headers, timeout=20)
        assert g.status_code == 200
        assert g.json()["roll_number"] == "TESTROLL001"

    def test_duplicate_roll_number(self, s, admin_headers):
        payload = {
            "name": "TEST_Dup", "roll_number": "TESTROLL001",
            "email": "test_dup@college.edu", "course": "BCA", "phone": "9000000002",
        }
        r = s.post(f"{API}/students", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 400

    def test_duplicate_email(self, s, admin_headers):
        payload = {
            "name": "TEST_Dup2", "roll_number": "TESTROLL999",
            "email": "test_student1@college.edu", "course": "BCA", "phone": "9000000003",
        }
        r = s.post(f"{API}/students", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 400

    def test_update_student(self, s, admin_headers):
        sid = TestStudents.created_id
        assert sid
        r = s.put(f"{API}/students/{sid}", json={"course": "MCA"}, headers=admin_headers, timeout=20)
        assert r.status_code == 200
        assert r.json()["course"] == "MCA"

        g = s.get(f"{API}/students/{sid}", headers=admin_headers, timeout=20)
        assert g.json()["course"] == "MCA"


# ---------- FACE ENROLL & RECOGNIZE ----------
def _rand_desc(seed=None, n=128):
    rnd = random.Random(seed)
    return [rnd.uniform(-1, 1) for _ in range(n)]


class TestFace:
    descriptor = _rand_desc(seed=42)
    target_sid = None

    def test_enroll_requires_admin(self, s, admin_headers, student_headers):
        # Use admin to list (SEC-003 blocks student). Cache target_sid.
        r = s.get(f"{API}/students", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        sid = [x for x in r.json() if x["roll_number"] == "BCA2101"][0]["id"]
        TestFace.target_sid = sid
        # student token should be forbidden on enroll
        r = s.post(f"{API}/students/{sid}/face", json={"descriptor": self.descriptor},
                   headers=student_headers, timeout=20)
        assert r.status_code == 403

    def test_admin_enroll_face(self, s, admin_headers):
        sid = TestFace.target_sid
        assert sid
        r = s.post(f"{API}/students/{sid}/face", json={"descriptor": self.descriptor},
                   headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["face_enrolled"] is True

        # verify list reflects enrolled=true
        lst = s.get(f"{API}/students", headers=admin_headers, timeout=20).json()
        target = [x for x in lst if x["id"] == sid][0]
        assert target["face_enrolled"] is True

    def test_enroll_invalid_descriptor(self, s, admin_headers):
        sid = TestFace.target_sid
        r = s.post(f"{API}/students/{sid}/face", json={"descriptor": [0.1, 0.2, 0.3]},
                   headers=admin_headers, timeout=20)
        assert r.status_code == 400

    def test_recognize_match_and_dedupe(self, s, admin_headers):
        # SEC-002: /api/face/recognize now requires auth
        r1 = s.post(f"{API}/face/recognize", json={"descriptor": self.descriptor},
                    headers=admin_headers, timeout=30)
        assert r1.status_code == 200, r1.text
        b1 = r1.json()
        assert b1["matched"] is True
        assert b1["student"]["id"] == TestFace.target_sid
        # already_marked may be True if previous test run created one; both are valid successes.

        # Second call must dedupe
        r2 = s.post(f"{API}/face/recognize", json={"descriptor": self.descriptor},
                    headers=admin_headers, timeout=30)
        assert r2.status_code == 200
        b2 = r2.json()
        assert b2["matched"] is True
        assert b2["already_marked"] is True

    def test_recognize_unmatched(self, s, admin_headers):
        # Use a very different descriptor (all large positive) far from enrolled random-uniform vector
        far = [5.0] * 128
        r = s.post(f"{API}/face/recognize", json={"descriptor": far},
                   headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.json()["matched"] is False


# ---------- ATTENDANCE ----------
class TestAttendance:
    def test_stats_admin(self, s, admin_headers):
        r = s.get(f"{API}/attendance/stats", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        d = r.json()
        for k in ("total_students", "today_attendance", "attendance_percentage", "face_enrolled", "recent", "week"):
            assert k in d
        assert isinstance(d["week"], list) and len(d["week"]) == 7
        assert isinstance(d["recent"], list)

    def test_stats_forbidden_for_student(self, s, student_headers):
        r = s.get(f"{API}/attendance/stats", headers=student_headers, timeout=20)
        assert r.status_code == 403

    def test_list_by_date_and_search(self, s, admin_headers):
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date().isoformat()
        r = s.get(f"{API}/attendance", headers=admin_headers,
                  params={"date": today}, timeout=20)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        # if any rows, all should have today's date
        for row in rows:
            assert row["date"] == today

        month = today[:7]
        r2 = s.get(f"{API}/attendance", headers=admin_headers,
                   params={"month": month}, timeout=20)
        assert r2.status_code == 200
        for row in r2.json():
            assert row["date"].startswith(month)

        # search by roll number of the enrolled seeded student
        r3 = s.get(f"{API}/attendance", headers=admin_headers,
                   params={"search": "BCA2101"}, timeout=20)
        assert r3.status_code == 200
        for row in r3.json():
            assert row["roll_number"] == "BCA2101" or "BCA2101" in row.get("student_name", "")

    def test_me_stats_student(self, s, student_headers):
        r = s.get(f"{API}/attendance/me/stats", headers=student_headers, timeout=20)
        assert r.status_code == 200
        d = r.json()
        for k in ("present_days", "working_days", "attendance_percentage", "recent"):
            assert k in d
        assert isinstance(d["recent"], list)

    def test_me_stats_forbidden_for_admin(self, s, admin_headers):
        r = s.get(f"{API}/attendance/me/stats", headers=admin_headers, timeout=20)
        assert r.status_code == 403

    def test_export_csv_date(self, s, admin_headers):
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date().isoformat()
        r = s.get(f"{API}/attendance/export", headers=admin_headers, params={"date": today}, timeout=30)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "").lower()
        assert "attachment" in r.headers.get("content-disposition", "").lower()
        text = r.text
        assert text.splitlines()[0].startswith("Date,Time,Roll Number,Name,Course,Status")

    def test_export_csv_month(self, s, admin_headers):
        from datetime import datetime, timezone
        month = datetime.now(timezone.utc).date().isoformat()[:7]
        r = s.get(f"{API}/attendance/export", headers=admin_headers, params={"month": month}, timeout=30)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "").lower()


# ---------- CLEANUP ----------
class TestZCleanup:
    def test_delete_created_student(self, s, admin_headers):
        sid = TestStudents.created_id
        if not sid:
            pytest.skip("nothing to clean")
        r = s.delete(f"{API}/students/{sid}", headers=admin_headers, timeout=20)
        assert r.status_code == 200

        g = s.get(f"{API}/students/{sid}", headers=admin_headers, timeout=20)
        assert g.status_code == 404

    def test_delete_nonexistent(self, s, admin_headers):
        r = s.delete(f"{API}/students/nonexistent-id", headers=admin_headers, timeout=20)
        assert r.status_code == 404
