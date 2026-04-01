# Role-Based Attendance System with Facial Recognition

An automated attendance tracking system for educational institutions using facial recognition and role-based access control.

## Tech Stack

- **Backend**: FastAPI, Python 3.11, SQL Server (pyodbc), PyTorch, facenet-pytorch
- **Frontend**: React (Vite), Tailwind CSS, shadcn/ui
- **Face Recognition**: MTCNN (face detection) + custom FaceEmbeddingNet (128-dim embeddings)

## Roles

| Privilege Level | Role | Access |
|---|---|---|
| 1 | Superadmin | Manage admins, view all users |
| 2 | Admin | Enroll students, schedule lectures, manage teachers |
| 3 | Teacher | Mark attendance, finalize, download CSV |

---

## Project Structure

```
├── backend/
│   ├── model/
│   │   ├── face_model.py          # FaceModel wrapper (embeddings, identify, save/load)
│   │   └── inference.py           # InferenceEngine (MTCNN detection + recognition)
│   ├── services/
│   │   ├── recognition_service.py # Orchestrates recognition workflow
│   │   ├── training_service.py    # Incremental model training
│   │   └── csv_service.py         # Attendance CSV generation
│   ├── main.py                    # FastAPI app, startup, shared model injection
│   ├── auth.py                    # Login endpoint
│   ├── admin.py                   # Admin endpoints (enroll student, schedule lecture, create teacher)
│   ├── user.py                    # Teacher endpoints (mark attendance, finalize)
│   ├── superadmin.py              # Superadmin endpoints (create admin, list users)
│   ├── database.py                # DB connection helpers
│   ├── dependencies.py            # Auth dependencies (require_privilege, get_current_user_id)
│   ├── face_model.py              # FaceEmbeddingNet neural network definition
│   ├── trained_face_brain.pth     # Saved model weights + enrolled embeddings
│   ├── trained_face_brain_mappings.pkl  # PRN → embeddings backup
│   ├── Attendance Records/        # Generated CSV files saved here
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Login.jsx
│       │   ├── Dashboard.jsx          # Teacher/Admin attendance workflow
│       │   ├── SuperadminDashboard.jsx # Superadmin user management
│       │   ├── AdminStudents.jsx      # Student enrollment
│       │   └── Results.jsx            # Attendance results + finalize
│       ├── services/
│       │   └── api.js                 # Axios API client
│       └── components/
│           ├── Layout.jsx
│           └── ProtectedRoute.jsx
├── setup_database.sql             # Full DB schema
└── README.md
```

---

## Setup

### 1. Database

Run `setup_database.sql` in SQL Server Management Studio (SSMS) or via sqlcmd:

```bash
sqlcmd -S .\SQLEXPRESS -d master -i setup_database.sql
```

This creates: `Login_Master`, `User_Master`, `Student_Master`, `Lecture_Master`, `Attendance_Record`, `Request_Master`.

### 2. Create initial superadmin account

Use `backend/passgen.py` to generate a bcrypt hash, then insert manually:

```sql
INSERT INTO Login_Master (username, password_hash, privilege_level)
VALUES ('superadmin@yourdomain.com', '<bcrypt_hash>', 1);

INSERT INTO User_Master (user_id, name, email_id, school, department)
VALUES (SCOPE_IDENTITY(), 'Super Admin', 'superadmin@yourdomain.com', 'MIT', 'Admin');
```

### 3. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Create `backend/.env`:

```env
SERVER=.\SQLEXPRESS
DATABASE=AttendanceDB
UID=capstonedb
PWD=capstone
DRIVER=ODBC Driver 17 for SQL Server
```

Start the server:

```bash
uvicorn main:app --reload
```

API available at `http://127.0.0.1:8000` — docs at `http://127.0.0.1:8000/docs`

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

App available at `http://localhost:5173`

---

## Workflow

### Admin: Enroll a Student
1. Log in as admin → click **Manage Students**
2. Fill in PRN, Name, Panel
3. Upload exactly **25 face photos** of the student
4. Click **Enroll Student** — MTCNN detects and crops faces, embeddings are generated and saved

### Admin: Schedule a Lecture
Use the API directly (`POST /admin/schedule-lecture`) or via Swagger UI at `/docs`.

### Teacher: Mark Attendance
1. Log in as teacher → select a scheduled lecture
2. Upload one or more classroom photos
3. Click **Process Attendance** — faces are detected and matched
4. Review identified students on the Results page
5. Click **Finalize Attendance** — writes to DB and generates CSV in `backend/Attendance Records/`

---

## API Overview

| Method | Endpoint | Role | Description |
|---|---|---|---|
| POST | `/auth/login` | All | Login |
| POST | `/superadmin/create-admin` | Superadmin | Create admin account |
| GET | `/superadmin/users` | Superadmin | List all users |
| POST | `/admin/create-teacher` | Admin | Create teacher account |
| POST | `/admin/enroll-student` | Admin | Enroll student with 25 images |
| POST | `/admin/schedule-lecture` | Admin | Schedule a lecture |
| GET | `/user/lectures/{user_id}` | Teacher | Get teacher's lectures |
| POST | `/user/mark-attendance` | Teacher | Process classroom images |
| POST | `/user/finalize-attendance` | Teacher | Save attendance + generate CSV |
| GET | `/health` | All | Health check |

All protected endpoints require `X-User-Id` and `X-Privilege-Level` headers (set automatically by the frontend).

---

## Environment Variables

| Variable | Description | Example |
|---|---|---|
| `SERVER` | SQL Server host | `.\SQLEXPRESS` |
| `DATABASE` | Database name | `AttendanceDB` |
| `UID` | DB username | `capstonedb` |
| `PWD` | DB password | `yourpassword` |
| `DRIVER` | ODBC driver | `ODBC Driver 17 for SQL Server` |
| `FACE_MODEL_PATH` | Model weights path (optional) | `trained_face_brain.pth` |

---

## Notes

- The face model (`trained_face_brain.pth`) stores both network weights and enrolled student embeddings. Back it up after enrolling students.
- CSV files are saved to `backend/Attendance Records/` with filename format: `{panel}_{lecture_name}_{datetime}.csv`
- MTCNN is used at both enrollment and recognition time to ensure consistent face crops — this is critical for accurate matching.
- The similarity threshold for face matching is `0.6` (cosine similarity). Adjust in `recognition_service.py` if needed.
