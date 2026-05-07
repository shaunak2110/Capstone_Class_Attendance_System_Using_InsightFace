from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging
import pymssql
import os

# Routers
from auth import router as auth_router
from admin import router as admin_router
from user import router as user_router
from superadmin import router as superadmin_router

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Attendance System",
    version="2.0"
)

# ============================
# ERROR HANDLERS
# ============================

@app.exception_handler(pymssql.IntegrityError)
async def integrity_error_handler(request: Request, exc: pymssql.IntegrityError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"error": "Conflict", "message": str(exc)}
    )


@app.exception_handler(pymssql.Error)
async def database_error_handler(request: Request, exc: pymssql.Error):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Database Error", "message": str(exc)}
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "Validation Error", "details": exc.errors()}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal Server Error"}
    )

# ============================
# CORS
# ============================

raw_origins = os.getenv('ALLOWED_ORIGINS', '')
allowed_origins = [o.strip() for o in raw_origins.split(',') if o.strip()] or ['*']

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================
# MIDDLEWARE
# ============================

@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 50 * 1024 * 1024:
        return JSONResponse(
            status_code=413,
            content={"error": "Request body too large. Maximum size is 50 MB."}
        )
    return await call_next(request)

# ============================
# ROUTERS
# ============================

app.include_router(auth_router)
app.include_router(superadmin_router)
app.include_router(admin_router)
app.include_router(user_router)

# ============================
# HEALTH
# ============================

@app.get("/health")
def health():
    return {"status": "ok"}

# ============================
# RUN
# ============================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', '8000'))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)