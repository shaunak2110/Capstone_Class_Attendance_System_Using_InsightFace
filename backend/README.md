---
title: Attendance Backend
emoji: 🎓
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# Class Attendance Backend (FastAPI + InsightFace)

FastAPI service backing the [class attendance frontend on Vercel](https://capstone-class-attendance-system-us.vercel.app). Handles authentication, student enrollment, and face-based attendance marking via InsightFace `buffalo_l` (ArcFace 512-dim embeddings, ONNX Runtime).

> This Space hosts the **`deploy-clean`** branch from [GitHub](https://github.com/shaunak2110/Capstone_Class_Attendance_System_Using_InsightFace/tree/deploy-clean) — a slimmed, cloud-ready cut of the project. The full project (with tests, evaluation, benchmarks) lives on `main`.

---

## Endpoints

| Group | Prefix | Privilege required |
|---|---|---|
| Health | `/health` | Public |
| Auth | `/auth/login` | Public |
| Admin | `/admin/*` | 2 (Admin) or lower |
| User | `/user/*` | 3 (Teacher) or lower |
| Superadmin | `/superadmin/*` | 1 (Superadmin) only |

Full endpoint reference is in the [project README](https://github.com/shaunak2110/Capstone_Class_Attendance_System_Using_InsightFace/blob/deploy-clean/README.md#api-reference). Swagger docs available at `/docs` when running locally — disabled in production for surface-area reasons.

### Auth headers

Every protected endpoint requires:
- `X-User-Id: <integer>` — the user's ID returned by `/auth/login`
- `X-Privilege-Level: <1|2|3>` — same response

The frontend's axios interceptor attaches these automatically from `localStorage`.

---

## Required environment variables

Configure these in **Settings → Variables and secrets**:

| Name | Type | Required | Example | Notes |
|---|---|---|---|---|
| `DB_CONNECTION_STRING` | Secret | Yes | `Driver={ODBC Driver 18 for SQL Server};Server=tcp:my-server.database.windows.net,1433;Database=AttendanceDB;Uid=admin;Pwd={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;` | ODBC-style accepted; the parser strips `tcp:`, `{...}` braces, and ignores driver/encrypt directives that pymssql handles automatically |
| `ALLOWED_ORIGINS` | Variable | Yes | `https://my-app.vercel.app` | Comma-separated allowed CORS origins. **Must be set** — wildcard is forbidden because `allow_credentials=True` |
| `MODEL_ROOT` | Variable | Yes | `/home/appuser` | Parent of `models/buffalo_l/`. Must be writable by the container user (UID 1000). InsightFace creates `<MODEL_ROOT>/models/buffalo_l/` and downloads weights on first request |

Alternative individual vars (only used if `DB_CONNECTION_STRING` is unset): `SERVER`, `DATABASE`, `DB_USER`, `DB_PASSWORD`.

---

## Container

`Dockerfile` highlights:
- `python:3.11-slim` base
- Adds `gcc`, `g++`, `python3-dev` so InsightFace's `mesh_core_cython` extension compiles from source
- Adds `libglib2.0-0`, `libgomp1` for opencv-python-headless and ONNX Runtime
- Non-root `appuser` (UID 1000) — HF Spaces requirement
- `pip install --user` to `~/.local`
- Listens on `${PORT}` (HF injects `PORT=7860`)

First build takes 5–10 minutes (compiling Cython). Subsequent rebuilds are faster thanks to layer caching.

---

## Runtime behaviour

### First request after a cold start

1. Azure SQL Serverless wakes (~30–60 s, transient `40613` errors retried internally)
2. InsightFace downloads `buffalo_l` ONNX weights (~280 MB) to `<MODEL_ROOT>/models/buffalo_l/`
3. Model loads into memory (~600 MB RAM peak)

Subsequent requests are fast.

### Memory profile

- Idle: ~200 MB
- Model loaded: ~800 MB
- Per-request peak (large enrollment batch): up to ~1.5 GB

HF Spaces free CPU tier provides 16 GB — comfortable headroom.

### Body size limit

The middleware caps requests at 50 MB, but HF's edge proxy enforces a tighter limit (~30 MB) before the request reaches the app. Large enrollment uploads (40+ images) hit this. Solution: split into batches of ~10 images per call. The `/admin/enroll-student` endpoint **appends** embeddings on repeat calls for the same PRN.

### Ephemeral filesystem

HF Spaces free tier resets the container filesystem on every restart. Means `MODEL_ROOT` cache is lost and `buffalo_l` re-downloads on first request after restart. Persistent storage requires a paid HF tier or baking the weights into the Docker image (~280 MB image size increase).

---

## Local development

```bash
cd backend
pip install -r requirements.txt

# .env (gitignored)
# DB_CONNECTION_STRING=Driver={ODBC Driver 17 for SQL Server};Server=.\SQLEXPRESS;Database=AttendanceDB;Uid=sa;Pwd=YourPassword;
# OR for Windows Auth:
# SERVER=.\SQLEXPRESS
# DATABASE=AttendanceDB

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Hit `http://localhost:8000/docs` for the interactive Swagger UI.

---

## Module layout

```
main.py                      FastAPI app, CORS, exception handlers, body-size middleware
auth.py                      /auth/login
admin.py                     /admin/* — manage teachers, students, schedules
user.py                      /user/* — teacher attendance flow (mark, resolve, finalize, CSV)
superadmin.py                /superadmin/* — manage admins, approve privilege requests
database.py                  pymssql connection wrapper:
                              - ODBC-style connection string parser
                              - Azure SQL transient error retry (40613 etc)
                              - _RowConnection / _RowCursor for pyodbc-style attribute access
dependencies.py              require_privilege(n), get_current_user_id()
model/
  insightface_engine.py      FaceAnalysis(buffalo_l) wrapper, MODEL_ROOT resolution
  inference.py               Recognition orchestration, threshold + ratio test
services/
  recognition_service.py     Orchestrates mark-attendance flow, unidentified face cache
  training_service.py        Enrollment + incremental embedding append
  csv_service.py             Per-lecture CSV generation + download streaming
Dockerfile                   HF Spaces container
Procfile                     Render fallback (legacy / paid plan)
runtime.txt                  Python version pin (Render)
requirements.txt             Slim cloud-only deps (16 packages)
```

---

## Deployment guide

Full step-by-step setup (Azure SQL, HF Spaces, Vercel) is in [`deployment.md`](https://github.com/shaunak2110/Capstone_Class_Attendance_System_Using_InsightFace/blob/deploy-clean/deployment.md) on GitHub.
