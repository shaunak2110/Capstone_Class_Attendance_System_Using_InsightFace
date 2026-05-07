# Design Document: Cloud Deployment

## Overview

This design prepares the attendance system for cloud deployment across three platforms:

- **Frontend** (React + Vite) → Vercel (static site)
- **Backend** (FastAPI + InsightFace) → Render (native Python web service)
- **Database** (SQL Server) → Azure SQL Database

The system currently runs entirely on a single Windows machine using Windows Authentication for the database. The cloud deployment requires switching to SQL username/password authentication, making the backend port and host configurable, restricting CORS to the production frontend domain, ensuring InsightFace ONNX models are available on Render's Linux environment, and redirecting CSV file writes to a writable temporary directory.

No new user-facing features are introduced. All changes are configuration, environment, and infrastructure adaptations.

---

## Architecture

```mermaid
graph TD
    subgraph Vercel
        FE[React + Vite SPA<br/>VITE_API_URL → Render URL]
    end

    subgraph Render
        BE[FastAPI + Uvicorn<br/>host=0.0.0.0, port=$PORT]
        MODELS[buffalo_l/ ONNX models<br/>committed to repo]
        TMP[/tmp/ writable directory<br/>CSV output]
    end

    subgraph Azure
        DB[(Azure SQL Database<br/>SQL Authentication)]
    end

    FE -- HTTPS API calls --> BE
    BE -- pyodbc + DB_CONNECTION_STRING --> DB
    BE -- loads at startup --> MODELS
    BE -- writes CSV --> TMP
```

The frontend is a pure static build served by Vercel's CDN. All API calls go to the Render backend URL, configured via `VITE_API_URL` at build time. The backend connects to Azure SQL using a `pyodbc` connection string stored in the `DB_CONNECTION_STRING` environment variable. InsightFace models are committed to the repository and loaded from a path resolved at startup. CSV files are written to `/tmp` (writable on Render) and streamed back to the client.

---

## Components and Interfaces

### 1. Backend — Port and Host Configuration (`main.py`)

**Current state:** `uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)` is hardcoded in the `if __name__ == "__main__"` block. Render injects a `PORT` environment variable and expects the process to bind to it.

**Change:** Read `PORT` from the environment with a fallback of `8000`. The `Procfile` will invoke uvicorn directly (not via `__main__`), so the port must be passed as a CLI argument in the `Procfile`.

**Procfile** (`backend/Procfile`):
```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

**runtime.txt** (`backend/runtime.txt`):
```
python-3.11.9
```

The Python version is chosen to match the project's current development environment and to be compatible with all dependencies (insightface, onnxruntime, pyodbc, torch).

### 2. Backend — Database Connection (`database.py`)

**Current state:** Always uses Windows Authentication (`Trusted_Connection=yes`), reading `SERVER` and `DATABASE` from `.env`.

**Change:** Introduce a `DB_CONNECTION_STRING` environment variable. When set, use it directly as the pyodbc connection string. When absent, fall back to the existing Windows Authentication path for local development.

```python
def get_db_connection() -> pyodbc.Connection:
    conn_str = os.getenv('DB_CONNECTION_STRING')
    if conn_str:
        return pyodbc.connect(conn_str)
    # fallback: Windows Auth (local dev)
    server = os.getenv('SERVER')
    database = os.getenv('DATABASE')
    driver = os.getenv('DRIVER', '{ODBC Driver 17 for SQL Server}')
    connection_string = (
        f"DRIVER={driver};SERVER={server};DATABASE={database};Trusted_Connection=yes;"
    )
    return pyodbc.connect(connection_string)
```

**Azure SQL connection string format** (set as `DB_CONNECTION_STRING` on Render):
```
DRIVER={ODBC Driver 18 for SQL Server};SERVER=<server>.database.windows.net;DATABASE=AttendanceDB;UID=<user>;PWD=<password>;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30
```

Note: Azure SQL requires ODBC Driver 17 or 18. Render's native Python environment includes ODBC Driver 18 for SQL Server via the `msodbcsql18` system package, which must be declared in a `render.yaml` or installed via a build script.

### 3. Backend — CORS Configuration (`main.py`)

**Current state:** `allow_origins=["*"]` is hardcoded.

**Change:** Read `ALLOWED_ORIGINS` from the environment. Parse it as a comma-separated list. Fall back to `["*"]` when not set.

```python
raw_origins = os.getenv('ALLOWED_ORIGINS', '')
allowed_origins = [o.strip() for o in raw_origins.split(',') if o.strip()] or ['*']

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Production value** (set on Render):
```
ALLOWED_ORIGINS=https://your-app.vercel.app
```

