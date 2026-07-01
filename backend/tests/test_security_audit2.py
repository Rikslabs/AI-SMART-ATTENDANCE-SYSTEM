"""
Security Audit #2 tests
- SEC-001 (data continuity): seeded admin+3 students still exist; login works.
- SEC-002: /api/face/recognize is admin-only (student token -> 403);
           admin still matches + creates attendance; student uses /face/mark-self.
- SEC-003: biometric fields (face_image, face_descriptor) are never returned in
           /api/students*, /face/recognize, /face/mark-self responses; face_enrolled boolean still present.
"""
import os
import uuid
import random
import pytest
import requests
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@college.edu"
ADMIN_PASSWORD = "admin123"
STUDENT_EMAIL = "aarav@college.edu"
STUDENT_PASSWORD = "student123"


BIOMETRIC_KEYS = {"face_image", "face_descriptor"}


def _assert_no_biometric(payload, ctx=""):
    assert isinstance(payload, dict), f"{ctx}: expected dict, got {type(payload)}"
    for k in BIOMETRIC_KEYS:
        assert k not in payload, f"{ctx}: biometric key '{k}' leaked in response body keys={list(payload.keys())}"


def _rand_desc(seed, n=128):
    rnd = random.Random(seed)
    return [rnd.uniform(-1, 1) for _ in range(n)]


def _today():
    return datetime.now(timezone.utc).date().isoformat()


