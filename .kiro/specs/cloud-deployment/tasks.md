# Tasks: Cloud Deployment

## Task List

- [x] 1. Create Render deployment files
  - [x] 1.1 Create `backend/Procfile` with `web: uvicorn main:app --host 0.0.0.0 --port $PORT`
  - [x] 1.2 Create `backend/runtime.txt` declaring `python-3.11.9`
  - **Validates: Requirements 2.1, 2.2, 2.3**

- [x] 2. Create Vercel routing configuration
  - [x] 2.1 Create `frontend/vercel.json` with a rewrite rule that sends all non-asset requests to `index.html`
  - **Validates: Requirements 5.4, 5.5**

- [x] 3. Fix database connection to support SQL authentication
  - [x] 3.1 Update `backend/database.py`: when `DB_CONNECTION_STRING` env var is set, call `pyodbc.connect(conn_str)` directly; otherwise fall back to the existing Windows Auth path using `SERVER`, `DATABASE`, and `DRIVER`
  - [x] 3.2 Remove the `UID`/`PWD` validation that was added in a prior refactor — the fallback path uses `Trusted_Connection=yes` and does not need those vars
  - [x] 3.3 Write property-based test in `backend/test_database.py`: for any non-empty `DB_CONNECTION_STRING`, `get_db_connection()` must call `pyodbc.connect` with exactly that string and must NOT include `Trusted_Connection=yes`; when `DB_CONNECTION_STRING` is absent, the constructed string must contain `Trusted_Connection=yes` (mock `pyodbc.connect`)
    - **PBT — Validates: Requirements 3.1, 3.2, 3.3**
  - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

- [x] 4. Make CORS origins configurable
  - [x] 4.1 Update `backend/main.py`: read `ALLOWED_ORIGINS` env var, split on commas, strip whitespace, filter empty strings; if the resulting list is empty fall back to `["*"]`; pass the list to `CORSMiddleware`'s `allow_origins`
  - [x] 4.2 Write property-based test in `backend/test_main.py`: for any list of 1–5 valid HTTPS origin strings joined with commas, the parsed `allowed_origins` list must equal the input list (order-insensitive); when `ALLOWED_ORIGINS` is unset the result must be `["*"]`
    - **PBT — Validates: Requirements 4.1, 4.2, 4.3**
  - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**

- [x] 5. Make backend port configurable
  - [x] 5.1 Update the `if __name__ == "__main__"` block in `backend/main.py` to read `PORT` from the environment with a fallback of `8000` and pass it to `uvicorn.run`
  - [x] 5.2 Write property-based test in `backend/test_main.py`: for any integer port in 1–65535 set as the `PORT` env var, `int(os.getenv('PORT', '8000'))` must equal that port; when `PORT` is absent the result must be `8000`
    - **PBT — Validates: Requirements 1.1, 1.2**
  - **Validates: Requirements 1.1, 1.2, 1.3**

- [x] 6. Fix InsightFace model path for Linux/Render
  - [x] 6.1 Add `_resolve_model_root()` function to `backend/model/insightface_engine.py`: read `MODEL_ROOT` env var; if not set, default to the parent directory of `backend/` (i.e., the repo root, which contains `buffalo_l/`); log the resolved path via `logging`; raise `RuntimeError` with a descriptive message if the resolved directory does not exist
  - [x] 6.2 Replace `FaceAnalysis(name="buffalo_l", providers=providers)` with `FaceAnalysis(name="buffalo_l", root=_resolve_model_root(), providers=providers)` in `InsightFaceEngine.__init__`
  - [x] 6.3 Fix `_onnx_cuda_available()` to be cross-platform: replace the `ctypes.WinDLL(...)` call with a platform-agnostic check — on non-Windows, skip the DLL load and return `False` if `CUDAExecutionProvider` is not in `ort.get_available_providers()`
  - [x] 6.4 Create `backend/test_insightface_engine.py` with unit tests for `_resolve_model_root()`: (a) when `MODEL_ROOT` points to an existing directory, return that path; (b) when `MODEL_ROOT` is unset and `buffalo_l/` exists at the repo root, return the repo root; (c) when the resolved path does not exist, raise `RuntimeError` containing the missing path
  - **Validates: Requirements 6.1, 6.2, 6.3, 6.4**

- [x] 7. Fix CSV output directory for Render
  - [x] 7.1 Add `_get_output_dir()` function to `backend/services/csv_service.py`: return `/tmp/Attendance Records` on non-Windows platforms (using `platform.system()`), and the existing `backend/Attendance Records/` absolute path on Windows
  - [x] 7.2 Replace the hardcoded `directory` assignment in `generate_attendance_csv` with a call to `_get_output_dir()`
  - [x] 7.3 Write property-based test in `backend/test_csv_service.py`: for each of `['Windows', 'Linux', 'Darwin']` (mocking `platform.system`), `_get_output_dir()` must return a path containing `Attendance Records`; on non-Windows it must start with `/tmp`; on Windows it must not contain `/tmp`
    - **PBT — Validates: Requirements 8.1, 8.3**
  - **Validates: Requirements 8.1, 8.2, 8.3**

- [x] 8. Add request body size limit middleware
  - [x] 8.1 Add an `@app.middleware("http")` function `limit_body_size` in `backend/main.py` that reads the `Content-Length` header and returns HTTP 413 with `{"error": "Request body too large. Maximum size is 50 MB."}` when the value exceeds 50 × 1024 × 1024 bytes; requests without a `Content-Length` header pass through unchanged
  - [x] 8.2 Add unit tests in `backend/test_main.py` verifying: (a) a request with `Content-Length: 52428801` returns 413; (b) a request with `Content-Length: 52428800` (exactly 50 MB) passes through; (c) a request with no `Content-Length` header passes through
  - **Validates: Requirement 7.3**

- [x] 9. Create Azure SQL migration script
  - [x] 9.1 Create `azure_migration.sql` at the repository root containing idempotent `CREATE TABLE IF NOT EXISTS` (or `IF OBJECT_ID IS NULL` pattern) statements for all tables: `Login_Master`, `User_Master`, `Student_Master`, `Student_Embeddings`, `Lecture_Master`, `Request_Master`, `Attendance_Record`, and `Schedules`
  - [x] 9.2 Ensure the script has no `USE master`, `CREATE DATABASE`, or `Trusted_Connection` references
  - [x] 9.3 Preserve all foreign key constraints, unique constraints, check constraints, and indexes from the original schema in `Full Database Query.sql` and `timetable_setup.sql`
  - [x] 9.4 Include the `Schedules` table with its foreign key to `Login_Master` (from `timetable_setup.sql`)
  - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 11.1, 11.2**

- [x] 10. Create deployment guide
  - [x] 10.1 Create `deployment.md` at the repository root with sections: (a) all backend env vars (`DB_CONNECTION_STRING`, `ALLOWED_ORIGINS`, `PORT`, `MODEL_ROOT`, `SECRET_KEY`, `SERVER`, `DATABASE`) with descriptions and example values; (b) frontend env var (`VITE_API_URL`); (c) step-by-step Vercel deployment; (d) step-by-step Render deployment; (e) Azure SQL setup and migration; (f) local development setup
  - **Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7**