### 4. Backend — InsightFace Model Path (`model/insightface_engine.py`)

**Current state:** `FaceAnalysis(name="buffalo_l", providers=providers)` relies on InsightFace's default model root (`~/.insightface/models/`). On Render, the home directory is ephemeral and the models would not be present.

**Change:** Pass an explicit `root` parameter to `FaceAnalysis`, resolved from a `MODEL_ROOT` environment variable with a fallback to the `buffalo_l/` directory at the repository root.

The `buffalo_l/` directory already exists at the workspace root with all five ONNX files. It must be committed to the repository (not in `.gitignore`) so Render includes it in the deployment.

```python
import logging
logger = logging.getLogger(__name__)

def _resolve_model_root() -> str:
    model_root = os.getenv('MODEL_ROOT')
    if model_root:
        resolved = model_root
    else:
        # Default: buffalo_l/ directory at the repo root (one level above backend/)
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        resolved = os.path.join(backend_dir, 'buffalo_l')
        # Also check one level up (repo root) in case CWD is repo root
        repo_root = os.path.dirname(backend_dir)
        candidate = os.path.join(repo_root, 'buffalo_l')
        if os.path.isdir(candidate):
            resolved = candidate

    logger.info(f"[InsightFace] Resolved model root: {resolved}")
    if not os.path.isdir(resolved):
        raise RuntimeError(
            f"InsightFace model directory not found at: {resolved}. "
            f"Set MODEL_ROOT env var or commit buffalo_l/ to the repository."
        )
    return resolved
```

`FaceAnalysis` is then initialised with:
```python
self._app = FaceAnalysis(name="buffalo_l", root=_resolve_model_root(), providers=providers)
```

The `root` parameter in InsightFace's `FaceAnalysis` expects the **parent** directory of the model pack (i.e., the directory that contains `buffalo_l/`). So if `buffalo_l/` is at `/opt/render/project/src/buffalo_l`, then `root` should be `/opt/render/project/src`.

**Revised resolution logic:**
```python
# MODEL_ROOT should point to the PARENT of buffalo_l/
# e.g. MODEL_ROOT=/opt/render/project/src  → loads /opt/render/project/src/buffalo_l/
model_root = os.getenv('MODEL_ROOT', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

On Render, the working directory is the repository root (`/opt/render/project/src`), so the default (parent of `backend/model/`) resolves to the repo root, which contains `buffalo_l/`. This is correct.

### 5. Backend — CSV Generation (`services/csv_service.py`)

**Current state:** Writes to `backend/Attendance Records/` using an absolute path anchored to the `services/` directory. This path is writable locally but may not be writable on Render's read-only filesystem (only `/tmp` is guaranteed writable).

**Change:** Use `/tmp/Attendance Records/` when running on a non-Windows platform, falling back to the existing local path for Windows development.

```python
import platform

def _get_output_dir() -> str:
    if platform.system() == 'Windows':
        # Local dev: write next to the backend directory
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "Attendance Records"
        )
    else:
        # Render (Linux): use /tmp which is always writable
        return "/tmp/Attendance Records"
```

The `download-csv` endpoint in `user.py` already uses `FileResponse`, which streams the file from disk. This works correctly with `/tmp` paths.

### 6. Frontend — API Base URL (`frontend/src/services/api.js`)

**Current state:** `const BASE_URL = import.meta.env.VITE_API_URL || '';` — already reads from the environment variable. No code change needed.

**Vercel environment variable** (set in Vercel dashboard):
```
VITE_API_URL=https://your-backend.onrender.com
```

### 7. Frontend — Vercel Routing (`frontend/vercel.json`)

Vercel serves static files by default. React Router uses client-side routing, so all non-asset requests must be rewritten to `index.html`.

**New file** (`frontend/vercel.json`):
```json
{
  "rewrites": [
    { "source": "/((?!assets/).*)", "destination": "/index.html" }
  ]
}
```

### 8. Azure SQL Migration Script

A new file `azure_migration.sql` at the repository root will contain the full schema creation script adapted for Azure SQL:

- No `USE master` or `CREATE DATABASE` statements
- No `Trusted_Connection` references
- All `IF NOT EXISTS` / `IF OBJECT_ID IS NULL` guards for idempotency
- All tables from `Full Database Query.sql` plus `Lecture_Schedule` from `timetable_setup.sql`
- `GO` batch separators preserved (Azure SQL supports them via SSMS or `sqlcmd`)

### 9. Deployment Guide (`deployment.md`)

A new `deployment.md` at the repository root covering:
- All environment variables (backend and frontend)
- Step-by-step Vercel deployment
- Step-by-step Render deployment
- Azure SQL setup and migration
- Local development setup

---

## Data Models

No new database tables or schema changes are introduced by this feature. The migration script (`azure_migration.sql`) recreates the existing schema on Azure SQL.

### Environment Variables

#### Backend (Render)

| Variable | Required | Example | Description |
|---|---|---|---|
| `DB_CONNECTION_STRING` | Yes (cloud) | `DRIVER={ODBC Driver 18 for SQL Server};SERVER=...` | Full pyodbc connection string for Azure SQL |
| `ALLOWED_ORIGINS` | Yes (cloud) | `https://your-app.vercel.app` | Comma-separated list of allowed CORS origins |
| `PORT` | Injected by Render | `10000` | TCP port for uvicorn to bind to |
| `MODEL_ROOT` | No | `/opt/render/project/src` | Parent directory of `buffalo_l/` model pack |
| `SECRET_KEY` | Yes | `<random 32-byte hex>` | Application secret for token signing |
| `SERVER` | Local dev only | `.\SQLEXPRESS` | SQL Server hostname (Windows Auth fallback) |
| `DATABASE` | Local dev only | `AttendanceDB` | Database name (Windows Auth fallback) |

