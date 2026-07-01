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
