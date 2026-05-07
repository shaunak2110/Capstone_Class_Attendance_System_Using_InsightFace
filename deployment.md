# Deployment Guide

End-to-end guide for deploying the attendance system to production.

**Live deployment:**
| Layer | Host | URL |
|---|---|---|
| Frontend | Vercel | https://capstone-class-attendance-system-us.vercel.app |
| Backend | Hugging Face Spaces | https://Shaunak2110-attendance-backend.hf.space |
| Database | Azure SQL | `attendance-server-shaunak.database.windows.net` / `ClassAttendanceDB` |

GitHub branch deployed: **`deploy-clean`** (slimmed, cloud-ready).

---

## Why this stack

| Choice | Reason |
|---|---|
| **Vercel** for frontend | Native Vite support, free tier, automatic preview deploys per branch. |
| **Hugging Face Spaces** for backend | InsightFace + ONNX Runtime peak at ~600 MB RAM during model load — exceeds Render free tier's 512 MB. HF Spaces free CPU tier provides 2 vCPU + 16 GB RAM, no sleep. |
| **Azure SQL Serverless** for DB | Auto-pause when idle, generous free vCore-second budget, public endpoint reachable from any host. |
| **pymssql** instead of pyodbc | pymssql is pure-Python on Linux (uses bundled FreeTDS); pyodbc requires `msodbcsql18` installed at the OS level, which isn't available on HF Spaces or Render's Python runtime without Docker. |

> **Render was tried first and abandoned** because the backend OOM-killed during InsightFace's `buffalo_l` model load on the 512 MB free tier. The `deploy-clean` branch retains a `Dockerfile` and Render-compatible patterns in case you upgrade to a paid Render Standard plan later.

---

## Table of Contents