#### Frontend (Vercel)

| Variable | Required | Example | Description |
|---|---|---|---|
| `VITE_API_URL` | Yes (cloud) | `https://your-backend.onrender.com` | Backend base URL for all axios requests |

### File Locations

| File | Purpose |
|---|---|
| `backend/Procfile` | Render start command |
| `backend/runtime.txt` | Python version declaration |
| `frontend/vercel.json` | Vercel SPA routing rewrite |
| `azure_migration.sql` | Azure SQL schema migration |
| `deployment.md` | Deployment guide |

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Port binding respects PORT environment variable

*For any* value of the `PORT` environment variable (valid port number), the backend server SHALL bind to exactly that port, and when `PORT` is absent the server SHALL bind to port `8000`.

**Validates: Requirements 1.1, 1.2**

---

### Property 2: Database connection string selection

*For any* environment where `DB_CONNECTION_STRING` is set to a non-empty string, the `get_db_connection()` function SHALL use that string directly as the pyodbc connection string and SHALL NOT append `Trusted_Connection=yes`. When `DB_CONNECTION_STRING` is absent, the function SHALL construct a Windows Authentication connection string from `SERVER` and `DATABASE`.

**Validates: Requirements 3.1, 3.2, 3.3**

---

### Property 3: CORS origin filtering

*For any* HTTP request arriving at the backend, if the `Origin` header is present and `ALLOWED_ORIGINS` is set, the response SHALL include `Access-Control-Allow-Origin` only if the request origin appears in the `ALLOWED_ORIGINS` list. When `ALLOWED_ORIGINS` is not set, the response SHALL allow all origins.

**Validates: Requirements 4.1, 4.2, 4.3**

---

### Property 4: InsightFace model path resolution

*For any* value of `MODEL_ROOT` (or its absence), the model path resolution function SHALL return a directory path that contains the `buffalo_l/` subdirectory when the models are present, and SHALL raise a descriptive `RuntimeError` when the resolved directory does not exist.

**Validates: Requirements 6.2, 6.4**

---

### Property 5: CSV output directory selection

*For any* operating system platform, the CSV output directory SHALL be `/tmp/Attendance Records` on non-Windows platforms and the local `backend/Attendance Records/` path on Windows, and the directory SHALL be created if it does not exist before writing.

**Validates: Requirements 8.1, 8.3**

---

### Property 6: Azure SQL migration script idempotency

*For any* Azure SQL database that already contains the AttendanceDB schema, re-running `azure_migration.sql` SHALL complete without errors and SHALL NOT alter existing data or drop existing tables.

**Validates: Requirements 9.4**

---

## Error Handling

### Database Connection Failures

