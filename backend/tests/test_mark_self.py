"""
Tests for POST /api/face/mark-self (Iteration 3 - Student Face Attendance).

Covers:
 - Role gating: 401 anonymous, 403 admin, 200 (semantic) for students.
 - Happy path: enrolled student self-marks -> matched:true; second call same day -> already_marked:true
   (verifies no duplicate row created in db.attendance for (student_id, date)).
 - not_enrolled: student without face_descriptor -> matched:false + reason='not_enrolled'.
 - no_match: enrolled student sends random descriptor -> matched:false + reason='no_match'
   AND no attendance row is created.
 - Cross-user boundary: a student sending ANOTHER student's descriptor cannot create an
   attendance row for the other student (endpoint uses caller's own id).
 - 400 for descriptor < 64 elements.
 - Regression check: /api/face/recognize (admin scan) still enrolls-then-marks-then-dedupes
   for a freshly created student.
"""
import os
import uuid
import random
import pytest
import requests

def _load_backend_url():
    # Prefer env var, fall back to frontend/.env (same as prior test files)
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if url:
        return url.rstrip("/")
    env_path = "/app/frontend/.env"
    if os.path.exists(env_path):
        with open(env_path) as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@college.edu"
ADMIN_PASSWORD = "admin123"


# ---------- utilities ----------
def _login(sess, email, password):
    r = sess.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


def _rand_desc(seed, n=128):
    rnd = random.Random(seed)
    return [rnd.uniform(-1, 1) for _ in range(n)]


