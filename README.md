# Classroom Attendance System
# Classroom Attendance System

Face-recognition-based attendance management system.

**Backend:** FastAPI (Python) | **Frontend:** React + Vite | **AI:** InsightFace buffalo_l (ArcFace, ONNX) | **Database:** SQL Server (Windows Auth)

> See `CREDENTIALS.md` for all login credentials and the complete fresh-start guide.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Project Structure](#project-structure)
3. [Architecture Overview](#architecture-overview)
4. [Database Schema](#database-schema)
5. [Environment Configuration](#environment-configuration)
6. [API Reference](#api-reference)
7. [Frontend Pages](#frontend-pages)
8. [Privilege and Auth System](#privilege-and-auth-system)
9. [Face Recognition Pipeline](#face-recognition-pipeline)
10. [Timetable Feature](#timetable-feature)
11. [Recent Changes and Fixes](#recent-changes-and-fixes)
12. [Running the Application](#running-the-application)
13. [Testing](#testing)
14. [Troubleshooting](#troubleshooting)

---

## Quick Start

### 1. Database Setup (run once in SSMS)

```sql
-- Step 1: Create all tables
Full Database Query.sql

-- Step 2: Add timetable support
timetable_setup.sql

-- Step 3: Seed default superadmin
usernamepsswd.sql
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

Open **http://localhost:5173**

Default login: `superadmin@mitwpu.edu.in` / `Super@admin`

---

## Project Structure

See `structure.txt` for the full annotated file tree.

Key directories:

```
backend/
  main.py              FastAPI app entry point
  auth.py              Authentication
  admin.py             Admin endpoints
  user.py              Teacher endpoints
  superadmin.py        Superadmin endpoints
  model/               InsightFace engine + adapter
  services/            Recognition, training, CSV services

frontend/src/
  pages/               All UI pages
  services/api.js      All API functions (27 total)
  components/          Layout, ProtectedRoute, UI primitives
```

---

## Architecture Overview

```
Browser (React/Vite :5173)
        |  HTTP via Vite proxy
        v
FastAPI (:8000)
  |-- /auth          auth.py
  |-- /admin         admin.py
  |-- /user          user.py
  `-- /superadmin    superadmin.py
        |
        |-- SQL Server (Windows Auth)
        |     `-- AttendanceDB
        |
        `-- InsightFace buffalo_l (ONNX)
              |-- det_10g.onnx      (face detection)
              `-- w600k_r50.onnx    (ArcFace 512-dim embedding)
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

---

## Environment Configuration

### backend/.env

```env
SERVER=.\SQLEXPRESS        # SQL Server instance name
DATABASE=AttendanceDB      # Database name
```

### frontend/.env

```env
# Empty = use Vite dev proxy (recommended for local dev)
# Set for production: VITE_API_URL=http://your-server:8000
VITE_API_URL=
```

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
Enroll a student with face images. Updates existing student if PRN already exists.
Fields: prn, name, year, course, specialisation, rollno, panel, images (base64 array)
Response: `{ "message": "Student enrolled successfully with 5 embeddings", "prn": "..." }`
Error 400: no valid faces detected

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

## Recent Changes and Fixes

### Bug Fixes

**Duplicate attendance record error**
- Fixed: resolve-faces now checks if (lec_id, prn) already exists before INSERT
- Both "existing" and "new" actions are idempotent

**Face ID not found in cache**
- Fixed: FaceResolution model now accepts optional `image` field (base64 fallback)
- If server cache was cleared (restart), uses frontend-provided image
- Embedding still saved, attendance still marked

**Process attendance on finalized lecture**
- Fixed: Backend rejects mark-attendance if attendance_status='Y' (HTTP 400)
- Frontend: button disabled + shows "Lecture Already Finalized" for completed lectures
- Frontend: auto-select skips completed lectures

**Process attendance without selecting lecture**
- Fixed: Button disabled when no lecture selected, shows "Select a Lecture First"
- handleSubmit validates selectedLecId before proceeding

**EnrollStudentRequest missing prn field**
- Fixed: prn field was accidentally removed from the Pydantic model

**Lecture_Schedule table missing**
- Fixed: timetable_setup.sql creates the table idempotently

**Auto-generated lectures failing (NOT NULL constraint)**
- Fixed: user.py now fetches teacher's school/department from User_Master before INSERT

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

**Classroom Attendance System branding**
- Navbar heading updated from "Attendance System"

**Forgot Password**
- Shows informational alert with SSMS reset instructions instead of freezing

---

## Running the Application

### Backend

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

API: http://localhost:8000
Swagger docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm run dev
```

App: http://localhost:5173

The Vite proxy forwards /auth, /admin, /user, /superadmin to :8000.

### If npm install fails

```bash
npm install --legacy-peer-deps
```

---

## Testing

```bash
cd backend
pytest -v
```

All tests mock database and InsightFace. No live DB or GPU required.

---

## Troubleshooting

**Backend 500 on /user/lectures**
- Run timetable_setup.sql in SSMS to create Lecture_Schedule table

**Invalid credentials on login**
- Run the password reset SQL in SSMS (see CREDENTIALS.md)

**Face not detected during enrollment**
- Use well-lit, forward-facing images
- More images = better centroid = better recognition

**Process Attendance button greyed out**
- Select a lecture from the dropdown first
- If it shows "Lecture Already Finalized", choose a different lecture

**Browser showing old version after code change**
- Hard refresh: Ctrl+Shift+R
- Or restart the Vite dev server

**InsightFace model download on first run**
- Requires internet access (~500MB download to ~/.insightface/models/buffalo_l/)
