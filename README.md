# Classroom Attendance System

Face-recognition-based attendance management system using InsightFace ArcFace embeddings.

| Layer | Stack | Production host |
|---|---|---|
| Frontend | React 18 + Vite | **Vercel** — https://capstone-class-attendance-system-us.vercel.app |
| Backend | FastAPI + Python 3.11 | **Hugging Face Spaces (Docker)** — https://Shaunak2110-attendance-backend.hf.space |
| Database | SQL Server (T-SQL) | **Azure SQL Serverless** |
| Face recognition | InsightFace `buffalo_l` (ArcFace, ONNX Runtime) | Bundled in backend container |

> Live deployment runs from the **`deploy-clean`** branch — slimmed for cloud (no torch/ultralytics, pymssql instead of pyodbc, Dockerfile for HF). The `main` branch retains the original local-dev setup.

> See `CREDENTIALS.md` for default login + the fresh-start guide. See `deployment.md` for full cloud deployment instructions.

---

## Table of Contents

1. [Quick Start (Local)](#quick-start-local)
2. [Quick Start (Cloud)](#quick-start-cloud)
3. [Project Structure](#project-structure)
4. [Architecture Overview](#architecture-overview)
5. [Database Schema](#database-schema)
6. [Environment Configuration](#environment-configuration)
7. [API Reference](#api-reference)
8. [Frontend Pages](#frontend-pages)
9. [Privilege and Auth System](#privilege-and-auth-system)
10. [Face Recognition Pipeline](#face-recognition-pipeline)
11. [Timetable Feature](#timetable-feature)
12. [Cloud Deployment Notes](#cloud-deployment-notes)
13. [Running the Application](#running-the-application)
14. [Testing](#testing)
15. [Troubleshooting](#troubleshooting)

---

## Quick Start (Local)

### 1. Database (run once in SSMS)

```sql
-- Run in this order against a fresh AttendanceDB:
1. Full Database Query.sql   -- All tables, indexes, constraints
2. timetable_setup.sql        -- Lecture_Schedule + schedule_id FK
3. usernamepsswd.sql          -- Default Superadmin seed
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Frontend

```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
```

Open **http://localhost:5173**. Login: `superadmin@mitwpu.edu.in` / `Super@admin`.

---

## Quick Start (Cloud)

The system is already deployed. To use the live app:

1. Open **https://capstone-class-attendance-system-us.vercel.app**
2. Login with `superadmin@mitwpu.edu.in` / `Super@admin`
3. First request after idle may take 30–90 s (Azure SQL Serverless wake + InsightFace model download on cold start)

To deploy your own copy, see [`deployment.md`](deployment.md).

---

## Project Structure

```
backend/
  main.py                FastAPI entry point + CORS + exception handlers
  auth.py                /auth/login endpoint
  admin.py               /admin/* — manage teachers, students, schedules
  user.py                /user/* — teacher attendance flow
  superadmin.py          /superadmin/* — manage admins, approve requests
  database.py            pymssql connection wrapper + Row compatibility layer
  dependencies.py        require_privilege, get_current_user_id
  model/
    insightface_engine.py   FaceAnalysis(buffalo_l) wrapper
    inference.py            Recognition orchestration
  services/
    recognition_service.py  Orchestrates mark-attendance flow
    training_service.py     Enrollment / incremental embedding append
    csv_service.py          Attendance CSV generation + download
  Dockerfile             Used by Hugging Face Spaces
  README.md              HF Space metadata frontmatter
  Procfile               Used by Render (legacy / paid plan)
  runtime.txt            Python version pin

frontend/
  src/
    pages/               All UI pages
    services/api.js      27 API functions
    components/          Layout, ProtectedRoute, UI primitives
  vercel.json            SPA rewrites
  vite.config.js         Dev proxy + build config

Full Database Query.sql  Local SQL Server schema (uses USE)
azure_migration.sql      Azure SQL schema (no USE, idempotent)
timetable_setup.sql      Lecture_Schedule additions
usernamepsswd.sql        Superadmin seed insert
deployment.md            Full cloud deployment guide
CREDENTIALS.md           Account credentials + fresh-start guide
```

---

## Architecture Overview

### Local (development)

```
Browser (React/Vite :5173)
        | HTTP via Vite proxy → /auth, /admin, /user, /superadmin
        v
FastAPI (uvicorn :8000)
        |
        |── SQL Server (Windows Auth or SQL Auth)
        |     └── AttendanceDB
        |
        └── InsightFace buffalo_l (ONNX Runtime)
               ├── det_10g.onnx          (face detection)
               └── w600k_r50.onnx        (ArcFace 512-dim embedding)
```

### Production (deployed)

```
Browser
   |
   | HTTPS
   v
Vercel CDN ── serves React SPA (built with VITE_API_URL baked in)
   |
   | XHR to backend URL
   v
HuggingFace Spaces (Docker, 2 vCPU, 16 GB RAM)
   |
   | uvicorn :7860, FastAPI middleware (CORS, body-size limit)
   |
   ├── Azure SQL Serverless (TLS, port 1433, pymssql)
   |     └── ClassAttendanceDB
   |
   └── InsightFace buffalo_l (downloaded to /home/appuser/models/ on first request)
```

### Privilege Levels

| Level | Role | Access |
|---|---|---|
| 1 | Superadmin | Everything |
| 2 | Admin | Admin + User endpoints |
| 3 | Teacher | User endpoints only |

Every request carries `X-User-Id` and `X-Privilege-Level` headers set by the frontend interceptor.

---

## Database Schema

### Tables

| Table | Purpose |
|---|---|
| Login_Master | Credentials + privilege level for all users |
| User_Master | Profile info (name, email, school, department) |
| Student_Master | Enrolled students (PRN, name, year, panel, etc.) |
| Student_Embeddings | InsightFace 512-dim face embeddings (VARBINARY) |
| Lecture_Master | Scheduled lecture instances |
| Lecture_Schedule | Recurring timetable templates |
| Attendance_Record | Per-lecture attendance (Present/Absent) |
| Request_Master | Privilege escalation requests |

### Key Constraints

- `UQ_Attendance_LecId_PRN` — prevents double-marking the same student in the same lecture
- `CK_Lecture_Status` — attendance_status must be 'Y' or 'N'
- `FK_Schedule_User` — Lecture_Schedule.user_id references Login_Master

### Schema files

- `Full Database Query.sql` — uses `USE AttendanceDB`, run in SSMS for **local** SQL Server
- `azure_migration.sql` — `USE`-free and idempotent, run in Azure Query editor for **cloud**
- `timetable_setup.sql` — adds `Lecture_Schedule` table + FK
- `usernamepsswd.sql` — seeds default Superadmin

---

## Environment Configuration

### Local development

`backend/.env`:

```env
# Local SQL Server with Windows Auth (legacy pyodbc-style)
SERVER=.\SQLEXPRESS
DATABASE=AttendanceDB

# Or with explicit SQL auth via connection string (pymssql-compatible)
# DB_CONNECTION_STRING=Driver={ODBC Driver 17 for SQL Server};Server=.\SQLEXPRESS;Database=AttendanceDB;Uid=sa;Pwd=YourPassword;
```

`frontend/.env`:

```env
# Empty = use Vite dev proxy (recommended for local dev)
VITE_API_URL=
```

### Production

| Layer | Variable | Set in |
|---|---|---|
| Backend | `DB_CONNECTION_STRING` | HF Spaces → Settings → Variables and secrets (as **Secret**) |
| Backend | `ALLOWED_ORIGINS` | HF Spaces → Settings → Variables and secrets (as Variable) |
| Backend | `MODEL_ROOT=/home/appuser` | HF Spaces → Settings → Variables and secrets (as Variable) |
| Frontend | `VITE_API_URL` | Vercel → Settings → Environment Variables |

See [`deployment.md`](deployment.md) for full details.

---

## API Reference

### Authentication

#### POST /auth/login
Authenticate with username and password.
Request: `{ "username": "...", "password": "..." }`
Response: `{ "user_id": 5, "username": "...", "privilege_level": 3 }`
Errors: 401 invalid credentials, 500 database error

---

### Admin Endpoints (/admin)
Requires `X-Privilege-Level: 2` or lower.

#### POST /admin/create-teacher
Create a new teacher account (privilege 3).
Fields: username, password, name, email_id, school, department, mob
Response: `{ "user_id": 7, "message": "Teacher created successfully" }`
Error 409: username already exists

#### POST /admin/schedule-lecture
Schedule a one-off lecture. Accepts `username` (string) or `user_id` (int).
School/department auto-filled from teacher profile if not provided.
Fields: username OR user_id, year, specialisation, lecorlab, panel, lec_name, course_code, lecture_datetime
Response: `{ "lec_id": 12, "message": "Lecture scheduled successfully" }`

#### POST /admin/enroll-student
Enroll a student with face images. Updates existing student if PRN already exists. Appends embeddings on repeat calls — useful for batched uploads.
Fields: prn, name, year, course, specialisation, rollno, panel, images (base64 array)
Response: `{ "message": "Student enrolled successfully with 5 embeddings", "prn": "..." }`
Error 400: no valid faces detected
Error 413: request body exceeds ~30 MB (HF Spaces edge limit). Upload in smaller batches.

#### GET /admin/students
Return all enrolled students. Accessible to all logged-in users (privilege 3+).
Used by admin unenroll panel and Results page face-resolution dialog.
Response: Array of `{ prn, name, year, course, specialisation, rollno, panel }`

#### DELETE /admin/unenroll-student/{prn}
Permanently remove a student, all their face embeddings, and all attendance records.
Response: `{ "message": "...", "embeddings_deleted": 5, "attendance_records_deleted": 12 }`
Error 404: student not found

#### GET /admin/lectures
All lectures with teacher username for admin records view.
Response: Array of lecture objects with username field.

#### GET /admin/attendance-analytics
Aggregate attendance data. Query params: year, course_code, panel, username, start_date, end_date.
Response: `{ "subject": "...", "panel": "H", "totalLectures": 10, "overallPercentage": 78.5, "students": [...] }`

#### POST /admin/create-schedule
Create recurring timetable template. One Lecture_Schedule row per selected day.
Fields: username, lec_name, course_code, lecorlab, year, specialisation, panel, days_of_week[], start_time, sem_start_date, sem_end_date
Response: `{ "schedule_id": 3, "message": "Schedule created for 3 day(s) successfully" }`

#### GET /admin/schedules
All active schedule templates with teacher usernames.
Response: Array of ScheduleRecord objects.

#### DELETE /admin/schedule/{schedule_id}
Soft-deactivate a schedule template (sets is_active=0). Existing lectures preserved.
Response: `{ "message": "Schedule deactivated successfully" }`

---

### User/Teacher Endpoints (/user)
Requires `X-Privilege-Level: 3` or lower + `X-User-Id` header.

#### GET /user/lectures/{user_id}
All lectures for a teacher. Timetable-aware: auto-generates today's Lecture_Master rows
from matching Lecture_Schedule templates (idempotent). Results ordered today-first.
Response: Array of LectureResponse objects.

#### GET /user/today-lectures/{user_id}
Only today's lectures, ordered by start time ASC.
Used by Dashboard "Today's Classes" tab.

#### GET /user/schedules/{user_id}
Teacher's own active recurring schedule templates.

#### GET /user/enrolled-students/{lec_id}
Students enrolled in the panel/year/specialisation matching the lecture.
Response: Array of `{ prn, name, rollno }`

#### GET /user/attendance-records/{lec_id}
Attendance records with optional date range filter.
Query params: date_from, date_to (YYYY-MM-DD)
Response: Array of `{ name, rollno, prn, status, lecture_datetime, lec_name }`

#### POST /user/mark-attendance
Process classroom images through InsightFace to identify students.
BLOCKED if lecture is already finalized (attendance_status = 'Y').
Request: `{ "lec_id": 5, "images": ["<base64>", ...], "lecture_datetime": "..." }`
Response: `{ "identified_students": [...], "unidentified_faces": [...] }`
Error 400: lecture already finalized, no images provided
Error 403: lecture does not belong to this teacher
Error 404: lecture not found

#### POST /user/resolve-faces
Resolve unidentified faces. Three actions:
- existing: link to enrolled student, mark present, save face embedding
- new: create student, mark present, save face embedding
- discard: remove from cache, skip

Includes fallback: if server cache was cleared (restart), uses base64 image from frontend.
Duplicate attendance records are silently skipped (idempotent).

Request:
```json
{
  "lec_id": 5,
  "resolutions": [
    { "face_id": "uuid", "action": "existing", "prn": "1032221489", "image": "<base64>" },
    { "face_id": "uuid", "action": "new", "prn": "9999", "name": "...", "panel": "H", "year": "FY", "course": "B.Tech", "specialisation": "CSE", "rollno": "25", "image": "<base64>" },
    { "face_id": "uuid", "action": "discard" }
  ]
}
```

#### POST /user/finalize-attendance
Finalize lecture attendance. Sets attendance_status='Y', generates CSV.
Request: `{ "lec_id": 5, "identified_prns": ["prn1", "prn2"] }`
Response: `{ "message": "Attendance finalized successfully", "csv_path": "..." }`

#### GET /user/download-csv/{lec_id}
Stream attendance CSV as file download. Regenerates on demand.
Response: CSV file (Content-Type: text/csv)

#### GET /user/profile
Current user's profile details.
Response: `{ user_id, username, privilege_level, name, email_id, school, department }`

#### POST /user/request-privilege
Submit privilege escalation request (teacher -> admin). Idempotent.
Response: `{ "message": "Privilege request submitted successfully" }`

---

### Superadmin Endpoints (/superadmin)
Requires `X-Privilege-Level: 1`.

#### GET /superadmin/users
All users with school and department fields.
Response: Array of `{ user_id, username, name, privilege_level, school, department }`

#### POST /superadmin/create-admin
Create admin account (privilege 2).
Fields: username, password, name, email_id, school, department
Response: `{ "user_id": 3, "message": "Admin created successfully" }`
Error 409: username already exists

#### DELETE /superadmin/revoke-user/{user_id}
Demote an admin (privilege 2) to teacher (privilege 3).
Cannot revoke superadmins (privilege 1).
Response: `{ "message": "User rights revoked. Account demoted to Teacher level." }`
Error 400: cannot revoke superadmin, user already teacher-level

#### GET /superadmin/requests
Pending privilege escalation requests.
Response: Array of `{ request_id, user_id, username, name, privilege_level }`

#### POST /superadmin/approve-request
Approve a privilege request. Promotes user to privilege 2 (admin).
Request: `{ "request_id": 1, "user_id": 5 }`
Response: `{ "message": "Privilege escalation approved" }`

---

### Health

#### GET /health
Returns `{"status":"ok"}` if uvicorn is up. Does **not** verify DB connectivity — first `/auth/login` is the smoke test for that.

---

## Frontend Pages

| Page | Route | Access | Description |
|---|---|---|---|
| Login | /login | Public | Username + password form |
| Dashboard | /dashboard | All | Mark attendance (Today/Past tabs), archive logs |
| Results | /results | All | Attendance results, face resolution dialog |
| AdminDashboard | /admin-dashboard | Admin+ | Create teacher, schedule timetable |
| AdminStudents | /admin-students | Admin+ | Enroll student, unenroll student |
| AdminRecords | /admin-records | Admin+ | All lectures, analytics, timetable tab |
| SuperadminDashboard | /superadmin | Superadmin | User roster with revoke, create admin/teacher |
| Profile | /profile | All | User profile details |

---

## Privilege and Auth System

After login, frontend stores in localStorage:
- `user_id`, `username`, `privilege_level`, `token`, `role`

Every axios request automatically attaches:
- `X-User-Id: <user_id>`
- `X-Privilege-Level: <privilege_level>`

Backend `require_privilege(n)` validates `privilege_level <= n`.
`get_current_user_id()` extracts user_id from header.

Route guards in frontend (ProtectedRoute):
- `/superadmin` — privilege [1] only
- `/admin-*` — privilege <= 2
- All others — any logged-in user

---

## Face Recognition Pipeline

### How It Works (No Training Involved)

InsightFace buffalo_l is a **pre-trained model** with fixed weights. No training epochs, no backpropagation. The "learning" is purely adding reference embeddings to the database.

### Enrollment

```
Images (base64) -> InsightFace detect_and_embed()
                -> 512-dim ArcFace embedding per image
                -> Store in Student_Embeddings (VARBINARY)
```

Multiple enrollment calls for the same PRN **append** embeddings rather than replacing — useful when uploading large image sets in batches.

### Recognition

```
Classroom image -> InsightFace detect_and_embed()
               -> 512-dim embedding per detected face
               -> Load centroids from Student_Embeddings
               -> Euclidean distance + ratio test
               -> Match or no match (threshold: 0.85)
               -> similarity = max(0, 1 - dist/threshold)
```

### Incremental Enrollment (resolve-faces)

When a teacher identifies an unknown face, the face crop is saved as a new embedding:
1. Try normal detect_and_embed on the crop
2. If no face detected (tight crop), add 25% padding and retry
3. Store the embedding — next time the same face appears, it will be auto-identified

### Similarity Score

`similarity = max(0.0, 1.0 - euclidean_distance / threshold)`

Ranges 0.0 to 1.0, displayed as percentage in UI.

### Model storage

InsightFace looks for `<MODEL_ROOT>/models/buffalo_l/` containing the ONNX files:
- Local: `MODEL_ROOT` defaults to repo root, expects `buffalo_l/` committed there
- Cloud (HF): `MODEL_ROOT=/home/appuser`, weights auto-download on first request

---

## Timetable Feature

### Overview

Admins create recurring schedule templates (Lecture_Schedule table). Each morning when a teacher opens their dashboard, the system auto-creates Lecture_Master rows for any scheduled classes that day.

### Database Migration

Run `timetable_setup.sql` once. Creates:
- `Lecture_Schedule` table
- `schedule_id` FK column on `Lecture_Master`

### Auto-Generation Logic

When `GET /user/lectures/{user_id}` is called:
1. Queries Lecture_Schedule for templates matching today's day name
2. Checks if a Lecture_Master row already exists for today (idempotent)
3. If not, inserts with attendance_status='N'
4. Returns all lectures: today first, then others DESC

### Admin Workflow

1. Login as Admin -> Management Portal -> Schedule Lectures card
2. Enter teacher username, lecture details, select days (Mon-Sun toggles), start time, semester dates
3. Save Schedule Template -> POST /admin/create-schedule
4. View templates in Admin Records -> Timetable tab
5. Deactivate with trash button (soft-delete)

---

## Cloud Deployment Notes

These are decisions specific to the live deployment that affect runtime behaviour. See [`deployment.md`](deployment.md) for setup steps.

### Why pymssql instead of pyodbc

pyodbc requires Microsoft's `msodbcsql18` driver installed at the OS level. Render's free Python runtime and HF Spaces both run as non-root and don't have this. Switching to **pymssql** (pure-Python with bundled FreeTDS) eliminated the driver dependency. Code differences:

| Concern | pyodbc | pymssql |
|---|---|---|
| Placeholder syntax | `?` | `%s` |
| Row attribute access (`row.user_id`) | ✓ built-in | added via `_RowConnection`/`_RowCursor` wrapper in `database.py` |
| Exception classes | `pyodbc.IntegrityError`, `pyodbc.Error` | `pymssql.IntegrityError`, `pymssql.Error` |
| Connection string | ODBC-style | Native kwargs (server, user, password, database). `database.py` parses ODBC strings into kwargs. |

### Why Hugging Face Spaces instead of Render

InsightFace `buffalo_l` peaks ~600 MB RAM during model load. Render free (512 MB) OOM-kills the worker mid-request, which surfaces in the browser as `ERR_CONNECTION_CLOSED` or stealth-CORS errors. HF Spaces free CPU tier provides 16 GB RAM — comfortable headroom. The `Dockerfile` and `Procfile` both remain in `backend/` so a paid Render Standard plan would also work.

### Azure SQL Serverless behaviour

The DB auto-pauses after 1 hour idle. The first connection after a pause triggers Azure error `40613` for ~30–60 s while the DB resumes. `database.py` retries this transient error 4× with backoff. To bypass entirely, set Auto-pause delay to "Never" — at the cost of 24/7 vCore-second billing.

### CORS and credentials

`main.py` uses `allow_credentials=True` plus a strict origin list (`ALLOWED_ORIGINS`). The wildcard `*` is forbidden by browsers when credentials are allowed, so every frontend origin must be explicitly listed.

### Body size limit

`main.py` middleware caps requests at 50 MB, but HF Spaces' edge proxy enforces a tighter limit (~30 MB) before the request reaches the app. Large enrollment uploads (40+ images) hit this — split into batches of ~10 images per call. The backend's `/admin/enroll-student` endpoint appends embeddings on repeat calls for the same PRN.

---

## Recent Changes and Fixes

### Cloud deployment (deploy-clean branch)

- Slim repo: dropped `evaluation/`, tests, runtime caches (~470 MB removed from working tree)
- Slim `requirements.txt`: 115 → 16 packages (no torch, ultralytics, Windows-only deps)
- Fixed `runtime.txt` encoding (UTF-16 BOM → ASCII)
- Swapped `pyodbc` → `pymssql` for cross-platform Linux deploy
- Added `_RowConnection`/`_RowCursor` wrapper for pyodbc-style attribute access on pymssql tuples
- Added `_connect_with_retry` for Azure SQL Serverless wake-up errors (40613, 40197, etc.)
- Added `Dockerfile` for HF Spaces (gcc/g++/python3-dev for InsightFace Cython build)
- Added HF Space metadata frontmatter to `backend/README.md`
- Connection string parser handles ODBC-style `Pwd={...}` brace escaping

### Bug Fixes (functional)

**Duplicate attendance record error**
- resolve-faces now checks if (lec_id, prn) already exists before INSERT
- Both "existing" and "new" actions are idempotent

**Face ID not found in cache**
- FaceResolution model accepts optional `image` field (base64 fallback)
- If server cache was cleared (restart), uses frontend-provided image
- Embedding still saved, attendance still marked

**Process attendance on finalized lecture**
- Backend rejects mark-attendance if attendance_status='Y' (HTTP 400)
- Frontend: button disabled + shows "Lecture Already Finalized" for completed lectures
- Frontend: auto-select skips completed lectures

**Process attendance without selecting lecture**
- Button disabled when no lecture selected, shows "Select a Lecture First"
- handleSubmit validates selectedLecId before proceeding

**EnrollStudentRequest missing prn field**
- prn field was accidentally removed from the Pydantic model

**Lecture_Schedule table missing**
- timetable_setup.sql creates the table idempotently

**Auto-generated lectures failing (NOT NULL constraint)**
- user.py now fetches teacher's school/department from User_Master before INSERT

### New Features

**Revoke User Rights (Superadmin)**
- DELETE /superadmin/revoke-user/{user_id}
- Demotes admin to teacher level
- Revoke button in System Roster table

**Unenroll Student (Admin)**
- DELETE /admin/unenroll-student/{prn}
- Deletes student + all embeddings + all attendance records
- Searchable unenroll panel in AdminStudents page

**Face Resolution Dialog — Tabbed**
- "Select Existing Student" tab: searchable list of all enrolled students
- Selecting existing student saves face crop as new embedding (auto-recognition next time)
- "Register New Student" tab: manual form for brand-new students

**Forgot Password**
- Shows informational alert with SSMS reset instructions instead of freezing

---

## Running the Application

### Backend (local)

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

API: http://localhost:8000
Swagger docs: http://localhost:8000/docs

### Frontend (local)

```bash
cd frontend
npm run dev
```

App: http://localhost:5173

The Vite proxy forwards /auth, /admin, /user, /superadmin, /health to :8000.

### If npm install fails

```bash
npm install --legacy-peer-deps
```

### Cloud (already deployed)

Just open https://capstone-class-attendance-system-us.vercel.app and log in.

---

## Testing

```bash
cd backend
pytest -v
```

All tests mock the database and InsightFace. No live DB or GPU required.

> Tests live on the `main` branch (or a dev branch with the original test suite). The `deploy-clean` branch strips them to keep the cloud image small.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| **Backend 500 on /user/lectures** | `Lecture_Schedule` table missing | Run `timetable_setup.sql` |
| **Invalid credentials on login** | Login_Master empty or wrong hash | Run `usernamepsswd.sql` (or the cloud-friendly INSERT in CREDENTIALS.md) |
| **Face not detected during enrollment** | Poor image quality | Use well-lit, forward-facing images. Multiple images = better centroid. |
| **Process Attendance button greyed out** | No lecture selected | Pick a lecture from the dropdown. Finalized ones are skipped. |
| **Browser shows old version after code change** | Vite cache | Ctrl+Shift+R or restart the dev server |
| **InsightFace model download on first run** | Expected | ~280 MB download to `~/.insightface/models/buffalo_l/` (local) or `/home/appuser/models/buffalo_l/` (HF Spaces) |
| **First request after long idle very slow** | Azure SQL paused + InsightFace cold load | 30–90 s combined. Subsequent requests are fast. |
| **413 Request Entity Too Large on enroll** | Image batch exceeds HF edge limit | Upload in batches of ~10. Backend appends embeddings per call. |
| **`ERR_HTTP2_PROTOCOL_ERROR` or stealth CORS error** | Backend OOM-killed mid-request (more likely on Render free tier) | Check host metrics; HF Spaces free has 16 GB and shouldn't hit this |
| **`'tuple' has no attribute 'user_id'`** | pymssql tuples vs pyodbc Rows | Already fixed via `_RowConnection` wrapper — verify code is up to date |
| **Permission denied: '/models'** | `MODEL_ROOT` not set on HF Spaces | Set `MODEL_ROOT=/home/appuser` in HF Variables |
