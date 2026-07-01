# AI Smart Attendance System — PRD

## Original Problem Statement
Build "AI Smart Attendance System Using Face Recognition" — a college attendance management web application. Register students, store their faces, and automatically mark attendance via webcam face recognition. Admin dashboard, student CRUD, live scanning page, attendance reports (daily/monthly, search, CSV export). Intended as a BCA final-year project.

## Adaptation
The problem statement asked for Django + SQLite + dlib. To be practical in the cloud Kubernetes container (no physical webcam device, avoid heavy dlib install), the same functional spec is implemented on the Emergent stack:
- Backend: FastAPI + MongoDB + JWT
- Frontend: React + Tailwind + Shadcn + face-api.js (browser-side face detection + 128-D descriptor extraction)
- Backend does Euclidean-distance matching over descriptors stored per student (threshold 0.55)

## Architecture
- `backend/server.py` — FastAPI with routes: `/api/auth/login`, `/api/auth/me`, `/api/students` CRUD, `/api/students/{id}/face` enrollment, `/api/face/recognize`, `/api/attendance` filters, `/api/attendance/stats`, `/api/attendance/me/stats`, `/api/attendance/export` CSV.
- MongoDB collections: `users`, `students`, `attendance`.
- Frontend routes: `/login`, admin `/dashboard`, `/students`, `/students/new`, `/students/:id/edit`, `/students/:id/enroll`, `/scan`, `/attendance`; student `/my`, `/my/attendance`.
- Face recognition: face-api.js loaded from CDN (tinyFaceDetector + landmark68 + faceRecognitionNet).
- Prevent duplicate attendance per day per student.

## Personas
1. **Admin** — Manages students, enrolls their faces, runs live scan, reviews reports, exports CSV.
2. **Student** — Logs in to see own attendance percentage, present days, and history.

## Implemented (2026-07-01)
- JWT auth (admin + student)
- Student CRUD + face enrollment
- Live face scan with automatic attendance marking + duplicate prevention
- Admin dashboard with stats + 7-day trend + recent check-ins
- Attendance page with daily/monthly filter, search, CSV export
- Student self-service dashboard and attendance history
- Seeded admin + 3 sample students
- Swiss high-contrast UI (Manrope headings, Figtree body, IBM Plex Mono for numerics)

## Backlog (P1/P2)
- P1: Bulk face enrollment via multiple photos for higher accuracy
- P1: Attendance reason codes (present/late/absent) with class period selection
- P2: Class timetable & subject-wise attendance
- P2: Email/SMS notifications when a student's percentage drops below threshold
- P2: Multi-face-per-frame batch marking in a single scan pass

## Next Action Items
- Run testing_agent_v3 for end-to-end backend flows
- If desired, add course-wise report filtering and per-student attendance graphs

## Security Hardening (2026-07-01, Demo-friendly pass)
Applied the following in response to the security audit:
- **SEC-002**: `/api/face/recognize` now requires JWT auth (`Depends(current_user)`).
- **SEC-003**: `/api/students` list is now admin-only via `Depends(require_admin)`. Students can still access `/api/students/{id}` for their own record and `/api/attendance/me/stats`.
- **SEC-004**: `JWT_SECRET` hard-coded fallback removed. `server.py` now reads `os.environ["JWT_SECRET"]` and fails fast if missing. Value is stored in `/app/backend/.env`.
- **SEC-005**: All user-controlled inputs to Mongo `$regex` queries (`search`, `month`) are wrapped with `re.escape()`.
- **Login UI**: Removed public demo credentials block and pre-filled inputs.

## Setup Instructions (Local)
Required env vars in `backend/.env`:
```
MONGO_URL="mongodb://localhost:27017"
DB_NAME="attendance_db"
CORS_ORIGINS="*"
JWT_SECRET="<generate with: python -c 'import secrets;print(secrets.token_urlsafe(48))'>"
```
Frontend `frontend/.env`:
```
REACT_APP_BACKEND_URL="<your backend URL>"
```

## Security Hardening #2 (2026-07-01)
- **SEC-001**: Startup seeding only runs when `users` collection is COMPLETELY empty. Demo admin/students are NOT auto-recreated on subsequent restarts, even if deleted. Optional overrides `SEED_ADMIN_PASSWORD` and `SEED_STUDENT_PASSWORD` env vars for the first-run only.
- **SEC-002**: `POST /api/face/recognize` now requires **admin role** (`require_admin`). Students can no longer call this endpoint; their only path to attendance is `/api/face/mark-self` which matches against their OWN descriptor only.
- **SEC-003**: `face_image` (base64 biometric) is no longer returned by `/students/{id}`, `/students` create/update, `/face/recognize`, or `/face/mark-self`. Face descriptors + images are stored and used internally for matching only. Admin ScanPage no longer displays the stored photo.
- Added unique compound index `(student_id, date)` on `attendance` to make dedupe race-safe; `DuplicateKeyError` is handled gracefully in both `/face/recognize` and `/face/mark-self`.

## Security Hardening #3 — Env-required Admin Seed (2026-07-01, SEC-001 fully closed)
- **No hard-coded default passwords anywhere in code.**
- Backend `startup` refuses to boot with an empty DB unless `SEED_ADMIN_EMAIL` + `SEED_ADMIN_PASSWORD` env vars are set. Seed password must pass the same strength rules as `/auth/change-password`.
- Only the admin is seeded on first boot (no sample students). Admin creates students via `POST /api/students`.
- `.env.example` added at `/app/backend/.env.example` with full setup docs.
- Existing dev DB was wiped and re-seeded via the new flow to prove end-to-end.
- Backend enforcement of `force_password_change` (from Hardening #3 iter) still in place: any protected endpoint returns 403 while flag is true, except `/auth/me` and `/auth/change-password`.

## Setup Instructions (Updated)
1. `cp /app/backend/.env.example /app/backend/.env`
2. Edit `/app/backend/.env` and set:
   - `SEED_ADMIN_EMAIL` (your admin email)
   - `SEED_ADMIN_PASSWORD` (strong initial password — will be forced to change on first login)
   - `JWT_SECRET` (random, e.g. `python -c "import secrets;print(secrets.token_urlsafe(48))"`)
   - `MONGO_URL`, `DB_NAME`
3. Start backend (`sudo supervisorctl restart backend`).
4. Open the app, sign in as admin, complete the forced password change.
5. Use the admin dashboard to create students. Each student gets `force_password_change:true` and must change their initial password on first login.
