"""
AI Smart Attendance System - FastAPI Backend
- JWT auth (admin + student)
- Student CRUD with face descriptor enrollment
- Face recognition matching (Euclidean distance on 128-D descriptors)
- Attendance marking with daily duplicate prevention
- Exports CSV report
"""
from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, Query
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os, io, csv, math, uuid, logging, re
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional
from datetime import datetime, timezone, date, timedelta
from pymongo.errors import DuplicateKeyError
import jwt
import bcrypt

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# ---------- Configuration ----------
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
# SEC-004: JWT_SECRET must be provided via environment; fail fast if missing.
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGO = "HS256"
JWT_EXPIRE_HOURS = 24 * 7
FACE_MATCH_THRESHOLD = float(os.environ.get("FACE_MATCH_THRESHOLD", "0.55"))

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="AI Smart Attendance System")
api = APIRouter(prefix="/api")
bearer = HTTPBearer(auto_error=False)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

# ---------- Helpers ----------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def verify_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False

def create_token(uid: str, role: str) -> str:
    payload = {
        "sub": uid,
        "role": role,
        "exp": now_utc() + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": now_utc(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def euclidean(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return math.inf
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

# ---------- Models ----------
class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user: dict

class StudentCreate(BaseModel):
    name: str
    roll_number: str
    email: EmailStr
    course: str
    phone: str
    password: str = "student123"

class StudentUpdate(BaseModel):
    name: Optional[str] = None
    roll_number: Optional[str] = None
    email: Optional[EmailStr] = None
    course: Optional[str] = None
    phone: Optional[str] = None

class FaceEnrollIn(BaseModel):
    descriptor: List[float]
    image_base64: Optional[str] = None  # data URL

class FaceRecognizeIn(BaseModel):
    descriptor: List[float]

class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str

# ---------- Auth Dependency ----------
async def current_user(cred: Optional[HTTPAuthorizationCredentials] = Depends(bearer)) -> dict:
    if not cred:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = jwt.decode(cred.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

async def active_user(user: dict = Depends(current_user)) -> dict:
    """SEC-001: Block all API access while the user has a pending forced password change.
    Only /auth/me and /auth/change-password use `current_user` directly to bypass this gate."""
    if user.get("force_password_change"):
        raise HTTPException(
            status_code=403,
            detail="Password change required. Please change your password before continuing.",
        )
    return user

async def require_admin(user: dict = Depends(active_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user

# ---------- Auth Routes ----------
@api.post("/auth/login", response_model=TokenOut)
async def login(payload: LoginIn):
    doc = await db.users.find_one({"email": payload.email.lower()})
    if not doc or not verify_pw(payload.password, doc["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token(doc["id"], doc["role"])
    user = {k: v for k, v in doc.items() if k not in ("_id", "password")}
    return TokenOut(access_token=token, role=doc["role"], user=user)

@api.get("/auth/me")
async def me(user: dict = Depends(current_user)):
    return user

# ---------- Password policy ----------
def validate_password_strength(pw: str) -> Optional[str]:
    """Return None if strong enough, else an error message."""
    if not pw or len(pw) < 8:
        return "Password must be at least 8 characters."
    if len(pw) > 128:
        return "Password must be at most 128 characters."
    if pw.strip() != pw:
        return "Password cannot start or end with whitespace."
    has_alpha = any(c.isalpha() for c in pw)
    has_digit = any(c.isdigit() for c in pw)
    if not (has_alpha and has_digit):
        return "Password must contain at least one letter and one digit."
    # reject the well-known seeded defaults
    if pw.lower() in {"admin123", "student123", "password", "password1", "12345678"}:
        return "Password is too common. Please choose a stronger one."
    return None

@api.post("/auth/change-password")
async def change_password(payload: ChangePasswordIn, user: dict = Depends(current_user)):
    doc = await db.users.find_one({"id": user["id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_pw(payload.current_password, doc["password"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must be different from the current password")
    err = validate_password_strength(payload.new_password)
    if err:
        raise HTTPException(status_code=400, detail=err)
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"password": hash_pw(payload.new_password), "force_password_change": False}},
    )
    return {"ok": True, "message": "Password changed successfully."}

# ---------- Student Routes (Admin) ----------
@api.get("/students")
async def list_students(_: dict = Depends(require_admin)):
    # SEC-003: strip biometric data from list responses
    students = await db.students.find({}, {"_id": 0, "face_descriptor": 0, "face_image": 0}).sort("created_at", -1).to_list(1000)
    return students

@api.post("/students")
async def create_student(payload: StudentCreate, _: dict = Depends(require_admin)):
    email = payload.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    if await db.students.find_one({"roll_number": payload.roll_number}):
        raise HTTPException(status_code=400, detail="Roll number already exists")
    sid = str(uuid.uuid4())
    student = {
        "id": sid,
        "name": payload.name,
        "roll_number": payload.roll_number,
        "email": email,
        "course": payload.course,
        "phone": payload.phone,
        "face_enrolled": False,
        "face_descriptor": None,
        "face_image": None,
        "created_at": now_utc().isoformat(),
    }
    user_doc = {
        "id": sid,
        "email": email,
        "password": hash_pw(payload.password),
        "role": "student",
        "name": payload.name,
        "force_password_change": True,  # newly created students must change their initial password
        "created_at": now_utc().isoformat(),
    }
    await db.students.insert_one(student)
    await db.users.insert_one(user_doc)
    # SEC-003: strip biometric fields + Mongo _id from response
    student.pop("face_descriptor", None)
    student.pop("face_image", None)
    student.pop("_id", None)
    return student

@api.get("/students/{sid}")
async def get_student(sid: str, user: dict = Depends(active_user)):
    if user["role"] == "student" and user["id"] != sid:
        raise HTTPException(status_code=403, detail="Forbidden")
    # SEC-003: do not return biometric image or descriptor in normal profile responses
    s = await db.students.find_one({"id": sid}, {"_id": 0, "face_descriptor": 0, "face_image": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Student not found")
    return s

@api.put("/students/{sid}")
async def update_student(sid: str, payload: StudentUpdate, _: dict = Depends(require_admin)):
    update = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")
    if "email" in update:
        update["email"] = update["email"].lower()
    res = await db.students.update_one({"id": sid}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    # sync user email/name
    user_update = {}
    if "email" in update: user_update["email"] = update["email"]
    if "name" in update: user_update["name"] = update["name"]
    if user_update:
        await db.users.update_one({"id": sid}, {"$set": user_update})
    s = await db.students.find_one({"id": sid}, {"_id": 0, "face_descriptor": 0, "face_image": 0})
    return s

@api.delete("/students/{sid}")
async def delete_student(sid: str, _: dict = Depends(require_admin)):
    r1 = await db.students.delete_one({"id": sid})
    await db.users.delete_one({"id": sid})
    await db.attendance.delete_many({"student_id": sid})
    if r1.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"ok": True}

@api.post("/students/{sid}/face")
async def enroll_face(sid: str, payload: FaceEnrollIn, _: dict = Depends(require_admin)):
    if len(payload.descriptor) < 64:
        raise HTTPException(status_code=400, detail="Invalid descriptor")
    res = await db.students.update_one(
        {"id": sid},
        {"$set": {
            "face_descriptor": payload.descriptor,
            "face_image": payload.image_base64,
            "face_enrolled": True,
        }},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"ok": True, "student_id": sid, "face_enrolled": True}

# ---------- Face Recognition (Admin-only) ----------
@api.post("/face/recognize")
async def face_recognize(payload: FaceRecognizeIn, _: dict = Depends(require_admin)):
    if len(payload.descriptor) < 64:
        raise HTTPException(status_code=400, detail="Invalid descriptor")
    cursor = db.students.find({"face_enrolled": True}, {"_id": 0})
    best = None
    best_dist = math.inf
    async for s in cursor:
        d = euclidean(payload.descriptor, s.get("face_descriptor") or [])
        if d < best_dist:
            best_dist = d
            best = s
    if not best or best_dist > FACE_MATCH_THRESHOLD:
        return {"matched": False, "distance": best_dist if best else None}

    # Mark attendance (once per day)
    today = now_utc().date().isoformat()
    student_info = {
        "id": best["id"], "name": best["name"], "roll_number": best["roll_number"],
        "course": best["course"],
    }
    try:
        existing = await db.attendance.find_one({"student_id": best["id"], "date": today})
        if existing:
            return {
                "matched": True,
                "already_marked": True,
                "student": student_info,
                "distance": best_dist,
                "attendance": {"date": today, "time": existing["time"]},
            }
        now = now_utc()
        record = {
            "id": str(uuid.uuid4()),
            "student_id": best["id"],
            "student_name": best["name"],
            "roll_number": best["roll_number"],
            "course": best["course"],
            "date": today,
            "time": now.isoformat(),
            "status": "present",
        }
        await db.attendance.insert_one(record)
    except DuplicateKeyError:
        existing = await db.attendance.find_one({"student_id": best["id"], "date": today})
        return {
            "matched": True,
            "already_marked": True,
            "student": student_info,
            "distance": best_dist,
            "attendance": {"date": today, "time": existing["time"] if existing else now_utc().isoformat()},
        }
    return {
        "matched": True,
        "already_marked": False,
        "student": student_info,
        "distance": best_dist,
        "attendance": {"date": today, "time": record["time"]},
    }

# ---------- Student Self-Mark ----------
@api.post("/face/mark-self")
async def face_mark_self(payload: FaceRecognizeIn, user: dict = Depends(active_user)):
    """Student marks their own attendance by matching against ONLY their own enrolled descriptor.
    Prevents impersonation via other students' photos."""
    if user.get("role") != "student":
        raise HTTPException(status_code=403, detail="Only students can self-mark attendance")
    if len(payload.descriptor) < 64:
        raise HTTPException(status_code=400, detail="Invalid descriptor")

    me = await db.students.find_one({"id": user["id"]}, {"_id": 0})
    if not me:
        raise HTTPException(status_code=404, detail="Student profile not found")
    if not me.get("face_enrolled") or not me.get("face_descriptor"):
        return {"matched": False, "reason": "not_enrolled",
                "message": "Your face is not enrolled yet. Please ask the admin to enroll you."}

    dist = euclidean(payload.descriptor, me["face_descriptor"])
    if dist > FACE_MATCH_THRESHOLD:
        return {"matched": False, "reason": "no_match", "distance": dist,
                "message": "Face did not match your registered face. Please try again."}

    today = now_utc().date().isoformat()
    # SEC-003: do not include face_image in response
    student_info = {
        "id": me["id"], "name": me["name"], "roll_number": me["roll_number"],
        "course": me["course"],
    }
    try:
        existing = await db.attendance.find_one({"student_id": me["id"], "date": today})
        if existing:
            return {"matched": True, "already_marked": True, "distance": dist,
                    "student": student_info,
                    "attendance": {"date": today, "time": existing["time"]},
                    "message": "Attendance already marked for today."}
        now = now_utc()
        record = {
            "id": str(uuid.uuid4()),
            "student_id": me["id"],
            "student_name": me["name"],
            "roll_number": me["roll_number"],
            "course": me["course"],
            "date": today,
            "time": now.isoformat(),
            "status": "present",
        }
        await db.attendance.insert_one(record)
    except DuplicateKeyError:
        existing = await db.attendance.find_one({"student_id": me["id"], "date": today})
        return {"matched": True, "already_marked": True, "distance": dist,
                "student": student_info,
                "attendance": {"date": today, "time": existing["time"] if existing else now_utc().isoformat()},
                "message": "Attendance already marked for today."}
    return {"matched": True, "already_marked": False, "distance": dist,
            "student": student_info,
            "attendance": {"date": today, "time": record["time"]},
            "message": "Attendance marked successfully."}

# ---------- Attendance ----------
@api.get("/attendance")
async def list_attendance(
    user: dict = Depends(active_user),
    date_filter: Optional[str] = Query(None, alias="date"),
    month: Optional[str] = Query(None, description="YYYY-MM"),
    student_id: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 500,
):
    q: dict = {}
    if user["role"] == "student":
        q["student_id"] = user["id"]
    elif student_id:
        q["student_id"] = student_id
    if date_filter:
        q["date"] = date_filter
    elif month:
        # SEC-005: escape user-controlled regex input
        q["date"] = {"$regex": f"^{re.escape(month)}"}
    if search:
        # SEC-005: escape user-controlled regex input
        safe = re.escape(search)
        q["$or"] = [
            {"student_name": {"$regex": safe, "$options": "i"}},
            {"roll_number": {"$regex": safe, "$options": "i"}},
        ]
    rows = await db.attendance.find(q, {"_id": 0}).sort("time", -1).to_list(limit)
    return rows

@api.get("/attendance/stats")
async def attendance_stats(_: dict = Depends(require_admin)):
    total_students = await db.students.count_documents({})
    today = now_utc().date().isoformat()
    today_count = await db.attendance.count_documents({"date": today})
    pct = round((today_count / total_students * 100), 1) if total_students else 0.0
    # recent 5
    recent = await db.attendance.find({}, {"_id": 0}).sort("time", -1).to_list(5)
    # attendance last 7 days
    week = []
    for i in range(6, -1, -1):
        d = (now_utc().date() - timedelta(days=i)).isoformat()
        c = await db.attendance.count_documents({"date": d})
        week.append({"date": d, "count": c})
    enrolled = await db.students.count_documents({"face_enrolled": True})
    return {
        "total_students": total_students,
        "today_attendance": today_count,
        "attendance_percentage": pct,
        "face_enrolled": enrolled,
        "recent": recent,
        "week": week,
    }

@api.get("/attendance/me/stats")
async def my_stats(user: dict = Depends(active_user)):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student only")
    total = await db.attendance.count_documents({"student_id": user["id"]})
    # working days considered = number of unique attendance dates in system for demo
    days = await db.attendance.distinct("date")
    working_days = max(len(days), 1)
    pct = round((total / working_days * 100), 1) if working_days else 0.0
    recent = await db.attendance.find({"student_id": user["id"]}, {"_id": 0}).sort("time", -1).to_list(30)
    return {"present_days": total, "working_days": working_days, "attendance_percentage": pct, "recent": recent}

@api.get("/attendance/export")
async def export_csv(
    _: dict = Depends(require_admin),
    date_filter: Optional[str] = Query(None, alias="date"),
    month: Optional[str] = None,
):
    q: dict = {}
    if date_filter:
        q["date"] = date_filter
    elif month:
        # SEC-005: escape user-controlled regex input
        q["date"] = {"$regex": f"^{re.escape(month)}"}
    rows = await db.attendance.find(q, {"_id": 0}).sort("time", -1).to_list(10000)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Time", "Roll Number", "Name", "Course", "Status"])
    for r in rows:
        writer.writerow([r["date"], r["time"], r["roll_number"], r["student_name"], r["course"], r["status"]])
    buf.seek(0)
    filename = f"attendance_{date_filter or month or 'all'}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@api.get("/")
async def root():
    return {"service": "AI Smart Attendance System", "status": "ok"}

# ---------- Startup Seeding ----------
@app.on_event("startup")
async def seed():
    # Indexes
    await db.users.create_index("email", unique=True)
    await db.students.create_index("roll_number", unique=True)
    # SEC hardening: unique attendance per (student, day) - prevents duplicate race inserts.
    # Guard against failure if legacy duplicates exist.
    try:
        await db.attendance.create_index(
            [("student_id", 1), ("date", 1)],
            unique=True,
            name="uniq_student_date",
        )
    except Exception as e:
        log.warning("Could not create unique attendance index (legacy duplicates?): %s", e)

    # SEC-001: Only seed demo data when the users collection is COMPLETELY EMPTY.
    # After first run, we never re-create default accounts, even if they were deleted / had passwords changed.
    existing_users = await db.users.count_documents({})
    if existing_users > 0:
        log.info("Users already exist (%d); skipping demo seed.", existing_users)
        return

    log.warning("First-run detected — seeding demo admin + sample students. Please change these passwords immediately.")
    admin_pw = os.environ.get("SEED_ADMIN_PASSWORD", "admin123")
    student_pw = os.environ.get("SEED_STUDENT_PASSWORD", "student123")

    await db.users.insert_one({
        "id": str(uuid.uuid4()),
        "email": "admin@college.edu",
        "password": hash_pw(admin_pw),
        "role": "admin",
        "name": "System Administrator",
        "force_password_change": True,
        "created_at": now_utc().isoformat(),
    })
    samples = [
        {"name": "Aarav Sharma", "roll_number": "BCA2101", "email": "aarav@college.edu", "course": "BCA", "phone": "9876543210"},
        {"name": "Diya Patel", "roll_number": "BCA2102", "email": "diya@college.edu", "course": "BCA", "phone": "9876543211"},
        {"name": "Rohan Verma", "roll_number": "BCA2103", "email": "rohan@college.edu", "course": "BCA", "phone": "9876543212"},
    ]
    for s in samples:
        sid = str(uuid.uuid4())
        await db.students.insert_one({
            "id": sid, **s, "face_enrolled": False, "face_descriptor": None,
            "face_image": None, "created_at": now_utc().isoformat(),
        })
        await db.users.insert_one({
            "id": sid, "email": s["email"], "password": hash_pw(student_pw),
            "role": "student", "name": s["name"],
            "force_password_change": True,
            "created_at": now_utc().isoformat(),
        })
    log.info("First-run demo seed complete (%d students).", len(samples))

@app.on_event("shutdown")
async def shutdown():
    client.close()

app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
