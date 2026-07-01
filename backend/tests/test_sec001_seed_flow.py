"""
SEC-001 iteration 8 — Env-driven admin seed, no hard-coded defaults,
no sample students, and full end-to-end regression.

All test methods live in a single class so xdist's `--dist loadscope` keeps them
on one worker and shared admin/session state is deterministic.
"""
from __future__ import annotations

import os
import random
import subprocess
import sys
import textwrap
import time
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

SEED_ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "admin@college.edu").strip().lower()
SEED_ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe#Adm1n2026")

ROTATED_ADMIN_PW = "RotatedStr0ng!"
STUDENT_INIT_PW = "Init!alPw2026"
STUDENT_NEW_PW = "StrongerP@ss2026"

_MONGO = MongoClient(os.environ["MONGO_URL"])
_DB = _MONGO[os.environ["DB_NAME"]]

SCRATCH_DB = f"sec001_scratch_{random.randint(100000, 999999)}"


def _login(email, password):
    return requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)


def _bearer(tok):
    return {"Authorization": f"Bearer {tok}"}


def _mongo_reset_admin_to_seed_state():
    pw_hash = bcrypt.hashpw(SEED_ADMIN_PASSWORD.encode(), bcrypt.gensalt()).decode()
    _DB.users.update_one(
        {"email": SEED_ADMIN_EMAIL},
        {"$set": {"password": pw_hash, "force_password_change": True}},
    )


def _run_seed_subprocess(env_overrides):
    env = os.environ.copy()
    for k, v in env_overrides.items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = v
    env["DB_NAME"] = SCRATCH_DB
    script = textwrap.dedent(
        """
        import os, asyncio, sys
        import dotenv
        dotenv.load_dotenv = lambda *a, **kw: False
        sys.path.insert(0, "/app/backend")
        import server
        assert server.DB_NAME == os.environ["DB_NAME"], (
            f"DB_NAME mismatch: server={server.DB_NAME} env={os.environ['DB_NAME']}"
        )
        try:
            asyncio.run(server.seed())
        except RuntimeError as e:
            print("RUNTIME_ERROR::" + str(e))
            sys.exit(0)
        except Exception as e:
            print("OTHER_ERROR::" + type(e).__name__ + "::" + str(e))
            sys.exit(2)
        print("NO_ERROR")
        sys.exit(3)
        """
    )
    return subprocess.run([sys.executable, "-c", script], env=env,
                          capture_output=True, text=True, timeout=60)


def _drop_scratch_db():
    _MONGO.drop_database(SCRATCH_DB)


def _rand_descriptor(seed):
    rng = random.Random(seed)
    return [rng.random() for _ in range(128)]


def _get_active_admin_token():
    """Reset admin to seed state, log in, rotate away the force flag, return token."""
    _mongo_reset_admin_to_seed_state()
    r = _login(SEED_ADMIN_EMAIL, SEED_ADMIN_PASSWORD)
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    rr = requests.post(f"{API}/auth/change-password", headers=_bearer(tok),
                       json={"current_password": SEED_ADMIN_PASSWORD,
                             "new_password": ROTATED_ADMIN_PW}, timeout=30)
    assert rr.status_code == 200, rr.text
    r2 = _login(SEED_ADMIN_EMAIL, ROTATED_ADMIN_PW)
    return r2.json()["access_token"]


@pytest.fixture(scope="class")
def admin_token():
    tok = _get_active_admin_token()
    yield tok