def _mk_student(sess, admin_h, prefix):
    tag = uuid.uuid4().hex[:8]
    payload = {
        "name": f"TEST_MS_{prefix}_{tag}",
        "roll_number": f"TEST_MS_{prefix}_{tag}".upper()[:20],
        "email": f"test_ms_{prefix}_{tag}@college.edu",
        "course": "BCA",
        "phone": "9000000000",
        "password": "student123",
    }
    r = sess.post(f"{API}/students", json=payload, headers=admin_h, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    return body["id"], body["email"], body["roll_number"]


def _enroll(sess, admin_h, sid, descriptor):
    r = sess.post(
        f"{API}/students/{sid}/face",
        json={"descriptor": descriptor},
        headers=admin_h,
        timeout=20,
    )
    assert r.status_code == 200, r.text
    assert r.json()["face_enrolled"] is True


def _count_attendance_today(sess, admin_h, sid):
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date().isoformat()
    r = sess.get(
        f"{API}/attendance",
        headers=admin_h,
        params={"date": today, "student_id": sid},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    rows = [row for row in r.json() if row["student_id"] == sid and row["date"] == today]
    return len(rows)


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def sess():
    return requests.Session()


@pytest.fixture(scope="module")
def admin_headers(sess):
    tok = _login(sess, ADMIN_EMAIL, ADMIN_PASSWORD)
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def enrolled_student(sess, admin_headers):
    """Fresh student enrolled with a known 128-D descriptor. Cleaned up after module."""
    sid, email, _ = _mk_student(sess, admin_headers, "enr")
    descriptor = _rand_desc(seed=1001)
    _enroll(sess, admin_headers, sid, descriptor)
    tok = _login(sess, email, "student123")
    yield {"id": sid, "email": email, "token": tok, "descriptor": descriptor,
           "headers": {"Authorization": f"Bearer {tok}"}}
    sess.delete(f"{API}/students/{sid}", headers=admin_headers, timeout=20)


@pytest.fixture(scope="module")
def unenrolled_student(sess, admin_headers):
    sid, email, _ = _mk_student(sess, admin_headers, "unenr")
    tok = _login(sess, email, "student123")
    yield {"id": sid, "email": email, "token": tok,
           "headers": {"Authorization": f"Bearer {tok}"}}
    sess.delete(f"{API}/students/{sid}", headers=admin_headers, timeout=20)


@pytest.fixture(scope="module")
def other_enrolled_student(sess, admin_headers):
    """Second enrolled student to test cross-user boundary."""
    sid, email, _ = _mk_student(sess, admin_headers, "other")
    descriptor = _rand_desc(seed=2002)
    _enroll(sess, admin_headers, sid, descriptor)
    yield {"id": sid, "email": email, "descriptor": descriptor}
    sess.delete(f"{API}/students/{sid}", headers=admin_headers, timeout=20)


# ---------- role gating ----------
class TestMarkSelfRoleGating:
    def test_anonymous_401(self, sess):
        r = sess.post(f"{API}/face/mark-self", json={"descriptor": _rand_desc(1)}, timeout=20)
        assert r.status_code == 401, r.text

    def test_admin_forbidden_403(self, sess, admin_headers):
        r = sess.post(
            f"{API}/face/mark-self",
            json={"descriptor": _rand_desc(1)},
            headers=admin_headers,
            timeout=20,
        )
        assert r.status_code == 403, r.text

    def test_short_descriptor_400(self, sess, enrolled_student):
        r = sess.post(
            f"{API}/face/mark-self",
            json={"descriptor": [0.1] * 32},
            headers=enrolled_student["headers"],
            timeout=20,
        )
        assert r.status_code == 400, r.text


# ---------- not_enrolled ----------
class TestMarkSelfNotEnrolled:
    def test_not_enrolled_returns_reason(self, sess, unenrolled_student):
        r = sess.post(
            f"{API}/face/mark-self",
            json={"descriptor": _rand_desc(seed=7)},
            headers=unenrolled_student["headers"],
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["matched"] is False
        assert body["reason"] == "not_enrolled"
        assert isinstance(body.get("message"), str) and len(body["message"]) > 0


# ---------- happy path + dedupe ----------
class TestMarkSelfHappyPath:
    def test_matched_creates_attendance(self, sess, enrolled_student, admin_headers):
        before = _count_attendance_today(sess, admin_headers, enrolled_student["id"])
        r = sess.post(
            f"{API}/face/mark-self",
            json={"descriptor": enrolled_student["descriptor"]},
            headers=enrolled_student["headers"],
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["matched"] is True
        assert body["student"]["id"] == enrolled_student["id"]
        # first call may be already_marked only if there was a pre-existing row
        # (which we asserted was 0 by using a fresh student)
        assert body["already_marked"] is False
        assert body["attendance"]["date"]
        after = _count_attendance_today(sess, admin_headers, enrolled_student["id"])
        assert after == before + 1, f"expected +1 row, got before={before} after={after}"

    def test_second_call_already_marked_no_duplicate(self, sess, enrolled_student, admin_headers):
        before = _count_attendance_today(sess, admin_headers, enrolled_student["id"])
        assert before >= 1, "prior test should have created a row"
        r = sess.post(
            f"{API}/face/mark-self",
            json={"descriptor": enrolled_student["descriptor"]},
            headers=enrolled_student["headers"],
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["matched"] is True
        assert body["already_marked"] is True
        after = _count_attendance_today(sess, admin_headers, enrolled_student["id"])
        assert after == before, "duplicate attendance row was created"


# ---------- no_match ----------
class TestMarkSelfNoMatch:
    def test_random_descriptor_no_match_no_row(self, sess, admin_headers):
        """Fresh enrolled student; send far-off descriptor; expect no_match and no attendance row."""
        # Use a dedicated fresh student to avoid interference from happy-path row.
        sid, email, _ = _mk_student(sess, admin_headers, "nomatch")
        descriptor = _rand_desc(seed=3003)
        _enroll(sess, admin_headers, sid, descriptor)
        tok = _login(sess, email, "student123")
        h = {"Authorization": f"Bearer {tok}"}
        try:
            before = _count_attendance_today(sess, admin_headers, sid)
            # far vector - constant 5.0 gives distance sqrt(sum((5-x)^2)) ~ 57 >> 0.55
            far = [5.0] * 128
            r = sess.post(f"{API}/face/mark-self", json={"descriptor": far},
                          headers=h, timeout=20)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["matched"] is False
            assert body["reason"] == "no_match"
            assert "distance" in body
            after = _count_attendance_today(sess, admin_headers, sid)
            assert after == before, "no_match should NOT create attendance row"
        finally:
            sess.delete(f"{API}/students/{sid}", headers=admin_headers, timeout=20)


# ---------- cross-user boundary ----------
class TestMarkSelfCrossUser:
    def test_other_students_descriptor_does_not_mark_other(
        self, sess, admin_headers, other_enrolled_student
    ):
        """
        Caller = a fresh student S1 (enrolled with descriptor D1).
        Payload = OTHER student's descriptor D_other (very different from D1).
        Expectation:
         - Response is matched:false (since compared only against caller's D1).
         - No attendance row created for the OTHER student.
         - No attendance row created for the CALLER either.
        """
        # Fresh caller enrolled with D1 that is far from other_enrolled_student.descriptor
        sid, email, _ = _mk_student(sess, admin_headers, "cross")
        d1 = _rand_desc(seed=4004)  # different from other's seed 2002
        _enroll(sess, admin_headers, sid, d1)
        tok = _login(sess, email, "student123")
        h = {"Authorization": f"Bearer {tok}"}
        try:
            other_before = _count_attendance_today(sess, admin_headers, other_enrolled_student["id"])
            self_before = _count_attendance_today(sess, admin_headers, sid)

            r = sess.post(
                f"{API}/face/mark-self",
                json={"descriptor": other_enrolled_student["descriptor"]},
                headers=h,
                timeout=20,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            # Since compared only against caller's own descriptor (d1), and other's
            # descriptor differs (different seed / uniform-random over 128 dims,
            # expected L2 distance ~ sqrt(128 * 2/3) ~= 9.2 >> 0.55), must be no_match.
            assert body["matched"] is False
            assert body["reason"] == "no_match"
            # If for any reason it matched, the student in response must be the CALLER,
            # never the "other" student. Assert student id NEVER equals other's id.
            assert body.get("student", {}).get("id") != other_enrolled_student["id"]

            other_after = _count_attendance_today(sess, admin_headers, other_enrolled_student["id"])
            self_after = _count_attendance_today(sess, admin_headers, sid)
            assert other_after == other_before, "must not create attendance for OTHER student"
            assert self_after == self_before, "no_match must not create attendance for caller"
        finally:
            sess.delete(f"{API}/students/{sid}", headers=admin_headers, timeout=20)


# ---------- regression: /api/face/recognize (admin scan) still works ----------
class TestRecognizeRegression:
    def test_admin_recognize_creates_and_dedupes(self, sess, admin_headers):
        sid, _, _ = _mk_student(sess, admin_headers, "recog")
        descriptor = _rand_desc(seed=5005)
        _enroll(sess, admin_headers, sid, descriptor)
        try:
            before = _count_attendance_today(sess, admin_headers, sid)
            r1 = sess.post(f"{API}/face/recognize", json={"descriptor": descriptor},
                           headers=admin_headers, timeout=30)
            assert r1.status_code == 200, r1.text
            b1 = r1.json()
            assert b1["matched"] is True
            assert b1["student"]["id"] == sid
            after1 = _count_attendance_today(sess, admin_headers, sid)
            assert after1 == before + 1

            r2 = sess.post(f"{API}/face/recognize", json={"descriptor": descriptor},
                           headers=admin_headers, timeout=30)
            assert r2.status_code == 200
            b2 = r2.json()
            assert b2["matched"] is True
            assert b2["already_marked"] is True
            after2 = _count_attendance_today(sess, admin_headers, sid)
            assert after2 == after1, "recognize must dedupe same-day attendance"
        finally:
            sess.delete(f"{API}/students/{sid}", headers=admin_headers, timeout=20)