1. [Environment Variables](#1-environment-variables)
2. [Azure SQL Setup](#2-azure-sql-setup)
3. [Backend on Hugging Face Spaces](#3-backend-on-hugging-face-spaces)
4. [Frontend on Vercel](#4-frontend-on-vercel)
5. [Local Development](#5-local-development)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Environment Variables

### Backend (HF Spaces — Settings → Variables and secrets)

| Variable | Type | Required | Example | Description |
|---|---|---|---|---|
| `DB_CONNECTION_STRING` | Secret | Yes | `Driver={ODBC Driver 18 for SQL Server};Server=tcp:my-server.database.windows.net,1433;Database=AttendanceDB;Uid=admin;Pwd={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;` | Full connection string (ODBC-style is supported — `database.py` parses it). Braces around the password are stripped automatically. |
| `ALLOWED_ORIGINS` | Variable | Yes | `https://my-app.vercel.app` | Comma-separated allowed CORS origins. **Required** because the backend uses `allow_credentials=True`, which forbids the wildcard `*`. |
| `MODEL_ROOT` | Variable | Yes | `/home/appuser` | Parent of `models/buffalo_l/`. Must be a directory the container user (UID 1000) can write to — InsightFace creates `<MODEL_ROOT>/models/buffalo_l/` and downloads weights on first request. |
| `PORT` | Variable | No | `7860` | HF default. Already set in the Dockerfile. |

### Backend (alternative env vars, used only if `DB_CONNECTION_STRING` is unset)

| Variable | Description |
|---|---|
| `SERVER` | DB hostname, e.g. `my-server.database.windows.net` |
| `DATABASE` | Database name |
| `DB_USER` | SQL auth username |
| `DB_PASSWORD` | SQL auth password |

### Frontend (Vercel — Settings → Environment Variables)

| Variable | Required | Example | Description |
|---|---|---|---|
| `VITE_API_URL` | Yes (production) | `https://Shaunak2110-attendance-backend.hf.space` | Backend base URL. Vite bakes this into the bundle at build time, so any change requires a redeploy. |

---

## 2. Azure SQL Setup

### Create the server + database

1. Azure portal → **Create a resource** → **SQL Database**
2. Server: create new with **SQL authentication** (note username + password)
3. Database name: `ClassAttendanceDB` (or whatever you prefer)
4. Compute tier: **Serverless General Purpose Gen5** (auto-pauses, free monthly vCore-second budget)
5. Create

### Open the firewall

The database is locked down by default. Render/HF/Vercel containers can't connect until you allow them.

1. SQL **server** (not database) → **Security** → **Networking**
2. **Public network access:** Selected networks
3. Tick **Allow Azure services and resources to access this server**
4. Add a firewall rule:
   - Start IPv4: `0.0.0.0`
   - End IPv4: `255.255.255.255` *(wide-open for dev; tighten with Render's static IPs on paid plans, or use Azure Service Endpoints)*
5. Save

### Run schema + seed scripts

Use Azure portal → your DB → **Query editor (preview)** → log in with SQL credentials → paste and run, in order:

| Order | File | Purpose |
|---|---|---|
| 1 | `azure_migration.sql` | Idempotent schema (Login_Master, User_Master, Student_Master, Student_Embeddings, Lecture_Master, Lecture_Schedule, Request_Master, Attendance_Record). **Use this on Azure SQL, not `Full Database Query.sql`** — the former is `USE`-free and idempotent. |
| 2 | `timetable_setup.sql` | Adds `Lecture_Schedule` and `schedule_id` FK *(only if not already in `azure_migration.sql`)*. |
| 3 | `usernamepsswd.sql` (without the `USE AttendanceDB; GO` lines) | Seeds the default Superadmin: `superadmin@mitwpu.edu.in` / `Super@admin`. |

> Azure SQL forbids `USE <db>` between databases — connections target the DB selected in the connection string. Strip `USE` and `GO` statements when adapting local SSMS scripts.

### Build the connection string

```
Driver={ODBC Driver 18 for SQL Server};Server=tcp:<server>.database.windows.net,1433;Database=<db>;Uid=<user>;Pwd={<password>};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;
```

The braces around `<password>` are ODBC syntax — they're literally part of the string. Our `database.py` parser strips them automatically before passing to pymssql.

### Note on Serverless auto-pause

Serverless DBs pause when idle (default: 1 hour). The first request after a pause can take 30–60 s while the DB resumes, returning Azure error `40613` until ready. The backend already retries this transient error up to 4× with backoff (3 s / 6 s / 12 s) — see `database.py` `_connect_with_retry`. Subsequent requests are fast.

To disable auto-pause: DB → **Compute + storage** → set **Auto-pause delay** to "Never". Trade-off: you'll be billed for vCore-seconds 24/7 instead of only when active.

---

## 3. Backend on Hugging Face Spaces

### Create the Space

1. [huggingface.co](https://huggingface.co) → sign in → profile menu → **New Space**
2. Settings:
   - SDK: **Docker** → **Blank** template
   - Hardware: **CPU basic** (free, 16 GB RAM)
   - Visibility: Public is fine (the API still requires login)
3. Create

You'll get a Space URL: `https://huggingface.co/spaces/<username>/<space-name>` and a public app URL: `https://<username>-<space-name>.hf.space`.

### Push the backend

HF Spaces is its own git repo, separate from GitHub. Cleanest workflow: clone it as a sibling folder, copy the `backend/` contents in, push.

```powershell
# Clone the empty Space repo (sibling to your project folder)
git clone https://huggingface.co/spaces/<username>/<space-name> C:\HF-attendance-backend
cd C:\HF-attendance-backend

# Copy backend contents (note: the dot — copies contents, not the folder itself)
xcopy /E /Y C:\CapstoneVer3\backend\* .

# Drop Render-specific files HF doesn't need
del Procfile runtime.txt .env

# Commit and push
git add -A
git commit -m "Initial backend deploy"
git push
```

When prompted for a password, generate an HF access token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) (Write scope) and paste it. Username is your HF handle.

### Set the secrets

Space page → **Settings** (gear icon, top right) → **Variables and secrets** → **New secret/variable** for each:

| Name | Type | Value |
|---|---|---|
| `DB_CONNECTION_STRING` | Secret | (full Azure SQL connection string from Section 2) |
| `ALLOWED_ORIGINS` | Variable | `https://<your-vercel-app>.vercel.app` |
| `MODEL_ROOT` | Variable | `/home/appuser` |

The Space restarts automatically after each one is added.

### Watch the build

Space page → **Logs** tab. First build takes 5–10 minutes (compiling InsightFace's Cython extension, installing ONNX Runtime). Status badge:
- 🟡 Building → 🟢 Running (success)
- 🔴 Build failed → check log for the actual error

### Verify

Open `https://<username>-<space-name>.hf.space/health` in a browser — should return `{"status":"ok"}`.

### What the Dockerfile does

`backend/Dockerfile`:
- `python:3.11-slim` base (smallest viable Python image)
- Adds `gcc`, `g++`, `python3-dev` so InsightFace's `mesh_core_cython` extension compiles from source
- Adds `libglib2.0-0`, `libgomp1` for opencv-python-headless and ONNX Runtime
- Creates non-root `appuser` (HF runs containers as UID 1000)
- Pip-installs `requirements.txt` to `~/.local`
- `CMD: uvicorn main:app --host 0.0.0.0 --port ${PORT}` (HF injects `PORT=7860`)

### First-request behaviour

On the first call to any face-recognition endpoint, InsightFace downloads `buffalo_l` weights (~280 MB) to `<MODEL_ROOT>/models/buffalo_l/`. This takes 30–60 s. Subsequent requests are instant. Note: HF Spaces' filesystem is **ephemeral** on the free tier — every Space restart re-downloads the model.

---

## 4. Frontend on Vercel

### Create the project

1. Push the `deploy-clean` branch to GitHub (already done in this repo).
2. [vercel.com](https://vercel.com) → **New Project** → import your GitHub repo
3. Settings:
   - **Framework Preset:** Vite
   - **Root Directory:** `frontend`
   - **Build Command:** `npm run build` (default)
   - **Output Directory:** `dist` (default)
   - **Branch:** `deploy-clean` (or whichever branch hosts your latest code)
4. **Environment Variables** → add `VITE_API_URL=https://<username>-<space-name>.hf.space`
5. **Deploy**

### Repointing or rotating the backend URL

If you change the backend URL later: Vercel → Settings → Environment Variables → edit `VITE_API_URL` → Save → **Deployments** → latest → ⋯ → **Redeploy**. Vite bakes env vars in at build time — an existing build won't pick up env-var changes without a rebuild.

### Vercel Deployment Protection

If you see a "403 Forbidden" page on a fresh preview deploy, it's Vercel's preview password protection. Disable for production: Vercel → Settings → **Deployment Protection** → set to "Disabled" or "Only Preview Deployments".

---

## 5. Local Development

### Prerequisites

| What | Version | Where |
|---|---|---|
| Python | 3.11.x | [python.org](https://www.python.org/downloads/) |
| Node.js | 20.19+ or 22.12+ | [nodejs.org](https://nodejs.org/) |
| SQL Server | Express (free) is fine | [Microsoft](https://www.microsoft.com/en-us/sql-server/sql-server-downloads) |
| SSMS | Latest | [aka.ms/ssmsfullsetup](https://aka.ms/ssmsfullsetup) |
| ODBC Driver 17 for SQL Server | Latest | [Microsoft Docs](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) — needed only if you stick with `pyodbc` locally |

### Choose a DB driver

The cloud deploy uses `pymssql`. For local development you can use either pymssql (matches production exactly) or pyodbc (older codebases used this). The `database.py` on `deploy-clean` is pymssql-only; if you need to support both, swap based on import.

### Database setup (local SQL Server)

In SSMS, run in this order against a freshly created `AttendanceDB`:

1. `Full Database Query.sql` — full schema (uses `USE AttendanceDB`, fine for local)
2. `timetable_setup.sql` — Lecture_Schedule + FK
3. `usernamepsswd.sql` — Superadmin seed

### Backend

```bash
cd backend
pip install -r requirements.txt

# .env file — for local SQL Server with SQL auth:
# DB_CONNECTION_STRING=Driver={ODBC Driver 17 for SQL Server};Server=.\SQLEXPRESS;Database=AttendanceDB;Uid=sa;Pwd=YourPassword;
#
# Or for Windows Auth on the old pyodbc-based code:
# SERVER=.\SQLEXPRESS
# DATABASE=AttendanceDB

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm install --legacy-peer-deps   # peer-dep conflicts on some Node versions
npm run dev
```

The Vite dev proxy forwards `/auth`, `/admin`, `/user`, `/superadmin`, `/health` to `http://127.0.0.1:8000` (see `vite.config.js`). `VITE_API_URL` should be left **empty** locally so the proxy is used.

Open **http://localhost:5173**, log in with `superadmin@mitwpu.edu.in` / `Super@admin`.

---

## 6. Troubleshooting

### Backend

| Symptom | Likely cause | Fix |
|---|---|---|
| `[Errno 13] Permission denied: '/models'` | `MODEL_ROOT` env var not set, fallback resolves to filesystem root `/` which appuser can't write to | Set `MODEL_ROOT=/home/appuser` in HF Variables |
| `Failed to connect using DB_CONNECTION_STRING. Error: (40613, ...)` | Azure SQL Serverless is paused | The retry layer should handle this; if it persists past 30 s, manually wake the DB by running `SELECT 1` in Azure Query editor |
| `Adaptive Server connection failed` | DB firewall blocks the host | Add the host's outbound IP (or `0.0.0.0` – `255.255.255.255` for dev) to Azure SQL → Networking → Firewall rules |
| `g++ failed: No such file or directory` during HF build | Slim image lacks compiler; insightface's Cython extension can't build | Already fixed in `Dockerfile` — `apt-get install gcc g++ python3-dev` |
| Browser shows `ERR_HTTP2_PROTOCOL_ERROR` or "CORS blocked" but server seems fine | Backend OOM-killed mid-request — error has no CORS headers, browser misreports as CORS | Check Render/HF metrics for memory cap. Move to host with more RAM (HF Spaces free has 16 GB) |
| 413 `Request Entity Too Large` on enroll | Image batch exceeds HF Spaces' edge proxy limit (~30 MB) | Upload in batches of ~10 images; backend appends embeddings per call |
| `'tuple' object has no attribute 'user_id'` | pymssql cursors return tuples; pyodbc returned Row objects with attribute access | Already fixed via `_RowConnection` / `_RowCursor` wrapper in `database.py` — verify code is up to date |
| `ImportError: No module named 'pymssql'` locally | Local env still on pyodbc | Either `pip install pymssql` or check out a branch where `database.py` uses pyodbc |

### Frontend

| Symptom | Fix |
|---|---|
| API calls 404 or hit localhost in production | `VITE_API_URL` not set (or set in wrong Vercel environment) — verify in Vercel → Settings → Environment Variables, then **redeploy** (Vite bakes envs at build time) |
| CORS errors that *aren't* a stealth backend crash | `ALLOWED_ORIGINS` on the backend doesn't exactly match the frontend origin (no trailing slash, no `http://` mismatch) |

### Database

| Symptom | Fix |
|---|---|
| First-request latency 30–60 s after idle | Azure SQL Serverless waking from auto-pause. Set Auto-pause delay to "Never" if you can afford the vCore-second cost. |
| `Cannot open database "ClassAttendanceDB" requested by the login` | Connection string targets a DB that doesn't exist on the server. Verify spelling and that you ran the schema script on this DB. |

---

## Deployment checklist

When pushing a new build:

- [ ] Schema/seed migrations are idempotent (no `USE`, no destructive `DROP`s)
- [ ] `requirements.txt` is the slim production list (no torch, ultralytics, Windows-only deps)
- [ ] `runtime.txt` (if used) is plain ASCII (UTF-16/BOM breaks Render and HF)
- [ ] `.env` is **not** committed
- [ ] `MODEL_ROOT` is set to a writable directory on the target host
- [ ] `ALLOWED_ORIGINS` matches the frontend production URL exactly
- [ ] CORS sanity test: `curl -i -X OPTIONS <backend>/auth/login -H "Origin: <frontend>"` returns `Access-Control-Allow-Origin: <frontend>`
- [ ] `/health` returns `{"status":"ok"}` after deploy
- [ ] First login from the deployed frontend succeeds (catches DB connectivity + CORS in one test)