def _mk_student(admin_tok, suffix):
    payload = {
        "name": f"TEST_Student_{suffix}",
        "roll_number": f"TESTROLL{suffix}",
        "email": f"test_student_{suffix}@example.com",
        "course": "TestCourse",
        "phone": "9999999999",
        "password": STUDENT_INIT_PW,
    }
    r = requests.post(f"{API}/students", headers=_bearer(admin_tok), json=payload, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "face_descriptor" not in body
    assert "face_image" not in body
    return body


class TestSEC001E2E:
    """End-to-end validation of the new env-driven admin seed."""

    # ---------- 1) Admin login + old creds dead ----------
    def test_01_admin_login_with_env_credentials_succeeds(self):
        _mongo_reset_admin_to_seed_state()
        r = _login(SEED_ADMIN_EMAIL, SEED_ADMIN_PASSWORD)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["role"] == "admin"
        assert isinstance(d["access_token"], str) and d["access_token"]
        assert d["user"]["email"] == SEED_ADMIN_EMAIL
        assert d["user"]["force_password_change"] is True

    def test_02_old_hardcoded_admin_password_rejected(self):
        assert _login(SEED_ADMIN_EMAIL, "admin123").status_code == 401

    def test_03_old_sample_student_login_rejected(self):
        assert _login("aarav@college.edu", "student123").status_code == 401

    # ---------- 2) No sample students ----------
    def test_04_students_list_has_no_seed_students(self):
        _mongo_reset_admin_to_seed_state()
        r = _login(SEED_ADMIN_EMAIL, SEED_ADMIN_PASSWORD)
        tok = r.json()["access_token"]
        requests.post(f"{API}/auth/change-password", headers=_bearer(tok),
                      json={"current_password": SEED_ADMIN_PASSWORD,
                            "new_password": ROTATED_ADMIN_PW}, timeout=30).raise_for_status()
        gr = requests.get(f"{API}/students", headers=_bearer(tok), timeout=30)
        assert gr.status_code == 200
        lst = gr.json()
        assert isinstance(lst, list)
        seed_emails = {"aarav@college.edu", "diya@college.edu", "rohan@college.edu"}
        assert not any(s["email"] in seed_emails for s in lst)

    # ---------- 3) Seed guard (subprocess w/ scratch DB) ----------
    def test_05_seed_guard_missing_both_env_vars_raises_runtime_error(self):
        proc = _run_seed_subprocess({"SEED_ADMIN_EMAIL": None, "SEED_ADMIN_PASSWORD": None})
        combined = (proc.stdout or "") + (proc.stderr or "")
        assert "RUNTIME_ERROR::" in combined, f"rc={proc.returncode}\n{combined}"
        assert "First-run setup error" in combined
        assert "SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD" in combined
        assert "environment variables must be set" in combined

    def test_06_seed_guard_missing_password_only_raises(self):
        proc = _run_seed_subprocess({"SEED_ADMIN_EMAIL": "someone@example.com",
                                     "SEED_ADMIN_PASSWORD": None})
        combined = (proc.stdout or "") + (proc.stderr or "")
        assert "RUNTIME_ERROR::" in combined
        assert "SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD" in combined

    def test_07_seed_guard_weak_password_raises(self):
        proc = _run_seed_subprocess({"SEED_ADMIN_EMAIL": "someone@example.com",
                                     "SEED_ADMIN_PASSWORD": "weak"})
        combined = (proc.stdout or "") + (proc.stderr or "")
        assert "RUNTIME_ERROR::" in combined
        assert "SEED_ADMIN_PASSWORD rejected" in combined

    def test_08_scratch_db_cleanup(self):
        _drop_scratch_db()
        # DB should not appear in Mongo listing.
        assert SCRATCH_DB not in _MONGO.list_database_names()

    # ---------- 4) Admin forced-password-change lifecycle ----------
    def test_09_admin_forced_change_lifecycle(self):
        _mongo_reset_admin_to_seed_state()
        r = _login(SEED_ADMIN_EMAIL, SEED_ADMIN_PASSWORD)
        assert r.status_code == 200
        d = r.json()
        assert d["user"]["force_password_change"] is True
        tok = d["access_token"]

        # protected endpoint blocked
        gr = requests.get(f"{API}/students", headers=_bearer(tok), timeout=30)
        assert gr.status_code == 403
        assert "password change required" in gr.json().get("detail", "").lower()

        # weak new password rejected
        weak = requests.post(f"{API}/auth/change-password", headers=_bearer(tok),
                             json={"current_password": SEED_ADMIN_PASSWORD,
                                   "new_password": "admin123"}, timeout=30)
        assert weak.status_code == 400

        # proper change
        cp = requests.post(f"{API}/auth/change-password", headers=_bearer(tok),
                           json={"current_password": SEED_ADMIN_PASSWORD,
                                 "new_password": ROTATED_ADMIN_PW}, timeout=30)
        assert cp.status_code == 200

        # same token now unlocked
        gr2 = requests.get(f"{API}/students", headers=_bearer(tok), timeout=30)
        assert gr2.status_code == 200

        # fresh login → flag now false
        r2 = _login(SEED_ADMIN_EMAIL, ROTATED_ADMIN_PW)
        assert r2.status_code == 200
        assert r2.json()["user"]["force_password_change"] is False

    # ---------- 5) Student creation + forced-change gate ----------
    def test_10_student_created_is_force_pw_gated(self, admin_token):
        s = _mk_student(admin_token, f"lc_{int(time.time()*1000)}")
        r = _login(s["email"], STUDENT_INIT_PW)
        assert r.status_code == 200
        d = r.json()
        assert d["role"] == "student"
        assert d["user"]["force_password_change"] is True
        stok = d["access_token"]

        b = requests.get(f"{API}/attendance/me/stats", headers=_bearer(stok), timeout=30)
        assert b.status_code == 403
        assert "password change required" in b.json().get("detail", "").lower()

        cp = requests.post(f"{API}/auth/change-password", headers=_bearer(stok),
                           json={"current_password": STUDENT_INIT_PW,
                                 "new_password": STUDENT_NEW_PW}, timeout=30)
        assert cp.status_code == 200

        assert requests.get(f"{API}/attendance/me/stats", headers=_bearer(stok),
                            timeout=30).status_code == 200
        ms = requests.post(f"{API}/face/mark-self", headers=_bearer(stok),
                           json={"descriptor": [0.0] * 128}, timeout=30)
        assert ms.status_code == 200 and ms.json().get("reason") == "not_enrolled"

    # ---------- 6) Face enroll + mark-self + impersonation ----------
    def test_11_face_enroll_mark_self_and_impersonation(self, admin_token):
        suf = int(time.time() * 1000)
        sa = _mk_student(admin_token, f"faceA_{suf}")
        sb = _mk_student(admin_token, f"faceB_{suf}")
        desc_a = _rand_descriptor(101)
        desc_b = _rand_descriptor(202)
        assert requests.post(f"{API}/students/{sa['id']}/face", headers=_bearer(admin_token),
                             json={"descriptor": desc_a}, timeout=30).status_code == 200
        assert requests.post(f"{API}/students/{sb['id']}/face", headers=_bearer(admin_token),
                             json={"descriptor": desc_b}, timeout=30).status_code == 200

        r = _login(sa["email"], STUDENT_INIT_PW)
        stok = r.json()["access_token"]
        requests.post(f"{API}/auth/change-password", headers=_bearer(stok),
                      json={"current_password": STUDENT_INIT_PW,
                            "new_password": STUDENT_NEW_PW}, timeout=30).raise_for_status()

        m1 = requests.post(f"{API}/face/mark-self", headers=_bearer(stok),
                           json={"descriptor": desc_a}, timeout=30)
        assert m1.status_code == 200 and m1.json()["matched"] is True
        assert m1.json().get("already_marked") is False
        assert "face_image" not in m1.json()

        m2 = requests.post(f"{API}/face/mark-self", headers=_bearer(stok),
                           json={"descriptor": desc_a}, timeout=30)
        assert m2.status_code == 200 and m2.json().get("already_marked") is True

        # Impersonation: A submits B's descriptor → no_match
        m3 = requests.post(f"{API}/face/mark-self", headers=_bearer(stok),
                           json={"descriptor": desc_b}, timeout=30)
        assert m3.status_code == 200
        assert m3.json()["matched"] is False
        assert m3.json().get("reason") == "no_match"

    # ---------- 7) /face/recognize admin-only ----------
    def test_12_face_recognize_admin_only(self, admin_token):
        r = requests.post(f"{API}/face/recognize", headers=_bearer(admin_token),
                          json={"descriptor": _rand_descriptor(999)}, timeout=30)
        assert r.status_code == 200
        assert "face_image" not in r.json()

        suf = f"rc_{int(time.time()*1000)}"
        s = _mk_student(admin_token, suf)
        lr = _login(s["email"], STUDENT_INIT_PW)
        stok = lr.json()["access_token"]
        requests.post(f"{API}/auth/change-password", headers=_bearer(stok),
                      json={"current_password": STUDENT_INIT_PW,
                            "new_password": STUDENT_NEW_PW}, timeout=30).raise_for_status()

        rr = requests.post(f"{API}/face/recognize", headers=_bearer(stok),
                           json={"descriptor": _rand_descriptor(1)}, timeout=30)
        assert rr.status_code == 403

    # ---------- 8) Attendance filters + CSV ----------
    def test_13_attendance_filters(self, admin_token):
        for params in ({"date": "2026-01-15"}, {"month": "2026-01"}, {"search": ".*"}):
            r = requests.get(f"{API}/attendance", headers=_bearer(admin_token),
                             params=params, timeout=30)
            assert r.status_code == 200, f"params={params} body={r.text}"

    def test_14_csv_export(self, admin_token):
        r = requests.get(f"{API}/attendance/export", headers=_bearer(admin_token), timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("text/csv")
        assert r.text.splitlines()[0].startswith("Date,Time,Roll Number")

    # ---------- 9) SEC-003 regression ----------
    def test_15_no_face_image_in_any_endpoint(self, admin_token):
        suf = f"sec003_{int(time.time()*1000)}"
        s = _mk_student(admin_token, suf)
        desc = _rand_descriptor(7)
        assert requests.post(f"{API}/students/{s['id']}/face", headers=_bearer(admin_token),
                             json={"descriptor": desc,
                                   "image_base64": "data:image/png;base64,AAAA"},
                             timeout=30).status_code == 200

        lst = requests.get(f"{API}/students", headers=_bearer(admin_token), timeout=30).json()
        target = next(x for x in lst if x["id"] == s["id"])
        assert "face_image" not in target and "face_descriptor" not in target

        got = requests.get(f"{API}/students/{s['id']}", headers=_bearer(admin_token),
                           timeout=30).json()
        assert "face_image" not in got and "face_descriptor" not in got

        up = requests.put(f"{API}/students/{s['id']}", headers=_bearer(admin_token),
                          json={"phone": "1112223333"}, timeout=30).json()
        assert "face_image" not in up

        rec = requests.post(f"{API}/face/recognize", headers=_bearer(admin_token),
                            json={"descriptor": desc}, timeout=30).json()
        assert "face_image" not in rec