@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module")
def admin_token(s):
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def student_token(s):
    r = s.post(f"{API}/auth/login", json={"email": STUDENT_EMAIL, "password": STUDENT_PASSWORD}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def student_h(student_token):
    return {"Authorization": f"Bearer {student_token}"}


@pytest.fixture(scope="module")
def student_me(s, student_h):
    r = s.get(f"{API}/auth/me", headers=student_h, timeout=20)
    assert r.status_code == 200
    return r.json()


# ---------------- SEC-001 data continuity ----------------
class TestSEC001DataContinuity:
    def test_seeded_admin_can_login(self, s):
        r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    def test_seeded_student_aarav_can_login(self, s):
        r = s.post(f"{API}/auth/login", json={"email": "aarav@college.edu", "password": "student123"}, timeout=20)
        assert r.status_code == 200
        assert r.json()["role"] == "student"

    def test_seeded_students_present_in_list(self, s, admin_h):
        r = s.get(f"{API}/students", headers=admin_h, timeout=20)
        assert r.status_code == 200
        emails = {row["email"] for row in r.json()}
        for e in ("aarav@college.edu", "diya@college.edu", "rohan@college.edu"):
            assert e in emails, f"seeded student {e} missing (SEC-001 regression!)"


# ---------------- SEC-002 admin-only /face/recognize ----------------
class TestSEC002RecognizeAdminOnly:
    def test_anonymous_401(self, s):
        r = s.post(f"{API}/face/recognize", json={"descriptor": _rand_desc(1)}, timeout=20)
        assert r.status_code == 401

    def test_student_token_403(self, s, student_h):
        r = s.post(f"{API}/face/recognize", json={"descriptor": _rand_desc(1)}, headers=student_h, timeout=20)
        assert r.status_code == 403, r.text

    def test_admin_still_works_and_dedupes(self, s, admin_h):
        # Fresh student + enroll fresh descriptor
        tag = uuid.uuid4().hex[:8]
        payload = {
            "name": f"TEST_SA2_R_{tag}",
            "roll_number": f"TEST_SA2_R_{tag}".upper()[:20],
            "email": f"test_sa2_r_{tag}@college.edu",
            "course": "BCA", "phone": "9000000000", "password": "student123",
        }
        cr = s.post(f"{API}/students", json=payload, headers=admin_h, timeout=20)
        assert cr.status_code == 200, cr.text
        sid = cr.json()["id"]
        # SEC-003 sanity on create
        _assert_no_biometric(cr.json(), "POST /students response")
        try:
            desc = _rand_desc(seed=9101)
            er = s.post(f"{API}/students/{sid}/face", json={"descriptor": desc}, headers=admin_h, timeout=20)
            assert er.status_code == 200

            r1 = s.post(f"{API}/face/recognize", json={"descriptor": desc}, headers=admin_h, timeout=30)
            assert r1.status_code == 200, r1.text
            b1 = r1.json()
            assert b1["matched"] is True
            assert b1["student"]["id"] == sid
            # SEC-003: student sub-object must be minimal, no biometric
            assert set(b1["student"].keys()) == {"id", "name", "roll_number", "course"}, b1["student"].keys()
            assert "face_image" not in b1  # top-level either

            # duplicate check + attendance rowcount via /attendance
            r2 = s.post(f"{API}/face/recognize", json={"descriptor": desc}, headers=admin_h, timeout=30)
            assert r2.status_code == 200
            assert r2.json()["already_marked"] is True

            rows = s.get(f"{API}/attendance", headers=admin_h,
                         params={"date": _today(), "student_id": sid}, timeout=20).json()
            assert len([x for x in rows if x["student_id"] == sid and x["date"] == _today()]) == 1
        finally:
            s.delete(f"{API}/students/{sid}", headers=admin_h, timeout=20)


# ---------------- SEC-002 mark-self impersonation & dedupe ----------------
class TestSEC002MarkSelfImpersonation:
    def test_impersonation_no_row_for_either(self, s, admin_h):
        # Caller = fresh student S1 with descriptor D1
        tag = uuid.uuid4().hex[:8]
        s1_body = s.post(f"{API}/students", json={
            "name": f"TEST_IMP_A_{tag}",
            "roll_number": f"TEST_IMP_A_{tag}".upper()[:20],
            "email": f"test_imp_a_{tag}@college.edu",
            "course": "BCA", "phone": "9000000001", "password": "student123",
        }, headers=admin_h, timeout=20)
        assert s1_body.status_code == 200
        s1_id = s1_body.json()["id"]
        s1_email = s1_body.json()["email"]
        d1 = _rand_desc(seed=6001)
        s.post(f"{API}/students/{s1_id}/face", json={"descriptor": d1}, headers=admin_h, timeout=20)

        # Victim = fresh student S2 enrolled with D2
        tag2 = uuid.uuid4().hex[:8]
        s2_body = s.post(f"{API}/students", json={
            "name": f"TEST_IMP_B_{tag2}",
            "roll_number": f"TEST_IMP_B_{tag2}".upper()[:20],
            "email": f"test_imp_b_{tag2}@college.edu",
            "course": "BCA", "phone": "9000000002", "password": "student123",
        }, headers=admin_h, timeout=20)
        assert s2_body.status_code == 200
        s2_id = s2_body.json()["id"]
        d2 = _rand_desc(seed=6002)
        s.post(f"{API}/students/{s2_id}/face", json={"descriptor": d2}, headers=admin_h, timeout=20)

        tok = s.post(f"{API}/auth/login", json={"email": s1_email, "password": "student123"},
                     timeout=20).json()["access_token"]
        s1_h = {"Authorization": f"Bearer {tok}"}
        try:
            r = s.post(f"{API}/face/mark-self", json={"descriptor": d2}, headers=s1_h, timeout=20)
            assert r.status_code == 200
            body = r.json()
            assert body["matched"] is False
            assert body["reason"] == "no_match"

            # Verify no attendance row for either student today
            for sid in (s1_id, s2_id):
                rows = s.get(f"{API}/attendance", headers=admin_h,
                             params={"date": _today(), "student_id": sid}, timeout=20).json()
                assert not any(x["student_id"] == sid and x["date"] == _today() for x in rows), \
                    f"impersonation leaked a row for {sid}"
        finally:
            s.delete(f"{API}/students/{s1_id}", headers=admin_h, timeout=20)
            s.delete(f"{API}/students/{s2_id}", headers=admin_h, timeout=20)

    def test_mark_self_matched_no_biometric_and_dedupes(self, s, admin_h):
        tag = uuid.uuid4().hex[:8]
        cr = s.post(f"{API}/students", json={
            "name": f"TEST_MSOK_{tag}",
            "roll_number": f"TEST_MSOK_{tag}".upper()[:20],
            "email": f"test_msok_{tag}@college.edu",
            "course": "BCA", "phone": "9000000003", "password": "student123",
        }, headers=admin_h, timeout=20)
        assert cr.status_code == 200
        sid = cr.json()["id"]
        email = cr.json()["email"]
        _assert_no_biometric(cr.json(), "POST /students response")
        desc = _rand_desc(seed=6011)
        s.post(f"{API}/students/{sid}/face", json={"descriptor": desc}, headers=admin_h, timeout=20)
        tok = s.post(f"{API}/auth/login", json={"email": email, "password": "student123"},
                     timeout=20).json()["access_token"]
        sh = {"Authorization": f"Bearer {tok}"}
        try:
            r1 = s.post(f"{API}/face/mark-self", json={"descriptor": desc}, headers=sh, timeout=20)
            assert r1.status_code == 200
            b1 = r1.json()
            assert b1["matched"] is True
            assert b1["student"]["id"] == sid
            # SEC-003 on mark-self
            assert set(b1["student"].keys()) == {"id", "name", "roll_number", "course"}
            assert "face_image" not in b1
            assert b1["already_marked"] is False

            r2 = s.post(f"{API}/face/mark-self", json={"descriptor": desc}, headers=sh, timeout=20)
            assert r2.status_code == 200
            b2 = r2.json()
            assert b2["already_marked"] is True
            assert "face_image" not in b2
            assert set(b2["student"].keys()) == {"id", "name", "roll_number", "course"}

            rows = s.get(f"{API}/attendance", headers=admin_h,
                         params={"date": _today(), "student_id": sid}, timeout=20).json()
            assert len([x for x in rows if x["student_id"] == sid and x["date"] == _today()]) == 1
        finally:
            s.delete(f"{API}/students/{sid}", headers=admin_h, timeout=20)


# ---------------- SEC-003 no face_image in any /students* response ----------------
class TestSEC003NoBiometricLeak:
    def test_list_students_no_biometric(self, s, admin_h):
        r = s.get(f"{API}/students", headers=admin_h, timeout=20)
        assert r.status_code == 200
        for row in r.json():
            _assert_no_biometric(row, f"list row id={row.get('id')}")
            assert "face_enrolled" in row, "face_enrolled boolean must remain in list responses"
            assert isinstance(row["face_enrolled"], bool)

    def test_get_student_by_admin_no_biometric(self, s, admin_h):
        lst = s.get(f"{API}/students", headers=admin_h, timeout=20).json()
        assert lst, "seeded students should exist"
        sid = lst[0]["id"]
        r = s.get(f"{API}/students/{sid}", headers=admin_h, timeout=20)
        assert r.status_code == 200
        body = r.json()
        _assert_no_biometric(body, f"GET /students/{sid} admin")
        assert "face_enrolled" in body
        assert isinstance(body["face_enrolled"], bool)

    def test_get_own_profile_student_no_biometric(self, s, student_h, student_me):
        sid = student_me["id"]
        r = s.get(f"{API}/students/{sid}", headers=student_h, timeout=20)
        assert r.status_code == 200
        body = r.json()
        _assert_no_biometric(body, f"GET /students/{sid} self")
        assert "face_enrolled" in body

    def test_create_student_response_no_biometric(self, s, admin_h):
        tag = uuid.uuid4().hex[:8]
        r = s.post(f"{API}/students", json={
            "name": f"TEST_S3C_{tag}",
            "roll_number": f"TEST_S3C_{tag}".upper()[:20],
            "email": f"test_s3c_{tag}@college.edu",
            "course": "BCA", "phone": "9000000004", "password": "student123",
        }, headers=admin_h, timeout=20)
        assert r.status_code == 200
        body = r.json()
        _assert_no_biometric(body, "POST /students response")
        assert body.get("face_enrolled") is False
        try:
            # Now enroll a face; GET must STILL not return face_image
            desc = _rand_desc(seed=6021)
            s.post(f"{API}/students/{body['id']}/face",
                   json={"descriptor": desc, "image_base64": "data:image/png;base64,AAAA"},
                   headers=admin_h, timeout=20)
            g = s.get(f"{API}/students/{body['id']}", headers=admin_h, timeout=20).json()
            _assert_no_biometric(g, "GET after enroll")
            assert g["face_enrolled"] is True
        finally:
            s.delete(f"{API}/students/{body['id']}", headers=admin_h, timeout=20)

    def test_update_student_response_no_biometric(self, s, admin_h):
        tag = uuid.uuid4().hex[:8]
        cr = s.post(f"{API}/students", json={
            "name": f"TEST_S3U_{tag}",
            "roll_number": f"TEST_S3U_{tag}".upper()[:20],
            "email": f"test_s3u_{tag}@college.edu",
            "course": "BCA", "phone": "9000000005", "password": "student123",
        }, headers=admin_h, timeout=20)
        assert cr.status_code == 200
        sid = cr.json()["id"]
        try:
            desc = _rand_desc(seed=6031)
            s.post(f"{API}/students/{sid}/face",
                   json={"descriptor": desc, "image_base64": "data:image/png;base64,BBBB"},
                   headers=admin_h, timeout=20)
            up = s.put(f"{API}/students/{sid}", json={"phone": "9111111111"}, headers=admin_h, timeout=20)
            assert up.status_code == 200
            body = up.json()
            _assert_no_biometric(body, "PUT /students response")
            assert body["phone"] == "9111111111"
            assert body["face_enrolled"] is True
        finally:
            s.delete(f"{API}/students/{sid}", headers=admin_h, timeout=20)


# ---------------- Regression: auth boundaries ----------------
class TestAuthBoundariesRegression:
    def test_student_cannot_hit_admin_endpoints(self, s, student_h):
        blocked = [
            ("GET", f"{API}/students"),
            ("GET", f"{API}/attendance/stats"),
            ("GET", f"{API}/attendance/export"),
        ]
        for method, url in blocked:
            r = s.request(method, url, headers=student_h, timeout=20)
            assert r.status_code == 403, f"{method} {url} expected 403 got {r.status_code}"

    def test_student_cannot_create_or_delete_student(self, s, student_h):
        r = s.post(f"{API}/students", json={
            "name": "TEST_NOAUTH", "roll_number": "TESTNOAUTH01",
            "email": "test_noauth@college.edu", "course": "BCA", "phone": "9000000006",
        }, headers=student_h, timeout=20)
        assert r.status_code == 403

    def test_anonymous_cannot_hit_protected(self, s):
        for url in (f"{API}/students", f"{API}/attendance", f"{API}/attendance/stats",
                    f"{API}/attendance/export", f"{API}/attendance/me/stats", f"{API}/auth/me"):
            r = s.get(url, timeout=20)
            assert r.status_code == 401, f"GET {url} expected 401 got {r.status_code}"
