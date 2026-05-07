# Deployment Guide

This guide covers deploying the attendance system to Vercel (frontend), Render (backend), and Azure SQL Database. It also includes local development setup and troubleshooting tips.

---

## Table of Contents

1. [Environment Variables](#1-environment-variables)
2. [Vercel Deployment (Frontend)](#2-vercel-deployment-frontend)
3. [Render Deployment (Backend)](#3-render-deployment-backend)
4. [Azure SQL Setup and Migration](#4-azure-sql-setup-and-migration)
5. [Local Development Setup](#5-local-development-setup)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Environment Variables

### Backend (Render)

| Variable | Required | Example | Description |
|---|---|---|---|
| `DB_CONNECTION_STRING` | Yes (cloud) | `DRIVER={ODBC Driver 18 for SQL Server};SERVER=myserver.database.windows.net;DATABASE=AttendanceDB;UID=myuser;PWD=mypassword;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30` | Full pyodbc connection string for Azure SQL. When set, overrides Windows Auth fallback. |
| `ALLOWED_ORIGINS` | Yes (cloud) | `https://my-attendance-app.vercel.app` | Comma-separated list of allowed CORS origins. Falls back to `*` (allow all) when not set. |
| `PORT` | Injected by Render | `10000` | TCP port for uvicorn. Render injects this automatically — do not set manually. |
| `MODEL_ROOT` | No | `/opt/render/project/src` | Parent directory of `buffalo_l/` model pack. Defaults to repo root (correct for Render). |
| `SECRET_KEY` | Yes | `a3f8b2c1d4e5f6a7b8c9d0e1f2a3b4c5` | Application secret for token signing. Generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `SERVER` | Local dev only | `.\SQLEXPRESS` | SQL Server hostname for Windows Auth fallback. Not needed when `DB_CONNECTION_STRING` is set. |
| `DATABASE` | Local dev only | `AttendanceDB` | Database name for Windows Auth fallback. Not needed when `DB_CONNECTION_STRING` is set. |

### Frontend (Vercel)

| Variable | Required | Example | Description |
|---|---|---|---|
| `VITE_API_URL` | Yes (cloud) | `https://my-attendance-backend.onrender.com` | Backend base URL for all API calls. Set in Vercel dashboard under Project Settings → Environment Variables. |

---

## 2. Vercel Deployment (Frontend)

1. Push your code to GitHub (ensure `frontend/vercel.json` is committed).
2. Go to [vercel.com](https://vercel.com) → New Project → Import your GitHub repo.
3. Set **Root Directory** to `frontend`.
4. Set **Framework Preset** to `Vite`.
5. Set **Build Command** to `npm run build`.
6. Set **Output Directory** to `dist`.
7. Under **Environment Variables**, add:
   - `VITE_API_URL` = `https://your-backend.onrender.com` (fill in after Render deployment)
8. Click **Deploy**.
9. After deployment, copy the Vercel URL (e.g. `https://my-app.vercel.app`).
10. Go back to Render and set `ALLOWED_ORIGINS` to that URL.

---

## 3. Render Deployment (Backend)

1. Push your code to GitHub (ensure `backend/Procfile` and `backend/runtime.txt` are committed).
2. Ensure the `buffalo_l/` directory with all 5 ONNX files is committed to the repo root.
3. Go to [render.com](https://render.com) → New → Web Service.
4. Connect your GitHub repo.
5. Set **Root Directory** to `backend`.
6. Render will auto-detect `Procfile` and `runtime.txt`.
7. Set **Instance Type** to at least **Standard** (InsightFace requires significant RAM).
8. Under **Environment Variables**, add:
   - `DB_CONNECTION_STRING` = your Azure SQL connection string
   - `ALLOWED_ORIGINS` = your Vercel URL (e.g. `https://my-app.vercel.app`)
   - `SECRET_KEY` = a random 32-byte hex string
9. Click **Create Web Service**.
10. Wait for the build to complete (first build may take 5–10 minutes due to model loading).
11. Copy the Render URL (e.g. `https://my-backend.onrender.com`).
12. Go back to Vercel and update `VITE_API_URL` to this URL, then redeploy.

> **Note on ODBC Driver**: Render's native Python environment includes ODBC Driver 18 for SQL Server. If you encounter driver errors, add a `build.sh` script or use `render.yaml` to install `msodbcsql18`.

---

## 4. Azure SQL Setup and Migration

1. Go to [portal.azure.com](https://portal.azure.com) → Create a resource → SQL Database.
2. Create a new SQL Server (or use existing):
   - Authentication: **SQL authentication** (username + password)
   - Note the server name: `<server>.database.windows.net`
3. Create the database named `AttendanceDB`.
4. Under **Networking**, add your IP address to the firewall rules.
5. Also add the Render outbound IP addresses (find them in Render dashboard → your service → Outbound IPs).
6. Connect using SSMS or Azure Data Studio:
   - Server: `<server>.database.windows.net`
   - Authentication: SQL Server Authentication
   - Username/Password: as set in step 2
7. Open `azure_migration.sql` from the repo root and execute it against `AttendanceDB`.
8. Verify all 8 tables were created: `Login_Master`, `User_Master`, `Student_Master`, `Student_Embeddings`, `Lecture_Master`, `Lecture_Schedule`, `Request_Master`, `Attendance_Record`.
9. Build your `DB_CONNECTION_STRING`:
   ```
   DRIVER={ODBC Driver 18 for SQL Server};SERVER=<server>.database.windows.net;DATABASE=AttendanceDB;UID=<username>;PWD=<password>;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30
   ```

---

## 5. Local Development Setup

1. **Prerequisites**: Python 3.11, Node.js 18+, SQL Server Express (Windows), ODBC Driver 17 for SQL Server.
2. **Database**: Run `Full Database Query.sql` in SSMS to create `AttendanceDB`, then run `timetable_setup.sql`.
3. **Backend**:
   ```bash
   cd backend
   pip install -r requirements.txt
   # Create .env file:
   # SERVER=.\SQLEXPRESS
   # DATABASE=AttendanceDB
   python main.py
   ```
4. **Frontend**:
   ```bash
   cd frontend
   npm install
   # VITE_API_URL is not needed locally — the Vite proxy handles it
   npm run dev
   ```
5. Open `http://localhost:5173` in your browser.

---

## 6. Troubleshooting

- **InsightFace model not found**: Ensure the `buffalo_l/` directory with all 5 ONNX files is committed to the repo root. Check Render logs for the resolved model path.
- **CORS errors in browser**: Verify `ALLOWED_ORIGINS` on Render exactly matches your Vercel URL (no trailing slash).
- **Database connection failed**: Check that Render's outbound IPs are whitelisted in Azure SQL firewall rules.
- **413 Request Too Large**: The backend enforces a 50 MB limit. Reduce image batch size.