- If `DB_CONNECTION_STRING` is malformed or the Azure SQL server is unreachable, `pyodbc.connect()` raises `pyodbc.Error`. The existing `database_error_handler` in `main.py` catches this and returns HTTP 500 with a descriptive message.
- A startup health check is not added (Render's health check endpoint `/health` already exists and will fail naturally if the DB is unreachable on first request).

### InsightFace Model Not Found

- If the `buffalo_l/` directory is missing at the resolved path, `_resolve_model_root()` raises `RuntimeError` at import time, which causes the Render deployment to fail with a clear log message. This is intentional — a missing model is a fatal misconfiguration.

### CSV Write Failures

- If `/tmp` is not writable (unlikely on Render but possible in edge cases), `open()` raises `OSError`. The `generate_attendance_csv` function already wraps this in a `try/except` and re-raises as `Exception("Failed to write CSV file: ...")`. The `download-csv` endpoint catches this and returns HTTP 500.

### CORS Misconfiguration

- If `ALLOWED_ORIGINS` is set but the Vercel domain is misspelled, the browser will block API calls with a CORS error. This is a configuration error, not a code error. The deployment guide documents the exact format required.

### Request Body Size

- Render's default request body limit is sufficient for most use cases, but batch image uploads can be large. The existing FastAPI/Starlette default is no limit. To enforce the 50 MB requirement from Requirement 7.3, add a `ContentSizeLimitMiddleware` or configure uvicorn's `--limit-concurrency` and `--limit-max-requests`. The simplest approach is to add a middleware:

```python
from starlette.middleware import Middleware
# In main.py, before adding CORSMiddleware:
@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 50 * 1024 * 1024:
        return JSONResponse(
            status_code=413,
            content={"error": "Request body too large. Maximum size is 50 MB."}
        )
    return await call_next(request)
```

---

## Testing Strategy

This feature is primarily infrastructure and configuration adaptation. The changes are:

1. Environment variable reads (pure functions with clear input/output)
2. File path resolution logic (pure functions)
3. Middleware configuration (wiring, not logic)
4. SQL migration script (declarative DDL)

**PBT applicability assessment:** Properties 1–5 involve pure functions (port selection, connection string selection, origin filtering, path resolution, directory selection) that are testable with property-based testing. Property 6 (SQL idempotency) is an integration test against a real or mocked database.

### Unit Tests

Focus on the pure logic functions that are being added or modified:

- `test_database.py`: Add tests for `get_db_connection()` with `DB_CONNECTION_STRING` set vs. unset (mock `pyodbc.connect`)
- `test_main.py`: Add tests for CORS origin parsing from `ALLOWED_ORIGINS` (empty, single value, multiple values, not set)
- `test_insightface_engine.py` (new): Test `_resolve_model_root()` with `MODEL_ROOT` set, unset, and pointing to a non-existent directory
- `test_csv_service.py`: Add tests for `_get_output_dir()` on Windows vs. non-Windows (mock `platform.system()`)

### Property-Based Tests

Use `hypothesis` (already in `requirements.txt`) for the pure functions:

**Property 1 — Port selection:**
```python
@given(port=st.integers(min_value=1, max_value=65535))
def test_port_env_var_respected(port):
    with patch.dict(os.environ, {'PORT': str(port)}):
        assert int(os.getenv('PORT', '8000')) == port
```

**Property 2 — Connection string selection:**
```python
@given(conn_str=st.text(min_size=1))
def test_db_connection_string_used_when_set(conn_str):
    with patch.dict(os.environ, {'DB_CONNECTION_STRING': conn_str}):
        with patch('pyodbc.connect') as mock_connect:
            get_db_connection()
            mock_connect.assert_called_once_with(conn_str)
```

**Property 3 — CORS origin filtering:**
```python
@given(origins=st.lists(st.from_regex(r'https://[a-z]+\.vercel\.app', fullmatch=True), min_size=1, max_size=5))
def test_cors_origins_parsed_correctly(origins):
    env_value = ','.join(origins)
    parsed = [o.strip() for o in env_value.split(',') if o.strip()]
    assert set(parsed) == set(origins)
```

**Property 5 — CSV directory selection:**
```python
@given(platform_name=st.sampled_from(['Windows', 'Linux', 'Darwin']))
def test_csv_dir_selection(platform_name):
    with patch('platform.system', return_value=platform_name):
        result = _get_output_dir()
        if platform_name == 'Windows':
            assert 'Attendance Records' in result
            assert '/tmp' not in result
        else:
            assert result.startswith('/tmp')
```

Each property test is configured to run a minimum of 100 iterations.

Tag format: `# Feature: cloud-deployment, Property {N}: {property_text}`

### Integration Tests

- **Database connectivity**: Verify `get_db_connection()` successfully connects to a real Azure SQL instance using a test `DB_CONNECTION_STRING` (run in CI with secrets, not in unit test suite)
- **Migration script idempotency**: Run `azure_migration.sql` twice against a test Azure SQL database and verify no errors on the second run
- **End-to-end CORS**: Deploy to staging and verify that a request from the Vercel domain succeeds while a request from an unlisted origin is rejected

### Smoke Tests

- Render deployment health check: `GET /health` returns `{"status": "ok"}` after deployment
- InsightFace model load: Backend starts without `RuntimeError` when `buffalo_l/` is present
- Frontend routing: Navigating directly to `/admin` on the Vercel URL returns the React app (not a 404)
